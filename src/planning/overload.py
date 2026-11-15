"""One main plan; when the trip's days cannot hold every pick, three plans that each drop places by one criterion
the user understands (spec section 7): Giữ nơi hợp gu nhất, Di chuyển thuận lợi nhất, Tiết kiệm nhất. A direction is a drop ORDER: drop the
next place until everything fits, then give back any dropped place that still fits. Must-go places never drop. Budget
never enters a place's score: prices only order the `cost` direction, and a place with no known price is never dropped
by it."""

import logging
import multiprocessing as mp
from types import SimpleNamespace
import os
import pickle
import signal
import tempfile
import time
from pathlib import Path
from multiprocessing.connection import wait
from dataclasses import asdict, replace
from functools import partial

from .backup import backups
from .build import Schedule, itinerary, schedule_trip, travel_load
from .composer import must_places, profile_metrics, selection_utilities
from .robustness import robustness
from .timefit import describe as time_description
from .traits import visit_minutes

DIRECTIONS = ("fit", "travel", "cost")
LABEL = {"main": "Lịch của bạn", "fit": "Giữ nơi hợp gu nhất", "travel": "Di chuyển thuận lợi nhất", "cost": "Tiết kiệm nhất",
         "kept": "Giữ các nơi đã xếp vừa"}
TRADEOFF = {"fit": "có thể phải đi xa hơn và tốn hơn để giữ nơi hợp gu",
            "travel": "có thể bỏ nơi bạn thích nhưng nằm xa các nơi còn lại",
            "cost": "có thể bỏ nơi bạn thích nhưng tốn tiền hơn",
            "kept": "bỏ các nơi không còn chỗ, mỗi nơi có lý do"}
GAIN = {"fit": "giữ những nơi khớp gu bạn nhất", "travel": "ít ngồi xe nhất", "cost": "rẻ nhất",
        "kept": "chốt được ngay với lịch đã kiểm"}
ORDINAL = {2: "thứ hai", 3: "thứ ba", 4: "thứ tư"}
ALONE_MIN = 15              # spec section 7: "các nơi khác cách khách sạn < 15′", the dropped place off on its own
EXTEND_STEP = 15            # extend offers go up in quarter hours, to extend_max_min
OVERRUN = {"day_window", "departure"}   # a day past its end or its departure: only must-go places get laid out so
NEUTRAL_UTILITY = 1.0       # composer.selection_utilities' value for a place with no utility and no soft weights
UNAVAILABLE = {"protected": "Các nơi còn lại đều là nơi bạn chắc chắn đi, không bỏ được nơi nào.",
               "unpriced": "Các nơi còn lại chưa có giá, không xét để tiết kiệm.",
               "no_gain": "Bỏ thêm nơi theo hướng này cũng không làm lịch vừa.",
               "timeout": "Chưa tìm xong phương án trong thời gian cho phép; giữ kết quả đã kiểm tra."}


def _short(trip, sched: Schedule) -> int:
    """Minutes the trip is short by: the left-over places' shortest visits and how far must-go places overran a day."""
    return sum(trip.by_place[p].visit["short"] for p in sched.leftover) + \
        sum(v.minutes for v in sched.violations if v.kind in OVERRUN)


def _over(sched: Schedule) -> bool:
    """The days cannot hold every pick: a place is left over, or must-go places pushed a day past its end."""
    return bool(sched.leftover) or any(v.kind in OVERRUN for v in sched.violations)


def _gap(trip, sched: Schedule) -> tuple[int, bool]:
    """How far a schedule is from fitting, to compare two of them: fewer missing minutes first, then fitting at all
    (an overrun of 0 minutes is still an overrun). (0, False) = it fits."""
    return _short(trip, sched), _over(sched)


def _utility(values: dict, pid: str) -> float:
    return values.get(pid, NEUTRAL_UTILITY)


def _vnd(v: int) -> str:
    if v < 1000:
        return f"~{v}đ/người"
    return f"~{v // 1000}k/người" if v < 1_000_000 else f"~{v / 1_000_000:.1f}tr/người".replace(".", ",")


def _hm(minutes: int) -> str:
    return f"{minutes // 60}h{minutes % 60:02d}" if minutes >= 60 else f"{minutes}′"


