""""Tối ưu lịch" (docs/PLANNING.md §Tối ưu lịch): a deterministic search, no model; never worse than the plan as shown,
never more road; the user's own moves kept unless they ask for the whole plan; replayed exactly after a restart."""

import pytest
from plan_fixtures import CENTRE, CFG, LODGING, SOUTH, FakeLive, decision, fake_matrix, no_geocode, spot
from planning.engine import Engine
from planning.session import ActionError, Store


def mixed(store=None, agent=None):
    """Two places in the centre, two out south, two days, the days mixed up by the user (a centre place and a south one
    each day): the trip a regrouping saves road on."""
    records = [spot("a", CENTRE, 0), spot("b", CENTRE, 1), spot("c", SOUTH, 0), spot("d", SOUTH, 1)]
    e = Engine(records + LODGING, cfg=CFG, live_cfg=FakeLive(), store=store or Store(None), geocode_fn=no_geocode,
               matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), route_fn=lambda *a: {"points": []},
               background=False, proposal_agent=agent)
    sid = e.create(decision(["a", "b", "c", "d"], days=2))["id"]
    e.act(sid, {"type": "pick_variant", "id": "main"})
    for place, day in [("a", 0), ("c", 0), ("b", 1), ("d", 1)]:
        e.act(sid, {"type": "move_place", "place": place, "day": day})
    return e, sid


def days_of(view) -> list[set]:
    return [{i["place_id"] for i in d["items"] if i["kind"] == "visit"} for d in view["itinerary"]]


def test_the_whole_plan_regroups_the_days_with_less_road_and_no_model():
    async def agent(fields):
        raise AssertionError("the search never asks a model")
    e, sid = mixed(agent=agent)
    before = e.load(sid)["view"]
    out = e.recommend(sid, "all")
    p = out["proposal"]
    assert p["status"] == "accepted" and p["changed"] and p["diagnostics"] == ["optimized"]
    assert p["after"]["travel_min"] < p["before"]["travel_min"]
    assert p["after"]["problems"] <= p["before"]["problems"]
    assert sorted(map(sorted, days_of(out["view"]))) == [["a", "b"], ["c", "d"]]
    assert out["view"]["metrics"]["travel_min"] < before["metrics"]["travel_min"]
    assert not out["view"]["violations"]
    # one step of history: undo gives the user's own days back
    undone = e.act(sid, {"type": "undo"})["view"]
    assert days_of(undone) == days_of(before)


def test_the_users_own_moves_stay_unless_the_whole_plan_is_asked_for():
    e, sid = mixed()
    before = e.load(sid)["view"]
    out = e.recommend(sid)                      # default scope: keep_mine
    assert days_of(out["view"]) == days_of(before)
    assert out["proposal"]["changed"] is False


def test_an_optimised_plan_is_never_worse_and_a_second_run_finds_nothing_more():
    e, sid = mixed()
    first = e.recommend(sid, "all")["proposal"]
    again = e.recommend(sid, "all")["proposal"]
    assert first["changed"]
    assert again == {"status": "accepted", "diagnostics": ["already_best"], "changed": False,
                     "before": again["before"], "after": again["before"]}
    assert again["before"]["value"] <= first["before"]["value"]


def test_a_locked_place_keeps_its_day():
    e, sid = mixed()
    e.act(sid, {"type": "lock_slot", "place": "c"})
    out = e.recommend(sid, "all")
    assert "c" in days_of(out["view"])[0]


def test_the_optimised_plan_is_replayed_exactly_after_a_restart(tmp_path):
    e, sid = mixed(store=Store(tmp_path))
    shown = e.recommend(sid, "all")["view"]
    fresh = Engine(e.records, cfg=CFG, live_cfg=FakeLive(), store=Store(tmp_path), geocode_fn=no_geocode,
                   matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), route_fn=lambda *a: {"points": []},
                   background=False)
    assert fresh.load(sid)["view"]["itinerary"] == shown["itinerary"]


def test_an_unknown_scope_is_refused():
    e, sid = mixed()
    with pytest.raises(ActionError):
        e.recommend(sid, "everything")


def test_optimize_must_keep_exactly_the_plans_places():
    e, sid = mixed()
    with pytest.raises(ActionError):
        e.act(sid, {"type": "optimize", "days": [["a", "b"], ["c"]]})


def test_the_matrix_tour_is_exact_and_open_without_a_lodging():
    from planning.optimize import tour
    from plan_fixtures import line_travel
    travel = line_travel({"h": 0, "x": 1, "y": 2, "z": 3})
    leg = lambda a, b: travel.leg(a, b)[0]          # noqa: E731
    assert tour(travel, "h", "h", ["z", "x", "y"]) == leg("h", "x") + leg("x", "y") + leg("y", "z") + leg("z", "h")
    assert tour(travel, None, None, ["z", "x", "y"]) == leg("x", "y") + leg("y", "z")


def test_regrouping_never_empties_a_day_just_to_save_a_ride_home():
    # three places, three days, one a day (layout.assign's spread_extra_min rule): putting them all on one day saves
    # two rides out and back, but leaves two days the user came for empty
    records = [spot("a", CENTRE, 0), spot("b", CENTRE, 1), spot("c", CENTRE, 2)]
    e = Engine(records + LODGING, cfg=CFG, live_cfg=FakeLive(), geocode_fn=no_geocode, matrix_fn=fake_matrix,
               sun_fn=lambda *a: (360, 1050), route_fn=lambda *a: {"points": []}, background=False)
    sid = e.create(decision(["a", "b", "c"], days=3))["id"]
    e.act(sid, {"type": "pick_variant", "id": "main"})
    before = days_of(e.load(sid)["view"])
    out = e.recommend(sid, "all")
    after = days_of(out["view"])
    assert sum(1 for d in after if d) >= sum(1 for d in before if d)


def test_a_meal_whose_window_closed_before_the_day_began_is_not_missed():
    # an arrival day that starts at 14:00 has no lunch: counting it would make the search empty that day
    from types import SimpleNamespace
    from planning.optimize import meals_missed
    cx = SimpleNamespace(cfg=CFG, day=SimpleNamespace(start=14 * 60))
    r = SimpleNamespace(notes=("meal_missed:lunch", "meal_missed:dinner"))
    assert meals_missed(cx, r) == 1


def test_optimize_refuses_given_up_times_of_day_that_are_not_on_their_day():
    e, sid = mixed()
    days = [sorted(d) for d in days_of(e.load(sid)["view"])]
    with pytest.raises(ActionError):
        e.act(sid, {"type": "optimize", "days": days, "unpinned": [[[days[1][0], ["hours"]]], []]})
