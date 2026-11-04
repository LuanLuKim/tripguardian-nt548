"""Final check (docs/ARCHITECTURE.md §11): the only place that decides whether a plan passes.

It re-derives every check from the finished timeline instead of trusting what simulate() noticed, so a bug in the
scheduler cannot also hide from the check. Fail-closed: a violation is reported, never repaired here.
"""

from dataclasses import replace
from datetime import date, datetime, timedelta

from requirements import allowed, hard_result

from . import diet, pets
from .conditions import hazard
from .feature_ontology import ontology
from .lodging import price_cap
from .model import DayResult, Violation
from .roles import ROLE_SLOTS, takes_meal_slot
from .schedule import DayCtx, intervals_for, meal_floor, meals_needed, pin_hostable, pin_window
from .cache import day_key, fingerprint, put, travel_key
from .settings import Settings
from .stayprice import age_h


def _is_physical(feature: str) -> bool:
    f = ontology().features.get(feature)
    return f is not None and f.group == "effort"


def _released(cx: DayCtx, r: DayResult) -> DayCtx:
    """The day as the scheduler laid it out: a place whose time-of-day pin it gave up (and said so) is not held to it.
    Without this, a plan shown as valid would fail the same check at confirm."""
    return release(cx, r.unpinned)


def release(cx: DayCtx, ids) -> DayCtx:
    """The day with the given places no longer held to their time of day."""
    if not ids:
        return cx
    return replace(cx, places={**cx.places, **{i: replace(cx.places[i], pins=()) for i in ids if i in cx.places}})


def _road_gaps(cx: DayCtx, items: list) -> list[Violation]:
    """The person cannot be in two places without a road between them: from the day's start node every visit and every
    leg must begin where the previous one ended, and a day with visits ends at its end node. Re-derived from the
    timeline alone (a leg's length is checked apart, in `validate`). Rests, waits and meal blocks stay where they are."""
    d, out = cx.day, []
    at, until = d.start_node, 0
    for it in items:
        overlapped, until = it.start < until, max(until, it.end)     # an overlap is reported once, as an overlap
        if overlapped and it.kind in {"travel", "visit"}:
            at = it.to_id if it.kind == "travel" and it.to_id is not None else it.place_id if it.kind == "visit" else at
            continue
        if it.kind == "travel":
            if at is not None and it.from_id is not None and it.from_id != at:
                out.append(Violation("travel", d.index, it.to_id, 0, False, "the road does not start where the day is"))
            at = it.to_id if it.to_id is not None else at
        elif it.kind == "visit":
            if at is not None and it.place_id != at:
                out.append(Violation("travel", d.index, it.place_id, 0, False, "no road to this visit"))
            at = it.place_id
    if out or at is None or d.end_node is None or at == d.end_node or not any(it.kind == "visit" for it in items):
        return out
    return [Violation("travel", d.index, None, 0, False, "no road back to where the day ends")]


# The trip's budget never blocks or trims a plan (owner 04/11: the budget is the whole trip's, the plan says what pushes
# it over and the user decides): the engine passes this instead of budget_vnd, and budget_warnings tells the user.
NO_BUDGET_CAP = None


def budget_warnings(ctxs, results, budget_vnd: int | None) -> list[dict]:
    """One line per day whose estimated spend per person runs over budget_vnd (VND per person per day, Trip's
    scalar): by how much, and the stops that cost the most, so the user can drop or swap one of them."""
    if not budget_vnd:
        return []
    out = []
    for cx, r in zip(ctxs, results):
        costs = [(cx.places[i.place_id].cost_vnd or 0, cx.places[i.place_id].name) for i in r.items if i.kind == "visit"]
        spend = sum(c for c, _ in costs)
        if spend <= budget_vnd:
            continue
        top = ", ".join(f"{name} (~{c // 1000}k)" for c, name in sorted(costs, reverse=True)[:2] if c)
        out.append({"code": "budget_over", "day": cx.day.index, "minutes": 0,
                    "text": f"Ngày {cx.day.index + 1}: chi phí ước tính ~{spend // 1000}k/người, vượt ngân sách "
                            f"{budget_vnd // 1000}k khoảng {(spend - budget_vnd) // 1000}k"
                            + (f"; tốn nhất: {top}. Bạn có thể bỏ hoặc đổi một nơi." if top else ".")})
    return out


