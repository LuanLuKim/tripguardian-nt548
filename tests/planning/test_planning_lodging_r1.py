"""Lodging applicability and explicit choices in the production mobility case."""

import pytest

from corpus import load_ontology
from requirements import allowed, applicable, hard_result
from plan_fixtures import CFG, CENTRE, decision, rec, stay
from planning.lodging import anywhere
from test_planning_r12 import engine

YORI = "0x31711306e76823df:0x5a4fd92d57d365cd"
HARD = [{"feature": fid, "op": "ne", "value": "present", "unknown_policy": "exclude"}
        for fid in ("long_walk", "steep_or_stairs")]


def test_every_feature_outside_stay_ontology_is_not_applicable_to_accommodation():
    ont = load_ontology()
    record = stay(YORI, *CENTRE)
    for fid, definition in ont.features.items():
        if fid in ont.stay or any(item.startswith(fid + "=") for item in ont.stay):
            continue
        requirement = {"feature": fid, "value": next(iter(definition.values)), "op": "ne", "unknown_policy": "exclude"}
        assert not applicable(record, requirement, activity="accommodation"), fid
        assert hard_result(record, requirement, activity="accommodation") == ("not_applicable", None), fid
        assert allowed(record, requirement, activity="accommodation"), fid
    assert hard_result(record, HARD[1], activity="accommodation")[0] == "unknown"
    assert not allowed(record, HARD[1], activity="accommodation")
    visit = rec("visit", *CENTRE, features={"long_walk": "present"})
    assert not allowed(visit, HARD[0], activity="sightseeing")


def test_lodging_suggestions_flag_unknown_stairs_but_exclude_fail_and_ignore_non_stay_walk():
    records = [stay("safe", *CENTRE, features={"steep_or_stairs": "absent"}),
               stay("stairs", *CENTRE, features={"steep_or_stairs": "present"}), stay(YORI, *CENTRE)]
    candidates = anywhere(decision([], hard=HARD), CFG, records)
    assert [c["id"] for c in candidates] == ["safe", YORI]
    assert candidates[0]["unverified"] == []
    assert candidates[1]["unverified"] == ["steep_or_stairs"]


@pytest.mark.parametrize("stairs", [None, "present", "absent"])
@pytest.mark.parametrize("booked", [True, False])
def test_two_picks_and_explicit_yori_never_block_planning(booked, stairs):
    features = {"long_walk": "absent", "steep_or_stairs": "absent"}
    records = [rec("a", *CENTRE, features=features), rec("b", CENTRE[0] + .001, CENTRE[1], features=features),
               stay(YORI, *CENTRE, features={"steep_or_stairs": stairs} if stairs else {})]
    d = decision(["a", "b"], days=2, hard=HARD)
    own = {"kind": "corpus", "place_id": YORI, "text": "Yori House", "lat": CENTRE[0], "lng": CENTRE[1]}
    if booked:
        d["trip_context"]["context"].update(lodging_booked="yes", lodging=own)
    else:
        d["lodging"] = {**own, "id": YORI}
    e = engine(records)
    created = e.create(d)
    assert created["view"]["itinerary"]
    out = e.confirm(created["id"])
    assert out["itinerary"]
    warnings = [w for w in created["view"]["warnings"] if w.get("code") == "lodging_requirement"]
    if stairs == "absent":
        assert not warnings
    else:
        expected = "Chưa rõ có bậc thang" if stairs is None else "Có bậc thang theo đánh giá"
        assert any(expected in w["text"] for w in warnings)
        assert all(w.get("feature") != "long_walk" for w in warnings)
        assert any(expected in w["text"] for w in out["warnings"] if w.get("code") == "lodging_requirement")


def test_no_current_lodging_does_not_emit_requirement_warnings():
    from planning.lodging import warnings
    assert warnings(decision([], hard=HARD), {}, {"place_id": None}) == []
    assert warnings(decision([], hard=HARD), {}, {}) == []
