"""Google Flights: URL, result-page parser on pages saved 2026-10-29, the observation row, the due queue, the serving file."""

import asyncio
import gzip
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from corpus.crawl import gflights
from corpus.crawl.gflights import parser

FIX = Path(__file__).parent / "fixtures"
DAY = date(2026, 11, 5)


def page(name: str) -> str:
    return gzip.decompress((FIX / f"{name}.html.gz").read_bytes()).decode("utf-8")


def test_search_url_names_the_route_and_the_day():
    url = gflights.url("SGN", "DLI", DAY)
    assert url.startswith("https://www.google.com/travel/flights?q=") and "SGN" in url and "2026-11-05" in url and "curr=VND" in url


def test_direct_flights_of_a_saved_page():
    flights = parser.parse_list(page("list_sgn_dli_2026-11-05"), DAY)
    assert len(flights) >= 6 and [f.depart_at for f in flights] == sorted(f.depart_at for f in flights)
    first = flights[0]
    assert (first.carrier, first.depart_at, first.arrive_at, first.price_vnd, first.stops) == (
        "Vietnam Airlines", "2026-11-05T06:10", "2026-11-05T07:05", 1452181, 0)
    assert "Tân Sơn Nhất" in first.from_point and "Liên Khương" in first.to_point


def test_a_connecting_flight_keeps_its_stops_and_next_day_arrival():
    flights = parser.parse_list(page("list_vii_dli_2026-11-05"), DAY)
    night = next(f for f in flights if f.depart_at == "2026-11-05T21:40" and f.price_vnd == 2607214)
    assert (night.carrier, night.stops, night.arrive_at) == ("Vietjet", 1, "2026-11-06T17:15")


def test_flights_of_another_day_are_not_returned():
    assert parser.parse_list(page("list_sgn_dli_2026-11-05"), date(2026, 11, 20)) == []


def test_unreadable_label_is_skipped_not_guessed():
    assert parser.parse_list('<div aria-label="Từ 100 đồng Việt Nam trở lên. Rời đâu đó"></div>', DAY) == []


def test_flight_number_of_an_expanded_row():
    assert parser.flight_numbers((FIX / "detail_vj360.txt").read_text(encoding="utf-8")) == ["VJ 360"]


def test_the_page_prints_a_non_breaking_space_in_the_number():  # seen on the live page 2026-10-29
    assert parser.flight_numbers("VietjetHạng phổ thôngAirbus A321VJ\xa0360\nChọn chuyến bay") == ["VJ 360"]


def test_two_segments_give_two_numbers_in_order():  # synthetic: the same line shape Google prints per segment
    text = ("06:30Cảng A (VII)\nThời gian chuyến đi: 1 giờ\n08:00Cảng B (SGN)\nVietjetHạng phổ thôngAirbus A321VJ 360\n"
            "Chỗ duỗi chân\n10:00Cảng B (SGN)\nVietnam AirlinesHạng phổ thôngAirbus A320VN 1342\n")
    assert parser.flight_numbers(text) == ["VJ 360", "VN 1342"]


def test_no_number_shown_is_unknown():
    assert parser.flight_numbers("VietjetHạng phổ thôngAirbus A321\nChọn chuyến bay") == []


CFG = {"dest": "DLI", "routes": [{"src": "SGN", "days": 2}, {"src": "VII", "days": 1}], "fresh_h": 12, "max_per_run": 60,
       "tabs": 2, "pause_s": [0, 0]}
TODAY = date(2026, 11, 1)


def flight(depart="2026-11-02T06:30", price=1210781, numbers=("VJ 360",)):
    f = parser.Flight("Vietjet", depart, "2026-11-02T07:25", "Cảng hàng không quốc tế Tân Sơn Nhất",
                      "Cảng Hàng Không Quốc Tế Liên Khương", price, 0)
    return {"flight": f, "numbers": list(numbers)}


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


def test_every_route_is_searched_both_ways_nearest_day_first():
    got = gflights.crawl.searches(CFG, TODAY)
    assert [(s, d, day.isoformat()) for s, d, day in got] == [
        ("DLI", "SGN", "2026-11-02"), ("DLI", "VII", "2026-11-02"), ("SGN", "DLI", "2026-11-02"), ("VII", "DLI", "2026-11-02"),
        ("DLI", "SGN", "2026-11-03"), ("SGN", "DLI", "2026-11-03")]


