"""D.3, the evening check before each trip day (docs/PLANNING.md §Đổi lịch tối trước ngày đi).

New factors (hourly weather at each stop, closures, notices on pass legs, peak events, a new day window) times what
each stop is sensitive to (from its own features, never asked of a model) give one level per stop:
0 nothing · 1 a note · 2 worth changing (offer options, default keep) · 3 cannot go (pick a replacement, maybe drop).
Missing data is no cause: an unknown forecast is never an alarm. Pure here; I/O is in gather().
"""

from dataclasses import dataclass, field

from corpus.serving import feature

from .expert import doubts
from .placename import short_name
from .settings import Settings, to_min

CLEAR_SKY = ("cloud_hunting", "sunset_view", "scenic_view", "fog_blocks_view")
SLOPE = ("steep_or_stairs", "rough_road_access")
WEATHER = ("rain", "storm", "wind", "fog", "slippery", "pass")
REASON = {"rain": "rain", "wind": "rain", "storm": "rain", "crowd": "crowd", "notice": "advisory", "closed": "hours"}


@dataclass(frozen=True)
class Factors:
    """Everything new about one trip day. weather: place id -> live.weather_hourly answer (None = unknown);
    passes: place id -> pass steps on the leg into it; closed: place id -> {"text", "source", "retrieved_at"};
    window: the day's ("HH:MM", "HH:MM") after a changed arrival / departure; known: (place id, backup reason) the
    plan already flagged at confirm."""
    date: str
    weather: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    notices: list = field(default_factory=list)
    passes: dict = field(default_factory=dict)
    closed: dict = field(default_factory=dict)
    window: tuple | None = None
    window_source: str = "user"
    crowd_averse: bool = False
    known: frozenset | set = frozenset()
    holiday: str | None = None          # CalendarDay holiday name, or an events.yaml period with closure_risk
    normal: dict | None = None          # ClimateNormal of the day's month ({"rain_prob", ...}); None = unknown


def _value(rec: dict, fid: str) -> str | None:
    f = feature(rec, fid)
    return f["value"] if f else None


def sensitivity(rec: dict) -> set[str]:
    """exposed | sheltered (from weather_exposed, else setting), clear_sky, slope, crowd."""
    out = set()
    w, s = _value(rec, "weather_exposed"), _value(rec, "setting")
    if w == "present" or (w is None and s == "outdoor"):
        out.add("exposed")
    elif w == "sheltered" or (w is None and s == "indoor"):
        out.add("sheltered")
    if any(_value(rec, f) == "present" for f in CLEAR_SKY):
        out.add("clear_sky")
    if any(_value(rec, f) == "present" for f in SLOPE):
        out.add("slope")
    if _value(rec, "crowd") == "high":
        out.add("crowd")
    return out


def _hours(start: int, end: int) -> list[int]:
    return [h for h in range(24) if h * 60 < end and (h + 1) * 60 > start]


def _sky(w: dict | None, hours: list[int]) -> dict | None:
    """Worst of the window: max rain chance, rain sum, max gust, any storm / fog / disagreement. None when the
    forecast says nothing about these hours."""
    rows = [((w or {}).get("hours") or {}).get(h) for h in hours]
    rows = [r for r in rows if r and any(r.get(k) is not None for k in ("rain_prob", "rain_mm", "storm", "fog", "gust_kmh"))]
    if not rows:
        return None
    def mx(k):
        vals = [r[k] for r in rows if r.get(k) is not None]
        return max(vals) if vals else None
    mm = [r["rain_mm"] for r in rows if r.get("rain_mm") is not None]
    return {"prob": mx("rain_prob"), "mm": round(sum(mm), 1) if mm else None, "gust": mx("gust_kmh"),
            "storm": any(r.get("storm") for r in rows), "fog": any(r.get("fog") for r in rows),
            "disagree": any(r.get("disagree") for r in rows),
            "agreed": all(r.get("disagree") is False for r in rows),     # both models answered and are close
            "source": w.get("source"), "at": w.get("fetched_at")}


def _span(hours: list[int]) -> str:
    return f"{hours[0]}–{hours[-1] + 1}h" if hours else ""


def _rain_text(sky: dict, hours: list[int]) -> str:
    """For a person: what and when. The source and the time it was read stay in the cause's own fields."""
    what = f"dự báo mưa {round(sky['prob'] * 100)}%" if sky["prob"] is not None else "dự báo có mưa"
    return f"{what} lúc {_span(hours)}".strip()


def _within(lat, lng, notice: dict) -> bool:
    from .travel import km
    if notice.get("lat") is None or notice.get("radius_km") is None:
        return notice.get("scope") == "city"
    return km((lat, lng), (notice["lat"], notice["lng"])) <= notice["radius_km"]


