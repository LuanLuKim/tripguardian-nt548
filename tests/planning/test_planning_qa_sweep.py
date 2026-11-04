"""The QA sweep must cross the same typed boundary as a real Decision Output."""

import importlib.util
import random
from pathlib import Path

from decision import DecisionOutput
from plan_fixtures import CENTRE, spot


def test_sweep_uses_real_handoff_shape_and_valid_meal_wishes():
    path = Path(__file__).resolve().parents[2] / ".superpowers/sdd/2026-11-03-prod-e2e/plan-qa/sweep.py"
    spec = importlib.util.spec_from_file_location("qa_sweep", path)
    sweep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sweep)
    records = [spot("home", CENTRE, 0, group="stay"),
               spot("sight", CENTRE, 1, group="attraction"),
               spot("food", CENTRE, 2, group="restaurant", usable=("meal",))]
    sc = dict(id="shape", comp=["partner"], people=2, days=2, n=2, mob="motorbike",
              pace="normal", dishes=["bánh căn"])
    d, _ = sweep.decision_for(sc, records, random.Random("shape"))
    parsed = DecisionOutput.model_validate(d)
    ctx = parsed.trip_context.context
    assert ctx.base.place_id == "home"
    assert ctx.lodging.place_id == "home"
    assert ctx.checkin_at == "14:00" and ctx.checkout_at == "12:00"
    assert parsed.trip_context.wishes.dishes[0].dish == "bánh căn"
    row = sweep.run(sc, records, {r["id"]: r for r in records})
    assert row["independent_violations"] == row["view_violations"]
    assert row["validation_matches_view"]
