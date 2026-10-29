"""The lodging cost line of the budget check: one row per night, the price with its kind and age, a warning (never a
block) when a night is dearer than the share of the budget set aside for lodging."""

from datetime import UTC, datetime, timedelta

from plan_fixtures import CFG

from planning.validate import lodging_budget

NOW = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)
SEEN = (NOW - timedelta(hours=5)).isoformat()
# 2 people x 2 days x 1_000_000 = 4M for the party; lodging_share of it over 2 nights is the per-night allowance
CTX = {"start_date": "2026-12-12", "days": 3, "nights": 2, "people": 2, "budget_vnd": 1_000_000}
CAP = round(6_000_000 * CFG.lodging_share / 2)


def lodging(price, kind="dated", at=SEEN):
    return {"id": "h1", "name": "Khách sạn A", "price_vnd": price, "price_kind": kind, "price_at": at}


def test_each_night_is_a_row_with_its_date_price_kind_and_age():
    line = lodging_budget(CTX, lodging(400_000), CFG, NOW)
    assert [(r["night"], r["date"], r["price_vnd"], r["price_kind"], r["price_age_h"]) for r in line["nights"]] == [
        (1, "2026-12-12", 400_000, "dated", 5.0), (2, "2026-12-13", 400_000, "dated", 5.0)]
    assert line["total_vnd"] == 800_000 and line["per_night_cap_vnd"] == CAP
    assert line["over_budget"] is False and line["over_vnd"] == 0


def test_a_reference_price_is_labelled_as_such_with_its_age():
    line = lodging_budget(CTX, lodging(300_000, "reference", "2026-11-30"), CFG, NOW)
    assert {(r["price_kind"], r["price_age_h"]) for r in line["nights"]} == {("reference", 36.0)}


def test_over_the_share_is_a_flag_and_the_amount_not_a_block():
    line = lodging_budget(CTX, lodging(CAP + 100_000), CFG, NOW)
    assert line["over_budget"] is True and line["over_vnd"] == 200_000
    assert [r["over_vnd"] for r in line["nights"]] == [100_000, 100_000]


def test_unknown_price_or_budget_is_unknown_not_over_and_not_within():
    line = lodging_budget(CTX, lodging(None, None, None), CFG, NOW)
    assert line["total_vnd"] is None and line["over_budget"] is None
    assert all(r["price_vnd"] is None and r["over_vnd"] is None for r in line["nights"])
    no_budget = lodging_budget({**CTX, "budget_vnd": None}, lodging(900_000), CFG, NOW)
    assert no_budget["per_night_cap_vnd"] is None and no_budget["over_budget"] is None and no_budget["total_vnd"] == 1_800_000


def test_no_lodging_or_no_night_gives_no_line():
    assert lodging_budget(CTX, None, CFG, NOW) is None
    assert lodging_budget({**CTX, "nights": 0, "days": 1}, lodging(400_000), CFG, NOW) is None


def test_without_a_start_date_the_rows_have_no_date():
    line = lodging_budget({**CTX, "start_date": None}, lodging(400_000), CFG, NOW)
    assert [r["date"] for r in line["nights"]] == [None, None]


def _engine(**kw):
    from plan_fixtures import FakeLive, LODGING, fake_matrix, no_geocode, sample_trip
    from planning import Engine
    from planning.session import Store
    d, recs = sample_trip(**kw)
    e = Engine(recs + LODGING, cfg=CFG, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode,
               matrix_fn=fake_matrix, sun_fn=lambda *a: (6 * 60, 17 * 60 + 30), route_fn=lambda *a: None, background=False)
    sid = e.create(d, None)["id"]
    e.act(sid, {"type": "pick_variant", "id": next(v for v in e.variants(sid) if v["status"] == "available")["id"]})
    return e, sid


def test_the_chosen_lodging_carries_the_line_into_the_view_and_the_confirmed_plan():
    e, sid = _engine(budget=5_000_000)
    view = e.act(sid, {"type": "pick_lodging", "id": "h1"})["view"]
    line = view["active_variant"]["lodging_budget"]
    assert line["nights"][0]["price_vnd"] == 300_000 and line["nights"][0]["price_kind"] == "reference"
    assert line["over_budget"] is False
    assert not any(w["code"] == "lodging_over_budget" for w in view["active_variant"]["warnings"])
    plan = e.confirm(sid)
    assert plan["cost"]["lodging_nights"]["total_vnd"] == line["total_vnd"]
    assert plan["lodging"]["chosen"]["price_kind"] == "reference"


def test_a_chosen_lodging_over_the_share_warns_and_keeps_every_stop():
    e, sid = _engine(budget=5_000_000)
    view = e.act(sid, {"type": "pick_lodging", "id": "h1"})["view"]
    stops = view["itinerary"]
    # the share allows the night price; a dearer price from the same stay (the price the user sees later) only warns
    s = e.store.get(sid)
    card = dict(view["active_variant"])
    card["lodging"] = {**card["lodging"], "price_vnd": 8_000_000, "price_kind": "dated", "price_at": SEEN}
    e._lodging_budget_line(card, s.decision["trip_context"]["context"])
    codes = [w["code"] for w in card["warnings"]]
    assert codes.count("lodging_over_budget") == 1
    e._lodging_budget_line(card, s.decision["trip_context"]["context"])      # idempotent: still one sentence
    assert [w["code"] for w in card["warnings"]].count("lodging_over_budget") == 1
    assert view["itinerary"] == stops
