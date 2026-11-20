"""Reputation score: Maps rating and review count on one pool scale (docs/CORPUS.md §5. Aggregate)."""

import json
import math
import random

import pytest

from corpus.serving import reputation

CFG = {"prior_strength": 20, "weights": {"rating": 0.35, "volume": 0.65}, "z_span": 3, "min_pool": 30}


def pool(n=400, seed=0):
    """Pairs shaped like the Da Lat stay pool: rating mean ~4.5 (left-skewed), reviews log-normal (median ~100)."""
    rnd = random.Random(seed)
    return [(round(min(5.0, 5.0 - rnd.gammavariate(1.6, 0.28)), 4), max(1, int(math.exp(rnd.gauss(4.6, 1.2))))) for _ in range(n)]


def rep(rating, reviews, pairs=None):
    return reputation.of(rating, reviews, reputation.pool_stats(pairs or pool(), CFG), CFG)["score"]


def test_owner_orderings_hold_on_the_pool():
    big = rep(4.6, 3000)
    assert big > rep(4.7, 1000)
    assert big > rep(4.9, 500)


def test_volume_matters_but_a_good_place_outranks_a_big_poor_one():
    assert rep(4.6, 3000) > rep(4.0, 1500)
    assert rep(4.6, 3000) > rep(4.3, 1500)
    assert rep(4.5, 500) > rep(4.0, 20)


def test_five_stars_from_three_reviews_cannot_win():
    assert rep(5.0, 3) < rep(4.5, 500) < rep(4.6, 3000)
    assert rep(5.0, 3) < rep(4.7, 1000)


def test_rating_adjusted_toward_pool_mean_by_prior_strength():
    stats = reputation.pool_stats(pool(), CFG)
    few, many = reputation.of(5.0, 3, stats, CFG), reputation.of(5.0, 3000, stats, CFG)
    assert few["rating_adj"] < many["rating_adj"] <= 5.0
    assert abs(few["rating_adj"] - stats["mean"]) < abs(5.0 - stats["mean"]) * 0.2


def test_parts_are_on_one_zero_to_one_scale():
    r = reputation.of(4.6, 3000, reputation.pool_stats(pool(), CFG), CFG)
    assert all(0.0 <= r[k] <= 1.0 for k in ("score", "rating_pct", "volume_pct"))
    assert r["score"] == pytest.approx(0.35 * r["rating_pct"] + 0.65 * r["volume_pct"], abs=1e-3)
    assert (r["rating"], r["reviews"]) == (4.6, 3000)


def test_extremes_clip_to_the_scale():
    r = reputation.of(5.0, 10**7, reputation.pool_stats(pool(), CFG), CFG)
    assert r["volume_pct"] == 1.0 and r["score"] <= 1.0


def test_unknown_rating_or_reviews_is_none_never_zero():
    stats = reputation.pool_stats(pool(), CFG)
    assert reputation.of(None, 100, stats, CFG) is None
    assert reputation.of(4.5, None, stats, CFG) is None
    assert reputation.of(4.5, 0, stats, CFG) is None  # a rating without reviews is not evidence
    assert reputation.of(4.5, 100, None, CFG) is None


def test_flat_pool_has_no_spread_so_none():
    assert reputation.pool_stats([(4.5, 10)] * 50, CFG) is None


def _place(base, fid, score, reviews):
    d = base / "gmaps" / "places" / fid.replace(":", "_")
    d.mkdir(parents=True)
    (d / "place.json").write_text(json.dumps({"fid": fid, "score": score, "reviews": reviews}), encoding="utf-8")


def _rec(fid, group, lat=11.94, lng=108.44):
    return {"id": fid, "identity": {"category_group": group, "lat": lat, "lng": lng}, "provenance": {}}


CITIES = {"dalat": {"area": [11.78, 108.3, 12.12, 108.66]}}


def test_attach_sets_identity_numbers_and_provenance_reputation(tmp_path):
    recs = []
    for i, (s, n) in enumerate(pool(60, 1)):
        fid = f"0xa{i}:0xb{i}"
        _place(tmp_path, fid, s, n)
        recs.append(_rec(fid, "stay"))
    gone = _rec("0xnone:0xnone", "stay")  # no Maps file: unknown, not zero
    recs.append(gone)
    assert reputation.attach(recs, tmp_path, CFG, CITIES) == 60
    r = recs[0]
    assert r["identity"]["rating"] is not None and r["identity"]["reviews"] is not None
    assert set(r["provenance"]["reputation"]) >= {"score", "rating", "reviews", "rating_adj", "rating_pct", "volume_pct"}
    assert gone["provenance"]["reputation"] is None and gone["identity"]["rating"] is None


def test_small_group_is_measured_against_the_whole_city(tmp_path):
    recs = []
    for i, (s, n) in enumerate(pool(80, 2)):
        fid = f"0xa{i}:0xb{i}"
        _place(tmp_path, fid, s, n)
        recs.append(_rec(fid, "stay" if i < 70 else "golf"))
    reputation.attach(recs, tmp_path, CFG, CITIES)
    assert all(r["provenance"]["reputation"] for r in recs)
    assert recs[-1]["provenance"]["reputation"]["pool"] == "dalat/*"
    assert recs[0]["provenance"]["reputation"]["pool"] == "dalat/stay"


def test_owner_orderings_hold_in_every_pool_of_the_real_snapshot():
    """Real Maps numbers of the served corpus, with the shipped config (skipped without a snapshot)."""
    try:
        from corpus import serving
        recs = serving.load()
    except Exception:
        pytest.skip("no snapshot")
    pairs = {}
    for r in recs:
        base = reputation.maps_numbers(reputation.data_dir() / "gmaps" / "places", r["id"])
        if base[0] and base[1]:
            pairs.setdefault(r["identity"].get("category_group"), []).append(base)
    pairs["*"] = [p for v in pairs.values() for p in v]
    cfg = reputation.settings()
    checked = 0
    for g, ps in pairs.items():
        stats = reputation.pool_stats(ps, cfg) if len(ps) >= cfg["min_pool"] else None
        if stats is None:
            continue
        s = lambda a, b: reputation.of(a, b, stats, cfg)["score"]
        assert s(4.6, 3000) > s(4.7, 1000) and s(4.6, 3000) > s(4.9, 500), g
        assert s(4.6, 3000) > s(4.0, 1500) and s(5.0, 3) < s(4.5, 500), g
        checked += 1
    assert checked >= 3
