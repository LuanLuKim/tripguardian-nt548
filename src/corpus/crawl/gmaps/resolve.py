"""Phase resolve: nominees sol proposed that `navigate compare` could not find in the corpus -> a Maps lookup each.

Reads the queue (`corpus.navigate.pending_nominees`: data/<city>/navigate/resolve_queue.jsonl plus the `maybe` matches of
the newest compare report), searches Maps for "<name> <city name>" in a fresh cookie-less session (no Google profile),
and lets `navigate.decide_resolution` say what the result list means. Only a nominee Maps resolves to ONE clear place
inside the city area, with enough reviews, is written, in the search-file format, to
data/gmaps/search/<city>/resolve.jsonl; `filter`, `counts` and `list` then gate it like every other place (Extractor
relevance, min_reviews, same-place merge). Everything else stays a proposal. Each verdict is one line of
data/<city>/navigate/resolved.jsonl; no verdict says a place does not exist. A page that fails or lists nothing writes no
line, so the nominee is looked up again next run.
"""

import asyncio
import collections

from ... import navigate
from ..common.browser import LoginRequired, open_sessions, pause
from ..common.files import append_jsonl, data_dir, listed, load_config, log_error, now
from ..common.throttle import Throttle
from .listing import is_lodging
from .search import ATTEMPTS, search
from .tiles import in_area

TABS = 2  # a lookup is one short list: few parallel tabs are enough, and Maps' throttling is per session


async def run(city: str, headed: bool = False, limit: int | None = None, sessions=open_sessions, searcher=search) -> dict:
    name, cfg = load_config(city)
    c, root, area = cfg["gmaps"], data_dir() / "gmaps", cfg.get("area")
    if not area:
        raise SystemExit(f"config/cities.yaml: {city} has no area")
    todo = navigate.pending_nominees(city)[:limit]
    held = {r["fid"] for r in listed(city) or []}
    at = (round((area[0] + area[2]) / 2, 6), round((area[1] + area[3]) / 2, 6), c["grid"]["start_zoom"])
    per_query = navigate.resolve_search_limit()
    city_words = set(navigate.fold(name).split())
    throttle = Throttle(root / "resolve_throttle.json", start=1, hi=TABS, cooldown_s=c.get("cooldown_s", 60),
                        max_cooldown_s=c.get("max_cooldown_s", 900))
    out, counts = root / "search" / city / "resolve.jsonl", collections.Counter()
    print(f"resolve {city}: {len(todo)} nominees to look up")

    async def one(new_session, nominee: dict):
        query = f"{nominee['name']} {name}"
        for attempt in range(1, ATTEMPTS + 1):
            async with throttle:
                ctx = None
                try:
                    ctx = await new_session()
                    rows, _, _ = await searcher(ctx, query, per_query, at)
                    if not rows:  # a throttled list is empty, not a sign that the place is absent
                        throttle.blocked()
                        if attempt < ATTEMPTS:
                            continue
                        log_error(root, query, "resolve", RuntimeError("Maps listed nothing"))
                        return
                    rows = [{**r, "inside": in_area(r.get("lat"), r.get("lng"), area), "lodging": is_lodging(r.get("category"))}
                            for r in rows]
                    verdict = navigate.decide_resolution(
                        nominee, rows, min_reviews=c.get("min_reviews", 0), same_name_m=c.get("same_name_m", 0),
                        min_reviews_stay=cfg.get("stay", {}).get("min_reviews", c.get("min_reviews", 0)),
                        held_fids=held, city_words=city_words)
                    item = verdict.pop("item", None)
                    if item is not None:
                        append_jsonl(out, {"at": now(), "query": f"resolve: {nominee['name']}", "tile": [], "end": True,
                                           "lodging": False, "items": [item], "nominee": nominee})
                    navigate.record_resolution(city, {**nominee, "query": query, **verdict})
                    counts[verdict["status"]] += 1
                    throttle.success()
                    return
                except LoginRequired:
                    raise
                except Exception as e:
                    if attempt < ATTEMPTS and (type(e).__name__ == "TimeoutError" or "net::ERR_" in str(e)):
                        throttle.blocked()
                        continue
                    log_error(root, query, "resolve", e)
                    return
                finally:
                    if ctx is not None:
                        await ctx.close()
                    await pause(*c.get("pause_s", (2.0, 5.0)))

    if todo:
        async with sessions(headed) as new_session, asyncio.TaskGroup() as tg:
            for nominee in todo:
                tg.create_task(one(new_session, nominee))
    stats = {"total": len(todo), **{s: counts[s] for s in navigate.RESOLVE_STATUSES}}
    stats["looked_up"] = sum(counts.values())
    print(f"resolve {city}: {stats}")
    return stats

