"""Deterministic, bounded session-only reranking from backed curation evidence."""

from collections import Counter
from math import comb

import numpy as np

from corpus.serving import conf, feature

GROUPS = ("experience", "environment", "service", "effort", "suitability")


def attributes(rec):
    """Only measured, verified attributes can teach or receive a taste adjustment."""
    if not rec:
        return {}
    return {fid: f for group in GROUPS for fid in rec.get(group, {})
            if (f := feature(rec, fid)) is not None
            and f.get("status") == "VERIFIED" and f.get("n", 0) > 0 and f.get("evidence")}


def signals(state, si, by_id, cfg):
    """Recompute from current choices, not an accumulating log: undo/reselect retracts votes."""
    blocked = {w.feature for w in si.soft_weights if w.source != "profile"}
    blocked |= {h.feature for h in si.hard_filters} | {w.feature for w in state.profile.soft}
    anchors = {a.place_id for a in si.anchors}
    positive, negative, unexplained = Counter(), Counter(), Counter()
    cf = cfg.wish["session_learning"]
    for pid in sorted(set(state.selected) - anchors):
        positive.update((fid, f["value"]) for fid, f in attributes(by_id.get(pid)).items()
                        if fid not in blocked and f["value"] in cf["taste_values"].get(fid, []))
    for drop in state.dropped:
        target = negative if drop.reason == "dislike" else unexplained if drop.reason is None else None
        if target is not None:
            target.update((fid, f["value"]) for fid, f in attributes(by_id.get(drop.place_id)).items() if fid not in blocked)
    cf = cfg.wish["session_learning"]
    count = len(set(state.selected) - anchors)
    weights = {}
    for key in sorted(positive.keys() | negative.keys() | unexplained.keys()):
        pos = positive[key]
        if count == 1:
            pos *= cf["single_scale"]
        elif pos < cf["consistent_min"] or pos / count < cf["consistent_share"]:
            pos = 0
        neg = negative[key]
        pattern = unexplained[key] if unexplained[key] >= cfg.pattern_min else 0
        weight = (cf["select_weight"] * pos - cf["dislike_weight"] * neg - cf["pattern_weight"] * pattern)
        if weight:
            weights[key] = weight / (positive[key] + neg + pattern + cf["shrink"])
    return weights


def evidence_strength(successes, count, matches, pool_size, prior):
    """One-sided binomial evidence with a smoothed null and small-sample shrinkage."""
    if not count or not pool_size or matches == pool_size:
        return 0.0
    prevalence = (matches + 1) / (pool_size + 2)
    if successes / count <= prevalence:
        return 0.0
    tail = sum(comb(count, k) * prevalence ** k * (1 - prevalence) ** (count - k)
               for k in range(successes, count + 1))
    return (1 - tail) * count / (count + prior)


def adjustments(region, state, si, cfg, memo=None):
    """A separate score delta: no uncertainty term, filtering, profile writes or full-weight path."""
    if not cfg.wish["session_learning"].get("enabled", False):
        return {}
    votes = signals(state, si, region.by_id, cfg)
    if not votes:
        return {}
    masks = memo.setdefault("learning_masks", {}) if memo is not None else {}
    terms, total = np.zeros(len(region.ids)), 0.0
    weighted = []
    selected = sorted(set(state.selected) - {a.place_id for a in si.anchors})
    selected_groups = {region.column("category_group")[region.index[p]] for p in selected if p in region.index}
    baseline = np.array([g in selected_groups for g in region.column("category_group")], dtype=bool)
    cf = cfg.wish["session_learning"]
    for (fid, value), weight in votes.items():
        key = (fid, value)
        if key not in masks:
            col = region.feature(fid)
            matches = np.zeros(len(region.ids))
            for i, (pid, v, st, n) in enumerate(zip(region.ids, col.value, col.status, col.n)):
                if v == value and st == "VERIFIED" and n and n > 0:
                    f = feature(region.record(pid), fid)
                    if f and f.get("evidence"):
                        matches[i] = conf(f)
            masks[key] = matches
        matches = masks[key]
        strength = 1.0
        if weight > 0 and len(selected) >= cf["consistent_min"]:
            successes = sum(bool(matches[region.index[p]]) for p in selected if p in region.index)
            strength = evidence_strength(successes, len(selected), np.count_nonzero(matches[baseline]),
                                         np.count_nonzero(baseline), cf["evidence_prior"])
        if strength:
            weighted.append((key, weight * strength, matches))
    positives = sorted((x for x in weighted if x[1] > 0), key=lambda x: (-x[1], x[0]))[:cf["top_k"]]
    for _, weight, matches in [*positives, *(x for x in weighted if x[1] < 0)]:
        terms += matches * weight
        total += max(abs(weight), cf["select_weight"])
    if not total:
        return {}
    delta = cfg.wish["session_learning"]["max_lift"] * terms / total
    return {pid: round(float(v), 4) for pid, v in zip(region.ids, delta) if v}
