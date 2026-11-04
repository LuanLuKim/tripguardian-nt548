import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from corpus.releases import Binding
from harness import Harness, Store
from harness.contracts import Journey, StaleDataVersion
from test_corpus_binding import bundle


def test_background_warmup_returns_before_build_and_request_shares_build():
    active = Binding(release_id="r-active", region="dalat")
    entered, release = threading.Event(), threading.Event()
    calls = []
    tools = bundle()

    def factory(binding):
        calls.append(binding)
        entered.set()
        assert release.wait(5)
        return tools

    h = Harness(None, None, None, Store(None), corpus_binding=active, tools_for_binding=factory)
    worker = h.warm_releases(lambda: [])
    try:
        assert entered.wait(2)
        assert worker.is_alive()
        with ThreadPoolExecutor(2) as executor:
            requests = [executor.submit(h._module, Journey(id="a" * 12, corpus_binding=active), "trip") for _ in range(2)]
            release.set()
            assert all(request.result(3) is tools["trip"] for request in requests)
        assert calls == [active]
        assert h.tools["trip"] is tools["trip"]
    finally:
        release.set()
        worker.join(5)


def test_warmup_limits_distinct_pins_and_keeps_most_recent():
    pins = [Binding(release_id=f"r-{name}", region="dalat") for name in ("active", "newest", "older", "ignored")]
    calls = []

    def factory(binding):
        calls.append(binding)
        return bundle()

    h = Harness(None, None, None, Store(None), corpus_binding=pins[0], tools_for_binding=factory)
    worker = h.warm_releases(lambda: [pins[0], pins[1], pins[1], pins[2], pins[3]])
    worker.join(5)
    assert not worker.is_alive()
    assert len(calls) == 3 and set(calls) == set(pins[:3])
    assert h._module(Journey(id="a" * 12, corpus_binding=pins[1]), "trip")
    assert len(calls) == 3


def test_warmup_logs_bad_release_and_continues_but_request_fails_closed(caplog):
    active, bad, good = [Binding(release_id=f"r-{name}", region="dalat") for name in ("active", "bad", "good")]

    def factory(binding):
        if binding == bad:
            from corpus.releases import PinnedVersionMissing
            raise PinnedVersionMissing("release", "r-bad")
        return bundle()

    h = Harness(None, None, None, Store(None), corpus_binding=active, tools_for_binding=factory)
    with caplog.at_level(logging.WARNING):
        worker = h.warm_releases(lambda: [bad, good])
        worker.join(5)
    assert not worker.is_alive()
    assert "r-bad" in caplog.text and "explicit revalidation" in caplog.text
    assert h._module(Journey(id="a" * 12, corpus_binding=good), "trip")
    with pytest.raises(StaleDataVersion):
        h._module(Journey(id="b" * 12, corpus_binding=bad), "trip")


def test_recent_bindings_query_uses_owned_recent_distinct_pins(pg_url):
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    from harness.__main__ import recent_bindings

    def envelope(name):
        return Jsonb({"corpus_binding": {"release_id": f"r-{name}", "region": "dalat"}})

    with ConnectionPool(pg_url, kwargs={"row_factory": dict_row}) as pool:
        with pool.connection() as conn:
            conn.execute("INSERT INTO users(id) VALUES (%s), (%s) ON CONFLICT DO NOTHING", ("a" * 32, "b" * 32))
            for i, (name, days, owner) in enumerate([
                ("newest", 0, "a" * 32), ("newest", 1, "a" * 32),
                ("older", 2, "b" * 32), ("stale", 8, "a" * 32), ("discarded", 0, None),
            ]):
                conn.execute("INSERT INTO journeys(id, user_id, stage, revision, envelope, updated_at) "
                             "VALUES (%s, %s, 'trip', 0, %s, now() - %s * interval '1 day')",
                             (f"{i:012x}", owner, envelope(name), days))
        assert [b.release_id for b in recent_bindings(pool)] == ["r-newest", "r-older"]


def test_read_only_load_does_not_copy_unrelated_snapshots_or_expose_stored_state(monkeypatch):
    store = Store(None)
    h = Harness(**{f"{stage}_tools": tool for stage, tool in bundle().items()}, store=store)
    view = h.create()
    copies = []
    original = Journey.model_copy

    def counted(self, **kwargs):
        copies.append(kwargs.get("deep", False))
        return original(self, **kwargs)

    monkeypatch.setattr(Journey, "model_copy", counted)
    loaded = h.load(view["id"])
    loaded["sessions"]["trip"] = "changed-by-caller"
    assert store.read(view["id"]).sessions["trip"] == view["sessions"]["trip"]
    assert copies == []


def test_warmup_logs_database_failure_without_stopping_active(caplog):
    active = Binding(release_id="r-active", region="dalat")
    h = Harness(None, None, None, Store(None), corpus_binding=active, tools_for_binding=lambda _: bundle())

    def unavailable():
        raise RuntimeError("database unavailable")

    with caplog.at_level(logging.WARNING):
        worker = h.warm_releases(unavailable)
        worker.join(5)
    assert "database unavailable" in caplog.text
    assert h.tools["trip"]


def test_warmup_restores_recent_journeys_and_survives_a_missing_one(caplog):
    store = Store(None)
    h = Harness(**{f"{stage}_tools": tool for stage, tool in bundle().items()}, store=store)
    view = h.create()
    h._loaded.clear()                    # as after a restart: nothing restored yet
    with caplog.at_level(logging.INFO):
        worker = h.warm_releases(lambda: [], lambda: ["f" * 12, view["id"]])
        worker.join(5)
    assert view["id"] in h._loaded
    assert "Journey warmup failed " + "f" * 12 in caplog.text
    assert "Journey warmup: 1 journeys" in caplog.text
