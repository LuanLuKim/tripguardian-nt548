"""Phase price: Google Travel's price for the trip dates of lodging already in the corpus -> data/gtravel/<city>/.

One hotel page per (lodging, stay): the URL carries the dates (url.hotel_url), no list is crawled and nothing is
typed. Writes observations.jsonl (lodging.append_observation rows), runs.jsonl (one summary line per run),
throttle.json and errors.jsonl. The pairs that are due go oldest first, at most `max_per_run` per run; the rest
wait for the next run (the hourly loop, logs/lodging_price_loop.sh). No login, no profile: each page is a fresh
cookie-less context, 2 tabs at most. A captcha waits for a person in a headed run and stops a headless one
(LoginRequired): no retry, nothing solved in code.
"""

import asyncio
import time
from dataclasses import replace

from ..common import lodging
from ..common.browser import LoginRequired, is_captcha, open_sessions, pause, wait_for_person
from ..common.files import append_jsonl, data_dir, load_config, log_error, now
from ..common.throttle import Throttle
from .parser import Hotel, dates_match, parse_hotel
from .url import hotel_url

SOURCE = "gtravel"
SETTLE_S = 15  # the offers load after the page (priced pages take 2-4 s): wait this long before calling a page unreadable
TEXT_JS = "() => document.body.innerText"
SKIP = {"image", "media", "font"}  # the price is text: no photos, no map tiles


async def _skip_heavy(route) -> None:
    await (route.abort() if route.request.resource_type in SKIP else route.continue_())


async def read(ctx, url: str, wait=wait_for_person) -> Hotel:
    """The hotel page at url, read once its offers (or the lack of them) are drawn. Hotel("pending") when they never were."""
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        if "/sorry/" in page.url or await is_captcha(page):
            await wait(page, SOURCE, wait_s=None)
        hotel = Hotel("pending")
        for _ in range(SETTLE_S):
            hotel = parse_hotel(await page.evaluate(TEXT_JS))
            if hotel.state != "pending":
                break
            await page.wait_for_timeout(1000)
        if hotel.state == "priced" and hotel.dates == "inputs":
            vals = await page.evaluate("() => [...document.querySelectorAll('input[aria-label=\"Nhận phòng\"],"
                                       "input[aria-label=\"Trả phòng\"]')].map(i => i.value)")
            hotel = replace(hotel, dates="|".join(vals[:1] + vals[-1:]) if len(vals) >= 2 else None)
        return hotel
    finally:
        await page.close()


def observation(row: dict, stay: lodging.Stay, hotel: Hotel, url: str, city_name: str) -> dict:
    """The observation for a read page. A price counts only when the page shows the dates asked for. A page that
    wants a longer stay carries `min_nights`; one whose offers never drew carries `note: "not_drawn"`: both are
    unknown (no price, available None), never "sold out"."""
    priced = hotel.state == "priced" and dates_match(hotel.dates, stay)
    night = hotel.price_night_vnd if priced else None
    extra = {"min_nights": hotel.min_nights} if hotel.state == "min_stay" else {"note": "not_drawn"} if hotel.state == "pending" else {}
    return {**extra, "fid": row["fid"], "price_total_vnd": night * stay.nights if night else None, "price_night_vnd": night,
            "currency": "VND", "available": True if night else None, "stay_date": stay.checkin.isoformat(),
            "nights": stay.nights, "adults": stay.adults, "observed_at": now(), "source": SOURCE, "url": url,
            "matched_name": hotel.name, "match_score": lodging.similarity(hotel.name or "", row["name"], city_name)}


def todo_pairs(city: str, cfg: dict, limit: int | None = None) -> list[tuple[dict, lodging.Stay]]:
    rows = lodging.load_stays(city)[: cfg["top_lodgings"]]
    by_fid = {r["fid"]: r for r in rows}
    pairs = lodging.queue(list(by_fid), lodging.stay_dates(cfg), lodging.latest(SOURCE, city), cfg["fresh_h"],
                          cfg["no_offer_h"], cfg.get("dead_h", 336))
    return [(by_fid[fid], stay) for fid, stay in pairs[: limit or cfg["max_per_run"]]]


async def run(city: str, headed: bool = False, limit: int | None = None, sessions=open_sessions, wait=wait_for_person,
              pairs: list[tuple[dict, lodging.Stay]] | None = None) -> dict:
    cfg = lodging.settings(city)
    city_name = load_config(city)[0]
    root = data_dir() / SOURCE / city
    pairs = pairs if pairs is not None else todo_pairs(city, cfg, limit)
    stats = {"pairs": len(pairs), "priced": 0, "no_offer": 0, "min_stay": 0, "not_drawn": 0, "errors": 0, "captcha": 0}
    print(f"gtravel price {city}: {len(pairs)} (lodging, date) pairs due")
    throttle = Throttle(root / "throttle.json", start=1, hi=cfg["tabs"])
    t0 = time.monotonic()

    async def one(new_session, row: dict, stay: lodging.Stay) -> None:
        url = hotel_url(row["fid"], stay)
        async with throttle:
            if time.monotonic() - t0 > cfg.get("budget_s", float("inf")):
                return  # the rest waits for the next hour's pass
            ctx = None
            try:
                ctx = await new_session()
                await ctx.route("**/*", _skip_heavy)
                hotel = await read(ctx, url, wait)
                obs = observation(row, stay, hotel, url, city_name)
                lodging.append_observation(SOURCE, city, obs)
                stats["priced" if obs["price_night_vnd"] else {"min_stay": "min_stay", "pending": "not_drawn"}.get(hotel.state, "no_offer")] += 1
                if hotel.state == "pending":
                    log_error(root, row["fid"], "not_drawn", ValueError(f"offers not drawn for {stay.checkin} +{stay.nights}"))
                if hotel.state == "priced" and not obs["price_night_vnd"]:
                    log_error(root, row["fid"], "dates", ValueError(f"asked {stay.checkin} +{stay.nights}, page shows {hotel.dates}"))
                throttle.success()
            except LoginRequired:
                stats["captcha"] += 1
                raise
            except Exception as e:
                stats["errors"] += 1
                if type(e).__name__ == "TimeoutError" or "net::ERR_" in str(e):
                    throttle.blocked()
                log_error(root, row["fid"], "price", e)
            finally:
                if ctx is not None:
                    await ctx.close()
                await pause(*cfg["pause_s"])

    try:
        async with sessions(headed) as new_session, asyncio.TaskGroup() as tg:
            for row, stay in pairs:
                tg.create_task(one(new_session, row, stay))
    except* LoginRequired as eg:
        stats["stopped"] = "captcha"
        print("gtravel price: stopped by a captcha; run again with --headed to solve it")
        _summary(root, stats, t0)
        raise eg.exceptions[0] from None
    _summary(root, stats, t0)
    return stats


def _summary(root, stats: dict, t0: float) -> None:
    stats["seconds"] = round(time.monotonic() - t0, 1)
    append_jsonl(root / "runs.jsonl", {"at": now(), **stats})
    print(f"gtravel price: {stats}")
