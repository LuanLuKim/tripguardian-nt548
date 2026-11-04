"""Public Trip to Planning contract: hub margins once, airport road legs once."""

import json
from pathlib import Path

import pytest

from plan_fixtures import CENTRE, FakeLive, decision, fake_matrix, no_geocode, rec
from planning import Engine
from trip import TripState, compile_search_input, load_settings
from trip.domain.readback import build

MATRIX = Path(__file__).resolve().parents[2] / ".superpowers/sdd/2026-11-03-prod-e2e/matrix/runs/after-deploy2-20261104-070935"


def field(value):
    return {"value": value, "source": "user", "evidence": [{"turn": 1, "quote": "matrix logistics input"}]}


@pytest.mark.parametrize("case,mode,start", [
    ("day_trip_early_flight", "plane", "09:45"),
    ("ambiguous_dates_next_weekend", "self", "09:00"),
    ("day_trip_early_flight", "bus", "09:45"),
])
def test_readback_and_public_planning_share_window_and_routed_exit(case, mode, start):
    context = json.loads((MATRIX / f"{case}.json").read_text())["search_input_context"]
    frame = {key: field({**value, "how": mode}) for key in ("arrive", "leave")
             if (value := context["frame"][key])}
    fields = {key: field(context[key]) for key in ("start_date", "days", "checkin_at", "checkout_at")
              if context[key] is not None}
    if mode == "bus":
        fields.update({key: field({"text": "Bến xe Liên tỉnh Đà Lạt", "lat": 11.9276, "lng": 108.4446})
                       for key in ("entry_point", "exit_point")})
    state = TripState.model_validate({**fields, "frame": frame})
    cfg = load_settings()
    si = compile_search_input(state, cfg.arrival_buffer_min, entry_min=cfg.entry_min)
    output = decision(["a"], days=context["days"])
    output["trip_context"] = si.model_dump(mode="json")
    # The matrix proceeds through the gate; this fixture isolates its confirmed logistics handoff.
    output["trip_context"]["readiness"] = {"missing": [], "readback_ok": True}
    engine = Engine([rec("a", *CENTRE)], background=False, live_cfg=FakeLive(), geocode_fn=no_geocode,
                    matrix_fn=fake_matrix, sun_fn=lambda *args: None, route_fn=lambda *args: None)
    view = engine.create(output)["view"]
    assert view["itinerary"], view
    assert view["itinerary"][0]["window"][0] == start
    assert si.context.frame.days[0].start == start
    assert f"ngày 1 từ {start}" in " · ".join(line.text for line in build(si).lines)
    if mode in {"plane", "bus"}:
        last = view["itinerary"][-1]
        legs = [item for item in last["items"] if item["kind"] == "travel"]
        assert legs, last
        assert any(item.get("to") == "@exit" for item in legs), legs
        assert max(item["end"] for item in legs) <= "18:15"
        assert last["window"][1] == "18:15"