class _Runs:
    """schedule_trip once per kept set within one plan_or_directions call: the directions often try the same sets.
    Fork workers share a counter; spawn workers return local counts through their result pipe."""

    def __init__(self, trip, counter=None):
        self.trip, self.memo = trip, {}
        self.counter = counter if counter is not None else mp.get_context(_PROCESS_CONTEXT).Value('i', 0)

    @property
    def calls(self) -> int:
        return self.counter.get_obj().value if hasattr(self.counter, 'get_obj') else self.counter.value

    def count(self) -> None:
        if not hasattr(self.counter, 'get_lock'):
            self.counter.value += 1       # spawn workers return independent counts through their result pipe
            return
        lock = self.counter.get_lock()
        if lock.acquire(timeout=1):                     # a child killed mid-increment must not hang the others
            try:
                self.counter.get_obj().value += 1
            finally:
                lock.release()

    def __call__(self, kept) -> Schedule:
        key = frozenset(kept)
        if key not in self.memo:
            self.count()
            self.memo[key] = schedule_trip(self.trip, kept=key)
        return self.memo[key]


def _saving(trip, sched: Schedule, pid: str, gone=frozenset()) -> int:
    """Minutes on the road saved by not going to pid, in the day order it has now (places in `gone` already left)."""
    leg = lambda a, b: trip.travel.leg(a, b)[0] if a and b else 0
    for cx, r in zip(sched.ctxs, sched.results):
        if pid in r.order:
            order = [p for p in r.order if p not in gone]
            k = order.index(pid)
            prev = order[k - 1] if k else cx.day.start_node
            nxt = order[k + 1] if k + 1 < len(order) else cx.day.end_node
            return max(0, leg(prev, pid) + leg(pid, nxt) - leg(prev, nxt))
    home = sched.ctxs[0].home if sched.ctxs else None
    return 2 * leg(home, pid)                     # not placed: the round trip from the lodging it would need


def _freed(trip, sched: Schedule, pid: str, gone) -> int:
    """Minutes dropping pid gives the other places (its visit and the road it saves); a left-over place frees none."""
    placed = any(pid in r.order for r in sched.results)
    if not placed:
        return 0
    visit = sum(i.end - i.start for r in sched.results for i in r.items if i.kind == "visit" and i.place_id == pid)
    return visit + _saving(trip, sched, pid, gone)


def _alone(trip, pid: str, kept) -> bool:
    """pid is off on its own: at least ALONE_MIN from the lodging while every other kept place is closer than that."""
    home = trip.ctxs[0].home if trip.ctxs else None
    others = [p for p in kept if p != pid]
    return bool(home and others) and trip.travel.leg(home, pid)[0] >= ALONE_MIN and \
        all(trip.travel.leg(home, p)[0] < ALONE_MIN for p in others)


def _next(trip, sched, candidates, direction, values, ranks, gone):
    """(place, its number on the criterion, the reason on the card) to drop next, or None when nothing can go."""
    if direction == "fit":
        pid = min(candidates, key=lambda p: (_utility(values, p), -_saving(trip, sched, p, gone), p))
        n = 1 + sum(_utility(values, q) < _utility(values, pid) for q in ranks)    # ties share a rank
        return pid, _utility(values, pid), "ít khớp gu nhất" if n == 1 else \
            f"khớp gu {ORDINAL.get(n, f'thứ {n}')} từ dưới lên"
    if direction == "travel":
        pid = max(candidates, key=lambda p: (_saving(trip, sched, p, gone), -_utility(values, p), p))
        s = _saving(trip, sched, pid, gone)
        reason = f"bớt {_hm(s)} đi xe" if s else "không bớt phút đi xe nào"
        if _alone(trip, pid, set(trip.by_place) - gone - {pid}):
            reason += f", các nơi khác cách chỗ ở < {ALONE_MIN}′"
        return pid, s, reason
    priced = [p for p in candidates if trip.by_place[p].cost_vnd is not None]
    if not priced:
        return None
    pid = max(priced, key=lambda p: (trip.by_place[p].cost_vnd, p))
    v = trip.by_place[pid].cost_vnd
    return pid, v, f"đắt nhất {_vnd(v)}" if v else "miễn phí"


