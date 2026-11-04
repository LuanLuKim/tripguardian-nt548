"""The overload search runs its independent work in forked processes (spec §D.1: first plan p95 < 2 s): the longer-day
offer while the three directions search, and its two widest trials side by side. Same answers as one after another;
the tests time sleeps, not CPU, so a busy machine does not fail them."""

import os
import time
from dataclasses import replace

import pytest


@pytest.fixture(autouse=True)
def fork_only_for_scheduler_probes(monkeypatch, request):
    # These injected closures / short sleeps isolate search scheduling, not native-runtime initialization.
    if request.node.name != "test_spawn_search_works_with_an_open_parent_native_runtime":
        monkeypatch.setattr(overload, "_PROCESS_CONTEXT", "fork")


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


def test_children_share_one_deadline_and_keep_a_fast_answer(monkeypatch):
    from functools import partial

    monkeypatch.setattr(overload, "_FORK_WAIT_S", 0.4)
    started = time.monotonic()
    got = overload._in_children({"a": partial(time.sleep, 2), "b": partial(time.sleep, 2),
                                 "c": partial(time.sleep, 2), "d": partial(time.sleep, 2),
                                 "fast": partial(str, "ready")})
    assert time.monotonic() - started < 1.2
    assert got == {"fast": "ready"}


def test_overload_timeout_does_not_retry_a_hung_child_in_the_parent(monkeypatch):
    original = overload._direction

    def hung(*args):
        time.sleep(0.8)
        return original(*args)

    trip = a_little_short()
    trip = replace(trip, cfg=replace(trip.cfg, realistic={**trip.cfg.realistic, "overload_deadline_s": 0.15}))
    monkeypatch.setattr(overload, "_FORK_WAIT_S", 0.05)
    monkeypatch.setattr(overload, "_direction", hung)
    started = time.monotonic()
    out = plan_or_directions(trip)
    assert time.monotonic() - started < 0.6
    assert any(w["code"] == "overload_deadline" for w in out["warnings"])
    assert out["variants"]
    assert not out["ok"] or any(v["confirmable"] for v in out["variants"])
    for v in out["variants"]:
        if v["violations"] or v["left_over"]:
            assert not v["confirmable"]


def test_deadline_keeps_a_checked_main_draft_when_directions_are_slow(monkeypatch):
    def hung(*args):
        time.sleep(2)

    trip = a_little_short()
    monkeypatch.setattr(overload, "_FORK_WAIT_S", 0.4)
    monkeypatch.setattr(overload, "_direction", hung)
    monkeypatch.setattr(overload, "_extend", lambda *args: {"side": "end", "per_day_min": 60})
    out = plan_or_directions(trip)
    available = [v for v in out["variants"] if v["available"] and v["status"] == "available"]
    assert available and out["back_to_decision"] is None
    assert available[0]["left_over"] and not available[0]["confirmable"]
    assert not available[0]["violations"]
    assert any(w["code"] == "overload_deadline" for w in out["warnings"])
    assert out["overload"]["extend"] is not None


def test_deadline_draft_never_claims_a_required_place_fits(monkeypatch):
    def hung(*args):
        time.sleep(2)

    trip = a_little_short()
    monkeypatch.setattr(overload, "_FORK_WAIT_S", 0.1)
    monkeypatch.setattr(overload, "_direction", hung)
    monkeypatch.setattr(overload, "_extend", hung)
    out = plan_or_directions(trip, protected=set(trip.by_place))
    draft = next(v for v in out["variants"] if v["available"])
    assert not draft["confirmable"] and draft["left_over"]
    assert any(v["kind"] == "anchor" for v in draft["violations"])
    assert not out["ok"] and out["back_to_decision"] is None


