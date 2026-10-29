from fixtures import feat, si, srec

from decision.cards import card, phrase, price_text
from decision.model import Cand
from decision.settings import default

CFG = default()


def cand(rec, **kw):
    c = Cand(rec, "experience")
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_why_comes_from_matches_anchor_and_nearness():
    c = cand(srec("A"), matches=[("scenic_view", "present", 1.0, 7), ("crowd", "low", 0.5, 4)], minutes=8,
             center="trung tâm Đà Lạt")
    got = card(c, si(), CFG, anchor=True)["why"]
    assert [w["text"] for w in got] == ["Nơi bạn muốn đến", "View đẹp, 7 người nhắc", "Độ đông: vắng, 4 người nhắc"]
    assert got[1]["sid"] == "scenic_view"
    near = card(cand(srec("B"), minutes=8, center="trung tâm Đà Lạt"), si(), CFG)["why"]
    assert near == [{"text": "Gần trung tâm Đà Lạt, ≈8 phút (ước tính)", "sid": None}]


def test_tradeoffs_flags_avoided_matches_and_bad_firm_values():
    rec = srec("A", features={"noise": feat("loud", n=5), "parking": feat("hard", n=1)})
    c = cand(rec, flags=[{"code": "rain", "text": "Ngoài trời", "sid": "setting"}],
             matches=[("live_music", "present", -1.0, 3)])
    texts = [t["text"] for t in card(c, si(), CFG)["tradeoffs"]]
    assert texts == ["Ngoài trời", "Nhạc sống, điều bạn muốn tránh", "Độ ồn: ồn, theo 5 người"]


def test_confidence_levels_follow_wanted_features():
    rec = srec("A", voices=50, features={"scenic_view": "present", "noise": feat("quiet", status="UNCERTAIN")})
    assert card(cand(rec), si(), CFG, wanted=["scenic_view"])["confidence"]["level"] == "high"
    assert card(cand(rec), si(), CFG, wanted=["scenic_view", "noise"])["confidence"]["level"] == "medium"
    low = card(cand(rec), si(), CFG, wanted=["hiking", "noise", "scenic_view"])["confidence"]
    assert low["level"] == "low" and "chưa có bằng chứng về leo núi, trekking" in low["reason"]
    assert card(cand(rec), si(), CFG)["confidence"]["level"] == "high"  # nothing wanted: by voices


def test_price_unknown_budget_warnings_failed_and_declined():
    rec = srec("A", price={"min_vnd": 100000, "max_vnd": 200000}, rating_trend={"direction": "falling"})
    c = cand(rec, warnings=["hours_outdated", "uncertain_value:noise"],
             checks=[{"kind": "hard", "feature": "steep_or_stairs", "value": "present", "op": "ne", "result": "fail",
                      "reason": "hard:steep_or_stairs", "policy": "exclude"},
                     {"kind": "hard", "feature": "long_walk", "value": "present", "op": "ne", "result": "unknown",
                      "reason": "hard:long_walk", "policy": "flag"}])
    got = card(c, si(unknowns=["budget_vnd"]), CFG)
    assert price_text(rec) == "100k–200k/người"
    assert got["depends_on_unknown"] == "Chưa biết ngân sách của bạn; giá khoảng 100k–200k/người"
    assert got["warnings"] == ["Giờ mở cửa có thể đã đổi, kiểm tra lại trước chuyến", "Độ ồn: chưa xác nhận chắc"]
    assert got["failed"] == ["Dốc, nhiều bậc: có"] and got["unverified"] == ["Chưa xác minh được: phải đi bộ xa"]
    assert got["declined"] is True and phrase("crowd", "high", CFG) == "Độ đông: đông"


def test_missing_record_card():
    c = Cand(srec("Z", name=None, hours=None, voices=0), "experience", keep=True, missing=True)
    got = card(c, si(), CFG)
    assert got["confidence"]["level"] == "low" and "Chưa có trong dữ liệu đang phục vụ (có thể đã đóng cửa)" in got["warnings"]


def test_irrelevant_food_preference_does_not_reduce_a_parks_confidence():
    park = srec("park", group="garden_farm", voices=50, features={"scenic_view": "present"})
    result = card(cand(park), si(), CFG, wanted=["scenic_view", "vegetarian_options"])
    assert result["confidence"]["level"] == "high"
    assert "món chay" not in result["confidence"]["reason"].lower()


def _menu(rec, *names):
    rec["menu"] = {"dishes": [{"name": n, "name_en": None, "section": None, "popular": False, "price": None}
                              for n in names], "photos": []}
    return rec


