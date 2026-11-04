"""A read fork preserves runtime identity without holding writer locks while rendering."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

import planning
from planning.session import Store
from test_planning_ghosts import engine_for
from test_planning_safety_warnings import setup_safety


@pytest.mark.parametrize("edited", [False, True])
def test_read_fork_exactly_matches_live_views_and_runtime_tokens(edited):
    records, d = setup_safety()
    engine = engine_for(records, Store(None))
    engine.route_fn = lambda *args: None
    sid = engine.create(d)["id"]
    if edited:
        engine.act(sid, {"type": "drop_place", "place": "chosen"})
        engine.act(sid, {"type": "undo"})
    preview = engine.preview_act(sid, {"type": "drop_place", "place": "chosen"})
    before = engine.store.get(sid).model_dump(mode="json")
    reader = planning.fork_readonly(engine, sid)
    assert reader.load(sid) == engine.load(sid)
    assert reader.suggestions(sid) == engine.suggestions(sid)
    assert reader.variants(sid) == engine.variants(sid)
    assert reader.lodging(sid) == engine.lodging(sid)
    assert reader.routes(sid) == engine.routes(sid)
    assert reader.store.get(sid).model_dump(mode="json") == before
    assert reader._base[sid].generation == engine._base[sid].generation
    assert reader._base[sid].trip.by_id is engine._base[sid].trip.by_id
    assert reader._base[sid].trip.by_place["chosen"].rec is records[0]
    assert reader._base[sid].trip.cfg is engine._base[sid].trip.cfg
    assert reader._epochs == {sid: engine._epochs.get(sid, 0)}
    assert reader._preview_tokens[sid] == engine._preview_tokens[sid]
    assert reader._preview_tokens[sid][0]["token"] == preview["token"]
    reader.act(sid, {"type": "drop_place", "place": "chosen"})
    assert engine.store.get(sid).model_dump(mode="json") == before
    assert engine._preview_tokens[sid][0]["token"] == preview["token"]
    engine.act(sid, {"type": "drop_place", "place": "chosen", "_preview_token": preview["token"]})


def test_read_fork_is_stable_while_writer_advances_and_does_not_hold_its_lock(monkeypatch):
    records, d = setup_safety()
    engine = engine_for(records, Store(None))
    sid = engine.create(d)["id"]
    expected = engine.load(sid)
    reader = planning.fork_readonly(engine, sid)
    entered, release = Event(), Event()
    render = reader._view

    def slow_view(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return render(*args, **kwargs)

    monkeypatch.setattr(reader, "_view", slow_view)
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = executor.submit(reader.load, sid)
        assert entered.wait(5)
        try:
            write = executor.submit(engine.act, sid, {"type": "drop_place", "place": "chosen"})
            write.result(timeout=3)
        finally:
            release.set()
        assert pending.result(timeout=5) == expected
    assert reader.store.root is None
    assert reader.store.get(sid) is not engine.store.get(sid)


def test_pending_background_work_keeps_its_exact_snapshot_status_and_starts_no_workers(monkeypatch):
    records, d = setup_safety()
    engine = engine_for(records, Store(None))
    sid = engine.create(d)["id"]
    base = engine._base[sid]
    base.suggestions.clear()
    active = engine._active_itinerary(engine.store.get(sid), base)
    base.pending.add(active["context_key"])
    engine.background = True
    expected = engine.load(sid)
    reader = planning.fork_readonly(engine, sid)
    monkeypatch.setattr("threading.Thread.start", lambda self: pytest.fail("read fork started a worker"))
    assert reader.load(sid) == expected
    assert reader.suggestions(sid) == engine.suggestions(sid)


def test_cold_session_fork_matches_the_current_load_path():
    records, d = setup_safety()
    writer = engine_for(records, Store(None))
    sid = writer.create(d)["id"]
    cold = engine_for(records, Store(None))
    cold.store.restore(writer.store.get(sid).model_copy(deep=True))
    reader = planning.fork_readonly(cold, sid)
    assert reader.load(sid) == cold.load(sid)


def test_cold_background_capture_queues_writer_work_instead_of_pending_forever(monkeypatch):
    records, d = setup_safety()
    writer = engine_for(records, Store(None))
    sid = writer.create(d)["id"]
    cold = engine_for(records, Store(None))
    cold.store.restore(writer.store.get(sid).model_copy(deep=True))
    cold.background = True
    started = []
    monkeypatch.setattr("threading.Thread.start", lambda self: started.append(self))
    reader = planning.fork_readonly(cold, sid)
    assert started
    assert cold._base[sid].pending
    assert reader.load(sid) == cold.load(sid)
    assert len(started) == 1