def assess(itinerary_day: dict, records: dict, f: Factors, cfg: Settings) -> list[dict]:
    """One row per visit of the day: {day, date, place_id, name, start, end, level, causes}. A cause is
    {factor, level, text, source, retrieved_at, key}; level = the worst cause (0 with none)."""
    e, cond = cfg.eve_replan, cfg.conditions
    out = []
    for it in itinerary_day.get("items") or []:
        if it.get("kind") != "visit" or not it.get("place_id"):
            continue
        pid, rec = it["place_id"], records.get(it["place_id"]) or {}
        start, end = to_min(it["start"]), to_min(it["end"])
        sens, causes = sensitivity(rec), []

        def add(factor, level, text, source, at):
            if (pid, REASON.get(factor)) in f.known and level == 2:
                level = 1          # already on the plan the user confirmed: a note, not a new alarm
            causes.append({"factor": factor, "level": level, "text": text, "source": source, "retrieved_at": at,
                           "key": f"{factor}:{pid}:{f.date}"})

        win = _hours(start, end)
        sky = _sky(f.weather.get(pid), win)
        if sky:
            far = (f.normal or {}).get("rain_prob") is not None and sky["prob"] is not None and \
                abs(sky["prob"] - f.normal["rain_prob"]) >= cfg.expert["gate"]["normal_gap"]
            # the models disagree, or the chance is far from the month's normal and the models do not both confirm it:
            # not a firm forecast, a note at most (both models agreeing on an unusual day still alerts)
            cap = 1 if sky["disagree"] or (far and not sky["agreed"]) else 3
            wet = (sky["prob"] or 0) >= e["rain_prob"] and (sky["mm"] or 0) >= e["rain_mm"]
            light = (sky["prob"] or 0) >= e["light_prob"] or (sky["mm"] or 0) > 0
            day_mm = (_sky(f.weather.get(pid), list(range(24))) or {}).get("mm") or 0
            if "exposed" in sens:
                if sky["storm"] or day_mm >= cond["severe_rain_mm"] or (sky["gust"] or 0) >= cond["severe_gust_kmh"]:
                    add("storm", min(3, cap), ("dự báo có dông, " + _rain_text(sky, win).removeprefix("dự báo ") if sky["storm"]
                                           else _rain_text(sky, win)), sky["source"], sky["at"])
                elif wet:
                    add("rain", min(2, cap), _rain_text(sky, win), sky["source"], sky["at"])
                elif (sky["gust"] or 0) >= cond["heavy_gust_kmh"]:
                    add("wind", min(2, cap), f"gió giật tới {sky['gust']:g} km/h lúc {_span(win)}", sky["source"], sky["at"])
                elif light:
                    add("rain", 1, _rain_text(sky, win), sky["source"], sky["at"])
            elif wet or sky["storm"]:
                add("rain", 1, _rain_text(sky, win), sky["source"], sky["at"])   # sheltered or unknown: a note
            if "clear_sky" in sens and sky["fog"]:
                add("fog", min(2, cap), f"dự báo sương mù lúc {_span(win)}, khó thấy cảnh", sky["source"], sky["at"])
            elif "clear_sky" in sens and wet:
                add("rain", min(2, cap), _rain_text(sky, win), sky["source"], sky["at"])
            if "slope" in sens and wet:
                add("slippery", min(2, cap), "lối dốc, bậc thang dễ trơn: " + _rain_text(sky, win), sky["source"], sky["at"])
        for step in f.passes.get(pid) or []:
            hit = next((n for n in f.notices for lat, lng in step["coords"] if _within(lat, lng, n)), None)
            if hit:
                add("pass", 3 if hit.get("severity") == "severe" else 2, f"{hit.get('title')} trên {step['name']}",
                    hit.get("source"), hit.get("retrieved_at"))
                continue
            lead = _sky(f.weather.get(pid), _hours(start - 60 * e["lead_h"], start))
            if lead and not lead["disagree"] and ((lead["prob"] or 0) >= e["rain_prob"] and (lead["mm"] or 0) >= e["rain_mm"]
                                                  or lead["storm"]):
                add("pass", 2, f"qua {step['name']}: " + _rain_text(lead, _hours(start - 60 * e["lead_h"], start)),
                    lead["source"], lead["at"])
        ident = rec.get("identity") or {}
        for n in f.notices:
            if n.get("severity") == "severe" and ident.get("lat") is not None and _within(ident["lat"], ident["lng"], n):
                add("notice", 3, n.get("title") or "cảnh báo trong vùng", n.get("source"), n.get("retrieved_at"))
        peak = next((ev for ev in f.events if ev.get("crowd") == "peak"), None)
        busy = "crowd" in sens or any(v >= cfg.crowd_busy_pct for v in
                                      ((rec.get("operation") or {}).get("crowd_by_time") or {}).get("holiday", {}).values())
        if peak and busy:
            add("crowd", 2 if f.crowd_averse else 1, f"{peak.get('name')}: chỗ này sẽ rất đông", peak.get("source"), None)
        hours = (rec.get("operation") or {}).get("hours") or {}
        if f.holiday and hours.get("status") != "VERIFIED":
            add("holiday", 1, f"Dịp {f.holiday}: giờ mở cửa có thể khác, nên gọi hỏi trước", "calendar", None)
        if pid in f.closed:
            c = f.closed[pid]
            add("closed", 3, c.get("text") or "đóng cửa", c.get("source"), c.get("retrieved_at"))
        if f.window and (start < to_min(f.window[0]) or end > to_min(f.window[1])):
            add("window", 3, f"giờ đến / đi đã đổi, ngày chỉ còn {f.window[0]}–{f.window[1]}", f.window_source, None)
        causes.sort(key=lambda c: -c["level"])
        out.append({"day": itinerary_day.get("day"), "date": itinerary_day.get("date") or f.date, "place_id": pid,
                    "name": short_name(it.get("name") or _name(records, pid)), "start": it["start"], "end": it["end"],
                    "level": max((c["level"] for c in causes), default=0), "causes": causes})
    return out


