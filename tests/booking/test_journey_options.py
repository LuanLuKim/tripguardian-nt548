"""journey.options: which ways home -> lodging are feasible, decided by code. OSRM and offers are injected."""

from datetime import date

import pytest

import booking
import journey
from live import Unavailable

DAY = date(2026, 11, 12)
SGN_HOME = (10.78, 106.70)
HANOI_HOME = (21.03, 105.85)
LODGING = (11.95, 108.44)


def fake_route(fail=()):
    def route(points, mode, cfg):
        if mode in fail:
            raise Unavailable("osrm down")
        (a, b) = points[0], points[-1]
        return {"coords": [list(a), list(b)], "minutes": 300 if mode == "car" else 330, "source": "osrm",
                "fetched_at": "2026-10-28T10:00:00+00:00"}
    return route


def trip(price=None):
    return booking.Offer(provider="vexere", kind="coach", mode="deeplink", url="https://v/x", carrier="A",
                         depart_at="2026-11-12T06:00", arrive_at="2026-11-12T13:00", price_vnd=price,
                         price_unit="ticket" if price else None)


def link_only(kind):
    return booking.Offer(provider="google_flights" if kind == "flight" else "vexere", kind=kind, mode="deeplink", url="https://l/x")


def offers_of(coach=(), flight=None):
    def f(kind, q, cfg=None, sources=None):
        return list(coach) if kind == "coach" else [flight or link_only("flight")]
    return f


def by_mode(j):
    return {o.mode: o for o in j.options}


def test_from_saigon_all_four_ways_are_shown_with_what_is_known():
    j = journey.options(SGN_HOME, DAY, LODGING, route=fake_route(), offers=offers_of([trip(300000), trip(350000)]))
    o = by_mode(j)
    assert list(o) == ["car", "motorbike", "bus", "plane"] and not j.dest_is_centre
    assert o["car"].feasible is True and o["car"].minutes == 300 and o["car"].legs[0].coords
    assert 200 < o["car"].legs[0].distance_km < 260  # the fake route is a straight line
    assert o["motorbike"].feasible is True and o["motorbike"].minutes == 330
    assert o["bus"].feasible is True and o["bus"].minutes == 300 + 420 + 300  # Sài Gòn and Đà Lạt stations are Maps-located (door to door)
    assert (o["bus"].price_min_vnd, o["bus"].price_max_vnd) == (300000, 350000)
    p = o["plane"]
    assert p.feasible is None and p.reason == "flights_unchecked"  # a link cannot promise a flight
    assert [l.kind for l in p.legs] == ["transfer", "flight", "transfer"]
    assert p.legs[1].minutes is None and p.minutes is None and p.price_min_vnd is None
    assert p.legs[0].to_label == "SGN" and p.legs[2].from_label == "DLI"


def test_far_start_drops_the_motorbike_and_a_near_airport_keeps_the_plane():
    j = journey.options(HANOI_HOME, DAY, LODGING, route=fake_route(), offers=offers_of())
    o = by_mode(j)
    assert o["motorbike"].feasible is False and o["motorbike"].reason == "too_far"
    assert o["car"].feasible is True
    assert o["bus"].feasible is False and o["bus"].reason in ("no_coach_region", "no_trips")
    assert o["plane"].legs[0].to_label == "HAN"


def test_a_start_close_to_the_city_does_not_fly():
    j = journey.options((11.77, 108.0), DAY, LODGING, route=fake_route(), offers=offers_of([trip()]))
    p = by_mode(j)["plane"]
    assert p.feasible is False and p.reason == "too_close"


def test_no_lodging_yet_draws_to_the_city_centre():
    j = journey.options(SGN_HOME, DAY, None, route=fake_route(), offers=offers_of())
    assert j.dest_is_centre and j.dest == (11.9404, 108.4583)


def test_no_date_keeps_the_road_options_and_marks_the_dated_ones_unknown():
    j = journey.options(SGN_HOME, None, LODGING, route=fake_route(), offers=offers_of())
    o = by_mode(j)
    assert o["car"].feasible is True
    assert o["bus"].feasible is None and o["bus"].reason == "needs_date"
    assert o["plane"].feasible is None and o["plane"].reason == "needs_date" and o["plane"].offers == ()


