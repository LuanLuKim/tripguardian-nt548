"""Reads the dated signals the crawls already left under data/ (docs/CORPUS.md §Nhịp). I/O only; compute.py decides.

Nothing here crawls: a source that is missing gives an empty signal, never an invented one."""

import json
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from .. import data_root
from ..views import calendar_days

SERVING = ("serving", "places.json")
CLOSED = "Bị đóng vĩnh viễn"


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _safe(fid: str) -> str:
    return fid.replace(":", "_")


def served(root: Path) -> dict:
    """{fid: {name, category, group, area, rating_direction}} of the served corpus (data/serving/places.json)."""
    doc = _read(root.joinpath(*SERVING)) or {}
    return {r["id"]: {"name": (r.get("identity") or {}).get("name") or "", "category": (r.get("identity") or {}).get("category"),
                      "group": (r.get("identity") or {}).get("category_group"),
                      "area": (r.get("identity") or {}).get("area"),
                      "rating_direction": ((r.get("provenance") or {}).get("rating_trend") or {}).get("direction")}
            for r in doc.get("records", []) if (r.get("identity") or {}).get("name")}


def tagged(root: Path) -> list:
    """corpus.tags.PlaceTags of every served place (data/serving/places.json + the current semantic index' style tags)."""
    from ..tags import load_styles, of_record
    doc = _read(root.joinpath(*SERVING)) or {}
    styles = load_styles(root)
    return [of_record(r, styles.get(r["id"], ())) for r in doc.get("records", []) if (r.get("identity") or {}).get("name")]


def tiktok_videos(root: Path, fids: set, tz_h: int) -> dict:
    """{fid: [{id, url, author, date, text}]} from data/tiktok/poi_crawl and the nightly re-listing poi_recent
    (created_at = the video's own epoch); a video both list counts once."""
    tz = timezone(timedelta(hours=tz_h))
    out: dict[str, dict] = {}
    for sub in ("poi_crawl", "poi_recent"):
        for f in (root / "tiktok" / sub).glob("*.json"):
            d = _read(f)
            if not d or d.get("fid") not in fids:
                continue
            for v in d.get("videos", []):
                if v.get("video_id") and v.get("created_at") and v.get("author_id"):
                    out.setdefault(d["fid"], {})[str(v["video_id"])] = {
                        "id": str(v["video_id"]), "url": v.get("url") or "", "author": v.get("author_id") or "",
                        "date": datetime.fromtimestamp(v["created_at"], UTC).astimezone(tz).date().isoformat(),
                        "text": v.get("desc") or ""}
    return {fid: list(rows.values()) for fid, rows in out.items()}


def maps_recent(root: Path, fid: str) -> dict | None:
    """The place's newest reviews from `gmaps refresh` (data/gmaps/reviews_recent/), None when never refreshed."""
    return _read(root / "gmaps" / "reviews_recent" / f"{_safe(fid)}.json")


def maps_reviews(root: Path, fids: set) -> dict:
    """{fid: [{date, author, stars}]} from data/gmaps/observations (the date is the crawl's reading of 'x trước') and
    the reviews `gmaps refresh` read since; one row per author (Maps keeps one review per person), the later reading
    winning."""
    out = {}
    for fid in fids:
        d = _read(root / "gmaps" / "observations" / f"{_safe(fid)}.json")
        rows = {r["author"]: {"date": r["observed_at"][:10], "author": r["author"], "stars": r["stars"]}
                for r in (d or {}).get("ratings", []) if r.get("observed_at") and r.get("author") and r.get("stars") is not None}
        recent = maps_recent(root, fid) or {}
        for r in recent.get("reviews") or ():
            day, s = observed_at(r.get("published_text"), recent["at"]), stars(r.get("rating"))
            if day and s and r.get("author_hash"):
                rows[r["author_hash"]] = {"date": day, "author": r["author_hash"], "stars": s}
        if rows:
            out[fid] = list(rows.values())
    return out


