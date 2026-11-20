"""Keep road estimates distinct from scheduling slack in the public timeline."""

from planning.build import itinerary
from planning.model import Day, DayResult, Item


def test_travel_output_separates_road_minutes_from_buffer_without_changing_clock():
    day = Day(0, None, None, 480, 1260, "@home", "@home")
    result = DayResult((Item("travel", 671, 717, from_id="em", to_id="dream", mode="motorbike", note="+40"),),
                       (), (), 6, 0, 717)
    leg = itinerary([day], [result])[0]["items"][0]
    assert leg["road_min"] == 6
    assert leg["buffer_min"] == 40
    assert (leg["start"], leg["end"]) == ("11:11", "11:57")


def test_walk_output_has_no_invented_buffer():
    day = Day(0, None, None, 480, 1260, None, None)
    result = DayResult((Item("travel", 480, 487, from_id="a", to_id="b", mode="walk"),), (), (), 7, 0, 487)
    leg = itinerary([day], [result])[0]["items"][0]
    assert leg["road_min"] == 7
    assert leg["buffer_min"] == 0


def test_travel_output_carries_the_estimated_road_km_when_the_day_knows_its_points():
    from types import SimpleNamespace

    from planning.travel import Travel

    day = Day(0, None, None, 480, 1260, None, None)
    result = DayResult((Item("travel", 480, 492, from_id="a", to_id="b", mode="motorbike"),), (), (), 12, 0, 492)
    travel = Travel(["a", "b"], [[(0, "none"), (12, "motorbike")], [(12, "motorbike"), (0, "none")]], "osrm", None, 0,
                    [[0.0, 4.2], [4.2, 0.0]])
    cx = SimpleNamespace(travel=travel, pet=False, places={})
    assert itinerary([day], [result], [cx])[0]["items"][0]["distance_km"] == 4.2
    assert "distance_km" not in itinerary([day], [result])[0]["items"][0]  # no points known: nothing is made up
