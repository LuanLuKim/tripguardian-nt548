import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from harness import Conflict, Request, Store
from test_dispatch import decision, make, run


class CountCopies(dict):
    copies = 0

    def __deepcopy__(self, memo):
        type(self).copies += 1
        return type(self)(copy.deepcopy(dict(self), memo))


@pytest.mark.parametrize("operation", ["act", "confirm"])
def test_write_does_not_copy_historical_receipt_payloads(operation):
    from types import SimpleNamespace

    h, _ = make()
    # Memory Store preserves the instrumented payload; PostgreSQL JSON cannot.
    h.store = Store(None)
    view = decision(h)
    if operation == "confirm":
        view = run(h, view, "advance", "planning")
        h.companion = SimpleNamespace(sync=lambda *args: None, quality=lambda *args: {})
    session = h.store.get(view["id"])
    session.receipts["history"] = CountCopies(response={"large": [1, 2, 3]})
    h.store.save(session)
    CountCopies.copies = 0
    out = run(h, view, operation, "next")
    assert out["revision"] == view["revision"] + 1
    assert CountCopies.copies == 0


def test_replay_and_emitter_cannot_mutate_stored_receipt():
    h, _ = make()
    view = decision(h)
    req = Request(request_id="chat", stage="decision", operation="turn", expected_revision=view["revision"],
                  payload={"text": "hello"})
    first = h.request(view["id"], req)
    expected = copy.deepcopy(first)
    first["result"]["view"]["value"] = 98
    replay = h.request(view["id"], req, emit=lambda event, data: data.clear())
    replay["result"]["view"]["value"] = 99
    assert h.request(view["id"], req) == expected
    events = []
    h.request(view["id"], req, emit=lambda event, data: events.append(data))
    assert any(data.get("delta") == "Mình hiểu rồi." for data in events)


def test_module_failure_preserves_entire_envelope_and_receipts(monkeypatch):
    h, tools = make()
    view = decision(h)
    before = h.store.get(view["id"]).model_dump()
    tool = tools["decision"]

    def fail(sid, operation, payload, emit):
        tool.states[sid]["value"] = 99
        emit("view", {"value": 99})
        raise ValueError("mid-module failure")

    monkeypatch.setattr(tool, "apply", fail)
    with pytest.raises(ValueError, match="mid-module"):
        run(h, view, "act", "failed")
    assert h.store.get(view["id"]).model_dump() == before
    assert tool.load(view["sessions"]["decision"])["view"]["value"] == 0


def test_save_failure_preserves_entire_envelope_and_receipts(monkeypatch):
    h, tools = make()
    view = decision(h)
    before = h.store.get(view["id"]).model_dump()
    with monkeypatch.context() as m:
        m.setattr(h.store, "save", lambda session: (_ for _ in ()).throw(OSError("disk full")))
        with pytest.raises(OSError, match="disk full"):
            run(h, view, "act", "failed")
    assert h.store.get(view["id"]).model_dump() == before
    assert tools["decision"].load(view["sessions"]["decision"])["view"]["value"] == 0
    assert run(h, view, "act", "failed")["revision"] == view["revision"] + 1


@pytest.mark.parametrize("same_request", [False, True])
def test_simultaneous_writes_commit_once_and_preserve_history(same_request):
    h, tools = make()
    view = decision(h)
    before = h.store.get(view["id"]).receipts
    gate = Barrier(2)

    def write(request_id):
        gate.wait(timeout=5)
        try:
            return run(h, view, "act", request_id)
        except Conflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["one", "one" if same_request else "two"]))
    assert sum(result is not None for result in results) == (2 if same_request else 1)
    if same_request:
        assert results[0] == results[1]
    saved = h.store.get(view["id"])
    assert saved.revision == view["revision"] + 1
    assert len(saved.receipts) == len(before) + 1
    assert {key: saved.receipts[key] for key in before} == before
    assert tools["decision"].calls == 1


def test_legacy_file_receipts_survive_write_restart_and_external_mutation(tmp_path):
    from harness.contracts import Journey

    store = Store(tmp_path)
    legacy = Journey(id="abcdef012345", receipts={"old": {"response": {"value": [1]}}})
    (tmp_path / f"{legacy.id}.json").write_text(legacy.model_dump_json())
    session = store.get(legacy.id)
    session.revision += 1
    session.receipts["new"] = {"response": {"value": [2]}}
    store.save(session)
    session.receipts["old"]["response"]["value"].append(99)
    session.receipts["new"]["response"]["value"].append(99)
    want = {"old": {"response": {"value": [1]}}, "new": {"response": {"value": [2]}}}
    assert store.get(legacy.id).receipts == want
    assert Store(tmp_path).get(legacy.id).receipts == want
