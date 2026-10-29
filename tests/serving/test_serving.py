import json
from datetime import date

from corpus.serving import areas, build, check, mmr, near_duplicate_groups, run

BUILT = date(2026, 10, 2)


def sig(top, dist=None, n=3, status="signal", servable=True, needs_review=False, fresh=10, rate=0.1, authority=None):
    return {"n": n, "distribution": dist or {top: n}, "top_value": top, "status": status, "authority": authority,
            "by_context": {}, "mention_rate": rate, "needs_review": needs_review, "servable": servable,
            "quality": None, "observation_ids": [f"x:{i}" for i in range(9)],
            "confidence": {"independent_sources": n, "agreement": 1.0, "freshness_days": fresh, "source_types": ["provider"]}}


def intel(fid="F", features=None, closure=None, category="Quán cà phê", group="cafe", lat=11.94, lng=108.44,
          usable=("experience", "meal", "backup"), coverage=None):
    return {"place_fid": fid, "place_name": fid, "as_of": "2026-09-30", "voices": 30,
            "identity": {"category": category, "lat": lat, "lng": lng, "address": "Đà Lạt"},
            "features": features or {}, "coverage": coverage or {"experience": "PARTIAL"},
            "operation": {"closure": closure, "hours": {"mon": [["07:00", "22:00"]]}, "price_range": None,
                          "crowd_by_time": None},
            "estimates": {"category_group": group, "usable_as_default": list(usable), "effort_hint": "unknown",
                          "visit_minutes": {"short": 45, "typical": 75, "long": 150, "source": "category_default", "n": 0},
                          "entry_fee": None}}


def test_statuses_never_serve_needs_review_or_disabled_and_unmeasured_is_uncertain():
    rec = build(intel(features={"scenic_view": sig("present"), "kids": sig("suitable", needs_review=True),
                                "noise": sig("quiet", status="disabled", servable=False),
                                "crowd": sig("high", servable=False), "parking": sig("easy", fresh=900)}), BUILT)
    assert rec["experience"]["scenic_view"]["status"] == "VERIFIED"
    assert "kids" not in rec["suitability"] and "noise" not in rec["environment"]
    assert (rec["environment"]["crowd"]["status"], rec["environment"]["crowd"]["reason"]) == ("UNCERTAIN", "unmeasured_precision")
    assert rec["environment"]["parking"]["status"] == "OUTDATED"
    assert rec["operation"]["visit_minutes"]["kind"] == "estimate" and rec["status"] == "VERIFIED"
    assert build(intel(closure="permanent"), BUILT)["status"] == "DISABLED"


def test_phone_and_website_served_in_identity_and_absent_is_none():
    src = intel()
    src["identity"] = {**src["identity"], "phone": "0919419835", "website": "https://example.vn/"}
    ident = build(src, BUILT)["identity"]
    assert (ident["phone"], ident["website"]) == ("0919419835", "https://example.vn/")
    ident = build(intel(), BUILT)["identity"]
    assert ident["phone"] is None and ident["website"] is None


def test_up_to_price_from_old_observations_has_unknown_minimum():
    for old in ({"min_vnd": 1, "max_vnd": 100000}, {"min_vnd": None, "max_vnd": 100000, "up_to": True}):
        src = intel()
        src["operation"] = {**src["operation"], "price_range": {**old, "per": "person", "reports": 9}}
        v = build(src, BUILT)["operation"]["price_per_person"]["value"]
        assert v["min_vnd"] is None and v["max_vnd"] == 100000 and v["up_to"] is True
    src = intel()
    src["operation"] = {**src["operation"], "price_range": {"min_vnd": 100000, "max_vnd": 200000}}
    v = build(src, BUILT)["operation"]["price_per_person"]["value"]
    assert (v["min_vnd"], v["max_vnd"]) == (100000, 200000) and "up_to" not in v


