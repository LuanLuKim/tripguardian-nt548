"""⑤ Ranking (docs/PLACE_DECISION.md §8). Every part is kept on the candidate to explain and debug the score."""

from bisect import bisect_left

from corpus.serving import conf, feature
from requirements import applicable

from .diversify import display_group
from .model import Cand
from .settings import default
from .wishes import lift

# conf: corpus.serving.evidence (config/serving.yaml `evidence`): grows with the authors past 3, shrinks when few of
# the place's reviewers said it. The snapshot's `conf` column is the same function.


def wants(si, profile, cfg=None) -> list[tuple[str, str, dict | None, float, str | None]]:
    """(feature, value, context, weight, scope): Search Input, then the session's own additions. A wish whose source is
    the long-term profile is a prior: it counts cfg.prior_weight of a wish of this trip, and is dropped when this trip
    has any wish of its own on the same feature (the current trip wins, owner decision 11)."""
    return prior_scaled([(w.feature, w.value, w.context, w.weight, w.scope, w.source) for w in si.soft_weights
                         if w.weight != 0], cfg) + [(s.feature, s.value, None, s.weight, None) for s in profile.soft]


def prior_scaled(rows, cfg=None) -> list[tuple]:
    """rows: (feature, value, context, weight, scope, source). Priors scaled and overridden; the source is dropped."""
    k = (cfg or default()).prior_weight
    own = {r[0] for r in rows if r[5] != "profile"}
    return [(*r[:3], r[3] * k if r[5] == "profile" else r[3], r[4]) for r in rows if r[5] != "profile" or r[0] not in own]


def _contextual(f: dict, ctx: dict | None) -> str:
    for k, v in (ctx or {}).items():
        d = f["by_context"].get(f"{k}={v}")
        if d:
            return max(d, key=d.get)
    return f["value"]


def preference(rec: dict, ws, activity=None, role=None) -> tuple[float, float, list[tuple]]:
    """(preference fit, uncertainty, matches). No evidence adds 0, never a minus; it counts as uncertainty."""
    ws = [(*w[:4], w[4] if len(w) > 4 else None) for w in ws]
    ws = [w for w in ws if applicable(rec, {"feature": w[0], "scope": w[4]}, activity, role)]
    total = sum(max(1.0, abs(w[3])) for w in ws)  # a prior counts 1 below, its weight above: alone it is a small fit
    if not total:
        return 0.0, 0.0, []
    fit = missing = 0.0
    matches = []
    for fid, val, ctx, w, _ in ws:
        f = feature(rec, fid)
        if (f is None or f["status"] == "UNCERTAIN") and w > 0:
            missing += w
        if f is None:
            continue
        if _contextual(f, ctx) == val:
            contrib = w * conf(f)
            fit += contrib
            matches.append((fid, val, round(contrib, 4), f["n"]))
    return fit / total, missing / total, matches


def preference_fit(rec: dict, soft_weights: list[dict], activity=None) -> tuple[float, list[tuple]]:
    """Public: how one serving record matches a trip's soft wishes (Search Input soft_weights as dicts), as
    (fit in -1..1, matches). Used outside Decision (companion's nearby picks) without building candidates."""
    ws = prior_scaled([(w["feature"], w["value"], w.get("context"), w["weight"], w.get("scope"), w.get("source"))
                       for w in soft_weights if w.get("weight")])
    fit, _, matches = preference(rec, ws, activity)
    return fit, matches


def _price_norm(rec: dict, cfg) -> float:
    p = rec["operation"].get("price_per_person")
    if not p:
        return 0.0
    v = p["value"]
    lo = v.get("min_vnd") or 0
    mid = (lo + (v.get("max_vnd") or lo)) / 2
    return min(1.0, mid / cfg.price_ref_vnd)


def reputation_part(rec: dict) -> float:
    """Maps rating + review volume on one pool scale (corpus.serving.reputation), centred: above the pool's middle adds,
    below subtracts. Unknown (no rating or no reviews) adds 0, never a minus."""
    rep = (rec["provenance"].get("reputation") or {}).get("score")
    return 0.0 if rep is None else round(rep - 0.5, 4)


def score(cands: list[Cand], si, profile, cfg, voices: list[int] | None = None, wishes=()) -> None:
    """voices: the sorted voices of every live candidate, when scoring a few of them alone (decision.frame).
    wishes: decision.wishes.build of this Search Input."""
    ws = wants(si, profile, cfg)
    voices = voices if voices is not None else sorted(c.rec["provenance"].get("voices") or 0 for c in cands)
    top = max(1, len(voices) - 1)
    visited = set(si.novelty.visited) | set(profile.visited)
    nov_of = {"new": -1.0, "familiar": 0.3}
    for c in cands:
        pref, unc, matches = preference(c.rec, ws, si.activities.get(c.id), c.role)
        pop = min(1.0, bisect_left(voices, c.rec["provenance"].get("voices") or 0) / top)
        exp = si.context.experience
        # a kept place with no serving record: nothing known, so no wish can be said to be met
        wish, c.wishes = (0.0, []) if c.missing else lift(wishes, c.id, c.role, display_group(c, cfg))
        c.parts = {"ctx": c.fit, "pref": round(pref, 4),
                   "nov": nov_of.get(si.novelty.level, 0.0) if c.id in visited else 0.0,
                   "exp": pop if exp == "first" else 1 - pop if exp == "returning" else 0.0,
                   "pop": round(pop, 4), "unc": -round(unc, 4),
                   "price": -round(profile.price_sensitivity * _price_norm(c.rec, cfg), 4),
                   "wish": round(wish, 4), "rep": reputation_part(c.rec)}
        c.score = round(sum(cfg.weights.get(k, 0.0) * v for k, v in c.parts.items()), 4)
        c.matches = sorted(matches, key=lambda m: (-m[2], m[0]))
