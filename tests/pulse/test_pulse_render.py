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
