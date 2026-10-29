"""Shared lodging-price pieces (corpus.crawl.common.lodging): stay dates, name fold + distance match, observation store,
and the published latest price per (fid, stay date) (corpus.serving.stay_prices)."""

import json
from datetime import date

import pytest

from corpus.crawl.common import lodging
from corpus.serving import stay_prices


@pytest.fixture(autouse=True)
def data_root(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


CFG = {"adults": 2, "stays": [{"weekday": "sat", "count": 2, "nights": 1}, {"weekday": "tue", "count": 1, "nights": 2}]}


def test_stay_dates_from_config_rules():
    # 2026-10-28 is a Wednesday
    got = lodging.stay_dates(CFG, date(2026, 10, 28))
    assert got == [lodging.Stay(date(2026, 10, 31), 1, 2), lodging.Stay(date(2026, 11, 7), 1, 2),
                   lodging.Stay(date(2026, 11, 3), 2, 2)]
    assert got[2].checkout == date(2026, 11, 5)


def test_stay_dates_never_today_and_no_duplicates():
    # on a Saturday the first weekend is the next one: tonight's price is gone by the time anyone plans
    got = lodging.stay_dates({"adults": 2, "stays": [{"weekday": "sat", "count": 1, "nights": 1},
                                                     {"weekday": "sat", "count": 1, "nights": 1}]}, date(2026, 10, 31))
    assert got == [lodging.Stay(date(2026, 11, 7), 1, 2)]


def test_fold_drops_accents_case_punctuation_and_generic_words():
    assert lodging.fold("Khách sạn Bee Hill - Đà Lạt", "Đà Lạt") == "bee hill"
    assert lodging.fold("Nature Hotel- Nam Kỳ Khởi Nghĩa", "Đà Lạt") == "nature nam ky khoi nghia"
    assert lodging.fold("Dalat Center Residence", "Đà Lạt") == "center residence"


STAYS = [
    {"fid": "a:1", "name": "Khách sạn Bee Hill", "lat": 11.9400, "lng": 108.4400},
    {"fid": "a:2", "name": "Nature Hotel - Lê Đại Hành", "lat": 11.9450, "lng": 108.4380},
    {"fid": "a:3", "name": "Nature Hotel - Nguyễn Thị Nghĩa", "lat": 11.9452, "lng": 108.4383},
    {"fid": "a:4", "name": "Colline Dalat", "lat": 11.9420, "lng": 108.4370},
]
MATCH = {"max_m": 400, "min_score": 0.6, "far_m": 1500, "far_score": 0.9, "margin": 0.1}


def test_match_by_name_and_distance():
    m = lodging.match("Bee Hill Hotel", 11.9405, 108.4402, STAYS, "Đà Lạt", MATCH)
    assert m.fid == "a:1" and m.score == 1.0 and m.meters < 100


def test_match_keeps_branches_apart():
    m = lodging.match("Nature Hotel - Nguyễn Thị Nghĩa", 11.9451, 108.4382, STAYS, "Đà Lạt", MATCH)
    assert m.fid == "a:3"


def test_same_name_far_away_needs_a_near_exact_name():
    # 1 km off: a near-exact name still matches (OTA pins drift), a loose one does not
    assert lodging.match("Colline Dalat", 11.9510, 108.4370, STAYS, "Đà Lạt", MATCH).fid == "a:4"
    assert lodging.match("Colline Garden Villa", 11.9510, 108.4370, STAYS, "Đà Lạt", MATCH).fid is None


def test_no_match_without_point_or_name():
    assert lodging.match("Some New Hotel", 11.9400, 108.4400, STAYS, "Đà Lạt", MATCH).fid is None
    assert lodging.match("Khách sạn Bee Hill", None, None, STAYS, "Đà Lạt", MATCH).fid is None


def test_names_sharing_no_word_never_match():
    # "almira home" and "mia house" are 70% alike letter by letter and 40 m apart, and are two lodgings
    near = [{"fid": "c:1", "name": "Mia house", "lat": 11.94, "lng": 108.44}]
    assert lodging.match("Almira Home Da Lat", 11.9401, 108.4401, near, "Đà Lạt", MATCH).fid is None


def test_ambiguous_names_stay_unmatched():
    twins = [{"fid": "b:1", "name": "Hoa Hồng Hotel", "lat": 11.94, "lng": 108.44},
             {"fid": "b:2", "name": "Hoa Hồng Hotel 2", "lat": 11.9401, "lng": 108.4401}]
    assert lodging.match("Hoa Hồng", 11.94, 108.44, twins, "Đà Lạt", MATCH).fid is None


def _obs(**kw):
    row = {"fid": "a:1", "price_total_vnd": 800000, "price_night_vnd": 800000, "currency": "VND", "available": True,
           "stay_date": "2026-11-07", "nights": 1, "adults": 2, "observed_at": "2026-10-28T10:00:00+00:00",
           "source": "gtravel", "url": "u", "matched_name": "Bee Hill", "match_score": 1.0}
    return {**row, **kw}


def test_observation_rows_are_checked_at_the_boundary(data_root):
    with pytest.raises(ValueError):
        lodging.append_observation("gtravel", "dalat", _obs(available=False))  # no offer seen = unknown, never false
    with pytest.raises(ValueError):
        lodging.append_observation("gtravel", "dalat", _obs(fid=None))
    with pytest.raises(ValueError):
        lodging.append_observation("gtravel", "dalat", _obs(price_total_vnd=None, price_night_vnd=None, available=True))
    lodging.append_observation("gtravel", "dalat", _obs(price_total_vnd=None, price_night_vnd=None, available=None))
    path = data_root / "gtravel" / "dalat" / "observations.jsonl"
    assert len(path.read_text().splitlines()) == 1


def test_unmatched_rows_live_apart(data_root):
    lodging.append_unmatched("tripcom", "dalat", {"name": "New Hotel", "lat": 11.9, "lng": 108.4, "stay_date": "2026-11-07"})
    assert (data_root / "tripcom" / "dalat" / "unmatched.jsonl").exists()
    assert not (data_root / "tripcom" / "dalat" / "observations.jsonl").exists()


def test_latest_per_fid_and_stay(data_root):
    lodging.append_observation("gtravel", "dalat", _obs(price_total_vnd=900000, price_night_vnd=900000))
    lodging.append_observation("gtravel", "dalat", _obs(observed_at="2026-10-28T11:00:00+00:00", price_total_vnd=950000,
                                                        price_night_vnd=950000))
    lodging.append_observation("gtravel", "dalat", _obs(stay_date="2026-11-14"))
    latest = lodging.latest("gtravel", "dalat")
    assert latest[("a:1", "2026-11-07", 1)]["price_total_vnd"] == 950000
    assert latest[("a:1", "2026-11-14", 1)]["price_total_vnd"] == 800000


def test_publish_prefers_main_source_and_keeps_unknown_out(data_root):
    lodging.append_observation("gtravel", "dalat", _obs())
    lodging.append_observation("tripcom", "dalat", _obs(source="tripcom", price_total_vnd=760000, price_night_vnd=760000))
    # gtravel saw no offer for this one; Trip.com's price is still evidence
    lodging.append_observation("gtravel", "dalat", _obs(fid="a:2", price_total_vnd=None, price_night_vnd=None, available=None))
    lodging.append_observation("tripcom", "dalat", _obs(fid="a:2", source="tripcom", price_total_vnd=1200000,
                                                        price_night_vnd=1200000))
    # neither source priced it: not published, unknown stays unknown
    lodging.append_observation("gtravel", "dalat", _obs(fid="a:3", price_total_vnd=None, price_night_vnd=None, available=None))
    out = stay_prices.publish("dalat")
    assert out["stats"] == {"priced": 2, "fids": 2}
    prices = stay_prices.load("dalat")
    assert prices[("a:1", "2026-11-07", 1)]["source"] == "gtravel"
    assert prices[("a:1", "2026-11-07", 1)]["price_total_vnd"] == 800000
    assert prices[("a:1", "2026-11-07", 1)]["cross_check"]["tripcom"]["price_total_vnd"] == 760000
    assert prices[("a:2", "2026-11-07", 1)]["source"] == "tripcom"
    assert ("a:3", "2026-11-07", 1) not in prices
    saved = json.loads((data_root / "serving" / "stay_prices" / "dalat.json").read_text())
    assert len(saved["items"]) == 2


def test_load_without_a_published_file_is_empty(data_root):
    assert stay_prices.load("dalat") == {}


def test_due_pairs_rotate_oldest_first():
    stays = [lodging.Stay(date(2026, 11, 7), 1, 2), lodging.Stay(date(2026, 11, 14), 1, 2)]
    seen = {("a:1", "2026-11-07", 1): ("2026-10-28T09:00:00+00:00", True),   # priced 2 h ago: due (fresh_h 1)
            ("a:1", "2026-11-14", 1): ("2026-10-28T10:30:00+00:00", True),   # priced 30 min ago: not due
            ("a:2", "2026-11-07", 1): ("2026-10-28T05:00:00+00:00", None)}   # no offer 6 h ago: not due (no_offer_h 24)
    due = lodging.due(["a:1", "a:2"], stays, seen, fresh_h=1, no_offer_h=24, now="2026-10-28T11:00:00+00:00")
    # never seen first (a:2 on the 14th), then the oldest
    assert due == [("a:2", stays[1]), ("a:1", stays[0])]
