"""Place phase, refresh: the reviews posted on Maps since the first crawl, so Nhịp Đà Lạt sees who is going now
(docs/CORPUS.md §Nhịp, crawl định kỳ) -> data/gmaps/reviews_recent/<fid_dir>.json.

`crawl` reads a place once (place.json = done); this phase opens the places the current release serves again, signed
in, sorts the reviews by "Mới nhất" and keeps those up to REFRESH_MONTHS old (scrape_place stops scrolling at the first
older one), with the place's rating, review count and status as Maps shows them now. Writes
{at, fid, name, rating, review_count, status, reviews:[{review_id, author_hash, rating, published_text, text}]}.
Each run takes the places refreshed longest ago first (never refreshed first; not lodging first), `limit` of them
(config gmaps.refresh_per_run). corpus.pulse reads these files with the observations' ratings. No model here.
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import BrowserContext

from ..common.browser import LoginRequired, open_profile, pause
from ..common.files import data_dir, load_config, log_error, now, safe_name, write_json
from ..common.throttle import Throttle
from .crawl import ATTEMPTS, scrape_place
from .page import CaptchaBlocked, ensure_login, text_only
from .revisit import served_groups

REFRESH_MONTHS = 1      # "một tháng trước" and newer: the Nhịp window is 30 days
REFRESH_REVIEWS = 120   # at most, on a place that gets many a day
PER_RUN = 300           # places a run, when config gmaps.refresh_per_run is not set
LAST = ("stay",)        # lodging after every other group: Nhịp's hot and trend lists are places to go
ROW_KEYS = ("review_id", "author_hash", "rating", "published_text", "text")


def _last_refreshed(root: Path, fid: str) -> float:
    f = root / "reviews_recent" / f"{safe_name(fid)}.json"
    return f.stat().st_mtime if f.exists() else 0.0


def todo(root: Path, items: list[dict], groups: dict[str, str] | None, limit: int) -> list[dict]:
    """The listed places the release serves (all when there is no release), lodging last, refreshed longest ago
    first; `limit` of them."""
    rows = [r for r in items if groups is None or r["fid"] in groups]
    rows.sort(key=lambda r: ((groups or {}).get(r["fid"]) in LAST, _last_refreshed(root, r["fid"]),
                             -int(float(r.get("reviews") or 0))))
    return rows[:limit]


async def _refresh(ctx: BrowserContext, row: dict, root: Path, c: dict, throttle: Throttle) -> bool:
    for attempt in range(1, ATTEMPTS + 1):
        async with throttle:
            try:
                place, reviews = await scrape_place(ctx, row["url"], REFRESH_REVIEWS, REFRESH_MONTHS, 0)
                throttle.success()
                break
            except LoginRequired:
                raise
            except Exception as e:
                blocked = type(e).__name__ == "TimeoutError" or isinstance(e, CaptchaBlocked)
                if attempt < ATTEMPTS and blocked:
                    throttle.blocked()
                    continue
                log_error(root, row["fid"], "refresh", e)
                return False
            finally:
                await pause(*c.get("pause_s", (2.0, 5.0)))
    write_json(root / "reviews_recent" / f"{safe_name(row['fid'])}.json", {
        "at": now(), "fid": row["fid"], "name": row.get("name"),
        **{k: place.get(k) for k in ("rating", "review_count", "status")},
        "reviews": [{k: r.get(k) for k in ROW_KEYS} for r in reviews]})
    return True


async def run(city: str, headed: bool = False, profile=open_profile, limit: int | None = None,
              shard: tuple[int, int] | None = None, profile_name: str | None = None) -> None:
    _, cfg = load_config(city)
    c, root = cfg["gmaps"], data_dir() / "gmaps"
    listed = root / "list" / f"{city}.json"
    if not listed.exists():
        raise SystemExit(f"no {listed}; run `python -m corpus gmaps list --city {city}` first")
    rows = todo(root, json.loads(listed.read_text(encoding="utf-8"))["items"], served_groups(data_dir()),
                limit or c.get("refresh_per_run") or PER_RUN)
    if shard:  # one process per account
        rows = rows[shard[0]::shard[1]]
    print(f"refresh {city}: {len(rows)} places" + (f" (shard {shard[0]}/{shard[1]})" if shard else ""), flush=True)
    throttle = Throttle(root / "refresh_throttle.json", start=c.get("tabs_start", 1), hi=c.get("tabs", 1),
                        cooldown_s=c.get("cooldown_s", 60), max_cooldown_s=c.get("max_cooldown_s", 900))
    async with profile(profile_name or "gmaps", headed) as ctx:
        await text_only(ctx)
        await ensure_login(ctx)
        try:
            async with asyncio.TaskGroup() as tg:  # one LoginRequired stops all
                tasks = [tg.create_task(_refresh(ctx, r, root, c, throttle)) for r in rows]
        except* LoginRequired as eg:
            raise eg.exceptions[0] from None
    print(f"refresh {city}: {sum(t.result() for t in tasks)}/{len(rows)} refreshed, the rest in errors.jsonl", flush=True)
