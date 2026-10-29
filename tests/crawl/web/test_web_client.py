"""corpus.crawl.web client: search_page, daily budget, pause, engine log, read_document (no network)."""

import json
import socket

import httpx
import pytest

from corpus.crawl.web import BudgetExhausted, Web, WebError

PAYLOAD = {
    "results": [
        {"url": "https://www.tiktok.com/@a/video/7433374830822526216", "title": "A", "content": "a",
         "engines": ["duckduckgo"]},
        {"url": "https://www.tiktok.com/@b/video/7433374830822526217", "title": "B", "content": "b",
         "engines": ["duckduckgo", "google cse"]},
        {"url": "https://www.tiktok.com/discover/du-lich-da-lat", "title": "C", "content": "c", "engines": []},
    ],
    "unresponsive_engines": [["brave", "Suspended: too many requests"]],
}
BLOCKED = {"results": [], "unresponsive_engines": [["brave", "Suspended: too many requests"]]}


class Clock:
    def __init__(self):
        self.t = 100.0
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)


def make(tmp_path, handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Web("http://search.test", tmp_path / "cache", client=client, **kwargs)


def counting(payload):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)
    return calls, handler


def state(tmp_path, **kwargs):
    clock = Clock()
    return clock, {"state_dir": tmp_path, "clock": clock, "sleep": clock.sleep, "today": lambda: "2026-10-28",
                   **kwargs}


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_search_page_returns_every_result_and_engines(tmp_path):
    _, handler = counting(PAYLOAD)
    page = make(tmp_path, handler).search_page("site:tiktok.com đà lạt")
    assert len(page.results) == 3
    assert page.results[0].engines == ("duckduckgo",)
    assert page.unresponsive == (("brave", "Suspended: too many requests"),)
    assert page.cached is False and page.blocked is False


def test_search_page_logs_engines(tmp_path):
    _, handler = counting(PAYLOAD)
    _, kw = state(tmp_path, daily_queries=10)
    make(tmp_path, handler, **kw).search_page("đà lạt")
    rows = lines(tmp_path / "engines.jsonl")
    assert len(rows) == 1
    assert rows[0]["n"] == 3
    assert rows[0]["engines"] == {"duckduckgo": 2, "google cse": 1}
    assert rows[0]["unresponsive"] == [["brave", "Suspended: too many requests"]]


def test_cache_hit_is_free(tmp_path):
    calls, handler = counting(PAYLOAD)
    clock, kw = state(tmp_path, daily_queries=10, min_interval_s=2.0)
    web = make(tmp_path, handler, **kw)
    web.search_page("đà lạt")
    second = web.search_page("đà lạt")
    assert len(calls) == 1
    assert second.cached is True
    assert json.loads((tmp_path / "budget.json").read_text())["used"] == 1
    assert len(lines(tmp_path / "engines.jsonl")) == 1
    assert clock.sleeps == []


def test_blocked_page_is_not_cached(tmp_path):
    calls, handler = counting(BLOCKED)
    _, kw = state(tmp_path, daily_queries=10)
    web = make(tmp_path, handler, **kw)
    assert web.search_page("đà lạt").blocked is True
    web.search_page("đà lạt")
    assert len(calls) == 2
    assert json.loads((tmp_path / "budget.json").read_text())["used"] == 2


def test_budget_exhausted_raises(tmp_path):
    calls, handler = counting(PAYLOAD)
    _, kw = state(tmp_path, daily_queries=2)
    web = make(tmp_path, handler, **kw)
    web.search_page("a")
    web.search_page("b")
    with pytest.raises(BudgetExhausted, match="2/2"):
        web.search_page("c")
    assert len(calls) == 2
    assert web.search_page("a").cached is True


def test_budget_resets_on_new_day(tmp_path):
    _, handler = counting(PAYLOAD)
    day = {"v": "2026-10-28"}
    clock = Clock()
    web = make(tmp_path, handler, state_dir=tmp_path, daily_queries=2, clock=clock, sleep=clock.sleep,
               today=lambda: day["v"])
    web.search_page("a")
    web.search_page("b")
    assert web.budget_left() == 0
    day["v"] = "2026-10-29"
    assert web.budget_left() == 2
    web.search_page("c")
    assert json.loads((tmp_path / "budget.json").read_text()) == {"day": "2026-10-29", "used": 1}


def test_min_interval_sleeps_between_real_queries(tmp_path):
    _, handler = counting(PAYLOAD)
    clock, kw = state(tmp_path, min_interval_s=2.0)
    web = make(tmp_path, handler, **kw)
    web.search_page("a")
    assert clock.sleeps == []
    clock.t += 0.5
    web.search_page("b")
    assert clock.sleeps == [pytest.approx(1.5)]


def test_failed_request_counts_and_raises(tmp_path):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)
    _, kw = state(tmp_path, daily_queries=10)
    with pytest.raises(WebError):
        make(tmp_path, handler, **kw).search_page("a")
    assert json.loads((tmp_path / "budget.json").read_text())["used"] == 1
    assert "error" in lines(tmp_path / "engines.jsonl")[0]


