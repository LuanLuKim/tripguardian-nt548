import sys
from types import SimpleNamespace


def test_lazy_records_does_not_build_until_data_is_read():
    from harness.__main__ import _LazyRecords
    calls = []

    def records():
        calls.append(True)
        return [{"id": "real-place", "name": "Real place"}]

    lazy = _LazyRecords(records)
    assert calls == []
    assert lazy.get("real-place")["name"] == "Real place"
    assert lazy.get("missing") is None
    assert list(lazy) == ["real-place"] and len(lazy) == 1
    assert calls == [True]


def test_main_listens_without_waiting_for_active_engine(monkeypatch):
    import harness.__main__ as entry
    from corpus.releases import Binding
    from harness import Store
    from test_corpus_binding import bundle
    import threading

    gate, entered = threading.Event(), threading.Event()
    active = Binding(release_id="r-active", region="dalat")
    worker = None

    def slow_factory(data, trip_live):
        def build(binding):
            entered.set()
            assert gate.wait(5)
            tools = bundle()
            tools["planning"].engine = SimpleNamespace(records=[])
            return tools
        return build

    def serve(harness, *args):
        nonlocal worker
        assert entered.wait(2)
        assert not gate.is_set()
        assert harness.companion is not None
        gate.set()
        assert harness.tools["trip"]
        worker = harness

    monkeypatch.setattr(sys, "argv", ["harness", "serve"])
    monkeypatch.setattr(entry, "pool", lambda: None)
    monkeypatch.setattr(entry, "Accounts", lambda *args: None)
    monkeypatch.setattr(entry, "PgStore", lambda *args: Store(None))
    monkeypatch.setattr(entry, "EventLog", lambda *args: None)
    monkeypatch.setattr(entry, "Social", lambda *args: None)
    monkeypatch.setattr(entry, "Library", lambda *args: None)
    monkeypatch.setattr(entry, "ChatSafety", lambda: None)
    monkeypatch.setattr(entry, "mailer_from_env", lambda: None)
    monkeypatch.setattr(entry, "_eve_store", lambda: None)
    monkeypatch.setattr(entry, "bind", lambda *args, **kwargs: active)
    monkeypatch.setattr(entry, "trip_live_tools", lambda *args: None)
    monkeypatch.setattr(entry, "create_tools_factory", slow_factory)
    monkeypatch.setattr(entry, "recent_bindings", lambda pool: [])
    monkeypatch.setattr(entry, "run", serve)
    try:
        entry.main()
        assert worker is not None
    finally:
        gate.set()
