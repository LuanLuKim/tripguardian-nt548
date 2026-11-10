"""Planning reads Trip's gate and day frame (git 7c4da01:docs/plans/2026-10-15-trip-understanding-architecture.md
A1, A5; test Q14 and hand-off H1)."""

import pytest
from plan_fixtures import CFG, LODGING, FakeLive, fake_matrix, no_geocode, sample_trip

from planning import TripIncomplete
from planning.engine import Engine
from planning.frame import trip_days
from planning.session import Store
from planning.settings import to_min


def engine(recs):
    return Engine(recs + LODGING, cfg=CFG, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode,
                  matrix_fn=fake_matrix, sun_fn=lambda *a: (6 * 60, 17 * 60 + 30))


@pytest.mark.parametrize("readiness, missing", [
    ({"missing": ["trip", "care"], "readback_ok": True}, ["trip", "care"]),
    ({"missing": ["care"], "readback_ok": False}, ["care"]),
])
def test_q14_planning_refuses_a_trip_that_is_not_ready(readiness, missing):
    d, recs = sample_trip()
    d["trip_context"]["readiness"] = readiness
    with pytest.raises(TripIncomplete) as err:
        engine(recs).create(d)
    assert err.value.missing == missing


@pytest.mark.parametrize("legacy_missing", [[], ["companions", "mobility", "pace", "budget", "lodging", "readback"]])
def test_q14_a_ready_trip_is_planned_without_readback(legacy_missing):
    d, recs = sample_trip()
    d["trip_context"]["readiness"] = {"missing": legacy_missing, "readback_ok": False}
    assert engine(recs).create(d)["id"]


def test_dates_and_care_produce_a_schedule_with_all_optional_inputs_unknown():
    from trip import TripState, compile_search_input
    from datetime import date

    def said(value):
        return {"value": value, "source": "user", "status": "confirmed", "evidence": [{"turn": 1, "quote": "q"}]}

    state = TripState.model_validate({"start_date": said(date(2026, 12, 12)), "days": said(2),
                                      "care": said("none")})
    search = compile_search_input(state)
    assert search.readiness.missing == () and search.readiness.readback_ok is False
    assert all(not getattr(state, key).known for key in ("companions", "people", "mobility", "pace", "budget_vnd", "lodging"))
    d, recs = sample_trip()
    d["trip_context"] = search.model_dump(mode="json")
    e = engine(recs)
    e.background = False
    created = e.create(d)
    view = created["view"]
    assert len(view["itinerary"]) == 2
    assert any(day["items"] for day in view["itinerary"])
    assert e.store.get(created["id"]).decision["trip_context"] == d["trip_context"]


FRAME = {"days": [
    {"date": "2026-12-12", "start": "10:45", "end": "21:00", "busy": [], "intensity": "normal"},
    {"date": "2026-12-13", "start": "05:00", "end": "19:30",
     "busy": [{"start": "12:00", "end": "14:00", "kinds": ["rest"], "labels": ["nghỉ trưa"], "where": "lodging"}],
     "intensity": "normal"},
    {"date": "2026-12-14", "start": "08:00", "end": "14:45", "busy": [], "intensity": "normal"}]}


def test_h1_planning_days_are_the_frame_trip_compiled_not_its_own_defaults():
    d, _ = sample_trip()
    ctx = {**d["trip_context"]["context"], "days": 3, "start_date": "2026-12-12", "frame": FRAME,
           "checkin_at": "14:00", "checkout_at": "12:00"}  # the old fields disagree on purpose: the frame wins
    days = trip_days(ctx, CFG, "home")
    assert [(x.start, x.end) for x in days] == [(to_min(a["start"]), to_min(a["end"])) for a in FRAME["days"]]


def test_r4_a_rest_day_in_the_frame_has_no_window_to_fill():
    d, _ = sample_trip()
    frame = {"days": [dict(FRAME["days"][0]), dict(FRAME["days"][1], intensity="free"), dict(FRAME["days"][2])]}
    ctx = {**d["trip_context"]["context"], "days": 3, "start_date": "2026-12-12", "frame": frame}
    day = trip_days(ctx, CFG, "home")[1]
    assert day.end - day.start == 0
