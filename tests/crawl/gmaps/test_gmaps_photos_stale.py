"""Photos older than MAX_AGE_YEARS: kept as `stale` only when a place has nothing newer, and never read as evidence."""

import json

from corpus.crawl.gmaps.photos import needs_fetch
from corpus.index.vectors import photo_inputs


def _write(path, doc):
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_empty_save_with_old_photos_is_fetched_once_more(tmp_path):
    f = tmp_path / "photos.json"
    _write(f, {"wanted": 12, "photos": [], "skipped": {"too_old": 7}})
    assert needs_fetch(f, 12, 12)
    _write(f, {"wanted": 12, "photos": [], "skipped": {"too_old": 7}, "stale_fallback": True})
    assert not needs_fetch(f, 12, 12)


def test_empty_save_without_a_reason_is_left_alone(tmp_path):
    f = tmp_path / "photos.json"
    _write(f, {"wanted": 12, "photos": [], "skipped": {}})
    assert not needs_fetch(f, 12, 12)


def test_evidence_readers_skip_stale_photos(tmp_path):
    d = tmp_path / "gmaps" / "places" / "0xa_0xb"
    (d / "photos").mkdir(parents=True)
    for n in ("fresh", "old"):
        (d / "photos" / f"{n}.jpg").write_bytes(b"x")
    _write(d / "photos.json", {"photos": [{"photo_id": "1", "file": "photos/fresh.jpg"},
                                          {"photo_id": "2", "file": "photos/old.jpg", "stale": True}]})
    assert [p["photo_id"] for p in photo_inputs(tmp_path, "0xa:0xb")] == ["1"]


def test_scene_chips_skip_tabs_video_menu_360_and_food():
    from corpus.crawl.gmaps.photos import scene_chips
    labels = ["Tất cả", "Thực đơn", "Video", "Thực phẩm và đồ uống", "Bầu không khí", "Phòng", "Bầu không khí",
              "Chế độ xem Phố và 360°", "Bên ngoài", "Của chủ sở hữu", "Bên trong", "Mới nhất"]
    assert scene_chips(labels) == ["Bầu không khí", "Phòng", "Bên ngoài", "Của chủ sở hữu"]  # CHIP_MAX = 4, page order
    assert scene_chips([]) == [] and scene_chips([None, ""]) == []


def test_chips_pass_refetches_a_place_without_the_chips_key(tmp_path):
    f = tmp_path / "photos.json"
    _write(f, {"wanted": 30, "photos": [{"photo_id": "1"}], "skipped": {}})
    assert not needs_fetch(f, 30, 12) and needs_fetch(f, 30, 12, chips=True)
    _write(f, {"wanted": 30, "photos": [{"photo_id": "1"}], "skipped": {}, "chips": ["Bên ngoài"]})
    assert not needs_fetch(f, 30, 12, chips=True)


def test_aged_flag_on_disk_only_for_sight_places_within_the_window_and_without_touching_evidence(tmp_path):
    from corpus.crawl.gmaps import photos
    this_year = int(photos.now()[:4])
    for fid, cat in (("0xa_0xb", "Thác nước"), ("0xc_0xd", "Khách sạn")):
        d = tmp_path / "places" / fid
        (d / "photos").mkdir(parents=True)
        for n in ("a", "b"):
            (d / "photos" / f"{n}.jpg").write_bytes(b"x")
        _write(d / "place.json", {"category": cat})
        _write(d / "photos.json", {"photos": [
            {"photo_id": "a", "file": "photos/a.jpg", "stale": True, "month": f"{this_year - 4}-06"},
            {"photo_id": "b", "file": "photos/b.jpg", "stale": True, "month": f"{this_year - 9}-06"}]})
    assert photos.flag_aged_on_disk(tmp_path) == {"places": 1, "photos": 1}
    sight = json.loads((tmp_path / "places" / "0xa_0xb" / "photos.json").read_text())
    assert [(p["photo_id"], bool(p.get("display_old")), p["stale"]) for p in sight["photos"]] == [("a", True, True), ("b", False, True)]
    assert "aged_years" not in sight  # the crawl still fetches the place once
    assert not any(p.get("display_old") for p in json.loads((tmp_path / "places" / "0xc_0xd" / "photos.json").read_text())["photos"])
    assert photos.flag_aged_on_disk(tmp_path) == {"places": 0, "photos": 0}
    assert needs_fetch(tmp_path / "places" / "0xa_0xb" / "photos.json", 12, 12, aged=6)