def maps_places(root: Path, fids: set, tz_h: int) -> tuple[dict, dict]:
    """(review_totals {fid: n} for served places, status {fid: {name, status, as_of, reviews}} of every permanently
    closed place Maps lists) from data/gmaps/places/*/place.json; as_of = the day that file was written."""
    totals, status = {}, {}
    tz = timezone(timedelta(hours=tz_h))
    for f in (root / "gmaps" / "places").glob("*/place.json"):
        d = _read(f)
        if not d or not d.get("fid"):
            continue
        recent = maps_recent(root, d["fid"]) or {}
        now_count = _count(recent.get("review_count"))  # what Maps shows at the last refresh, when there was one
        if d["fid"] in fids and (now_count or isinstance(d.get("reviews"), int)):
            totals[d["fid"]] = now_count or d["reviews"]
        if (recent.get("status") or d.get("status")) == CLOSED:
            as_of = (recent["at"][:10] if recent.get("status") == CLOSED else
                     datetime.fromtimestamp(f.stat().st_mtime, UTC).astimezone(tz).date().isoformat())
            status[d["fid"]] = {"name": d.get("name") or "", "status": CLOSED, "as_of": as_of,
                                "reviews": now_count or d.get("reviews") or 0}
    return totals, status


_AGE = re.compile(r"(một|\d+) (phút|giờ|ngày|tuần|tháng|năm) trước")   # as corpus.observe.gmaps.prep, which pulls the
_DAYS = {"phút": 0, "giờ": 0, "ngày": 1, "tuần": 7, "tháng": 30, "năm": 365}  # Extractor in: online reads this module


def observed_at(published_text: str | None, fetched_at: str) -> str | None:
    """The day Maps' "3 tuần trước" means, read at fetched_at."""
    m = _AGE.search(published_text or "")
    if not m:
        return None
    days = (1 if m.group(1) == "một" else int(m.group(1))) * _DAYS[m.group(2)]
    return (datetime.fromisoformat(fetched_at).date() - timedelta(days=days)).isoformat()


def stars(rating: str | None) -> int | None:
    m = re.match(r"\s*([1-5])", rating or "")
    return int(m.group(1)) if m else None


def _count(text) -> int | None:
    """Number in a Maps label ("1.701 bài đánh giá" -> 1701)."""
    digits = re.sub(r"\D", "", str(text or "").split(" ")[0])
    return int(digits) if digits else None


def web_domains(root: Path, city: str, fids: set) -> dict:
    """{fid: [domain]} of the sites whose Documents hold a claim about the place (data/<city>/local/poi_claims.json)."""
    doc = _read(root / city / "local" / "poi_claims.json") or {}
    out: dict = {}
    for c in doc.get("claims", []):
        if c.get("subject_id") in fids:
            out.setdefault(c["subject_id"], set()).update(e["domain"] for e in c.get("evidence", []) if e.get("domain"))
    return {k: sorted(v) for k, v in out.items()}


def local_claims(root: Path, city: str) -> list:
    return (_read(root / city / "local" / "local_claims.json") or {}).get("claims", [])


def holidays(city: str) -> list:
    return [{"date": d["date"], "name": d["holiday"]} for d in (calendar_days(city) or []) if d.get("holiday")]


def web_documents(root: Path, city: str) -> dict:
    """{doc_id: the page's text} of the web Documents the local claims were read from (data/web/<city>/documents/):
    where a season is seen is in the page around its name, not in the claim's one-sentence quote."""
    out = {}
    for path in sorted((root / "web" / city / "documents").glob("*.json")):
        d = _read(path) or {}
        if d.get("doc_id"):
            out[d["doc_id"]] = " ".join(f"{s.get('heading') or ''} {s.get('text') or ''}" for s in d.get("sections") or ()
                                        if isinstance(s, dict))
    return out


def web_events(root: Path, city: str) -> dict | None:
    """The newest dated-events snapshot (data/<city>/events/latest.json, corpus.events), or None when never built."""
    return _read(root / city / "events" / "latest.json")


def load(city: str, tz_h: int, root: Path | None = None) -> dict:
    root = root or data_root()
    places = served(root)
    fids = set(places)
    totals, status = maps_places(root, fids, tz_h)
    return {"places": places, "videos": tiktok_videos(root, fids, tz_h), "reviews": maps_reviews(root, fids),
            "review_totals": totals, "web": web_domains(root, city, fids), "status": status,
            "claims": local_claims(root, city), "holidays": holidays(city), "events": web_events(root, city),
            "documents": web_documents(root, city)}
