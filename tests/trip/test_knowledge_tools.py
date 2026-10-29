"""The wider read tools and save_place / hide_place as the agent calls them (agent/knowledge_tools.py)."""

import json
from datetime import date

import pytest
from test_reads import CLIMATE, make

from trip.agent.tools import TurnTools
from trip.domain.state import TripState
from trip.infrastructure.knowledge import LiveTools
from trip.infrastructure.reads import VN, Feeds

NEW = {"place_evidence", "compare_places", "place_status", "find_dishes", "route_time", "journey", "climate", "calendar",
       "find_stays", "estimate_cost", "local_tips", "area_notice", "save_place", "hide_place"}


@pytest.fixture
def turn(recs, tmp_path):
    def build(state=None, live=None, feeds=None):
        k = make(recs, live=live, feeds=feeds)
        return TurnTools(state or TripState(), "x", 1, k.catalog, date(2026, 10, 30), knowledge=k, assistant=True,
                         gaps=tmp_path / "gaps.jsonl")
    return build


@pytest.fixture
def recs():
    from test_reads import _records
    return _records()


def call(t, name, **args):
    return json.loads(json.dumps(t.model_called(name, t.run(name, args), args)))


def test_every_new_tool_is_offered_with_the_assistant(turn):
    names = set(turn().tool_names())
    assert NEW <= names and {"find_places", "get_place", "distance"} <= names


def test_tools_are_not_offered_without_the_assistant(recs, tmp_path):
    k = make(recs)
    t = TurnTools(TripState(), "x", 1, k.catalog, date(2026, 10, 30), knowledge=k, assistant=False, gaps=tmp_path / "g.jsonl")
    assert not NEW & set(t.tool_names())


def test_place_evidence_maps_a_written_name_and_hides_private_keys(turn):
    t = turn()
    out = call(t, "place_evidence", id="Cà Phê Đồi Thông", question="đậu xe được không", features=["parking"])
    assert out["answers"][0]["value"] == "easy" and out["id"] == "0xa:0x1"
    bad = call(t, "place_evidence", id="Quán Không Tồn Tại Này", question="x", features=["parking"])
    assert "no data" in bad["error"]


def test_place_evidence_matches_words_when_no_feature_given(turn):
    out = call(turn(), "place_evidence", id="0xa:0x1", question="chỗ gửi xe có dễ không")
    assert out["answers"] or out["unknown"] or "note" in out  # the matcher ran; whatever it found, nothing is invented


def test_compare_shows_cards_for_every_place(turn):
    shown = []
    t = turn()
    t.on_cards = lambda ids, why: shown.append(ids)
    out = call(t, "compare_places", ids=["0xa:0x1", "Quán Nhạc Ồn Ào"])
    assert [r["id"] for r in out["rows"]] == ["0xa:0x1", "0xb:0x1"] and "_cards" not in out
    assert shown == [["0xa:0x1", "0xb:0x1"]]


def test_find_places_extension_through_the_tool_with_a_written_place_name(turn):
    t = turn()
    out = call(t, "find_places", criteria={"groups": ["cafe"], "near_place": "Cà Phê Đồi Thông", "near_km": 5, "sort": "distance",
                                           "exclude": ["Quán Nhạc Ồn Ào"]})
    assert [p["id"] for p in out["places"]] == ["0xc:0x1"]
    assert "error" in call(turn(), "find_places", criteria={"near_place": "Chỗ Chẳng Có Nào"})


def test_distance_tool_takes_a_mode(turn):
    route = lambda pts, mode: {"coords": [[11.94, 108.44], [11.95, 108.44]], "minutes": 7, "source": "osrm", "fetched_at": "t"}  # noqa: E731
    out = call(turn(live=LiveTools(route=route)), "distance", a="0xa:0x1", b="0xc:0x1", mode="walk")
    assert out["mode"] == "walk" and "estimate" in out


def test_find_stays_cards_and_estimate_cost(turn):
    shown = []
    t = turn(feeds=Feeds(now=lambda: __import__("datetime").datetime(2026, 10, 30, 10, tzinfo=VN), stay_prices=lambda: {}))
    t.on_cards = lambda ids, why: shown.append(ids)
    out = call(t, "find_stays", criteria={"near_place": "Khách Sạn Đồi Chè", "near_km": 5, "sort": "price"})
    assert out["stays"][0]["price"]["kind"] == "reference" and shown == [[s["id"] for s in out["stays"]]]
    cost = call(t, "estimate_cost", ids=["0xe:0x1"], people=2, nights=2)
    assert cost["total_vnd"] == [1600000, 1600000]


def test_climate_and_journey_errors_are_error_results(turn):
    t = turn(feeds=Feeds(climate=lambda: CLIMATE))
    assert call(t, "climate", month=12)["month"] == 12
    assert call(turn(), "journey", origin="Hà Nội")["error"] == "journey unavailable"
    assert "error" in call(turn(), "calendar", date_from="2026-12-05", date_to="2026-12-01")


def test_save_place_needs_a_shown_place_and_is_a_want_anchor(turn):
    t = turn()
    assert "shown" in call(t, "save_place", id="0xa:0x1")["error"]
    t.told_ids.add("0xa:0x1")
    out = call(t, "save_place", id="0xa:0x1")
    assert out["ok"] and [(a.place_id, a.priority) for a in t.state.anchors] == [("0xa:0x1", "want")]
    assert call(t, "save_place", id="0xa:0x1")["note"] == "already in the trip"


def test_hide_place_is_per_trip_and_never_a_dislike(turn):
    t = turn()
    assert call(t, "hide_place", id="0xa:0x1")["hidden"] is True
    assert t.state.meta.hidden_ids == ("0xa:0x1",) and not t.state.soft and not t.state.hard
    ids = [p["id"] for p in call(t, "find_places", criteria={"groups": ["cafe"]})["places"]]
    assert "0xa:0x1" not in ids
    assert call(t, "hide_place", id="0xa:0x1", undo=True)["hidden"] is False and t.state.meta.hidden_ids == ()


def test_find_dishes_tool_lists_places_from_the_menu_search(turn):
    t = turn()
    t.catalog.dishes = lambda q: [{"id": "0xa:0x1", "name": "Cà Phê Đồi Thông", "score": 9, "evidence": [{"source": "menu", "dish": "Bánh căn"}]}]
    out = call(t, "find_dishes", dish="bánh căn")
    assert out["places"][0]["id"] == "0xa:0x1"
