"""Trip redesign part 5 at the harness: "Lập lịch" with an incomplete trip is a 409 the web can answer in place.

Architecture doc §1 A5, §5.7. Ids H1-H4. Before this, planning.TripIncomplete escaped the harness as a 500 and no
real journey could reach Lịch trình.
"""

import pytest
from test_dispatch import decision, make, run

READBACK = {"lines": [{"kind": "said", "text": "T6 20/11 → CN 22/11", "tab": "trip", "undo": None}],
            "digest": "d1", "ok": False, "missing": [], "deck": None}


def gated(tools, missing):
    """Only unanswered dates or care hold planning; the trip module answers reads and turns."""
    from planning import TripIncomplete
    state = {"ok": False, "turns": []}

    create_plan = tools["planning"].create

    def create(payload):
        if not state["ok"]:
            raise TripIncomplete(list(missing))
        return create_plan(payload)

    def read(sid, operation, payload):
        assert operation in ("readback", "search_input")
        if operation == "readback":
            return dict(READBACK, ok=state["ok"], missing=[] if state["ok"] else list(missing))
        out = []
        tools["trip"]._compiled(sid, lambda event, data: out.append(data["search_input"]))
        return out[-1] | {"readiness": {"missing": [], "readback_ok": False}}

    apply_trip = tools["trip"].apply

    def apply(sid, operation, payload, emit):
        if operation == "turn" and payload.get("kind") in ("readback_ok", "deck", "drop"):
            state["turns"].append(payload)
            state["ok"] = payload.get("kind") == "deck" and payload.get("answers") == {"care": ["none"]}
            return tools["trip"].load(sid)
        return apply_trip(sid, operation, payload, emit)

    tools["planning"].create = create
    tools["trip"].read = read
    tools["trip"].apply = apply
    return state


def test_h1_missing_care_is_a_typed_conflict_with_gate_cards_not_a_crash():
    from harness import Conflict, TripNotReady
    h, tools = make()
    v = decision(h)
    gated(tools, ["care"])
    with pytest.raises(TripNotReady) as caught:
        run(h, v, "advance", "to-planning")
    assert isinstance(caught.value, Conflict)
    assert caught.value.missing == ["care"] and caught.value.readback["digest"] == "d1"
    after = h.load(v["id"])
    assert after["stage"] == "decision" and "planning" not in after["sessions"] and after["revision"] == v["revision"]


def test_failed_selected_requirement_does_not_hide_the_trip_question_gate():
    from decision import Data, Engine, Store, Tools, load_settings
    from fixtures import hard, si, srec
    from harness import TripNotReady

    h, tools = make()
    dt = Tools(Engine(Data([srec("meal", group="restaurant", usable=("meal",),
                                features={"vegetarian_options": "no"})]), load_settings(), Store(None)))
    h.tools["decision"] = dt
    v = decision(h)
    search = si(context={"days": 3}, hard_filters=[hard("vegetarian_options", "yes", "eq")],
                activities={"meal": "eating"}).model_dump(mode="json")
    dt.rebase(v["sessions"]["decision"], {"search_input": search})
    v = run(h, v, "act", "select-meal", {"type": "select", "place_id": "meal"})
    gated(tools, ["care"])
    with pytest.raises(TripNotReady) as caught:
        run(h, v, "advance", "to-planning")
    assert caught.value.missing == ["care"]
    assert caught.value.readback["digest"] == "d1"
    assert h.load(v["id"])["stage"] == "decision"
    assert dt.engine.store.get(v["sessions"]["decision"]).output is None


def test_h2_the_last_care_answer_opens_planning_without_readback_confirmation():
    h, tools = make()
    v = decision(h)
    state = gated(tools, ["care"])
    v = run(h, v, "trip", "answer", {"kind": "deck", "answers": {"care": ["none"]}})
    assert v["stage"] == "decision" and state["turns"] == [{"kind": "deck", "answers": {"care": ["none"]}, "at": "gate"}]
    assert v["outputs"]["trip"]["readiness"]["readback_ok"] is False
    assert "rebased" in tools["decision"].states[v["sessions"]["decision"]]  # Lựa chọn sees the same trip
    v = run(h, v, "advance", "to-planning")
    assert v["stage"] == "planning"


def test_h3_a_legacy_confirmation_does_not_waive_unanswered_care():
    from harness import TripNotReady
    h, tools = make()
    v = decision(h)
    gated(tools, ["care"])
    v = run(h, v, "trip", "stale", {"kind": "readback_ok", "value": "old"})
    with pytest.raises(TripNotReady):
        run(h, v, "advance", "to-planning")


def test_h4_only_read_back_answers_reach_the_trip_from_the_decision_stage():
    from harness import RouteError
    h, tools = make()
    v = decision(h)
    gated(tools, ["care"])
    for payload in ({"kind": "text", "text": "đổi sang 5 ngày"}, {"kind": "show"}, {"kind": "answer", "qid": "x"}):
        with pytest.raises((RouteError, ValueError)):
            run(h, v, "trip", f"bad-{payload['kind']}", payload)
    v = run(h, v, "trip", "tap", {"kind": "deck", "answers": {"care": ["none"]}})
    assert v["stage"] == "decision"


