"""Tags ranked by recent social signal: distinct TikTok clips (and posters) in the last `window_days` at the places that
carry the tag. It counts people posting about the places, not users of this app. Pure: the caller reads the clips.

Rank = clips / sqrt(places that carry the tag): a tag held by a third of the city would win on size alone, so volume is
tempered by size. The numbers shown stay the raw counts. A tag held by more than `max_share` of all places is no topic."""

from __future__ import annotations

import math
from collections import Counter
from datetime import date, timedelta
from typing import Mapping, Sequence

from . import vocab
from .vocab import PlaceTags


def eligible(axis: str, key: str) -> bool:
    """Whether a tag may be a topic on the home page (config/tags.yaml `home: false` on a feature or a dish kind)."""
    entry = (vocab.config()["features"] if axis == "experience" else vocab.dish_kinds() if axis == "dish" else {}).get(key) or {}
    return entry.get("home", True) is not False


def trending(places: Sequence[PlaceTags], videos: Mapping[str, Sequence[dict]], today: date,
             cfg: dict | None = None) -> list[dict]:
    """Tags with enough places, clips and posters, best rank first (see the module doc). videos: place id -> [{id, author, date "YYYY-MM-DD"}].
    Each item: {ref, axis, key, label, places, clips, authors, newest, top} where top = the place ids with the most clips."""
    cfg = cfg or vocab.config()["trend"]
    since = (today - timedelta(days=cfg["window_days"])).isoformat()
    recent = {pid: [v for v in vs if v.get("date") and since <= v["date"] <= today.isoformat()] for pid, vs in videos.items()}
    out = []
    for axis in vocab.AXES:
        keys: dict[str, list[PlaceTags]] = {}
        for p in places:
            for k in p.keys(axis):
                if (not vocab.enabled() or vocab.known(axis, k)) and eligible(axis, k):
                    keys.setdefault(k, []).append(p)
        for key, group in keys.items():
            if len(group) < cfg["min_places"] or len(group) > cfg["max_share"] * len(places):
                continue
            clips = {v["id"]: v for p in group for v in recent.get(p.id, ())}
            authors = {v["author"] for v in clips.values() if v.get("author")}
            if len(clips) < cfg["min_clips"] or len(authors) < cfg["min_authors"]:
                continue
            per_place = Counter({p.id: len({v["id"] for v in recent.get(p.id, ())}) for p in group})
            top = [pid for pid, n in sorted(per_place.items(), key=lambda kv: (-kv[1], kv[0])) if n][:cfg["top_places"]]
            out.append({"ref": vocab.ref(axis, key), "axis": axis, "key": key, "label": vocab.label(axis, key),
                        "places": len(group), "clips": len(clips), "authors": len(authors),
                        "newest": max(v["date"] for v in clips.values()), "top": top})
    out.sort(key=lambda t: (-t["clips"] / math.sqrt(t["places"]), -t["clips"], t["ref"]))
    kept, used = [], Counter()
    for t in out:
        if used[t["axis"]] < cfg["max_per_axis"].get(t["axis"], 2):
            kept.append(t)
            used[t["axis"]] += 1
    return kept[:cfg["max_items"]]