def test_plain_web_has_no_budget_and_no_log(tmp_path):
    _, handler = counting(PAYLOAD)
    web = make(tmp_path, handler)
    web.search_page("a")
    assert not (tmp_path / "budget.json").exists()
    assert not (tmp_path / "engines.jsonl").exists()
    assert not list(tmp_path.glob("**/engines.jsonl"))
    assert web.budget_left() is None


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("93.184.216.34", 80))])


def test_read_document_keeps_headings(tmp_path, public_dns):
    para = "Thành phố ngàn hoa có khí hậu mát mẻ quanh năm, nhiều đồi thông và hồ nước đẹp. " * 4
    body = (f"<html><head><title>Đà Lạt</title></head><body><article><h1>Đà Lạt</h1><p>{para}</p>"
            f"<h2>Đi mùa nào</h2><p>{para}</p></article></body></html>")
    web = make(tmp_path, lambda r: httpx.Response(200, text=body, headers={"content-type": "text/html"}))
    doc = web.read_document("http://example.test/da-lat")
    assert "\n## Đi mùa nào\n" in doc.text
    assert doc.lang == "vi"
    assert doc.cut is False
    assert doc.domain == "example.test"


def test_read_document_cuts_and_flags(tmp_path, public_dns):
    text = "x" * 60_000
    web = make(tmp_path, lambda r: httpx.Response(200, text=text, headers={"content-type": "text/plain"}))
    doc = web.read_document("http://example.test/long.txt", max_chars=40_000)
    assert len(doc.text) == 40_000
    assert doc.chars == 60_000
    assert doc.cut is True


def test_from_config_uses_root_dirs(tmp_path):
    _, handler = counting(PAYLOAD)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = {"base_url": "http://search.test", "timeout_s": 10.0, "cache_ttl_days": 30, "daily_queries": 300,
           "min_interval_s": 0.0}
    web = Web.from_config(cfg, tmp_path / "web", client=client)
    web.search_page("a")
    assert list((tmp_path / "web" / "cache").glob("*.json"))
    assert web.daily_queries == 300
    assert (tmp_path / "web" / "budget.json").exists()


SERP = {"organic_results": [{"link": "https://vnexpress.net/a", "title": "A", "snippet": "a"},
                            {"link": "https://www.tiktok.com/@u/video/7433374830822526216", "title": "V"}]}


def serp_web(tmp_path, serp_payload=SERP, serp_status=200, monthly=5, **kw):
    calls = {"searx": 0, "serp": 0}

    def handler(request):
        if request.url.host == "serpapi.com":
            calls["serp"] += 1
            assert request.url.params["api_key"] == "SECRETKEY123" and request.url.params["engine"] == "google"
            return httpx.Response(serp_status, json=serp_payload)
        calls["searx"] += 1
        return httpx.Response(200, json=BLOCKED)
    _, state_kw = state(tmp_path, daily_queries=10)
    return calls, make(tmp_path, handler, serpapi_key="SECRETKEY123", serpapi_monthly=monthly, **state_kw, **kw)


def test_serpapi_answers_when_every_engine_is_blocked(tmp_path):
    calls, web = serp_web(tmp_path)
    page = web.search_page("đà lạt")
    assert page.blocked is False
    assert [r.url for r in page.results] == ["https://vnexpress.net/a",
                                             "https://www.tiktok.com/@u/video/7433374830822526216"]
    assert page.results[0].engines == ("serpapi",)
    assert json.loads((tmp_path / "serpapi.json").read_text())["used"] == 1
    assert lines(tmp_path / "engines.jsonl")[-1]["fallback"] == "serpapi"
    assert web.search_page("đà lạt").cached is True
    assert calls == {"searx": 1, "serp": 1}


def test_serpapi_monthly_cap_keeps_the_blocked_page(tmp_path):
    calls, web = serp_web(tmp_path, monthly=1)
    web.search_page("a")
    assert web.search_page("b").blocked is True
    assert calls["serp"] == 1


def test_serpapi_failure_keeps_the_blocked_page(tmp_path):
    calls, web = serp_web(tmp_path, serp_status=500)
    page = web.search_page("a")
    assert page.blocked is True
    assert "serpapi" in lines(tmp_path / "engines.jsonl")[-1]["fallback_error"]
    assert "SECRETKEY123" not in (tmp_path / "engines.jsonl").read_text()


def test_no_serpapi_without_key(tmp_path):
    calls, handler = counting(BLOCKED)
    _, kw = state(tmp_path, daily_queries=10)
    assert make(tmp_path, handler, **kw).search_page("a").blocked is True
    assert not (tmp_path / "serpapi.json").exists()


