"""When the chat shows TAGS, SUBTAGS or a plain LIST (config/tags.yaml `policy`, docs/TRIP_UNDERSTANDING.md §Tag, subtag hay
danh sách). Pure: the ask's own words decide, no model.

    dims = what the ask already fixes: a category group, a must feature, a dish, a text (a prefer feature is a mood)
    0 dims, many allowed places   -> TAGS     the biggest kinds of the places ("gợi ý gì hay ở Đà Lạt")
    1 dim, a good split           -> SUBTAGS  groups inside that interest ("thích săn mây, có kiểu nào")
    >= flat_dims, few matches, a weak split, or the same block was just shown -> LIST (the plain place cards)
"""

from __future__ import annotations

from typing import Literal, Sequence

from corpus import tags

Mode = Literal["tags", "subtags", "places"]


def config() -> dict:
    return tags.config()["policy"]


def dimensions(groups: Sequence[str], must: Sequence, dish: str | None, text: str | None) -> int:
    """How many things the ask names: groups count once, all must features once."""
    return bool(groups) + bool(must) + bool((dish or "").strip()) + bool((text or "").strip())


def first_pick(dims: int, allowed: int, cfg: dict | None = None) -> tuple[Mode, str]:
    """The mode the ask calls for before any data says otherwise -> (mode, why)."""
    cfg = cfg or config()
    if dims >= cfg["flat_dims"]:
        return "places", "specific"
    if dims == 0:
        return ("tags", "vague") if allowed >= cfg["tags_min_places"] else ("places", "few_places")
    return "subtags", "interest"


def signature(mode: str, fixed: str, ids: Sequence[str]) -> str:
    """Names one block: its level, what the ask fixed, the tags / subtags it offered."""
    return f"{mode}|{fixed}|{','.join(sorted(ids))}"


def repeated(sig: str, seen: Sequence[str], cfg: dict | None = None) -> bool:
    """The same block among the last `repeat_back` ones the chat showed (seen: newest first)."""
    return sig in list(seen)[:(cfg or config())["repeat_back"]]
