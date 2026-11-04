"""Prod end-to-end findings of 2026-11-03 (N1, R1, ...): each test is the shape of a trip a tester ran."""

import pytest

from plan_fixtures import CENTRE, all_days, decision, prepared, rec
from realistic_cases import frame

from planning.variants import plan_cards


def framed_trip(recs, fr, *, days, start_date, **kw):
    d = decision([r["id"] for r in recs], days=days, start_date=start_date, mobility="car", **kw)
    d["trip_context"]["context"]["frame"] = fr
    return prepared(d, recs)


def test_one_grill_with_a_misread_review_length_still_gets_a_plan():
    """N1: a review "until 10:30" read as a length made a grill 3,5-8 h; no day could hold it, so the plan was empty."""
    grill = rec("grill", *CENTRE, usable=("meal",), group="restaurant", visit=(210, 345, 480),
                hours={d: [["14:00", "23:00"]] for d in all_days()})
    grill["operation"]["visit_minutes"]["source"] = "reviews"
    trip = framed_trip([grill], frame("2026-11-14", 3), days=3, start_date="2026-11-14")
    out = plan_cards(trip)
    assert out["overload"] is None
    assert [pid for v in out["variants"] for d in v["itinerary"] for pid in
            (i.get("place_id") for i in d["items"] if i["kind"] == "visit")] == ["grill"]


def test_a_user_given_length_is_never_capped():
    from planning.places import build_places
    from plan_fixtures import CFG
    grill = rec("grill", *CENTRE, usable=("meal",), group="restaurant", visit=(210, 345, 480))
    grill["operation"]["visit_minutes"]["source"] = "user"
    (place,), _ = build_places(decision(["grill"]), {"grill": grill}, CFG)
    assert place.visit["typical"] == 345


def test_a_lunch_place_fits_before_the_confirmed_midday_rest():
    """R1/R2: the user's 12-14 rest is theirs; a lunch place eats down to an hour so it still takes the 11:00 lunch."""
    veg = rec("veg", *CENTRE, usable=("meal",), group="restaurant", visit=(45, 75, 120),
              hours={d: [["06:30", "17:30"]] for d in all_days()})
    rest = [{"day": None, "start": "12:00", "end": "14:00", "kind": "rest", "label": "nghỉ trưa", "where": "lodging"}]
    trip = framed_trip([veg], frame("2026-11-20", 4, busy=rest), days=4, start_date="2026-11-20")
    out = plan_cards(trip)
    assert out["overload"] is None, out["overload"] and out["overload"]["text"]
    visits = [(d["day"], i) for v in out["variants"] for d in v["itinerary"] for i in d["items"] if i["kind"] == "visit"]
    assert len(visits) == 1


def test_a_place_closed_all_trip_is_named_for_its_hours_not_for_missing_time():
    """N1/R1: "thiếu ~6 giờ" with 24 free hours was the wrong reason; a place that never opens says so."""
    late = rec("late", *CENTRE, usable=("meal",), group="restaurant", visit=(60, 90, 90),
               hours={d: [["23:00", "23:50"]] for d in all_days()})
    trip = framed_trip([late], frame("2026-11-14", 3), days=3, start_date="2026-11-14")
    ov = plan_cards(trip)["overload"]
    assert ov is not None and "giờ mở cửa" in ov["text"] and "thiếu" not in ov["text"]
    assert ov["leftover_reasons"] == [{"place_id": "late", "name": "late", "reason": "hours"}]


@pytest.mark.parametrize("signal", [None, "wish", "period", "frame_period", "other_place"])
def test_a_dawn_visit_and_recovery_rest_require_the_users_wish(signal):
    from planning.build import schedule_trip
    hill = rec("hill", *CENTRE, hours=None, features={"cloud_hunting": "present"})
    d = decision(["hill"], days=2, leave_at="21:00")
    if signal == "wish":
        d["trip_context"]["soft_weights"] = [{"feature": "cloud_hunting", "value": "present", "weight": 1}]
    elif signal in {"period", "other_place"}:
        d["trip_context"]["time_preferences"] = [{"period": "sunrise", "place_id": "hill" if signal == "period" else "other", "weight": 1}]
    elif signal == "frame_period":
        d["trip_context"]["context"]["frame"] = frame("2026-12-12", 2)
        d["trip_context"]["context"]["frame"]["periods"] = [{"period": "sunrise", "kinds": [], "weight": 1}]
    wants_dawn = signal not in {None, "other_place"}
    s = schedule_trip(prepared(d, [hill]))
    day = next(k for k, r in enumerate(s.results) if "hill" in r.order)
    visit = next(i for i in s.results[day].items if i.kind == "visit")
    assert (s.ctxs[day].day.start < 480) == wants_dawn
    assert (visit.start < 480) == wants_dawn
    assert any(b[3] == "Nghỉ trưa bù dậy sớm" for b in s.ctxs[day].day.busy) == wants_dawn


@pytest.mark.parametrize("pace,limit", [("slow", 3), ("normal", 4), ("packed", 6)])
def test_user_pace_spreads_nearby_stops_before_exceeding_the_daily_count(pace, limit):
    from planning.layout import assign
    recs = [rec(f"p{i}", CENTRE[0] + i * .0001, CENTRE[1], visit=(20, 30, 40)) for i in range(limit + 2)]
    recs[-1]["identity"].update(lat=CENTRE[0] - .08, area="far")
    d = decision([r["id"] for r in recs], days=2, pace=pace, leave_at="21:00",
                 base={"text": "home", "lat": CENTRE[0], "lng": CENTRE[1]})
    d["trip_context"]["sources"] = {"pace": "user"}
    trip = prepared(d, recs)
    days, left = assign(trip, trip.ctxs, list(trip.by_place))
    assert not left
    assert max(map(len, days)) <= limit, days
    from planning.build import schedule_trip
    schedule = schedule_trip(trip)
    assert not schedule.leftover
    assert max(len(r.order) for r in schedule.results) <= limit


def test_pace_count_does_not_drop_places_when_only_one_day_can_host_them():
    from planning.layout import assign
    recs = [rec(f"p{i}", CENTRE[0] + i * .0001, CENTRE[1], visit=(20, 30, 40)) for i in range(5)]
    for r in recs:
        r["operation"]["hours"]["value"]["sun"] = []
    d = decision([r["id"] for r in recs], days=2, leave_at="21:00")
    d["trip_context"]["sources"] = {"pace": "user"}
    trip = prepared(d, recs)
    days, left = assign(trip, trip.ctxs, list(trip.by_place))
    assert not left and len(days[0]) == 5 and days[1] == []


def test_planning_preserves_the_eight_oclock_compiled_start():
    from planning.build import schedule_trip
    place = rec("park", *CENTRE)
    fr = frame("2026-11-14", 2)
    fr["days"][0]["start"] = "08:00"
    trip = framed_trip([place], fr, days=2, start_date="2026-11-14")
    assert trip.days[0].start == 480
    assert schedule_trip(trip).ctxs[0].day.start == 480
