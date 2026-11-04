"""Meal-role and fixed-rest regressions from the prod E2E review."""

from dataclasses import replace

import pytest

from plan_fixtures import CENTRE, CFG, FakeLive, day_ctx, decision, fake_matrix, no_geocode, rec
from planning.build import itinerary
from planning.schedule import simulate


def test_breakfast_dish_is_not_reassigned_to_lunch():
    breakfast = rec("breakfast", *CENTRE, name="Bánh Căn Cô Chín", usable=("meal",), group="restaurant")
    cx = day_ctx([breakfast], start=810)
    result = simulate(["breakfast"], cx)
    assert any(v.kind == "meal_window" for v in result.violations)


def test_validator_rejects_a_breakfast_visit_forged_into_lunch():
    from planning.model import DayResult, Item
    from planning.validate import validate

    breakfast = rec("breakfast", *CENTRE, name="Bánh Căn", usable=("meal",), group="restaurant")
    cx = day_ctx([breakfast])
    result = DayResult((Item("visit", 810, 870, place_id="breakfast"),), ("breakfast",), (), 0, 0, 870)
    violations = validate([cx], [result], [], set(), None, None)
    assert any(v.kind == "meal_window" for v in violations)


def test_breakfast_suggestion_is_not_offered_for_lunch():
    from planning.ghosts import fill
    from planning.model import DayResult, Item

    breakfast = rec("breakfast", *CENTRE, name="Bánh Căn", usable=("meal",), group="restaurant")
    cx = day_ctx([breakfast], start_node="breakfast")
    result = DayResult((Item("meal_free", 660, 750, name="lunch"),), (), (), 0, 0, 750)
    slots = fill([cx], [result], list(cx.places.values()), set(), set(), [], {})
    assert slots[0]["items"] == []


def test_local_breakfast_moves_to_next_morning_when_arrival_is_late():
    from plan_fixtures import prepared
    from planning.build import schedule_trip
    from realistic_cases import frame

    breakfast = rec("breakfast", *CENTRE, name="Bánh Căn Cô Chín", usable=("meal",), group="restaurant")
    d = decision(["breakfast"], days=2, start_date="2026-11-11")
    fr = frame("2026-11-11", 2)
    fr["days"][0]["start"] = "09:15"
    d["trip_context"]["context"]["frame"] = fr
    schedule = schedule_trip(prepared(d, [breakfast]))
    visits = [(day, i.start) for day, result in enumerate(schedule.results) for i in result.items if i.kind == "visit"]
    assert visits == [(1, 480)]
    assert not schedule.leftover


def test_selected_local_breakfast_takes_the_morning_slot():
    breakfast = rec("breakfast", *CENTRE, name="Bánh Căn Cô Chín", usable=("meal",), group="restaurant")
    cx = day_ctx([breakfast])
    result = simulate(["breakfast"], cx)
    visit = next(i for i in result.items if i.kind == "visit")
    assert 390 <= visit.start <= 540
    assert not any(i.kind == "meal_free" and i.name == "breakfast" for i in result.items)


@pytest.mark.parametrize("hours,status", [(None, "VERIFIED"), ("open", "UNCERTAIN"), ("open", "OUTDATED")])
def test_unconfirmed_hours_are_noted_on_the_stop(hours, status):
    place = rec("place", *CENTRE, hours=hours, status=status)
    cx = day_ctx([place])
    result = simulate(["place"], cx)
    stop = next(i for i in itinerary([cx.day], [result])[0]["items"] if i["kind"] == "visit")
    assert "Chưa rõ giờ mở" in (stop.get("note") or "")


def test_afternoon_snack_keeps_its_time_when_free_meals_are_reserved():
    snack = rec("snack", *CENTRE, name="Kem bơ", usable=("meal",), group="restaurant")
    cx = replace(day_ctx([snack]), require_meals=True, compact_estimates=True)
    result = simulate(["snack"], cx)
    visit = next(i for i in result.items if i.kind == "visit")
    assert 14 * 60 <= visit.start < 18 * 60
    assert not result.violations
    assert not any(n.startswith("meal_missed") for n in result.notes)


