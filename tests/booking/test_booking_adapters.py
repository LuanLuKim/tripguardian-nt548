"""Adapters: what each provider link may state, and nothing else. Sources are injected; no network."""

from datetime import UTC, date, datetime, timedelta


import booking
from booking.settings import Settings
from live import Unavailable

DAY = date(2026, 11, 12)
CFG = Settings(version=1, stay_city="dalat", stay_max_age_h=72.0,
               affiliate={"tripcom": {"param": "Allianceid", "env": "BOOKING_T_TEST"}})
ROWS = [{"mode": "bus", "carrier": "Thành Bưởi", "depart_at": "2026-11-12T22:00", "arrive_at": "2026-11-13T05:00",
         "from_point": "Bến xe Miền Đông", "to_point": "Bến xe Đà Lạt", "price_vnd": 320000,
         "source": "vexere", "fetched_at": "2026-10-28T10:00:00+00:00"},
        {"mode": "bus", "carrier": "Phương Trang", "depart_at": "2026-11-12T06:00", "arrive_at": "2026-11-12T13:00",
         "from_point": "Q.10", "to_point": "Đà Lạt", "price_vnd": None,
         "source": "vexere", "fetched_at": "2026-10-28T10:00:00+00:00"}]


def coach(source):
    return booking.offers("coach", booking.CoachQuery("Sài Gòn", DAY, "inbound"), CFG, {"vexere": source})


def test_coach_offers_state_only_what_the_page_showed():
    got = coach(lambda *a, **k: ROWS)
    assert [o.carrier for o in got] == ["Thành Bưởi", "Phương Trang"]
    first = got[0]
    assert first.kind == "coach" and first.mode == "deeplink" and first.provider == "vexere"
    assert first.price_vnd == 320000 and first.price_unit == "ticket" and first.observed_at == "2026-10-28T10:00:00+00:00"
    assert first.depart_at == "2026-11-12T22:00" and first.url.endswith("-129t23991.html?date=12-11-2026")
    assert got[1].price_vnd is None and got[1].observed_at is None  # no fare on the page: unknown, no observation either


def test_coach_with_no_trip_that_day_has_no_offer():
    assert coach(lambda *a, **k: []) == []


def test_unreadable_vexere_page_gives_one_link_without_price_or_time():
    def down(*a, **k):
        raise Unavailable("blocked")
    (o,) = coach(down)
    assert o.url and o.price_vnd is None and o.depart_at is None and o.carrier is None and o.observed_at is None


def test_coach_from_a_place_with_no_vexere_region_has_no_offer():
    q = booking.CoachQuery("Atlantis", DAY, "inbound")
    assert booking.offers("coach", q, CFG, {"vexere": lambda *a, **k: ROWS}) == []


def flights(rows, observed=None):
    found = {"src": "SGN", "dst": "DLI", "day": "2026-11-12", "observed_at": observed or hours_ago(2), "offers": rows}
    return {"google_flights": lambda city, max_age_h: {("SGN", "DLI", "2026-11-12"): found} if rows is not None else {}}


VJ = {"carrier": "Vietjet", "flight_no": "VJ 360", "depart_at": "2026-11-12T06:30", "arrive_at": "2026-11-12T07:25",
      "from_point": "Tân Sơn Nhất", "to_point": "Liên Khương", "price_vnd": 1210781, "stops": 0}
VN = {**VJ, "carrier": "Vietnam Airlines", "flight_no": None, "depart_at": "2026-11-12T09:55", "price_vnd": None}


def test_flight_without_a_crawled_search_is_a_prefilled_google_flights_link_and_nothing_more():
    (o,) = booking.offers("flight", booking.FlightQuery("SGN", "DLI", DAY), CFG, flights(None))
    assert o.provider == "google_flights" and o.mode == "deeplink" and o.url.startswith("https://www.google.com/travel/flights?q=")
    assert "SGN" in o.url and "DLI" in o.url and "2026-11-12" in o.url
    assert (o.price_vnd, o.depart_at, o.arrive_at, o.carrier, o.flight_no, o.observed_at) == (None,) * 6