def validate(ctxs: list[DayCtx], results: list[DayResult], hard_filters: list, anchors: set,
             budget_vnd: int | None, max_leg_min: int | None, *, day_cache: dict | None = None,
             cache_limit: int = 128) -> list[Violation]:
    if day_cache is not None:
        out, visited = [], {}
        for cx, result in zip(ctxs, results):
            day_visited = {i.place_id for i in result.items if i.kind == "visit"}
            travel_nodes = {node for i in result.items if i.kind == "travel" for node in (i.from_id, i.to_id)
                            if node is not None}
            key = fingerprint((day_key(cx, day_visited), travel_key(cx.travel, travel_nodes), result,
                               hard_filters, budget_vnd, max_leg_min))
            if key not in day_cache:
                put(day_cache, key, validate([cx], [result], hard_filters, set(), budget_vnd, max_leg_min), cache_limit)
            out.extend(day_cache[key])
            for pid in day_visited:
                if pid in visited:
                    out.append(Violation("duplicate", cx.day.index, pid, 0, False, "the place is scheduled twice"))
                visited[pid] = cx.day.index
        for pid in sorted(anchors - set(visited)):
            out.append(Violation("anchor", None, pid, 0, False, "an anchor is not in the plan"))
        return out
    out: list[Violation] = []
    visited: dict = {}
    for cx, r in zip(ctxs, results):
        cx = _released(cx, r)
        d = cx.day
        items = sorted(r.items, key=lambda i: (i.start, i.end))
        for a, b in zip(items, items[1:]):
            if b.start < a.end:
                out.append(Violation("overlap", d.index, b.place_id or a.place_id, a.end - b.start, False,
                                     f"{a.kind} and {b.kind} overlap"))
        for a, b, kind, label, _ in d.busy:         # the user's fixed times are theirs (user hard)
            for it in items:
                if it.kind in {"visit", "travel"} and it.start < b and a < it.end:
                    out.append(Violation("busy", d.index, it.place_id or it.to_id, min(b, it.end) - max(a, it.start),
                                         False, f"overlaps {label}"))
        last_end = max((it.end for it in items), default=None)
        if d.depart_by is not None and last_end is not None and last_end > d.depart_by:     # whatever the window says
            out.append(Violation("departure", d.index, None, last_end - d.depart_by, True, "misses the departure"))
        cap = (cx.cfg.realistic or {}).get("drive_day_min")
        drive = sum(cx.travel.leg(i.from_id, i.to_id)[0] for i in items if i.kind == "travel")
        if cap and drive > cap:
            out.append(Violation("drive_day", d.index, None, drive - cap, False, f"over {cap} min of driving"))
        if items and items[-1].end > d.end:
            out.append(Violation("day_window", d.index, None, items[-1].end - d.end, False, "the day runs past its end"))
        if items and items[0].start < d.start:
            out.append(Violation("day_window", d.index, None, d.start - items[0].start, False, "starts before the day"))
        out.extend(_road_gaps(cx, items))
        spend = 0
        requirements = pets.filters({'hard_filters': hard_filters, 'context': {'companions': ['pet'] if cx.pet else []}})
        meal_slots = set()
        for it in items:
            if it.kind == 'meal_free':
                # A free meal on a diet day names no place, so nothing failed: diet.warnings tells the user and the
                # slot's faded suggestions are verified options (owner 04/11: unknown is shown and warned, not blocked).
                window = cx.cfg.meal_windows.get(it.name)
                if window and window[0] <= it.start <= window[1] and it.end - it.start >= meal_floor(it.name, cx):
                    if it.name in meal_slots:
                        out.append(Violation('meal_window', d.index, None, 0, False, 'the meal is scheduled twice'))
                    meal_slots.add(it.name)
                else:
                    out.append(Violation('meal_window', d.index, None, 0, False, 'invalid free meal block'))
            if it.kind == "travel":
                need = cx.travel.leg(it.from_id, it.to_id)[0]
                if it.end - it.start < need:
                    out.append(Violation("travel", d.index, it.to_id, need - (it.end - it.start), False,
                                         "shorter than the travel time"))
                if max_leg_min and need > max_leg_min:      # the road, not the buffer that rides on it
                    out.append(Violation("long_leg", d.index, it.to_id, need - max_leg_min, False,
                                         f"longer than {max_leg_min} min"))
            if it.kind != "visit":
                continue
            p = cx.places[it.place_id]
            if cx.require_meals and it.end - it.start < p.visit["short"]:
                out.append(Violation("visit_duration", d.index, p.id, p.visit["short"] - (it.end - it.start), False,
                                     "visit shorter than the minimum estimate"))
            if takes_meal_slot(p):
                names = list(cx.cfg.meal_windows)[:cx.cfg.meals_per_day]
                slot = next((name for name in names if name not in meal_slots
                             and name in ROLE_SLOTS.get(p.meal_kind, names)
                             and cx.cfg.meal_windows[name][0] <= it.start <= cx.cfg.meal_windows[name][1]), None)
                if slot is None:
                    out.append(Violation('meal_window', d.index, p.id, 0, False, 'no distinct meal window for this visit'))
                else:
                    meal_slots.add(slot)
            if not any(o <= it.start and it.end <= c for o, c in intervals_for(p, cx)):
                out.append(Violation("hours", d.index, p.id, 0, False, "visit outside the opening hours"))
            if why := hazard(p, cx.cond):
                out.append(Violation("hazard", d.index, p.id, 0, False, f"hazard that day: {why}"))
            if p.start_time is not None and it.start != p.start_time:
                out.append(Violation("start_time", d.index, p.id, abs(it.start - p.start_time), False,
                                     "does not start at the requested time"))
            lo, hi = pin_window(p, cx)
            # a time of day this day cannot reach at all (a sunset lake moved to a morning-only last day) is a wish
            # given up and told (pin_warnings), not a conflict the user must undo
            if not lo <= it.start <= hi and pin_hostable(p, cx):
                out.append(Violation("timed", d.index, p.id, 0, False, "off the time of day its feature needs"))
            if p.id in visited:
                out.append(Violation("duplicate", d.index, p.id, 0, False, "the place is scheduled twice"))
            visited[p.id] = d.index
            spend += p.cost_vnd or 0
            for rule in cx.diet_days:
                if diet.result(p, rule) == "fail":        # evidence it has no such dish; unknown only warns
                    out.append(Violation("hard", d.index, p.id, 0, False, diet.explanation(rule)))
            for hf in requirements:
                if (hf["feature"] == 'pets' or hf["feature"] not in p.relaxed) \
                        and not allowed(p.rec, hf, p.activity, p.kind):
                    verdict = hard_result(p.rec, hf, p.activity, p.kind)[0]
                    out.append(Violation("hard", d.index, p.id, 0, _is_physical(hf["feature"]),
                                         f'{hf["feature"]} {"==" if hf["op"] == "eq" else "!="} {hf["value"]}: {verdict}'))
        if cx.require_meals and any(it.kind == "visit" for it in items):
            for name in meals_needed(items, cx):
                out.append(Violation('meal_missing', d.index, None, 0, False, f'missing {name}'))
        if budget_vnd and spend > budget_vnd:
            out.append(Violation("budget", d.index, None, spend - budget_vnd, False,
                                 f"{spend} VND per person against {budget_vnd}"))
    for pid in sorted(anchors - set(visited)):
        out.append(Violation("anchor", None, pid, 0, False, "an anchor is not in the plan"))
    return out


