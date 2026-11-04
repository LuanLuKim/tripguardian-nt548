"""Split a ranked set of places into subtags (docs/PLACE_DECISION.md §Tag và subtag). Pure: no I/O, no model.

One AXIS is chosen for the whole set (category, experience, style or dish): the one whose groups cover most of the set
and are the most even. An axis the query already fixed is skipped (asked "săn mây": no split by cloud_hunting). A place
is in a group only with evidence (PlaceTags); a place no group holds is a leftover, never shown as a fake group.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from ..serving import dishes as menu
from . import vocab
from .vocab import PlaceTags


FILLER = {"có", "được", "giữa"}  # words of a `with` phrase that add nothing to a noun that already says the rest
VARIANT = "v:"  # key prefix of a dish variant (bánh căn + trứng cút), against a dish kind


@dataclass(frozen=True)
class Fixed:
    """What the query already states, so no subtag repeats it."""
    groups: frozenset[str] = frozenset()    # category groups asked
    features: frozenset[str] = frozenset()  # feature keys asked (must / prefer)
    styles: frozenset[str] = frozenset()
    dish: str | None = None                 # the dish phrase asked


@dataclass(frozen=True)
class Subtag:
    id: str                    # "axis:key"
    axis: str
    key: str
    label: str
    count: int
    place_ids: tuple[str, ...]  # best first, as the set was ranked


@dataclass(frozen=True)
class Split:
    axis: str
    subtags: tuple[Subtag, ...]
    total: int      # places in the set
    covered: int    # places the subtags hold
    score: float


def fixed_dishes(dish: str | None) -> frozenset[str]:
    """Dish kinds a dish query already names: a kind is fixed when the query holds one of its phrases (a more specific
    kind, "lẩu gà lá é" under "lẩu", is not)."""
    if not dish:
        return frozenset()
    q = menu.key_for(dish, True)
    return frozenset(d["id"] for d in vocab.dish_kinds().values()
                     if any(menu.has_phrase(q, menu.key_for(p, True)) for p in d["phrases"]))


def _members(axis: str, places: Sequence[PlaceTags], skip: frozenset[str],
             allow: frozenset[str] | None = None) -> dict[str, list[int]]:
    """key -> indexes of the places that carry it (in vocabulary order). A parent is carried only by a place without
    one of its children (a child is the more exact evidence). allow: only these keys; skip: never these."""
    kids = vocab.children(axis)
    feats = vocab.config()["features"]
    out: dict[str, list[int]] = {}
    for i, p in enumerate(places):
        have = p.keys(axis)
        for k in have:
            if k in skip or (allow is not None and k not in allow) or (kids.get(k) and have & kids[k]):
                continue
            if axis == "experience" and feats.get(k, {}).get("split") is False:
                continue
            out.setdefault(k, []).append(i)
    order = {k: n for n, k in enumerate({"category": vocab.config()["categories"], "experience": vocab.config()["features"],
                                         "style": vocab.styles(), "dish": vocab.dish_kinds()}[axis])}
    return dict(sorted(out.items(), key=lambda kv: order.get(kv[0], len(order))))


def _skip(axis: str, places: Sequence[PlaceTags], fixed: Fixed, cfg: dict) -> tuple[frozenset[str], frozenset[str] | None] | None:
    """(keys the query fixed, the only keys allowed or None) of the axis; None = the axis does not apply to this set:
    the query fixed it (a category), or the dish axis on a set that is not mostly food. A dish query leaves only the
    kinds under the dish it names (lẩu -> lẩu bò, lẩu cá): other dishes a place also serves say nothing of the ask."""
    if axis == "category":
        if fixed.groups or (vocab.enabled() and fixed.dish):
            return None
        if vocab.enabled() and fixed.features:
            pairs = vocab.config().get("subtag_categories", {})
            allowed = set.intersection(*(set(pairs.get(k, ())) for k in sorted(fixed.features)))
            return frozenset(), frozenset(allowed)
        if vocab.enabled() and fixed.styles:
            return frozenset(), frozenset(vocab.config()["membership"]["style_groups"])
        return frozenset(), None
    if axis == "experience":
        if vocab.enabled():
            if fixed.features or fixed.dish or fixed.styles:
                return None
            if fixed.groups:
                pairs = vocab.config().get("subtag_categories", {})
                return frozenset(), frozenset(k for k, groups in pairs.items() if fixed.groups <= set(groups))
        return fixed.features, None
    if axis == "style":
        if vocab.enabled() and (fixed.features or fixed.dish or fixed.styles
                                or not fixed.groups <= set(vocab.config()["membership"]["style_groups"])):
            return None
        return fixed.styles, None
    if not fixed.dish:
        if vocab.enabled() and (fixed.features or fixed.styles):
            return None
        food = sum(p.group in cfg["dish_groups"] for p in places)
        return None if food < cfg["dish_min_food"] * len(places) else (frozenset(), None)
    named = fixed_dishes(fixed.dish)
    return named, frozenset().union(*(vocab.children("dish").get(k, frozenset()) for k in named))


def _cover(members: dict[str, list[int]], total: int, cfg: dict) -> tuple[list[tuple[str, list[int]]], int]:
    """The biggest groups first, up to max_groups. A group holding more than max_share of the set is no split and is
    left out; one that is nearly the same places as a group already taken (Jaccard above max_similar) adds nothing.
    -> ([(key, ALL the places that carry it)], places in at least one group). A place carrying two tags is in two
    groups; each group list stays true to its tag."""
    pool = [(k, set(v)) for k, v in members.items() if cfg["min_size"] <= len(v) <= cfg["max_share"] * total]
    pool.sort(key=lambda kv: -len(kv[1]))  # a tie keeps vocabulary order
    taken: set[int] = set()
    kept: list[tuple[str, set[int]]] = []
    chosen: list[tuple[str, list[int]]] = []
    for key, ids in pool:
        if len(chosen) >= cfg["max_groups"]:
            break
        if any(len(ids & g) / len(ids | g) > cfg["max_similar"] for _, g in kept):
            continue
        taken |= ids
        kept.append((key, ids))
        chosen.append((key, sorted(ids)))
    return chosen, len(taken)


def _balance(sizes: list[int]) -> float:
    """0..1: how evenly the groups share the places (normalized entropy of their sizes)."""
    mass = sum(sizes)
    return -sum(s / mass * math.log(s / mass) for s in sizes) / math.log(len(sizes)) if len(sizes) > 1 else 0.0


def _overlap(sizes: list[int], covered: int) -> float:
    """0..1: the share of the groups' places that sit in more than one group (0 = a partition)."""
    return (sum(sizes) - covered) / sum(sizes)