def test_crawled_flights_state_what_the_page_showed_with_when_it_was_seen():
    got = booking.offers("flight", booking.FlightQuery("SGN", "DLI", DAY), CFG, flights([VJ, VN]))
    assert [o.carrier for o in got] == ["Vietjet", "Vietnam Airlines"]
    first = got[0]
    assert (first.price_vnd, first.price_unit, first.flight_no, first.stops, first.depart_at, first.arrive_at) == (
        1210781, "ticket", "VJ 360", 0, "2026-11-12T06:30", "2026-11-12T07:25")
    assert first.available is True and first.observed_at and first.url.startswith("https://www.google.com/travel/flights?q=")
    assert (got[1].price_vnd, got[1].price_unit, got[1].flight_no, got[1].available) == (None, None, None, None)  # not shown: unknown


def test_a_crawled_flight_is_pickable_as_the_trips_inbound():
    from trip.domain.state import Transit
    (o, _) = booking.offers("flight", booking.FlightQuery("SGN", "DLI", DAY), CFG, flights([VJ, VN]))
    t = o.as_dict()["transit"]
    assert t["mode"] == "plane" and t["carrier"] == "Vietjet" and t["source"] == "gflights" and t["stops"] == 0
    assert (t["from_point"], t["to_point"]) == ("Tân Sơn Nhất", "Liên Khương") and o.duration_min == 55
    Transit.model_validate(t)  # the payload the trip's inbound answer takes
    assert o.as_dict()["duration_min"] == 55


def test_the_flight_adapter_asks_for_a_search_no_older_than_the_config_allows():
    seen = {}

    def reader(city, max_age_h):
        seen.update(city=city, max_age_h=max_age_h)
        return {}
    (o,) = booking.offers("flight", booking.FlightQuery("SGN", "DLI", DAY), CFG, {"google_flights": reader})
    assert seen == {"city": "dalat", "max_age_h": CFG.flight_max_age_h} and o.price_vnd is None


def item(source, total, night, observed, url, cross=None):
    return {"fid": "f1", "stay_date": "2026-11-12", "nights": 2, "adults": 2, "price_total_vnd": total,
            "price_night_vnd": night, "available": True, "observed_at": observed, "source": source, "url": url,
            "cross_check": cross or {}}


def hours_ago(h):
    return (datetime.now(UTC) - timedelta(hours=h)).isoformat(timespec="seconds")


def stay(prices, query=None):
    q = query or booking.StayQuery("f1", DAY, 2)
    return booking.offers("stay", q, CFG, {"gtravel": lambda city: prices, "tripcom": lambda city: prices})


def test_stay_offers_come_one_per_source_from_the_published_prices(monkeypatch):
    monkeypatch.setenv("BOOKING_T_TEST", "77")
    fresh = hours_ago(3)
    p = {("f1", "2026-11-12", 2): item("gtravel", 2000000, 1000000, fresh, "https://g/entity",
                                         {"tripcom": {"price_total_vnd": 1800000, "price_night_vnd": 900000,
                                                      "observed_at": fresh, "url": "https://vn.trip.com/hotels/detail/?hotelId=1"}})}
    got = {o.provider: o for o in stay(p)}
    assert set(got) == {"gtravel", "tripcom"}
    g, t = got["gtravel"], got["tripcom"]
    assert (g.price_vnd, g.price_unit, g.price_night_vnd, g.stay_dates) == (2000000, "stay_total", 1000000, ("2026-11-12", "2026-11-14"))
    assert g.available is True and g.observed_at == fresh and g.source == "gtravel"
    assert t.price_vnd == 1800000 and t.available is None  # cross_check does not carry availability
    assert t.url == "https://vn.trip.com/hotels/detail/?hotelId=1&Allianceid=77"  # affiliate added by config + .env
    assert g.url == "https://g/entity"


def test_stay_without_a_published_price_has_no_offer_and_a_stale_price_is_not_stated():
    assert stay({}) == []
    old = {("f1", "2026-11-12", 2): item("tripcom", 900000, 450000, hours_ago(100), "https://t/x")}
    (o,) = stay(old)
    assert o.provider == "tripcom" and o.url == "https://t/x"
    assert (o.price_vnd, o.price_night_vnd, o.observed_at, o.available) == (None, None, None, None)
