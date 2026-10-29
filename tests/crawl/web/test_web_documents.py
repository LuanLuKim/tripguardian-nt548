"""corpus.crawl.web documents: doc_urls.jsonl -> documents/<doc_id>.json split by heading (no network)."""

import json
import socket
from datetime import datetime

import httpx
import pytest

from corpus.crawl.web import Web
from corpus.crawl.web import documents
from corpus.crawl.web.documents import split_sections
from corpus.crawl.web.links import doc_id

PARA = "Thành phố ngàn hoa có khí hậu mát mẻ quanh năm, nhiều đồi thông và hồ nước đẹp. " * 5


@pytest.fixture(autouse=True)
def public_dns_no_pause(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("93.184.216.34", 80))])
    monkeypatch.setattr(documents, "_sleep", lambda s: None)


def setup(tmp_path, urls, handler):
    root = tmp_path / "web" / "dalat"
    root.mkdir(parents=True)
    (root / "doc_urls.jsonl").write_text("".join(json.dumps(
        {"url": u, "doc_id": doc_id(u), "domain": "vnexpress.net", "title": "t", "snippet": "", "query": "q Đà Lạt",
         "found_at": "2026-10-28T00:00:00+00:00"}, ensure_ascii=False) + "\n" for u in urls), encoding="utf-8")
    calls = []

    def counted(request):
        calls.append(request)
        return handler(request)
    client = httpx.Client(transport=httpx.MockTransport(counted))
    return root, calls, Web("http://search.test", tmp_path / "web" / "cache", client=client)


def html_page(request):
    body = (f"<html><head><title>Đà Lạt</title></head><body><article><h1>Đà Lạt</h1><p>{PARA}</p>"
            f"<h2>Đi mùa nào</h2><p>{PARA}</p></article></body></html>")
    return httpx.Response(200, text=body, headers={"content-type": "text/html"})


def test_split_sections():
    text = "Mở đầu\n\n## Đi mùa nào\nTháng 12\n\n## Trống\n\n## Ăn gì\n- Bánh căn"
    assert split_sections(text) == [{"heading": "", "text": "Mở đầu"},
                                    {"heading": "Đi mùa nào", "text": "Tháng 12"},
                                    {"heading": "Ăn gì", "text": "- Bánh căn"}]
    assert split_sections("chỉ một đoạn\ndòng hai") == [{"heading": "", "text": "chỉ một đoạn\ndòng hai"}]


def test_document_schema(tmp_path):
    url = "https://vnexpress.net/da-lat"
    root, _, web = setup(tmp_path, [url], html_page)
    stats = documents.run("dalat", web=web)
    doc = json.loads((root / "documents" / f"{doc_id(url)}.json").read_text(encoding="utf-8"))
    assert set(doc) == {"doc_id", "source_url", "domain", "title", "retrieved_at", "lang", "kind", "sections", "chars",
                        "cut", "query"}
    assert doc["doc_id"] == doc_id(url) and doc["source_url"] == url
    assert doc["kind"] == "web" and doc["lang"] == "vi" and doc["domain"] == "vnexpress.net"
    assert datetime.fromisoformat(doc["retrieved_at"]).utcoffset().total_seconds() == 0
    assert "Đi mùa nào" in [s["heading"] for s in doc["sections"]]
    assert doc["query"] == "q Đà Lạt"
    assert stats["ok"] == 1


def test_document_cut_at_40000(tmp_path):
    url = "https://vnexpress.net/long"
    root, _, web = setup(tmp_path, [url], lambda r: httpx.Response(200, text="x" * 60_000,
                                                                     headers={"content-type": "text/plain"}))
    stats = documents.run("dalat", web=web)
    doc = json.loads((root / "documents" / f"{doc_id(url)}.json").read_text(encoding="utf-8"))
    assert sum(len(s["text"]) for s in doc["sections"]) <= 40_000
    assert doc["cut"] is True and doc["chars"] == 60_000
    assert stats["cut"] == 1


def test_existing_document_not_fetched_again(tmp_path):
    _, calls, web = setup(tmp_path, ["https://vnexpress.net/a"], html_page)
    documents.run("dalat", web=web)
    documents.run("dalat", web=web)
    assert len(calls) == 1


def test_failed_page_logged_and_given_up_after_two(tmp_path):
    root, calls, web = setup(tmp_path, ["https://vnexpress.net/bad"], lambda r: httpx.Response(500))
    for run_no in (1, 2):
        documents.run("dalat", web=web)
        assert len(calls) == run_no
        errors = [json.loads(x) for x in (root / "errors.jsonl").read_text().splitlines()]
        assert len(errors) == run_no and errors[-1]["stage"] == "document"
    stats = documents.run("dalat", web=web)
    assert len(calls) == 2
    assert stats["skipped_failed"] == 1


def test_too_short_page_is_not_a_document(tmp_path):
    root, _, web = setup(tmp_path, ["https://vnexpress.net/short"],
                         lambda r: httpx.Response(200, text="x" * 100, headers={"content-type": "text/plain"}))
    stats = documents.run("dalat", web=web)
    assert not (root / "documents").exists() or not list((root / "documents").glob("*.json"))
    assert "TooShort" in (root / "errors.jsonl").read_text()
    assert stats["too_short"] == 1


def test_limit(tmp_path):
    _, calls, web = setup(tmp_path, [f"https://vnexpress.net/{i}" for i in range(3)], html_page)
    stats = documents.run("dalat", limit=2, web=web)
    assert len(calls) == 2
    assert stats["todo"] == 3
