"""Dated lodging prices for online budget checks: the newest observation per (fid, stay date, nights) from the price
crawls -> data/serving/stay_prices/<city>.json. python -m corpus stay_prices --city dalat

The main source (Google Travel) wins; another source answers only for a stay the main one saw no offer for, and the
other sources' prices ride along as `cross_check`. A stay no source priced is not published: unknown stays unknown.
"""

import json
from datetime import UTC, date, datetime

from ..crawl.common.files import data_dir, now, write_json
from ..crawl.common.lodging import latest

SOURCES = ("gtravel", "tripcom")  # preference order
KEEP = ("fid", "stay_date", "nights", "adults", "price_total_vnd", "price_night_vnd", "currency", "available",
        "observed_at", "source", "url")


def path(city: str):
    return data_dir() / "serving" / "stay_prices" / f"{city}.json"


def publish(city: str, today: date | None = None) -> dict:
    """Newest priced observation per (fid, stay date, nights), without stays that have already started."""
    today = (today or date.today()).isoformat()
    per_source = {s: latest(s, city) for s in SOURCES}
    items = []
    for key in sorted({k for rows in per_source.values() for k in rows if k[1] >= today}):
        priced = [(s, per_source[s][key]) for s in SOURCES
                  if key in per_source[s] and per_source[s][key].get("price_total_vnd")]
        if not priced:
            continue
        source, row = priced[0]
        item = {k: row.get(k) for k in KEEP}
        item["cross_check"] = {s: {k: r[k] for k in ("price_total_vnd", "price_night_vnd", "observed_at", "url")}
                               for s, r in priced[1:]}
        items.append(item)
    out = {"at": now(), "city": city, "stats": {"priced": len(items), "fids": len({i["fid"] for i in items})},
           "items": items}
    write_json(path(city), out)
    return out


def load(city: str, max_age_h: float | None = None) -> dict[tuple[str, str, int], dict]:
    """(fid, stay_date, nights) -> the published price; empty without a published file. max_age_h drops older rows."""
    p = path(city)
    if not p.exists():
        return {}
    items = json.loads(p.read_text(encoding="utf-8"))["items"]
    if max_age_h is not None:
        edge = datetime.now(UTC).timestamp() - max_age_h * 3600
        items = [i for i in items if datetime.fromisoformat(i["observed_at"]).timestamp() >= edge]
    return {(i["fid"], i["stay_date"], i["nights"]): i for i in items}
