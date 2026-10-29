"""find_services: utilities / rental / tour / coach stations for the assistant (agent/services_tool.py). They are not
PlaceCards: no cards, never Decision candidates or Planning stops."""

from datetime import date

import pytest
from test_knowledge_tools import call, recs, turn  # noqa: F401  (fixtures)

from agents.assistant import REGISTRY
from trip.agent import services_tool
from trip.domain.state import TripState

ROWS = [
    {"fid": "s1", "name": "ATM Vietcombank Chợ", "lat": 11.943, "lng": 108.437, "group": "utilities", "words": ["ATM"],
     "category": "ATM", "rating": 4.1, "reviews": 30, "url": "https://maps/s1", "phone": "0263 111", "website": None,
     "hours": ["Thứ Hai 00:00-24:00"], "address": "1 Nguyễn Thị Minh Khai", "status": "Đang mở cửa", "fetched_at": "2026-10-29T10:00:00+00:00"},
    {"fid": "s2", "name": "ATM Far", "lat": 11.90, "lng": 108.40, "group": "utilities", "words": ["ATM"], "category": "ATM",
     "rating": None, "reviews": None, "url": "https://maps/s2", "phone": None, "website": None, "hours": [], "address": None,
     "status": None, "fetched_at": "2026-10-29T10:00:00+00:00"},
    {"fid": "s3", "name": "Thuê xe máy Z", "lat": 11.944, "lng": 108.438, "group": "rental_tour", "words": ["thuê xe máy"],
     "category": "Cửa hàng xe máy", "rating": 4.8, "reviews": 200, "url": "https://maps/s3", "phone": "0909", "website": "https://z.vn",
     "hours": [], "address": "2 X", "status": None, "fetched_at": "2026-10-29T10:00:00+00:00"},
]


@pytest.fixture(autouse=True)
def rows(monkeypatch):
    monkeypatch.setattr(services_tool, "service_places", lambda city, group=None: [dict(r) for r in ROWS])


def test_atm_near_a_written_place_nearest_first_with_unknowns(turn):
    out = call(turn(), "find_services", kind="ATM", near_place="Cà Phê Đồi Thông")
    assert [r["name"] for r in out["rows"]] == ["ATM Vietcombank Chợ", "ATM Far"]
    near, far = out["rows"]
    assert near["distance_km"] < far["distance_km"] and near["phone"] == "0263 111" and near["website"] == "unknown"
    assert far["hours"] == "unknown" and far["phone"] == "unknown" and far["rating"] is None
    assert out["sources"] == ["Google Maps"] and out["crawled"] == "2026-10-29"


def test_a_user_word_maps_to_the_kind_and_the_group(turn):
    assert [r["name"] for r in call(turn(), "find_services", kind="rút tiền", near_place="0xa:0x1")["rows"]][0].startswith("ATM")
    assert [r["name"] for r in call(turn(), "find_services", kind="thuê xe máy", near_place="0xa:0x1")["rows"]] == ["Thuê xe máy Z"]
    assert call(turn(), "find_services", kind="services", near_place="0xa:0x1")["found"] == 3


def test_anchor_defaults_to_the_trip_lodging():
    from trip.domain.state import Base
    state = TripState()
    raw = state.model_dump(mode="json")
    raw["lodging"] = {"value": Base(text="Khách sạn A", lat=11.9429, lng=108.4372).model_dump(mode="json"), "source": "user",
                      "confidence": "high", "status": "confirmed", "evidence": [{"turn": 1, "quote": "ở khách sạn A"}]}
    lodged = TripState.model_validate(raw)
    from unittest.mock import MagicMock
    t = MagicMock(state=lodged, catalog=MagicMock(by_id={}))
    out = services_tool.find_services(t, services_tool.FindServices(kind="atm"))
    assert out["anchor"] == "Khách sạn A" and out["rows"][0]["distance_km"] is not None


def test_no_anchor_means_unknown_distance_not_a_made_up_one(turn):
    out = call(turn(), "find_services", kind="atm")
    assert out["rows"] and all(r["distance_km"] is None for r in out["rows"]) and "unknown" in out["anchor"]


def test_unknown_kind_and_no_data_are_said_not_invented(turn, monkeypatch):
    assert "unknown kind" in call(turn(), "find_services", kind="sân bay")["error"]
    monkeypatch.setattr(services_tool, "service_places", lambda city, group=None: [])
    out = call(turn(), "find_services", kind="atm", near_place="0xa:0x1")
    assert out["rows"] == [] and "no data" in out["note"]
    assert "no place" in call(turn(), "find_services", kind="atm", near_place="Quán Không Tồn Tại Này")["error"]


def test_services_are_never_cards_or_plan_places(turn):
    shown = []
    t = turn()
    t.on_cards = lambda ids, why: shown.append(ids)
    out = call(t, "find_services", kind="atm", near_place="0xa:0x1")
    assert "_cards" not in out and shown == []
    tool = REGISTRY.get("find_services")
    assert tool.cards is None and tool.group == "services"
    assert not {r["fid"] for r in ROWS} & set(t.catalog.by_id)  # not catalog places: Decision / Planning cannot pick them


def test_the_tool_is_offered_with_the_assistant(turn):
    assert "find_services" in set(turn().tool_names())


def test_real_data_shape_end_to_end(monkeypatch, tmp_path, turn):
    """The list file holds city-suffixed queries; through corpus.service_places the tool must still find the rows."""
    import json
    from corpus.crawl.gmaps import services as svc
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "gmaps" / "list").mkdir(parents=True)
    (tmp_path / "gmaps" / "list" / "dalat_svc.json").write_text(json.dumps({"items": [
        {"fid": "r1", "name": "Thuê xe máy Z", "lat": 11.944, "lng": 108.438, "group": "rental_tour",
         "queries": ["thuê xe máy Đà Lạt"], "category": "Cửa hàng xe máy"}]}), encoding="utf-8")
    monkeypatch.setattr(services_tool, "service_places", svc.load)
    out = call(turn(), "find_services", kind="thuê xe máy", near_place="Cà Phê Đồi Thông")
    assert [r["name"] for r in out["rows"]] == ["Thuê xe máy Z"] and out["rows"][0]["kind"] == "thuê xe máy"
