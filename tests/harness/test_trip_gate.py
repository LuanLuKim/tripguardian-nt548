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


def test_h4_a_chat_turn_on_lua_chon_goes_to_trip_and_rebuilds_the_lists_only_when_the_trip_moved():
    """There is no separate chat screen: Trip's chat runs beside Lựa chọn (decision.trip with any turn kind)."""
    from harness import Request
    h, tools = make()
    v = decision(h)
    did = v["sessions"]["decision"]
    days = {"n": 2}

    def read(sid, operation, payload):
        if operation == "readback":
            return dict(READBACK, missing=[])
        out = []
        tools["trip"]._compiled(sid, lambda event, data: out.append(data["search_input"]))
        return {**out[-1], "context": {**out[-1]["context"], "days": days["n"]}}

    tools["trip"].read = read

    def chat(view, rid, text):
        events = []
        out = h.request(view["id"], Request(request_id=rid, stage="decision", operation="trip", expected_revision=view["revision"],
                                            payload={"kind": "text", "text": text}), emit=lambda e, d: events.append(e))
        return out, events

    v, events = chat(v, "chat-same", "Đà Lạt có gì vui?")
    assert v["stage"] == "decision" and "view" not in events and "rebased" not in tools["decision"].states[did]
    days["n"] = 3
    v, events = chat(v, "chat-moved", "đi 3 ngày nhé")
    assert v["stage"] == "decision" and "view" in events and events.index("view") > events.index("done")
    assert tools["decision"].states[did]["rebased"] == 3 and v["outputs"]["trip"]["context"]["days"] == 3
    v = run(h, v, "trip", "tap", {"kind": "deck", "answers": {"care": ["none"]}})
    assert v["stage"] == "decision"


def test_h4c_a_chat_message_about_the_lists_is_answered_by_decision_and_its_trip_wish_by_trip():
    from harness import Request
    h, tools = make()
    v = decision(h)
    read = tools["decision"].read
    tools["decision"].read = lambda sid, op, payload: {"route": "decision"} if op == "route" else read(sid, op, payload)
    events = []
    v = h.request(v["id"], Request(request_id="chat-list", stage="decision", operation="trip", expected_revision=v["revision"],
                                   payload={"kind": "text", "text": "yên tĩnh hơn"}), emit=lambda e, d: events.append((e, d)))
    assert v["stage"] == "decision" and "trip" not in [e for e, _ in events]
    assert tools["trip"].states[v["sessions"]["trip"]]["refined"] == "muốn yên tĩnh hơn"
    assert any(e == "view" and d["diff"]["text"].startswith("Giữ 22") for e, d in events)


def test_h4d_the_chat_on_lich_trinh_edits_the_schedule_or_asks_trip_without_touching_it():
    from harness import Request
    h, tools = make()
    v = decision(h)
    v = run(h, v, "act", "pick")
    v = run(h, v, "advance", "to-planning")
    assert v["stage"] == "planning"
    read = tools["decision"].read
    ways = {"Dời sang ngày 2": "planning", "Tháng này có lễ hội gì?": "trip"}
    tools["decision"].read = lambda sid, op, payload: {"route": ways[payload["text"]]} if op == "route" else read(sid, op, payload)
    plan_before = tools["planning"].calls
    trip_before = tools["trip"].calls

    def chat(view, rid, payload):
        return h.request(view["id"], Request(request_id=rid, stage="planning", operation="trip", expected_revision=view["revision"], payload=payload))

    v = chat(v, "plan-edit", {"kind": "text", "text": "Dời sang ngày 2"})
    assert v["stage"] == "planning" and tools["planning"].calls == plan_before + 1 and tools["trip"].calls == trip_before
    v = chat(v, "plan-ask", {"kind": "text", "text": "Tháng này có lễ hội gì?"})
    assert v["stage"] == "planning" and tools["planning"].calls == plan_before + 1 and tools["trip"].calls == trip_before + 1
    with pytest.raises(ValueError):
        chat(v, "plan-deck", {"kind": "deck", "answers": {"care": ["none"]}})


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


def test_real_trip_adapter_plans_only_after_the_health_hint_the_user_raised_is_answered(tmp_path, monkeypatch):
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
    assert err.value.missing == ["care"]  # only the health hint the user raised; no dates asked (owner 2026-11-18)
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


def test_an_answer_planning_never_reads_keeps_the_plan_and_one_it_reads_drops_it(tmp_path, monkeypatch):
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
    v = run(h, v, "trip", "dates", {"kind": "deck", "answers": {"trip.dates": "2026-11-20..2026-11-22"}})
    v = run(h, v, "trip", "care", {"kind": "deck", "answers": {"care": ["none"]}})
    v = run(h, v, "advance", "plan")
    planning_id = v["sessions"]["planning"]
    # the way in and where the trip starts do not change a plan: it, and the decision it came from, stay
    v = run(h, v, "back", "back-1")
    v = run(h, v, "trip", "origin", {"kind": "edit", "target": "origin", "value": '{"text": "Hồ Chí Minh", "lat": 10.77, "lng": 106.7, "province": null}'})
    assert v["sessions"]["planning"] == planning_id and "decision" in v["outputs"]
    assert v["outputs"]["trip"]["context"]["origin"]["text"] == "Hồ Chí Minh"
    v = run(h, v, "trip", "arrival", {"kind": "deck", "answers": {"arrival": ["plane"]}, "at": "plan"})
    assert v["sessions"]["planning"] == planning_id and v["outputs"]["trip"]["context"]["arrival_mode"] == "plane"
    v = run(h, v, "advance", "again")
    assert v["stage"] == "planning" and v["sessions"]["planning"] == planning_id
    v = run(h, v, "back", "back-2")
    # the pace is read by Planning: the plan is built again
    v = run(h, v, "trip", "pace", {"kind": "deck", "answers": {"pace": ["slow"]}, "at": "plan"})
    assert "planning" not in v["sessions"] and "decision" not in v["outputs"]
