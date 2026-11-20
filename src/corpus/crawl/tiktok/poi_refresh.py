"""Place phase, poi_refresh: the TikTok place pages poi_crawl already mapped, listed again so Nhịp Đà Lạt sees the videos
posted since (docs/CORPUS.md §Nhịp, crawl định kỳ) -> data/tiktok/poi_recent/<fid_dir>.json.

poi_crawl reads a place once and keeps only the ten videos it downloads; this phase downloads nothing: it opens the place
page in the same logged-out session, keeps every listed video's id, author, caption and post time, and writes
{at, fid, name, poi, listed, videos:[{video_id, url, author_id, desc, hashtags, created_at, score}]}. Each run takes the
places listed longest ago first (never listed first), `limit` of them (config tiktok.poi_refresh_per_run), so a nightly
run goes round the whole city in a couple of weeks. corpus.pulse reads these files with poi_crawl's.
"""

import asyncio
import json

from playwright.async_api import BrowserContext

from ..common.browser import LoginRequired, open_sessions, pause
from ..common.files import data_dir, load_config, log_error, now, safe_name, write_json
from ..common.throttle import Throttle
from .page import is_block
from .poi_crawl import ATTEMPTS, ROW_KEYS, list_place, name_keys


def _last_listed(root, fid: str) -> float:
    """When the place's page was last listed (this phase or poi_crawl), 0 when never."""
    for sub in ("poi_recent", "poi_crawl"):
        f = root / sub / f"{safe_name(fid)}.json"
        if f.exists():
            return f.stat().st_mtime
    return 0.0


async def _refresh(ctx: BrowserContext, place: dict, root, c: dict, throttle: Throttle) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        async with throttle:
            try:
                rows = await list_place(ctx, place["poi"]["id"], c["poi_list_items"], name_keys(place["name"], place["poi"]["name"]))
                throttle.success()
                break
            except LoginRequired:
                raise
            except Exception as e:
                if attempt < ATTEMPTS and (is_block(e) or "never loaded" in str(e)):
                    throttle.blocked()
                    continue
                log_error(root, place["fid"], "poi_refresh", e)
                return
            finally:
                await pause(*c.get("pause_s", (0.0, 0.0)))
    write_json(root / "poi_recent" / f"{safe_name(place['fid'])}.json", {
        "at": now(), **{k: place.get(k) for k in ("fid", "name", "poi")}, "listed": len(rows),
        "videos": [{k: r[k] for k in ROW_KEYS} for r in rows]})


async def run(city: str, headed: bool = False, profile_name: str | None = None, sessions=open_sessions,
              limit: int | None = None) -> None:
    """profile_name is ignored: place pages need no account."""
    _, cfg = load_config(city)
    c, root = cfg["tiktok"], data_dir() / "tiktok"
    src = root / "place_poi" / f"{city}.json"
    if not src.exists():
        raise SystemExit(f"no {src}; run `python -m corpus tiktok place_poi --city {city}` first")
    places = [{"fid": fid, **p} for fid, p in json.loads(src.read_text(encoding="utf-8"))["places"].items() if p["poi"]]
    todo = sorted(places, key=lambda p: _last_listed(root, p["fid"]))[:limit or c.get("poi_refresh_per_run", 200)]
    print(f"poi_refresh {city}: listing {len(todo)} of {len(places)} mapped places, longest ago first", flush=True)
    throttle = Throttle(root / "poi_crawl_throttle.json", start=c.get("poi_tabs_start", 2), hi=c.get("poi_tabs", 3),
                        cooldown_s=c.get("cooldown_s", 60), max_cooldown_s=c.get("max_cooldown_s", 900))
    async with sessions(headed) as new_session:
        ctx = await new_session()
        try:
            async with asyncio.TaskGroup() as tg:  # a captcha in a headless run stops all
                for p in todo:
                    tg.create_task(_refresh(ctx, p, root, c, throttle))
        except* LoginRequired as eg:
            raise eg.exceptions[0] from None
    done = sum(_last_listed(root, p["fid"]) and (root / "poi_recent" / f"{safe_name(p['fid'])}.json").exists() for p in todo)
    print(f"poi_refresh {city}: {done}/{len(todo)} places listed, the rest in errors.jsonl", flush=True)
