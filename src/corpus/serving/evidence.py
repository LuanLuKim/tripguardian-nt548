"""Confidence of one served feature, the single definition Decision's ranking and the snapshot's `conf` column share.

  conf = agreement x support(n) x mention(rate) x status weight

support(n): authors who said it. Rises linearly to `base` at `full_n` authors, then log-shaped up to 1.0 at `ref_n`
(diminishing returns, strictly increasing between them): 3, 30 and 300 authors with equal agreement order strictly.
mention(rate): share of the place's read reviewers who named it. Below `rate_ref` it takes up to `rate_weight` off,
so 6 mentions among 3,000 reviews count less than 6 among 10; a rate of 0 or None (declared by Maps / the business
itself, or no review volume) is unknown and costs nothing. Only ranking uses conf; hard filters never do.
"""

import math

STATUS_W = {"VERIFIED": 1.0, "OUTDATED": 0.7, "UNCERTAIN": 0.5}


def support(n: int, cfg: dict) -> float:
    full, base, ref = cfg["full_n"], cfg["base"], cfg["ref_n"]
    if n <= 0:
        return 0.0
    if n < full:
        return base * n / full
    return min(1.0, base + (1 - base) * math.log(n / full) / math.log(ref / full))


def mention(rate: float | None, cfg: dict) -> float:
    if not rate:
        return 1.0
    return 1 - cfg["rate_weight"] * (1 - min(1.0, rate / cfg["rate_ref"]))


def conf(f: dict, cfg: dict | None = None) -> float:
    """A served feature's confidence in 0..1; derived features with no author (agreement None) have none."""
    if cfg is None:
        from .record import config
        cfg = config()["evidence"]
    agreement = f["confidence"]["agreement"]
    if agreement is None:
        return 0.0
    return agreement * support(f["n"], cfg) * mention(f.get("mention_rate"), cfg) * STATUS_W[f["status"]]