# ---------- minimal repair ----------

def _start(itinerary: list[dict], pid: str) -> str:
    return next((i["start"] for d in itinerary for i in d.get("items") or [] if i.get("place_id") == pid), "")


def _visits(day: dict) -> list[str]:
    return [i["place_id"] for i in day.get("items") or [] if i.get("kind") == "visit" and i.get("place_id")]


def _slots(itinerary: list[dict]) -> dict[str, tuple[int, int]]:
    return {i["place_id"]: (d["day"], to_min(i["start"])) for d in itinerary for i in d.get("items") or []
            if i.get("kind") == "visit" and i.get("place_id")}


def _lcs(a: list[str], b: list[str]) -> set[str]:
    """The stops of a longest common subsequence: the ones that kept their order relative to each other."""
    t = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            t[i][j] = t[i + 1][j + 1] + 1 if a[i] == b[j] else max(t[i + 1][j], t[i][j + 1])
    keep, i, j = set(), 0, 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            keep.add(a[i])
            i, j = i + 1, j + 1
        elif t[i + 1][j] >= t[i][j + 1]:
            i += 1
        else:
            j += 1
    return keep


def changed(old: list[dict], new: list[dict]) -> list[str]:
    """Stops the option itself changes: left or joined the plan, moved to another day, or moved in the order of
    their day. A stop whose clock only follows a neighbour's move is not counted (see shifted)."""
    a, b = _slots(old), _slots(new)
    out = {p for p in set(a) | set(b) if p not in a or p not in b or a[p][0] != b[p][0]}
    for d in {v[0] for v in a.values()}:
        x = [p for p in sorted(a, key=lambda p: a[p][1]) if a[p][0] == d and p in b and b[p][0] == d]
        y = [p for p in sorted(b, key=lambda p: b[p][1]) if b[p][0] == d and p in x]
        out |= set(x) - _lcs(x, y)
    return sorted(out)


def shifted(old: list[dict], new: list[dict], min_shift: int) -> list[str]:
    """Stops that stay on their day but start at least min_shift minutes earlier or later."""
    a, b = _slots(old), _slots(new)
    return sorted(p for p in a if p in b and a[p][0] == b[p][0] and abs(a[p][1] - b[p][1]) >= min_shift)


def levels(itinerary: list[dict], records: dict, factors: dict, cfg: Settings) -> dict[str, dict]:
    """place id -> its assess row, over every day that has factors."""
    return {r["place_id"]: r for d in itinerary if d.get("date") in factors
            for r in assess(d, records, factors[d["date"]], cfg)}


def _name(records: dict, pid: str) -> str:
    return short_name(((records.get(pid) or {}).get("identity") or {}).get("name")) or pid


