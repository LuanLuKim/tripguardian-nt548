"""Phase offers: the flights Google Flights shows for the routes and days into a city -> data/gflights/<city>/.

One results page per (origin airport, destination airport, day), both directions of every route in config/queries.yaml
`flight_price:`. Each row is expanded once to read its flight number. Writes observations.jsonl (one line per search,
carrying its offers), runs.jsonl (one summary line per run), throttle.json and errors.jsonl. A page that showed no
flight row (slow, changed, blocked) writes no observation: nothing is recorded as "no flights" without evidence. The due
searches go never-seen first, then oldest, at most `max_per_run` per run (the hourly loop, logs/flight_price_loop.sh).
No login, no profile: each page is a fresh cookie-less context, 2 tabs at most. A captcha waits for a person when the
browser has a DevTools port (CORPUS_DEBUG_PORT) and stops a headless run (LoginRequired): no retry, nothing solved in code.
"""

import asyncio
import html as htmllib
import json
import time
import urllib.parse
from datetime import UTC, date, datetime, timedelta

from ..common.browser import LoginRequired, is_captcha, open_sessions, pause, wait_for_person
from ..common.files import append_jsonl, data_dir, load_config, log_error, now
from ..common.throttle import Throttle
from .parser import Flight, flight_numbers, parse_list

SOURCE = "gflights"
URL = "https://www.google.com/travel/flights?q={q}&hl=vi&curr=VND"
ROW = '[aria-label^="Từ "][aria-label*="Rời"]'
WAIT_S = 45  # a results page can take well over 20 s on a loaded server
SKIP = {"image", "media", "font"}  # prices are text: no photos, no map tiles
REQUIRED = ("src", "dst", "day", "observed_at", "source", "url", "offers")


class NotDrawn(Exception):
    """The page loaded but showed no flight row: not a block, nothing is recorded."""


def url(src: str, dst: str, day: date) -> str:
    """The search page for that day: what the crawler reads and where the user books."""
    return URL.format(q=urllib.parse.quote(f"Flights from {src} to {dst} on {day.isoformat()} one way"))


def settings(city: str) -> dict:
    """The `flight_price:` block of config/queries.yaml."""
    cfg = load_config(city)[1].get("flight_price")
    if not cfg:
        raise SystemExit("config/queries.yaml has no `flight_price:` block")
    return cfg


def searches(cfg: dict, today: date | None = None) -> list[tuple[str, str, date]]:
    """(src, dst, day) for every route in config, to and from the destination, from tomorrow (today's flights have
    mostly left) for the route's `days` days. Nearest day first."""
    today, dest, out = today or date.today(), cfg["dest"], []
    for route in cfg["routes"]:
        for k in range(1, int(route["days"]) + 1):
            day = today + timedelta(days=k)
            out += [(route["src"], dest, day), (dest, route["src"], day)]
    return sorted(out, key=lambda s: (s[2], s[0], s[1]))


def check(row: dict) -> None:
    missing = [k for k in REQUIRED if row.get(k) in (None, "", [])]
    if missing:
        raise ValueError(f"flight observation without {', '.join(missing)}")
    for o in row["offers"]:
        if not (o.get("carrier") and o.get("depart_at") and o.get("arrive_at")):
            raise ValueError("a flight offer has carrier, depart_at and arrive_at")
        if o.get("price_vnd") is not None and not (isinstance(o["price_vnd"], int) and o["price_vnd"] > 0):
            raise ValueError("price_vnd is a positive integer or None")


def append_observation(city: str, row: dict) -> None:
    check(row)
    append_jsonl(data_dir() / SOURCE / city / "observations.jsonl", row)


