"""corpus.events: the code gate and merge over the Extractor's events (docs/CORPUS.md §Sự kiện sắp tới)."""

from datetime import date

from corpus.events.gate import kept, merge, why_not

TODAY = date(2026, 11, 13)
PAGE = {"url": "https://dalat-info.gov.vn/a", "domain": "dalat-info.gov.vn", "title": "Festival",
        "text": "Festival Âm nhạc quốc tế Lang Biang năm 2026 dự kiến diễn ra từ ngày 13 - 15/11/2026 tại khu vực Đà Lạt. "
                "Lễ hội nhạc Jazz Việt Nam 2026 diễn ra từ ngày 6 đến 8/11. Phường Lang Biang tổ chức nhiều hoạt động tháng 11. "
                "K-Vietnam Wellness Festa & Expo in Dalat 2026 Fri, Nov 20 · TBD",
        "image": "https://dalat-info.gov.vn/a.jpg"}


def ev(name, start, end, quote, **kw):
    return {"name": name, "start": start, "end": end, "time": "", "venue": "", "summary": "", "quote": quote, **kw}


def test_an_event_stands_when_its_quote_holds_its_name_and_first_day():
    item = ev("Festival Âm nhạc quốc tế Lang Biang năm 2026", "2026-11-13", "2026-11-15",
              "Festival Âm nhạc quốc tế Lang Biang năm 2026 dự kiến diễn ra từ ngày 13 - 15/11/2026")
    assert why_not(item, PAGE["text"], TODAY, 60, "Đà Lạt") is None
    row = kept(item, PAGE, TODAY)
    assert row["image"] == PAGE["image"] and row["sources"][0]["domain"] == "dalat-info.gov.vn"


def test_an_english_month_name_counts_as_the_month():
    item = ev("K-Vietnam Wellness Festa & Expo in Dalat 2026", "2026-11-20", "2026-11-20",
              "K-Vietnam Wellness Festa & Expo in Dalat 2026 Fri, Nov 20")
    assert why_not(item, PAGE["text"], TODAY, 60, "Đà Lạt") is None


def test_what_the_gate_refuses():
    jazz = "Lễ hội nhạc Jazz Việt Nam 2026 diễn ra từ ngày 6 đến 8/11"
    assert why_not(ev("Lễ hội nhạc Jazz Việt Nam 2026", "2026-11-06", "2026-11-08", jazz), PAGE["text"], TODAY, 60, "Đà Lạt") == "over"
    ward = "Phường Lang Biang tổ chức nhiều hoạt động tháng 11"
    assert why_not(ev("phường Lang Biang - Đà Lạt", "2026-11-13", "", ward), PAGE["text"], TODAY, 60, "Đà Lạt") == "not an event's name"
    assert why_not(ev("Lễ hội nhạc Jazz Việt Nam 2026", "", "", jazz), PAGE["text"], TODAY, 60, "Đà Lạt") == "no day"
    made_up = ev("Festival Âm nhạc quốc tế Lang Biang", "2026-11-13", "", "Festival diễn ra 13/11 tại sân vận động")
    assert why_not(made_up, PAGE["text"], TODAY, 60, "Đà Lạt") == "quote not in the page"
    wrong_day = ev("Festival Âm nhạc quốc tế Lang Biang năm 2026", "2026-11-17", "2026-11-19",
                   "Festival Âm nhạc quốc tế Lang Biang năm 2026 dự kiến diễn ra từ ngày 13 - 15/11/2026")
    assert why_not(wrong_day, PAGE["text"], TODAY, 60, "Đà Lạt") == "quote does not hold its first day"


def row(name, start, end, domain, summary=""):
    return {"name": name, "start": start, "end": end, "time": "", "venue": "", "summary": summary, "image": "",
            "sources": [{"url": f"https://{domain}/{name}", "domain": domain, "title": "", "quote": "", "read": "2026-11-13"}]}


def test_one_event_on_several_pages_merges_and_keeps_its_whole_run_of_days():
    out = merge([row("Chương trình Âm nhạc quốc tế Lang Biang", "2026-11-14", "2026-11-14", "dalat.app"),
                 row("Festival Âm nhạc quốc tế Lang Biang năm 2026", "2026-11-13", "2026-11-15", "dalat-info.gov.vn", "Đêm chính 14/11")])
    assert len(out) == 1
    assert (out[0]["name"], out[0]["start"], out[0]["end"]) == ("Festival Âm nhạc quốc tế Lang Biang năm 2026", "2026-11-13", "2026-11-15")
    assert [s["domain"] for s in out[0]["sources"]] == ["dalat.app", "dalat-info.gov.vn"] and out[0]["summary"] == "Đêm chính 14/11"


def test_a_social_post_that_dates_the_event_otherwise_gives_way_to_the_site():
    out = merge([row("Festival Hoa Đà Lạt 2026", "2026-12-18", "2026-12-18", "facebook.com"),
                 row("Festival Hoa Đà Lạt lần thứ XI năm 2026", "2026-12-19", "2026-12-31", "hoadalattravel.vn")],
                social=("facebook.com",))
    assert [(e["start"], e["sources"][0]["domain"]) for e in out] == [("2026-12-19", "hoadalattravel.vn")]


def test_a_picture_two_events_share_is_the_sites_banner_and_is_dropped():
    a = {**row("Festival Âm nhạc quốc tế Lang Biang", "2026-11-13", "2026-11-15", "dalat.app"), "images": ["https://dalat.app/og.png"]}
    b = {**row("Festival Âm nhạc quốc tế Lang Biang năm 2026", "2026-11-13", "2026-11-15", "dalat-info.gov.vn"),
         "images": ["https://dalat-info.gov.vn/langbiang.jpg"]}
    c = {**row("Giải chạy vì Đà Lạt xanh", "2026-11-21", "2026-11-21", "dalat.app"), "images": ["https://dalat.app/og.png"]}
    out = merge([a, b, c])
    assert [(e["name"][:9], e["image"]) for e in out] == [("Festival ", "https://dalat-info.gov.vn/langbiang.jpg"), ("Giải chạy", "")]
