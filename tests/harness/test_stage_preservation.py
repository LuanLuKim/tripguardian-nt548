"""Navigation is not an edit: persisted schedules and summaries survive it."""
from copy import deepcopy


from test_dispatch import decision, make, run


def planned(h, tools, *, confirmed=False):
    view = run(h, decision(h), "advance", "plan")
    sid = view["sessions"]["planning"]
    tools["planning"].states[sid].update(
        assignment={"lavender": 1}, duration={"lavender": 60},
        selected=["lavender", "cafe-a", "cafe-b"], origin="TP.HCM")
    session = h.store.get(view["id"])
    session.outputs["trip"]["context"].update(
        start_date="2026-11-20", days=4, people=4,
        origin={"text": "TP.HCM", "lat": 10.77, "lng": 106.7})
    from trip import SearchInput
    session.outputs["trip"] = SearchInput.model_validate(session.outputs["trip"]).model_dump(mode="json")
    session.snapshots["planning"] = tools["planning"].snapshot(sid)
    if confirmed:
        session.outputs["planning"] = {"itinerary": [{"items": [
            {"kind": "visit", "place_id": pid} for pid in ["lavender", "cafe-a", "cafe-b"]]}]}
    h.store.save(session)
    return h.load(view["id"])


def test_why_not_roundtrip_keeps_three_places_and_manual_day():
    h, tools = make()
    before = planned(h, tools)
    back = run(h, before, "back", "see-selection")
    h.read(back["id"], "decision", "why-not", {"place": "other"})
    after = run(h, back, "advance", "return-plan")
    assert after["sessions"] == before["sessions"]
    assert after["result"] == before["result"]


def test_confirmed_trip_open_understand_and_return_keeps_full_summary_and_edits():
    h, tools = make()
    before = planned(h, tools, confirmed=True)
    summary = h.summaries([before["id"]])[0]
    trip = run(h, run(h, before, "back", "view-decision"), "back", "view-trip")
    for field in ("confirmed", "start_date", "days", "people", "places"):
        assert h.summaries([trip["id"]])[0][field] == summary[field]
    assert trip["outputs"] == before["outputs"]
    decision_view = run(h, trip, "advance", "return-decision")
    after = run(h, decision_view, "advance", "return-plan")
    assert after["sessions"] == before["sessions"]
    assert after["outputs"] == before["outputs"]
    assert after["result"] == before["result"]


def test_reopened_planning_supplies_persisted_origin_not_browser_cache(tmp_path):
    h, tools = make(tmp_path)
    before = planned(h, tools, confirmed=True)
    reopened, _ = make(tmp_path)
    assert reopened.load(before["id"], stage="planning")["outputs"]["trip"]["context"]["origin"]["text"] == "TP.HCM"
    # This is the hydration endpoint used by Plan; it must work without a browser Trip cache.
    loaded = reopened.load(before["id"], stage="planning")
    viewed_trip = run(reopened, run(reopened, loaded, "back", "origin-decision"), "back", "origin-trip")
    assert viewed_trip["outputs"]["trip"]["context"]["origin"]["text"] == "TP.HCM"


def test_real_trip_edit_unconfirms_but_show_does_not(monkeypatch):
    h, tools = make()
    before = planned(h, tools, confirmed=True)
    view = run(h, run(h, before, "back", "edit-decision"), "back", "edit-trip")
    original = deepcopy(before["outputs"]["trip"])
    def turn(sid, operation, payload, emit):
        output = deepcopy(original)
        if payload.get("kind") == "text":
            output["context"]["days"] = 5
        emit("done", {"search_input": output})
        return tools["trip"].load(sid)
    monkeypatch.setattr(tools["trip"], "apply", turn)
    shown = run(h, view, "turn", "show-only", {"kind": "show"})
    assert shown["outputs"] == before["outputs"]
    changed = run(h, shown, "turn", "change-days", {"kind": "text", "text": "5 ngày"})
    assert "planning" not in changed["outputs"]
    assert "decision" not in changed["outputs"]
    assert changed["outputs"]["trip"]["context"]["days"] == 5


def test_feedback_does_not_restore_corpus_or_planning(tmp_path, monkeypatch):
    h, tools = make(tmp_path)
    before = planned(h, tools, confirmed=True)
    reopened, _ = make(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("feedback must not restore corpus or Planning")
    monkeypatch.setattr(reopened, "_module", forbidden)
    assert reopened.feedback(before["id"], {"note": "ok"}) == {"stored": True}
