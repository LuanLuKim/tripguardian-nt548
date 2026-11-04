"""Arrival modes and the matrix's real handoff must share scheduling boundaries."""

import json
from pathlib import Path

import pytest

from trip import TripState, compile_frame, compile_search_input
from trip.domain.readback import build
from trip.domain.required import tabs
from trip.domain.state import Base, Field

MATRIX = (Path(__file__).resolve().parents[2] / ".superpowers/sdd/2026-11-03-prod-e2e/matrix/runs/after-deploy2-20261104-070935")


def field(value):
    return {"value": value, "source": "user", "confidence": "high", "status": "confirmed",
            "evidence": [{"turn": 1, "quote": "matrix logistics input"}]}


def matrix_state(name):
    context = json.loads((MATRIX / f"{name}.json").read_text())["search_input_context"]
    frame = context["frame"]
    return TripState.model_validate({
        **{key: field(context[key]) for key in ("start_date", "days", "checkin_at", "checkout_at") if context[key] is not None},
        "frame": {key: field(frame[key]) for key in ("arrive", "leave") if frame[key]},
    })


def test_matrix_self_arrival_at_nine_is_not_airport_processing():
    state = matrix_state("ambiguous_dates_next_weekend")
    si = compile_search_input(state)
    assert si.context.frame.days[0].start == "09:00"
    assert si.context.checkin_at == "09:00"
    assert not si.context.frame.issues
    assert "ngày 1 từ 09:00" in " · ".join(line.text for line in build(si).lines)


def test_matrix_flight_provides_routable_airport_and_identical_legacy_bounds():
    state = matrix_state("day_trip_early_flight")
    si = compile_search_input(state)
    assert (si.context.checkin_at, si.context.checkout_at) == ("09:45", "18:15")
    assert (si.context.frame.days[0].start, si.context.frame.days[0].end) == ("09:45", "18:15")
    for point in (si.context.entry_point, si.context.exit_point):
        assert point is not None and point.text == "Sân bay Liên Khương"
        assert (point.lat, point.lng) == (11.7502, 108.3672)
    assert si.sources["entry_point"] == si.sources["exit_point"] == "inferred"
    assert not state.entry_point.known and not state.exit_point.known


def test_repeat2_n5_readback_matches_hub_start_without_fixed_airport_road():
    state = TripState.model_validate({"start_date": field("2026-11-20"), "days": field(4), "frame": {
        "arrive": field({"at": "2026-11-20T09:00", "how": "plane"}),
        "leave": field({"at": "2026-11-23T18:00", "how": "plane"})}})
    si = compile_search_input(state)
    assert si.context.frame.days[0].start == "09:45"
    assert si.context.frame.days[-1].end == "17:15"
    text = " · ".join(line.text for line in build(si).lines)
    assert "ngày 1 từ 09:45" in text and "ngày cuối xong 17:15" in text
    assert si.context.entry_point.lat is not None and si.context.exit_point.lat is not None


def test_flight_inference_does_not_overwrite_explicit_boundary():
    state = matrix_state("day_trip_early_flight").model_copy(update={
        "entry_point": Field(**field(Base(text="Điểm đón riêng", lat=11.8, lng=108.4)))})
    si = compile_search_input(state)
    assert si.context.entry_point.text == "Điểm đón riêng"
    assert si.sources["entry_point"] == "user"
    assert si.context.exit_point is not None


def test_named_local_airport_gets_coordinates_without_overwriting_user_fact():
    state = matrix_state("day_trip_early_flight").model_copy(update={
        "entry_point": Field(**field(Base(text="Sân bay Liên Khương")))})
    si = compile_search_input(state)
    assert (si.context.entry_point.lat, si.context.entry_point.lng) == (11.7502, 108.3672)
    assert state.entry_point.value.lat is None
    assert si.sources["entry_point"] == "user"
    assert si.context.frame.days[0].start == "09:45"


def test_unknown_unroutable_hub_keeps_conservative_transfer_time():
    state = matrix_state("day_trip_early_flight").model_copy(update={
        "entry_point": Field(**field(Base(text="Điểm đón chưa định vị"))),
        "exit_point": Field(**field(Base(text="Điểm trả chưa định vị")))})
    si = compile_search_input(state)
    assert (si.context.frame.days[0].start, si.context.frame.days[0].end) == ("10:15", "17:45")
    assert si.context.entry_point.lat is None and si.context.exit_point.lat is None


