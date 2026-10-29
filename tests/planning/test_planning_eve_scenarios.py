"""Spec §D.3 "Đo": the synthetic scenario set must pass before eve_replan.enabled may be true."""

import eve_scenarios
from plan_fixtures import CFG


def test_the_synthetic_scenarios_all_pass():
    result = eve_scenarios.run()
    bad = {r["scenario"]: r["problems"] for r in result["rows"] if r["problems"]}
    assert result["ok"], bad
    assert sum(r["needed"] for r in result["rows"]) == 5 and sum(not r["needed"] for r in result["rows"]) == 3


def test_the_feature_flag_is_only_on_when_the_scenarios_pass():
    if CFG.eve_replan["enabled"]:
        assert eve_scenarios.run()["ok"]
