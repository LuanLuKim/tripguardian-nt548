"""Reputation of a place from Maps' own population numbers (`score`, `reviews` in data/gmaps/places/<fid>/place.json),
never the size of the crawled sample (docs/CORPUS.md, serving). Rating and review volume are put on one scale:

  rating_adj = (n*rating + m*pool_mean) / (n + m)         Bayesian average, so 5.0 from 3 reviews cannot win
  rating_pct, volume_pct = z-score inside the pool (of rating_adj, of ln(1+reviews)), each squashed to 0..1 the
                           same way (z / 2*z_span + 0.5, clipped), so one pool standard deviation is the same
                           distance on both axes; a rank percentile would saturate for volume at the top
  score = w_rating*rating_pct + w_volume*volume_pct

Pool = city x category_group; a pool under `min_pool` places is measured against its whole city. A place with no
rating or no reviews has no reputation: None, never 0 (unknown is not bad).
"""

import json
import math
from collections import defaultdict

import yaml

from ..crawl.common.files import ROOT, data_dir, safe_name
from .record import config

ROUND = 4


def settings() -> dict:
    return config()["reputation"]


def _mean_sd(xs: list[float]) -> tuple[float, float]:
    mean = sum(xs) / len(xs)
    return mean, math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))


def _adjusted(rating: float, reviews: int, mean: float, m: float) -> float:
    return (reviews * rating + m * mean) / (reviews + m)


def pool_stats(pairs: list[tuple[float, int]], cfg: dict | None = None) -> dict | None:
    """(rating, reviews) of every place of one pool -> the pool's mean rating and the mean / sd of rating_adj and of
    ln(1+reviews). None when the pool has no spread to measure against (empty, or all alike)."""
    cfg = cfg or settings()
    pairs = [(r, n) for r, n in pairs if r is not None and n]
    if not pairs:
        return None
    mean = sum(r for r, _ in pairs) / len(pairs)
    adj_mean, adj_sd = _mean_sd([_adjusted(r, n, mean, cfg["prior_strength"]) for r, n in pairs])
    vol_mean, vol_sd = _mean_sd([math.log1p(n) for _, n in pairs])
    if adj_sd < 1e-9 or vol_sd < 1e-9:
        return None
    return {"mean": mean, "adj": (adj_mean, adj_sd), "vol": (vol_mean, vol_sd), "n": len(pairs)}


def _unit(z: float, span: float) -> float:
    return min(1.0, max(0.0, 0.5 + z / (2 * span)))


def of(rating: float | None, reviews: int | None, stats: dict | None, cfg: dict | None = None) -> dict | None:
    """The reputation of one place in a pool, or None when its rating, review count or pool is unknown."""
    cfg = cfg or settings()
    if rating is None or not reviews or reviews < 0 or stats is None:
        return None
    adj = _adjusted(rating, reviews, stats["mean"], cfg["prior_strength"])
    rating_u = _unit((adj - stats["adj"][0]) / stats["adj"][1], cfg["z_span"])
    volume_u = _unit((math.log1p(reviews) - stats["vol"][0]) / stats["vol"][1], cfg["z_span"])
    w = cfg["weights"]
    return {"score": round(w["rating"] * rating_u + w["volume"] * volume_u, ROUND), "rating": rating, "reviews": reviews,
            "rating_adj": round(adj, ROUND), "rating_pct": round(rating_u, ROUND), "volume_pct": round(volume_u, ROUND)}


def city_of(identity: dict, cities: dict) -> str:
    """config/cities.yaml key whose area holds the place; "" outside every area."""
    lat, lng = identity.get("lat"), identity.get("lng")
    if lat is not None and lng is not None:
        for key, c in cities.items():
            a = c.get("area")
            if a and a[0] <= lat <= a[2] and a[1] <= lng <= a[3]:
                return key
    return ""


def maps_numbers(base, fid: str) -> tuple[float | None, int | None]:
    f = base / safe_name(fid) / "place.json"
    if not f.exists():
        return None, None
    doc = json.loads(f.read_text(encoding="utf-8"))
    score, reviews = doc.get("score"), doc.get("reviews")
    return (float(score) if isinstance(score, (int, float)) else None,
            int(reviews) if isinstance(reviews, (int, float)) else None)


def attach(records: list[dict], root=None, cfg: dict | None = None, cities: dict | None = None) -> int:
    """Set identity.rating / identity.reviews (Maps' numbers) and provenance.reputation on every record; returns how
    many got a reputation."""
    cfg = cfg or settings()
    if cities is None:
        cities = yaml.safe_load((ROOT / "config" / "cities.yaml").read_text(encoding="utf-8"))
    base = (root or data_dir()) / "gmaps" / "places"
    pools = defaultdict(list)  # (city, group) -> [(record, rating, reviews)]
    for rec in records:
        rating, reviews = maps_numbers(base, rec["id"])
        rec["identity"]["rating"], rec["identity"]["reviews"] = rating, reviews
        rec["provenance"]["reputation"] = None
        if rating is not None and reviews:
            pools[(city_of(rec["identity"], cities), rec["identity"].get("category_group"))].append((rec, rating, reviews))
    by_city = defaultdict(list)
    for (city, _), rows in pools.items():
        by_city[city] += rows
    city_stats = {c: pool_stats([(r, n) for _, r, n in rows], cfg) for c, rows in by_city.items()}
    done = 0
    for (city, group), rows in pools.items():
        small = len(rows) < cfg["min_pool"]
        stats = city_stats[city] if small else pool_stats([(r, n) for _, r, n in rows], cfg)
        label = f"{city}/*" if small else f"{city}/{group}"
        for rec, rating, reviews in rows:
            if rep := of(rating, reviews, stats, cfg):
                rec["provenance"]["reputation"] = {**rep, "pool": label}
                done += 1
    return done
