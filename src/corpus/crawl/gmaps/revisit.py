"""Phase revisit: one more visit of the Maps page of the served places that lack hours or popular times, taking in
that one visit everything the page shows -> data/gmaps/places/<fid_dir>/revisit.json (place.json is not touched).

Why: the first crawl read the page as soon as its title rendered; the popular times graph renders later and a
slow page lost it (probe 2026-10-30: 1 of 31 live pages had a graph the saved record lacked). The visit waits for the
graph, opens the hours dropdown, and reads hours, popular times, price range, the ticket box and the "people
typically spend ... here" line (never seen on a Dalat page in the Vietnamese or English UI, 0 of 41 on 2026-10-30:
kept in case Maps shows it again). `panels` records which blocks the page had, so a place Maps has no hours for is
told apart from a page that did not load ("unknown", never "closed"). Observe adds these only where place.json had
nothing (observe/gmaps/extract.py maps_place). Lodging is left out: Maps shows no hours or visit time for it.
A page counts as done when it loaded signed in. A place is visited again only while hours or popular times are still
missing after the visit, at most PASSES times (the graph renders late: the first full pass of 2026-10-30 found
popular times for 88 of 570 places, so a second pass is measured before stopping); resume = `pass` in revisit.json.
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import BrowserContext

from ..common.browser import LoginRequired, open_profile, pause
from ..common.files import data_dir, load_config, log_error, now, safe_name, write_json
from ..common.throttle import Throttle
from .crawl import HOURS_BUTTON, parse_place
from .page import CaptchaBlocked, ensure_login, open_page

FILE = "revisit.json"
PASSES = 2
ATTEMPTS = 2
GRAPH = "div.C7xf8b > div"  # popular times graph; height 0, so wait for it attached, not visible
GRAPH_WAIT_MS = 10000
GROUP_ORDER = ("attraction", "garden_farm", "religious", "nature", "camping", "amusement", "museum")  # then the rest
SKIP_GROUPS = {"stay"}
_LINE_JS = r"""() => { const m = (document.querySelector('div[role="main"]') || document.body).innerText
  .match(/[^\n]*(?:thường dành|typically spend)[^\n]*/i); return m ? m[0].trim() : null; }"""
_BOX_JS = r"""() => !![...document.querySelectorAll('h2')].find(h => /^Vé vào cửa/.test(h.innerText.trim()))"""
KEEP = ("hours", "status", "popular_times", "price", "tickets")


def served_groups(root: Path) -> dict[str, str] | None:
    """fid -> category_group of the places the current release serves; None when there is no release."""
    try:
        name = (root / "releases" / "current").read_text(encoding="utf-8").strip()
        rows = json.loads((root / "releases" / name / "serving" / "places.json").read_text(encoding="utf-8"))["records"]
    except (OSError, ValueError, KeyError):
        return None
    return {r["id"]: (r.get("identity") or {}).get("category_group") or "" for r in rows}


def missing(place: dict) -> bool:
    """No hours or no popular times."""
    return not place.get("hours") or not any(place.get("popular_times") or [])


def seen_before(d: Path) -> dict | None:
    try:
        return json.loads((d / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def targets(places: list[tuple[Path, dict]], groups: dict[str, str] | None) -> list[tuple[Path, str]]:
    """(folder, url) of the places to visit: served (all of the list when there is no release), not lodging, still
    missing hours or popular times after the first crawl and the earlier visits, fewer than PASSES visits so far;
    the group order of GROUP_ORDER first."""
    rows = []
    for d, p in places:
        group = groups.get(p["fid"]) if groups is not None else ""
        if (groups is not None and group is None) or group in SKIP_GROUPS:
            continue
        before = seen_before(d)
        now_has = dict(p)
        if before:
            s = before.get("place") or {}
            now_has["hours"] = p.get("hours") or s.get("hours")
            now_has["popular_times"] = p["popular_times"] if any(p.get("popular_times") or []) else s.get("popular_times")
        if not missing(now_has) or (before and before.get("pass", 1) >= PASSES):
            continue
        rank = GROUP_ORDER.index(group) if group in GROUP_ORDER else len(GROUP_ORDER)
        rows.append((rank, d.name, d, p["url"]))
    return [(d, url) for _, _, d, url in sorted(rows, key=lambda r: r[:2])]


async def read_revisit(ctx: BrowserContext, url: str, passes: int = 1) -> dict:
    page = await ctx.new_page()
    try:
        await open_page(page, url, "h1.DUwDvf")
        try:
            await page.wait_for_selector(GRAPH, timeout=GRAPH_WAIT_MS, state="attached")
            graph = True
        except Exception:
            graph = False
        await page.wait_for_timeout(1200)
        button = page.locator(HOURS_BUTTON)
        has_button = await button.count() > 0
        if has_button:
            await button.first.click()
            await page.wait_for_timeout(800)
        place = await parse_place(page)
        return {"fetched_at": now(), "pass": passes, "place": {k: place[k] for k in KEEP},
                "panels": {"graph": graph, "hours_button": has_button, "hours_rows": len(place["hours"]),
                           "ticket_box": await page.evaluate(_BOX_JS)},
                "text": await page.evaluate(_LINE_JS)}
    finally:
        await page.close()


async def _place(ctx, d: Path, url: str, root, c: dict, throttle: Throttle) -> None:
    passes = (seen_before(d) or {"pass": 0}).get("pass", 1) + 1  # a file without `pass` is the first full pass
    for attempt in range(1, ATTEMPTS + 1):
        async with throttle:
            try:
                write_json(d / FILE, await read_revisit(ctx, url, passes))
                throttle.success()
                return
            except LoginRequired:
                raise
            except Exception as e:
                if isinstance(e, CaptchaBlocked) or type(e).__name__ == "TimeoutError":
                    throttle.blocked()
                if attempt < ATTEMPTS:
                    continue
                log_error(root, d.name, "revisit", e)
                return
            finally:
                await pause(*c.get("pause_s", (2.0, 5.0)))


async def run(city: str, headed: bool = False, profile=open_profile, limit: int | None = None,
              shard: tuple[int, int] | None = None, profile_name: str | None = None) -> None:
    _, cfg = load_config(city)
    c, root = cfg["gmaps"], data_dir() / "gmaps"
    places = [(f.parent, json.loads(f.read_text(encoding="utf-8"))) for f in sorted((root / "places").glob("*/place.json"))]
    listed = root / "list" / f"{city}.json"
    if listed.exists():
        keep = {safe_name(r["fid"]) for r in json.loads(listed.read_text(encoding="utf-8"))["items"]}
        places = [(d, p) for d, p in places if d.name in keep]
    todo = targets(places, served_groups(data_dir()))[:limit]
    if shard:  # one process per account
        todo = todo[shard[0]::shard[1]]
    print(f"revisit {city}: {len(todo)} places left" + (f" (shard {shard[0]}/{shard[1]})" if shard else ""))
    throttle = Throttle(root / "revisit_throttle.json", start=3, hi=3, cooldown_s=c.get("cooldown_s", 60),
                        max_cooldown_s=c.get("max_cooldown_s", 900))
    async with profile(profile_name or "gmaps", headed) as ctx:
        await ensure_login(ctx)
        try:
            async with asyncio.TaskGroup() as tg:
                for d, url in todo:
                    tg.create_task(_place(ctx, d, url, root, c, throttle))
        except* LoginRequired as eg:
            raise eg.exceptions[0] from None
    print(f"revisit {city}: {sum(seen_before(d) is not None for d, _ in todo)}/{len(todo)} visited")
