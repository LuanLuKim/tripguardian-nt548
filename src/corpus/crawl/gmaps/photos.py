"""Phase photos: newest Maps photos of each listed place -> data/gmaps/places/<fid_dir>/photos/ + photos.json.

The place page's photo gallery, tab "Mới nhất" (newest first; "Tất cả" when a place has no such tab), first
photos_per_place tiles. Each tile is opened once to read who posted it (contrib id -> author_hash, the same hash
as their reviews, so one person is one vote across text and photos) and when ("Ảnh - thg 9 2026"); the image is
downloaded at photo_px. A photo posted by the place itself (contributor name = place name) is flagged `owner`:
marketing pictures, kept but weighed by the reader. Video tiles keep their still frame (`kind = video`).

At most PER_AUTHOR photos per poster, from the first SCAN_FACTOR x photos_per_place tiles. Complete = enough photos,
or the gallery ended (stopped growing after END_SCROLLS scrolls: a small gallery). A page that breaks mid-way is retried; the last try is saved with `complete: false` and logged.
Sights (photo_groups, config/category_defaults.yaml groups) get photos_per_sight: stairs and paths show in photos more
than in reviews. A place saved with fewer than it now wants, because it stopped at its old cap (not at the gallery's
end), is fetched again with the new count. Otherwise written once per place; delete photos.json to fetch again.
A place whose every photo is older than MAX_AGE_YEARS would have no picture at all: its newest STALE_KEEP old photos are
kept with `stale: true`. They are for the web cover only; every reader of evidence (observe, styles, vectors) skips them.

Aged outdoor photos (env GMAPS_PHOTO_AGED=1, owner 2026-10-30; config/scenes.yaml pick.old): in a sight group (nature, attraction, ...)
a photo older than MAX_AGE_YEARS but not older than pick.old.max_age_years is kept too (up to AGED_KEEP per place), flagged
`stale: true` (so no reader of evidence sees it) and `display_old: true` (so `photo_scenes` labels it and a card may show it, only as a
view / exterior and with its year). Such a place is fetched again once (`aged_years` in photos.json).

Scene pass (env GMAPS_PHOTO_CHIPS=1, the fill-photos track 2026-10-30): a gallery with the first two tabs read still holds category
chips (interior / exterior / vibe / room ...). Every chip that is not a tab, a video, a menu, a 360 view or the food chips is
read too, up to CHIP_PHOTOS more photos, and the file records `chips` (a place with that key is not read again). The Maps gallery
is only there when the account is signed in: a page with no gallery tab and the sign-in link raises LoginRequired (the SID cookie outlives the
session, 2026-10-30 gmaps_s0 / gmaps_s2), and a run that opened no tab never replaces a photos.json that has photos.
"""

import asyncio
import collections
import json
import os
import re

from playwright.async_api import BrowserContext, Page

from ..common.browser import LoginRequired, open_profile, pause
from ..common.files import author_hash, data_dir, load_config, log_error, now, safe_name, write_json
from ..common.throttle import Throttle
from .gate import GateThrottle
from .keywords import category_group
from .page import SIGN_IN_LINK, CaptchaBlocked, ensure_login, more, open_page

FILE = "photos.json"
TILE = "a[data-photo-index]"
ATTEMPTS = 2
END_SCROLLS = 2
PER_AUTHOR = 3  # photos kept per poster
SCAN_FACTOR = 3  # tiles looked at per photo wanted
MAX_AGE_YEARS = 3  # older photos (taken, else posted) are skipped: the place may have changed
STALE_KEEP = 4  # a place with no photo newer than that keeps this many old ones, flagged `stale`, for its cover only
_SIZE = re.compile(r"=w\d+-h\d+[^\"')]*$")

TILES_JS = r"""() => [...document.querySelectorAll('a[data-photo-index]')].map(a => {
  const img = a.querySelector('[style*="googleusercontent"]');
  const url = img?.getAttribute('style').match(/url\(["']?([^"')]+)/)?.[1] ?? null;
  return {index: +a.dataset.photoIndex, url, video: (a.getAttribute('aria-label') || '') === 'Video'};
})"""

