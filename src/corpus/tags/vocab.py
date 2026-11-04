"""The tag vocabulary (config/tags.yaml) and what a place carries of it.

A place carries a tag only with evidence in its serving record: a VERIFIED / OUTDATED feature value, a style tag read
from photos (corpus.index), a dish on its menu / in review orders / in its own name, its Maps category group. A place
with no evidence carries nothing: unknown is never "not that".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

import yaml

from ..crawl.common.files import ROOT, data_dir
from ..serving import dishes as menu
from ..serving import feature as served_feature

PATH = ROOT / "config" / "tags.yaml"
STYLES = ROOT / "config" / "styles.yaml"
AXES = ("category", "experience", "style", "dish")
FIRM = ("VERIFIED", "OUTDATED")


@cache
def raw_config() -> dict:
    """Shared config, including pending vocabulary not consumed by the deployed reader."""
    return yaml.safe_load(PATH.read_text(encoding="utf-8"))


_PENDING = ContextVar("tag_membership_pending", default=False)


@contextmanager
def pending_vocabulary():
    """Offline builders inspect pending tags without changing shared online configuration."""
    token = _PENDING.set(True)
    try:
        yield
    finally:
        _PENDING.reset(token)


def enabled() -> bool:
    return _PENDING.get() or raw_config().get("membership", {}).get("enabled") is True


def config() -> dict:
    """Effective vocabulary; unapproved membership leaves deployed semantics intact."""
    cfg = raw_config()
    return {**cfg, **cfg.get("vocabulary_v2", {})} if enabled() else cfg


@cache
def styles() -> dict[str, dict]:
    """config/styles.yaml: style id -> {label, parent?}."""
    doc = yaml.safe_load(STYLES.read_text(encoding="utf-8"))
    return {s["id"]: {"label": s["label"], **({"parent": s["parent"]} if s.get("parent") else {})} for s in doc["styles"]}


@cache
def dish_kinds() -> dict[str, dict]:
    return {d["id"]: d for d in config()["dishes"]}


@cache
def variant_kinds() -> dict[str, dict]:
    return {v["id"]: v for v in config()["variants"]}


def children(axis: str) -> dict[str, frozenset[str]]:
    """parent id -> its child ids, for the axes whose vocabulary has parents (style, dish)."""
    out: dict[str, set[str]] = {}
    items = styles() if axis == "style" else dish_kinds() if axis == "dish" else {}
    for kid, d in items.items():
        if d.get("parent"):
            out.setdefault(d["parent"], set()).add(kid)
    return {k: frozenset(v) for k, v in out.items()}


def label(axis: str, key: str) -> str:
    """The standalone Vietnamese label of one tag."""
    if axis == "category":
        return (config()["categories"].get(key) or {}).get("label", key)
    if axis == "experience":
        return (config()["features"].get(key) or {}).get("label", key)
    if axis == "style":
        return (styles().get(key) or {}).get("label", key)
    return (dish_kinds().get(key) or {}).get("label", key)


def known(axis: str, key: str) -> bool:
    return key in {"category": config()["categories"], "experience": config()["features"], "style": styles(),
                   "dish": dish_kinds()}.get(axis, {})


def ref(axis: str, key: str) -> str:
    return f"{axis}:{key}"


def resolve_ref(text: str) -> tuple[str, str] | None:
    """Resolve saved refs, including renamed tags; a retired unknown ref is harmless."""
    text = config().get("aliases", {}).get(str(text), str(text)) if enabled() else str(text)
    axis, _, key = text.partition(":")
    return (axis, key) if axis in AXES and known(axis, key) else None


def parse_ref(text: str) -> tuple[str, str]:
    """"experience:cloud_hunting" -> ("experience", "cloud_hunting"); ValueError when it is not a known tag."""
    result = resolve_ref(text)
    if result is None:
        raise ValueError(f"unknown tag {text!r}: use a tag id a tags tool returned")
    return result


@dataclass(frozen=True)
class PlaceTags:
    """The tags one place carries, each with evidence. group: Maps category group; features: keys of
    config/tags.yaml `features`; styles: style ids; dishes: dish kind ids."""
    id: str
    group: str | None = None
    features: frozenset[str] = frozenset()
    styles: frozenset[str] = frozenset()
    dishes: frozenset[str] = frozenset()

    def keys(self, axis: str) -> frozenset[str]:
        if axis == "category":
            return frozenset((self.group,)) if self.group in config()["categories"] else frozenset()
        return {"experience": self.features, "style": self.styles, "dish": self.dishes}[axis]

    def carries(self, axis: str, key: str) -> bool:
        return key in self.keys(axis)


def _feature_present(record: dict, key: str) -> bool:
    source = config()["features"].get(key, {}).get("source", key)
    if source != key:
        return False  # a split concept needs its own offline judgement, never inherits a broader old feature
    fid, _, value = source.partition("=")
    try:
        f = served_feature(record, fid)
    except KeyError:
        return False
    limits = config().get("membership", {})
    return (bool(f) and f.get("status") in FIRM and f.get("value") == (value or "present")
            and (f.get("n") or 0) >= limits.get("fallback_min_mentions", 3)
            and (f.get("mention_rate") or 0) >= limits.get("fallback_min_rate", .01))


def dish_keys(record: dict) -> frozenset[str]:
    """Dish kinds the record's own dish statements hold (menu, menu photo, review orders, a dish-named eatery)."""
    texts = [menu.key_for(t, True) for _, ts in menu.rows_of(record) for t in ts]
    if not texts:
        return frozenset()
    blob = f" {' | '.join(texts)} "  # " | " cannot sit inside a phrase, so a whole-word match never spans two statements
    return frozenset(d["id"] for d in dish_kinds().values() if any(f" {menu.key_for(p, True)} " in blob for p in d["phrases"]))