def repair(trial, itinerary: list[dict], target: dict, factors: dict, records: dict, cfg: Settings,
           pool: list[str], must: set[str], shared: dict | None = None) -> list[dict]:
    """Options for one stop at level 2-3, tried in order and each through trial(actions) (the engine's validator)
    plus a fresh assess with the new factors: 0 (a changed day window only) the same stops laid out again inside it,
    0b (same cause) the smallest set of stops that cannot fit the window dropped together ("trim"), 1 shift within its day, 2 swap with an unaffected stop of another day
    still to come, 3 a look-alike from backup_pool (sheltered first), and for level 3 dropping it. A must-go place
    is only moved, never replaced or dropped. At most one option per kind (the fewest changed stops); level 2 ends
    with "keep" (the default). Any failure rejects that option: nothing unchecked is offered."""
    e = cfg.eve_replan
    pid, k, date = target["place_id"], target["day"] - 1, target["date"]
    before = levels(itinerary, records, factors, cfg)
    budget = [e["max_trials"]]

    def check(actions: list[dict], fresh: str | None = None):
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        try:
            out = trial(actions)
        except Exception:
            return None
        if not out.get("confirmable"):
            return None
        after = levels(out["itinerary"], records, factors, cfg)
        for q, row in after.items():
            if q in (pid, fresh):
                if row["level"] >= 2:
                    return None
            elif row["level"] >= 2 and (before.get(q) or {}).get("level", 0) < 2:
                return None
        return out

    def best(kind: str, tries: list[tuple[list[dict], str | None, str]]) -> dict | None:
        found = []
        for actions, fresh, text in tries:
            out = check(actions, fresh)
            if out is not None:
                moved = changed(itinerary, out["itinerary"])
                later = shifted(itinerary, out["itinerary"], e["min_shift_min"])
                found.append((len(moved), len(later), moved, later, actions, text, out, fresh))
        if not found:
            return None
        _, _, moved, later, actions, text, out, fresh = min(found, key=lambda x: x[:2])
        text = text(out["itinerary"]) if callable(text) else text
        return {"id": f"{kind}:{pid}", "kind": kind, "actions": actions, "changed": moved, "shifted": later,
                "text": text, "place": fresh or pid, "itinerary": out["itinerary"]}

    name, options = _name(records, pid), []
    day = next(d for d in itinerary if d["day"] == target["day"])
    order = _visits(day)
    i = order.index(pid)
    shifts = []
    for j in range(len(order)):
        if j != i:
            new = order[:i] + order[i + 1:]
            new.insert(j, pid)
            shifts.append(([{"type": "reorder", "day": k, "order": new}], None,
                           lambda it: f"Đi {name} lúc {_start(it, pid)} thay vì {target['start']}"))
    swaps = []
    sky_cause = any(c["factor"] in WEATHER for c in target["causes"] if c["level"] >= 2)
    for d in itinerary:
        if d["day"] == target["day"] or not d.get("date") or d["date"] < date or d["date"] not in factors:
            continue
        if sky_cause and factors[d["date"]].weather.get(pid) is None:
            continue           # that day's sky over this stop is unknown: moving there would only be a guess
        for q in _visits(d):
            if (before.get(q) or {}).get("level", 0) < 2:
                swaps.append(([{"type": "move_place", "place": pid, "day": d["day"] - 1},
                               {"type": "move_place", "place": q, "day": k}], None,
                              f"Đi {name} vào ngày {d['day']}, ngày {target['day']} đi {_name(records, q)}"))
    subs = []
    if pid not in must:
        shelter = sorted(pool, key=lambda b: "sheltered" not in sensitivity(records.get(b) or {}))
        subs = [([{"type": "swap", "place": pid, "with": b}], b, f"Ghé {_name(records, b)}{' (có mái che)' if 'sheltered' in sensitivity(records.get(b) or {}) else ''}"
                                       f" thay cho {name}")
                for b in shelter if b != pid]
    win = factors[date].window
    windowed = bool(win) and any(c["factor"] == "window" for c in target["causes"])
    if windowed:
        # The day's window itself moved. What fits is a property of the day, not of one stop, so it is worked out once
        # per day (shared across the day's asks) and each stop only keeps the options that clear it.
        day_opts = (shared if shared is not None else {}).setdefault(("window", date), None)
        if day_opts is None:
            day_opts = []
            if opt := best("relay", [([{"type": "reorder", "day": k, "order": order}], None,
                                      f"Xếp lại ngày {target['day']} trong khung {win[0]}–{win[1]}")]):
                day_opts.append(opt)
            cannot = [q for q in order if (before.get(q) or {}).get("level", 0) >= 3 and q not in must]
            for n in range(1, len(cannot) + 1):       # fewest stops first; the first set the validator accepts wins
                names = ", ".join(_name(records, q) for q in cannot[:n])
                if opt := best("trim", [([{"type": "drop_place", "place": q} for q in cannot[:n]], None,
                                         f"Bỏ {names} vì không kịp trong khung {win[0]}–{win[1]}")]):
                    day_opts.append(opt)
                    break
            if shared is not None:
                shared[("window", date)] = day_opts
        for opt in day_opts:
            if (levels(opt["itinerary"], records, factors, cfg).get(pid) or {}).get("level", 0) < 2:
                options.append({**opt, "id": f"{opt['kind']}:{pid}", "place": pid})
    # a within-day shift cannot clear a window that moved: relay above is the same move, done properly
    for kind, tries in (("shift", [] if windowed else shifts), ("swap_day", swaps), ("backup", subs)):
        opt = best(kind, tries)
        if opt:
            options.append(opt)
    if target["level"] >= 3 and pid not in must and not windowed:
        opt = best("drop", [([{"type": "drop_place", "place": pid}], None, f"Bỏ {name} khỏi lịch ngày {target['day']}")])
        if opt:
            options.append(opt)
    if target["level"] == 2:
        options.append({"id": f"keep:{pid}", "kind": "keep", "actions": [], "changed": [], "shifted": [],
                        "text": "Giữ nguyên lịch", "place": pid,
                        "itinerary": itinerary})
    return options


