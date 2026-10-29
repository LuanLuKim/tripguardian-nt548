"""The overload search runs its independent work in forked processes (spec §D.1: first plan p95 < 2 s): the longer-day
offer while the three directions search, and its two widest trials side by side. Same answers as one after another;
the tests time sleeps, not CPU, so a busy machine does not fail them."""

import os
import time
from dataclasses import replace

from plan_fixtures import CENTRE, decision, prepared, spot

import planning.overload as overload
from planning.overload import _Runs, _extend, plan_or_directions


def trip_of(recs, **kw):
    d = decision([r["id"] for r in recs], base={"place_id": None, "text": "home", "lat": CENTRE[0], "lng": CENTRE[1]},
                 **kw)
    return prepared(d, recs)


def a_little_short():
    """One day an hour short: the longer-day search is quick (a few hundredths of a second)."""
    return trip_of([spot(f"c{i}", CENTRE, i, visit=(50, 60, 70)) for i in range(4)], days=1)


def workers(trip, directions):
    return replace(trip, cfg=replace(trip.cfg, direction_workers=directions), routes={})


def public(out):
    """The plan output without the in-process objects (_results, _ctxs, _home) and the call count."""
    strip = lambda v: {k: x for k, x in v.items() if not k.startswith("_")}
    return {**{k: x for k, x in out.items() if k not in ("variants", "schedule_calls")},
            "variants": [strip(v) for v in out["variants"]]}


def test_the_longer_day_is_searched_while_the_directions_are(monkeypatch):
    slow_direction, slow_extend = overload._direction, overload._extend

    def direction(*a):
        time.sleep(1.0)
        return slow_direction(*a)

    def extend(*a):
        time.sleep(1.0)
        return slow_extend(*a)

    trip = a_little_short()
    expected = public(plan_or_directions(workers(trip, 1)))
    monkeypatch.setattr(overload, "_direction", direction)
    monkeypatch.setattr(overload, "_extend", extend)
    started = time.perf_counter()
    out = plan_or_directions(workers(trip, 3))
    assert time.perf_counter() - started < 1.8      # one after the other: >= 2 s of sleep alone
    assert public(out) == expected and out["overload"]["extend"]


def test_the_two_widest_longer_days_are_tried_side_by_side(monkeypatch):
    trip = a_little_short()
    main = overload.schedule_trip(trip)
    slow, here = overload.schedule_trip, []

    def schedule_trip(*a, **k):
        here.append(1)                              # a call in this process (a forked child's are not seen)
        return slow(*a, **k)

    monkeypatch.setattr(overload, "schedule_trip", schedule_trip)
    serial = _extend(workers(trip, 1), _Runs(trip), main)
    n_serial, here[:] = len(here), []
    forked = _extend(workers(trip, 3), _Runs(trip), main)
    assert serial and forked == serial and len(here) == n_serial - 2


def test_parallel_search_finds_the_same_plans_as_one_after_another():
    trip = trip_of([spot(f"c{i}", CENTRE, i, visit=(120, 150, 180), price={"typical_vnd": 10_000 * (i + 1)})
                    for i in range(10)], days=2)
    serial = public(plan_or_directions(workers(trip, 1)))
    assert serial["overload"]
    assert public(plan_or_directions(workers(trip, 3))) == serial


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:                                            # a zombie is not running
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def alive_pids(path):
    return path.exists() and any(alive(int(p)) for p in path.read_text().split())


def test_a_timed_out_child_takes_its_grandchildren_with_it(monkeypatch, tmp_path):
    """The longer-day child forks two trials of its own: when the child is given up on, they must not run on."""
    pids = tmp_path / "pids"
    monkeypatch.setattr(overload, "_FORK_WAIT_S", 0.5)

    def grandchild():
        with open(pids, "a") as f:
            f.write(f"{os.getpid()}\n")
        time.sleep(60)

    def child():
        overload._in_children({"a": grandchild, "b": grandchild})
        return "never"

    assert overload._in_children({"x": child}) == {}
    deadline = time.time() + 5
    while time.time() < deadline and alive_pids(pids):
        time.sleep(0.05)
    found = [int(p) for p in pids.read_text().split()]
    assert len(found) == 2 and not any(alive(p) for p in found)
