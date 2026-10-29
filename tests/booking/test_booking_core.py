"""booking core: the Offer contract, typed queries at the boundary, affiliate tagging. No network, no clock."""

from datetime import date

import pytest

import booking
from booking.links import tag
from booking.settings import Settings

DAY = date(2026, 11, 12)


def cfg(**kw):
    base = dict(version=1, stay_city="dalat", stay_max_age_h=72.0, affiliate={})
    return Settings(**{**base, **kw})


def test_offer_id_is_stable_and_depends_on_what_the_offer_states():
    a = booking.Offer(provider="vexere", kind="coach", mode="deeplink", url="https://x/y", carrier="A", depart_at="2026-11-12T06:00")
    b = booking.Offer(provider="vexere", kind="coach", mode="deeplink", url="https://x/y", carrier="A", depart_at="2026-11-12T06:00")
    c = booking.Offer(provider="vexere", kind="coach", mode="deeplink", url="https://x/y", carrier="A", depart_at="2026-11-12T07:00")
    assert a.offer_id == b.offer_id and a.offer_id != c.offer_id and len(a.offer_id) == 16
    d = a.as_dict()
    assert d["offer_id"] == a.offer_id and d["price_vnd"] is None and d["observed_at"] is None  # unknown stays unknown


def test_affiliate_is_added_only_when_param_and_env_value_both_exist(monkeypatch):
    monkeypatch.delenv("BOOKING_X_ID", raising=False)
    c = cfg(affiliate={"vexere": {"param": "aff", "env": "BOOKING_X_ID"}})
    assert tag("https://v.com/a?date=1", "vexere", c) == "https://v.com/a?date=1"  # no value in .env
    monkeypatch.setenv("BOOKING_X_ID", "abc 1")
    assert tag("https://v.com/a?date=1", "vexere", c) == "https://v.com/a?date=1&aff=abc+1"
    assert tag("https://v.com/a", "vexere", c) == "https://v.com/a?aff=abc+1"
    assert tag("https://v.com/a", "other", c) == "https://v.com/a"
    assert tag("https://v.com/a", "vexere", cfg(affiliate={"vexere": {"param": None, "env": "BOOKING_X_ID"}})) == "https://v.com/a"


def test_query_from_params_validates_untrusted_input():
    q = booking.query_from_params("coach", {"lat": "10.8", "lng": "106.7", "date": "2026-11-12", "way": "inbound"})
    assert q == booking.CoachQuery(origin=(10.8, 106.7), day=DAY, way="inbound")
    assert booking.query_from_params("coach", {"origin": "Sài Gòn", "date": "2026-11-12"}).origin == "Sài Gòn"
    f = booking.query_from_params("flight", {"src": "sgn", "dst": "DLI", "date": "2026-11-12"})
    assert f == booking.FlightQuery(src="SGN", dst="DLI", day=DAY)
    s = booking.query_from_params("stay", {"fid": "0x1:0x2", "check_in": "2026-11-12", "nights": "2"})
    assert s == booking.StayQuery(fid="0x1:0x2", check_in=DAY, nights=2, city=None)
    for kind, bad in [("coach", {"lat": "999", "lng": "1", "date": "2026-11-12"}), ("coach", {"date": "2026-11-12"}),
                      ("coach", {"origin": "x", "date": "12/11/2026"}), ("coach", {"origin": "x", "date": "2026-11-12", "way": "up"}),
                      ("flight", {"src": "SG", "dst": "DLI", "date": "2026-11-12"}),
                      ("stay", {"fid": "a b", "check_in": "2026-11-12", "nights": "2"}),
                      ("stay", {"fid": "0x1:0x2", "check_in": "2026-11-12", "nights": "0"}),
                      ("hotel", {})]:
        with pytest.raises(ValueError):
            booking.query_from_params(kind, bad)


def test_offers_rejects_a_query_of_another_kind():
    with pytest.raises(ValueError):
        booking.offers("stay", booking.FlightQuery("SGN", "DLI", DAY), cfg())


def test_an_offer_with_both_times_is_a_pickable_transit_and_a_link_only_one_is_not():
    full = booking.Offer(provider="vexere", kind="coach", mode="deeplink", url="https://v/x", carrier="A", depart_at="2026-11-12T06:00:00",
                 arrive_at="2026-11-12T13:00:00", from_point="Sài Gòn", to_point="Đà Lạt", price_vnd=300000, source="vexere",
                 fetched_at="2026-10-29T03:00:00+00:00")
    t = full.as_dict()["transit"]
    assert t["mode"] == "bus" and t["depart_at"] == "2026-11-12T06:00"
    assert booking.Offer(provider="vexere", kind="coach", mode="deeplink", url="https://v/x").as_dict()["transit"] is None
    assert booking.Offer(provider="gtravel", kind="stay", mode="deeplink", url="https://v/x").as_dict()["transit"] is None
