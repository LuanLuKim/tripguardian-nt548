import json
import logging

import pytest

from test_dispatch import decision, make, run


def advance_logs(caplog):
    return [json.loads(record.getMessage().removeprefix("Harness advance "))
            for record in caplog.records if record.getMessage().startswith("Harness advance ")]


def test_advance_logs_stage_costs_without_changing_handoff(caplog, monkeypatch):
    h, tools = make()
    view = decision(h)
    clock = [100.0]
    monkeypatch.setattr("harness.dispatch.time.monotonic", lambda: clock[0])

    def timed(obj, name, seconds):
        original = getattr(obj, name)

        def call(*args, **kwargs):
            clock[0] += seconds
            return original(*args, **kwargs)

        monkeypatch.setattr(obj, name, call)

    timed(tools["decision"], "apply", 2)
    timed(tools["planning"], "create", 3)
    timed(h.store, "save", 5)
    with caplog.at_level(logging.INFO, logger="harness.dispatch"):
        out = run(h, view, "advance", "span-request")
        replay = run(h, view, "advance", "span-request")
    assert out == replay
    assert out["stage"] == "planning"
    assert out["outputs"]["decision"]["confirmed"] == [{"id": "place-1"}]
    logs = advance_logs(caplog)
    assert len(logs) == 1
    row = logs[0]
    assert row["journey"] == view["id"] and row["request"] == "span-request"
    assert row["pin"] is None and row["status"] == "ok"
    assert row["decision_handoff_ms"] == 2000
    assert row["planning_create_ms"] == 3000
    assert row["store_ms"] == 5000
    assert row["tools_ms"] == row["snapshot_ms"] == row["load_ms"] == 0
    assert row["total_ms"] == 10000


def test_cold_advance_attributes_pinned_factory_to_tools_not_confirm(caplog, monkeypatch):
    from corpus.releases import Binding
    from harness import Harness, Store
    from test_corpus_binding import bundle

    old = Binding(release_id="r-old", region="dalat")
    original = bundle()
    store = Store(None)
    maker = Harness(**{f"{stage}_tools": tool for stage, tool in original.items()}, store=store,
                    corpus_binding=old)
    view = decision(maker)
    clock = [100.0]
    monkeypatch.setattr("harness.dispatch.time.monotonic", lambda: clock[0])

    def factory(binding):
        assert binding == old
        clock[0] += 4
        return bundle()

    restarted = Harness(None, None, None, store, corpus_binding=Binding(release_id="r-new", region="dalat"),
                        tools_for_binding=factory)
    with caplog.at_level(logging.INFO, logger="harness.dispatch"):
        out = run(restarted, view, "advance", "cold-span")
    assert out["outputs"]["decision"]["corpus_binding"]["release_id"] == "r-old"
    row, = advance_logs(caplog)
    assert row["pin"]["release_id"] == "r-old"
    assert row["tools_ms"] == row["load_ms"] == 4000
    assert row["decision_handoff_ms"] == row["planning_create_ms"] == 0


def test_advance_logs_failed_stage_and_keeps_rollback(caplog, monkeypatch):
    h, tools = make()
    view = decision(h)

    def fail(payload):
        raise ValueError("planning failed")

    monkeypatch.setattr(tools["planning"], "create", fail)
    with caplog.at_level(logging.INFO, logger="harness.dispatch"), pytest.raises(ValueError, match="planning failed"):
        run(h, view, "advance", "failed-span")
    assert h.load(view["id"])["stage"] == "decision"
    row, = advance_logs(caplog)
    assert row["status"] == "ValueError"
    assert row["planning_create_ms"] >= 0
    assert "store_ms" not in row
