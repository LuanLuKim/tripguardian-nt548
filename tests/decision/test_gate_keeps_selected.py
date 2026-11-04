"""A hard constraint answered at the gate (before Lịch trình) rebases Decision; the user's picks stay.

Lựa chọn never blocks or nudges: a pick that fails or cannot be checked against the new constraint stays selected, and
the feasibility panel (not the list) names the place and the reason. Physical limits (closed days) never drop a pick either.
"""

import pytest

from decision import Data, Engine, Store, Tools, load_settings
from fixtures import hard, si, srec

CLOSED_MONDAY = {d: [["07:00", "22:00"]] for d in ("tue", "wed", "thu", "fri", "sat", "sun")}
PICKS = ["ok", "bad", "unknown"]


def session(extra=()):
    records = [srec("ok", features={"steep_or_stairs": "absent"}), srec("bad", features={"steep_or_stairs": "present"}),
               srec("unknown"), srec("closed", hours=CLOSED_MONDAY), *extra]
    engine = Engine(Data(records), load_settings(), Store(None))
    tools = Tools(engine)
    sid = tools.create({"search_input": si().model_dump(mode="json")})["id"]
    for pid in PICKS:
        engine.act(sid, {"type": "select", "place_id": pid})
    engine.act(sid, {"type": "lock", "place_id": "ok"})
    return engine, tools, sid


def chosen_cards(view):
    return sorted(c["id"] for g in view["groups"] for c in g["cards"] if c["chosen"])


@pytest.mark.parametrize("policy", ["exclude", "flag"])
def test_picks_survive_a_new_hard_constraint_and_the_panel_names_why(policy):
    engine, tools, sid = session()
    out = tools.rebase(sid, {"search_input": si(hard_filters=[hard("steep_or_stairs", "present", policy=policy)])
                             .model_dump(mode="json")})
    view = out["view"]
    assert view["selected"] == PICKS and chosen_cards(view) == sorted(PICKS)
    assert view["locked"] == ["ok"] and view["pending"] is None
    assert engine.store.get(sid).state.selected == PICKS
    relax = [c for c in view["feasibility"]["conflicts"] if c["check"] == "relax"]
    assert [c["places"] for c in relax] == [["bad"]] and "Nơi bad" in relax[0]["title"]
    assert not any("Nơi unknown" in w for w in view["feasibility"]["warnings"])
    assert next(c for g in view["groups"] for c in g["cards"] if c["id"] == "unknown")["tradeoffs"][0]["text"] == "Chưa rõ có dốc, nhiều bậc"


def test_picks_survive_the_snapshot_round_trip_after_a_gate_rebase():
    engine, tools, sid = session()
    tools.rebase(sid, {"search_input": si(hard_filters=[hard("steep_or_stairs", "present")]).model_dump(mode="json")})
    snapshot = tools.snapshot(sid)
    tools.restore(snapshot)
    assert tools.load(sid)["view"]["selected"] == PICKS
    assert snapshot["state"]["selected"] == PICKS


def test_gate_answers_that_change_who_travels_or_when_keep_the_picks():
    engine, tools, sid = session()
    for context in ({"companions": ["pet"]}, {"days": 4}, {"mobility": "walk"}, {"start_date": "2026-12-15", "days": 1}):
        out = tools.rebase(sid, {"search_input": si(context=context).model_dump(mode="json")})
        assert out["view"]["selected"] == PICKS, context


def test_a_pick_closed_on_the_trip_days_stays_selected_and_is_flagged():
    engine, tools, sid = session()
    engine.act(sid, {"type": "select", "place_id": "closed"})
    view = tools.rebase(sid, {"search_input": si(context={"days": 1}).model_dump(mode="json")})["view"]
    assert "closed" in view["selected"]
    assert any(c["id"] == "hours:closed" for c in view["feasibility"]["conflicts"])


def test_confirm_for_planning_hands_every_pick_over_after_the_gate():
    engine, tools, sid = session()
    tools.rebase(sid, {"search_input": si(hard_filters=[hard("steep_or_stairs", "present")]).model_dump(mode="json")})
    out = tools.apply(sid, "confirm", {"for_planning": True}, lambda *_: None)
    assert [c["id"] for c in out["confirmed"]] == PICKS