def test_h4b_a_field_edit_from_the_summary_or_lich_trinh_reaches_the_trip():
    h, tools = make()
    v = decision(h)
    gated(tools, [])
    origin = '{"text": "Thành phố Hồ Chí Minh", "lat": 10.77, "lng": 106.7, "province": null}'
    v = run(h, v, "trip", "origin", {"kind": "edit", "target": "origin", "value": origin})
    assert v["stage"] == "decision" and "planning" not in v["sessions"]


def test_partial_gate_answers_are_saved_while_a_health_hint_cannot_compile():
    from trip import UnhandledSignal
    from harness import TripNotReady
    h, tools = make()
    v = decision(h)
    state = gated(tools, ["trip", "care"])
    read = tools["trip"].read

    def pending(sid, operation, payload):
        if operation == "search_input":
            raise UnhandledSignal("pregnant")
        return read(sid, operation, payload)

    tools["trip"].read = pending
    v = run(h, v, "trip", "dates", {"kind": "deck", "answers": {"trip.dates": "2026-11-20..2026-11-22"}})
    assert v["revision"] > 0 and state["turns"][-1]["answers"]["trip.dates"] == "2026-11-20..2026-11-22"
    with pytest.raises(TripNotReady):
        run(h, v, "advance", "still-needs-care")


def test_real_trip_adapter_saves_dates_until_the_pending_health_question_is_answered(tmp_path, monkeypatch):
    from datetime import date
    import test_dispatch
    from trip import Catalog, Engine, SessionStore, Settings, Tools, TripState
    from trip.api import engine as trip_engine
    from harness import Harness, TripNotReady

    monkeypatch.setattr(trip_engine, "TURN_LOG", tmp_path / "trip_turns.log")

    def no_model(*_):
        raise AssertionError("gate answers must not call a model")

    trip = Tools(Engine(Catalog.from_records([], n_min=1), Settings(), SessionStore(None), no_model,
                        today=lambda: date(2026, 11, 10)))
    h = Harness(trip, test_dispatch.Tools("decision"), test_dispatch.Tools("planning"), test_dispatch.STORE(tmp_path))
    v = run(h, h.create(), "turn", "compile", {"kind": "show"})
    v = run(h, v, "advance", "choose")
    s = trip.engine.store.get(v["sessions"]["trip"])
    s.state = TripState.model_validate({"signals": [{"kind": "pregnant", "source": "user", "quote": "vợ bầu", "turn": 1}]})
    journey = h._get(v["id"])
    journey.snapshots["trip"] = trip.snapshot(s.id)
    h.store.save(journey)
    with pytest.raises(TripNotReady) as err:
        run(h, v, "advance", "gate")
    assert err.value.missing == ["trip", "care"]
    v = run(h, v, "trip", "dates", {"kind": "deck", "answers": {"trip.dates": "2026-11-20..2026-11-22"}})
    s = trip.engine.store.get(s.id)
    assert s.state.days.value == 3 and s.state.start_date.value == date(2026, 11, 20)
    assert trip.read(s.id, "readback", {})["missing"] == ["care"]
    v = run(h, v, "trip", "not-safe-yet", {"kind": "deck", "answers": {"care": ["none"]}})
    assert trip.read(s.id, "readback", {})["missing"] == ["care"]
    v = run(h, v, "trip", "care", {"kind": "deck", "answers": {"care": ["steps"]}})
    assert v["outputs"]["trip"]["readiness"] == {"missing": [], "readback_ok": False}
    assert all(not getattr(s.state, key).known for key in ("companions", "mobility", "pace", "budget_vnd", "lodging"))
    assert run(h, v, "advance", "plan")["stage"] == "planning"


def test_real_trip_adapter_takes_the_origin_edited_from_lich_trinh(tmp_path, monkeypatch):
    from datetime import date
    import test_dispatch
    from trip import Catalog, Engine, SessionStore, Settings, Tools
    from trip.api import engine as trip_engine
    from harness import Harness

    monkeypatch.setattr(trip_engine, "TURN_LOG", tmp_path / "trip_turns.log")

    def no_model(*_):
        raise AssertionError("a field edit must not call a model")

    trip = Tools(Engine(Catalog.from_records([], n_min=1), Settings(), SessionStore(None), no_model,
                        today=lambda: date(2026, 11, 10)))
    h = Harness(trip, test_dispatch.Tools("decision"), test_dispatch.Tools("planning"), test_dispatch.STORE(tmp_path))
    v = run(h, h.create(), "turn", "compile", {"kind": "show"})
    v = run(h, v, "advance", "choose")
    v = run(h, v, "trip", "care", {"kind": "deck", "answers": {"care": ["none"]}})
    origin = '{"text": "Thành phố Hồ Chí Minh", "lat": 10.77, "lng": 106.7, "province": null}'
    v = run(h, v, "trip", "origin", {"kind": "edit", "target": "origin", "value": origin})
    s = trip.engine.store.get(v["sessions"]["trip"])
    assert v["stage"] == "decision" and s.state.origin.value.text == "Thành phố Hồ Chí Minh"
    assert v["outputs"]["trip"]["context"]["origin"]["text"] == "Thành phố Hồ Chí Minh"