def test_check_is_fail_closed():
    rec = build(intel(features={
        "steep_or_stairs": sig("absent"),
        "long_walk": sig("absent", dist={"absent": 3, "present": 1}),  # somebody said it: not safe
        "rough_road_access": sig("present"),
        "elderly": sig("suitable", servable=False)}), BUILT)
    assert check(rec, "steep_or_stairs", "present") == "pass"
    assert check(rec, "long_walk", "present") == "unknown"
    assert check(rec, "rough_road_access", "present") == "fail"
    assert check(rec, "elderly", "unsuitable") == "unknown"  # unmeasured value never passes a hard filter
    assert check(rec, "wheelchair", "unsuitable") == "unknown"  # no evidence is never safe


def test_experience_none_cannot_be_used_as_experience():
    rec = build(intel(coverage={"experience": "NONE"}), BUILT)
    assert rec["usable_as"] == ["meal", "backup"]


def _rec(fid, kinds, lat=11.94, lng=108.44, group="cafe"):
    return build(intel(fid, {k: sig("present") for k in kinds}, group=group, lat=lat, lng=lng), BUILT)


def test_near_duplicates_by_leader_not_chained_and_only_within_group():
    a = _rec("A", ["scenic_view", "photo_spot", "cozy_decor", "nature"])
    b = _rec("B", ["scenic_view", "photo_spot", "cozy_decor", "nature", "animals"])
    c = _rec("C", ["photo_spot", "cozy_decor", "nature", "animals", "live_music", "camping"])
    d = _rec("D", ["scenic_view", "photo_spot", "cozy_decor", "nature"], group="restaurant")
    # C leads (most features) but B shares only 4/7 with it; B leads A; D is a restaurant
    assert near_duplicate_groups([a, b, c, d]) == [["B", "A"]]


def test_mmr_prefers_a_different_place_over_a_near_duplicate():
    a = _rec("A", ["scenic_view", "photo_spot", "cozy_decor", "nature"])
    b = _rec("B", ["scenic_view", "photo_spot", "cozy_decor", "nature"])
    c = _rec("C", ["live_music", "laptop_friendly", "long_stay_chill"])
    assert mmr([a, b, c], {"A": 1.0, "B": 0.95, "C": 0.7}, 2) == ["A", "C"]


def test_areas_group_close_places():
    near = [_rec(f"N{i}", [], lat=11.94 + i * 0.001) for i in range(3)]
    far = _rec("F", [], lat=12.10)
    got = areas(near + [far])
    assert len({got[r["id"]] for r in near}) == 1 and got["F"] != got["N0"] and got["N0"] == "area-1"