# ---------- one evening ----------

def check(itinerary: list[dict], records: dict, factors: dict, cfg: Settings, trial, *, today: str,
          previous: dict | None, pool: list[str], must: set[str]) -> dict:
    """The check on the evening of `today` for the next eve_replan.note_days trip days. Only tomorrow
    (notify_days) is asked about, and only for a stop whose level rose since the previous check of this plan to
    2-3 for a cause the user has not declined; later days and level 1 are notes. {"ask": [{date, place_id, name,
    level, cause, options}], "notes": [rows], "levels": {"date|place": level}, "notify": bool}."""
    from datetime import date as _d, timedelta
    e = cfg.eve_replan
    prev = previous or {}
    old, declined = prev.get("levels") or {}, set(prev.get("declined") or [])
    first = _d.fromisoformat(today) + timedelta(days=1)
    ask_until = (first + timedelta(days=e["notify_days"] - 1)).isoformat()
    note_until = (first + timedelta(days=e["note_days"] - 1)).isoformat()
    asks, notes, now, shared, window_ask = [], [], {}, {}, {}
    for d in itinerary:
        when = d.get("date")
        if not when or not first.isoformat() <= when <= note_until or when not in factors:
            continue
        for row in assess(d, records, factors[when], cfg):
            key = f"{when}|{row['place_id']}"
            now[key] = row["level"]
            if row["level"] == 0:
                continue
            cause = row["causes"][0]
            rose = row["level"] > old.get(key, 0)
            if when <= ask_until and row["level"] >= 2 and rose and cause["key"] not in declined:
                if cause["factor"] == "window" and when in window_ask:
                    window_ask[when].setdefault("also", []).append(row["place_id"])   # one question per day, not per stop
                    continue
                asks.append({"date": when, "place_id": row["place_id"], "name": row["name"], "level": row["level"],
                             "cause": cause, "options": repair(trial, itinerary, row, factors, records, cfg, pool, must, shared)})
                if cause["factor"] == "window":
                    window_ask[when] = asks[-1]
            else:
                notes.append(row)
    return {"ask": asks, "notes": notes, "levels": now, "notify": bool(asks)}


class Store:
    """data/planning/eve/<journey>.json: {"plan_hash", "levels", "pending", "notes", "declined"}. Levels, pending
    options and notes (what the check saw but does not ask about: level 1, and later days) belong to one confirmed
    plan (plan_hash); a declined cause stays declined for the journey."""

    def __init__(self, root):
        from pathlib import Path
        self.root = Path(root)

    def _path(self, journey: str):
        import re
        if not re.fullmatch(r"[0-9a-zA-Z_-]{1,64}", journey):
            raise ValueError("bad journey id")
        return self.root / f"{journey}.json"

    def _read(self, journey: str) -> dict:
        import json
        try:
            return json.loads(self._path(journey).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write(self, journey: str, doc: dict) -> None:
        import json, os
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self._path(journey).with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path(journey))

    def get(self, journey: str, plan_hash: str) -> dict:
        doc = self._read(journey)
        same = doc.get("plan_hash") == plan_hash
        return {"levels": doc.get("levels", {}) if same else {}, "declined": doc.get("declined", []),
                "pending": doc.get("pending", []) if same else [],
                "notes": (doc.get("notes", []) + doc.get("expert_notes", [])) if same else []}

    def save(self, journey: str, plan_hash: str, patch: dict) -> None:
        raw = self._read(journey)
        same = raw.get("plan_hash") == plan_hash
        doc = {**self.get(journey, plan_hash), "notes": raw.get("notes", []) if same else [], **patch,
               "plan_hash": plan_hash}
        for k in ("expert_notes", "expert") if same else ():     # the Local Expert's part belongs to the plan, not to an evening
            if k in raw:
                doc[k] = raw[k]
        self._write(journey, doc)

    def expert(self, journey: str, plan_hash: str) -> dict:
        """{"status", "tries"} of the Local Expert's background pass on this plan; {} = not run yet."""
        raw = self._read(journey)
        return raw.get("expert") or {} if raw.get("plan_hash") == plan_hash else {}

    def save_expert(self, journey: str, plan_hash: str, state: dict, notes: list[dict]) -> None:
        raw = self._read(journey)
        same = raw.get("plan_hash") == plan_hash
        doc = raw if same else {"declined": raw.get("declined", []), "accepted": raw.get("accepted")}
        doc.update({"plan_hash": plan_hash, "expert": state, "expert_notes": notes})
        self._write(journey, doc)

    def accepted(self, journey: str, record: dict | None) -> None:
        """The option the user took last ({"plan_hash": the plan it made, "n": actions to undo, ...}); None clears."""
        doc = self._read(journey)
        doc["accepted"] = record
        self._write(journey, doc)

    def last_accept(self, journey: str, plan_hash: str) -> dict | None:
        rec = self._read(journey).get("accepted")
        return rec if rec and rec.get("plan_hash") == plan_hash else None

    def decline(self, journey: str, cause_key: str) -> None:
        doc = self._read(journey)
        doc["declined"] = sorted(set(doc.get("declined", [])) | {cause_key})
        doc["pending"] = [p for p in doc.get("pending", []) if (p.get("cause") or {}).get("key") != cause_key]
        self._write(journey, doc)


