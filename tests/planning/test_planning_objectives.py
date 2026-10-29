import pytest
from plan_fixtures import CFG, day_ctx, rec

from planning.objectives import LABEL, add_lodging_cost, metrics, score
from planning.route import order_day


def test_metrics_add_up_travel_known_costs_exposure_repeats_and_preference_risk():
    price = {"min_vnd": 50000, "typical_vnd": 50000, "max_vnd": 50000}
    recs = [rec("a", 1, 1, price=price, features={"weather_exposed": "present"}, group="park"),
            rec("b", 1, 1, group="park"), rec("c", 1, 1, group="cafe", features={"setting": "indoor"})]
    cx = day_ctx(recs, rain=0.5, prefs={"a": 2.0}, start_node="h", extra_nodes=["h"])
    m = metrics([cx], [order_day(["a", "b", "c"], cx)])
    assert (m["cost_vnd"], m["cost_unknown"]) == (50000, 2)
    assert (m["rain_exposed"], m["exposure_unknown"], m["repeats"]) == (0.5, 1, 1)
    assert m["pref_risk"] == pytest.approx(1.0) and m["travel_min"] > 0


def test_each_objective_scores_on_its_own_measure_then_on_travel():
    m = {"travel_min": 90, "cost_vnd": 120000, "rain_exposed": 0.4, "repeats": 2, "pref_risk": 1.5}
    assert [score(o, m) for o in ("least_travel", "low_cost", "weather_robust", "diverse", "preference_fit")] == [
        (90, 90), (120000, 90), (0.4, 90), (2, 90), (1.5, 90)]
    assert set(LABEL) == set(CFG.objective_weights)


def test_add_lodging_cost_merges_a_known_price_or_counts_it_unknown():
    m = {"cost_vnd": 100000, "cost_unknown": 1}
    assert add_lodging_cost(m, 50000, 3)["cost_vnd"] == 250000
    assert add_lodging_cost(m, None, 3)["cost_unknown"] == 2