def test_compact_replay_preserves_feasible_afternoon_snack_preferences():
    snacks = [rec(f"snack{i}", *CENTRE, group="cafe", usable=("meal", "experience"), visit=(60, 100, 120))
              for i in range(2)]
    sight = rec("sight", *CENTRE, visit=(60, 60, 60))
    cx = replace(day_ctx([*snacks, sight], minutes=45), compact_estimates=True, require_meals=True)
    result = simulate(["snack0", "snack1", "sight"], cx)
    assert not result.violations
    assert not any(n.startswith("meal_missed") for n in result.notes)
    snack_visits = [i for i in result.items if i.place_id in {"snack0", "snack1"} and i.kind == "visit"]
    assert len(snack_visits) == 2
    assert all(870 <= i.start < 1050 for i in snack_visits)


@pytest.mark.parametrize("home", [None, "home"])
@pytest.mark.parametrize("usable", [("meal",), ("meal", "experience"), ("experience",)])
def test_evening_preference_never_consumes_the_confirmed_midday_rest(home, usable):
    dinner = rec("dinner", *CENTRE, usable=usable, group="restaurant")
    cx = day_ctx([dinner], start_node=home, end_node=home, extra_nodes=("home",) if home else ())
    cx = replace(cx, day=replace(cx.day, busy=((720, 840, "rest", "Nghỉ trưa", "lodging"),)),
                 home=home, compact_estimates=True, require_meals=True,
                 time_preferences=({"place_id": "dinner", "period": "evening", "weight": 1},))
    result = simulate(["dinner"], cx)
    assert [(i.start, i.end) for i in result.items if i.kind == "busy"] == [(720, 840)]
    assert all(i.end <= 720 or i.start >= 840 for i in result.items if i.kind in {"visit", "meal_free", "travel"})
    assert not result.violations


def test_confirmed_rest_survives_add_undo_redo_and_restore():
    from planning.engine import Engine
    from planning.session import Store
    from realistic_cases import frame

    park = rec("park", *CENTRE)
    dinner = rec("dinner", *CENTRE, usable=("meal",), group="restaurant")
    d = decision(["park"], days=1, start_date="2026-11-22")
    d["backup_pool"] = [{"id": "dinner"}]
    d["trip_context"]["context"]["frame"] = frame("2026-11-22", 1, busy=[
        {"day": None, "start": "12:00", "end": "14:00", "kind": "rest", "label": "Nghỉ trưa", "where": "lodging"}])
    d["trip_context"]["time_preferences"] = [{"place_id": "dinner", "period": "evening", "weight": 1}]

    def engine():
        return Engine([park, dinner], cfg=CFG, live_cfg=FakeLive(), store=Store(None),
                      geocode_fn=no_geocode, matrix_fn=fake_matrix, sun_fn=lambda *a: (360, 1050), background=False)

    e = engine()
    created = e.create(d, None)
    sid = created["id"]
    picked = e.act(sid, {"type": "pick_variant", "id": created["view"]["variants"][0]["id"]})["view"]
    added = e.act(sid, {"type": "add_from_backup", "place": "dinner", "day": 0})["view"]
    undone = e.act(sid, {"type": "undo"})["view"]
    redone = e.act(sid, {"type": "redo"})["view"]
    restored = engine()
    restored.store.restore(e.store.get(sid))
    reopened = restored.load(sid)["view"]
    for view in (picked, added, undone, redone, reopened):
        items = view["itinerary"][0]["items"]
        assert [(i["start"], i["end"]) for i in items if i["kind"] == "busy"] == [("12:00", "14:00")]
        assert all(i["end"] <= "12:00" or i["start"] >= "14:00" for i in items
                   if i["kind"] in {"visit", "meal_free", "travel"})