def test_osrm_down_is_unknown_not_infeasible():
    j = journey.options(SGN_HOME, DAY, LODGING, route=fake_route(fail=("car", "motorbike")), offers=offers_of())
    o = by_mode(j)
    assert o["car"].feasible is None and o["car"].reason == "no_route" and o["car"].minutes is None
    assert o["motorbike"].feasible is None


def test_a_coach_page_that_could_not_be_read_is_unknown_and_no_trip_is_false():
    j = journey.options(SGN_HOME, DAY, LODGING, route=fake_route(), offers=offers_of([link_only("coach")]))
    assert by_mode(j)["bus"].feasible is None and by_mode(j)["bus"].reason == "unchecked"
    j = journey.options(SGN_HOME, DAY, LODGING, route=fake_route(), offers=offers_of([]))
    assert by_mode(j)["bus"].feasible is False and by_mode(j)["bus"].reason == "no_trips"


def test_outbound_swaps_the_ends():
    j = journey.options(SGN_HOME, DAY, LODGING, way="outbound", route=fake_route(), offers=offers_of())
    car = by_mode(j)["car"]
    assert car.legs[0].coords[0] == list(LODGING) and car.legs[0].coords[-1] == list(SGN_HOME)
    p = by_mode(j)["plane"]
    assert p.legs[0].from_label == "lodging" and p.legs[0].to_label == "DLI" and p.legs[2].from_label == "SGN" and p.legs[2].to_label == "origin"


def test_as_dict_is_json_ready():
    import json
    j = journey.options(SGN_HOME, DAY, LODGING, route=fake_route(), offers=offers_of([trip(1)]))
    json.dumps(j.as_dict())


def test_a_drive_leg_names_the_pass_the_road_runs_through():
    def route(points, mode, cfg):  # a road that passes the Prenn point
        return {"coords": [list(points[0]), [11.8332, 108.4504], list(points[-1])], "minutes": 230, "source": "osrm",
                "fetched_at": "2026-10-29T10:00:00+00:00"}
    j = journey.options(SGN_HOME, DAY, None, route=route, offers=offers_of())
    car = next(o for o in j.options if o.mode == "car")
    assert car.legs[0].via == "Đèo Prenn"
    assert next(o for o in j.options if o.mode == "plane").legs[0].via is None  # transfers are not mountain roads


def test_a_road_far_from_every_pass_is_not_labelled():
    j = journey.options(SGN_HOME, DAY, None, route=fake_route(), offers=offers_of())
    assert next(o for o in j.options if o.mode == "car").legs[0].via is None


def crawled(depart, arrive, price, stops=0, observed="2026-10-29T06:00:00+00:00"):
    return booking.Offer(provider="google_flights", kind="flight", mode="deeplink", url="https://l/x", carrier="Vietjet",
                         flight_no="VJ 360", stops=stops, depart_at=depart, arrive_at=arrive, price_vnd=price,
                         price_unit="ticket", observed_at=observed)


def test_a_crawled_flight_that_day_makes_the_plane_feasible_with_its_time_and_price():
    flights = [crawled("2026-11-12T06:30", "2026-11-12T07:25", 1210781), crawled("2026-11-12T09:55", "2026-11-12T10:50", 2443181),
               crawled("2026-11-12T21:40", "2026-11-13T17:15", 2607214, stops=1)]
    j = journey.options(SGN_HOME, DAY, LODGING, route=fake_route(), offers=lambda kind, q, cfg=None, sources=None:
                        flights if kind == "flight" else [])
    p = by_mode(j)["plane"]
    assert p.feasible is True and p.reason == "flights"
    assert p.legs[1].minutes == 55 and p.legs[1].source == "gflights"  # the shortest direct flight, not the 1-stop one
    assert p.minutes == 300 + 55 + 300 + 90 + 20  # transfers (fake route) + air time + check-in before and bags after
    assert (p.price_min_vnd, p.price_max_vnd) == (1210781, 2607214) and len(p.offers) == 3


