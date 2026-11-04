"""Production regressions for contextual suggestions, lodging warnings and travel provenance."""

from copy import deepcopy

from plan_fixtures import CENTRE, CFG, decision, spot, prepared
from planning.build import schedule_trip
from planning.recommendations import recommend
from planning.ghosts import fill
from planning.model import DayResult, Item
from test_planning_ghosts import engine_for, placed
from planning.ghosts import pool
from planning.session import Store
from requirements import hard_result


def family_trip():
    records = [spot("chosen", CENTRE, 0),
               spot("bar", CENTRE, 1, group="bar", name="Drunkmate Cocktail Bar"),
               spot("cafe", CENTRE, 2, group="cafe"),
               spot("stairs", CENTRE, 3, group="cafe", features={"steep_or_stairs": "present"})]
    d = decision(["chosen"], days=1, base={"text": "home", "lat": CENTRE[0], "lng": CENTRE[1]})
    d["trip_context"]["context"]["companions"] = ["kids", "parents"]
    d["trip_context"]["context"]["frame"] = {"days": [{"date": "2026-12-12", "start": "08:00", "end": "21:00", "busy": []}]}
    return records, d


def test_family_suggestions_do_not_volunteer_nightlife_but_keep_manual_choices():
    records, d = family_trip()
    d["backup_pool"] = [{"id": "bar"}, {"id": "cafe"}]
    trip = prepared(d, records)
    sched = schedule_trip(trip)
    solo = deepcopy(d)
    solo["trip_context"]["context"]["companions"] = []
    baseline = recommend(sched.ctxs, sched.results, solo, trip.by_id)
    assert "bar" in {a["id"] for gap in baseline for a in gap["alternatives"]}
    suggestions = recommend(sched.ctxs, sched.results, d, trip.by_id)
    assert "bar" not in {a["id"] for gap in suggestions for a in gap["alternatives"]}
    assert "bar" not in {p.id for p in pool(records, d, CFG)}
    manual = deepcopy(d)
    manual["confirmed"].append({"id": "bar", "role": "selected"})
    assert "bar" in placed(engine_for(records, Store(None)).create(manual)["view"])


def test_contextual_fit_ranks_family_friendly_places_before_closer_bad_fit():
    records, d = family_trip()
    records[1]["identity"]["category_group"] = "cafe"
    records[1]["details"] = {"fit": {"parents": {"value": "bad", "status": "VERIFIED", "reasons": ["stairs"]}}}
    trip = prepared(d, records)
    result = DayResult((Item("free", 900, 1020),), (), (), 0, 0, 1020)
    slots = fill(trip.ctxs, [result], pool(records, d, CFG), {"chosen"}, set(), [], trip.points)
    assert slots[0]["items"][0]["place_id"] == "cafe"


def test_unknown_safety_fillers_remain_unknown_and_proven_failures_are_excluded():
    records, d = family_trip()
    d["trip_context"]["hard_filters"] = [{"feature": "steep_or_stairs", "op": "eq", "value": "absent",
                                               "unknown_policy": "flag"}]
    candidates = pool(records, d, CFG)
    assert {p.id for p in candidates} == {"cafe"}
    assert candidates.unverified == {"cafe": ["steep_or_stairs"]}
    requirement = d["trip_context"]["hard_filters"][0]
    assert hard_result(records[2], requirement)[0] == "unknown"
    assert hard_result(records[3], requirement)[0] == "fail"


def test_hidden_handoff_ids_are_not_suggested_and_do_not_remove_selected_places():
    records, d = family_trip()
    d["hidden_ids"] = ["cafe", "chosen"]
    assert "cafe" not in {p.id for p in pool(records, d, CFG)}
    view = engine_for(records, Store(None)).create(d)["view"]
    assert "chosen" in placed(view)
    assert "cafe" not in {p["place_id"] for slot in view["ghosts"] for p in slot["items"]}


def test_companions_without_a_suitability_feature_keep_unknown_fit_neutral():
    records, d = family_trip()
    d["trip_context"]["context"]["companions"] = ["friends", "solo"]
    assert {p.id for p in pool(records, d, CFG)} == {"bar", "cafe", "stairs"}


def test_recommendations_do_not_leak_hidden_backup_ids():
    records, d = family_trip()
    d["trip_context"]["context"]["companions"] = []
    d["backup_pool"] = [{"id": "bar"}]
    trip = prepared(d, records)
    sched = schedule_trip(trip)
    baseline = recommend(sched.ctxs, sched.results, d, trip.by_id)
    assert "bar" in {a["id"] for gap in baseline for a in gap["alternatives"]}
    d["hidden_ids"] = ["bar"]
    assert not any(gap["alternatives"] for gap in recommend(sched.ctxs, sched.results, d, trip.by_id))


def test_recommendations_keep_unknown_safety_fit_but_exclude_proven_bad_fit():
    records, d = family_trip()
    d["trip_context"]["context"]["companions"] = []
    d["backup_pool"] = [{"id": "bar"}]
    trip = prepared(d, records)
    sched = schedule_trip(trip)
    d["trip_context"]["hard_filters"] = [{"feature": "fit.wheelchair", "op": "eq", "value": "good",
                                               "unknown_policy": "flag"}]
    suggestions = recommend(sched.ctxs, sched.results, d, trip.by_id)
    assert {a["id"] for gap in suggestions for a in gap["alternatives"]} == {"bar"}
    requirement = d["trip_context"]["hard_filters"][0]
    assert hard_result(records[1], requirement)[0] == "unknown"
    records[1]["details"] = {"fit": {"wheelchair": {"value": "bad", "status": "VERIFIED",
                                                       "distribution": {"bad": 1}, "n": 1, "evidence": ["review"]}}}
    trip = prepared(d, records)
    assert hard_result(records[1], requirement)[0] == "fail"
    assert not any(gap["alternatives"] for gap in recommend(sched.ctxs, sched.results, d, trip.by_id))


def test_selecting_lodging_clears_unknown_base_warning_through_replay(tmp_path):
    records = [spot("chosen", CENTRE, 0)]
    d = decision(["chosen"], days=1)
    engine = engine_for(records, Store(tmp_path))
    result = engine.create(d)
    assert "base_unknown" in {w["code"] for w in result["view"]["warnings"]}
    act = {"type": "set_lodging", "lat": CENTRE[0], "lng": CENTRE[1], "text": "DaLat Peach Valley"}
    selected = engine.act(result["id"], act)["view"]
    assert "base_unknown" not in {w["code"] for w in selected["warnings"]}
    home = selected["state"]["lodging_point"]["id"]
    assert any(i.get("from") == home for day in selected["itinerary"] for i in day["items"])
    replay = engine_for(records, Store(tmp_path)).load(result["id"])
    assert "base_unknown" not in {w["code"] for w in replay["view"]["warnings"]}
    engine.route_fn = lambda *args: None
    confirmed = engine.confirm(result["id"])
    assert "base_unknown" not in {w["code"] for w in confirmed["warnings"]}
    undone = engine.act(result["id"], {"type": "undo"})["view"]
    assert "base_unknown" in {w["code"] for w in undone["warnings"]}
