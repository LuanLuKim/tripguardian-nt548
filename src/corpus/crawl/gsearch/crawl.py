"""Google web search through the repo's browser (docs/CORPUS.md §Nguồn, gsearch): one result page per (query, page).

Writes only data/gsearch/<city>/: results.jsonl (one line per page fetched: {at, query, page, url, n, results:[{rank,
url, title, snippet}], related, has_next, captcha_wait_s, raw}), raw/<hash>_p<page>.html (the page as loaded),
throttle.json, errors.jsonl. A (query, page) in results.jsonl younger than MAX_AGE_DAYS is not fetched again.

The browser profile is the Maps crawl's signed-in Google account (ACCOUNT, .browser/gmaps_a; cookies in
.browser/gmaps_a.json with CORPUS_PROFILE_STATE=1): a signed-in search meets fewer captchas, and a captcha a person
solved keeps its cookie for the next queries and runs. Google's /sorry/ page waits for the person (wait_for_person,
wait_s=None; reach the tab through chrome://inspect on CORPUS_DEBUG_PORT); headless without a port stops instead
(LoginRequired). The tab goes on with the page the person unlocked: no retry, no captcha handling in code.
"""

import asyncio
import hashlib
import json
import time
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

from ..common.browser import DEBUG_PORT, LoginRequired, open_profile, pause, wait_for_person
from ..common.files import append_jsonl, data_dir, log_error, now, write_bytes
from ..common.throttle import Throttle
from ..web import SearchPage, SearchResult
from .serp import parse

SOURCE = "gsearch"
ACCOUNT = "gmaps_a"  # browser profile: the Maps crawl's signed-in Google account (owner 2026-10-28)
ENGINE = "google-browser"
URL = "https://www.google.com/search?q={q}&hl=vi&gl=vn"
PER_PAGE = 10  # Google's page size: page n starts at (n - 1) * 10
TABS = 1  # one session: Google flags parallel queries from one IP at once
PAUSE_S = (4.0, 9.0)  # between two result pages of the same tab
MAX_AGE_DAYS = 30
RESULTS = "#rso, #botstuff, form#captcha-form"


def city_dir(city: str) -> Path:
    return data_dir() / SOURCE / city


def page_url(query: str, page: int) -> str:
    return URL.format(q=quote_plus(query)) + (f"&start={(page - 1) * PER_PAGE}" if page > 1 else "")