def test_why_says_the_wish_first_with_its_source():  # D1, D2
    c = cand(_menu(srec("M", group="restaurant", usable=("meal",)), "Bánh căn"),
             wishes=[("dish:bánh căn", "dish", "bánh căn", 0.8), ("purpose:food_culture", "purpose", "food_culture", 0.25)],
             matches=[("scenic_view", "present", 1.0, 7), ("crowd", "low", 0.5, 4)])
    got = [w["text"] for w in card(c, si(), CFG)["why"]]
    assert got[0] == "Có bánh căn bạn muốn · theo menu"
    assert got[1:] == ["View đẹp, 7 người nhắc", "Độ đông: vắng, 4 người nhắc"]


def test_purpose_reason_is_marked_as_a_guess():  # D3
    c = cand(srec("C"), wishes=[("purpose:relax", "purpose", "relax", 0.25)])
    assert card(c, si(), CFG)["why"] == [{"text": "Hợp chuyến thư giãn ✎", "sid": None}]


def test_card_with_no_reason_still_says_something_true_but_not_a_fit():  # D4
    far = card(cand(srec("B", voices=240), minutes=30, center="chỗ ở"), si(), CFG)["why"]
    assert far == [{"text": "Cách chỗ ở ≈30 phút (ước tính)", "sid": None}]
    unknown = card(cand(srec("B", voices=240)), si(), CFG)["why"]
    assert unknown == [{"text": "240 người đã viết về nơi này", "sid": None}]


def test_other_wish_texts():
    c = cand(srec("K"), wishes=[("kind:karaoke", "kind", "karaoke", 0.8), ("vibe:0", "vibe", "mây", 0.8),
                                ("like:X", "like", "Mọt Cafe", 0.8)])
    assert [w["text"] for w in card(c, si(), CFG)["why"]] == [
        "Đúng loại karaoke bạn tìm", "Hợp phong cách “mây” bạn chọn", "Giống Mọt Cafe bạn thích"]
    g = cand(srec("C"), wishes=[("group:chill", "group", "chill", 0.4)])
    assert card(g, si(), CFG)["why"] == [{"text": "Vì bạn thích cà phê và thư giãn", "sid": None}]
    nameless = cand(srec("Y"), wishes=[("like:X", "like", "", 0.8)])
    assert card(nameless, si(), CFG)["why"][0]["text"] == "Giống nơi bạn nhắc tới"


def test_fallback_says_the_largest_score_part():  # D4
    known = cand(srec("B", voices=240), minutes=30, center="chỗ ở", parts={"ctx": 0.1, "pop": 0.9})
    assert card(known, si(), CFG)["why"] == [{"text": "240 người đã viết về nơi này", "sid": None}]
    close = cand(srec("B", voices=240), minutes=30, center="chỗ ở", parts={"ctx": 0.9, "pop": 0.1})
    assert card(close, si(), CFG)["why"] == [{"text": "Cách chỗ ở ≈30 phút (ước tính)", "sid": None}]


def _label(tmp_path, pid, photos):
    import json

    from PIL import Image
    d = tmp_path / "gmaps" / "places" / pid.replace(":", "_")
    (d / "photos").mkdir(parents=True)
    rows = []
    for name, scene, kw in photos:
        Image.new("RGB", (40, 30), "white").save(d / "photos" / f"{name}.jpg")
        rows.append({"photo_id": name, "file": f"photos/{name}.jpg", "scene": scene, "keep": True, "owner": False,
                     "blur": kw.get("blur", 900.0), "brightness": 120.0, "person": {"value": kw.get("person", False), "confidence": "high"}})
    out = tmp_path / "gmaps" / "photo_scenes"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{pid.replace(':', '_')}.json").write_text(json.dumps({"place_fid": pid, "photos": rows}), encoding="utf-8")


def test_card_photos_are_scene_photos_without_people_and_blur_in_the_order_of_the_kind(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    rec = srec("0xa:0xb", group="cafe")
    _label(tmp_path, "0xa:0xb", [("f", "food", {}), ("i", "interior", {}), ("e", "exterior", {}), ("v", "view", {}),
                                  ("d", "drink", {}), ("p", "interior", {"person": True, "blur": 3000.0}),
                                  ("b", "amenity", {"blur": 10.0})])
    got = card(cand(rec), si(), CFG)["photos"]
    assert [p["scene"] for p in got] == ["interior", "food", "exterior", "drink"]  # cafe order, 4 scenes, no person, no blur
    assert got[0] == {"scene": "interior", "src": "/media/gmaps/0xa_0xb/photos/i.jpg", "credit": "Google Maps", "kind": "gmaps",
                      "w": 40, "h": 30}


def test_card_without_labels_has_no_photos_so_the_web_keeps_its_own(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert card(cand(srec("0xc:0xd")), si(), CFG)["photos"] == []