def test_deadline_draft_can_be_opened_without_losing_unplaced_selections(monkeypatch):
    from plan_fixtures import CFG, FakeLive, fake_matrix, no_geocode
    from planning import Engine
    from planning.session import Store

    def hung(*args):
        time.sleep(2)

    recs = [spot(f"c{i}", CENTRE, i, visit=(50, 60, 70)) for i in range(4)]
    d = decision([r["id"] for r in recs], days=1,
                 base={"place_id": None, "text": "home", "lat": CENTRE[0], "lng": CENTRE[1]})
    monkeypatch.setattr(overload, "_FORK_WAIT_S", 0.1)
    monkeypatch.setattr(overload, "_direction", hung)
    engine = Engine(recs, cfg=CFG, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode,
                    matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    created = engine.create(d)
    draft = next(v for v in created["view"]["variants"] if v["status"] == "available")
    opened = engine.act(created["id"], {"type": "pick_variant", "id": draft["id"]})
    assert opened["view"]["unplaced"]
    assert "chưa" in created["view"]["overload"]["text"].lower()
    assert "thiếu ~" not in created["view"]["overload"]["text"]
    assert not engine._get(created["id"]).state.plan_dropped
    from planning.engine import NotConfirmable
    with pytest.raises(NotConfirmable):
        engine.confirm(created["id"])


def test_worker_settings_do_not_discard_the_main_day_route_cache():
    from planning.cache import day_key

    trip = a_little_short()
    cx = trip.ctxs[0]
    ids = list(trip.by_place)
    worker = replace(cx, cfg=replace(cx.cfg, direction_workers=1))
    assert day_key(cx, ids) == day_key(worker, ids)
    changed = replace(cx, cfg=replace(cx.cfg, buffer_min={k: v + 1 for k, v in cx.cfg.buffer_min.items()}))
    assert day_key(cx, ids) != day_key(changed, ids)


def test_spawn_scheduler_import_does_not_load_chat_or_retrieval_runtime():
    import subprocess
    import sys

    probe = subprocess.run([sys.executable, "-c",
                            "import planning.overload, sys; "
                            "assert 'trip.api.engine' not in sys.modules; "
                            "assert 'agents.assistant.loop' not in sys.modules; "
                            "assert 'lancedb' not in sys.modules"], capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr


def spawned_hang(path):
    path.write_text(str(os.getpid()))
    time.sleep(60)


def test_spawned_hung_child_is_killed_by_the_shared_deadline(monkeypatch, tmp_path):
    from functools import partial

    monkeypatch.setattr(overload, "_PROCESS_CONTEXT", "spawn")
    pids = tmp_path / "spawned_pid"
    started = time.monotonic()
    assert overload._in_children({"hung": partial(spawned_hang, pids)}, deadline=started + 8) == {}
    assert time.monotonic() - started < 10
    assert pids.exists() and not alive(int(pids.read_text()))


def test_large_trip_payload_does_not_block_spawn_startup_past_deadline(monkeypatch):
    monkeypatch.setattr(overload, "_PROCESS_CONTEXT", "spawn")
    trip = a_little_short()
    trip = replace(trip, decision={**trip.decision, "startup_payload": "x" * 2_000_000},
                   cfg=replace(trip.cfg, realistic={**trip.cfg.realistic, "overload_deadline_s": 0.2}))
    started = time.monotonic()
    out = plan_or_directions(trip)
    assert time.monotonic() - started < 1.5
    assert out["warnings"][0]["code"] == "overload_deadline"


def parent_runtime_absent():
    import multiprocessing
    import sys
    return "parent_runtime_marker" not in sys.modules and multiprocessing.get_start_method() == "spawn"


def test_spawn_search_works_with_an_open_parent_native_runtime(monkeypatch):
    import sys
    import types

    # A fork would inherit this live parent-only native runtime marker.
    monkeypatch.setitem(sys.modules, "parent_runtime_marker", types.ModuleType("parent_runtime_marker"))
    assert overload._in_children({"runtime": parent_runtime_absent}) == {"runtime": True}
    trip = a_little_short()
    out = plan_or_directions(trip)
    assert out["overload"] and out["ok"]
    assert not out["warnings"]
    assert any(v["dropped"] for v in out["variants"])


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