def test_observation_carries_the_flights_and_unknown_stays_none():
    row = gflights.observation("SGN", "DLI", date(2026, 11, 2), "u", [flight(), flight("2026-11-02T09:00", None, ())])
    assert (row["src"], row["dst"], row["day"], row["source"]) == ("SGN", "DLI", "2026-11-02", "gflights")
    assert row["offers"][0]["flight_no"] == "VJ 360" and row["offers"][0]["price_vnd"] == 1210781
    assert row["offers"][1]["flight_no"] is None and row["offers"][1]["price_vnd"] is None
    gflights.crawl.check(row)


def test_a_search_without_flights_is_not_an_observation():
    row = gflights.observation("SGN", "DLI", date(2026, 11, 2), "u", [])
    with pytest.raises(ValueError):
        gflights.crawl.check(row)


def test_a_bad_price_is_refused():
    row = gflights.observation("SGN", "DLI", date(2026, 11, 2), "u", [flight(price=0)])
    row["offers"][0]["price_vnd"] = 0
    with pytest.raises(ValueError):
        gflights.crawl.check(row)


def test_due_queue_never_seen_first_then_oldest_and_fresh_ones_wait(data):
    now = datetime.now(UTC)
    old, fresh = (now - timedelta(hours=30)).isoformat(timespec="seconds"), (now - timedelta(hours=1)).isoformat(timespec="seconds")
    for src, dst, observed in (("SGN", "DLI", fresh), ("DLI", "SGN", old)):
        row = gflights.observation(src, dst, date(2026, 11, 2), "u", [flight()])
        gflights.crawl.append_observation("dalat", {**row, "observed_at": observed})
    todo = gflights.todo_searches("dalat", CFG, today=TODAY)
    keys = [(s, d, day.isoformat()) for s, d, day in todo]
    assert ("SGN", "DLI", "2026-11-02") not in keys  # seen an hour ago
    assert keys[-1] == ("DLI", "SGN", "2026-11-02") and len(keys) == 5  # the one seen 30 h ago comes after every unseen one
    assert len(gflights.todo_searches("dalat", CFG, limit=2, today=TODAY)) == 2


def test_run_records_a_read_page_and_skips_one_that_showed_nothing(data, monkeypatch):
    monkeypatch.setattr(gflights.crawl, "settings", lambda city: CFG)

    async def reader(ctx, link, day, wait):
        if "VII" in link:
            raise gflights.crawl.NotDrawn("no flight row on the page")
        return [flight()]

    class Ctx:
        async def route(self, *a): pass
        async def close(self): pass

    class Sessions:
        def __init__(self, headed): pass
        async def __aenter__(self):
            async def new(): return Ctx()
            return new
        async def __aexit__(self, *a): pass

    todo = [("SGN", "DLI", date(2026, 11, 2)), ("VII", "DLI", date(2026, 11, 2))]
    stats = asyncio.run(gflights.run("dalat", sessions=Sessions, todo=todo, reader=reader))
    assert (stats["with_flights"], stats["not_drawn"], stats["errors"]) == (1, 1, 0)
    assert set(gflights.latest("dalat")) == {("SGN", "DLI", "2026-11-02")}


def test_config_routes_are_airports_we_fly_from():
    import yaml
    root = Path(__file__).resolve().parents[3] / "config"
    air = yaml.safe_load((root / "airports.yaml").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((root / "queries.yaml").read_text(encoding="utf-8"))["flight_price"]
    assert cfg["dest"] == air["dest"]["iata"]
    assert {r["src"] for r in cfg["routes"]} <= {a["iata"] for a in air["airports"]}


def test_serving_publishes_the_newest_search_and_max_age_drops_stale_ones(data):
    from corpus.serving import flight_offers
    old = (datetime.now(UTC) - timedelta(hours=40)).isoformat(timespec="seconds")
    first = gflights.observation("SGN", "DLI", date(2026, 11, 2), "u", [flight(price=2000000)])
    gflights.crawl.append_observation("dalat", {**first, "observed_at": old})
    gflights.crawl.append_observation("dalat", gflights.observation("SGN", "DLI", date(2026, 11, 2), "u", [flight(price=1210781)]))
    gflights.crawl.append_observation("dalat", {**gflights.observation("DLI", "SGN", date(2026, 11, 2), "u", [flight()]), "observed_at": old})
    assert flight_offers.publish("dalat")["stats"] == {"searches": 2, "offers": 2}
    got = flight_offers.load("dalat")
    assert got[("SGN", "DLI", "2026-11-02")]["offers"][0]["price_vnd"] == 1210781  # the newer search wins
    fresh = flight_offers.load("dalat", max_age_h=24)
    assert set(fresh) == {("SGN", "DLI", "2026-11-02")}  # the 40 h old search is dropped, not reported as "no flight"
    assert flight_offers.load("nowhere") == {}
