"""Trip.com: list-page parser on a saved page (2026-10-28, Đà Lạt, 7-9 Nov 2026), URL, match, observation, run."""

import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from corpus.crawl import tripcom
from corpus.crawl.common import lodging

FIX = Path(__file__).parent / "fixtures"


def page() -> str:
    return gzip.open(FIX / "list_2n.html.gz", "rt", encoding="utf-8").read()


def test_parse_list_reads_name_point_dates_and_total():
    hotels = tripcom.parse_list(page())
    assert len(hotels) == 10
    h = hotels[0]
    assert (h.id, h.name, h.lat, h.lng) == ("134612818", "Nelly Hotel Dalat", 11.947949, 108.439959)
    assert (h.checkin, h.nights, h.price_total_vnd, h.price_night_vnd) == ("2026-11-07", 2, 991412, 495706)
    assert h.url.endswith("hotelId=134612818&checkIn=2026-11-07&checkOut=2026-11-09&adult=2&curr=VND")


def test_parse_list_of_a_page_without_data_is_empty():
    assert tripcom.parse_list("<html></html>") == []


def test_one_night_total_wording():
    # a 1-night card says "Tổng (bao gồm thuế & phí): 824.742₫" instead of "Tổng giá: ..."
    from corpus.crawl.tripcom.parser import _TOTAL
    assert _TOTAL.search("Tổng (bao gồm thuế & phí): 824.742₫").group(1) == "824.742"
    assert _TOTAL.search("Tổng giá: 991.412₫\n1 phòng × 2 đêm bao gồm thuế & phí").group(1) == "991.412"


def test_list_url_carries_the_dates():
    url = tripcom.list_url(5204, lodging.Stay(date(2026, 11, 7), 2, 2))
    assert "city=5204&checkin=2026-11-07&checkout=2026-11-09&adult=2" in url


@pytest.fixture
def root(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    corpus = {"items": [
        {"fid": "a:1", "name": "Khách sạn Bee Hill", "lat": 11.937334, "lng": 108.4536, "score": 4},
        {"fid": "a:2", "name": "Nature Hotel - Lê Đại Hành", "lat": 11.93857, "lng": 108.43874, "score": 3}]}
    (tmp_path / "gmaps" / "list").mkdir(parents=True)
    (tmp_path / "gmaps" / "list" / "dalat_stay.json").write_text(json.dumps(corpus), encoding="utf-8")
    return tmp_path


def test_run_matches_to_the_corpus_and_keeps_the_rest_apart(root, monkeypatch):
    html = page()
    monkeypatch.setattr(lodging, "stay_dates", lambda cfg, today=None: [lodging.Stay(date(2026, 11, 7), 2, 2)])
    stats = tripcom.run("dalat", get=lambda url, t: html, sleep=lambda s: None)
    calls = lodging.settings("dalat")["tripcom"]["calls_per_date"]
    assert (stats["calls"], stats["hotels"], stats["matched"], stats["priced"], stats["unmatched"]) == (calls, 10, 2, 2, 8)
    got = lodging.latest("tripcom", "dalat")
    assert got[("a:1", "2026-11-07", 2)]["price_total_vnd"] == 535200
    assert got[("a:2", "2026-11-07", 2)]["source"] == "tripcom"
    unmatched = (root / "tripcom" / "dalat" / "unmatched.jsonl").read_text().splitlines()
    assert len(unmatched) == 8 and "fid" not in json.loads(unmatched[0])


def test_other_dates_than_asked_are_not_a_price(root):
    h = tripcom.parse_list(page())[0]
    obs = tripcom.observation(h, lodging.Match("a:1", 1.0, 5.0), lodging.Stay(date(2026, 11, 14), 2, 2))
    assert obs["price_night_vnd"] is None and obs["available"] is None
    lodging.check(obs)


def test_a_failed_call_is_an_error_not_an_observation(root, monkeypatch):
    monkeypatch.setattr(lodging, "stay_dates", lambda cfg, today=None: [lodging.Stay(date(2026, 11, 7), 2, 2)])
    stats = tripcom.run("dalat", get=lambda url, t: "<html></html>", sleep=lambda s: None)
    assert stats["errors"] == lodging.settings("dalat")["tripcom"]["calls_per_date"] and stats["matched"] == 0
    assert not (root / "tripcom" / "dalat" / "observations.jsonl").exists()