def test_a_link_without_flight_times_stays_unknown_even_with_other_fields():
    j = journey.options(SGN_HOME, DAY, LODGING, route=fake_route(), offers=offers_of())
    p = by_mode(j)["plane"]
    assert p.feasible is None and p.reason == "flights_unchecked" and p.legs[1].minutes is None


def test_with_only_connections_the_plane_is_feasible_and_timed_by_the_shortest_connection():
    flights = [crawled("2026-11-12T21:40", "2026-11-13T17:15", 2607214, stops=1),
               crawled("2026-11-12T13:15", "2026-11-12T18:20", 3490231, stops=1)]
    j = journey.options(HANOI_HOME, DAY, LODGING, route=fake_route(), offers=lambda kind, q, cfg=None, sources=None:
                        flights if kind == "flight" else [])
    p = by_mode(j)["plane"]
    assert p.feasible is True and p.legs[1].minutes == 305


def test_the_nearest_airport_without_a_direct_flight_gives_way_to_a_quicker_one():
    hue, dad = (16.46, 107.59), (16.05, 108.20)

    def offers(kind, q, cfg=None, sources=None):
        if kind != "flight":
            return []
        if q.src == "DAD":
            return [crawled("2026-11-12T06:00", "2026-11-12T07:05", 1000000)]
        return [crawled("2026-11-12T13:20", "2026-11-12T18:20", 4000000, stops=1)]
    j = journey.options(hue, DAY, LODGING, route=fake_route(), offers=offers)
    p = by_mode(j)["plane"]
    assert p.feasible is True and p.legs[0].to_label == "DAD" and p.legs[1].minutes == 65


def test_with_no_flight_data_for_either_airport_the_nearest_one_is_shown_as_unknown():
    j = journey.options((16.46, 107.59), DAY, LODGING, route=fake_route(), offers=offers_of())
    p = by_mode(j)["plane"]
    assert p.feasible is None and p.legs[0].to_label == "HUI"


def test_coach_with_located_stations_gets_legs_and_door_to_door_minutes(monkeypatch):
    import dataclasses

    import live
    cfg = dataclasses.replace(live.load_settings(), vexere_city_station={"name": "Bến xe Đà Lạt", "lat": 11.9269, "lng": 108.4455})
    monkeypatch.setattr(live, "load_settings", lambda: cfg)
    j = journey.options(HANOI_HOME, DAY, LODGING, route=fake_route(), offers=offers_of([trip(500000)]))
    bus = by_mode(j)["bus"]
    assert [l.kind for l in bus.legs] == ["transfer", "coach", "transfer"]
    assert bus.legs[0].to_label == "Bến xe Nước Ngầm" and bus.legs[2].from_label == "Bến xe Đà Lạt"
    assert bus.legs[1].minutes == 420  # 06:00 -> 13:00 as the offer states
    assert bus.minutes == 300 + 420 + 300  # fake_route gives 300 min per car leg
    back = by_mode(journey.options(HANOI_HOME, DAY, LODGING, way="outbound", route=fake_route(), offers=offers_of([trip()])))["bus"]
    assert back.legs[0].from_label == "lodging" and back.legs[2].to_label == "origin"


def test_saigon_origin_gets_door_to_door_minutes_from_its_maps_station(monkeypatch):
    import live
    cfg = live.load_settings()
    assert cfg.vexere_city_station  # Maps-located, config/live.yaml
    j = journey.options(SGN_HOME, DAY, LODGING, route=fake_route(), offers=offers_of([trip(300000)]))
    bus = by_mode(j)["bus"]
    assert [l.kind for l in bus.legs] == ["transfer", "coach", "transfer"]
    assert bus.legs[0].to_label == "Bến xe Miền Đông Mới" and bus.minutes is not None


def test_coach_without_a_located_station_keeps_no_door_to_door_claim():
    ha_tinh = (18.3428, 105.9057)  # Hà Tĩnh region: no station in config/live.yaml
    j = journey.options(ha_tinh, DAY, LODGING, route=fake_route(), offers=offers_of([trip(300000)]))
    assert by_mode(j)["bus"].legs == () and by_mode(j)["bus"].minutes is None
