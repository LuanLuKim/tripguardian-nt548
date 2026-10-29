"""Reads the dated signals the crawls already left under data/ (docs/CORPUS.md §Nhịp). I/O only; compute.py decides.

Nothing here crawls: a source that is missing gives an empty signal, never an invented one."""

import json
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
    """{fid: {name, category, area, rating_direction}} of the served corpus (data/serving/places.json)."""
    doc = _read(root.joinpath(*SERVING)) or {}
    return {r["id"]: {"name": (r.get("identity") or {}).get("name") or "", "category": (r.get("identity") or {}).get("category"),
                      "area": (r.get("identity") or {}).get("area"),
                      "rating_direction": ((r.get("provenance") or {}).get("rating_trend") or {}).get("direction")}
            for r in doc.get("records", []) if (r.get("identity") or {}).get("name")}


def tiktok_videos(root: Path, fids: set, tz_h: int) -> dict:
    """{fid: [{id, url, author, date, text}]} from data/tiktok/poi_crawl (created_at = the video's own epoch)."""
    tz = timezone(timedelta(hours=tz_h))
    out = {}
    for f in (root / "tiktok" / "poi_crawl").glob("*.json"):
        d = _read(f)
        if not d or d.get("fid") not in fids:
            continue
        rows = [{"id": str(v["video_id"]), "url": v.get("url") or "", "author": v.get("author_id") or "",
                 "date": datetime.fromtimestamp(v["created_at"], UTC).astimezone(tz).date().isoformat(), "text": v.get("desc") or ""}
                for v in d.get("videos", []) if v.get("video_id") and v.get("created_at") and v.get("author_id")]
        if rows:
            out[d["fid"]] = rows
    return out


def maps_reviews(root: Path, fids: set) -> dict:
    """{fid: [{date, author, stars}]} from data/gmaps/observations (the date is the crawl's reading of 'x trước')."""
    out = {}
    for fid in fids:
        d = _read(root / "gmaps" / "observations" / f"{_safe(fid)}.json")
        rows = [{"date": r["observed_at"][:10], "author": r["author"], "stars": r["stars"]}
                for r in (d or {}).get("ratings", []) if r.get("observed_at") and r.get("author") and r.get("stars") is not None]
        if rows:
            out[fid] = rows
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
        if d["fid"] in fids and isinstance(d.get("reviews"), int):
            totals[d["fid"]] = d["reviews"]
        if d.get("status") == CLOSED:
            as_of = datetime.fromtimestamp(f.stat().st_mtime, UTC).astimezone(tz).date().isoformat()
            status[d["fid"]] = {"name": d.get("name") or "", "status": CLOSED, "as_of": as_of, "reviews": d.get("reviews") or 0}
    return totals, status


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


def load(city: str, tz_h: int, root: Path | None = None) -> dict:
    root = root or data_root()
    places = served(root)
    fids = set(places)
    totals, status = maps_places(root, fids, tz_h)
    return {"places": places, "videos": tiktok_videos(root, fids, tz_h), "reviews": maps_reviews(root, fids),
            "review_totals": totals, "web": web_domains(root, city, fids), "status": status,
            "claims": local_claims(root, city), "holidays": holidays(city)}