def test_run_writes_served_records_only(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    d = tmp_path / "intel" / "places"
    d.mkdir(parents=True)
    (d / "A.json").write_text(json.dumps(intel("A")), encoding="utf-8")
    (d / "B.json").write_text(json.dumps(intel("B", closure="temporary")), encoding="utf-8")
    summary = run("dalat")
    assert summary["places"] == 1 and summary["disabled"] == {"closure_temporary": 1}
    doc = json.loads((tmp_path / "serving" / "places.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in doc["records"]] == ["A"] and doc["records"][0]["identity"]["area"] == "area-1"


def test_place_status_from_maps_closure_then_judge():
    from corpus.serving.record import place_status
    assert place_status("permanent", "open") == ("DISABLED", "closure_permanent")
    assert place_status(None, "closed") == ("DISABLED", "judge_closed")
    assert place_status(None, "changed") == ("DISABLED", "judge_changed")
    assert place_status(None, "unclear") == ("UNCERTAIN", "closure_reported")
    assert place_status(None, None) == ("VERIFIED", None)


def test_hours_that_disagree_are_uncertain_and_official_fee_is_a_fact():
    from datetime import date
    from corpus.serving.record import _hours
    op = {"hours": {"mon": [["08:00", "18:00"]]}, "hours_source": "official",
          "hours_conflict": {"mon": [["07:00", "17:00"]]}}
    h = _hours(op, date(2026, 10, 1), date(2026, 10, 5))
    assert h["status"] == "UNCERTAIN" and h["source"] == "official" and h["conflict"] == {"mon": [["07:00", "17:00"]]}
    assert _hours({**op, "hours_conflict": None}, date(2026, 10, 1), date(2026, 10, 5))["status"] == "VERIFIED"


def test_lodging_price_a_night_is_a_dated_reference():
    base = intel(category="Khách sạn", group="stay", usable=())
    night = {"vnd": 467000, "at": "2026-09-01T10:00:00+00:00"}
    rec = build({**base, "operation": {**base["operation"], "price_night": night}}, BUILT)
    assert rec["operation"]["price_per_night"] == {"value": 467000, "status": "VERIFIED", "as_of": "2026-09-01",
                                                   "source": "gmaps_list", "kind": "estimate"}
    assert build(base, BUILT)["operation"]["price_per_night"] is None


def test_mmr_matches_the_pairwise_definition():
    import random

    from corpus.serving.groups import config, mmr, signature, similarity
    from corpus.serving.record import SERVED  # noqa: F401
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[1] / "decision"))
    from gen import records

    recs = records(3, 60)
    rng = random.Random(1)
    scores = {r["id"]: round(rng.random(), 3) for r in recs}
    sigs = {r["id"]: signature(r) for r in recs}

    def reference(k, lam=config()["mmr_lambda"]):
        pool, picked = {r["id"]: r for r in recs}, []
        while pool and len(picked) < k:
            def gain(rid):
                sim = max((similarity(pool[rid], p, sigs) for p in picked), default=0.0)
                return lam * scores.get(rid, 0.0) - (1 - lam) * sim
            best = max(sorted(pool), key=gain)
            picked.append(pool.pop(best))
        return [p["id"] for p in picked]

    for k in (1, 5, 20, 100):
        assert mmr(recs, scores, k) == reference(k)


def test_a_lodging_far_from_the_city_centre_is_not_served():
    from corpus.serving.run import stay_outside
    cities = {"dalat": {"area": [11.78, 108.30, 12.12, 108.66], "stay_within": {"lat": 11.9404, "lng": 108.4583, "km": 12}}}

    def rec(group, lat, lng):
        return {"identity": {"category_group": group, "lat": lat, "lng": lng}}

    assert not stay_outside(rec("stay", 11.944, 108.44), cities)  # Phan Bội Châu
    assert stay_outside(rec("stay", 11.84, 108.38), cities)  # Nam Ban, ~14 km
    assert not stay_outside(rec("nature", 11.84, 108.38), cities)  # only lodging is cut
    assert not stay_outside(rec("stay", 10.77, 106.70), cities)  # outside every area: not this rule's


FEE_ESTIMATE = {"min_vnd": 60000, "typical_vnd": 100000, "max_vnd": 120000, "n": 3, "source": "reviews"}


def _free_entry(estimate):
    i = intel(features={"entry_fee": sig("free")})
    i["estimates"]["entry_fee"] = estimate
    return build(i, BUILT)


def test_free_entry_conflicting_with_fee_estimate_is_uncertain():
    rec = _free_entry(FEE_ESTIMATE)
    assert rec["service"]["entry_fee"]["status"] == "UNCERTAIN"
    assert rec["service"]["entry_fee"]["reason"] == "conflicts_entry_fee_estimate"
    assert rec["service"]["entry_fee"]["value"] == "free"  # the conflict is kept, not resolved
    assert rec["operation"]["entry_fee"]["typical_vnd"] == 100000
    assert rec["details"]["cost"] is None  # place_block got the changed feature: no invented 0 VND entry


def test_free_entry_without_fee_estimate_stays_verified():
    free = _free_entry(None)
    assert free["service"]["entry_fee"]["status"] == "VERIFIED"
    assert free["details"]["cost"]["entry"]["adult"]["vnd"] == 0
    zero = _free_entry({**FEE_ESTIMATE, "min_vnd": 0, "typical_vnd": 0, "max_vnd": 0})
    assert zero["service"]["entry_fee"]["status"] == "VERIFIED"
