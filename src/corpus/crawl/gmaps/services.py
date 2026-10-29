"""Utilities and rental / tour places for the assistant tools (config/queries.yaml services). Three phases:

svc_search  word x map tile -> data/gmaps/search/<city>_svc/<word>.jsonl (search file format of search.py)
svc_list    those files -> data/gmaps/list/<city>_svc.json: in-area places, one row each, tagged with their group
svc_place   list -> data/gmaps/services/places/<fid_dir>.json: phone, website, hours, address (no reviews)

Boundary: these places are read only by assistant tools (`load`). They are never Decision candidates and never Planning
stops: nothing is written to data/gmaps/places, and files.listed() (the inventory observe / aggregate / serving use)
does not include the services list.
"""

import asyncio
import json
from functools import cache
from pathlib import Path

import yaml

from ..common.browser import LoginRequired, open_profile, pause
from ..common.files import ROOT, append_jsonl, data_dir, load_config, log_error, now, safe_name, slug, write_json
from ..common.throttle import Throttle
from .crawl import parse_place
from .listing import KEYS, _same_place, _scored
from .page import CaptchaBlocked, check_signed_in, ensure_login, open_page
from .search import done_tiles, search
from .tiles import in_area, root_tiles

SVC = "_svc"
ATTEMPTS = 3
HOURS_BUTTON = '[role="button"][jsaction*="openhours"][jsaction*="dropdown"]'


@cache
def config() -> dict:
    return yaml.safe_load((ROOT / "config" / "queries.yaml").read_text(encoding="utf-8"))["services"]


def group_of(word: str, groups: dict) -> str | None:
    return next((g for g, words in groups.items() if word in words), None)


def word_of(query: str, words: list[str]) -> str:
    """The config word a stored query searched: queries are "<word> <city name>" ("thuê xe máy Đà Lạt"); an unknown
    query is returned unchanged."""
    return next((w for w in words if query == w or query.startswith(w + " ")), query)


def build(search_dir: Path, area, groups: dict, same_name_m: float = 0) -> dict:
    """The services list: every in-area place any search of `search_dir` met, tagged with the group of the word that
    found it. No review minimum: an ATM or a pump has none."""
    best: dict[str, dict] = {}
    found: dict[str, set[str]] = {}
    raw = outside = 0
    for f in sorted(search_dir.glob("*.jsonl")) if search_dir.exists() else []:
        for line in f.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if "end" not in rec or not all("rating" in r for r in rec["items"]):
                continue
            group = group_of(rec.get("word", rec["query"]), groups)
            if group is None:
                continue
            for r in rec["items"]:
                raw += 1
                if not in_area(r.get("lat"), r.get("lng"), area):
                    outside += 1
                    continue
                found.setdefault(r["fid"], set()).add(rec["query"])
                if r["fid"] not in best or (r.get("reviews") or 0) > (best[r["fid"]].get("reviews") or 0):
                    best[r["fid"]] = {**{k: r.get(k) for k in KEYS}, "group": group}
    copies = _same_place(list(best.values()), None, same_name_m) if same_name_m else {}
    for fid, kept in copies.items():
        if best[fid]["group"] == kept["group"]:
            found[kept["fid"]] |= found.pop(fid)
            best.pop(fid)
    rows = _scored([dict(r) for r in best.values()])
    items = [{**r, "queries": sorted(found[r["fid"]])} for r in rows]
    by_group: dict[str, int] = {}
    for r in items:
        by_group[r["group"]] = by_group.get(r["group"], 0) + 1
    return {"at": now(), "stats": {"raw": raw, "outside_area": outside, "same_place": len(copies), "places": len(items),
                                   "by_group": by_group}, "items": items}


async def run_search(city: str, headed: bool = False, limit: int | None = None, shard=None,
                     profile_name: str | None = None, profile=open_profile) -> None:
    name, cfg = load_config(city)
    s, c, root, area = config(), cfg["gmaps"], data_dir() / "gmaps", cfg.get("area")
    if not area:
        raise SystemExit(f"config/cities.yaml: {city} has no area")
    out = root / "search" / f"{city}{SVC}"
    tiles = root_tiles(area, s["zoom"])
    done = done_tiles(out)
    throttle = Throttle(root / "svc_search_throttle.json", start=2, hi=min(s["tabs"], 4),
                        cooldown_s=c.get("cooldown_s", 60), max_cooldown_s=c.get("max_cooldown_s", 900))
    todo = [(w, t) for ws in s["groups"].values() for w in ws for t in tiles if (f"{w} {name}", tuple(t)) not in done]  # a bare word drifts to Ho Chi Minh City
    todo = todo[:limit] if limit else todo
    print(f"svc_search {city}: {len(todo)} searches left")

    async def one(ctx, word: str, tile: tuple) -> None:
        for attempt in range(1, ATTEMPTS + 1):
            async with throttle:
                try:
                    rows, end, _ = await search(ctx, f"{word} {name}", s["limit"], tile)
                    if not end and attempt < ATTEMPTS:
                        throttle.blocked()
                        continue
                    append_jsonl(out / f"{slug(word)}.jsonl", {"at": now(), "query": f"{word} {name}", "word": word, "tile": list(tile), "end": end,
                                                              "items": rows})
                    throttle.success()
                    return
                except (LoginRequired, CaptchaBlocked):
                    raise  # the person solves it; nothing retries
                except Exception as e:
                    if attempt < ATTEMPTS and (type(e).__name__ == "TimeoutError" or "net::ERR_" in str(e)):
                        throttle.blocked()
                        continue
                    log_error(root, f"{word}@{tile}", "svc_search", e)
                    return
                finally:
                    await pause(*c.get("pause_s", (0.2, 0.5)))

    async with profile(profile_name or "gmaps", headed) as ctx:
        async with asyncio.TaskGroup() as tg:
            for w, t in todo:
                tg.create_task(one(ctx, w, tuple(t)))