# ---------- I/O edge: today's factors from live, and one evening for one journey ----------

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def closed_now(rec: dict, day: str, start: str, end: str) -> dict | None:
    """The record as served today says the place is not open for [start, end] on that weekday (verified hours
    only; no hours or shaky hours say nothing), or that it closed. None = no evidence of a closure."""
    from datetime import date as _d
    if str(rec.get("status") or "").upper() in ("CLOSED", "PERMANENTLY_CLOSED", "DISABLED"):   # DISABLED: serving's closed
        return {"text": "theo dữ liệu mới nhất, nơi này đã đóng cửa", "source": "corpus", "retrieved_at": None}
    h = (rec.get("operation") or {}).get("hours") or {}
    if h.get("status") != "VERIFIED" or not isinstance(h.get("value"), dict):
        return None
    a, b = to_min(start), to_min(end)
    for o, c in h["value"].get(WEEKDAYS[_d.fromisoformat(day).weekday()]) or []:
        lo, hi = to_min(o), to_min(c)
        hi = hi + 24 * 60 if hi <= lo else hi
        if lo <= a and b <= hi:
            return None
    return {"text": f"giờ mở cửa mới nhất không phủ {start}–{end}", "source": "corpus",
            "retrieved_at": h.get("as_of")}


def gather(itinerary: list[dict], plan: dict, records: dict, cfg: Settings, live_cfg, trip_context: dict,
           dates: list[str], src=None, windows: dict | None = None, extra: list[str] | None = None) -> dict:
    """{date: Factors} for the given trip dates. Every source that fails or has nothing leaves its part empty
    (unknown, never a cause). Weather is read for every stop of every given date at a 0.02° grid, so a stop can be
    judged on another day too (extra: backup ids, read the same way). windows: {date: (from, to)} of a day whose arrival / departure changed."""
    from datetime import date as _d
    if src is None:
        import live as src
    e = cfg.eve_replan
    stops = {i["place_id"] for d in itinerary for i in d.get("items") or [] if i.get("place_id")}
    days = [_d.fromisoformat(x) for x in dates]
    events, notices, hols = src.events(days), src.advisories(days), src.holidays(days)
    try:
        from corpus.views import climate_normals
        normals = climate_normals(getattr(live_cfg, "views_city", "dalat"))
    except Exception:
        normals = None                        # no ClimateNormal view: unknown, the gap is simply not applied
    known = {(p["place_id"], r) for p in (plan.get("backups") or {}).get("places") or [] for r in p.get("reasons") or []}
    averse = ((trip_context.get("pace") or {}).get("crowd_tolerance") == "avoid")
    grid: dict = {}

    def gated(w):
        """D.2 tool gate: an hour whose figures are outside the physical range is a bad reading, so that hour is unknown
        (never an alarm). The ClimateNormal gap is applied in assess(): far from the month's normal and not confirmed by
        both models caps a cause at a note."""
        if not w:
            return w
        keep = {h: r for h, r in (w.get("hours") or {}).items()
                if not any("vật lý" in d for d in doubts({"rain_prob": r.get("rain_prob"), "rain_mm": r.get("rain_mm"),
                                                          "gust_kmh": r.get("gust_kmh")}, None, cfg))}
        return {**w, "hours": keep}

    def sky(pid, day):
        ident = (records.get(pid) or {}).get("identity") or {}
        if ident.get("lat") is None:
            return None
        key = (round(ident["lat"] / 0.02) * 0.02, round(ident["lng"] / 0.02) * 0.02, day)
        if key not in grid:
            try:
                grid[key] = gated(src.weather_hourly(key[0], key[1], day, live_cfg))
            except Exception:
                grid[key] = None
        return grid[key]

    stay = ((plan.get("lodging") or {}).get("chosen") or {}).get("id")
    home = (records.get(stay) or {}).get("identity") or {}
    out = {}
    for d in itinerary:
        when = d.get("date")
        if when not in dates:
            continue
        day = _d.fromisoformat(when)
        visits = [i for i in d.get("items") or [] if i.get("kind") == "visit" and i.get("place_id")]
        passes = {}
        pts = ([(home["lat"], home["lng"])] if home.get("lat") is not None else []) + [
            (records[i["place_id"]]["identity"]["lat"], records[i["place_id"]]["identity"]["lng"]) for i in visits
            if (records.get(i["place_id"]) or {}).get("identity", {}).get("lat") is not None]
        if len(pts) >= 2 and len(pts) == len(visits) + (1 if home.get("lat") is not None else 0):
            try:
                legs = src.route_steps(pts, (trip_context.get("context") or {}).get("mobility"), live_cfg)["legs"]
                into = 0 if home.get("lat") is not None else 1      # leg k ends at visit k (+1 without a lodging)
                for k, leg in enumerate(legs):
                    hits = [st for st in leg if any(st["name"].startswith(p) for p in e["pass_prefixes"])]
                    if hits and k + into < len(visits):
                        passes[visits[k + into]["place_id"]] = hits
            except Exception:
                passes = {}
        ev = events.get(day, [])
        hol = hols.get(day) or next((x["name"] for x in ev if x.get("closure_risk")), None)
        out[when] = Factors(
            date=when, weather={pid: sky(pid, when) for pid in stops | set(extra or [])},
            events=[{**x, "source": "config/events.yaml"} for x in ev],
            notices=[{"title": x.get("note") or x.get("kind"), "severity": x.get("severity"), "kind": x.get("kind"),
                      **(x["area"] if isinstance(x.get("area"), dict) else {"scope": "city"}),
                      "source": x.get("source"), "retrieved_at": str(x.get("issued") or "") or None}
                     for x in notices.get(day, [])],
            passes=passes,
            closed={i["place_id"]: c for i in visits
                    if (c := closed_now(records.get(i["place_id"]) or {}, when, i["start"], i["end"]))},
            window=(windows or {}).get(when), crowd_averse=averse, known=frozenset(known), holiday=hol,
            normal=(normals or {}).get(str(day.month)))
    return out


