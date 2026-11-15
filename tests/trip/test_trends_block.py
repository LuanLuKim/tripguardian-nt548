"""The chat's trends block (api/blocks.trends_block): only the sections the question asks for, rows from Nhịp items."""

from trip.api.blocks import trend_kinds, trends_block
from trip.domain.text import fold

SRC = [{"label": "dalat-info.gov.vn", "url": "https://www.dalat-info.gov.vn/a"}]
ROWS = {"as_of": "2026-11-13", "items": [
    {"kind": "event", "name": "Festival Âm nhạc quốc tế Lang Biang", "place_id": None, "days": "13–15/11", "on": "2026-11-13",
     "text": "13–15/11, 19:00 · Quảng trường Lâm Viên · Đêm chính 14/11", "summary": "Đêm chính 14/11",
     "image": "https://a.vn/p.jpg", "sources": SRC, "intro": None},
    {"kind": "event", "name": "Lễ hội nhạc Jazz", "place_id": None, "text": "Diễn ra tháng 11 (tham khảo) · 1 nguồn",
     "sources": SRC, "intro": None},
    {"kind": "season", "name": "săn mây ở Đà Lạt", "place_id": None, "text": "Đang vào mùa săn mây ở Đà Lạt (tháng 8–12) · video 16/09",
     "sources": SRC, "intro": None},
    {"kind": "season", "name": "Tháng 10 - 12", "place_id": None, "text": "Đang vào mùa Tháng 10 - 12 (tháng 10–12)",
     "sources": SRC, "intro": None},
    {"kind": "hot", "name": "Đồi Gác Vọng", "place_id": "0x1:0x1", "text": "3 video mới", "intro": "Đồi ngắm hoàng hôn.",
     "sources": [{"label": "Video TikTok", "url": "https://www.tiktok.com/@a/video/1"}]},
]}


def cards(ids):
    return [{"id": i} for i in ids]


def test_an_events_question_gets_only_the_dated_events():
    b = trends_block(ROWS, trend_kinds(fold("tháng 11 có sự kiện gì")), cards)
    assert [s["kind"] for s in b["sections"]] == ["event"]
    row = b["sections"][0]["rows"][0]
    assert row == {"title": "Festival Âm nhạc quốc tế Lang Biang", "meta": "13–15/11, 19:00 · Quảng trường Lâm Viên",
                   "text": "Đêm chính 14/11", "on": "2026-11-13", "image": "https://a.vn/p.jpg",
                   "source": {"url": "https://www.dalat-info.gov.vn/a", "title": "dalat-info.gov.vn", "domain": "dalat-info.gov.vn"}}
    assert len(b["sections"][0]["rows"]) == 1  # the month-only claim has no day to show


def test_a_broad_question_gets_events_seasons_and_places():
    b = trends_block(ROWS, trend_kinds(fold("đà lạt dạo này có gì đặc biệt")), cards)
    assert [s["kind"] for s in b["sections"]] == ["event", "season", "places"]
    season = b["sections"][1]["rows"]
    assert [(r["title"], r["meta"]) for r in season] == [("Săn mây ở Đà Lạt", "Đang vào mùa · tháng 8–12")]  # not "Tháng 10 - 12"
    place = b["sections"][2]["rows"][0]
    assert place["id"] == "0x1:0x1" and place["text"] == "Đồi ngắm hoàng hôn." and place["source"]["domain"] == "tiktok.com"
    assert b["cards"] == [{"id": "0x1:0x1"}]


def test_nothing_to_show_is_no_block():
    assert trends_block({}, ("event",), cards) is None
    assert trends_block({"as_of": "2026-11-13", "items": []}, ("event",), cards) is None
