""""Tối ưu lịch" (docs/PLANNING.md §Tối ưu lịch): the same places, re-split over the days and re-ordered inside each day
by a deterministic search, no model. Two stages:

1. a fast search on the travel matrix alone: each day's road is its exact tour from the lodging and back (Held-Karp up
   to HELD_KARP_N stops, nearest neighbour + 2-opt above), plus what the day's minutes would hold (capacity), how even
   the days are and the pace's places a day. Local search (move one place, swap two) from the current split and from
   sweep splits around the lodging gives a few distinct candidate splits;
2. each candidate is laid out by the real day clock (route.order_day: opening hours, meals, times of day, buffers) and
   scored by `objective`. The best one wins only when it is strictly better than the current days and adds no problem
   the validator sees; otherwise the current plan stays.

The caller (engine.recommend) commits the winner through the session's own move / reorder state, so replay and every
later edit read it like any other act.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from itertools import combinations

from .layout import capacity, pull_early
from .route import improve_order, order_day
from .validate import validate

HELD_KARP_N = 9              # exact tour on the matrix up to this many stops a day (9 * 2^9 * 9 steps)
BALANCE_PER_MIN = 0.25       # one minute of uneven load between days weighs a quarter minute of road
OVER_PER_MIN = 4.0           # a minute past what a day's free time holds (stage 1 estimate only)
PACE_PER_PLACE = 30.0        # a place past the pace's places a day (per_day) weighs half an hour of road
CANDIDATES = 6               # distinct splits stage 2 lays out with the real clock
IDLE_FREE_MIN = 30           # a wait or free stretch up to this long is a breather, not lost time
IDLE_PER_MIN = 0.5           # each minute sitting about past that
PIN_LOST = 90.0              # a time of day given up (sunset, dawn, live music): what the place was chosen for, more
                             # than an afternoon sitting at the lodging (IDLE_PER_MIN) is worth
LATE_PER_MIN = 2.0           # each minute the day runs past its end, the ride back included
EXACT_N = 5                  # a day of up to this many stops tries every order (120 clocks); above, local search
MIN_GAIN = 1.0               # the objective must drop by at least this much to replace the user's plan


@dataclass(frozen=True)
class Scored:
    days: tuple[tuple[str, ...], ...]   # place ids of each day, in visiting order
    results: tuple                      # DayResult of each day
    key: tuple                          # objective(): lower is better
    parts: dict                         # the objective's terms, for the user-facing summary


def _leg(travel, a, b) -> int:
    return travel.leg(a, b)[0] if a and b and a != b else 0


def tour(travel, start, end, ids) -> int:
    """Least road minutes from start through every id to end (None start / end: an open path, the day has no lodging)."""
    ids = list(ids)
    n = len(ids)
    if n == 0:
        return _leg(travel, start, end)
    if n == 1:
        return _leg(travel, start, ids[0]) + _leg(travel, ids[0], end)
    if n <= HELD_KARP_N:
        d = [[_leg(travel, a, b) for b in ids] for a in ids]
        first = [_leg(travel, start, b) if start else 0 for b in ids]
        last = [_leg(travel, a, end) if end else 0 for a in ids]
        full = (1 << n) - 1
        best = {(1 << j, j): first[j] for j in range(n)}
        for size in range(2, n + 1):
            for subset in combinations(range(n), size):
                mask = 0
                for j in subset:
                    mask |= 1 << j
                for j in subset:
                    prev = mask ^ (1 << j)
                    best[mask, j] = min(best[prev, i] + d[i][j] for i in subset if i != j)
        return min(best[full, j] + last[j] for j in range(n))
    order, here, left = [], start, set(ids)
    while left:
        nxt = min(sorted(left), key=lambda x: _leg(travel, here, x) if here else 0)
        order.append(nxt)
        left.remove(nxt)
        here = nxt

    def length(o):
        nodes = [start, *o, end]
        return sum(_leg(travel, a, b) for a, b in zip(nodes, nodes[1:]))
    cost, improved = length(order), True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                c = length(cand)
                if c < cost:
                    order, cost, improved = cand, c, True
    return cost


class _Estimate:
    """Stage 1: what a split costs on the matrix alone, each day memoized by its places."""

    def __init__(self, frames, by_place, travel):
        self.frames, self.by_place, self.travel = frames, by_place, travel
        self.caps = [capacity(cx) for cx in frames]
        self.memo: dict = {}

    def day(self, k: int, ids: frozenset) -> tuple[float, float]:
        """(road minutes, load as a share of the day's free time) of day k holding ids."""
        key = (k, ids)
        if key not in self.memo:
            cx = self.frames[k]
            road = tour(self.travel, cx.day.start_node, cx.day.end_node, sorted(ids))
            visit = sum(min(self.by_place[p].visit[cx.cfg.visit_key[cx.pace]], self.by_place[p].visit["typical"])
                        for p in ids)
            self.memo[key] = (road, (visit + road) / self.caps[k] if self.caps[k] else (math.inf if ids else 0.0))
        return self.memo[key]

    def cost(self, split: list[frozenset]) -> float:
        roads, loads, over, pace = 0, [], 0.0, 0
        for k, ids in enumerate(split):
            road, load = self.day(k, ids)
            roads += road
            cap = self.caps[k]
            if cap:
                loads.append(load)
                over += max(0.0, load - 1.0) * cap
            elif ids:
                over += 10 ** 6
            cx = self.frames[k]
            pace += max(0, len(ids) - cx.cfg.per_day[cx.pace])
        mean_cap = sum(self.caps) / max(1, len(self.caps))
        spread = (max(loads) - min(loads)) * mean_cap if len(loads) > 1 else 0.0
        return roads + OVER_PER_MIN * over + BALANCE_PER_MIN * spread + PACE_PER_PLACE * pace + \
            empty_cost(self.frames, [len(ids) for ids in split], self.caps)


def _local_search(est: _Estimate, split: list[frozenset], movable: set, may, deadline: float) -> list[frozenset]:
    """Best-improvement moves (one place to another day) and swaps (two places of two days) until none helps."""
    split = list(split)
    cost = est.cost(split)
    n = len(split)
    while time.monotonic() < deadline:
        best = None
        for k in range(n):
            for pid in sorted(split[k] & movable):
                for j in range(n):
                    if j == k or not may(j, pid):
                        continue
                    trial = list(split)
                    trial[k], trial[j] = split[k] - {pid}, split[j] | {pid}
                    c = est.cost(trial)
                    if c < cost - 1e-9 and (best is None or c < best[0]):
                        best = (c, trial)
        for k in range(n):
            for j in range(k + 1, n):
                for a in sorted(split[k] & movable):
                    if not may(j, a):
                        continue
                    for b in sorted(split[j] & movable):
                        if not may(k, b):
                            continue
                        trial = list(split)
                        trial[k], trial[j] = (split[k] - {a}) | {b}, (split[j] - {b}) | {a}
                        c = est.cost(trial)
                        if c < cost - 1e-9 and (best is None or c < best[0]):
                            best = (c, trial)
        if best is None:
            break
        cost, split = best
    return split


def _sweeps(est: _Estimate, current: list[frozenset], movable: set, may, points: dict, home_at) -> list[list[frozenset]]:
    """Splits that cut the places around the lodging by bearing into consecutive arcs, one per day, each arc as long as
    its day's share of the trip's free time; one split per starting place. Fixed places stay where they are."""
    if home_at is None:
        return []
    free = sorted(p for p in movable if p in points)
    if len(free) < 2:
        return []
    bearing = {p: math.atan2(points[p][0] - home_at[0], points[p][1] - home_at[1]) for p in free}
    ring = sorted(free, key=lambda p: (bearing[p], p))
    days = [k for k in range(len(current)) if est.caps[k]]
    if len(days) < 2:
        return []
    total = sum(est.caps[k] for k in days)
    out = []
    for start in range(len(ring)):
        order = ring[start:] + ring[:start]
        split = [frozenset(ids - movable) for ids in current]
        i = 0
        for n, k in enumerate(days):
            take = len(order) - i if n == len(days) - 1 else round(len(order) * est.caps[k] / total)
            for pid in order[i:i + take]:
                target = k if may(k, pid) else next((j for j in days if may(j, pid)), None)
                if target is None:
                    target = next(j for j, ids in enumerate(current) if pid in ids)
                split[target] = split[target] | {pid}
            i += take
        out.append(split)
    return out


def empty_cost(ctxs, counts: list[int], caps: list[int]) -> float:
    """A day the user has with room and no place on it, while the trip has a place for every such day, costs
    spread_extra_min: the road layout.assign may add to give an empty day one stop (the user came for every day). So
    regrouping never empties a day just to save a ride out and back."""
    room = [k for k, cap in enumerate(caps) if cap and ctxs[k].day.intensity != "free" and not ctxs[k].day.blocks]
    if not room or sum(counts) < len(room):
        return 0.0
    return sum(ctxs[0].cfg.spread_extra_min for k in room if counts[k] == 0)


def meals_missed(cx, r) -> int:
    """Meals the person finds missing on the day: the clock's meal_missed notes, except a meal whose window closed
    before the day began (a day that starts at 14:00 has no lunch, and nobody is told it missed one)."""
    windows = cx.cfg.meal_windows
    return sum(1 for n in r.notes if n.startswith("meal_missed:")
               and windows.get(n.split(":", 1)[1], (0, 24 * 60))[1] >= cx.day.start)


def _sitting(r) -> int:
    """Minutes sitting about past IDLE_FREE_MIN: a long wait, a free stretch at the lodging before anything starts."""
    return sum(max(0, i.end - i.start - IDLE_FREE_MIN) for i in r.items if i.kind in {"wait", "free"})


def _late(cx, r) -> int:
    """Minutes the day runs past its end, the ride back included."""
    return max(0, max((i.end for i in r.items), default=cx.day.end) - cx.day.end)


def day_value(cx, r) -> float:
    """The objective's terms one day owns alone: road, timing, sitting about, times of day given up, running late."""
    return r.travel_min + r.time_penalty + IDLE_PER_MIN * _sitting(r) + PIN_LOST * len(r.unpinned) + \
        LATE_PER_MIN * _late(cx, r)


def objective(ctxs, results, *, hard, anchors, max_leg) -> tuple[tuple, dict]:
    """(key, parts). Lower key is better: problems the validator sees, then missed meals (meals_missed), then one
    number: road minutes (the lodging legs included: every day opens and closes there), how uneven the days are, the
    timing penalty (time_suitability: a visit at a poor hour), places past the pace's places a day, days left empty
    (empty_cost), and what a person reading the day minds besides the road: sitting about, a time of day given up,
    coming back after the day's end (day_value)."""
    problems = validate(ctxs, results, hard, anchors, None, max_leg)
    meals = sum(meals_missed(cx, r) for cx, r in zip(ctxs, results))
    travel = sum(r.travel_min for r in results)
    busy = []
    for cx, r in zip(ctxs, results):
        span = cx.day.end - cx.day.start
        if span > 0 and cx.day.intensity != "free":
            busy.append(sum(i.end - i.start for i in r.items if i.kind in {"visit", "travel"}) / span)
    mean_span = sum(cx.day.end - cx.day.start for cx in ctxs) / max(1, len(ctxs))
    spread = (max(busy) - min(busy)) * mean_span if len(busy) > 1 else 0.0
    timing = sum(r.time_penalty for r in results)
    idle = sum(_sitting(r) for r in results)
    lost = sum(len(r.unpinned) for r in results)
    late = sum(_late(cx, r) for cx, r in zip(ctxs, results))
    pace = sum(max(0, len(r.order) - cx.cfg.per_day[cx.pace]) for cx, r in zip(ctxs, results))
    empty = empty_cost(ctxs, [len(r.order) for r in results], [capacity(cx) for cx in ctxs])
    value = travel + BALANCE_PER_MIN * spread + timing + PACE_PER_PLACE * pace + empty + \
        IDLE_PER_MIN * idle + PIN_LOST * lost + LATE_PER_MIN * late
    parts = {"problems": len(problems), "meals_missed": meals, "travel_min": travel, "spread_min": round(spread),
             "time_penalty": round(timing, 1), "pace_excess": pace, "empty_days": int(empty // max(1, ctxs[0].cfg.spread_extra_min)) if ctxs else 0,
             "idle_min": idle, "times_lost": lost, "late_min": late,
             "value": round(value, 1)}
    return (len(problems), meals, round(value, 1)), parts


def improves(new: Scored | tuple, old: Scored | tuple) -> bool:
    """new replaces old: fewer problems the validator sees or missed meals (a broken day mended may take more road),
    else the same of both, never more road minutes and a lower objective by at least MIN_GAIN. (Scored, or (key,
    parts) pairs.)"""
    nk, np_ = (new.key, new.parts) if isinstance(new, Scored) else new
    ok, op = (old.key, old.parts) if isinstance(old, Scored) else old
    if nk[:2] != ok[:2]:
        return nk[:2] < ok[:2]
    return np_["travel_min"] <= op["travel_min"] and nk[2] <= ok[2] - MIN_GAIN


def optimize(frames, current, by_place, travel, *, fixed: dict, may, hard, anchors, max_leg,
             points: dict, home_at=None, keep: frozenset = frozenset(), seeds=(), budget_s: float = 4.0) -> tuple[Scored, Scored]:
    """(the current plan scored, the best plan found: the current one when nothing beats it).
    frames: each day's context before any dawn pull (the place a day holds may pull it); current: the DayResult of each
    day now; fixed: place id -> the day it may not leave (locked, a time of day the user set); may(k, pid): the hard
    rules let pid on day k; points: place id -> (lat, lng) for the sweep splits; keep: days whose places and order stay
    exactly as they are (the user's own order); seeds: whole layouts (the DayResult of each day) always laid out and
    scored, each day as the seed laid it (with the times of day it gave up, `unpinned`), in its order re-timed, and in
    the searched order (the automatic layout of these places)."""
    from .build import simulate_order
    deadline = time.monotonic() + budget_s
    split0 = [frozenset(r.order) for r in current]
    placed = set().union(*split0) if split0 else set()
    movable = {p for p in placed if p not in fixed}
    est = _Estimate(frames, by_place, travel)
    laid: dict = {}             # (day, places) -> (ctx, DayResult): the real clock, once per day and set of places
    given: dict = {}
    for seed in seeds:
        for k, r in enumerate(seed):
            given.setdefault((k, frozenset(r.order)), []).append(r)

    def frame(k: int, r):
        """Day k's frame for a laid-out day: a time of day it gave up pulls no early start (as engine._ctxs_for)."""
        free = {**by_place, **{i: replace(by_place[i], pins=()) for i in r.unpinned if i in by_place}}
        return pull_early(frames[k], list(r.order), free, travel)[0]

    def rank(option) -> tuple:
        """One day's options by what its reader sees: problems, meals missed, then the day's own objective terms."""
        cx, r = option
        return len(validate([cx], [r], hard, set(), None, max_leg)), meals_missed(cx, r), round(day_value(cx, r), 1)

    def lay(k: int, ids: frozenset):
        key = (k, ids)
        if key in laid:
            return laid[key]
        if k in keep and ids == split0[k]:
            laid[key] = (frame(k, current[k]), current[k])
            return laid[key]
        options = [(frame(k, current[k]), current[k])] if ids == split0[k] else []   # a tie keeps the day as it is
        cx, _ = pull_early(frames[k], sorted(ids), by_place, travel)
        seed = list(current[k].order) if ids == split0[k] else None
        options.append((cx, order_day(sorted(ids), cx) if len(ids) <= EXACT_N else improve_order(sorted(ids), cx, seed)))
        for r in given.get(key, ()):
            options.append((frame(k, r), r))
            if len(ids) > 1:
                options.append((cx, simulate_order(list(r.order), cx, hard, None, max_leg)))
        laid[key] = min(options, key=rank)
        return laid[key]

    def score(split) -> Scored:
        days = [lay(k, ids) for k, ids in enumerate(split)]
        ctxs, results = [cx for cx, _ in days], [r for _, r in days]
        key, parts = objective(ctxs, results, hard=hard, anchors=anchors, max_leg=max_leg)
        return Scored(tuple(tuple(r.order) for r in results), tuple(results), key, parts)

    ctxs0 = [frame(k, r) for k, r in enumerate(current)]
    key0, parts0 = objective(ctxs0, list(current), hard=hard, anchors=anchors, max_leg=max_leg)
    now = Scored(tuple(tuple(r.order) for r in current), tuple(current), key0, parts0)
    if not movable and all(len(ids) <= 1 for ids in split0):
        return now, now
    starts = [split0, *_sweeps(est, split0, movable, may, points, home_at)]
    found: dict = {}
    for start in starts:
        if time.monotonic() >= deadline:
            break
        split = _local_search(est, start, movable, may, deadline)
        found.setdefault(tuple(split), est.cost(split))
    found.setdefault(tuple(split0), est.cost(split0))
    ranked = sorted(found, key=lambda s: (found[s], [sorted(x) for x in s]))
    # the current split always gets the real clock: the same days in a better order are a win too
    seeded = [tuple(frozenset(r.order) for r in seed) for seed in seeds]
    pool = list(dict.fromkeys([tuple(split0), *seeded,
                               *[s for s in ranked if s != tuple(split0)][:CANDIDATES - 1]]))
    best = now
    for n, split in enumerate(pool):
        if n > len(seeded) and time.monotonic() >= deadline:
            break
        got = score(list(split))
        if improves(got, now) and got.key < best.key:
            best = got
    return now, best