def _fmt(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _moment(ctx: dict, key: str) -> tuple[str | None, int] | None:
    """(date or None, minutes) of the trip's arrival / departure: the CompiledFrame's moment, else the plain
    arrive_at / leave_at clock (no date: it belongs to day one / the last day)."""
    at = ((ctx.get("frame") or {}).get(key) or {}).get("at")
    if at:
        return at[:10], to_min(at[11:16])
    clock = ctx.get(f"{key}_at")
    return (None, to_min(clock[-5:])) if clock else None


def trip_windows(old: dict, new: dict | None, plan: dict, cfg: Settings) -> dict[int, tuple[int, int]]:
    """DP5: day windows the Trip side tightened after the confirm. old: the context the plan was built on, new: the
    journey's current Search Input context. A later arrival closes the morning of day one up to the landing; an
    earlier departure closes the last day from departure minus the planning buffer. Earlier arrival, later
    departure, an unknown time or another date change nothing (nothing becomes infeasible by guessing).
    {day index: (from, to) in minutes}, the plan's own window (time_budget) kept on the untouched side."""
    itinerary = plan.get("itinerary") or []
    per_day = (plan.get("time_budget") or {}).get("per_day") or []
    if not new or not itinerary:
        return {}

    def bounds(k: int) -> tuple[int, int] | None:
        if k < len(per_day):
            return to_min(per_day[k]["from"]), to_min(per_day[k]["to"])
        times = [(to_min(i["start"]), to_min(i["end"])) for i in itinerary[k].get("items") or [] if i.get("start")]
        return (min(t[0] for t in times), max(t[1] for t in times)) if times else None

    out: dict[int, tuple[int, int]] = {}
    for key, k in (("arrive", 0), ("leave", len(itinerary) - 1)):
        now, before = _moment(new, key), _moment(old or {}, key)
        if now is None or now[0] not in (None, itinerary[k].get("date")) or bounds(k) is None:
            continue
        if before is not None and before[0] not in (None, now[0]) and now[0] is not None:
            continue                                  # the date itself moved: another trip, not a new window
        lo, hi = out.get(k) or bounds(k)
        if key == "arrive" and (before is None or now[1] > before[1]) and now[1] > lo:
            out[k] = (now[1], hi)
        elif key == "leave":
            ceiling = now[1] - cfg.realistic["leave_buffer_min"]
            if (before is None or now[1] < before[1]) and ceiling < hi:
                out[k] = (lo, ceiling)
    return out


def run_eve(engine, snapshot: dict, plan: dict, *, journey: str, plan_hash: str, today: str, store_root,
            live_cfg, src=None, trip_input: dict | None = None) -> dict:
    """One evening for one confirmed journey: restore its Planning session (the journey's snapshot) into
    engine's memory store, read today's factors, check, and keep what is asked as pending for this plan_hash.
    {"notify", "ask", "notes"}; options carry no itinerary (the banner shows text and changed stops)."""
    from datetime import date as _d, timedelta
    from .session import Session
    cfg = engine.cfg
    session = Session.model_validate(snapshot)
    # DP5: an arrival / departure changed on the Trip side (the journey's current Search Input) reaches this session as
    # the same day-window override a Planning edit would make; its acts go in front of every option (accept applies them)
    window_acts = []
    for k, (a, b) in trip_windows(session.decision["trip_context"].get("context") or {},
                                  (trip_input or {}).get("context"), plan, cfg).items():
        lo, hi = session.state.day_window_override.get(k, (a, b))
        session.state.day_window_override[k] = (max(a, lo), min(b, hi))
        window_acts.append({"type": "set_day_window", "day": k, "start": _fmt(max(a, lo)), "end": _fmt(min(b, hi))})
    engine.store.restore(session)
    engine._base.pop(session.id, None)
    engine._schedules.pop(session.id, None)
    itinerary = plan.get("itinerary") or []
    first = _d.fromisoformat(today) + timedelta(days=1)
    span = {(first + timedelta(days=k)).isoformat() for k in range(cfg.eve_replan["note_days"])}
    dates = sorted(d["date"] for d in itinerary if d.get("date") in span)
    if not dates:
        return {"notify": False, "ask": [], "notes": []}
    decision = session.decision
    pool = [b["id"] for b in decision.get("backup_pool") or []]
    must = {c["id"] for c in decision.get("confirmed") or [] if c.get("role") == "anchor"}
    per_day = (plan.get("time_budget") or {}).get("per_day") or []
    windows = {}
    for k, (a, b) in session.state.day_window_override.items():   # arrival / departure moved after the confirm
        if k < len(per_day) and k < len(itinerary) and (_fmt(a), _fmt(b)) != (per_day[k]["from"], per_day[k]["to"]):
            windows[itinerary[k]["date"]] = (_fmt(a), _fmt(b))
    factors = gather(itinerary, plan, engine.by_id, cfg, live_cfg, decision["trip_context"], dates, src, windows, pool)
    store = Store(store_root)
    prev = store.get(journey, plan_hash)
    out = check(itinerary, engine.by_id, factors, cfg, lambda acts: engine.eve_trial(session.id, acts), today=today,
                previous=prev, pool=pool, must=must)
    asks = [{**a, "options": [{k: v for k, v in o.items() if k != "itinerary"} |
                              ({"actions": window_acts + o["actions"]} if window_acts and o["kind"] != "keep" else {})
                              for o in a["options"]]} for a in out["ask"]]
    still = [p for p in prev["pending"] if p["date"] >= first.isoformat()
             and (p["date"], p["place_id"]) not in {(a["date"], a["place_id"]) for a in asks}]
    notes = [{"date": r["date"], "place_id": r["place_id"], "name": r["name"], "level": r["level"],
              "factor": r["causes"][0]["factor"], "text": r["causes"][0]["text"]} for r in out["notes"]]
    store.save(journey, plan_hash, {"levels": {**prev["levels"], **out["levels"]}, "pending": still + asks, "notes": notes})
    return {"notify": out["notify"], "ask": asks, "notes": out["notes"]}


def eve_runner(records: list[dict], live_cfg, store_root, cfg: Settings | None = None):
    """For the notify worker: (journey, snapshot, plan, plan_hash, today, trip=None) -> run_eve(...) (trip: the journey's
    current Search Input, where an arrival / departure edited on the Trip side shows up), with one Engine over the
    served records and the same live conditions as a Planning build; None while eve_replan.enabled is false."""
    from .conditions import fetch_live
    from .engine import Engine
    from .session import Store as SessionStore
    from .settings import load
    cfg = cfg or load()
    if not cfg.eve_replan.get("enabled"):
        return None
    engine = Engine(list(records), cfg=cfg, live_cfg=live_cfg, store=SessionStore(None),
                    conditions_fn=fetch_live(live_cfg), background=False)
    return lambda journey, snap, plan, plan_hash, today, trip=None: run_eve(
        engine, snap, plan, journey=journey, plan_hash=plan_hash, today=today, store_root=store_root, live_cfg=live_cfg,
        trip_input=trip)