VIEWER_JS = r"""() => {
  const who = [...document.querySelectorAll('a[href*="/contrib/"]')].find(a => a.innerText.trim());
  const texts = [...document.querySelectorAll('div, span')].map(e => e.childElementCount ? '' : (e.innerText || '').trim());
  return {
    id: location.href.match(/!1s([^!?]+)/)?.[1] ?? null,
    contributor: who?.href.match(/contrib\/(\d+)/)?.[1] ?? null,
    name: who?.innerText.trim() ?? null,
    posted: texts.find(t => /^(Ảnh|Video)\s*-\s*\S/.test(t)) ?? null,      // "Ảnh - thg 2 2026"
    taken: texts.find(t => /^Ảnh chụp vào:/.test(t))?.replace(/^Ảnh chụp vào:\s*/, '') ?? null,
  };
}"""


def sized(url: str, px: int) -> str:
    url = url if url.startswith("http") else "https:" + url
    return _SIZE.sub(f"=w{px}-h{px}-k-no", url) if _SIZE.search(url) else url + f"=w{px}-h{px}-k-no"


def norm(s: str | None) -> str:
    return re.sub(r"\W+", "", (s or "").casefold())


TABS = ("Mới nhất", "Tất cả")  # newest first; "Mới nhất" holds only recent months, "Tất cả" fills the rest
CHIPS = bool(os.environ.get("GMAPS_PHOTO_CHIPS"))
AGED = bool(os.environ.get("GMAPS_PHOTO_AGED"))
AGED_KEEP = 12  # aged photos kept per place (the labels decide which are views / exteriors)
CHIP_PHOTOS = 12  # photos read from the category chips on top of the place's wanted count
CHIP_MAX = 4  # chips read per place
# chips that are not a scene of the place: the two tabs, video, menu, 360 / street view, food (the menu and dishes are read by `menu`)
_NOT_SCENE = re.compile(r"^(tất cả|mới nhất|video|thực đơn|menu|thực phẩm|đồ ăn|món|chế độ xem|360)|360", re.I)


def aged_rule() -> dict:
    """config/scenes.yaml pick.old: {"max_age_years", "groups", "scenes"}."""
    import yaml
    from ..common.files import ROOT
    return yaml.safe_load((ROOT / "config" / "scenes.yaml").read_text(encoding="utf-8"))["pick"]["old"]


def aged_place(place: dict) -> bool:
    """Whether the aged-photo rule applies to this place (a sight group of pick.old)."""
    return AGED and category_group(place.get("category")) in aged_rule()["groups"]


def flag_aged_on_disk(root=None) -> dict:
    """No browser: the cover-only `stale` photos already on disk of sight places, not older than pick.old.max_age_years,
    get `display_old` (up to AGED_KEEP per place), as a crawl with GMAPS_PHOTO_AGED would have flagged them. Idempotent;
    `aged_years` is NOT written, so the crawl still fetches such a place once. {"places", "photos"}."""
    root = root or data_dir() / "gmaps"
    rule = aged_rule()
    cutoff = f"{int(now()[:4]) - rule['max_age_years']}-{now()[5:7]}"
    places = photos = 0
    for f in sorted((root / "places").glob("*/place.json")):
        place = json.loads(f.read_text(encoding="utf-8"))
        pj = f.parent / FILE
        if category_group(place.get("category")) not in rule["groups"] or not pj.exists():
            continue
        doc = json.loads(pj.read_text(encoding="utf-8"))
        flagged = sum(bool(p.get("display_old")) for p in doc.get("photos", []))
        new = 0
        for p in doc.get("photos", []):
            if (p.get("stale") and not p.get("display_old") and (p.get("month") or "") >= cutoff
                    and (f.parent / p["file"]).exists() and flagged + new < AGED_KEEP):
                p["display_old"] = True
                new += 1
        if new:
            write_json(pj, doc)
            places += 1
            photos += new
    return {"places": places, "photos": photos}


def scene_chips(labels: list[str]) -> list[str]:
    """The gallery chips worth a visit for scenes, in page order, deduplicated, at most CHIP_MAX."""
    out: list[str] = []
    for label in labels:
        label = (label or "").strip()
        if label and label not in out and not _NOT_SCENE.search(label):
            out.append(label)
    return out[:CHIP_MAX]