def test_matrix_allergy_default_afternoon_is_not_an_arrival():
    state = matrix_state("allergy_peanut_no_alcohol")
    before = compile_search_input(state)
    assert before.context.frame.days[0].start == "14:00"
    assert before.context.frame.arrive is None and before.context.checkin_at is None
    assert any(line.kind == "default" and "14:00" in line.text for line in build(before).lines)
    confirmed = state.model_copy(update={"checkin_at": Field(**field("09:00"))})
    after = compile_search_input(confirmed)
    assert after.context.frame.days[0].start == after.context.checkin_at == "09:00"
    assert after.context.frame.arrive is None


@pytest.mark.parametrize("how,start,end", [("self", "09:00", "19:00"), ("plane", "10:15", "17:45"), ("bus", "10:15", "17:45")])
def test_first_and_last_bounds_follow_each_moments_mode(how, start, end):
    state = matrix_state("day_trip_early_flight")
    frame = state.frame.model_copy(update={
        key: getattr(state.frame, key).model_copy(update={"value": getattr(state.frame, key).value.model_copy(update={"how": how})})
        for key in ("arrive", "leave")})
    result = compile_frame(state.model_copy(update={"frame": frame}))
    assert (result.days[0].start, result.days[0].end) == (start, end)


def test_mixed_mode_does_not_reuse_inbound_buffer_for_outbound():
    state = matrix_state("day_trip_early_flight")
    frame = state.frame.model_copy(update={"leave": state.frame.leave.model_copy(update={
        "value": state.frame.leave.value.model_copy(update={"how": "self"})})})
    si = compile_search_input(state.model_copy(update={"frame": frame}))
    assert (si.context.checkin_at, si.context.checkout_at) == ("09:45", "19:00")


def test_separate_hub_margins_are_loaded_from_planning_config(tmp_path):
    from trip import load_settings

    (tmp_path / "trip.yaml").write_text("entry_min: 30\n")
    (tmp_path / "planning.yaml").write_text("realistic:\n  arrive_buffer_min: 20\n  leave_buffer_min: 60\n")
    cfg = load_settings(tmp_path / "trip.yaml")
    si = compile_search_input(matrix_state("day_trip_early_flight"), cfg.arrival_buffer_min,
                              entry_min=cfg.entry_min, departure_buffer_min=cfg.departure_buffer_min)
    assert (si.context.frame.days[0].start, si.context.frame.days[0].end) == ("09:20", "18:00")


def test_custom_config_reaches_readback_and_frame_without_second_rule():
    si = compile_search_input(matrix_state("day_trip_early_flight"), 20, entry_min=10)
    assert (si.context.checkin_at, si.context.checkout_at) == ("09:20", "18:40")
    text = " · ".join(line.text for line in build(si).lines)
    assert "ngày 1 từ 09:20" in text and "ngày cuối xong 18:40" in text


def test_runtime_flight_uses_planning_hub_margins_without_fixed_transfer():
    from trip import load_settings

    cfg = load_settings()
    si = compile_search_input(matrix_state("day_trip_early_flight"), cfg.arrival_buffer_min,
                              entry_min=cfg.entry_min)
    assert (si.context.frame.days[0].start, si.context.frame.days[0].end) == ("09:45", "18:15")
    assert (si.context.checkin_at, si.context.checkout_at) == ("09:45", "18:15")
    text = " · ".join(line.text for line in build(si).lines)
    assert "ngày 1 từ 09:45" in text and "ngày cuối xong 18:15" in text
    assert "ước tính 45 phút ra khỏi sân bay" in text


def test_gate_without_dates_uses_same_self_arrival_boundary(cfg):
    state = matrix_state("ambiguous_dates_next_weekend")
    state = state.model_copy(update={"start_date": Field(), "checkin_at": Field(),
        "frame": state.frame.model_copy(update={"arrive": state.frame.arrive.model_copy(update={"source": "inferred"})})})
    tab = next(tab for tab in tabs(state, cfg) if tab.qid == "trip")
    option = next(opt for opt in tab.options if opt.id == "start.default")
    assert option.writes[0].value == "09:00"
