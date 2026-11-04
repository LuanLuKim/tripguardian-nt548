"""Dated dietary requirements survive scheduling, suggestions, validation and restore. Only evidence that a meal stop
has no such dish blocks a plan; an unverified stop or a free meal on that date is shown and warned (owner 04/11)."""

from dataclasses import replace

import pytest

from plan_fixtures import CENTRE, CFG, decision, prepared, spot
from planning.backup import backups
from planning.build import schedule_trip
from planning.ghosts import fill, pool
from planning.layout import allowed as allowed_on_day
from planning.model import DayResult, Item
from planning.recommendations import recommend
from planning.session import Store
from planning.validate import validate
from planning import diet
from test_planning_ghosts import engine_for


def with_roads(cx, pid, start=720, end=780):
    """One visit with the road to it from the day's start and the road back to its end, as a real day has."""
    there = cx.travel.leg(cx.day.start_node, pid)[0]
    back = cx.travel.leg(pid, cx.day.end_node)[0]
    return result(Item("travel", start - there, start, from_id=cx.day.start_node, to_id=pid),
                  Item("visit", start, end, place_id=pid),
                  Item("travel", end, end + back, from_id=pid, to_id=cx.day.end_node))


def setup(subject="member", feature="vegetarian_options"):
    records = [spot("chosen", CENTRE, 0)]
    for pid, value in (("mixed", "yes"), ("meat", "no"), ("unknown", None)):
        records.append(spot(pid, CENTRE, 1, usable=("meal", "backup"), group="restaurant",
                            features={feature: value} if value else {}))
    d = decision(["chosen"], days=3, base={"text": "home", "lat": CENTRE[0], "lng": CENTRE[1]})
    d["trip_context"]["context"]["checkout_at"] = "21:00"
    d["trip_context"]["context"]["diet_days"] = [{
        "date": "2026-12-13", "scope": "eating", "feature": feature, "op": "eq", "value": "yes",
        "subject": subject, "member": "mẹ" if subject == "member" else None,
        "strength": "mandatory", "unknown_policy": "exclude", "evidence": [{"quote": "ngày 2 ăn chay"}]}]
    return d, records


def result(*items):
    return DayResult(tuple(items), tuple(i.place_id for i in items if i.kind == "visit"), (), 0, 0,
                     max((i.end for i in items), default=480))


@pytest.mark.parametrize("subject,who", [("member", "mẹ"), ("group", "cả nhóm")])
def test_free_meals_need_verified_diet_only_on_the_applicable_date(subject, who):
    d, records = setup(subject)
    trip = prepared(d, records)
    meals = result(Item("meal_free", 480, 525, name="breakfast"),
                   Item("meal_free", 720, 780, name="lunch"), Item("meal_free", 1080, 1140, name="dinner"))
    assert validate(trip.ctxs, [meals] * 3, [], set(), None, None) == []
    open_ = diet.warnings(trip.ctxs, [meals] * 3)
    assert len(open_) == 3 and {w["code"] for w in open_} == {"diet_meal_open"}
    assert {w["day"] for w in open_} == {1}
    assert all("2026-12-13" in w["text"] and who in w["text"] and "xác minh" in w["text"] for w in open_)
    assert trip.decision["trip_context"]["hard_filters"] == []


@pytest.mark.parametrize("pid,status,expected", [("mixed", "VERIFIED", "pass"), ("meat", "VERIFIED", "block"),
    ("unknown", "VERIFIED", "warn"), ("mixed", "UNCERTAIN", "warn"), ("mixed", "OUTDATED", "warn")])
@pytest.mark.parametrize("feature", ["vegetarian_options", "vegan_options"])
def test_member_requires_verified_options_not_a_wholly_vegetarian_venue(pid, status, expected, feature):
    d, records = setup(feature=feature)
    d["confirmed"] = [{"id": pid, "role": "selected", "relaxed": [feature]}]
    if pid == "mixed":
        records[1]["service"][feature]["status"] = status
    trip = prepared(d, records)
    meal = with_roads(trip.ctxs[0], pid)
    assert not validate([replace(trip.ctxs[0], require_meals=False)], [meal], [], set(), None, None)
    assert not validate([replace(trip.ctxs[2], require_meals=False)], [with_roads(trip.ctxs[2], pid)], [], set(), None, None)
    day = replace(trip.ctxs[1], require_meals=False)
    violations = validate([day], [with_roads(trip.ctxs[1], pid)], [], set(), None, None)
    unknown = [w for w in diet.warnings([day], [with_roads(trip.ctxs[1], pid)]) if w["code"] == "diet_unknown"]
    assert bool(violations) is (expected == "block")
    assert bool(unknown) is (expected == "warn")
    if expected == "block":
        assert "mẹ" in violations[0].detail and "2026-12-13" in violations[0].detail
    if expected == "warn":
        assert "mẹ" in unknown[0]["text"] and "2026-12-13" in unknown[0]["text"]


def test_missing_meals_on_a_diet_day_are_still_named_open():
    d, records = setup()
    trip = prepared(d, records)
    assert validate([trip.ctxs[1]], [result()], [], set(), None, None) == []
    open_ = diet.warnings([trip.ctxs[1]], [result()])
    assert len(open_) == 3
    assert all("mẹ" in w["text"] and "2026-12-13" in w["text"] for w in open_)


