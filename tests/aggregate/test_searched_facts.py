"""Hours and entry price found by Google search (source `gsearch`): they fill what Maps and the own site lack, and say
whose word they are."""
from datetime import date

import pytest

from corpus.aggregate import estimates as estimates_mod, place as place_mod

from corpus.aggregate import aggregate_place
from corpus.aggregate.estimates import entry_fee, fact_bases
from corpus.ontology import load
from corpus.serving.record import _entry_fee, _hours

ONT = load()
WEEK = {d: [["07:30", "17:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


@pytest.fixture(autouse=True)
def all_bases_enabled(monkeypatch):
    """The label-gate config is not what these tests are about: every basis is read (the gate has its own test)."""
    monkeypatch.setattr(estimates_mod, "enabled_bases", lambda: frozenset({"google_panel", "official_site", "web"}))
    monkeypatch.setattr(place_mod, "enabled_bases", lambda: frozenset({"google_panel", "official_site", "web"}))


def doc(source=None, **facts):
    return {"place_fid": "F", "place_name": "P", "as_of": "2026-10-29", "ontology_version": ONT.version, "observations": [],
            "details": [], **({"source": source} if source else {}), "place_facts": facts}


def ev(basis, **kw):
    return {"basis": basis, "url": "https://x.vn/a", "quote": "q", "at": "2026-10-29", "dated": None, "domains": 1, **kw}


def test_search_hours_fill_only_when_maps_and_own_site_have_none():
    searched = doc("gsearch", hours=WEEK, hours_evidence=ev("google_panel"))
    op = aggregate_place([searched], ONT)["operation"]
    assert op["hours"] == WEEK and op["hours_source"] == "google_panel" and op["hours_as_of"] == "2026-10-29"
    assert op["hours_fact"] is (fact_bases() >= {"google_panel"})
    maps = doc(hours={"mon": [["08:00", "12:00"]]})
    op = aggregate_place([maps, searched], ONT)["operation"]
    assert op["hours"] == {"mon": [["08:00", "12:00"]]} and op["hours_source"] == "maps"
    own = doc("official", hours={"tue": [["09:00", "10:00"]]})
    assert aggregate_place([searched, own], ONT)["operation"]["hours_source"] == "official"


def test_served_hours_from_a_web_page_are_an_uncertain_estimate_a_panel_is_a_fact():
    built = date(2026, 10, 30)
    web = {"hours": WEEK, "hours_source": "web", "hours_as_of": "2026-10-29", "hours_evidence": ev("web"), "hours_fact": False}
    h = _hours(web, date(2026, 10, 1), built)
    assert h["status"] == "UNCERTAIN" and h["kind"] == "estimate" and h["as_of"] == "2026-10-29"
    panel = {**web, "hours_source": "google_panel", "hours_evidence": ev("google_panel"), "hours_fact": True}
    h = _hours(panel, date(2026, 10, 1), built)
    assert h["status"] == "VERIFIED" and h["source"] == "google_panel" and "kind" not in h


def test_entry_fee_order_official_site_then_own_panel_line_then_reviews_then_pages_then_maps_then_free():
    official = {"adult": [50000]}
    panel = {"tickets": {"adult": [150000]}, "evidence": ev("google_panel")}
    web2 = {"tickets": {"adult": [100000, 120000], "child": [50000]}, "evidence": ev("web", domains=2)}
    web1 = {"tickets": {"adult": [100000]}, "evidence": ev("web")}
    paid = {"id": "r1", "feature": "entry_fee", "value": "paid", "author": "a", "observed_at": "2026-09-01",
            "span": {"quote": "vé vào cổng 80k"}}
    assert entry_fee([paid], None, official, panel)["source"] == "official"
    got = entry_fee([paid], None, None, panel)
    if "google_panel" in fact_bases():
        assert got["source"] == "google_panel" and got["typical_vnd"] == 150000 and got["fact"]
    else:  # a basis that has not passed the label gate is an estimate: it waits behind the reviewers' words
        assert got["source"] == "reviews"
    assert entry_fee([paid], None, None, web1)["source"] == "reviews"  # one page is weaker than a reviewer's quote
    got = entry_fee([paid], None, None, web2)
    assert got["source"] == "web" and (got["min_vnd"], got["typical_vnd"], got["max_vnd"]) == (50000, 100000, 120000)
    assert entry_fee([], None, None, web1)["source"] == "web"
    assert entry_fee([], 5, None, web1)["source"] == "web"  # a price some page states beats Maps' US$ box
    free = {"free": True, "evidence": ev("google_panel")}
    assert entry_fee([], None, None, free) == {** {"min_vnd": 0, "typical_vnd": 0, "max_vnd": 0, "n": 1, "source": "google_panel",
                                               "free": True, "fact": "google_panel" in fact_bases(), "evidence": free["evidence"]}}
    assert entry_fee([paid], None, None, free)["typical_vnd"] == 80000  # a price anywhere beats "free"
    assert entry_fee([], None, None, None) is None


def test_served_entry_fee_kind_and_status():
    built = date(2026, 10, 30)
    fee = {"min_vnd": 150000, "typical_vnd": 150000, "max_vnd": 150000, "n": 1, "source": "google_panel", "fact": True,
           "evidence": ev("google_panel")}
    out = _entry_fee(fee, built)
    assert out["kind"] == "fact" and out["status"] == "VERIFIED" and out["as_of"] == "2026-10-29"
    old = _entry_fee({**fee, "evidence": ev("google_panel", at="2025-01-01")}, built)
    assert old["kind"] == "fact" and old["status"] == "OUTDATED"
    web = _entry_fee({**fee, "source": "web", "fact": False, "evidence": ev("web")}, built)
    assert web["kind"] == "estimate" and "status" not in web
    assert _entry_fee({"min_vnd": 1, "typical_vnd": 1, "max_vnd": 1, "n": 1, "source": "official"}, built)["kind"] == "fact"
    assert _entry_fee(None, built) is None


def test_aggregate_carries_search_price_into_estimates():
    searched = doc("gsearch", tickets_vnd={"adult": [150000]}, tickets_evidence=ev("google_panel"))
    est = aggregate_place([searched], ONT)["estimates"]["entry_fee"]
    assert est["source"] == "google_panel" and est["typical_vnd"] == 150000
    free = doc("gsearch", entry_free=ev("web"))
    assert aggregate_place([free], ONT)["estimates"]["entry_fee"]["free"] is True


def test_a_basis_that_has_not_passed_the_label_gate_is_ignored(monkeypatch):
    monkeypatch.setattr(place_mod, "enabled_bases", lambda: frozenset({"web"}))
    panel = doc("gsearch", hours=WEEK, hours_evidence=ev("google_panel"), tickets_vnd={"adult": [150000]},
                tickets_evidence=ev("google_panel"))
    res = aggregate_place([panel], ONT)
    assert res["operation"]["hours"] is None and res["estimates"]["entry_fee"] is None
    web = doc("gsearch", hours=WEEK, hours_evidence=ev("web"))
    assert aggregate_place([web], ONT)["operation"]["hours_source"] == "web"