def latest(city: str) -> dict[tuple[str, str, str], dict]:
    """(src, dst, day) -> the newest observation (a later line wins a tie)."""
    path, out = data_dir() / SOURCE / city / "observations.jsonl", {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            key = (r["src"], r["dst"], r["day"])
            if key not in out or r["observed_at"] >= out[key]["observed_at"]:
                out[key] = r
        except (ValueError, KeyError, TypeError):
            continue
    return out


def todo_searches(city: str, cfg: dict, limit: int | None = None, today: date | None = None,
                  at: str | None = None) -> list[tuple[str, str, date]]:
    """Searches to run: never-seen first, then the oldest, each again after `fresh_h` hours."""
    seen, edge = latest(city), (datetime.fromisoformat(at) if at else datetime.now(UTC))
    todo = []
    for i, (src, dst, day) in enumerate(searches(cfg, today)):
        got = seen.get((src, dst, day.isoformat()))
        if got is not None and (edge - datetime.fromisoformat(got["observed_at"])).total_seconds() / 3600 < cfg["fresh_h"]:
            continue
        todo.append(((got["observed_at"] if got else ""), i, (src, dst, day)))
    todo.sort(key=lambda t: t[:2])
    return [s for *_, s in todo][: limit or cfg["max_per_run"]]


async def _skip_heavy(route) -> None:
    await (route.abort() if route.request.resource_type in SKIP else route.continue_())


async def read(ctx, link: str, day: date, wait=wait_for_person) -> list[dict]:
    """The flights on the page at `link`, each with its flight numbers ([] when the row would not expand). Raises
    NotDrawn when no row ever showed."""
    page = await ctx.new_page()
    try:
        await page.goto(link, wait_until="domcontentloaded", timeout=WAIT_S * 1000)
        if "/sorry/" in page.url or await is_captcha(page):
            await wait(page, SOURCE, wait_s=None)
        try:
            await page.wait_for_selector(ROW, timeout=WAIT_S * 1000)
        except Exception:
            if "/sorry/" in page.url or await is_captcha(page):
                await wait(page, SOURCE, wait_s=None)
            raise NotDrawn("no flight row on the page") from None
        rows, out, seen = page.locator(ROW), [], set()
        for i in range(await rows.count()):
            row = rows.nth(i)
            label = await row.get_attribute("aria-label") or ""
            found = parse_list(f'<div aria-label="{htmllib.escape(label)}"></div>', day)
            if not found or found[0] in seen:
                continue
            seen.add(found[0])
            out.append({"flight": found[0], "numbers": await _numbers(row)})
        return out
    finally:
        await page.close()


async def _numbers(row) -> list[str]:
    """Expand one row and read its flight numbers; [] when it does not expand (unknown, not a guess)."""
    try:
        li = row.locator("xpath=ancestor::li[1]")
        await li.locator("[aria-expanded]").first.click(timeout=5000)
        await row.page.wait_for_timeout(600)
        return flight_numbers(await li.inner_text(timeout=5000))
    except Exception:
        return []


def observation(src: str, dst: str, day: date, link: str, flights: list[dict]) -> dict:
    return {"src": src, "dst": dst, "day": day.isoformat(), "observed_at": now(), "source": SOURCE, "url": link,
            "offers": [{"carrier": f["flight"].carrier, "flight_no": " + ".join(f["numbers"]) or None,
                        "depart_at": f["flight"].depart_at, "arrive_at": f["flight"].arrive_at,
                        "from_point": f["flight"].from_point, "to_point": f["flight"].to_point,
                        "price_vnd": f["flight"].price_vnd, "stops": f["flight"].stops} for f in flights]}


async def run(city: str, headed: bool = False, limit: int | None = None, sessions=open_sessions, wait=wait_for_person,
              todo: list[tuple[str, str, date]] | None = None, reader=read) -> dict:
    cfg = settings(city)
    root = data_dir() / SOURCE / city
    todo = todo if todo is not None else todo_searches(city, cfg, limit)
    stats = {"searches": len(todo), "with_flights": 0, "not_drawn": 0, "errors": 0, "captcha": 0}
    print(f"gflights offers {city}: {len(todo)} searches due")
    throttle = Throttle(root / "throttle.json", start=1, hi=cfg["tabs"])
    t0 = time.monotonic()

    async def one(new_session, src: str, dst: str, day: date) -> None:
        link = url(src, dst, day)
        async with throttle:
            ctx = None
            try:
                ctx = await new_session()
                await ctx.route("**/*", _skip_heavy)
                flights = await reader(ctx, link, day, wait)
                append_observation(city, observation(src, dst, day, link, flights))
                stats["with_flights"] += 1
                throttle.success()
            except LoginRequired:
                stats["captcha"] += 1
                raise
            except NotDrawn as e:
                stats["not_drawn"] += 1
                log_error(root, f"{src}-{dst}-{day}", "offers", e)
            except Exception as e:
                stats["errors"] += 1
                if type(e).__name__ == "TimeoutError" or "net::ERR_" in str(e):
                    throttle.blocked()
                log_error(root, f"{src}-{dst}-{day}", "offers", e)
            finally:
                if ctx is not None:
                    await ctx.close()
                await pause(*cfg["pause_s"])

    try:
        async with sessions(headed) as new_session, asyncio.TaskGroup() as tg:
            for src, dst, day in todo:
                tg.create_task(one(new_session, src, dst, day))
    except* LoginRequired as eg:
        stats["stopped"] = "captcha"
        print("gflights offers: stopped by a captcha; set CORPUS_DEBUG_PORT=<port> and reach the tab through chrome://inspect to solve it")
        _summary(root, stats, t0)
        raise eg.exceptions[0] from None
    _summary(root, stats, t0)
    return stats


def _summary(root, stats: dict, t0: float) -> None:
    stats["seconds"] = round(time.monotonic() - t0, 1)
    append_jsonl(root / "runs.jsonl", {"at": now(), **stats})
    print(f"gflights offers: {stats}")
