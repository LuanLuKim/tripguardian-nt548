import json

import yaml

from corpus.categories import defaults as category_defaults
from corpus.crawl.common.files import ROOT, listed
from corpus.crawl.gmaps import services

AREA = [11.78, 108.3, 12.12, 108.66]


def card(fid, name, lat=11.94, lng=108.44, category="ATM", rating=None, reviews=None):
    return {"fid": fid, "name": name, "url": f"https://maps/{fid}", "lat": lat, "lng": lng, "category": category,
            "rating": rating, "reviews": reviews}


def write_search(d, word, query, items):
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{word}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": "2026-10-29T10:00:00", "query": query, "tile": [11.9, 108.4, 14], "end": True,
                            "items": items}) + "\n")


def test_config_boundary_is_explicit():
    cfg = yaml.safe_load((ROOT / "config" / "queries.yaml").read_text(encoding="utf-8"))["services"]
    assert cfg["read_by"] == "assistant_tools"
    assert cfg["decision_candidates"] is False and cfg["planning_stops"] is False
    assert {"utilities", "rental_tour"} <= set(cfg["groups"])
    for w in ("ATM", "cây xăng", "bệnh viện", "phòng khám", "hiệu thuốc", "nhà vệ sinh công cộng", "trạm sạc xe điện"):
        assert w in cfg["groups"]["utilities"]
    for w in ("thuê xe máy", "thuê ô tô", "tour"):
        assert w in cfg["groups"]["rental_tour"]


def test_service_groups_are_not_decision_groups():
    groups = {g["id"] for g in category_defaults()["groups"]}
    assert not groups & set(services.config()["groups"])


def test_services_never_enter_the_place_inventory(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    lst = tmp_path / "gmaps" / "list"
    lst.mkdir(parents=True)
    (lst / "dalat.json").write_text(json.dumps({"items": [{"fid": "A"}]}), encoding="utf-8")
    (lst / "dalat_svc.json").write_text(json.dumps({"items": [{"fid": "S"}]}), encoding="utf-8")
    assert [r["fid"] for r in listed("dalat")] == ["A"]  # observe / aggregate / serving read only this


def test_build_groups_by_query_word_and_keeps_unrated_places():
    rows = [("ATM", "ATM", [card("0x1:0x1", "ATM Vietcombank"), card("0x1:0x2", "ATM xa", lat=20.0)]),
            ("cây xăng", "cây xăng", [card("0x1:0x3", "Petrolimex", category="Trạm xăng", rating=4.2, reviews=30)]),
            ("tour", "tour", [card("0x1:0x4", "Tour Đà Lạt", category="Công ty tour", rating=4.8, reviews=100)])]
    groups = {"utilities": ["ATM", "cây xăng"], "rental_tour": ["tour"]}
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        for word, query, items in rows:
            write_search(d, word, query, items)
        out = services.build(d, AREA, groups)
    by = {r["fid"]: r for r in out["items"]}
    assert set(by) == {"0x1:0x1", "0x1:0x3", "0x1:0x4"}  # outside the area dropped; no review minimum
    assert by["0x1:0x1"]["group"] == "utilities" and by["0x1:0x4"]["group"] == "rental_tour"
    assert out["stats"]["places"] == 3 and out["stats"]["outside_area"] == 1


def test_load_merges_place_page_facts(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    root = tmp_path / "gmaps"
    (root / "list").mkdir(parents=True)
    (root / "list" / "dalat_svc.json").write_text(json.dumps({"items": [
        {"fid": "0x1:0x1", "name": "Hiệu thuốc A", "lat": 11.9, "lng": 108.4, "group": "utilities",
         "category": "Hiệu thuốc", "rating": 4.0, "reviews": 10, "url": "u"}]}), encoding="utf-8")
    (root / "services" / "places").mkdir(parents=True)
    (root / "services" / "places" / "0x1_0x1.json").write_text(json.dumps(
        {"fid": "0x1:0x1", "phone": "0263 111 222", "website": None, "hours": ["Thứ Hai 07:00–21:00"],
         "address": "1 Hoàng Văn Thụ", "status": "Đang mở cửa"}), encoding="utf-8")
    rows = services.load("dalat", group="utilities")
    assert rows[0]["phone"] == "0263 111 222" and rows[0]["hours"] == ["Thứ Hai 07:00–21:00"]
    assert rows[0]["address"] == "1 Hoàng Văn Thụ" and rows[0]["name"] == "Hiệu thuốc A"
    assert services.load("dalat", group="rental_tour") == []


def test_load_words_are_the_config_words_not_the_city_suffixed_queries(tmp_path, monkeypatch):
    """The list stores the searched query ("thuê xe máy Đà Lạt"); `words` must be the config word the tool matches."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    root = tmp_path / "gmaps"
    (root / "list").mkdir(parents=True)
    (root / "list" / "dalat_svc.json").write_text(json.dumps({"items": [
        {"fid": "0x1:0x1", "name": "Thuê xe A", "group": "rental_tour", "queries": ["thuê xe máy Đà Lạt", "tour Đà Lạt"]},
        {"fid": "0x1:0x2", "name": "ATM B", "group": "utilities", "queries": ["ATM Đà Lạt", "ATM"]}]}), encoding="utf-8")
    by = {r["fid"]: r["words"] for r in services.load("dalat")}
    assert by == {"0x1:0x1": ["thuê xe máy", "tour"], "0x1:0x2": ["ATM"]}