def _key(query: str) -> str:
    norm = " ".join(unicodedata.normalize("NFC", query).casefold().split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def key(query: str) -> str:
    """Public name of the query key results.jsonl is indexed by."""
    return _key(query)


def forbidden(html: str) -> bool:
    """Google's bare 403 page: a short block (no captcha to solve), not a search with no result."""
    return "Error 403 (Forbidden)" in html[:2000]


def _blocked_record(root: Path, rec: dict) -> bool:
    """An empty record whose saved page is the 403 page (written before fetch knew it): as good as never asked."""
    if rec.get("n") or not rec.get("raw"):
        return False
    raw = root / rec["raw"]
    return raw.exists() and raw.stat().st_size < 5000 and forbidden(raw.read_text(encoding="utf-8", errors="replace"))


def load(city: str, max_age_days: float = MAX_AGE_DAYS) -> dict[tuple[str, int], dict]:
    """(query key, page) -> the newest record younger than max_age_days."""
    path, out = city_dir(city) / "results.jsonl", {}
    if not path.exists():
        return out
    oldest = datetime.now(UTC) - timedelta(days=max_age_days)
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            if datetime.fromisoformat(rec["at"]) >= oldest and not _blocked_record(city_dir(city), rec):
                out[(_key(rec["query"]), int(rec["page"]))] = rec
        except (ValueError, KeyError, TypeError):
            continue
    return out


async def fetch(ctx, query: str, page_no: int, wait=wait_for_person) -> tuple[dict, str]:
    """One result page -> (record without `at`/`raw`, html). A captcha waits for the person, then the unlocked page
    is read as it is."""
    page = await ctx.new_page()
    try:
        url = page_url(query, page_no)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        waited = 0.0
        if "/sorry/" in page.url or parse(await page.content()).captcha:
            if DEBUG_PORT:
                print(f"gsearch: captcha, open chrome://inspect on DevTools port {DEBUG_PORT} and solve it", flush=True)
            start = time.monotonic()
            await wait(page, SOURCE, wait_s=None)
            waited = round(time.monotonic() - start, 1)
        try:
            await page.wait_for_selector(RESULTS, timeout=10000)
        except Exception:
            pass  # a page without results still gets parsed and recorded
        html = await page.content()
        serp = parse(html)
        if serp.captcha:  # still the block page after the wait: nothing to record
            raise LoginRequired(SOURCE)
        if forbidden(html):  # nothing to record either: the caller sees the query as unread and may ask again later
            raise RuntimeError("google 403")
        return {"query": query, "page": page_no, "url": url, "n": len(serp.results),
                "results": [{"rank": r.rank, "url": r.url, "title": r.title, "snippet": r.snippet}
                            for r in serp.results],
                "related": list(serp.related), "has_next": serp.has_next, "captcha_wait_s": waited}, html
    finally:
        await page.close()


async def crawl(queries: list[str], city: str = "dalat", pages: int = 1, headed: bool = False,
                account: str = ACCOUNT, profile=open_profile, wait=wait_for_person, pause_s: tuple[float, float] = PAUSE_S) -> dict:
    """Fetches the (query, page) pairs not recorded yet; pages of one query in order, page n+1 only when page n
    had a next link. Returns counts {fetched, cached, errors}. LoginRequired (a captcha nobody can solve) stops all."""
    root = city_dir(city)
    done = load(city)
    stats = {"fetched": 0, "cached": 0, "errors": 0}
    queries = list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))
    throttle = Throttle(root / "throttle.json", start=1, hi=TABS)

    async def one(ctx, query: str) -> None:
        for page_no in range(1, max(1, pages) + 1):
            rec = done.get((_key(query), page_no))
            if rec is None:
                async with throttle:
                    try:
                        rec, html = await fetch(ctx, query, page_no, wait)
                    except LoginRequired:
                        raise
                    except Exception as e:
                        log_error(root, f"{query}#p{page_no}", "search", e)
                        stats["errors"] += 1
                        return
                    finally:
                        await pause(*pause_s)
                raw = root / "raw" / f"{_key(query)}_p{page_no}.html"
                write_bytes(raw, html.encode("utf-8"))
                rec = {"at": now(), **rec, "raw": str(raw.relative_to(root))}
                append_jsonl(root / "results.jsonl", rec)
                done[(_key(query), page_no)] = rec
                stats["fetched"] += 1
                throttle.success()
            else:
                stats["cached"] += 1
            if not rec.get("has_next"):
                return

    if any((_key(q), p) not in done for q in queries for p in range(1, max(1, pages) + 1)):
        async with profile(account, headed) as ctx:
            try:
                async with asyncio.TaskGroup() as tg:
                    for q in queries:
                        tg.create_task(one(ctx, q))
            except* LoginRequired as eg:
                raise eg.exceptions[0] from None
    else:
        stats["cached"] = sum(1 for q in queries for p in range(1, max(1, pages) + 1) if (_key(q), p) in done)
    return stats


def to_search_page(query: str, records: list[dict], cached: bool = False) -> SearchPage:
    """Pages of one query, in page then rank order, as corpus.crawl.web's SearchPage (engine "google-browser")."""
    rows, seen = [], set()
    for rec in sorted(records, key=lambda r: r["page"]):
        for r in sorted(rec["results"], key=lambda r: r["rank"]):
            if r["url"] not in seen:
                seen.add(r["url"])
                rows.append(SearchResult(url=r["url"], title=r["title"], snippet=r["snippet"], engines=(ENGINE,)))
    return SearchPage(query=query, results=tuple(rows), cached=cached)


def search_pages(queries: list[str], city: str = "dalat", pages: int = 1, headed: bool = False,
                 **kw) -> list[SearchPage]:
    """Sync entry for corpus.crawl.web: one SearchPage per query. A query left unfetched because of a captcha
    nobody solved comes back blocked (no results, unresponsive google-browser: captcha)."""
    queries = [q.strip() for q in queries if q and q.strip()]
    before = load(city)
    try:
        asyncio.run(crawl(queries, city, pages, headed, **kw))
    except LoginRequired:
        pass
    after = load(city)
    out = []
    for q in queries:
        recs = [after[(_key(q), p)] for p in range(1, max(1, pages) + 1) if (_key(q), p) in after]
        if not recs:
            out.append(SearchPage(query=q, results=(), unresponsive=((ENGINE, "captcha"),)))
            continue
        out.append(to_search_page(q, recs, cached=all((_key(q), r["page"]) in before for r in recs)))
    return out


def run(city: str, queries: list[str], pages: int = 1, headed: bool = False, account: str = ACCOUNT) -> None:
    """CLI: python -m corpus gsearch run --query "..." | --from-file <file> [--pages N] [--profile gmaps_b2]."""
    t0 = time.monotonic()
    stats = asyncio.run(crawl(queries, city, pages, headed, account))
    recs = load(city)
    for q in dict.fromkeys(queries):
        n = sum(recs[(_key(q), p)]["n"] for p in range(1, pages + 1) if (_key(q), p) in recs)
        print(f"{n:3d} results  {q}")
    print(f"gsearch {city}: {stats['fetched']} pages fetched, {stats['cached']} cached, {stats['errors']} errors, "
          f"{time.monotonic() - t0:.0f}s")
