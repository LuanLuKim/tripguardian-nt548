"""Sightseeing starts are wishes; city arrivals remain physical bounds."""

from datetime import date

import pytest

from trip import TripState, compile_frame
from trip.domain.guard import record_fact


def trip_state(**fields):
    def said(value):
        return {"value": value, "source": "user", "confidence": "high", "status": "confirmed",
                "evidence": [{"turn": 1, "quote": "2 ngày từ 11/11/2026"}]}

    return TripState.model_validate({"start_date": said("2026-11-11"), "days": said(2), **fields})


@pytest.mark.parametrize("quote", ["8h xuất phát từ homestay", "sáng 8h đi từ khách sạn", "sáng 8h xuất phát từ homestay"])
def test_daily_departure_recorded_as_arrival_still_starts_at_eight(catalog, quote):
    state, note = record_fact(trip_state(), "frame.arrive", "set", "2026-11-11T08:00", quote,
                              "said", quote, 1, catalog)
    assert not note.startswith("refused")
    assert not state.frame.arrive.known
    assert state.checkin_at.value == "08:00"
    assert state.checkin_at.evidence[0].quote == quote
    assert compile_frame(state).days[0].start == "08:00"


@pytest.mark.parametrize("quote,value,want", [
    ("xe tới 5h sáng", '{"at":"2026-11-11T05:00","how":"bus"}', "06:15"),
    ("máy bay hạ cánh 9h", '{"at":"2026-11-11T09:00","how":"plane"}', "10:15"),
    ("xe xuất phát đêm trước, xe tới 5h sáng", '{"at":"2026-11-11T05:00","how":"bus"}', "06:15"),
])
def test_city_arrivals_keep_buffer_and_entry_road(catalog, quote, value, want):
    state, note = record_fact(trip_state(), "frame.arrive", "set", value, quote, "said", quote, 1, catalog)
    assert note == ""
    assert state.frame.arrive.known
    assert compile_frame(state).days[0].start == want


def test_daily_start_does_not_erase_a_real_arrival(catalog):
    state = trip_state(frame={"arrive": {"value": {"at": "2026-11-11T09:00", "how": "plane"},
                                       "source": "user", "confidence": "high", "status": "confirmed",
                                       "evidence": [{"turn": 1, "quote": "máy bay hạ cánh 9h"}]}})
    quote = "sáng 8h đi từ homestay"
    state, _ = record_fact(state, "frame.arrive", "set", "2026-11-11T08:00", quote, "said", quote, 2, catalog)
    frame = compile_frame(state)
    assert frame.arrive.at == "2026-11-11T09:00"
    assert frame.days[0].start == "10:15"
    assert "start_before_arrival" in {issue.code for issue in frame.issues}


def test_agent_hour_only_fact_reaches_frame_as_sightseeing_start(catalog, tmp_path):
    from trip.agent.tools import TurnTools

    quote = "sáng 8h xuất phát từ homestay"
    tools = TurnTools(trip_state(), quote, 2, catalog, date(2026, 11, 3), gaps=tmp_path / "gaps.jsonl")
    result = tools.run("record_fact", {"facts": [{"field": "frame.arrive", "op": "set", "value": "08:00",
                                                "quote": quote, "how": "said"}]})
    assert not any("error" in row for row in result["results"]), result
    assert compile_frame(tools.state).days[0].start == "08:00"
    assert not tools.state.frame.arrive.known


@pytest.mark.parametrize("quote", ["8h xuất phát từ Sài Gòn", "xe khách xuất phát 8h", "8h đi Đà Lạt"])
def test_intercity_departure_is_neither_city_arrival_nor_daily_start(catalog, quote):
    state, note = record_fact(trip_state(), "frame.arrive", "set", "2026-11-11T08:00", quote,
                              "said", quote, 1, catalog)
    assert note.startswith("refused")
    assert not state.frame.arrive.known
    assert not state.checkin_at.known
