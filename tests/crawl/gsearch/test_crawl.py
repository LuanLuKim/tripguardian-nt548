import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import corpus.crawl.gsearch as gsearch
from corpus.crawl import LoginRequired


FIX = Path(__file__).parent / "fixtures"
ORGANIC = (FIX / "serp_organic.html").read_text(encoding="utf-8")
SORRY = (FIX / "sorry.html").read_text(encoding="utf-8")
LAST = ORGANIC.replace('<a id="pnnext" href="/search?q=x&amp;start=10">Tiếp</a>', "")


class FakePage:
    def __init__(self, site):
        self.site, self.url, self.html = site, "about:blank", ""

    async def goto(self, url, **kw):
        self.site.gotos.append(url)
        self.url, self.html = self.site.answer(url)

    async def content(self):
        return self.html

    async def wait_for_selector(self, sel, timeout=0):
        return None

    async def close(self):
        pass


class FakeSite:
    def __init__(self, answer):
        self.answer, self.gotos, self.opened, self.accounts = answer, [], 0, []

    def profile(self, headed_seen=None):
        @asynccontextmanager
        async def open_profile(source, headed=False):
            self.accounts.append(source)
            self.opened += 1
            ctx = type("Ctx", (), {})()

            async def new_page():
                return FakePage(self)

            ctx.new_page = new_page
            yield ctx
        return open_profile


def _organic(url):
    return url, (LAST if "start=10" in url else ORGANIC)


def test_crawl_records_pages_and_reuses_them(tmp_path):
    site = FakeSite(_organic)
    stats = asyncio.run(gsearch.crawl(["săn mây Đà Lạt"], "dalat", pages=2, profile=site.profile(), pause_s=(0, 0)))
    assert stats == {"fetched": 2, "cached": 0, "errors": 0}
    assert len(site.gotos) == 2 and site.gotos[1].endswith("&start=10")
    lines = [json.loads(x) for x in (tmp_path / "gsearch" / "dalat" / "results.jsonl").read_text().splitlines()]
    assert [(r["page"], r["n"], r["has_next"]) for r in lines] == [(1, 3, True), (2, 3, False)]
    assert lines[0]["results"][0] == {"rank": 1, "url": "https://www.tiktok.com/@an/video/7400000000000000001",
                                      "title": "Quán cà phê săn mây đẹp nhất",
                                      "snippet": "Đến lúc 5h sáng để săn mây ở Đà Lạt..."}
    assert lines[0]["related"] and lines[0]["captcha_wait_s"] == 0.0 and lines[0]["at"]
    assert (tmp_path / "gsearch" / "dalat" / lines[0]["raw"]).read_text(encoding="utf-8") == ORGANIC
    again = asyncio.run(gsearch.crawl(["săn mây Đà Lạt"], "dalat", pages=2, profile=site.profile(), pause_s=(0, 0)))
    assert again["fetched"] == 0 and len(site.gotos) == 2 and site.opened == 1  # no browser when all is recorded


def test_no_second_page_without_a_next_link():
    site = FakeSite(lambda url: (url, LAST))
    asyncio.run(gsearch.crawl(["q"], "dalat", pages=2, profile=site.profile(), pause_s=(0, 0)))
    assert len(site.gotos) == 1


def test_captcha_waits_for_the_person_then_reads_the_unlocked_page_without_retry():
    site = FakeSite(lambda url: ("https://www.google.com/sorry/index?continue=x", SORRY))
    waits = []

    async def person(page, source, wait_s=0):
        waits.append((source, wait_s))
        page.url, page.html = "https://www.google.com/search?q=q", LAST  # the person solved it

    stats = asyncio.run(gsearch.crawl(["q"], "dalat", profile=site.profile(), wait=person, pause_s=(0, 0)))
    assert waits == [("gsearch", None)] and len(site.gotos) == 1 and stats["fetched"] == 1
    (rec,) = gsearch.load("dalat").values()
    assert rec["n"] == 3 and rec["captcha_wait_s"] >= 0


def test_search_pages_gives_web_search_pages_and_blocked_on_unsolved_captcha():
    site = FakeSite(lambda url: (url, LAST) if "ok" in url else ("https://www.google.com/sorry/index", SORRY))

    async def nobody(page, source, wait_s=0):
        raise LoginRequired(source)

    first = gsearch.search_pages(["ok query"], "dalat", profile=site.profile(), wait=nobody, pause_s=(0, 0))
    assert first[0].cached is False and not first[0].blocked
    assert [r.engines for r in first[0].results] == [("google-browser",)] * 3
    assert first[0].results[1].url == "https://vnexpress.net/san-may-da-lat-123.html"
    pages = gsearch.search_pages(["ok query", "bad query"], "dalat", profile=site.profile(), wait=nobody,
                                 pause_s=(0, 0))
    assert pages[0].cached is True and len(pages[0].results) == 3
    assert pages[1].blocked and pages[1].unresponsive == (("google-browser", "captcha"),)


def test_searches_signed_in_on_the_maps_account_by_default():
    site = FakeSite(_organic)
    asyncio.run(gsearch.crawl(["q"], "dalat", profile=site.profile(), pause_s=(0, 0)))
    asyncio.run(gsearch.crawl(["q2"], "dalat", account="gmaps_b2", profile=site.profile(), pause_s=(0, 0)))
    assert site.accounts == ["gmaps_a", "gmaps_b2"]


def test_public_api_names():
    assert set(gsearch.__all__) == {"ENGINE", "Serp", "SerpResult", "crawl", "key", "load", "panel", "parse_serp", "places",
                                    "run", "search_pages", "to_search_page"}


def test_a_saved_403_page_is_not_a_cached_answer(tmp_path, monkeypatch):
    import importlib
    from datetime import UTC, datetime
    crawl = importlib.import_module("corpus.crawl.gsearch.crawl")
    monkeypatch.setattr(crawl, "city_dir", lambda city: tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "blocked.html").write_text("<title>Error 403 (Forbidden)!!1</title>", encoding="utf-8")
    (tmp_path / "raw" / "empty.html").write_text("<div id=rso></div>", encoding="utf-8")
    at = datetime.now(UTC).isoformat()
    lines = [{"at": at, "query": "a", "page": 1, "n": 0, "raw": "raw/blocked.html"},
             {"at": at, "query": "b", "page": 1, "n": 0, "raw": "raw/empty.html"}]
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in lines), encoding="utf-8")
    assert {r["query"] for r in crawl.load("dalat").values()} == {"b"}
