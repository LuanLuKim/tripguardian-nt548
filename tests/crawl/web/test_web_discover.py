"""corpus.crawl.web discover: the web search phase writes video URLs, discover slugs and document URLs (no network)."""

import json

import httpx

from corpus.crawl.web import Query, Web
from corpus.crawl.web import discover
from corpus.crawl.web.queries import query_hash

NEW, KNOWN = "7433374830822526216", "7433374830822526999"
SPLIT = {"results": [
    {"url": f"https://www.tiktok.com/@a/video/{NEW}", "title": "new video", "engines": ["duckduckgo"]},
    {"url": f"https://www.tiktok.com/@b/video/{KNOWN}", "title": "known video", "engines": ["duckduckgo"]},
    {"url": "https://www.tiktok.com/@du_lich_dalat", "title": "profile", "engines": ["duckduckgo"]},
    {"url": "https://www.tiktok.com/discover/du-l%E1%BB%8Bch-%C4%91%C3%A0-l%E1%BA%A1t", "title": "slug",
     "engines": ["duckduckgo"]},
    {"url": "https://www.tiktok.com/discover/coach-mint-bag", "title": "off topic", "engines": ["duckduckgo"]},
    {"url": "https://facebook.com/x", "title": "fb", "engines": ["duckduckgo"]},
    {"url": "https://vnexpress.net/p?utm_source=x", "title": "bài báo", "content": "tóm tắt", "engines": ["bing"]},
    {"url": "https://www.vnexpress.net/p", "title": "bài báo lại", "engines": ["bing"]},
]}
BLOCKED = {"results": [], "unresponsive_engines": [["brave", "Suspended: too many requests"]]}
OK = {"results": [{"url": "https://vnexpress.net/ok", "title": "ok", "engines": ["bing"]}]}


def make_web(tmp_path, handler, daily_queries=100):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Web("http://search.test", tmp_path / "web" / "cache", client=client, state_dir=tmp_path / "web",
               daily_queries=daily_queries, min_interval_s=0)


def counting(payloads):
    """Handler that answers the payloads in turn (the last one repeats) and records each request."""
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payloads[min(len(calls), len(payloads)) - 1])
    return calls, handler


def q(text, group="g"):
    return Query(text, group, "seed")


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def test_search_splits_links_and_writes_files(tmp_path):
    (tmp_path / "tiktok" / "videos" / KNOWN).mkdir(parents=True)
    _, handler = counting([SPLIT])
    stats = discover.run("dalat", queries=[q("site:tiktok.com du lịch Đà Lạt")], web=make_web(tmp_path, handler))
    root = tmp_path / "web" / "dalat"
    videos = rows(root / "tiktok_urls.jsonl")
    assert [v["video_id"] for v in videos] == [NEW]
    assert videos[0]["url"] == f"https://www.tiktok.com/@a/video/{NEW}"
    assert videos[0]["query"] == "site:tiktok.com du lịch Đà Lạt" and videos[0]["found_at"]
    slugs = rows(root / "discover_slugs.jsonl")
    assert [(s["text"], s["slug"]) for s in slugs] == [("du lịch đà lạt", "du-lich-da-lat")]
    docs = rows(root / "doc_urls.jsonl")
    assert [d["domain"] for d in docs] == ["vnexpress.net"]
    saved = json.loads((root / "search" / f"{query_hash('site:tiktok.com du lịch Đà Lạt')}.json").read_text())
    assert len(saved["results"]) == 8
    assert [r["kind"] for r in saved["results"]][:3] == ["video", "video", "drop"]
    assert saved["results"][2]["reason"] == "tiktok_other"
    (y,) = rows(root / "query_yield.jsonl")
    assert (y["videos_total"], y["videos_new"], y["slugs_new"], y["docs_new"], y["new"]) == (2, 1, 1, 1, 3)
    assert stats["dropped"] == {"tiktok_other": 1, "social": 1, "slug_offtopic": 1}
    assert stats["videos_known"] == 1
    assert stats["stop_reason"] is None


def test_second_run_is_free_and_idempotent(tmp_path):
    calls, handler = counting([SPLIT])
    web = make_web(tmp_path, handler)
    root = tmp_path / "web" / "dalat"
    discover.run("dalat", queries=[q("đà lạt")], web=web)
    before = {p.name: len(rows(p)) for p in root.glob("*.jsonl")}
    stats = discover.run("dalat", queries=[q("đà lạt")], web=web)
    assert len(calls) == 1
    assert {p.name: len(rows(p)) for p in root.glob("*.jsonl")} == before
    assert stats["resumed"] == 1


def test_stops_cleanly_when_budget_exhausted(tmp_path):
    calls, handler = counting([OK])
    stats = discover.run("dalat", queries=[q("a"), q("b"), q("c")], web=make_web(tmp_path, handler, daily_queries=1))
    assert stats["stop_reason"] == "budget"
    assert len(list((tmp_path / "web" / "dalat" / "search").glob("*.json"))) == 1
    assert len(calls) == 1
    assert stats["network"] == 1


def test_stops_after_three_blocked(tmp_path):
    calls, handler = counting([BLOCKED])
    stats = discover.run("dalat", queries=[q(x) for x in "abcde"], web=make_web(tmp_path, handler))
    root = tmp_path / "web" / "dalat"
    assert stats["stop_reason"] == "engines_blocked"
    assert len(calls) == 3
    assert not list((root / "search").glob("*.json"))
    assert stats["blocked_engines"] == {"brave": 3}
    assert len(rows(root / "errors.jsonl")) == 3
    assert [r["blocked_engines"] for r in rows(root / "query_yield.jsonl")] == [["brave"]] * 3


def test_blocked_then_ok_resets_counter(tmp_path):
    calls, handler = counting([BLOCKED, BLOCKED, OK, BLOCKED, BLOCKED, OK])
    stats = discover.run("dalat", queries=[q(x) for x in "abcde"], web=make_web(tmp_path, handler))
    assert stats["stop_reason"] is None
    assert len(calls) == 5


def test_limit_counts_only_network_queries(tmp_path):
    calls, handler = counting([OK])
    web = make_web(tmp_path, handler)
    discover.run("dalat", queries=[q("a"), q("b")], web=web)
    stats = discover.run("dalat", limit=1, queries=[q("a"), q("b"), q("c"), q("d"), q("e")], web=web)
    assert len(calls) == 3
    assert stats["network"] == 1 and stats["resumed"] == 2
    assert stats["stop_reason"] == "limit"


def test_known_video_ids_reads_every_tiktok_source(tmp_path):
    assert discover.known_video_ids() == set()
    t = tmp_path / "tiktok"
    (t / "videos" / "111").mkdir(parents=True)
    for rel, text in [("place_search/dalat/x.json", '{"items": [{"video_id": "222"}]}'),
                      ("poi_crawl/y.json", '{"videos": [{"video_id":"333"}]}'),
                      ("search/dalat/q.jsonl", '{"video_id": "444"}\n')]:
        (t / rel).parent.mkdir(parents=True, exist_ok=True)
        (t / rel).write_text(text)
    assert discover.known_video_ids() == {"111", "222", "333", "444"}


def test_run_with_explicit_queries_skips_planning(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("planned")
    monkeypatch.setattr(discover, "plan", boom)
    _, handler = counting([OK])
    stats = discover.run("dalat", queries=[q("a")], web=make_web(tmp_path, handler))
    assert stats["planned"] == 1
