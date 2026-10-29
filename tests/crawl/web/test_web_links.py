"""corpus.crawl.web.links: a search result's URL -> video / discover slug / document / dropped."""

import re

import pytest

from corpus.crawl.web.links import canonical_url, classify, doc_id, slug_relevant

VID = "7433374830822526216"


@pytest.mark.parametrize("url, author", [
    (f"https://www.tiktok.com/@adinhsg/video/{VID}", "adinhsg"),
    (f"https://www.tiktok.com/@adinhsg/video/{VID}?lang=vi", "adinhsg"),
    (f"https://m.tiktok.com/@a.b_c/video/{VID}/", "a.b_c"),
])
def test_tiktok_video_urls(url, author):
    link = classify(url)
    assert link.kind == "video"
    assert link.video_id == VID
    assert link.author == author
    assert link.url == f"https://www.tiktok.com/@{author}/video/{VID}"


@pytest.mark.parametrize("url, reason", [
    ("https://www.tiktok.com/@du_lich_dalat", "tiktok_other"),
    (f"https://www.tiktok.com/@x/photo/{VID}", "photo"),
    ("https://vm.tiktok.com/ZS8abc/", "tiktok_other"),
    ("https://www.tiktok.com/tag/dalat", "tiktok_other"),
])
def test_tiktok_non_video_is_dropped(url, reason):
    link = classify(url)
    assert (link.kind, link.reason) == ("drop", reason)


@pytest.mark.parametrize("url, text", [
    ("https://www.tiktok.com/discover/du-l%E1%BB%8Bch-%C4%91%C3%A0-l%E1%BA%A1t", "du lịch đà lạt"),
    ("https://notes.tiktok.com/discover/du%20l%E1%BB%8Bch%20%C4%91%C3%A0%20l%E1%BA%A1t?region=vn", "du lịch đà lạt"),
    ("https://www.tiktok.com/vi-VN/discover/c%E1%BA%A3nh-%C4%91%C3%A0-l%E1%BA%A1t", "cảnh đà lạt"),
])
def test_discover_slug_variants(url, text):
    link = classify(url)
    assert link.kind == "discover"
    assert link.text == text


@pytest.mark.parametrize("text, ok", [
    ("thành phố đà lạt mới nhất 2026", True),
    ("dalat", True),
    ("coach mint ashton bag", False),
    ("เที่ยวดาลัด", False),
])
def test_slug_relevant(text, ok):
    assert slug_relevant(text, "Đà Lạt") is ok


@pytest.mark.parametrize("url, reason", [
    ("https://m.facebook.com/x", "social"),
    ("https://www.youtube.com/watch?v=1", "social"),
    ("https://www.instagram.com/p/1/", "social"),
    ("https://www.booking.com/hotel/vn/x.html", "ota"),
    ("https://www.agoda.com/vi-vn/x", "ota"),
])
def test_social_and_ota_dropped(url, reason):
    link = classify(url)
    assert (link.kind, link.reason) == ("drop", reason)


@pytest.mark.parametrize("url", ["https://www.klook.com/vi/blog/du-lich-da-lat/",
                                 "https://mytour.vn/vi/blog/bai-viet/x.html"])
def test_ota_blog_is_kept(url):
    assert classify(url).kind == "doc"


@pytest.mark.parametrize("url", ["https://vnexpress.net/x", "https://dalat.lamdong.gov.vn/x",
                                 "https://vi.wikipedia.org/wiki/%C4%90%C3%A0_L%E1%BA%A1t"])
def test_news_and_gov_are_docs(url):
    link = classify(url)
    assert link.kind == "doc"
    assert link.url == url


@pytest.mark.parametrize("url, reason", [("https://a.vn/x.pdf", "file"), ("ftp://a/b", "invalid"),
                                         ("not a url", "invalid")])
def test_file_and_invalid_dropped(url, reason):
    link = classify(url)
    assert (link.kind, link.reason) == ("drop", reason)


def test_canonical_and_doc_id():
    a, b = "https://www.A.vn/p/?utm_source=x&id=2#top", "https://a.vn/p?id=2"
    assert canonical_url(a) == canonical_url(b) == "https://a.vn/p?id=2"
    assert doc_id(a) == doc_id(b)
    assert re.fullmatch(r"[0-9a-f]{16}", doc_id(a))
