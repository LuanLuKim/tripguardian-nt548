"""Crawled flights for online use: the newest Google Flights search per (src, dst, day) from data/gflights/<city>/ ->
data/serving/flight_offers/<city>.json. python -m corpus flight_offers --city dalat

Only searches that showed flights are published: a route and day with no published search is unknown, never "no flight".
"""

import json
from datetime import UTC, datetime

from ..crawl.common.files import data_dir, now, write_json
from ..crawl.gflights import latest


def path(city: str):
    return data_dir() / "serving" / "flight_offers" / f"{city}.json"


def publish(city: str) -> dict:
    items = [latest(city)[k] for k in sorted(latest(city))]
    out = {"at": now(), "city": city, "stats": {"searches": len(items), "offers": sum(len(i["offers"]) for i in items)},
           "items": items}
    write_json(path(city), out)
    return out


def load(city: str, max_age_h: float | None = None) -> dict[tuple[str, str, str], dict]:
    """(src, dst, day) -> the published search {src, dst, day, observed_at, url, offers}; empty without a published file.
    max_age_h drops older searches."""
    p = path(city)
    if not p.exists():
        return {}
    items = json.loads(p.read_text(encoding="utf-8"))["items"]
    if max_age_h is not None:
        edge = datetime.now(UTC).timestamp() - max_age_h * 3600
        items = [i for i in items if datetime.fromisoformat(i["observed_at"]).timestamp() >= edge]
    return {(i["src"], i["dst"], i["day"]): i for i in items}