def tag_group(record: dict) -> str | None:
    """Tag-only corrections; never mutate Maps groups used by Decision."""
    ident = record.get("identity") or {}
    name = menu.fold(ident.get("name"))
    group = ident.get("category_group")
    if "karaoke" in name:
        return "karaoke"
    if group in {"dessert", "bar"} and any(menu.has_phrase(name, p) for p in (
            "banh can", "banh uot", "banh mi", "nem nuong", "nha hang", "quan an", "tiem an")):
        return "restaurant"
    return group


def _discovery_dishes(record: dict) -> frozenset[str]:
    """Strong dish motives, independent of the deliberately broad typed-dish lookup."""
    policy = config().get("dish_policy", {})
    group = tag_group(record)
    found = set()
    for key in dish_keys(record):
        allowed = policy.get("drink_groups", ()) if key in policy.get("drinks", ()) else policy.get("food_groups", ())
        if group not in allowed:
            continue
        phrases = dish_kinds()[key]["phrases"]
        for ev, texts in menu.rows_of(record):
            text = ev.get("dish") or ""
            if not any(menu.has_phrase(menu.keep(text), menu.keep(p)) for p in phrases):
                continue
            if any(menu.has_phrase(menu.fold(text), menu.fold(p)) for p in policy.get("exclude", {}).get(key, ())):
                continue
            if ev.get("source") in {"name", "menu_popular"} or (ev.get("source") == "review_order" and (ev.get("n") or 0) >= 3):
                found.add(key)
                break
    return frozenset(found)


def of_record(record: dict, style_ids=(), *, root: Path | None = None) -> PlaceTags:
    """Travel motives: fresh offline yes wins; unjudged inputs use strong fallback, never old mention rules."""
    from .membership import decisions

    if not enabled():
        ident = record.get("identity") or {}
        present = set()
        for key in config()["features"]:
            fid, _, value = key.partition("=")
            try:
                feature = served_feature(record, fid)
            except KeyError:
                continue
            if feature and feature.get("status") in FIRM and feature.get("value") == (value or "present"):
                present.add(key)
        return PlaceTags(record.get("id") or "", ident.get("category_group"), frozenset(present),
                         frozenset(s for s in style_ids if s in styles()), dish_keys(record))
    group = tag_group(record)
    judged = decisions(record, style_ids, root)
    def accept(axis, key, fallback):
        verdict = judged.get(ref(axis, key))
        return verdict == "yes" if verdict is not None else fallback
    features = frozenset(k for k in config()["features"] if accept("experience", k, _feature_present(record, k)))
    allowed_styles = group in config().get("membership", {}).get("style_groups", ())
    looks = frozenset(s for s in style_ids if s in styles() and allowed_styles and accept("style", s, False))
    fallback = _discovery_dishes(record)
    food = frozenset(k for k in dish_kinds() if accept("dish", k, k in fallback))
    if group and judged.get(ref("category", group)) in {"no", "unclear"}:
        group = None
    return PlaceTags(record.get("id") or "", group, features, looks, food)


def dish_variants(record: dict, dish: str) -> frozenset[str]:
    """Variants (config/tags.yaml `variants`) that one dish statement of the record names together with `dish`."""
    q = menu.key_for(dish, True)
    out: set[str] = set()
    for _, texts in menu.rows_of(record):
        for t in texts:
            k = menu.key_for(t, True)
            if menu.has_phrase(k, q):
                rest = f" {k} ".replace(f" {q} ", " ", 1)
                for old, new in config()["variant_fold"].items():
                    rest = rest.replace(f" {menu.key_for(old, True)} ", f" {menu.key_for(new, True)} ")
                out.update(v["id"] for v in variant_kinds().values()
                           if any(menu.has_phrase(rest.strip(), menu.key_for(p, True)) for p in v["phrases"]))
    return frozenset(out)


def load_styles(root: Path | None = None) -> dict[str, frozenset[str]]:
    """place id -> style ids from the current semantic index (data/index/<current>/places.json); {} without an index."""
    base = (root or data_dir()) / "index"
    try:
        version = (base / "current").read_text(encoding="utf-8").strip()
        doc = json.loads((base / version / "places.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {pid: frozenset(d["styles"]) for pid, d in doc.items() if d.get("styles")}
