"""Clips the chat shows on its clip stage: each place's verified TikTok clips (crawl/tiktok/clips) with what the online
assistant needs to pick them for an ask -> data/serving/clips/<city>.json. python -m corpus clips --city dalat

A clip row: video_id, url, author, caption (at most CAPTION_CHARS), posted (YYYY-MM-DD, None when TikTok gave no time),
plays, score (crawl/tiktok/poi_crawl.score: how surely it is this place) and `text`: the words a request is matched
against (caption, the spoken words unless the transcript check found none or rejected them, and what video_observe saw
in it: feature values and the words it read them from). Nothing is guessed: a clip with no words has an empty text.
Only the clips the clips phase kept are published, in its order. Online reads it with `load` (cached by file time).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ..crawl.common.files import data_dir, now, write_json

CAPTION_CHARS = 220
TEXT_CHARS = 1500  # the words of one clip that requests are matched against
SPOKEN = frozenset({"good", "partial"})  # transcript checks whose words are kept (no_speech / unusable are not)

_cache: dict[str, tuple[float, dict]] = {}


def path(city: str) -> Path:
    return data_dir() / "serving" / "clips" / f"{city}.json"


def _posted(created_at) -> str | None:
    try:
        return datetime.fromtimestamp(int(created_at), UTC).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _seen(fid: str) -> dict[str, list[str]]:
    """video_id -> what video_observe read in it for this place: "feature value" and the words it read them from."""
    p = data_dir() / "tiktok" / "observations" / f"{fid.replace(':', '_')}.json"
    if not p.exists():
        return {}
    out: dict[str, list[str]] = {}
    for o in json.loads(p.read_text(encoding="utf-8")).get("observations") or ():
        vid = str(o.get("source_id") or "")
        if vid:
            words = (f"{o.get('feature', '')} {o.get('value', '')}".replace("_", " "), (o.get("span") or {}).get("quote") or "")
            out.setdefault(vid, []).extend(w.strip() for w in words if w and w.strip())
    return out


def _row(fid: str, clip: dict, seen: dict[str, list[str]]) -> dict:
    vid = clip["video_id"]
    v = {}
    f = data_dir() / "tiktok" / "videos" / vid / "video.json"
    if f.exists():
        v = json.loads(f.read_text(encoding="utf-8"))
    caption = " ".join(str(v.get("caption") or clip.get("desc") or "").split())
    t = v.get("transcript") or {}
    spoken = t.get("text") if (t.get("check") or {}).get("quality") in SPOKEN else ""
    stats = v.get("stats") or {}
    text = " · ".join(w for w in (caption, spoken or "", *dict.fromkeys(seen.get(vid, ()))) if w)
    return {"video_id": vid, "url": clip["url"], "author": clip.get("author_id"), "caption": caption[:CAPTION_CHARS],
            "posted": _posted(v.get("created_at")), "plays": stats.get("playCount"), "score": clip.get("score"),
            "text": text[:TEXT_CHARS]}


def publish(city: str) -> dict:
    """data/tiktok/clips/<city>.json + each clip's video.json and the place's observations -> the serving file."""
    src = data_dir() / "tiktok" / "clips" / f"{city}.json"
    places = json.loads(src.read_text(encoding="utf-8"))["places"] if src.exists() else {}
    out = {}
    for fid, clips in places.items():
        seen = _seen(fid)
        out[fid] = [_row(fid, c, seen) for c in clips]
    stats = {"places": len(out), "clips": sum(map(len, out.values())),
             "with_words": sum(1 for rows in out.values() for r in rows if r["text"])}
    write_json(path(city), {"at": now(), "city": city, "stats": stats, "places": out})
    return stats


def load(city: str) -> dict[str, list[dict]]:
    """fid -> its published clips, best first; empty without a published file. Read again when the file changes."""
    p = path(city)
    try:
        at = p.stat().st_mtime
    except OSError:
        return {}
    hit = _cache.get(city)
    if hit is None or hit[0] != at:
        hit = (at, json.loads(p.read_text(encoding="utf-8"))["places"])
        _cache[city] = hit
    return hit[1]
