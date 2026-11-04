"""Unknown safety evidence stays visible, ordered after proven fits, and warns on selection."""

from plan_fixtures import CENTRE, CFG, decision, prepared, spot
from planning import build_plan
from planning.build import schedule_trip
from planning.lodging import candidates
from planning.recommendations import recommend
from planning.session import Store
from test_planning_ghosts import engine_for, placed
from test_planning_lodging_rank import stay, places, trip
from planning.engine import NotConfirmable
import pytest

HARD = {"feature": "steep_or_stairs", "op": "ne", "value": "present", "unknown_policy": "exclude"}


def setup_safety():
    records = [spot("chosen", CENTRE, 0, name="Quán đã chọn"),
               spot("unknown", CENTRE, 1, group="cafe", name="Quán chưa rõ"),
               spot("flat", CENTRE, 2, group="cafe", features={"steep_or_stairs": "absent"}),
               spot("stairs", CENTRE, 3, group="cafe", features={"steep_or_stairs": "present"})]
    d = decision(["chosen"], days=1, hard=[HARD],
                 base={"text": "home", "lat": CENTRE[0], "lng": CENTRE[1]})
    d["trip_context"]["context"]["frame"] = {
        "days": [{"date": "2026-12-12", "start": "08:00", "end": "21:00", "busy": []}]}
    return records, d


def assert_warning(warnings, pid, name):
    found = [w for w in warnings if w.get("code") == "safety_unknown" and w.get("place_id") == pid]
    assert len(found) == 1
    assert found[0]["status"] == "unknown"
    assert name in found[0]["text"]
    assert "Chưa rõ có dốc, nhiều bậc" in found[0]["text"]


def test_selected_unknown_warns_in_view_confirm_and_build_without_blocking():
    records, d = setup_safety()
    # A legacy silence artifact must produce the same warning as missing evidence.
    records[0]["effort"]["steep_or_stairs"] = {
        "value": "absent", "status": "VERIFIED", "reason": "silence", "distribution": {}, "n": 0}
    engine = engine_for(records, Store(None))
    engine.route_fn = lambda *args: None
    out = engine.create(d)
    assert "chosen" in placed(out["view"])
    assert not out["view"]["violations"]
    assert_warning(out["view"]["warnings"], "chosen", "Quán đã chọn")
    assert_warning(engine.confirm(out["id"])["warnings"], "chosen", "Quán đã chọn")
    from plan_fixtures import fake_matrix, fixed_sun, no_geocode
    built = build_plan(d, records, cfg=CFG, matrix_fn=fake_matrix, sun_fn=fixed_sun, geocode_fn=no_geocode)
    assert_warning(built["warnings"], "chosen", "Quán đã chọn")


def test_unknown_ghosts_rank_after_proven_fits_and_warn_when_added():
    records, d = setup_safety()
    engine = engine_for(records, Store(None))
    out = engine.create(d)
    options = [item for slot in out["view"]["ghosts"] for item in slot["items"]]
    assert options and options[0]["place_id"] == "flat"
    assert "stairs" not in {i["place_id"] for i in options}
    ghost = next(i for i in options if i["place_id"] == "unknown")
    assert ghost["unverified"] == ["steep_or_stairs"]
    added = engine.act(out["id"], {"type": "add_from_backup", "place": "unknown", "day": 0})["view"]
    assert "unknown" in placed(added)
    assert_warning(added["warnings"], "unknown", "Quán chưa rõ")
    dropped = engine.act(out["id"], {"type": "drop_place", "place": "unknown"})["view"]
    assert not any(w.get("code") == "safety_unknown" and w.get("place_id") == "unknown" for w in dropped["warnings"])


def test_recommendations_rank_proven_fits_first_and_warn_for_unknown():
    records, d = setup_safety()
    d["backup_pool"] = [{"id": i} for i in ("unknown", "flat", "stairs")]
    trip_data = prepared(d, records)
    sched = schedule_trip(trip_data)
    suggestions = recommend(sched.ctxs, sched.results, d, trip_data.by_id)
    groups = [s["alternatives"] for s in suggestions if s.get("alternatives")]
    assert groups
    for alternatives in groups:
        assert alternatives[0]["id"] == "flat"
        assert "stairs" not in {a["id"] for a in alternatives}
    unknown = next(a for alternatives in groups for a in alternatives if a["id"] == "unknown")
    assert_warning(unknown["warnings"], "unknown", "Quán chưa rõ")


def test_lodging_safety_unknown_is_flagged_after_pass_but_pet_unknown_still_excludes():
    records = [stay("stairs", 1, features={"steep_or_stairs": "present"}), stay("unknown", 0),
               stay("flat", 3, features={"steep_or_stairs": "absent"})]
    out = candidates(places(), trip(hard=[HARD]), CFG, records)
    assert [c["id"] for c in out] == ["flat", "unknown"]
    assert out[1]["unverified"] == ["steep_or_stairs"]
    assert not candidates(places(), trip(hard=[{"feature": "pets", "op": "ne", "value": "not_allowed"}]), CFG, records)


def test_proven_safety_failure_is_still_a_physical_violation_and_not_confirmable():
    records, d = setup_safety()
    records[0]["effort"] = records[3]["effort"]
    engine = engine_for(records, Store(None))
    out = engine.create(d)
    sched = schedule_trip(prepared(d, records))
    assert any(v.kind == "hard" and v.physical for v in sched.violations)
    with pytest.raises(NotConfirmable):
        engine.confirm(out["id"])