def _direction(trip, run: _Runs, direction, protected, values):
    """(kept, dropped, schedule, why unavailable or None). A round drops a batch that frees about the missing minutes on
    the current layout (the criterion recomputed after each pick); if that does not bring the trip closer to fitting,
    it keeps dropping one more place at a time until it does. A round that cannot is taken back whole and dropping
    stops: a day with room never loses a place to an overrun dropping cannot fix (spec section 7). Then gives back,
    last dropped first, each place whose return leaves the trip no further from fitting, until a pass gives none
    back: a fitting trip stays fitting, one that still overruns keeps only the drops that helped."""
    kept = set(trip.by_place)
    sched = run(kept)
    ranks = sorted(set(trip.by_place) - protected)      # the places a fit reason ranks among
    dropped = []
    while _over(sched):
        gap = _gap(trip, sched)
        missing, gone, picks, trial = gap[0], set(), [], None
        while True:
            candidates = kept - protected - gone
            pick = _next(trip, sched, candidates, direction, values, ranks, gone) if candidates else None
            if pick is not None:
                pid, value, reason = pick
                picks.append({"place_id": pid, "name": trip.by_place[pid].name, "reason": reason, "value": value})
                missing -= trip.by_place[pid].visit["short"] if pid in sched.leftover else \
                    _freed(trip, sched, pid, gone)
                gone.add(pid)
                if missing > 0:
                    continue            # the batch: about the missing minutes, checked with one schedule_trip
            elif not gone:
                break                   # nothing this direction may drop
            trial = run(kept - gone)
            if _gap(trip, trial) < gap or pick is None:
                break                   # closer to fitting, or nothing more to try
        if trial is None or not _gap(trip, trial) < gap:
            break                       # nothing (more) to drop, or dropping stopped helping: the round is taken back
        kept -= gone
        dropped += picks
        sched = trial
    best = _gap(trip, sched)
    changed = True
    while changed:
        changed = False
        for d in list(reversed(dropped)):
            trial = run(kept | {d["place_id"]})
            if _gap(trip, trial) <= best:
                kept.add(d["place_id"])
                dropped.remove(d)
                sched, best, changed = trial, _gap(trip, trial), True
    if not _over(sched):
        return kept, dropped, sched, None
    left = kept - protected
    if not left:
        why = "protected"
    elif direction == "cost" and all(trip.by_place[p].cost_vnd is None for p in left):
        why = "unpriced"
    else:
        why = "no_gain"
    return kept, dropped, sched, why


_FORK_WAIT_S = 20          # one budget for the entire batch, never per child
_PROCESS_CONTEXT = "spawn"  # never inherit an open LanceDB / torch runtime from the server


def _in_children(tasks: dict, *, deadline=None) -> dict:
    """Collect ready answers in completion order under one deadline; never retry a failed task in the caller."""
    deadline = min(deadline, time.monotonic() + _FORK_WAIT_S) if deadline is not None else time.monotonic() + _FORK_WAIT_S
    ctx, procs, got = mp.get_context(_PROCESS_CONTEXT), {}, {}
    try:
        for name, task in tasks.items():
            if time.monotonic() >= deadline:
                break
            rx, tx = ctx.Pipe(duplex=False)
            proc = ctx.Process(target=_file_child, args=(tx, task)) if isinstance(task, Path) else ctx.Process(target=_child, args=(tx, task))
            try:
                proc.start()
            except Exception:
                logging.getLogger(__name__).exception("overload worker start failed: %s", name)
                rx.close()
                tx.close()
                continue
            if not _IN_CHILD and os.name == "posix":
                try:
                    os.setpgid(proc.pid, proc.pid)
                except OSError:
                    pass
            tx.close()
            procs[rx] = (name, proc)
        pending = set(procs)
        while pending:
            ready = wait(pending, timeout=max(0, deadline - time.monotonic()))
            if not ready:
                break
            for rx in ready:
                pending.remove(rx)
                try:
                    ok, payload = rx.recv()
                    if ok:
                        got[procs[rx][0]] = payload
                    else:
                        logging.getLogger(__name__).warning("overload worker failed: %s: %s", procs[rx][0], payload)
                except (EOFError, OSError):
                    logging.getLogger(__name__).warning("overload worker closed without a result: %s", procs[rx][0])
    finally:
        for rx, (_, proc) in procs.items():
            rx.close()
            _stop(proc)
    return got