async def open_gallery(page: Page, label: str) -> bool:
    b = page.locator(f'button[aria-label^="{label}"], button:has-text("{label}")')
    if not await b.count():
        return False
    await b.first.click()
    await page.wait_for_timeout(1500)  # the tiles of the previous tab stay until the new ones render
    await page.wait_for_selector(TILE, timeout=15000)
    return True


async def list_tiles(page: Page, n: int) -> tuple[list[dict], bool]:
    """First n tiles; complete = n reached or the gallery stopped growing after END_SCROLLS scrolls."""
    idle = 0
    while True:
        k = await page.locator(TILE).count()
        if k >= n:
            break
        await page.locator(TILE).last.scroll_into_view_if_needed(timeout=5000)
        if await more(page, TILE, k, timeout=6000):
            idle = 0
            continue
        idle += 1
        if idle >= END_SCROLLS:
            break
    tiles = sorted(await page.evaluate(TILES_JS), key=lambda t: t["index"])[:n]
    return [t for t in tiles if t["url"]], True


async def viewer_moved(page: Page, last_id: str | None, timeout_s: float = 8.0) -> dict | None:
    """The viewer's metadata once it shows a photo other than last_id with its poster line, read the same twice in a
    row (the header updates field by field: a single read can mix two photos); None if it never settles."""
    prev = None
    for _ in range(int(timeout_s / 0.4)):
        meta = await page.evaluate(VIEWER_JS)
        if meta["id"] and meta["id"] != last_id and meta["posted"]:
            if meta == prev:
                return meta
            prev = meta
        await page.wait_for_timeout(400)
    return None


_MONTH = re.compile(r"thg (\d{1,2}) (\d{4})")


def month(text: str | None) -> str | None:
    """"Ảnh - thg 9 2026" -> "2026-09"; relative dates ("2 tuần trước") are recent -> None, never too old."""
    m = _MONTH.search(text or "")
    return f"{m.group(2)}-{int(m.group(1)):02d}" if m else None


async def scrape_photos(ctx: BrowserContext, place: dict, d, n: int, px: int, per_author: int = PER_AUTHOR,
                        max_age_years: int = MAX_AGE_YEARS) -> dict:
    """Up to n photos, at most per_author from one poster (a gallery's newest are often one person's burst), from the
    first SCAN_FACTOR * n tiles."""
    oldest = f"{int(now()[:4]) - max_age_years}-{now()[5:7]}"
    page, img = await ctx.new_page(), await ctx.new_page()
    try:
        await open_page(page, place["url"], "h1.DUwDvf")
        out, stale, last_id, skipped, by_author, seen = [], [], None, collections.Counter(), collections.Counter(), set()
        aged = [] if aged_place(place) else None
        oldest_aged = f"{int(now()[:4]) - aged_rule()['max_age_years']}-{now()[5:7]}" if aged is not None else None
        tabs, complete = [], True
        (d / "photos").mkdir(exist_ok=True)
        for tab in TABS:
            if len(out) >= n or not await open_gallery(page, tab):
                continue
            tabs.append(tab)
            tiles, _ = await list_tiles(page, n * SCAN_FACTOR)
            complete = len(tiles) < n * SCAN_FACTOR  # the whole tab was looked at
            for t in tiles:
                if len(out) >= n:
                    break
                if t["url"] in seen:
                    continue
                seen.add(t["url"])
                last_id = await _one(page, img, place, d, t, px, per_author, last_id, out, skipped, by_author, oldest, stale, aged, oldest_aged)
        if not tabs:  # no gallery: a signed-out page too (its "Đăng nhập" link renders a few seconds late, after open_page's check)
            try:
                await page.bring_to_front()  # a background tab does not run the page's late scripts that draw the link
                await page.wait_for_selector(SIGN_IN_LINK, state="attached", timeout=10000)
            except Exception:
                pass  # no sign-in link: a signed-in place that simply has no gallery
            else:
                raise LoginRequired("gmaps")
        chips = None
        if CHIPS and tabs:
            chips = []
            labels = await page.evaluate("() => [...document.querySelectorAll('button[role=tab][aria-label]')].map(b => b.getAttribute('aria-label'))")
            for label in scene_chips(labels):
                if len(out) >= n + CHIP_PHOTOS:
                    break
                try:
                    if not await open_gallery(page, label):
                        continue
                    tiles, _ = await list_tiles(page, CHIP_PHOTOS * SCAN_FACTOR)
                    chips.append(label)
                    for t in tiles:
                        if len(out) >= n + CHIP_PHOTOS:
                            break
                        if t["url"] in seen:
                            continue
                        seen.add(t["url"])
                        last_id = await _one(page, img, place, d, t, px, per_author, last_id, out, skipped, by_author, oldest, stale, aged, oldest_aged)
                except (LoginRequired, CaptchaBlocked):
                    raise
                except Exception as e:  # a chip that does not open is skipped; the tabs already read stay
                    skipped[f"chip_error:{type(e).__name__}"] += 1
        complete = complete or len(out) >= n
        if out:
            for ph in stale:  # fresh photos exist: the old ones are not needed
                (d / ph["file"]).unlink(missing_ok=True)
        else:
            out = stale
        out = out + (aged or [])
        return {"fetched_at": now(), "wanted": n, "tabs": tabs, "complete": complete, "photos": out,
                "skipped": dict(skipped), "stale_fallback": True,
                **({"aged_years": aged_rule()["max_age_years"]} if aged is not None else {}), **({"chips": chips} if chips is not None else {})}
    finally:
        await page.close()
        await img.close()


