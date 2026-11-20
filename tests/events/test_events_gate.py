"""corpus.events: the code gate and merge over the Extractor's events (docs/CORPUS.md §Sự kiện sắp tới)."""

from datetime import date

from corpus.events import gate
from corpus.events.gate import fold_parts, kept, merge, why_not

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


def test_an_event_held_outside_the_city_is_refused_and_an_old_answer_without_the_field_stands():
    jazz = "Lễ hội nhạc Jazz Việt Nam 2026 diễn ra từ ngày 6 đến 8/11"
    away = ev("Lễ hội nhạc Jazz Việt Nam 2026", "2026-11-06", "2026-11-08", jazz, in_city=False)
    assert why_not({**away, "in_city": False}, PAGE["text"], date(2026, 11, 1), 60, "Đà Lạt") == "not in the city"
    assert why_not({**away, "in_city": True}, PAGE["text"], date(2026, 11, 1), 60, "Đà Lạt") is None
    old = {k: v for k, v in away.items() if k != "in_city"}
    assert why_not(old, PAGE["text"], date(2026, 11, 1), 60, "Đà Lạt") is None


def row(name, start, end, domain, summary=""):
    return {"name": name, "start": start, "end": end, "time": "", "venue": "", "summary": summary, "image": "",
            "sources": [{"url": f"https://{domain}/{name}", "domain": domain, "title": "", "quote": "", "read": "2026-11-13"}]}


def test_one_event_on_several_pages_merges_and_keeps_its_whole_run_of_days():
    out = merge([row("Chương trình Âm nhạc quốc tế Lang Biang", "2026-11-14", "2026-11-14", "dalat.app"),
                 row("Festival Âm nhạc quốc tế Lang Biang năm 2026", "2026-11-13", "2026-11-15", "dalat-info.gov.vn", "Đêm chính 14/11")])
    assert len(out) == 1
    assert (out[0]["name"], out[0]["start"], out[0]["end"]) == ("Festival Âm nhạc quốc tế Lang Biang năm 2026", "2026-11-13", "2026-11-15")
    assert {s["domain"] for s in out[0]["sources"]} == {"dalat.app", "dalat-info.gov.vn"} and out[0]["summary"] == "Đêm chính 14/11"
    assert "parts" not in out[0]  # the main night's page names the festival itself, not a programme of it


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


def test_a_search_result_that_never_names_the_city_is_not_read_for_events():
    from corpus.events.run import pages

    class Hit:
        def __init__(self, url, title, snippet):
            self.url, self.domain, self.title, self.snippet, self.image = url, "x.vn", title, snippet, ""

    class Web:
        def search(self, q, k, per_domain):
            return [Hit("https://x.vn/a", "Lịch lễ hội tháng 11", "Festival tại Đà Lạt"), Hit("https://x.vn/b", "Lễ hội Huế", "Festival Huế"),
                    Hit("https://x.vn/dalat-c", "Sự kiện", "lịch")]

    got = pages(Web(), ["q"], {"results_per_query": 3, "pages": 0, "social": [], "page_chars": 100}, "Đà Lạt")
    assert [x["url"] for x in got] == ["https://x.vn/a", "https://x.vn/dalat-c"]