def _stop(proc) -> None:
    """End a forked task that is still running together with anything it forked (the longer-day child's two trials):
    a top-level child leads its own process group, so one kill reaches the whole group; a nested child has no group of
    its own, only itself is killed."""
    try:
        if not _IN_CHILD and os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        elif proc.is_alive():
            proc.kill()
    except (ProcessLookupError, PermissionError):
        if proc.is_alive():
            proc.kill()
    proc.join(0.05)


_IN_CHILD = False           # True in a forked task: its own children stay in the task's process group


def _file_child(tx, path) -> None:
    def task():
        with path.open("rb") as stream:
            trip, main, protected, direction = pickle.load(stream)
        counter = SimpleNamespace(value=0)
        answer = _search(trip, main, protected, direction, counter)
        return answer, counter.value
    _child(tx, task)


def _child(tx, task) -> None:
    global _IN_CHILD
    if not _IN_CHILD:
        try:
            os.setpgid(0, 0)        # the group the parent kills on timeout (the parent sets it too: no race)
        except OSError:
            pass
    _IN_CHILD = True
    try:
        tx.send((True, task()))
    except BaseException as e:      # the caller keeps only completed, checked answers
        tx.send((False, repr(e)))
    finally:
        tx.close()
        os._exit(0)


def render_variant(trip, sched: Schedule, vid: str, dropped=(), available=True, why=None, day_parts=True) -> dict:
    """One plan card in the shape the engine reads (composer.render_profile's keys) plus the overload card fields.
    day_parts=False: robustness and backups are left None for a caller that has them per day already (the engine's
    cached day artifacts), so an edit does not work them out twice."""
    m = profile_metrics(trip, sched)
    kept = sorted({pid for r in sched.results for pid in r.order})
    days = [cx.day for cx in sched.ctxs]
    values = selection_utilities(trip)
    known = [trip.by_place[p].cost_vnd for p in kept if p in trip.by_place and trip.by_place[p].cost_vnd is not None]
    violations = [asdict(v) for v in sched.violations]
    confirmable = available and not violations and not sched.leftover
    return {"id": vid, "objective": vid, "preset": None, "label": LABEL[vid], "gain": GAIN.get(vid), "tradeoff": TRADEOFF.get(vid),
            "kept": kept, "dropped": list(dropped), "available": available, "left_over": list(sched.leftover),
            "unavailable_reason": None if available else UNAVAILABLE[why or "protected"],
            "compare": {"travel_min": m["travel_min"], "cost_known_vnd": sum(known),
                        "cost_unknown_n": len(kept) - len(known),
                        "fit": round(sum(_utility(values, p) for p in kept) / max(1e-9, sum(values.values())), 3)},
            "stars": [], "metrics": m, "violations": violations,
            "status": "available" if confirmable else "unavailable", "confirmable": confirmable,
            "itinerary": itinerary(days, sched.results, sched.ctxs), "travel_load": travel_load(days, sched.results),
            "time_suitability": time_description(sched.ctxs, sched.results), "recommendations": [],
            "robustness": robustness(sched.ctxs, sched.results, trip.travel.source) if day_parts else None,
            "backups": backups(sched.ctxs, sched.results, trip.decision, trip.by_id) if day_parts else None,
            "warnings": sched.warnings,
            "lodging": {"id": None, "name": None, "price_vnd": None}, "score": [m["travel_min"]],
            "_results": sched.results, "_ctxs": sched.ctxs, "_home": trip.days[0].start_node if trip.days else None}


def _holds(trip, run, sides, side, minutes) -> bool:
    ctxs = [cx if not ok else replace(cx, day=replace(cx.day, start=cx.day.start - minutes)) if side == "start"
            else replace(cx, day=replace(cx.day, end=min(24 * 60, cx.day.end + minutes)))
            for ok, cx in zip(sides[side], trip.ctxs)]
    run.count()
    return not _over(schedule_trip(replace(trip, ctxs=ctxs)))


