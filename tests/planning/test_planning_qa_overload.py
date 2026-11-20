"""plan-qa 04/11: a trip the days can hold is never called overloaded, and no exit from Planning skips the validator."""

from plan_fixtures import CENTRE, decision, prepared, spot

from planning.build import schedule_trip
from planning.overload import _over


def dinner_only_restaurant(pid, i, **kw):
    """Open from 15:00, tagged as a sunset spot: its sunset time (before the 17:30 dinner window) is only a wish."""
    hours = {d: [["15:00", "22:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    return spot(pid, CENTRE, i, hours=hours, group="restaurant", usable=("meal", "backup"), visit=(60, 90, 90),
                features={"sunset_view": "present"})


def test_two_restaurants_fit_two_days_even_when_one_has_a_sunset_wish_off_its_meal_window():
    recs = [dinner_only_restaurant("cuk", 0), spot("buffet", CENTRE, 1, group="restaurant", usable=("meal", "backup"), hours=None, visit=(15, 20, 30))]
    d = decision(["cuk", "buffet"], days=2, arrive_at="14:00", leave_at="13:00",
                 base={"place_id": None, "text": "home", "lat": CENTRE[0], "lng": CENTRE[1]})
    s = schedule_trip(prepared(d, recs))
    assert not s.leftover, s.leftover
    assert not _over(s)


# --- the validator catches plans that are wrong, whichever path made them -----------------------------------------

from plan_fixtures import day_ctx, rec

from planning.model import DayResult, Item
from planning.validate import validate


def _result(*items):
    return DayResult(tuple(items), (), (), 0, 0, items[-1].end if items else 0)


def _visit(pid, start, end):
    return Item("visit", start, end, place_id=pid, name=pid)


def _kinds(cx, res, **kw):
    return sorted({v.kind for v in validate([cx], [res], list(kw.get("hard", ())), set(), kw.get("budget"), kw.get("max_leg"))})


FAR = 0.09          # about 10 km between two places: well over an hour by motorbike on the rough road factor


def test_two_visits_back_to_back_with_no_road_between_far_places_fail():
    cx = day_ctx([rec("a", 11.9, 108.4), rec("b", 11.9 + FAR, 108.4)], minutes=40, start_node="h", end_node="h", extra_nodes=["h"])
    res = _result(Item("travel", 480, 520, from_id="h", to_id="a"), _visit("a", 520, 580), _visit("b", 580, 640),
                  Item("travel", 640, 680, from_id="b", to_id="h"))
    assert "travel" in _kinds(cx, res)


def test_a_day_that_never_goes_home_when_it_should_fails():
    cx = day_ctx([rec("a", 11.9, 108.4)], minutes=40, start_node="h", end_node="h", extra_nodes=["h"])
    res = _result(Item("travel", 480, 520, from_id="h", to_id="a"), _visit("a", 520, 580))
    assert "travel" in _kinds(cx, res)


def test_a_first_visit_with_no_road_from_the_start_node_fails():
    cx = day_ctx([rec("a", 11.9, 108.4)], minutes=40, start_node="h", end_node="h", extra_nodes=["h"])
    res = _result(_visit("a", 480, 540), Item("travel", 540, 580, from_id="a", to_id="h"))
    assert "travel" in _kinds(cx, res)


# --- every way out of Planning goes through the same check ------------------------------------------------------

import pytest



def _started():
    from test_planning_engine import two_day_started
    return two_day_started()


def test_a_window_too_small_for_the_picks_is_confirmed_with_the_left_out_places_named():
    e, sid = _started()
    e.act(sid, {"type": "set_day_window", "day": 0, "start": "09:00", "end": "09:20"})
    out = e.confirm(sid)
    assert any(w.get('code') == 'picks_left_out' for w in out['warnings'])


@pytest.mark.parametrize("start", ["03:00", "23:30"])
def test_a_visit_forced_outside_the_opening_hours_is_kept_and_flagged(start):
    # owner 2026-11-09: the user's time stands; what it breaks is a warning on the plan, never a refusal
    e, sid = _started()
    view = e.act(sid, {"type": "set_stop_time", "place": "c1", "start": start})["view"]
    assert view["violations"]
