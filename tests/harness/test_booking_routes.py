"""Harness read routes for booking offers and the journey to the lodging, and the booking_click event name."""

import json

import pytest

from harness import booking_routes
from harness.events import CLIENT


def test_booking_click_is_a_client_event_with_only_the_offer_props():
    assert CLIENT["booking_click"] == {"offer_id", "provider", "kind"}


def test_flight_offers_are_json_ready_links(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))  # no published flights: the link alone
    out = booking_routes.offers({"kind": "flight", "src": "SGN", "dst": "DLI", "date": "2026-11-12"})
    json.dumps(out)
    assert [o["provider"] for o in out["offers"]] == ["google_flights"] and out["offers"][0]["price_vnd"] is None


def test_stay_offers_read_the_published_prices(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    d = tmp_path / "serving" / "stay_prices"
    d.mkdir(parents=True)
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat(timespec="seconds")
    (d / "dalat.json").write_text(json.dumps({"items": [
        {"fid": "fid1", "stay_date": "2026-11-12", "nights": 2, "adults": 2, "price_total_vnd": 900000, "price_night_vnd": 450000,
         "available": True, "observed_at": now, "source": "gtravel", "url": "https://g/e", "cross_check": {}}]}))
    out = booking_routes.offers({"kind": "stay", "fid": "fid1", "check_in": "2026-11-12", "nights": "2"})
    assert [(o["provider"], o["price_vnd"]) for o in out["offers"]] == [("gtravel", 900000)]


def test_bad_parameters_are_value_errors_the_server_answers_with_400():
    for p in ({"kind": "stay", "fid": "x y", "check_in": "2026-11-12", "nights": "2"}, {"kind": "hotel"},
              {"kind": "flight", "src": "SG", "dst": "DLI", "date": "2026-11-12"}):
        with pytest.raises(ValueError):
            booking_routes.offers(p)


def test_journey_route_parses_points_and_date():
    seen = {}

    def fake(origin, day, dest, way):
        seen.update(origin=origin, day=day, dest=dest, way=way)
        import journey
        return journey.Journey(origin=origin, dest=dest or (1.0, 2.0), dest_is_centre=dest is None, way=way,
                               day=day.isoformat() if day else None, options=())
    out = booking_routes.journey_options({"lat": "10.78", "lng": "106.7", "dest_lat": "11.95", "dest_lng": "108.44",
                                          "date": "2026-11-12"}, fake)
    assert seen["origin"] == (10.78, 106.7) and seen["dest"] == (11.95, 108.44) and seen["way"] == "inbound"
    assert out["dest_is_centre"] is False and out["day"] == "2026-11-12"
    booking_routes.journey_options({"lat": "10.78", "lng": "106.7"}, fake)
    assert seen["dest"] is None and seen["day"] is None
    for bad in ({"lat": "10.7"}, {"lat": "x", "lng": "1"}, {"lat": "10", "lng": "100", "dest_lat": "11"},
                {"lat": "10", "lng": "100", "date": "soon"}, {"lat": "10", "lng": "100", "way": "up"}):
        with pytest.raises(ValueError):
            booking_routes.journey_options(bad, fake)


@pytest.mark.parametrize("way", ["inbound", "outbound"])
def test_text_origin_uses_only_a_known_city_point(way):
    seen = {}

    def fake(origin, day, dest, direction):
        import journey
        seen.update(origin=origin, way=direction)
        return journey.Journey(origin=origin, dest=(11.94, 108.44), dest_is_centre=True,
                               way=direction, day=None, options=())

    out = booking_routes.journey_options({"origin": "TP.HCM", "way": way}, fake)
    assert seen == {"origin": (10.7684, 106.6851), "way": way}
    assert out["options"] == []


@pytest.mark.parametrize("text", ["Một nơi chưa rõ", "Nhà gần TP.HCM"])
def test_unknown_text_origin_does_not_invent_coordinates_or_trips(text):
    def fail(*args):
        pytest.fail("an unresolved origin must not request routes")

    out = booking_routes.journey_options({"origin": text, "way": "outbound"}, fail)
    assert out["origin"] is None and out["options"] == []
    assert out["origin_text"] == text and out["reason"] == "unknown_origin"


def test_explicit_origin_point_wins_over_text():
    import journey
    out = booking_routes.journey_options({"origin": "TP.HCM", "lat": "16.46", "lng": "107.59"},
        lambda o, d, t, w: journey.Journey(origin=o, dest=(11.94, 108.44), dest_is_centre=True,
                                         way=w, day=None, options=()))
    assert out["origin"] == [16.46, 107.59]


def test_home_city_becomes_a_point_or_nothing():
    from harness import booking_routes
    assert booking_routes.home_point("Huế", lambda q: [{"lat": 16.46, "lng": 107.59, "province": "Thừa Thiên Huế"}]) == {
        "text": "Huế", "lat": 16.46, "lng": 107.59, "province": "Thừa Thiên Huế"}
    assert booking_routes.home_point("Huế", lambda q: []) is None
    assert booking_routes.home_point("  ", lambda q: [1]) is None


def test_self_entered_lodging_has_no_offers_not_an_error():
    """QA B12: the typed-in lodging has fid "@home"; the answer is an empty list, not a 400."""
    assert booking_routes.offers({"kind": "stay", "fid": "@home", "check_in": "2026-11-12", "nights": "2"}) == \
        {"offers": [], "reason": "self_entered_lodging"}