def _search(trip, main, protected, direction, counter):
    if _PROCESS_CONTEXT == "spawn":
        trip = replace(trip, cfg=replace(trip.cfg, direction_workers=1))
    run = _Runs(trip, counter)
    run.memo[frozenset(trip.by_place)] = main
    return _extend(trip, run, main) if direction == "extend" else \
        _direction(trip, run, direction, protected, selection_utilities(trip))


def _extend(trip, run: _Runs, main: Schedule) -> dict | None:
    """The smallest earlier start / later end (quarter hours, at most extend_max_min a day) that holds every place.
    A start the user set (arrival, check-in), a fixed departure and a free day never move. A step whose added minutes
    cannot even cover the left-over visits is not tried (no schedule_trip call)."""
    last = len(trip.ctxs) - 1
    short = _short(trip, main)

    def movable(k, cx, side):
        day = cx.day
        if day.intensity == "free":
            return False
        if side == "start":
            return not day.start_by_user and not (k == 0 and day.start_node == "@entry")
        return day.depart_by is None and not (k == last and day.end_node == "@exit") and day.end < 24 * 60

    sides = {side: [movable(k, cx, side) for k, cx in enumerate(trip.ctxs)] for side in ("start", "end")}
    tried: dict = {}

    holds = partial(_holds, trip, run, sides)

    def fits(side, minutes):
        if (side, minutes) not in tried:
            tried[side, minutes] = holds(side, minutes)
        return tried[side, minutes]

    top = trip.cfg.realistic["extend_max_min"] // EXTEND_STEP * EXTEND_STEP
    # Both sides' widest trial is always tried when its minutes could cover the short ones (open_sides below): with
    # direction_workers > 1 the two run in forked processes at once, each a whole schedule_trip on a frame no memo has.
    widest = [side for side in ("start", "end") if top and top * sum(sides[side]) >= short]
    if len(widest) > 1 and trip.cfg.direction_workers > 1:
        for side, ok in _in_children({side: partial(holds, side, top) for side in widest}).items():
            tried[side, top] = ok
    # A side that cannot hold every place even moved by the most it may move is not tried step by step (a whole
    # schedule_trip a step): the steps below the most only matter on a side the most fits.
    open_sides = [side for side in ("start", "end") if top and top * sum(sides[side]) >= short and fits(side, top)]
    for minutes in range(EXTEND_STEP, top + 1, EXTEND_STEP):
        for side in open_sides:
            if minutes * sum(sides[side]) >= short and fits(side, minutes):
                return {"side": side, "per_day_min": minutes}
    return None


