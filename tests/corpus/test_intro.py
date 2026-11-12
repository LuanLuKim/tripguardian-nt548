"""A place's introduction: the code gate and the tidy step (corpus.intro, docs/CORPUS.md §Giới thiệu địa điểm)."""
from corpus.intro import check
from corpus.intro.run import tidy

CFG = {"hype": ["nổi tiếng nhất", "đầu tiên"], "min_review_authors": 2}


def item(i, text, source="web", domain="a.vn", authority=False, n=1):
    return {"id": i, "text": text, "source": source, "domain": domain, "authority": authority, "n": n}


ITEMS = {x["id"]: x for x in [
    item("e1", "Dinh được xây trong khoảng từ năm 1933 đến 1938.", "search", "vi.wikipedia.org", True),
    item("e2", "Dinh xây năm 1938, có 26 phòng.", domain="b.vn"),
    item("e3", "Hồ rộng 25ha.", domain="c.vn"),
    item("e4", "Quán nhỏ, ấm cúng.", "review", "google.com/maps"),
    item("e5", "Không gian ấm cúng.", "review", "google.com/maps"),
]}


def line(text, *ids):
    return {"text": text, "evidence": list(ids)}


def test_supported_sentence_passes():
    assert check(line("Dinh được xây từ năm 1933 đến 1938.", "e1"), ITEMS, CFG) is None
    assert check(line("Mặt hồ rộng khoảng 25 ha.", "e3"), ITEMS, CFG) is None


def test_number_and_year_need_their_sources():
    assert check(line("Dinh có 30 phòng.", "e2"), ITEMS, CFG) == "number_not_in_evidence"
    assert check(line("Dinh xây năm 1938.", "e2"), ITEMS, CFG) == "year_one_source"  # one site, not authoritative
    assert check(line("Dinh xây năm 1938.", "e1", "e2"), ITEMS, CFG) is None
    assert check(line("Gạch Since 1988 có cầu gỗ.", "e4", "e5"), ITEMS, CFG, "Gạch Since 1988") is None


def test_price_hype_reviews_and_missing_evidence():
    assert check(line("Vé 60.000 đồng.", "e1"), ITEMS, CFG) == "price"
    assert check(line("Đây là dinh nổi tiếng nhất.", "e1"), ITEMS, CFG) == "hype"
    assert check(line("Quán ấm cúng.", "e4"), ITEMS, CFG) == "one_review"
    assert check(line("Quán ấm cúng.", "e4", "e5"), ITEMS, CFG) is None
    assert check(line("Quán ấm cúng."), ITEMS, CFG) == "no_evidence"


def test_tidy_moves_ids_out_of_the_text():
    assert tidy({"text": "Quán nhỏ. [e1, e2]", "evidence": []}) == {"text": "Quán nhỏ.", "evidence": ["e1", "e2"]}
    assert tidy({"text": "Dài 7 km.[e2][e5] ி", "evidence": ["e9"]}) == {"text": "Dài 7 km.", "evidence": ["e9", "e2", "e5"]}
    assert tidy({"text": "Hồ Xuân Hương — Đà Lạt", "evidence": ["e1"]})["text"] == "Hồ Xuân Hương — Đà Lạt"


def test_posts_keep_checked_blocks_and_drop_the_rest():
    from corpus.intro.posts import CLOSING, assemble, quote_ok
    items = [item("e1", "Dinh được xây trong khoảng từ năm 1933 đến 1938.", "search", "vi.wikipedia.org", True),
             item("e2", "Phòng khách rộng, nhiều ảnh gia đình.", "web", "b.vn"),
             item("e3", "Khuôn viên rộng, nhiều cây xanh, mình rất thích vườn hoa.", "review", "google.com/maps"),
             item("e4", "Vườn hoa đẹp, khuôn viên rộng.", "review", "google.com/maps")]
    by_id = {i["id"]: i for i in items}
    assert quote_ok({"t": "q", "text": "“mình rất thích vườn hoa”", "evidence": ["e3"]}, by_id)
    assert not quote_ok({"t": "q", "text": "mình rất mê vườn hoa", "evidence": ["e3"]}, by_id)
    answer = {"posts": [{"angle": "a", "title": "Dinh III qua những gian phòng", "tags": ["Dinh III"], "blocks": [
        {"t": "p", "text": "Dinh được xây từ năm 1933 đến 1938.", "evidence": ["e1"]},
        {"t": "p", "text": "Phòng khách có nhiều ảnh gia đình.", "evidence": ["e2"]},
        {"t": "q", "text": "mình rất thích vườn hoa", "evidence": ["e3"]},
        {"t": "p", "text": "Khuôn viên rộng, nhiều cây xanh.", "evidence": ["e3", "e4"]},
        {"t": "p", "text": "Dinh có 40 phòng.", "evidence": ["e2"]},
        {"t": "h", "text": "Cuối buổi", "evidence": []}]}]}
    cfg = {"gate": {**CFG, "hype": ["tuyệt vời"]}}
    posts, dropped = assemble("0x1:0x2", "dinh3", "Dinh III", items, answer, {0: "supported", 1: "supported",
                                                                                2: "supported", 3: "supported"}, cfg)
    assert [d["reason"] for d in dropped] == ["number_not_in_evidence"]
    (post,) = posts
    assert post["id"] == "tg-dinh3-1" and post["tags"] == ["dinh iii"]
    assert [b["t"] for b in post["blocks"]] == ["p", "img", "p", "q", "p", "img", "p"]  # the dangling heading goes
    assert post["blocks"][-1]["text"] == CLOSING
    assert {s["domain"] for s in post["sources"]} == {"vi.wikipedia.org", "b.vn"} and post["review_count"] == 3


def test_a_post_with_too_little_left_is_dropped():
    from corpus.intro.posts import assemble
    items = [item("e1", "Hồ rộng 25ha.", domain="c.vn")]
    answer = {"posts": [{"angle": "a", "title": "Hồ", "tags": [], "blocks": [
        {"t": "p", "text": "Hồ rộng 25 ha.", "evidence": ["e1"]}, {"t": "p", "text": "Hồ sâu 9 m.", "evidence": ["e1"]}]}]}
    posts, dropped = assemble("0x1:0x2", "ho", "Hồ", items, answer, {0: "supported", 1: "supported"}, {"gate": CFG})
    assert posts == [] and dropped[-1]["reason"] == "too_little_left"