def _score(sizes: list[int], covered: int, total: int, bias: float) -> float:
    return covered / total * (0.6 + 0.4 * _balance(sizes)) * (1 - _overlap(sizes, covered)) * bias


def _noun(group: str) -> str:
    return (vocab.config()["categories"].get(group) or {}).get("noun") or vocab.label("category", group)


def _single(fixed: Fixed) -> str | None:
    return _noun(next(iter(fixed.groups))) if len(fixed.groups) == 1 else None


def compose(axis: str, key: str, fixed: Fixed) -> str:
    """The natural Vietnamese label of one subtag, from the vocabulary and what the query fixed."""
    cfg = vocab.config()
    noun = _single(fixed)
    if axis == "category":
        over = next((cfg["overrides"][f"{key}+{f}"] for f in sorted(fixed.features) if f"{key}+{f}" in cfg["overrides"]), None)
        if over:
            return over
        with_ = next((cfg["features"][f].get("with") for f in sorted(fixed.features) if cfg["features"].get(f, {}).get("with")), None)
        if with_:
            noun = _noun(key)
            said = {w for w in with_.lower().split() if w not in FILLER}
            return noun if said <= set(noun.lower().split()) else f"{noun} {with_}"  # "Khu cắm trại", not "... cắm trại được"
        return f"{_noun(key)} có món {fixed.dish.strip()}" if fixed.dish and fixed.dish.strip() else vocab.label("category", key)
    if axis == "experience":
        with_ = (cfg["features"].get(key) or {}).get("with")
        return f"{noun} {with_}" if noun and with_ else vocab.label("experience", key)
    if axis == "style":
        return f"{noun or cfg['style_noun']} {cfg['style_with'].get(key) or vocab.label('style', key).lower()}"
    if key.startswith(VARIANT):
        dish = (fixed.dish or "").strip()
        return f"{dish[:1].upper()}{dish[1:]} {vocab.variant_kinds()[key[len(VARIANT):]]['label']}"
    return vocab.label("dish", key)