def plan_or_directions(trip, *, protected=()) -> dict:
    """The plan output for one trip: a fitting trip has one `main` plan and no overload; an overloaded one has up to
    three direction plans (two that keep the same places share one card, `merged`) and the overload card.
    protected: places the session also keeps whatever happens (locked days), on top of composer.must_places."""
    deadline = time.monotonic() + max(0, trip.cfg.realistic.get("overload_deadline_s", _FORK_WAIT_S))
    run = _Runs(trip, SimpleNamespace(value=0) if _PROCESS_CONTEXT == 'spawn' else None)
    main = run(set(trip.by_place))
    if not _over(main):
        v = render_variant(trip, main, "main")
        return {"variants": [v], "overload": None, "ok": v["confirmable"], "warnings": [], "back_to_decision": None,
                "comparison": [], "leftover": (), "schedule_calls": run.calls}
    protected = (must_places(trip) | set(protected)) & set(trip.by_place)
    out, seen = [], {}
    # Only immutable trip data crosses spawn; no corpus readers, callbacks or inherited native runtime.
    # Backups need selected / backup records, not the city's entire serving payload.
    ids = set(trip.by_place) | {p["id"] for p in trip.decision.get("backup_pool", [])}
    worker_trip = replace(trip, by_id={pid: trip.by_id[pid] for pid in ids if pid in trip.by_id})
    if _PROCESS_CONTEXT == "spawn":
        # Pass only tiny file paths to spawn: sending a large Trip through its startup pipe blocks Process.start()
        # until the fresh interpreter has imported the app, outside the parent's result-wait deadline.
        root = Path(__file__).resolve().parents[2] / "logs"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="overload-", dir=root) as folder:
            tasks = {}
            for direction in (*DIRECTIONS, "extend"):
                path = Path(folder) / direction
                with path.open("wb") as stream:
                    pickle.dump((worker_trip, main, protected, direction), stream)
                tasks[direction] = path
            answers = _in_children(tasks, deadline=deadline)
            searched = {name: answer for name, (answer, _) in answers.items()}
            for _, count in answers.values():
                run.counter.value += count
    else:
        tasks = {d: partial(_search, worker_trip, main, protected, d, run.counter) for d in (*DIRECTIONS, "extend")}
        searched = _in_children(tasks, deadline=deadline)
    incomplete = set(tasks) - set(searched)
    for direction in DIRECTIONS:
        kept, dropped, sched, why = searched.get(direction) or (set(trip.by_place), [], main, "timeout")
        key = frozenset(kept)
        if key in seen:
            seen[key].setdefault("merged", []).append(direction)  # one card, under the first direction's name (chủ dự án 13/11/2026)
        else:
            seen[key] = render_variant(trip, sched, direction, dropped, not _over(sched), why)
            out.append(seen[key])
        if direction == "cost":     # spec section 7: "N nơi chưa có giá, không xét"
            seen[key]["unpriced_n"] = sum(p.cost_vnd is None for pid, p in trip.by_place.items()
                                          if pid not in protected)
    if incomplete and not any(v["available"] for v in out):
        # Keep the already checked layout as an editable draft, not a claim that all selected / required places fit.
        from .model import Violation

        placed = {pid for r in main.results for pid in r.order}
        absent = protected - placed
        existing = {v.place_id for v in main.violations if v.kind == "anchor"}
        checked = replace(main, violations=[*main.violations,
                          *(Violation("anchor", None, pid, 0, False, "an anchor is not in the plan")
                            for pid in sorted(absent - existing))])
        draft = render_variant(trip, checked, "main")
        draft.update(status="available", editable=True, confirmable=False, kept=sorted(trip.by_place),
                     dropped=[{"place_id": pid, "name": trip.by_place[pid].name, "reason": "chưa xếp xong"}
                              for pid in main.leftover])
        out.insert(0, draft)
        if not checked.violations and main.leftover:
            # The checked layout is itself a way out the user can take now (spec section 7, "never leave the user
            # without a confirmable plan"): the places that fit, each one left out named with why and how long it needs.
            days = len(main.results)
            why = [{"place_id": pid, "name": trip.by_place[pid].name,
                    "reason": f"không còn chỗ trong {days} ngày đã kín lịch (cần thêm khoảng "
                              f"{visit_minutes(trip.by_place[pid], trip.cfg, trip.pace)} phút)"}
                   for pid in main.leftover]
            out.insert(1, render_variant(trip, replace(checked, leftover=()), "kept", why, True))
    ranked = [v for v in out if v["available"]]
    for field, better in (("travel_min", min), ("cost_known_vnd", min), ("fit", max)):
        if len(ranked) > 1:
            best = better(v["compare"][field] for v in ranked)
            for v in ranked:
                if v["compare"][field] == best:
                    v["stars"].append(field)
    missing = sum(visit_minutes(trip.by_place[p], trip.cfg, trip.pace) for p in main.leftover) + \
        sum(v.minutes for v in main.violations if v.kind in OVERRUN)
    extend = searched.get("extend")
    warnings = [{"code": "overload_deadline", "text": UNAVAILABLE["timeout"], "unfinished": sorted(incomplete)}] if incomplete else []
    overload = {"missing_min": missing, "places": len(trip.by_place),
                "directions": [{k: x for k, x in v.items() if not k.startswith("_")} for v in out], "extend": extend,
                "incomplete": sorted(incomplete)}
    ok = any(v["confirmable"] for v in out)
    back = None if any(v["available"] for v in out) else \
        {"reason": "overload_deadline" if incomplete else "required_places_do_not_fit",
         "places": sorted(protected), "leftover": list(main.leftover)}
    return {"variants": out, "overload": overload, "ok": ok, "warnings": warnings, "comparison": [], "back_to_decision": back,
            "leftover": main.leftover, "schedule_calls": run.calls}
