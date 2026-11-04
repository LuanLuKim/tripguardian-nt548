import pytest

from decision import Data, Engine, Store, Tools, load_settings
from fixtures import hard, si, srec


@pytest.mark.parametrize("group,activity", [("cafe", "coffee"), ("nature", "sightseeing")])
def test_dietary_requirement_outside_eating_does_not_create_a_relax_conflict(group, activity):
    rec = srec("place", group=group, features={"vegetarian_options": "no"})
    engine = Engine(Data([rec]), load_settings(), Store(None))
    search = si(context={"days": 3}, hard_filters=[hard("vegetarian_options", "yes", "eq")],
                activities={"place": activity})
    sid = engine.create(search.model_dump(mode="json"))["id"]
    view = engine.act(sid, {"type": "select", "place_id": "place"})["view"]
    assert not [c for c in view["feasibility"]["conflicts"] if c["check"] == "relax"]
    assert engine.confirm(sid)["confirmed"][0]["relaxed"] == []


@pytest.mark.parametrize("features", [{}, {"vegetarian_options": "no"}])
def test_planning_handoff_preserves_unverified_or_failed_meal_without_relaxing_it(features):
    engine = Engine(Data([srec("meal", group="restaurant", usable=("meal",), features=features)]),
                    load_settings(), Store(None))
    tools = Tools(engine)
    search = si(context={"days": 3}, hard_filters=[hard("vegetarian_options", "yes", "eq")],
                activities={"meal": "eating"})
    sid = tools.create({"search_input": search.model_dump(mode="json")})["id"]
    engine.act(sid, {"type": "select", "place_id": "meal"})
    output = tools.apply(sid, "confirm", {"for_planning": True}, lambda *_: None)
    assert [p["id"] for p in output["confirmed"]] == ["meal"]
    assert output["confirmed"][0]["relaxed"] == []
    assert any("món chay" in flag.lower() for flag in output["confirmed"][0]["flags"])
    assert output["trip_context"]["hard_filters"][0]["unknown_policy"] == "exclude"
    assert engine.load(sid)["view"]["selected"] == ["meal"]
