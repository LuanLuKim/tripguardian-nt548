from pathlib import Path

from corpus.crawl.gsearch import parse_serp

FIX = Path(__file__).parent / "fixtures"


def test_organic_results_in_rank_order_without_ads_dupes_or_google_links():
    serp = parse_serp((FIX / "serp_organic.html").read_text(encoding="utf-8"))
    assert not serp.captcha
    assert [r.url for r in serp.results] == ["https://www.tiktok.com/@an/video/7400000000000000001",
                                            "https://vnexpress.net/san-may-da-lat-123.html",
                                            "https://dalatblog.vn/cafe-san-may/"]
    assert [r.rank for r in serp.results] == [1, 2, 3]
    first = serp.results[0]
    assert first.title == "Quán cà phê săn mây đẹp nhất"
    assert first.snippet == "Đến lúc 5h sáng để săn mây ở Đà Lạt..."
    assert serp.results[1].snippet == "Những điểm săn mây quen thuộc."
    assert serp.results[2].snippet == ""  # no snippet on the page: empty, never made up
    assert serp.related == ("Săn mây Đà Lạt ở đâu đẹp nhất?", "Mấy giờ săn mây Đà Lạt?")
    assert serp.has_next


def test_sorry_page_is_a_captcha_with_no_results():
    serp = parse_serp((FIX / "sorry.html").read_text(encoding="utf-8"))
    assert serp.captcha
    assert serp.results == () and serp.related == () and not serp.has_next


def test_empty_page_is_not_a_captcha():
    serp = parse_serp("<html><body><div id='rso'></div></body></html>")
    assert not serp.captcha and serp.results == ()
