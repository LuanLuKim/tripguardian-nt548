"""Google search per listed place, for the facts a place's own search panel and result snippets carry: opening hours and
the entry price (docs/CORPUS.md §Nguồn, gsearch places).

Three query kinds, each recorded by gsearch.crawl like any other query (results.jsonl + raw html):
  panel  "<name> <city>"                  the knowledge panel: hours, "Vé vào cửa" prices
  fee    "giá vé <name> <city> 2026"      result snippets that name a ticket price (places that sell entry only)
  hours  "<name> <city> giờ mở cửa"       result snippets that name hours (places whose panel and Maps give none)
A query already recorded (younger than MAX_AGE_DAYS) is not asked again, so a stopped run goes on where it was.
"""

import json
import time

from ...categories import group
from ..common.files import data_dir, load_config, safe_name
from . import crawl as _crawl

KINDS = ("panel", "fee", "hours")
# groups whose places sell entry tickets (same list as observe.official.TICKET_GROUPS, kept here to stay independent)
TICKET_GROUPS = {"nature", "garden_farm", "attraction", "amusement", "museum", "religious", "camping", "other", "golf"}
# groups whose "opening hours" mean a visit window; lodging has a reception, not a visit window
NO_HOURS_GROUPS = {"stay"}
CHUNK = 30  # queries per browser session; the stop file is looked at between two chunks
STOP_FILE = "gsearch_places.stop"


def query_for(kind: str, name: str, city_name: str) -> str:
    where = "" if city_name.casefold() in name.casefold() else f" {city_name}"
    if kind == "panel":
        return f"{name}{where}"
    if kind == "fee":
        return f"giá vé {name}{where} 2026"
    if kind == "hours":
        return f"{name}{where} giờ mở cửa"
    raise ValueError(kind)


def _served() -> set[str] | None:
    """Ids of the places the live serving file holds (a place the corpus never serves is not worth a query); None when
    the file is missing."""
    try:
        rows = json.loads((data_dir() / "serving" / "places.json").read_text(encoding="utf-8"))["records"]
    except (OSError, ValueError, KeyError):
        return None
    return {r["id"] for r in rows}


def places(city: str) -> list[dict]:
    """[{fid, name, group, website, hours}] of the city's listed experience places, Maps' own record."""
    root = data_dir() / "gmaps"
    items = json.loads((root / "list" / f"{city}.json").read_text(encoding="utf-8"))["items"]
    served = _served()
    out = []
    for it in items:
        if served is not None and it["fid"] not in served:
            continue
        f = root / "places" / safe_name(it["fid"]) / "place.json"
        if not f.exists():
            continue
        p = json.loads(f.read_text(encoding="utf-8"))
        if not p.get("name"):
            continue
        out.append({"fid": it["fid"], "name": p["name"], "group": group(p.get("category"), p.get("name"))["id"],
                    "website": p.get("website"), "hours": bool(p.get("hours"))})
    out.sort(key=lambda p: p["group"] not in TICKET_GROUPS)  # places that sell entry first (stable)
    return out


def wanted(kind: str, p: dict) -> bool:
    if kind == "panel":
        return p["group"] in TICKET_GROUPS or (not p["hours"] and p["group"] not in NO_HOURS_GROUPS)
    if kind == "fee":
        return p["group"] in TICKET_GROUPS
    return not p["hours"] and p["group"] not in NO_HOURS_GROUPS


def queries(city: str, kind: str, only_missing_hours: dict[str, bool] | None = None) -> list[str]:
    """The queries of one kind, in list order. For `hours`, only_missing_hours {fid: True} names the places whose panel
    gave no hours either (the caller read the panels); without it every place Maps gives no hours for."""
    city_name, _ = load_config(city)
    out = []
    for p in places(city):
        if not wanted(kind, p):
            continue
        if kind == "hours" and only_missing_hours is not None and not only_missing_hours.get(p["fid"]):
            continue
        out.append(query_for(kind, p["name"], city_name))
    return list(dict.fromkeys(out))


def run(city: str, kind: str, limit: int | None = None, headed: bool = False, account: str = _crawl.ACCOUNT,
        only_missing_hours: dict[str, bool] | None = None) -> dict:
    """Asks the queries of one kind in chunks. Stops after a chunk when data/gsearch/<city>/STOP exists."""
    import asyncio
    todo = queries(city, kind, only_missing_hours)
    done = _crawl.load(city)
    todo = [q for q in todo if (_crawl._key(q), 1) not in done][:limit]
    print(f"gsearch places {city} {kind}: {len(todo)} queries to ask", flush=True)
    total = {"fetched": 0, "cached": 0, "errors": 0}
    stop = _crawl.city_dir(city) / "STOP"
    for i in range(0, len(todo), CHUNK):
        if stop.exists():
            print(f"gsearch places: {stop} exists, stopping", flush=True)
            break
        t0 = time.monotonic()
        stats = asyncio.run(_crawl.crawl(todo[i:i + CHUNK], city, 1, headed, account))
        for k, v in stats.items():
            total[k] += v
        print(f"gsearch places {kind}: {i + len(todo[i:i + CHUNK])}/{len(todo)} {stats} {time.monotonic() - t0:.0f}s", flush=True)
    return total
