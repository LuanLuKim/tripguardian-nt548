"""Nhịp Đà Lạt (docs/CORPUS.md §Nhịp): dated signals from data the crawls already hold -> trend items -> a bulletin.

Offline `build` writes data/<city>/pulse/{generated_at}.json + latest.json (CLI `python -m corpus pulse --city dalat`,
every 24 h); online only reads. Text comes from fixed templates over the items' fields; no model writes it. Public API:

    build(city, now=None, root=None) -> snapshot       (offline: read signals, compute, write)
    tag_trends(city, now=None, root=None) -> {as_of, window_days, stale, tags[]} | None   (home page topics)
    load(city, root=None) -> snapshot | None           (None: the job never ran)
    bulletin(city, now=None, root=None) -> {city, generated_at, stale, sections[{kind, title, items[]}]} | None
    hot(city, now=None, root=None) -> {fid: {label, newest, videos, authors, window_days, as_of}}   (display only)
    trends(city, kind=None, month=None, limit=6, now=None, root=None) -> {as_of, stale, items[], note?} | None
"""

from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path

import yaml

from . import compute, render, signals, store
from .. import tags

ROOT = Path(__file__).resolve().parents[3]


@cache
def config() -> dict:
    return yaml.safe_load((ROOT / "config" / "pulse.yaml").read_text(encoding="utf-8"))


def _city_name(city: str) -> str:
    cities = yaml.safe_load((ROOT / "config" / "cities.yaml").read_text(encoding="utf-8"))
    return cities.get(city, {}).get("name", "")


def build(city: str, now: datetime | None = None, root: Path | None = None) -> dict:
    cfg = config()
    now = now or datetime.now(UTC)
    sig = signals.load(city, cfg["tz_offset_h"], root)
    items = compute.build(sig, cfg, now.date(), previous=store.load(city, root), city_name=_city_name(city))
    snapshot = {"city": city, "generated_at": now.isoformat(timespec="seconds"), "day": now.date().isoformat(),
                "counts": {k: sum(1 for i in items if i["kind"] == k) for k in compute.KINDS},
                "inputs": {"places": len(sig["places"]), "places_with_videos": len(sig["videos"]),
                           "videos": sum(len(v) for v in sig["videos"].values()), "places_with_reviews": len(sig["reviews"]),
                           "claims": len(sig["claims"])},
                "items": items,
                # tags ranked by the TikTok clips of the last 30 days at the places that carry them (corpus.tags.trending)
                "tags": tags.trending(signals.tagged(root or signals.data_root()), sig["videos"], now.date())}
    store.write(city, snapshot, cfg["keep_snapshots"], root)
    return snapshot


def load(city: str, root: Path | None = None) -> dict | None:
    return store.load(city, root)


def _age_days(snapshot: dict, now: datetime | None) -> int:
    return ((now or datetime.now(UTC)).date() - date.fromisoformat(snapshot["day"])).days


def bulletin(city: str, now: datetime | None = None, root: Path | None = None) -> dict | None:
    snap = store.load(city, root)
    if snap is None:
        return None
    sections = []
    for kind, title in render.SECTIONS:
        items = [render.item(i) for i in snap["items"] if i["kind"] == kind]
        if items:
            sections.append({"kind": kind, "title": title, "items": items})
    return {"city": city, "generated_at": snap["generated_at"], "day": snap["day"],
            "stale": _age_days(snap, now) > config()["stale_after_days"], "sections": sections}


def hot(city: str, now: datetime | None = None, root: Path | None = None) -> dict:
    """Places with the "đang hot" label, for display only (a card shows it; nothing ranks or filters by it)."""
    snap = store.load(city, root)
    if snap is None or _age_days(snap, now) > config()["hide_after_days"]:
        return {}
    return {i["subject"]["id"]: {"label": "Đang hot", "newest": i["signals"]["newest"], "videos": i["signals"]["videos"],
                                 "authors": i["signals"]["authors"], "window_days": i["signals"]["window_days"], "as_of": snap["day"]}
            for i in snap["items"] if i["kind"] == "hot"}


def trends(city: str, kind: str | None = None, month: int | None = None, limit: int = 6, now: datetime | None = None,
           root: Path | None = None) -> dict | None:
    """What the assistant reads for "đang có gì hot": items with their words, dates and sources, `limit` per kind."""
    snap = store.load(city, root)
    if snap is None:
        return None
    out, seen = [], {}
    for i in snap["items"]:
        if kind and i["kind"] != kind:
            continue
        if month is not None and i["kind"] in ("season", "event") and month not in i["signals"].get("months", [month]):
            continue
        seen[i["kind"]] = seen.get(i["kind"], 0) + 1
        if seen[i["kind"]] <= limit:
            r = render.item(i)
            text = f"{r['text']} · {r['summary']}" if r.get("summary") else r["text"]  # a dated event says what happens
            out.append({"kind": i["kind"], "name": r["title"], "place_id": r["place_id"], "text": text,
                        "sources": [s for s in r["sources"] if s.get("url")][:3],
                        # the chat's trends block shows these (a dated event's own words, picture and days)
                        **{k: r[k] for k in ("summary", "image") if r.get(k)},
                        **({"days": r["signal"], "on": r["on"]} if i["signals"].get("source") == "web" else {})})
    res = {"as_of": snap["day"], "stale": _age_days(snap, now) > config()["stale_after_days"], "items": out}
    if month is not None and month != int(snap["day"][5:7]):
        res["note"] = f"Nhịp đo cho tháng {int(snap['day'][5:7])}; mùa và sự kiện được lọc theo tháng {month}, các mục còn lại là hiện tại."
    return res


def tag_trends(city: str, now: datetime | None = None, root: Path | None = None) -> dict | None:
    """The tags people post about most in the last 30 days (home page): {as_of, window_days, stale, tags[]}; None when the
    job never wrote tags or they are older than `hide_after_days` (the page then shows its fixed topics)."""
    snap = store.load(city, root)
    if snap is None or not snap.get("tags") or _age_days(snap, now) > config()["hide_after_days"]:
        return None
    return {"as_of": snap["day"], "window_days": tags.config()["trend"]["window_days"],
            "stale": _age_days(snap, now) > config()["stale_after_days"], "tags": snap["tags"]}


def run(city: str) -> None:
    snap = build(city)
    print(f"pulse {city}: {snap['counts']} -> {store.pulse_dir(city) / 'latest.json'}")


__all__ = ["build", "bulletin", "hot", "load", "run", "tag_trends", "trends"]
