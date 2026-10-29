"""The day-level risk terms Planning's objectives still read (planning.days): rain on exposed places, repeats of one
kind, a wanted place on a short or rainy day. How places are split over days is layout.py's (test_planning_layout*)."""

from plan_fixtures import day_ctx, rec

from planning.days import day_risk, exposed_risk, pref_risk, repeats


def test_exposed_places_count_only_with_a_forecast():
    wet = rec("w", 1, 1, features={"weather_exposed": "present"})
    rainy, unknown = (day_ctx([wet], rain=r) for r in (0.8, None))
    assert exposed_risk(["w"], rainy) == 0.8 and exposed_risk(["w"], unknown) == 0.0


def test_two_places_of_one_kind_on_a_day_repeat_and_unknown_kinds_do_not():
    cx = day_ctx([rec("a", 1, 1, group="cafe"), rec("b", 1, 1, group="cafe"), rec("c", 1, 1, group="park"),
                  rec("u", 1, 1, group=None), rec("v", 1, 1, group=None)])
    assert repeats(["a", "b", "c"], cx) == 1 and repeats(["a", "c"], cx) == 0 and repeats(["u", "v"], cx) == 0


def test_a_wanted_place_costs_more_on_a_short_or_rainy_day():
    recs = [rec("a", 1, 1)]
    full = day_ctx(recs, prefs={"a": 1.0})
    short = day_ctx(recs, prefs={"a": 1.0}, end=870)                        # 08:00-14:30: half of 08:00-21:00
    rainy = day_ctx(recs, prefs={"a": 1.0}, rain=0.5)
    assert day_risk(full) == 0.0 and day_risk(short) == 0.5 and day_risk(rainy) == 0.5
    assert pref_risk(["a"], short) == 0.5 and pref_risk(["a"], day_ctx(recs)) == 0.0