def split(places: Sequence[PlaceTags], fixed: Fixed = Fixed(), variants: Mapping[str, frozenset[str]] | None = None,
          cfg: dict | None = None) -> Split | None:
    """The best split of `places` (ranked best first) into subtags, or None when no axis splits it well: the set is
    small, or no axis gives min_groups groups of min_size places that together hold min_cover of the set.
    variants: place id -> the variants of the dish the query names that the place's menu holds (vocab.dish_variants);
    only used with fixed.dish."""
    cfg = cfg or vocab.config()["group"]
    total = len(places)
    if total < cfg["min_places"]:
        return None
    best: Split | None = None
    for axis in vocab.AXES:
        rule = _skip(axis, places, fixed, cfg)
        if rule is None:
            continue
        found = _members(axis, places, rule[0], rule[1])
        if axis == "dish" and fixed.dish:  # only what refines the named dish: finer kinds and its variants
            for i, p in enumerate(places):
                for v in (variants or {}).get(p.id, ()):
                    found.setdefault(f"{VARIANT}{v}", []).append(i)
        chosen, covered = _cover(found, total, cfg)
        sizes = [len(m) for _, m in chosen]
        limit = 1.0 if axis == "dish" and fixed.dish else cfg["max_overlap"]  # what a dish comes with overlaps by nature
        if (len(chosen) < cfg["min_groups"] or covered < cfg["min_cover"] * total or _balance(sizes) < cfg["min_balance"]
                or _overlap(sizes, covered) > limit):
            continue
        score = _score(sizes, covered, total, cfg["axis_bias"].get(axis, 1.0))
        if best is None or score > best.score:
            subs = tuple(Subtag(vocab.ref(axis, k), axis, k, compose(axis, k, fixed), len(m), tuple(places[i].id for i in m))
                         for k, m in chosen)
            best = Split(axis, subs, total, covered, round(score, 4))
    return best


def kinds(places: Sequence[PlaceTags], skip: Sequence[str] = (), cfg: dict | None = None) -> Split | None:
    """The tags (top-level kinds) a vague ask is offered: the biggest category / experience tags of the allowed places,
    a few per axis, none held by most of the set. Not a partition: a place may carry several, so `covered` counts the
    places in at least one. skip: tag refs ("axis:key") already picked. None when fewer than `min` kinds qualify or the
    set is smaller than `group.min_places`. Same evidence rule as split."""
    cfg = cfg or vocab.config()["policy"]["kinds"]
    total = len(places)
    if total < vocab.config()["group"]["min_places"]:
        return None
    pool: list[tuple[str, str, list[int]]] = []
    for axis, cap in cfg["per_axis"].items():
        gone = frozenset(r.partition(":")[2] for r in skip if r.startswith(f"{axis}:"))
        if axis == "experience":  # a feature the vocabulary marks home: false is too plain to be a kind to pick ("Decor ấm cúng")
            gone |= frozenset(k for k, f in vocab.config()["features"].items() if f.get("home") is False)
        found = [(axis, k, v) for k, v in _members(axis, places, gone).items()
                 if cfg["min_size"] <= len(v) <= cfg["max_share"] * total]
        found.sort(key=lambda t: -len(t[2]))  # a tie keeps vocabulary order
        pool += found[:cap]
    pool.sort(key=lambda t: -len(t[2]))
    kept: list[tuple[str, str, list[int]]] = []
    similar = vocab.config()["group"]["max_similar"]
    for t in pool:  # a kind that is nearly the same places as one already taken is a repeat
        if len(kept) < cfg["max"] and not any(len(set(t[2]) & set(o[2])) / len(set(t[2]) | set(o[2])) > similar for o in kept):
            kept.append(t)
    pool = kept
    if len(pool) < cfg["min"]:
        return None
    subs = tuple(Subtag(vocab.ref(a, k), a, k, compose(a, k, Fixed()), len(m), tuple(places[i].id for i in m)) for a, k, m in pool)
    return Split("tags", subs, total, len({i for _, _, m in pool for i in m}), 0.0)


def members(places: Sequence[PlaceTags], axis: str, key: str) -> list[PlaceTags]:
    """The places that carry one tag, in their order (a tag's own place list)."""
    return [p for p in places if p.carries(axis, key)]
