"""One distinct cover photo for each card of a level (docs/TRIP_UNDERSTANDING.md §19): several tags hold the same big
places, so taking each tag's best place gives the same picture on every card. Pure: no corpus, no model."""

from __future__ import annotations

from typing import Callable, Sequence

POOL = 24  # places of a group looked at for its cover (best first)


def assign(groups: Sequence[Sequence[str]], photo_of: Callable[[str], str | None], pool: int = POOL,
           fits: Sequence[Callable[[str], str | None] | None] | None = None) -> list[str | None]:
    """groups: the place ids of each card, best first. -> one photo url per group (None when no place of it has a photo).
    fits: per group, the photo of a place that shows what the card is about (a card "Thiên nhiên" wants a view, not the
    dishes of a restaurant with a view); every such photo is tried before any plain one.
    Greedy: the group with the fewest candidates picks first, taking its best place whose photo no card has yet; a group
    whose places are all used takes its best photo again (the only repeat that cannot be avoided)."""
    def choices(i: int, ids: Sequence[str]) -> list[tuple[str, str]]:
        fit = fits[i] if fits else None
        fitting = [(pid, url) for pid in ids[:pool] if fit and (url := fit(pid))]
        return fitting + [(pid, url) for pid in ids[:pool] if (url := photo_of(pid))]

    options = [choices(i, ids) for i, ids in enumerate(groups)]
    out: list[str | None] = [None] * len(groups)
    used_places: set[str] = set()
    used_urls: set[str] = set()
    for i in sorted(range(len(groups)), key=lambda i: (len(options[i]), i)):
        fresh = next(((pid, url) for pid, url in options[i] if pid not in used_places and url not in used_urls), None)
        got = fresh or (options[i][0] if options[i] else None)
        if got is not None:
            out[i] = got[1]
            used_places.add(got[0])
            used_urls.add(got[1])
    return out
