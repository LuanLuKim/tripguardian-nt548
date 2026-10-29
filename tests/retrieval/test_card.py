"""Compact place card for agents: only serving-record fields, empty keys omitted."""

from unittest.mock import MagicMock

from corpus.retrieval import RetrievalEngine, card

DAY = [["06:30", "21:30"]]
RECORD = {
    "id": "P1",
    "status": "VERIFIED",
    "identity": {"name": "Cafe A", "category": "Quán cà phê", "category_group": "cafe", "address": "Đà Lạt",
                 "lat": 11.9, "lng": 108.4},
    "operation": {
        "hours": {"value": {"mon": DAY, "tue": DAY, "wed": DAY, "thu": DAY, "fri": [["06:00", "21:30"]],
                            "sat": DAY, "sun": DAY}, "status": "VERIFIED", "source": "provider"},
        "price_per_person": {"value": {"min_vnd": 30000, "max_vnd": 60000}, "status": "VERIFIED"},
        "price_per_night": None,
        "entry_fee": None,
        "visit_minutes": {"short": 45, "typical": 75, "long": 150, "source": "category_default", "n": 0},
        "crowd_by_time": {"weekday": "low", "weekend": "high", "peak": "Sat 16:00-18:00"},
    },
    "experience": {"nature": {"value": "present", "status": "VERIFIED"},
                   "scenic_view": {"value": "present", "status": "UNCERTAIN", "reason": "low_agreement"}},
    "environment": {"crowd": {"value": "high", "status": "OUTDATED"}},
    "service": {}, "effort": {}, "suitability": {},
    "details": {
        "known_for": {"headline": "view đồi thông", "more": ["bánh mì que", "cà phê trứng"]},
        "order": [{"text": f"món {i}", "n": 3, "status": "VERIFIED"} for i in range(5)],
        "avoid": [],
        "timing": {"best_time": {"items": [{"text": "sáng sớm", "n": 4}]}, "avoid_time": {"items": []},
                   "best_months": [11, 12], "avoid_months": []},
    },
    "menu": {"dishes": [{"name": "Cà Phê Pha Máy"}] + [{"name": f"d{i}"} for i in range(10)]},
    "provenance": {"voices": 30, "rating_trend": {"direction": "up"}},
}


def test_card_keys_from_record():
    c = card(RECORD)
    assert (c["id"], c["n"], c["cat"], c["g"], c["addr"]) == ("P1", "Cafe A", "Quán cà phê", "cafe", "Đà Lạt")
    assert c["h"] == {"06:30-21:30": "mon,tue,wed,thu,sat,sun", "06:00-21:30": "fri"}
    assert "h_status" not in c and "status" not in c
    assert c["price"] == [30000, 60000] and c["visit"] == [45, 75, 150] and c["visit_src"] == "category_default"
    assert "nature=present" in c["f"] and "crowd=high" in c["f"]
    assert "scenic_view=present" in c["f?"] and "scenic_view=present" not in c["f"]
    assert c["known"] == ["view đồi thông", "bánh mì que", "cà phê trứng"]
    assert c["order"] == ["món 0", "món 1", "món 2"] and "avoid" not in c
    assert c["best"] == ["sáng sớm"] and "avoid_t" not in c
    assert c["months"] == [11, 12] and "months_avoid" not in c
    assert len(c["dishes"]) == 8 and c["dishes"][0] == "Cà Phê Pha Máy"
    assert (c["peak"], c["trend"], c["voices"]) == ("Sat 16:00-18:00", "up", 30)


def test_card_multiple_ranges_in_one_day_and_status_flags():
    rec = {**RECORD, "status": "UNCERTAIN",
           "operation": {**RECORD["operation"], "hours": {
               "value": {"mon": [["07:00", "11:00"], ["14:00", "21:00"]]}, "status": "OUTDATED"}}}
    c = card(rec)
    assert c["h"] == {"07:00-11:00,14:00-21:00": "mon"}
    assert (c["h_status"], c["status"]) == ("OUTDATED", "UNCERTAIN")


def test_card_omits_empty():
    c = card({"id": "P2", "identity": {"name": "X", "category": None, "category_group": "", "address": None}})
    assert set(c) <= {"id", "n", "cat", "g", "addr"} and c["id"] == "P2"
    assert all(v not in (None, "", [], {}) for v in c.values())