async def _one(page: Page, img: Page, place: dict, d, t: dict, px: int, per_author: int, last_id: str | None,
               out: list, skipped: collections.Counter, by_author: collections.Counter, oldest: str,
               stale: list, aged: list | None = None, oldest_aged: str | None = None) -> str | None:
    """Open one tile, keep its photo; returns the viewer's photo id for the next wait."""
    await page.locator(f'{TILE}[data-photo-index="{t["index"]}"]').first.click()
    meta = await viewer_moved(page, last_id)
    if meta is None:
        skipped["no_metadata"] += 1
        return last_id
    if any(o["photo_id"] == meta["id"] for o in out):
        return meta["id"]
    when = month(meta["taken"]) or month(meta["posted"])
    is_old = bool(when and when < oldest)
    keep_aged = bool(is_old and aged is not None and when >= oldest_aged and len(aged) < AGED_KEEP)
    if is_old and not keep_aged:
        skipped["too_old"] += 1
        if len(stale) >= STALE_KEEP or out:
            return meta["id"]
    elif keep_aged:
        skipped["aged_kept"] += 1
    who = author_hash(meta["contributor"]) if meta["contributor"] else None
    if who and by_author[who] >= per_author:
        skipped["same_author"] += 1
        return meta["id"]
    url = sized(t["url"], px)
    r = await img.goto(url, timeout=30000)  # a browser tab: direct requests to the image host time out
    if not r or not r.ok or not (r.headers.get("content-type") or "").startswith("image/"):
        skipped["download"] += 1
        return meta["id"]
    f = d / "photos" / f"{safe_name(meta['id'])[:80]}.jpg"
    f.write_bytes(await r.body())
    row = {"photo_id": meta["id"], "file": f"photos/{f.name}", "url": url,
           "kind": "video" if t["video"] else "photo", "author_hash": who,
           "owner": bool(meta["name"]) and norm(meta["name"]) == norm(place.get("name")),
           "posted": meta["posted"], "taken": meta["taken"], "month": when}
    if keep_aged:
        aged.append(row | {"stale": True, "display_old": True})
        by_author[who] += 1
        return meta["id"]
    if is_old:
        stale.append(row | {"stale": True})
        return meta["id"]
    by_author[who] += 1
    out.append(row)
    return meta["id"]



def want(place: dict, c: dict) -> int:
    sights = set(c.get("photo_groups", []))
    n = c.get("photos_per_place", 20)
    return max(n, c.get("photos_per_sight", n)) if category_group(place.get("category")) in sights else n