def lodging_budget(context: dict, lodging: dict | None, cfg: Settings, now: datetime | None = None) -> dict | None:
    """The lodging cost line of the budget check, apart from the places' per-day spend: one row per night with the price
    the plan is using (`price_kind` "dated" = seen for the trip's own stay, "reference" = Maps' list price, None = not
    known), how old it is, and how far it is over the lodging share of the budget (`per_night_cap_vnd`, the same cap the
    candidates were filtered with). Over budget is information for the user: it never fails a check or drops a stop.
    Unknown price or budget -> None fields and `over_budget` None (unknown is not "within"). None when there is no
    lodging or no night to pay for."""
    from trip import nights as stay_nights

    n = stay_nights(context)
    if not lodging or n <= 0:
        return None
    price, kind = lodging.get("price_vnd"), lodging.get("price_kind")
    age = age_h(lodging.get("price_at"), now) if price is not None else None
    cap = price_cap(context, n, cfg)
    try:
        first = date.fromisoformat(str(context.get("start_date")))
    except ValueError:
        first = None
    over = None if price is None or cap is None else max(price - cap, 0)
    rows = [{"night": i + 1, "date": (first + timedelta(days=i)).isoformat() if first else None, "price_vnd": price,
             "price_kind": kind if price is not None else None, "price_age_h": age, "over_vnd": over} for i in range(n)]
    return {"nights": rows, "total_vnd": price * n if price is not None else None, "per_night_cap_vnd": cap,
            "over_budget": None if over is None else over > 0, "over_vnd": None if over is None else over * n}
