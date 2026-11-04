"""Shared lodging-price pieces (corpus.crawl.common.lodging): stay dates, name fold + distance match, observation store,
and the published latest price per (fid, stay date) (corpus.serving.stay_prices)."""

import json
from datetime import date, datetime, timedelta

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


def test_names_alike_only_in_the_kind_of_lodging_never_match():
    near = [{"fid": "g:1", "name": "G Family Homestay", "lat": 11.94, "lng": 108.44}]
    assert lodging.match("Bông Bi Homestay", 11.9401, 108.4401, near, "Đà Lạt", MATCH).fid is None


def test_ambiguous_names_stay_unmatched():
    twins = [{"fid": "b:1", "name": "Hoa Hồng Villa 1", "lat": 11.94, "lng": 108.44},
             {"fid": "b:2", "name": "Hoa Hồng Villa 2", "lat": 11.9401, "lng": 108.4401}]
    assert lodging.match("Hoa Hồng Villa", 11.94, 108.44, twins, "Đà Lạt", MATCH).fid is None


def test_the_exact_name_beats_a_longer_name_that_contains_it():
    near = [{"fid": "t:3", "name": "Tulip Hotel 3", "lat": 11.9422, "lng": 108.4342},
            {"fid": "t:0", "name": "Tulip Hotel - Đà Lạt", "lat": 11.9423, "lng": 108.4343}]
    assert lodging.match("Khách sạn Tulip 3", 11.9422, 108.4342, near, "Đà Lạt", MATCH).fid == "t:3"


def test_branch_numbers_must_agree():
    five = [{"fid": "n:5", "name": "Thanh Thanh 5 Hotel", "lat": 11.9403, "lng": 108.4354}]
    assert lodging.match("Thanh Thanh 2 Hotel", 11.9403, 108.4354, five, "Đà Lạt", MATCH).fid is None


def test_same_letters_run_together_match():
    one = [{"fid": "d:1", "name": "Duparc Hotel Dalat", "lat": 11.9367, "lng": 108.4391}]
    assert lodging.match("Du Parc Hotel Dalat", 11.9367, 108.4390, one, "Đà Lạt", MATCH).fid == "d:1"


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
    out = stay_prices.publish("dalat", today=date(2026, 10, 28))
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


NOW = "2026-10-28T11:00:00+00:00"
D1, D2, D3 = (lodging.Stay(date(2026, 11, d), 1, 2) for d in (7, 14, 21))


def _row(fid, stay, hours_ago, price=800000, **kw):
    at = datetime.fromisoformat(NOW) - timedelta(hours=hours_ago)
    return (fid, stay.checkin.isoformat(), stay.nights), _obs(
        fid=fid, stay_date=stay.checkin.isoformat(), nights=stay.nights, observed_at=at.isoformat(),
        price_night_vnd=price, price_total_vnd=price * stay.nights if price else None, available=True if price else None,
        **kw)


def _queue(fids, rows, stays=(D1, D2, D3)):
    return lodging.queue(fids, list(stays), dict(rows), fresh_h=12, no_offer_h=48, dead_h=336, now=NOW)


def test_queue_gives_every_lodging_one_look_before_any_gets_two():
    got = _queue(["a:1", "a:2", "a:3"], [_row("a:1", D1, 1)])
    # a:2 and a:3 never looked at: probe date only, best first; a:1 (priced) fills its other dates after them
    assert got[:2] == [("a:2", D1), ("a:3", D1)]
    assert ("a:1", D2) in got[2:] and ("a:1", D1) not in got  # a:1's probe is fresh (1 h < 12)


def test_queue_asks_a_second_date_before_writing_a_lodging_off():
    one = _queue(["a:1"], [_row("a:1", D1, 1, price=None)])
    assert one == [("a:1", D2), ("a:1", D3)]  # one "no offer" is not "no listing"
    two = _queue(["a:1"], [_row("a:1", D1, 1, price=None), _row("a:1", D2, 1, price=None)])
    assert two == []  # 2 dates without an offer: no OTA listing, asked again only after dead_h (14 days)
    later = lodging.queue(["a:1"], [D1, D2, D3], dict([_row("a:1", D1, 400, price=None), _row("a:1", D2, 400, price=None)]),
                          12, 48, 336, NOW)
    assert later == [("a:1", D1)]


def test_queue_refreshes_priced_pairs_after_fresh_h_oldest_first():
    rows = [_row("a:1", D1, 13), _row("a:1", D2, 30), _row("a:1", D3, 2)]
    assert _queue(["a:1"], rows) == [("a:1", D2), ("a:1", D1)]


def test_a_longer_minimum_stay_is_priced_for_that_stay():
    rows = [_row("a:1", D1, 1, price=None, min_nights=2)]
    got = _queue(["a:1"], rows)
    assert ("a:1", lodging.Stay(date(2026, 11, 7), 2, 2)) in got  # the stay the hotel does sell


def test_a_page_that_never_drew_is_asked_again_in_hours_not_days():
    rows = [_row("a:1", D1, 3, price=None, note="not_drawn")]
    assert _queue(["a:1"], rows) == []  # 3 h < 6 h
    rows = [_row("a:1", D1, 7, price=None, note="not_drawn")]
    assert _queue(["a:1"], rows) == [("a:1", D1)]  # back to the probe date, not counted as a "no offer"


def test_queue_skips_stays_that_have_started():
    past = lodging.Stay(date(2026, 10, 28), 1, 2)
    assert _queue(["a:1"], [], stays=(past, D1)) == []  # the probe date is gone: nothing to ask for


def test_holiday_and_ahead_rules():
    runs = [(date(2026, 12, 31), 1), (date(2027, 2, 5), 5), (date(2027, 9, 2), 1)]
    cfg = {"adults": 2, "stays": [{"ahead_days": 30, "weekday": "sat", "nights": 1},
                                  {"holidays": True, "within_days": 120, "count": 2, "nights": 2}]}
    got = lodging.stay_dates(cfg, date(2026, 10, 28), holidays=runs)
    assert got == [lodging.Stay(date(2026, 11, 28), 1, 2), lodging.Stay(date(2026, 12, 30), 2, 2),
                   lodging.Stay(date(2027, 2, 4), 2, 2)]  # the evening before each run; the third run is out of range


def test_holiday_runs_group_consecutive_days(tmp_path):
    f = tmp_path / "h.yaml"
    f.write_text('holidays:\n  "2027-02-05": a\n  "2027-02-06": b\n  "2027-04-30": c\n  "2027-05-01": d\n  "2027-09-02": e\n')
    assert lodging.holiday_runs(f) == [(date(2027, 2, 5), 2), (date(2027, 4, 30), 2), (date(2027, 9, 2), 1)]


def test_publish_drops_stays_that_have_started(data_root):
    lodging.append_observation("gtravel", "dalat", _obs(stay_date="2026-10-28"))
    lodging.append_observation("gtravel", "dalat", _obs(fid="a:2", stay_date="2026-11-07"))
    out = stay_prices.publish("dalat", today=date(2026, 10, 29))
    assert out["stats"] == {"priced": 1, "fids": 1}
