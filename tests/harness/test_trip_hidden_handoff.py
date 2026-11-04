"""Journey handoffs carry Trip reports without removing manual choices."""

import pytest
import test_dispatch
from fixtures import srec
from test_dispatch import Tools as FakeTools, run

from decision import Data, Engine, Store as DecisionStore, Tools as DecisionTools, load_settings
from harness import Harness


class ReportTrip(FakeTools):
    def __init__(self):
        super().__init__("trip")

    def create(self, payload):
        result = super().create(payload)
        self.states[result["id"]]["state"] = {"meta": {"hidden_ids": []}}
        return self.load(result["id"])

    def apply(self, sid, operation, payload, emit):
        if operation == "refine":
            self.states[sid]["state"]["meta"]["hidden_ids"] = ["closed", "chosen"]
        return super().apply(sid, operation, payload, emit)

    def read(self, sid, operation, payload):
        if operation == "search_input":
            events = []
            self._compiled(sid, lambda event, data: events.append(data))
            return events[-1]["search_input"]
        return super().read(sid, operation, payload)


def make(tmp_path):
    trip = ReportTrip()
    decision = DecisionTools(Engine(Data([
        srec("open", name="Open cafe"),
        srec("closed", name="Reported cafe"),
        srec("chosen", name="Chosen cafe"),
    ]), load_settings(), DecisionStore(None)))
    harness = Harness(trip, decision, FakeTools("planning"), test_dispatch.STORE(tmp_path))
    view = run(harness, harness.create(), "turn", "compile", {"kind": "show"})
    return harness, trip, decision, view


def test_trip_hidden_ids_reach_decision_creation(tmp_path):
    harness, trip, decision, view = make(tmp_path)
    trip.states[view["sessions"]["trip"]]["state"]["meta"]["hidden_ids"] = ["closed"]
    view = run(harness, view, "advance", "choose")
    assert set(view["result"]["view"]["shortlist"]) == {"open", "chosen"}
    found = decision.read(view["sessions"]["decision"], "search", {"q": "Reported"})
    assert found["cards"] == [] and found["outside"] == []


@pytest.mark.parametrize("path", ["advance", "trip", "refine"])
def test_new_trip_reports_reach_rebase_and_keep_manual_selection(tmp_path, path):
    harness, trip, decision, view = make(tmp_path)
    view = run(harness, view, "advance", "choose")
    view = run(harness, view, "act", "select", {"type": "select", "place_id": "chosen"})
    assert "closed" in view["result"]["view"]["shortlist"]
    if path == "refine":
        # Simulate the assistant's internal Trip forwarding event, never call a model.
        original = decision.apply

        def forward(sid, operation, payload, emit):
            if operation == "turn":
                emit("trip", {"texts": ["Reported cafe đã đóng cửa"]})
                emit("done", {})
                return decision.load(sid)
            return original(sid, operation, payload, emit)

        decision.apply = forward
        view = run(harness, view, "turn", "report", {"text": "Reported cafe đã đóng cửa"})
    else:
        if path == "advance":
            view = run(harness, view, "back", "back-to-trip")
            view = run(harness, view, "turn", "recompile", {"kind": "show"})
        trip.states[view["sessions"]["trip"]]["state"]["meta"]["hidden_ids"] = ["closed", "chosen"]
        view = run(harness, view, "advance" if path == "advance" else "trip", "rebase",
                   {} if path == "advance" else {"kind": "readback_ok"})
    assert set(view["result"]["view"]["shortlist"]) == {"open", "chosen"}
    assert view["result"]["view"]["selected"] == ["chosen"]
    assert "closed" not in decision.read(view["sessions"]["decision"], "page", {"group": "cafe", "n": 1})["view"]["shortlist"]