def needs_fetch(f, wanted: int, default: int, chips: bool = False, aged: int | None = None) -> bool:
    """No photos.json yet, or one that stopped at a smaller cap than wanted now (a full gallery may hold more); with
    `chips`, also one whose category chips were not read yet."""
    if not f.exists():
        return True
    doc = json.loads(f.read_text(encoding="utf-8"))
    if chips and "chips" not in doc:
        return True
    if aged and doc.get("aged_years") != aged:  # the aged-photo rule was not applied to this file yet
        return True
    cap = doc.get("wanted", default)
    if not doc.get("photos") and not doc.get("stale_fallback") and (doc.get("skipped") or {}).keys() & {"too_old", "no_metadata"}:
        return True  # saved empty before the cover fallback existed (every photo old, or the viewer gave nothing): once more
    return wanted > cap and len(doc.get("photos", [])) >= cap


async def _place(ctx, d, place: dict, n: int, px: int, root, c: dict, throttle: Throttle) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        async with throttle:
            try:
                res = await scrape_photos(ctx, place, d, n, px)
                if not res["tabs"] and (d / FILE).exists() and json.loads((d / FILE).read_text(encoding="utf-8")).get("photos"):
                    raise RuntimeError("no gallery tab opened: kept the photos.json that has photos")
                write_json(d / FILE, res)
                throttle.success()
                return
            except LoginRequired:
                raise
            except Exception as e:
                if attempt < ATTEMPTS:
                    if type(e).__name__ == "TimeoutError" or isinstance(e, CaptchaBlocked):
                        throttle.blocked()
                    continue
                log_error(root, d.name, "photos", e)
                return
            finally:
                await pause(*c.get("pause_s", (2.0, 5.0)))


async def run(city: str, headed: bool = False, profile=open_profile, limit: int | None = None,
              shard: tuple[int, int] | None = None, profile_name: str | None = None) -> None:
    _, cfg = load_config(city)
    c, root = cfg["gmaps"], data_dir() / "gmaps"
    n, px = c.get("photos_per_place", 20), c.get("photo_px", 768)
    listed = root / "list" / f"{city}.json"
    keep = {safe_name(r["fid"]) for r in json.loads(listed.read_text(encoding="utf-8"))["items"]} if listed.exists() else None
    todo, wanted_of = [], {}
    targets = os.environ.get("GMAPS_PHOTO_TARGETS")  # JSON from scripts/photo_targets.py: thin places, most reviewed first
    if targets:
        doc = json.loads(open(targets, encoding="utf-8").read())
        for t in doc["places"]:
            f = root / "places" / t["dir"] / "place.json"
            if not f.exists():
                continue
            place = json.loads(f.read_text(encoding="utf-8"))
            if needs_fetch(f.parent / FILE, doc["wanted"], n, CHIPS, aged_rule()["max_age_years"] if aged_place(place) else None):
                todo.append((f.parent, place))
                wanted_of[f.parent.name] = doc["wanted"]
    else:
      for f in sorted((root / "places").glob("*/place.json")):
        if keep is not None and f.parent.name not in keep:
            continue
        place = json.loads(f.read_text(encoding="utf-8"))
        if needs_fetch(f.parent / FILE, want(place, c), n, False, aged_rule()["max_age_years"] if aged_place(place) else None):
            todo.append((f.parent, place))
    todo = todo[:limit] if limit is not None else todo
    if shard:  # one process per shard, each with its own browser (one Python process caps ~8 tabs)
        todo = todo[shard[0]::shard[1]]
    print(f"photos {city}: {len(todo)} places left" + (f" (shard {shard[0]}/{shard[1]})" if shard else ""))
    throttle = GateThrottle(root / "photos_throttle.json", start=c.get("tabs_start", 1), hi=c.get("photo_tabs", 3),
                        cooldown_s=c.get("cooldown_s", 60), max_cooldown_s=c.get("max_cooldown_s", 900))
    async with profile(profile_name or "gmaps", headed) as ctx:
        await ensure_login(ctx)
        try:
            async with asyncio.TaskGroup() as tg:
                for d, place in todo:
                    tg.create_task(_place(ctx, d, place, wanted_of.get(d.name) or want(place, c), px, root, c, throttle))
        except* LoginRequired as eg:
            raise eg.exceptions[0] from None
    done = sum((d / FILE).exists() for d, _ in todo)
    print(f"photos {city}: {done}/{len(todo)} done, the rest in errors.jsonl")
