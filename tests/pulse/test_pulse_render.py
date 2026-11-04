from corpus.pulse import render


def test_hot_template_uses_only_fields():
    item = {"id": "hot:p1", "kind": "hot", "subject": {"type": "place", "id": "p1", "name": "Quán Một"},
            "signals": {"videos": 12, "authors": 5, "newest": "2026-10-26", "window_days": 30}, "dates": {"to": "2026-10-29"}, "evidence": []}
    out = render.item(item)
    assert out["title"] == "Quán Một"
    assert out["text"] == "12 video mới trong 30 ngày, 5 tác giả khác nhau · mới nhất 26/10"


def test_season_text_never_says_blooming():
    item = {"id": "season:da-quy", "kind": "season", "subject": {"type": "season", "id": None, "name": "Dã quỳ"},
            "signals": {"months": [10, 11], "sources": 3, "status": "kept", "latest_video": {"id": "v", "date": "2026-10-28", "url": "u"}},
            "dates": {}, "evidence": []}
    text = render.item(item)["text"]
    assert text.startswith("Đang vào mùa Dã quỳ (tháng 10–11)")
    assert "nở" not in text and "video mới nhất nhắc tới Dã quỳ: 28/10" in text


def test_unverified_season_is_labelled_reference():
    item = {"id": "season:x", "kind": "season", "subject": {"type": "season", "id": None, "name": "Cỏ hồng"},
            "signals": {"months": [11], "sources": 1, "status": "unverified", "latest_video": None}, "dates": {}, "evidence": []}
    assert render.item(item)["text"].endswith("tham khảo, 1 nguồn")


def test_new_text_is_month_precise_when_not_exact():
    item = {"id": "new:p", "kind": "new", "subject": {"type": "place", "id": "p", "name": "Q"},
            "signals": {"first_review": "2026-07-02", "reviews": 60, "total": 60, "exact": False}, "dates": {}, "evidence": []}
    assert render.item(item)["text"] == "Đánh giá đầu tiên trên Maps khoảng tháng 7/2026 · 60 đánh giá"


def test_short_fields_for_the_rail_hot_and_top():
    hot = {"id": "hot:p1", "kind": "hot", "subject": {"type": "place", "id": "p1", "name": "Quán Một"},
           "signals": {"videos": 8, "authors": 6, "newest": "2026-10-27", "window_days": 30}, "dates": {}, "evidence": []}
    out = render.item(hot)
    assert (out["signal"], out["signal_kind"], out["count"], out["window_days"], out["newest"]) == ("8 clip TikTok mới", "tiktok", 8, 30, "2026-10-27")
    assert out["rising"] is False and out["on"] is None
    top = {"id": "top:p2", "kind": "top", "subject": {"type": "place", "id": "p2", "name": "Quán Hai"},
           "signals": {"reviews": {"n": 120, "authors": 120, "mean_stars": 4.8, "newest": "2026-10-28"}, "rating_trend": "rising", "web_domains": ["a.vn"]},
           "dates": {"from": "2026-09-30", "to": "2026-10-30"}, "evidence": []}
    out = render.item(top)
    assert (out["signal"], out["signal_kind"], out["count"], out["window_days"], out["rising"]) == ("120 đánh giá mới", "reviews", 120, 30, True)
    top["signals"] = {"web_domains": ["a.vn", "b.vn"]}
    assert render.item(top)["signal"] == "Nhiều trang nhắc tới"
    assert "text" in out and out["place_id"] == "p2"  # the old fields stay


def test_short_fields_for_events_and_others():
    cal = {"id": "event:holiday:2026-11-24", "kind": "event", "subject": {"type": "event", "id": None, "name": "Ngày Văn hóa Việt Nam"},
           "signals": {"source": "calendar"}, "dates": {"on": "2026-11-24"}, "evidence": []}
    out = render.item(cal)
    assert (out["signal"], out["on"], out["reference"], out["place_id"]) == ("24/11", "2026-11-24", False, None)
    claim = {"id": "event:x", "kind": "event", "subject": {"type": "event", "id": None, "name": "Lễ hội nhạc Jazz"},
             "signals": {"source": "claim", "months": [11], "status": "unverified", "sources": 1}, "dates": {"from": "2026-11-01"}, "evidence": []}
    out = render.item(claim)
    assert (out["signal"], out["on"], out["reference"]) == ("Tháng 11 (tham khảo)", None, True)
    closed = {"id": "closed:p3", "kind": "closed", "subject": {"type": "place", "id": "p3", "name": "Quán Ba"},
              "signals": {}, "dates": {"checked": "2026-10-29"}, "evidence": []}
    out = render.item(closed)
    assert out["signal"] == "Đóng cửa vĩnh viễn" and out["place_id"] is None
