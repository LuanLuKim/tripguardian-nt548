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
