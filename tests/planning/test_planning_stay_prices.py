"""Dated lodging prices for the trip's own stay lie over the reference night price (docs/PLANNING.md ⓐ)."""

from datetime import UTC, datetime, timedelta

from plan_fixtures import CENTRE, CFG, decision, rec, stay

from planning import stayprice
from planning.places import build_places
from planning.lodging import anywhere, candidates, from_record, price_cap

NOW = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)
SEEN = (NOW - timedelta(hours=5)).isoformat()


def row(fid, night, *, date="2026-12-12", nights=1):
    return {"fid": fid, "stay_date": date, "nights": nights, "price_night_vnd": night, "price_total_vnd": night * nights,
            "observed_at": SEEN, "source": "gtravel"}


def prices(*rows):
    return {(r["fid"], r["stay_date"], r["nights"]): r for r in rows}


def tc(**over):
    return {"start_date": "2026-12-12", "days": 2, **over}


def fixed(monkeypatch, table, asked=None):
    def load(city, max_age_h=None):
        if asked is not None:
            asked.append((city, max_age_h))
        return table
    monkeypatch.setattr(stayprice, "load_prices", load)


def test_a_dated_price_for_the_trips_own_stay_replaces_the_reference_price(monkeypatch):
    asked = []
    fixed(monkeypatch, prices(row("h1", 450_000)), asked)
    (c,) = stayprice.overlay([from_record(stay("h1", *CENTRE, price=300_000))], tc(), CFG)
    assert (c["price_vnd"], c["price_kind"], c["price_at"]) == (450_000, "dated", SEEN)
    assert asked == [("dalat", CFG.stay_price_max_age_h)]            # old rows are dropped by the loader, not guessed


def test_the_price_age_comes_from_observed_at():
    assert stayprice.age_h(SEEN, NOW) == 5.0
    assert stayprice.age_h(None, NOW) is None and stayprice.age_h("not a date", NOW) is None


def test_another_stay_length_or_date_is_not_the_trips_stay(monkeypatch):
    fixed(monkeypatch, prices(row("h1", 450_000, nights=2), row("h1", 460_000, date="2026-12-13")))
    (c,) = stayprice.overlay([from_record(stay("h1", *CENTRE, price=300_000))], tc(), CFG)
    assert (c["price_vnd"], c["price_kind"]) == (300_000, "reference")


def test_no_price_anywhere_stays_unknown(monkeypatch):
    fixed(monkeypatch, {})
    (c,) = stayprice.overlay([from_record(stay("h1", *CENTRE))], tc(), CFG)
    assert c["price_vnd"] is None and c["price_kind"] is None


def test_without_a_start_date_or_nights_only_the_reference_is_used(monkeypatch):
    fixed(monkeypatch, prices(row("h1", 450_000)))
    (c,) = stayprice.overlay([from_record(stay("h1", *CENTRE, price=300_000))], tc(start_date=None), CFG)
    assert (c["price_vnd"], c["price_kind"]) == (300_000, "reference")


def test_the_price_cap_uses_the_dated_price(monkeypatch):
    fixed(monkeypatch, prices(row("h1", 900_000)))
    records = [stay("h1", CENTRE[0] + 0.001, CENTRE[1], price=300_000), stay("h2", CENTRE[0] - 0.001, CENTRE[1], price=300_000)]
    d = decision(["a"], budget=500_000)
    cap = price_cap(d["trip_context"]["context"], 1, CFG)
    got = anywhere(d, CFG, records, limit=None)
    assert 300_000 < cap < 900_000 and {c["id"] for c in got} == {"h2"}     # h1 passes on its reference price only


def test_candidates_carry_the_dated_price(monkeypatch):
    fixed(monkeypatch, prices(row("h1", 450_000)))
    a = rec("a", *CENTRE)
    (pa,), _ = build_places(decision(["a"]), {"a": a}, CFG)
    got = candidates({"a": pa}, decision(["a"]), CFG, [stay("h1", CENTRE[0] + 0.001, CENTRE[1], price=300_000)])
    assert [(c["price_vnd"], c["price_kind"]) for c in got] == [(450_000, "dated")]


def test_the_lodging_card_says_how_old_the_dated_price_is_and_never_makes_one_up(monkeypatch):
    from test_planning_lodging_rank import engine, stay as card_stay
    from plan_fixtures import sample_trip
    d, recs = sample_trip()
    ctx = d["trip_context"]["context"]
    observed = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    table = {("priced", ctx["start_date"], 1): {**row("priced", 410_000, date=ctx["start_date"]), "observed_at": observed}}
    monkeypatch.setattr(stayprice, "load_prices", lambda city, max_age_h=None: table)
    out = engine(recs + [card_stay("priced", 3, night=300_000), card_stay("plain", 2, night=250_000), card_stay("none", 1)]).lodging_options(
        {**d, "confirmed": []})
    cards = {c["id"]: c for c in out["candidates"]}
    assert (cards["priced"]["price_vnd"], cards["priced"]["price_kind"], cards["priced"]["price_age_h"]) == (410_000, "dated", 3.0)
    assert (cards["plain"]["price_vnd"], cards["plain"]["price_kind"], cards["plain"]["price_age_h"]) == (250_000, "reference", None)
    assert (cards["none"]["price_vnd"], cards["none"]["price_kind"], cards["none"]["price_age_h"]) == (None, None, None)