def run_list(city: str) -> dict:
    name, cfg = load_config(city)
    root = data_dir() / "gmaps"
    lst = build(root / "search" / f"{city}{SVC}", cfg.get("area"), config()["groups"])  # no same-name merge: ATMs share names
    write_json(root / "list" / f"{city}{SVC}.json", lst)
    print(f"list {city}{SVC}: {lst['stats']}")
    return lst["stats"]


def place_path(city_root: Path, fid: str) -> Path:
    return city_root / "services" / "places" / f"{safe_name(fid)}.json"


async def scrape(ctx, url: str) -> dict:
    page = await ctx.new_page()
    try:
        await open_page(page, url, "h1.DUwDvf")
        hours = page.locator(HOURS_BUTTON)
        if await hours.count():
            await hours.first.click()
            await page.wait_for_timeout(800)
        place = await parse_place(page)
        await check_signed_in(page)
        return {k: place.get(k) for k in ("name", "category", "address", "phone", "website", "hours", "status",
                                          "rating", "review_count", "plus_code")}
    finally:
        await page.close()


async def run_place(city: str, headed: bool = False, limit: int | None = None, shard=None,
                    profile_name: str | None = None, profile=open_profile) -> None:
    _, cfg = load_config(city)
    s, c, root = config(), cfg["gmaps"], data_dir() / "gmaps"
    lst = root / "list" / f"{city}{SVC}.json"
    if not lst.exists():
        raise SystemExit(f"no {lst}; run `python -m corpus gmaps svc_list --city {city}` first")
    todo = [r for r in json.loads(lst.read_text(encoding="utf-8"))["items"] if r.get("url")
            and not place_path(root, r["fid"]).exists()]
    todo = todo[:limit] if limit else todo
    print(f"svc_place {city}: {len(todo)} places left")
    throttle = Throttle(root / "svc_place_throttle.json", start=2, hi=min(s["tabs"], 4),
                        cooldown_s=c.get("cooldown_s", 60), max_cooldown_s=c.get("max_cooldown_s", 900))

    async def one(ctx, row: dict) -> None:
        for attempt in range(1, ATTEMPTS + 1):
            async with throttle:
                try:
                    got = await scrape(ctx, row["url"])
                    write_json(place_path(root, row["fid"]), {**got, "fid": row["fid"], "fetched_at": now()})
                    throttle.success()
                    return
                except (LoginRequired, CaptchaBlocked):
                    raise
                except Exception as e:
                    if attempt < ATTEMPTS and type(e).__name__ == "TimeoutError":
                        throttle.blocked()
                        continue
                    log_error(root, row["fid"], "svc_place", e)
                    return
                finally:
                    await pause(*c.get("pause_s", (0.2, 0.5)))

    async with profile(profile_name or "gmaps", headed) as ctx:
        await ensure_login(ctx)
        async with asyncio.TaskGroup() as tg:
            for row in todo:
                tg.create_task(one(ctx, row))


def load(city: str, group: str | None = None) -> list[dict]:
    """The services list joined with what the place pages gave (phone, website, hours, address); [] when not crawled.
    The only reader of these files: assistant tools (corpus.service_places)."""
    root = data_dir() / "gmaps"
    lst = root / "list" / f"{city}{SVC}.json"
    if not lst.exists():
        return []
    out = []
    all_words = sorted((w for ws in config()["groups"].values() for w in ws), key=len, reverse=True)
    for r in json.loads(lst.read_text(encoding="utf-8"))["items"]:
        if group and r.get("group") != group:
            continue
        p = place_path(root, r["fid"])
        facts = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        out.append({**{k: v for k, v in r.items() if k != "queries"}, "words": list(dict.fromkeys(word_of(q, all_words) for q in r.get("queries") or ())),
                    **{k: facts.get(k) for k in ("phone", "website", "hours", "address", "status", "fetched_at")}})
    return out
