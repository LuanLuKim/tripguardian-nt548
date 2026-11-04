"""A long tab grouped by kind (docs/PLACE_DECISION.md §Tag và subtag): the same corpus.tags.split as the Trip chat, over the
places of one candidate list. It helps the user choose ("trong tab quán ăn có kiểu nào?"): each kind names its size and a
few places. A place is in a kind only on evidence (unknown is in none); a list that does not split well gives no kinds."""

from __future__ import annotations

from functools import lru_cache
from typing import Mapping, Sequence

from corpus import tags

EXAMPLES = 3  # places a kind names in the result


@lru_cache(maxsize=1)
def _styles() -> Mapping[str, frozenset[str]]:
    """Style tags read from photos (corpus.index); {} without an index."""
    return tags.load_styles()


def kinds_of(ids: Sequence[str], records: Mapping[str, dict], styles: Mapping[str, frozenset[str]] | None = None) -> dict | None:
    """ids: the list's places, best first. -> {axis, total, groups[{id, label, count, places[{id}]}], other} or None when the
    list is short or no axis splits it well. records: place id -> serving record."""
    styles = _styles() if styles is None else styles
    placed = [tags.of_record(records[p], styles.get(p, ())) for p in ids if p in records]
    split = tags.split(placed)
    if split is None:
        return None
    return {"axis": split.axis, "total": split.total, "other": split.total - split.covered,
            "groups": [{"id": s.id, "label": s.label, "count": s.count, "places": [{"id": p} for p in s.place_ids[:EXAMPLES]]}
                       for s in split.subtags]}
