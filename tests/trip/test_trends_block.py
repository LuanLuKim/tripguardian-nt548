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


def test_an_events_question_gets_the_dated_events_then_the_places_people_go_to_now():
    b = trends_block(ROWS, trend_kinds(fold("tháng 11 có sự kiện gì")), cards)
    assert [s["kind"] for s in b["sections"]] == ["event", "places"]
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


def test_a_season_row_has_its_pages_sentence_and_its_picture_with_the_site():
    rows = {"as_of": "2026-11-13", "items": [
        {"kind": "season", "name": "hoa Mimosa", "place_id": None, "text": "Đang vào mùa hoa Mimosa (tháng 11) · Sang tháng 11…",
         "summary": "Sang hẳn tháng 11 thì bạn tha hồ ngắm hoa rực rỡ.", "image": "https://mia.vn/m.jpg",
         "image_from": {"url": "https://mia.vn/m", "domain": "mia.vn"}, "sources": SRC, "intro": None}]}
    row = trends_block(rows, ("season",), cards)["sections"][0]["rows"][0]
    assert row["meta"] == "Đang vào mùa · tháng 11" and row["text"].startswith("Sang hẳn tháng 11")
    assert (row["image"], row["image_from"]) == ("https://mia.vn/m.jpg", "mia.vn")


def test_a_season_question_gets_only_the_season():
    assert trend_kinds(fold("tháng 11 này Đà Lạt có mùa hoa gì")) == ("season",)


def test_a_season_row_carries_where_to_see_it_and_those_places_come_as_cards():
    rows = {"as_of": "2026-11-15", "items": [
        {"kind": "season", "name": "hoa dã quỳ", "place_id": None, "text": "Đang vào mùa hoa dã quỳ (tháng 10–1)",
         "see": ["0x1:0xa", "0x1:0xb"], "sources": SRC, "intro": None}]}
    b = trends_block(rows, ("season",), cards)
    assert b["sections"][0]["rows"][0]["see"] == ["0x1:0xa", "0x1:0xb"]
    assert [c["id"] for c in b["cards"]] == ["0x1:0xa", "0x1:0xb"]


def test_a_hot_item_carries_its_note_to_the_row_and_a_plain_one_does_not():
    rows = {"as_of": "2026-11-16", "items": [
        {"kind": "season", "name": "hồng chín", "place_id": None, "text": "Đang vào mùa hồng chín (tháng 9–12)", "hot": True,
         "hot_note": "39 clip TikTok của 34 người trong 30 ngày", "sources": SRC, "intro": None},
        {"kind": "season", "name": "hoa cải trắng", "place_id": None, "text": "Đang vào mùa hoa cải trắng (tháng 11)", "sources": SRC, "intro": None}]}
    got = trends_block(rows, ("season",), cards)["sections"][0]["rows"]
    assert got[0]["hot"] == "39 clip TikTok của 34 người trong 30 ngày" and "hot" not in got[1]