def test_a_night_when_every_page_fails_to_extract_keeps_the_last_snapshot(tmp_path, monkeypatch):
    import pytest
    import importlib
    events_run = importlib.import_module("corpus.events.run")

    class Page:
        url, domain, title, snippet, image = "https://x.vn/dalat", "x.vn", "Đà Lạt", "Đà Lạt lịch", ""

    class Web:
        def search(self, q, k, per_domain):
            return [Page()]

    async def ask(**_):
        raise TimeoutError

    monkeypatch.setattr(events_run, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(events_run, "load_config", lambda city: ("Đà Lạt", {"web": {"base_url": "", "timeout_s": 1, "min_interval_s": 0}}))
    with pytest.raises(RuntimeError, match="snapshot kept"):
        events_run.run("dalat", TODAY, web=Web(), ask=ask)
    assert not (tmp_path / "dalat" / "events" / "latest.json").exists()


def test_a_ceremony_joins_the_festival_it_opens_instead_of_standing_as_an_event():
    festival = {**kept(ev("Festival Hoa Đà Lạt lần thứ XI năm 2026", "2026-12-19", "2026-12-31", "q"), PAGE, TODAY),
                "venue": "Quảng trường Lâm Viên", "image": "https://x/f.jpg"}
    night = {**kept(ev("Đêm Khai mạc", "2026-12-19", "2026-12-19", "q"), PAGE, TODAY),
             "venue": "Quảng trường Lâm Viên, phường Xuân Hương – Đà Lạt", "image": ""}
    other = {**kept(ev("Carnival Ban nhạc", "2026-12-31", "2026-12-31", "q"), PAGE, TODAY), "venue": "hồ Xuân Hương", "image": ""}
    out = fold_parts([festival, night, other])
    assert [e["name"] for e in out] == [festival["name"], "Carnival Ban nhạc"]  # a named event is left alone
    assert [(p["name"], p["start"]) for p in out[0]["parts"]] == [("Đêm Khai mạc", "2026-12-19")]
    alone = {**kept(ev("Đêm Khai mạc", "2026-12-19", "2026-12-19", "q"), PAGE, TODAY), "venue": "Quảng trường Lâm Viên"}
    assert fold_parts([alone])[0]["name"] == "Đêm Khai mạc"  # no festival holds it: stays as the page wrote it


def test_the_flower_festival_under_its_english_name_and_its_programmes_are_one_event():
    """The 17/11/2026 snapshot listed Festival Hoa five times: in English, as its flower space, its opening night, its
    closing night and as itself."""
    def at(name, start, end, domain, venue="", part_of=""):
        return {**row(name, start, end, domain), "venue": venue, **({"part_of": part_of} if part_of else {})}
    out = merge([
        at("Da Lat Flower Festival", "2026-12-01", "2027-01-31", "dalat.app", "Lam Vien Square and Xuan Huong Lake"),
        at("Không gian hoa", "2026-12-18", "2027-01-03", "ivivu.com", "xung quanh trung tâm Đà Lạt"),
        at("Festival Hoa Đà Lạt lần thứ XI năm 2026", "2026-12-19", "2026-12-31", "hoadalattravel.vn", "Quảng trường Lâm Viên"),
        at("Festival Hoa Đà Lạt lần thứ XI năm 2026", "2026-12-19", "2026-12-31", "vnexpress.net", "Quảng trường Lâm Viên"),
        at("Đêm Khai mạc", "2026-12-19", "2026-12-19", "ivivu.com", "Quảng trường Lâm Viên, phường Xuân Hương – Đà Lạt"),
        at("Lễ hội nhạc Jazz Việt Nam 2026", "2026-12-25", "2026-12-27", "ivivu.com", "bên bờ hồ Xuân Hương", part_of="Festival Hoa Đà Lạt 2026"),
        at("Đêm Bế mạc kết hợp chương trình nghệ thuật Chào năm mới 2027", "2026-12-31", "2026-12-31", "ivivu.com", "Quảng trường Lâm Viên"),
        at("K-Vietnam Wellness Festa & Expo in Dalat 2026", "2026-11-20", "2026-11-24", "vietbao.vn", "Quảng trường Lâm Viên"),
    ])
    assert [(e["name"], e["start"], e["end"]) for e in out] == [
        ("K-Vietnam Wellness Festa & Expo in Dalat 2026", "2026-11-20", "2026-11-24"),
        ("Festival Hoa Đà Lạt lần thứ XI năm 2026", "2026-12-19", "2026-12-31")]  # the days two sites give, not one page's
    assert [p["name"] for p in out[1]["parts"]] == ["Không gian hoa", "Đêm Khai mạc", "Lễ hội nhạc Jazz Việt Nam 2026",
                                                    "Đêm Bế mạc kết hợp chương trình nghệ thuật Chào năm mới 2027"]
    assert "Da Lat Flower Festival" not in [p["name"] for p in out[1]["parts"]]  # a translation is the name, not a programme


def test_part_of_stands_only_when_the_page_names_the_larger_event():
    page = {**PAGE, "text": PAGE["text"] + " Chương trình Festival Hoa Đà Lạt 2026 gồm Lễ hội nhạc Jazz."}
    got = kept(ev("Lễ hội nhạc Jazz Việt Nam 2026", "2026-11-06", "2026-11-08", "q", part_of="Festival Hoa Đà Lạt 2026"), page, TODAY)
    assert got["part_of"] == "Festival Hoa Đà Lạt 2026"
    assert "part_of" not in kept(ev("Lễ hội nhạc Jazz Việt Nam 2026", "2026-11-06", "2026-11-08", "q", part_of="Festival Trà Bảo Lộc"), page, TODAY)


def test_a_festivals_programmes_never_shorten_its_days_and_one_opening_is_listed_once():
    """18/11/2026: two pages gave the festival only its first day, three gave its opening night; the run of 19-31/12 stands."""
    def at(name, start, end, domain, part_of=""):
        return {**row(name, start, end, domain), **({"part_of": part_of} if part_of else {})}
    out = merge([
        at("Festival Hoa Đà Lạt lần thứ XI năm 2026", "2026-12-19", "2026-12-19", "hoadalattravel.vn"),
        at("Festival Hoa Đà Lạt lần thứ XI 2026", "2026-12-19", "2026-12-31", "hoadalattravel.vn"),
        at("Festival hoa Đà Lạt lần thứ XI năm 2026", "2026-12-19", "2026-12-19", "mia.vn"),
        at("Lễ khai mạc Festival hoa Đà Lạt lần thứ XI năm 2026", "2026-12-19", "2026-12-19", "mia.vn", "Festival hoa Đà Lạt lần thứ XI năm 2026"),
        at("Hội chợ hoa Đà Lạt", "2026-12-19", "2026-12-19", "mia.vn", "Festival hoa Đà Lạt lần thứ XI năm 2026"),
        at("Lễ khai mạc Festival Hoa Đà Lạt lần thứ XI", "2026-12-19", "2026-12-19", "dalat-info.gov.vn", "Festival Hoa Đà Lạt lần thứ XI, năm 2026"),
        at("Festival Hoa lần thứ XI", "2026-12-19", "2026-12-31", "thofleur.com"),
    ])
    assert [(e["start"], e["end"]) for e in out] == [("2026-12-19", "2026-12-31")]
    assert sorted(p["name"] for p in out[0]["parts"]) == ["Hội chợ hoa Đà Lạt", "Lễ khai mạc"]  # the festival is named once, above


def test_an_event_still_to_come_stays_when_tonights_pages_do_not_name_it():
    from corpus.events.gate import carried
    today = date(2026, 11, 18)
    def at(name, start, end, read, venue=""):
        r = row(name, start, end, "naturehotel.vn")
        r["sources"][0]["read"] = read
        return {**r, "venue": venue}
    festival = {**at("Festival Hoa Đà Lạt lần thứ XI", "2026-12-19", "2026-12-31", "2026-11-18", "Quảng trường Lâm Viên"),
                "parts": [{"name": "Lễ khai mạc", "start": "2026-12-19", "end": "2026-12-19", "time": "", "venue": ""}]}
    out = carried([at("Diễu hành áo dài – Liên hoan văn hóa Việt", "2026-11-16", "2026-11-20", "2026-11-16"),
                   at("Lễ hội Ẩm thực", "2026-11-01", "2026-11-10", "2026-11-01"),               # over
                   at("Giải chạy Dalat Ultra", "2026-12-05", "2026-12-06", "2026-11-02"),        # no page for 16 days
                   at("Da Lat Flower Festival", "2026-12-01", "2027-01-31", "2026-11-16"),       # tonight's festival in English
                   at("Đêm Khai mạc", "2026-12-19", "2026-12-19", "2026-11-16", "Quảng trường Lâm Viên"),
                   at("Lễ hội nhạc Jazz Việt Nam 2026", "2026-12-25", "2026-12-27", "2026-11-16", "bờ hồ Xuân Hương")],
                  [festival], today, programmes=(("Lễ hội nhạc Jazz Việt Nam 2026", "Festival Hoa Đà Lạt lần thứ XI"),))
    assert [e["name"] for e in out] == ["Diễu hành áo dài – Liên hoan văn hóa Việt", "Festival Hoa Đà Lạt lần thứ XI"]
    assert [p["name"] for p in out[1]["parts"]] == ["Lễ khai mạc", "Lễ hội nhạc Jazz Việt Nam 2026"]


def test_tidy_name_recases_a_shouted_listing_and_keeps_its_words():
    assert gate.tidy_name("BẠCH CÔNG KHANH - DƯƠNG EDWARD") == "Bạch Công Khanh – Dương Edward"
    assert gate.tidy_name("JIMMII NGUYỄN & KHÁCH MỜI: NGỌC PHẠM - DINH DZU") == "Jimmii Nguyễn & khách mời: Ngọc Phạm – Dinh Dzu"
    assert gate.tidy_name("FESTIVAL HOA ĐÀ LẠT LẦN THỨ XI") == "Festival Hoa Đà Lạt lần thứ XI"
    assert gate.tidy_name("lễ khai mạc Festival Hoa Đà Lạt lần thứ XI") == "Lễ khai mạc Festival Hoa Đà Lạt lần thứ XI"
    assert gate.tidy_name("K-Vietnam Wellness Festa & Expo in Dalat 2026") == "K-Vietnam Wellness Festa & Expo in Dalat 2026"


def test_tidy_venue_leaves_the_place_name_only():
    assert gate.tidy_venue("Mây Lang Thang | Đà Lạt", "Đà Lạt") == "Mây Lang Thang"
    assert gate.tidy_venue("Quảng trường Lâm Viên (phường Xuân Hương - Đà Lạt)", "Đà Lạt") == "Quảng trường Lâm Viên"
    assert gate.tidy_venue("Quảng trường Lâm Viên", "Đà Lạt") == "Quảng trường Lâm Viên"
    assert gate.tidy_venue("", "Đà Lạt") == ""


def test_tidy_reaches_the_parts():
    row = gate.tidy({"name": "festival hoa", "venue": "Quảng trường Lâm Viên | Đà Lạt",
                     "parts": [{"name": "LỄ KHAI MẠC", "venue": "Đà Lạt"}]}, "Đà Lạt")
    assert row["name"] == "Festival hoa" and row["venue"] == "Quảng trường Lâm Viên"
    assert row["parts"][0]["name"] == "Lễ Khai Mạc"