def test_card_never_serves_needs_review():
    rec = {"id": "P3", "identity": {"name": "X"},
           "experience": {"a": {"value": "present", "status": "NEEDS_REVIEW"},
                          "b": {"value": "present", "status": "DISABLED"}}}
    c = card(rec)
    assert "f" not in c and "f?" not in c


def test_card_marks_fee_conflict_and_fee_keys():
    fee = {"min_vnd": 60000, "typical_vnd": 100000, "max_vnd": 120000, "n": 3, "source": "reviews", "kind": "estimate"}
    rec = {"id": "P4", "identity": {"name": "X"}, "operation": {"entry_fee": fee},
           "service": {"entry_fee": {"value": "free", "status": "UNCERTAIN", "reason": "conflicts_entry_fee_estimate"}}}
    c = card(rec)
    assert c["fee"] == {"min": 60000, "typ": 100000, "max": 120000, "src": "reviews", "kind": "estimate",
                        "conflict": True}
    assert "entry_fee=free" in c["f?"]
    ok = card({**rec, "service": {}})
    assert "conflict" not in ok["fee"]


def test_card_night_price_and_size():
    rec = {"id": "H", "identity": {"name": "Hotel"},
           "operation": {"price_per_night": {"value": 399000, "status": "VERIFIED"}}}
    assert card(rec)["night"] == 399000
    import json
    assert len(json.dumps(card(RECORD), ensure_ascii=False)) < 2000


def test_engine_card_returns_card_or_none():
    engine = RetrievalEngine(_index=None, _snapshot=MagicMock(), _region=MagicMock(), _ontology=MagicMock(),
                             release_id="r")
    engine._region.record = lambda pid: RECORD if pid == "P1" else None
    assert engine.card("P1") == card(RECORD)
    assert engine.card("nope") is None


def test_card_splits_uncertain_detail_items():
    rec = {"id": "P5", "identity": {"name": "X"}, "details": {
        "activity": [{"text": "trượt cỏ", "status": "UNCERTAIN"}, {"text": "chèo thuyền", "status": "VERIFIED"},
                     {"text": "cũ", "status": "NEEDS_REVIEW"}, {"text": "đạp xe", "status": "OUTDATED"}],
        "order": [{"text": f"u{i}", "status": "UNCERTAIN"} for i in range(5)],
        "timing": {"best_time": {"items": [{"text": "chiều", "status": "UNCERTAIN"}, {"text": "sáng"}]}}}}
    c = card(rec)
    assert c["activity"] == ["chèo thuyền", "đạp xe"] and c["activity?"] == ["trượt cỏ"]
    assert "order" not in c and c["order?"] == ["u0", "u1", "u2"]
    assert c["best"] == ["sáng"] and c["best?"] == ["chiều"]
    assert not any("cũ" in v for v in c.values() if isinstance(v, list))


def test_card_visit_src_and_none_entry_fee_feature():
    rec = {"id": "P6", "identity": {"name": "X"},
           "operation": {"visit_minutes": {"short": 30, "typical": 60, "long": 90, "source": "reviews", "n": 4},
                         "entry_fee": {"min_vnd": 1, "typical_vnd": 2, "max_vnd": 3, "source": "official",
                                       "kind": "fact"}},
           "service": {"entry_fee": None}}
    c = card(rec)
    assert c["visit_src"] == "reviews" and "conflict" not in c["fee"]


def test_engine_scene_photos_uses_the_place_kind_and_is_empty_without_labels(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    out = tmp_path / "gmaps" / "photo_scenes"
    out.mkdir(parents=True)
    shot = lambda pid, scene: {"photo_id": pid, "file": f"photos/{pid}.jpg", "scene": scene, "blur": 900.0, "brightness": 120.0,
                               "keep": True, "owner": False, "person": {"value": False, "confidence": "high"}}
    (out / "P1.json").write_text(json.dumps({"place_fid": "P1", "photos": [shot("a", "food"), shot("b", "interior")]}),
                                 encoding="utf-8")
    engine = RetrievalEngine(_index=None, _snapshot=MagicMock(), _region=MagicMock(), _ontology=MagicMock(), release_id="r")
    engine._region.record = lambda pid: {"identity": {"category_group": "cafe"}} if pid in ("P1", "P2") else None
    assert [(p["scene"], p["file"]) for p in engine.scene_photos("P1")] == [
        ("interior", "gmaps/places/P1/photos/b.jpg"), ("food", "gmaps/places/P1/photos/a.jpg")]
    assert engine.scene_photos("P2") == [] and engine.scene_photos("nope") == []