def test_from_config_reads_serpapi_key_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SerpAPI_API_KEY", "secret")
    cfg = {"base_url": "http://search.test", "daily_queries": 300, "serpapi_monthly": 200}
    web = Web.from_config(cfg, tmp_path / "web", client=httpx.Client(transport=httpx.MockTransport(lambda r: None)))
    assert web.serpapi_key == "secret" and web.serpapi_monthly == 200


# Google through the browser (corpus.crawl.gsearch) between SearXNG and SerpApi.
from corpus.crawl.web import SearchPage, SearchResult  # noqa: E402

THIN = {"results": [{"url": "https://vnexpress.net/a", "title": "A", "engines": ["bing"]},
                    {"url": "https://vnexpress.net/b", "title": "B", "engines": ["bing"]}],
        "unresponsive_engines": [["brave", "Suspended: too many requests"]]}
GOOGLE = (SearchResult(url="https://vnexpress.net/b", title="B", snippet="", engines=("google-browser",)),
          SearchResult(url="https://www.tiktok.com/@u/video/7433374830822526216", title="V", snippet="",
                       engines=("google-browser",)))


def google_web(tmp_path, searx=BLOCKED, google_page="ok", monthly=5):
    """Web with a fake SearXNG answer, a fake gsearch and a fake SerpApi; returns (calls, web)."""
    calls = {"searx": 0, "google": [], "serp": 0}

    def handler(request):
        if request.url.host == "serpapi.com":
            calls["serp"] += 1
            return httpx.Response(200, json=SERP)
        calls["searx"] += 1
        return httpx.Response(200, json=searx)

    def google(query):
        calls["google"].append(query)
        if google_page == "error":
            raise RuntimeError("profile in use")
        if google_page == "blocked":
            return SearchPage(query=query, results=(), unresponsive=(("google-browser", "captcha"),))
        return SearchPage(query=query, results=GOOGLE)
    _, kw = state(tmp_path, daily_queries=10)
    return calls, make(tmp_path, handler, serpapi_key="SECRETKEY123", serpapi_monthly=monthly, google=google, **kw)


def test_google_answers_a_blocked_searxng_page_before_serpapi(tmp_path):
    calls, web = google_web(tmp_path)
    page = web.search_page("đà lạt")
    assert page.blocked is False and page.cached is False
    assert [r.engines for r in page.results] == [("google-browser",), ("google-browser",)]
    assert calls["google"] == ["đà lạt"] and calls["serp"] == 0
    assert lines(tmp_path / "engines.jsonl")[-1]["fallback"] == "google-browser"
    assert web.search_page("đà lạt").cached is True
    assert calls["searx"] == 1 and len(calls["google"]) == 1


def test_google_adds_to_a_thin_searxng_page(tmp_path):
    calls, web = google_web(tmp_path, searx=THIN)
    page = web.search_page("a")
    assert [r.url for r in page.results] == ["https://vnexpress.net/a", "https://vnexpress.net/b",
                                             "https://www.tiktok.com/@u/video/7433374830822526216"]
    assert page.results[1].engines == ("bing", "google-browser")
    assert calls["serp"] == 0


def test_google_is_not_asked_when_searxng_has_three_results(tmp_path):
    calls, web = google_web(tmp_path, searx=PAYLOAD)
    assert len(web.search_page("a").results) == 3
    assert calls["google"] == []


def test_serpapi_answers_only_when_google_is_blocked_too(tmp_path):
    calls, web = google_web(tmp_path, google_page="blocked")
    page = web.search_page("a")
    assert page.results[0].engines == ("serpapi",)
    assert ("google-browser", "captcha") in page.unresponsive
    assert calls["serp"] == 1


def test_google_failure_falls_through_to_serpapi_and_is_logged(tmp_path):
    calls, web = google_web(tmp_path, google_page="error")
    page = web.search_page("a")
    assert page.results[0].engines == ("serpapi",)
    assert "google-browser" in lines(tmp_path / "engines.jsonl")[-1]["fallback_error"]


def test_thin_page_with_google_blocked_keeps_serpapi_quota(tmp_path):
    calls, web = google_web(tmp_path, searx=THIN, google_page="blocked")
    page = web.search_page("a")
    assert [r.url for r in page.results] == ["https://vnexpress.net/a", "https://vnexpress.net/b"]
    assert calls["serp"] == 0


def test_from_config_with_city_uses_gsearch(tmp_path, monkeypatch):
    from corpus.crawl import gsearch
    asked = []

    def fake_search_pages(queries, city, **kw):
        asked.append((list(queries), city))
        return [SearchPage(query=queries[0], results=GOOGLE)]
    monkeypatch.setattr(gsearch, "search_pages", fake_search_pages)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=BLOCKED)))
    cfg = {"base_url": "http://search.test", "daily_queries": 300}
    page = Web.from_config(cfg, tmp_path / "web", client=client, city="dalat").search_page("q")
    assert asked == [(["q"], "dalat")] and len(page.results) == 2
    plain = Web.from_config(cfg, tmp_path / "web2", client=client)
    assert plain.search_page("q").blocked is True and len(asked) == 1