def test_day_validation_cache_changes_with_the_dated_diet():
    d, records = setup()
    d["confirmed"] = [{"id": "meat", "role": "selected"}]
    unrestricted = prepared({**d, "trip_context": {**d["trip_context"], "context": {
        **d["trip_context"]["context"], "diet_days": []}}}, records)
    restricted = prepared(d, records)
    meal = with_roads(restricted.ctxs[1], "meat")
    cache = {}
    assert not validate([replace(unrestricted.ctxs[1], require_meals=False)], [meal], [], set(), None, None, day_cache=cache)
    assert validate([replace(restricted.ctxs[1], require_meals=False)], [meal], [], set(), None, None, day_cache=cache)
    assert len(cache) == 2


def test_ghosts_filter_each_meal_on_the_diet_date_without_filtering_other_days():
    d, records = setup()
    trip = prepared(d, records)
    places = pool(records, d, CFG)
    meals = result(Item("meal_free", 720, 780, name="lunch"))
    ghosts = fill(trip.ctxs, [meals] * 3, places, {"chosen"}, set(), [], trip.points)
    assert [{p["place_id"] for p in g["items"]} for g in ghosts] == [
        {"mixed", "meat", "unknown"}, {"mixed"}, {"mixed", "meat", "unknown"}]
    empty = fill([trip.ctxs[1]], [meals], [p for p in places if p.id != "mixed"], set(), set(), [], trip.points)
    assert empty[0]["items"] == []
    assert [w["meal"] for w in diet.warnings([trip.ctxs[1]], [meals]) if w["code"] == "diet_meal_open"] == [
        "breakfast", "lunch", "dinner"]


def test_day_allocation_does_not_choose_an_unverified_meal_for_the_diet_date():
    d, records = setup()
    d["confirmed"] = [{"id": pid, "role": "selected"} for pid in ("mixed", "unknown", "meat")]
    trip = prepared(d, records)
    may = allowed_on_day(trip, trip.ctxs)
    assert [may(k, "unknown") for k in range(3)] == [True, False, True]
    assert [may(k, "mixed") for k in range(3)] == [True, True, True]
    sched = schedule_trip(trip)
    assert not ({"unknown", "meat"} & set(sched.results[1].order))
    assert {pid for r in sched.results for pid in r.order} == {"mixed", "unknown", "meat"}


def test_selected_noncompliant_meal_stays_in_the_plan_when_no_other_day_can_take_it():
    d, records = setup()
    d["trip_context"]["context"].update(days=1, start_date="2026-12-13")
    d["confirmed"] = [{"id": "meat", "role": "selected"}]
    trip = prepared(d, records)
    scheduled = schedule_trip(trip)
    assert scheduled.results[0].order == ("meat",)
    assert any(v.place_id == "meat" and "mẹ" in v.detail for v in scheduled.violations)


def test_recommendations_offer_only_verified_options_on_the_diet_date():
    d, records = setup()
    d["backup_pool"] = [{"id": pid} for pid in ("mixed", "meat", "unknown")]
    trip = prepared(d, records)
    suggestions = []
    for cx in trip.ctxs:
        # A lunch-only frame isolates the candidate from other, still-unfilled meals.
        cfg = replace(cx.cfg, time_suitability={**cx.cfg.time_suitability, "recommendations_per_gap": 3})
        lunch = replace(cx, day=replace(cx.day, start=690, end=870), cfg=cfg)
        suggestions.append({a["id"] for gap in recommend([lunch], [result()], d, trip.by_id)
                            for a in gap["alternatives"]})
    assert suggestions == [{"mixed", "meat", "unknown"}, {"mixed"}, {"mixed", "meat", "unknown"}]


def test_meal_backups_also_require_verified_options_only_on_the_diet_date():
    d, records = setup()
    d["confirmed"] = [{"id": "mixed", "role": "selected"}]
    d["backup_pool"] = [{"id": pid, "for": "mixed"} for pid in ("meat", "unknown")]
    records[1]["operation"]["hours"]["status"] = "UNCERTAIN"
    trip = prepared(d, records)
    meal = result(Item("visit", 720, 780, place_id="mixed"))
    alternatives = []
    for cx in trip.ctxs:
        alternatives.append({a["id"] for item in backups([cx], [meal], d, trip.by_id)["places"]
                             for a in item["alternatives"]})
    assert alternatives == [{"meat", "unknown"}, set(), {"meat", "unknown"}]


def test_restore_keeps_invalid_selected_meal_and_its_dated_violation(tmp_path):
    d, records = setup()
    d["confirmed"].append({"id": "mixed", "role": "selected"})
    d["backup_pool"] = [{"id": "meat"}]
    d["trip_context"]["context"]["frame"] = {"days": [
        {"date": date, "start": "11:30", "end": "14:30", "busy": []}
        for date in ("2026-12-12", "2026-12-13", "2026-12-14")]}
    records[1]["operation"]["hours"]["value"] = {"sat": [], "sun": [["11:30", "14:30"]], "mon": []}
    engine = engine_for(records, Store(tmp_path))
    created = engine.create(d)
    engine.act(created["id"], {"type": "pick_variant", "id": engine.variants(created["id"])[0]["id"]})
    selected = engine.act(created["id"], {"type": "add_from_backup", "place": "meat", "day": 1})
    view = selected["view"]
    assert any(i.get("place_id") == "meat" for i in view["itinerary"][1]["items"])
    violations = [v for v in view["violations"] if v.get("place_id") == "meat"]
    assert violations and all("mẹ" in v["detail"] and "2026-12-13" in v["detail"] for v in violations)
    restored = engine_for(records, Store(tmp_path)).load(created["id"])["view"]
    assert restored["violations"] == view["violations"]
    assert {i.get("place_id") for day in restored["itinerary"] for i in day["items"] if i["kind"] == "visit"} == {
        "chosen", "mixed", "meat"}
