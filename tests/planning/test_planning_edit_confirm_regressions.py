"""Edits expose a resolution before confirm; exact stop times use the checked clock."""

import pytest

from plan_fixtures import CENTRE, FakeLive, decision, fake_matrix, no_geocode, rec
from planning.engine import Engine, NotConfirmable
from planning.session import ActionError, Store
from test_planning_assistant import Script, call, reply, say, tool_results, turn


def started():
    records = [rec("horizon", *CENTRE, name="Horizon Kids & Coffee", visit=(30, 60, 60))]
    e = Engine(records, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode,
               matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    sid = e.create(decision(["horizon"], days=2, leave_at="12:00"))["id"]
    e.act(sid, {"type": "pick_variant", "id": e.variants(sid)[0]["id"]})
    return e, sid


def visit(view):
    return next(i for d in view["itinerary"] for i in d["items"] if i["kind"] == "visit")


def test_an_edit_with_a_problem_names_it_and_a_resolution_and_confirm_stays_the_users():
    e, sid = started()
    e.act(sid, {"type": "move_place", "place": "horizon", "day": 0})
    view = e.act(sid, {"type": "set_day_window", "day": 0, "start": "20:50", "end": "21:00"})["view"]
    assert view["violations"]
    notes = [w for w in view["warnings"] if w["code"] == "plan_violation"]
    assert notes and all(w.get("resolution") and "chốt" in w["text"] for w in notes)
    assert any("Horizon" in w["text"] or "Ngày 1" in w["text"] for w in notes)
    assert e.confirm(sid)["violations"]   # flagged, not gated: the user may still confirm
    e.act(sid, {"type": "undo"})
    assert not [w for w in e.load(sid)["view"]["warnings"] if w["code"] == "plan_violation"]
    assert e.confirm(sid)["violations"] == []


def test_exact_stop_time_and_another_edit_are_one_undoable_replayable_turn():
    e, sid = started()
    e.act(sid, {"type": "move_place", "place": "horizon", "day": 0})
    before = e.load(sid)["view"]["itinerary"]
    position = e._get(sid).position
    e.assistant = chat = Script(reply(call("set_stop_time", place="horizon", start="15:00", quote="đổi Horizon sang 15:00")),
                               reply(call("lock_place", place="horizon", quote="ghim Horizon")), say("Xong."))
    turn(e, sid, "đổi Horizon sang 15:00 và ghim Horizon")
    assert visit(e.load(sid)["view"])["start"] == "15:00"
    assert e._get(sid).position == position + 1
    assert tool_results(chat.seen[1][0])[0]["done"] == "set_stop_time"
    shown = e.load(sid)["view"]["itinerary"]
    e._base.clear()
    e._schedules.clear()
    assert e.load(sid)["view"]["itinerary"] == shown
    e.act(sid, {"type": "undo"})
    assert e.load(sid)["view"]["itinerary"] == before
    e.act(sid, {"type": "redo"})
    assert e.load(sid)["view"]["itinerary"] == shown
    e.confirm(sid)


@pytest.mark.parametrize("start", ["23:00", "25:00", "15:99"])
def test_a_refused_stop_time_changes_neither_history_nor_plan(start):
    e, sid = started()
    before = e._get(sid).model_dump()
    shown = e.load(sid)["view"]["itinerary"]
    e.assistant = chat = Script(reply(call("set_stop_time", place="horizon", start=start, quote=f"Horizon sang {start}")), say("Không đổi được."))
    turn(e, sid, f"đổi Horizon sang {start}")
    result = tool_results(chat.seen[1][0])[0]
    assert "error" in result
    after = e._get(sid).model_dump()
    for key in ("states", "position", "log", "output"):
        assert after[key] == before[key]
    assert e.load(sid)["view"]["itinerary"] == shown


def test_exact_time_cannot_move_departure_or_leave_a_redoable_rejected_edit():
    e, sid = started()
    e.act(sid, {"type": "move_place", "place": "horizon", "day": 1})
    before = e._get(sid).model_dump()
    with pytest.raises(ActionError, match="Không đổi giờ"):
        e.act(sid, {"type": "set_stop_time", "place": "horizon", "start": "15:00"})
    assert e._get(sid).model_dump() == before
    with pytest.raises(ActionError, match="nothing to redo"):
        e.act(sid, {"type": "redo"})
    e.confirm(sid)


def test_same_prefix_is_not_authorization_to_change_the_wrong_stop():
    e, sid = started()
    from planning.assistant import PlanTurn
    from datetime import date
    t = PlanTurn(e, sid, "đổi Horizon sang 15:00", date(2026, 12, 12))
    t.aliases["P99"] = {"kind": "place", "id": "other", "name": "Horizon Other"}
    e.by_id["other"] = {"identity": {"name": "Horizon Other"}}
    with pytest.raises(ValueError, match="did not name"):
        t.named("horizon", "đổi Horizon sang 15:00")


def test_timed_move_to_short_departure_day_is_kept_and_told():
    """The user moves a sunset lake to a morning-only departure day: their choice stands, the time of day is given up
    and said (pin_dropped naming the place), and the plan confirms (owner 04/11: never block a user's choice)."""
    records = [rec("lake", *CENTRE, name="Hồ Xuân Hương", features={"sunset_view": "present"})]
    e = Engine(records, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode,
               matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)
    d = decision(["lake"], days=2, leave_at="12:00")
    sid = e.create(d)["id"]
    e.act(sid, {"type": "pick_variant", "id": e.variants(sid)[0]["id"]})
    assert not e.load(sid)["view"]["violations"]
    view = e.act(sid, {"type": "move_place", "place": "lake", "day": 1})["view"]
    assert not any(v["kind"] == "timed" for v in view["violations"])
    assert any(i.get("place_id") == "lake" for i in view["itinerary"][1]["items"])
    assert any(w["code"] == "pin_dropped" and "Hồ Xuân Hương" in w["text"] for w in view["warnings"])
    e.confirm(sid)


def test_validator_checks_exact_start_even_when_feature_pins_are_released():
    from dataclasses import replace
    from plan_fixtures import day_ctx
    from planning.schedule import simulate
    from planning.validate import validate
    cx = day_ctx([rec("p", *CENTRE)], start=480, end=1260)
    result = simulate(["p"], cx)
    cx = replace(cx, places={"p": replace(cx.places["p"], start_time=900)})
    result = replace(result, unpinned=("p",))
    assert any(v.kind == "start_time" for v in validate([cx], [result], [], set(), None, None))


def test_exact_time_tool_capability_is_permitted_by_the_loaded_planning_skill():
    from planning import Tools
    from agents import permit_tool
    e, _ = started()
    assert permit_tool(Tools(e).skill, "planning.set_stop_time").access == "write"
