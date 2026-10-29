"""reads: the assistant's wider read tools (spec 2026-10-29 assistant-tools §5.1, §5.3-5.7), over fixture records."""

from datetime import date, datetime

import pytest
from trip_fixtures import ALL_DAY, served

from trip.domain.state import Hard, Meta, TripState
from trip.infrastructure.catalog import Catalog
from trip.infrastructure.knowledge import Knowledge, LiveTools
from trip.infrastructure.reads import VN, Feeds, open_state, unit_price
from trip.infrastructure.settings import Assistant

CENTER = ("Chợ Đà Lạt", 11.9429, 108.4372)
NOW = datetime(2026, 10, 30, 10, 0, tzinfo=VN)  # a Friday


def _records():
    a = served("0xa:0x1", "Cà Phê Đồi Thông", {"parking": "easy", "noise": "quiet", "kids": "suitable"}, price={"min_vnd": 30000, "max_vnd": 60000},
               lat=11.940, lng=108.440, voices=90)
    b = served("0xb:0x1", "Quán Nhạc Ồn Ào", {"noise": "loud", "kids": "unsuitable"}, price={"min_vnd": 20000, "max_vnd": 40000},
               lat=11.950, lng=108.450, voices=80)
    c = served("0xc:0x1", "Tiệm Không Giá", {}, lat=11.945, lng=108.442, voices=70)
    d = served("0xd:0x1", "Đồi Chè Cầu Đất", {"entry_fee": "paid"}, group="attraction", category="Đồi chè", lat=11.86, lng=108.56,
               voices=60)
    d["operation"]["entry_fee"] = {"min_vnd": 50000, "typical_vnd": 50000, "max_vnd": 50000, "source": "reviews", "kind": "estimate"}
    d["operation"]["visit_minutes"] = {"short": 60, "typical": 120, "long": 180}
    d["details"] = {"cost": {"entry": {"adult": {"vnd": 75000, "source": "official"}}},
                    "timing": {"best_time": {"items": [{"text": "đi sáng sớm để săn mây", "status": "VERIFIED"}]},
                               "best_months": [11, 12]}, "access": ["đường lên đèo khá dốc"]}
    e = served("0xe:0x1", "Khách Sạn Đồi Chè", {}, group="stay", category="Khách sạn", lat=11.941, lng=108.441, voices=50)
    e["operation"]["price_per_night"] = {"value": 800000, "status": "VERIFIED", "as_of": "2026-10-08", "source": "gmaps_list"}
    f = served("0xf:0x1", "Homestay Không Giá", {}, group="stay", category="Homestay", lat=11.942, lng=108.443, voices=40)
    g = served("0x10:0x1", "Khách Sạn Rẻ", {}, group="stay", category="Khách sạn", lat=11.943, lng=108.444, voices=30)
    g["operation"]["price_per_night"] = {"value": 400000, "status": "VERIFIED", "as_of": "2026-10-08", "source": "gmaps_list"}
    a["operation"]["crowd_by_time"] = {"weekday": {"morning": 20}, "weekend": {"morning": 60}, "peak": {"day": "sat", "hour": 9, "pct": 100}}
    a["near_duplicate_group"] = 7
    c["near_duplicate_group"] = 7
    a["provenance"].update({"as_of": "2026-10-11", "reputation": {"score": 0.9}})
    b["provenance"].update({"reputation": {"score": 0.4}})
    c["provenance"].update({"reputation": {"score": 0.7}})
    return [a, b, c, d, e, f, g]


@pytest.fixture
def recs():
    return _records()


def make(recs, live=None, feeds=None, pulse=None):
    from unittest.mock import MagicMock

    from corpus import load_ontology
    from corpus.retrieval import RetrievalEngine
    from corpus.snapshot import Region
    engine = RetrievalEngine(_index=None, _snapshot=MagicMock(), _region=Region.from_records(recs), _ontology=load_ontology(),
                             release_id="r-test")
    catalog = Catalog.from_records([], 1, evidence={r["id"]: r for r in recs})
    return Knowledge(engine, catalog, live, CENTER, cfg=Assistant(data_places=3, near_km=3.0), trends=pulse,
                     feeds=feeds or Feeds(now=lambda: NOW))


@pytest.fixture
def k(recs):
    return make(recs)


S = TripState()


# ---------- find_places extension ----------

def test_find_price_max_leaves_out_places_without_a_price(k):
    out = k.find({"groups": ["cafe"], "price_max": 35000}, S)
    ids = [p["id"] for p in out["places"]]
    assert "0xc:0x1" not in ids and out["no_price"] == 1  # c states no price: unknown, not cheap
    assert ids == ["0xa:0x1", "0xb:0x1"] and all(p["price_from"] <= 35000 for p in out["places"])


def test_find_price_max_strictly_filters(k):
    out = k.find({"groups": ["cafe"], "price_max": 25000}, S)
    assert [p["id"] for p in out["places"]] == ["0xb:0x1"]


def test_find_sort_price_and_exclude_and_page(k):
    out = k.find({"groups": ["cafe"], "sort": "price", "exclude": ["0xb:0x1"]}, S)
    assert [p["id"] for p in out["places"]] == ["0xa:0x1", "0xc:0x1"]  # priced first, the unpriced last
    p1 = k.find({"groups": ["cafe"], "sort": "price", "page": 1}, S, limit=2)
    p2 = k.find({"groups": ["cafe"], "sort": "price", "page": 2}, S, limit=2)
    assert [p["id"] for p in p1["places"]] == ["0xb:0x1", "0xa:0x1"] and p1["more"] is True
    assert [p["id"] for p in p2["places"]] == ["0xc:0x1"] and p2["more"] is False


def test_find_near_place_sorts_by_distance_and_skips_itself(k):
    out = k.find({"groups": ["cafe"], "near_place": "0xa:0x1", "near_km": 5, "sort": "distance"}, S)
    ids = [p["id"] for p in out["places"]]
    assert "0xa:0x1" not in ids and ids[0] == "0xc:0x1"  # c is nearer to a than b
    assert out["places"][0]["km_line"] < out["places"][1]["km_line"]


def test_find_distance_orders_by_road_minutes_when_live_gives_them(recs):
    live = LiveTools(matrix=lambda pts: {"minutes": [[0, 30, 5]], "source": "osrm", "fetched_at": "t"})  # c is slower by road
    kk = make(recs, live=live)
    out = kk.find({"groups": ["cafe"], "near_place": "0xa:0x1", "near_km": 5, "sort": "distance"}, S)
    assert out["places"][0]["min"] in (5, 30) and [p["min"] for p in out["places"]] == sorted(p["min"] for p in out["places"])


def test_find_sort_distance_without_a_point_is_an_error(k):
    with pytest.raises(ValueError, match="near_place"):
        k.find({"sort": "distance"}, S)
    with pytest.raises(ValueError, match="sort must"):
        k.find({"sort": "cheapest"}, S)
    with pytest.raises(ValueError, match="price_max"):
        k.find({"price_max": -1}, S)
    with pytest.raises(ValueError, match="unknown place"):
        k.find({"near_place": "nope"}, S)


def test_find_sort_reputation(k):
    out = k.find({"groups": ["cafe"], "sort": "reputation"}, S)
    assert [p["id"] for p in out["places"]] == ["0xa:0x1", "0xc:0x1", "0xb:0x1"]


def test_find_extension_keeps_the_hard_filters_and_hidden_places(k):
    from trip.domain.state import Evidence
    hard = TripState(hard=(Hard(feature="kids", op="ne", value="unsuitable", unknown_policy="exclude",
                                evidence=(Evidence(turn=1, quote="đi với bé"),)),))
    out = k.find({"groups": ["cafe"], "sort": "reputation"}, hard)
    assert [p["id"] for p in out["places"]] == ["0xa:0x1"]  # b unsuitable, c unknown under exclude
    hid = TripState(meta=Meta(hidden_ids=("0xa:0x1",)))
    assert "0xa:0x1" not in [p["id"] for p in k.find({"groups": ["cafe"], "sort": "reputation"}, hid)["places"]]
    assert "0xa:0x1" not in [p["id"] for p in k.find({"groups": ["cafe"]}, hid)["places"]]  # also the plain find


# ---------- place_evidence ----------

def test_evidence_answers_a_feature_and_lists_unknown(k):
    out = k.more.evidence("0xa:0x1", "có chỗ đậu xe không", ["parking", "toilet_available"], S)
    assert out["answers"][0]["fid"] == "parking" and out["answers"][0]["value"] == "easy" and out["answers"][0]["n"] == 3
    assert out["unknown"] == ["toilet_available"] and out["as_of"] == "2026-10-11"


def test_evidence_matches_the_question_when_no_feature_given(k):
    out = k.more.evidence("0xa:0x1", "yên tĩnh không", None, S, match=lambda q: ["noise"])
    assert [a["fid"] for a in out["answers"]] == ["noise"]
    assert "no evidence" in k.more.evidence("0xc:0x1", "ồn không", ["noise"], S)["note"]


def test_evidence_silence_is_not_a_fact(recs):
    recs[0]["environment"]["parking"].update(reason="silence", value="easy")
    out = make(recs).more.evidence("0xa:0x1", "đậu xe", ["parking"], S)
    assert "absence" in out["answers"][0]["note"]


def test_evidence_crowd_and_bad_feature(k):
    out = k.more.evidence("0xa:0x1", "đông giờ nào", ["crowd"], S)
    assert out["crowd"]["peak"]["day"] == "sat"
    with pytest.raises(ValueError, match="unknown feature"):
        k.more.evidence("0xa:0x1", "x", ["bogus"], S)
    with pytest.raises(ValueError, match="unknown place"):
        k.more.evidence("nope", "x", ["noise"], S)


def test_evidence_flags_a_place_the_trip_rules_out(k):
    from trip.domain.state import Evidence
    hard = TripState(hard=(Hard(feature="kids", op="ne", value="unsuitable", unknown_policy="exclude",
                                evidence=(Evidence(turn=1, quote="đi với bé"),)),))
    assert k.more.evidence("0xb:0x1", "ồn không", ["noise"], hard)["fits_trip"] is False


# ---------- compare_places ----------

def test_compare_gives_the_same_fields_and_unknown(k):
    out = k.more.compare(["0xa:0x1", "0xb:0x1"], ["noise", "parking"], S)
    a, b = out["rows"]
    assert a["price"] == [30000, 60000] and a["open_now"] is True and a["aspects"] == {"noise": "quiet", "parking": "easy"}
    assert b["aspects"] == {"noise": "loud", "parking": "unknown"}
    assert a["entry"] == "unknown" and a["night"] == "unknown"


def test_compare_default_aspects_and_same_place_note(k):
    out = k.more.compare(["0xa:0x1", "0xc:0x1"], None, S)
    assert out["aspects"] == ["crowd", "noise", "parking", "value_for_money"]
    assert out["same_place"] == [["0xa:0x1", "0xc:0x1"]]


def test_compare_needs_two_to_four_places(k):
    with pytest.raises(ValueError, match="2 to 4"):
        k.more.compare(["0xa:0x1"], None, S)
    with pytest.raises(ValueError, match="2 to 4"):
        k.more.compare(["0xa:0x1", "0xb:0x1", "0xc:0x1", "0xd:0x1", "0xe:0x1"], None, S)
    with pytest.raises(ValueError, match="aspect"):
        k.more.compare(["0xa:0x1", "0xb:0x1"], ["nope"], S)


# ---------- place_status ----------

def test_status_open_now_from_firm_hours(k):
    out = k.more.status("0xa:0x1", S)
    assert out["open_now"] is True and out["hours_today"] == "07:00-22:00" and out["closure"] == "no closure report in the data"
    assert out["corpus_status"] == "VERIFIED" and out["last_seen"] == "2026-10-11"


def test_status_open_now_is_unknown_without_firm_hours(recs):
    recs[2]["operation"]["hours"] = None
    out = make(recs).more.status("0xc:0x1", S)
    assert out["open_now"] == "unknown" and out["hours_today"] == "unknown"


def test_open_state_handles_midnight_and_uncertain():
    late = {"status": "VERIFIED", "value": {"fri": [["18:00", "02:00"]], "sat": [["18:00", "02:00"]]}}
    assert open_state(late, datetime(2026, 10, 31, 1, 0, tzinfo=VN))[0] is True  # Sat 01:00, Friday's window
    assert open_state(late, datetime(2026, 10, 30, 12, 0, tzinfo=VN))[0] is False
    assert open_state({"status": "UNCERTAIN", "value": ALL_DAY}, NOW) == (None, None)


def test_status_reports_a_closure_from_the_pulse(recs):
    pulse = lambda **kw: {"items": [{"kind": "closed", "name": "Quán Đã Đóng", "place_id": None,  # noqa: E731
                                     "text": "Google Maps ghi đóng cửa vĩnh viễn (tra ngày 07/10)"}]}
    kk = make(recs, pulse=pulse)
    out = kk.more.status("Quán Đã Đóng", S)
    assert out["status"] == "closed_reported" and "07/10" in out["closure"]["text"]
    recs[1]["identity"]["name"] = "Quán Đã Đóng"
    kk2 = make(recs, pulse=pulse)
    assert "07/10" in kk2.more.status("0xb:0x1", S)["closure"]["text"]
    with pytest.raises(ValueError, match="unknown place"):
        kk.more.status("không có", S)


# ---------- find_dishes ----------

def test_dishes_through_the_hard_filters(k):
    k.catalog.dishes = lambda q: [{"id": "0xa:0x1", "name": "Cà Phê Đồi Thông", "score": 9,
                                   "evidence": [{"source": "menu", "dish": "Bánh căn trứng"}]},
                                  {"id": "0xb:0x1", "name": "Quán Nhạc Ồn Ào", "score": 5, "evidence": [{"source": "reviews", "dish": "bánh căn"}]}]
    from trip.domain.state import Evidence
    hard = TripState(hard=(Hard(feature="kids", op="ne", value="unsuitable", unknown_policy="exclude",
                                evidence=(Evidence(turn=1, quote="đi với bé"),)),))
    out = k.more.dishes("bánh căn", hard)
    assert [p["id"] for p in out["places"]] == ["0xa:0x1"] and out["places"][0]["dish"] == ["Bánh căn trứng"]
    k.catalog.dishes = lambda q: []
    assert "unknown, not absent" in k.more.dishes("sushi", S)["note"]


# ---------- distance by mode, route_time ----------

ROUTE = lambda pts, mode: {"coords": [[11.94, 108.44], [11.95, 108.44]], "minutes": 7 if mode == "car" else 6,  # noqa: E731
                           "source": "osrm", "fetched_at": "t"}


def test_distance_by_mode(recs):
    kk = make(recs, live=LiveTools(route=ROUTE, matrix=lambda p: {"minutes": [[0, 9], [9, 0]], "source": "osrm", "fetched_at": "t"}))
    assert kk.distance("0xa:0x1", "0xc:0x1")["minutes"] == 9  # no mode: the default vehicle, as before
    car = kk.distance("0xa:0x1", "0xc:0x1", "car")
    assert car["minutes"] == 7 and car["mode"] == "car" and car["km_road"] > 0
    walk = kk.distance("0xa:0x1", "0xc:0x1", "walk")
    assert walk["minutes"] == round(walk["km_road"] / 4.5 * 60) and "estimate" in walk
    assert "error" in kk.distance("0xa:0x1", "0xc:0x1", "bike")
    assert kk.distance("0xa:0x1", "0xc:0x1", "walk")["from"] == "Cà Phê Đồi Thông"


def test_distance_by_mode_without_route_is_unavailable(recs):
    kk = make(recs, live=LiveTools(matrix=lambda p: {"minutes": [[0, 9], [9, 0]]}))
    assert kk.distance("0xa:0x1", "0xc:0x1", "car") == {"error": "distance unavailable"}


def test_route_time_chains_legs_and_states_partial_totals(recs):
    kk = make(recs, live=LiveTools(route=ROUTE))
    out = kk.more.route_time(["0xa:0x1", "0xc:0x1", "0xd:0x1"], "center", "car", S)
    assert [l["minutes"] for l in out["legs"]] == [7, 7, 7] and out["total_minutes"] == 21
    assert out["legs"][0]["from"] == "Chợ Đà Lạt"

    def flaky(pts, mode):
        if pts[1] == (11.86, 108.56):
            raise OSError("osrm down")
        return ROUTE(pts, mode)
    part = make(recs, live=LiveTools(route=flaky)).more.route_time(["0xa:0x1", "0xc:0x1", "0xd:0x1"], None, "car", S)
    assert part["total_minutes"] == "unknown" and part["partial_minutes"] == 7 and part["legs"][1]["minutes"] == "unknown"
    with pytest.raises(ValueError, match="stops"):
        kk.more.route_time(["0xa:0x1"], None, "car", S)


# ---------- journey ----------

RAW_JOURNEY = {"origin": "Hà Nội", "day": "2026-11-12", "options": [
    {"mode": "plane", "feasible": True, "reason": "flights", "minutes": 300, "price_min_vnd": 900000, "price_max_vnd": 1500000,
     "legs": [], "offers": [{"carrier": "Vietjet", "flight_no": "VJ 360", "depart_at": "2026-11-12T08:00", "arrive_at": "2026-11-12T09:30",
                             "price_vnd": 900000, "stops": 0, "observed_at": "2026-10-28", "source": "gflights", "url": "x"}]},
    {"mode": "bus", "feasible": None, "reason": "unchecked", "minutes": None, "legs": [], "offers": []},
    {"mode": "car", "feasible": True, "reason": "road", "minutes": 900, "legs": [{"via": "đèo Prenn"}], "offers": []}]}


def test_journey_summarises_options_and_keeps_unknown(recs):
    seen = []
    kk = make(recs, live=LiveTools(journey=lambda o, lat, lng, day: seen.append((o, lat, lng, day)) or RAW_JOURNEY))
    out = kk.more.journey("Hà Nội", "2026-11-12", S)
    plane, bus, car = out["options"]
    assert seen == [("Hà Nội", None, None, "2026-11-12")]
    assert plane["offers"][0]["flight_no"] == "VJ 360" and plane["price_vnd"] == [900000, 1500000] and "url" not in plane["offers"][0]
    assert bus["feasible"] == "unknown" and bus["minutes"] == "unknown" and car["via"] == "đèo Prenn"


def test_journey_uses_the_trip_origin_and_start_date(recs):
    seen = []
    kk = make(recs, live=LiveTools(journey=lambda o, lat, lng, day: seen.append((o, lat, lng, day)) or RAW_JOURNEY))
    raw = TripState().model_dump(mode="json")
    ev = [{"turn": 1, "quote": "từ Hà Nội"}]
    raw["origin"] = {"value": {"text": "Hà Nội", "lat": 21.0, "lng": 105.8}, "source": "user", "confidence": "high", "status": "confirmed", "evidence": ev}
    raw["start_date"] = {"value": "2026-11-12", "source": "user", "confidence": "high", "status": "confirmed", "evidence": ev}
    kk.more.journey(None, None, TripState.model_validate(raw))
    assert seen == [("Hà Nội", 21.0, 105.8, "2026-11-12")]
    with pytest.raises(ValueError, match="origin"):
        kk.more.journey(None, None, S)
    with pytest.raises(ValueError, match="journey unavailable"):
        make(recs).more.journey("Hà Nội", None, S)


# ---------- climate, calendar, area ----------

CLIMATE = {str(m): {"tmax_c": 20.0 + m / 10, "tmin_c": 12.0, "rain_prob": 0.1 * (m % 10), "fog_prob": None, "days": 300, "years": 11} for m in range(1, 13)}
CAL = [{"date": f"2026-12-{d:02d}", "lunar": {"year": 2026, "month": 10, "day": d, "leap": False}, "holiday": "Giáng sinh" if d == 25 else None}
       for d in range(1, 32)]


def test_climate_for_a_month_and_all_months(recs):
    kk = make(recs, feeds=Feeds(now=lambda: NOW, climate=lambda: CLIMATE))
    one = kk.more.climate(12)
    assert one["month"] == 12 and one["tmin_c"] == 12.0 and "fog_prob" not in one and "not a forecast" in one["note"]
    allm = kk.more.climate(None)
    assert len(allm["months"]) == 12 and len(allm["rainiest_months"]) == 5
    with pytest.raises(ValueError, match="climate unavailable"):
        make(recs).more.climate(1)


def test_calendar_holidays_events_and_no_crowd_claim(recs):
    pulse = lambda kind=None, month=None, limit=3: {"items": [{"kind": "event", "name": "Festival Hoa", "place_id": None, "text": "tháng 12", "sources": []}]}  # noqa: E731
    kk = make(recs, feeds=Feeds(now=lambda: NOW, calendar=lambda: CAL), pulse=pulse)
    out = kk.more.calendar(date(2026, 12, 20), date(2026, 12, 27), S)
    assert out["holidays"] == [{"date": "2026-12-25", "name": "Giáng sinh"}] and out["weekend_days"] == 3
    assert out["events"][0]["name"] == "Festival Hoa" and "no crowd data" in out["note"]
    assert out["lunar_first"] == "20/10"
    with pytest.raises(ValueError, match="range"):
        kk.more.calendar(date(2026, 12, 1), date(2027, 3, 1), S)
    with pytest.raises(ValueError, match="does not cover"):
        kk.more.calendar(date(2030, 1, 1), date(2030, 1, 3), S)


def test_area_notice_three_states(recs):
    area = {"kind": "military", "name": "Kho Quân khí K899"}
    kk = make(recs, feeds=Feeds(now=lambda: NOW, restricted=lambda lat, lng: [area] if lat > 11.945 else []))
    assert kk.more.area("0xb:0x1")["areas"] == [{"kind": "military", "name": "Kho Quân khí K899"}]
    assert kk.more.area("0xa:0x1")["status"] == "none_listed" and "not prove" in kk.more.area("0xa:0x1")["note"]
    never = make(recs, feeds=Feeds(now=lambda: NOW, restricted=lambda lat, lng: None))
    assert never.more.area("0xa:0x1")["status"] == "unknown"
    assert make(recs).more.area("0xa:0x1")["status"] == "unknown"


# ---------- find_stays, estimate_cost ----------

PRICES = {("0xe:0x1", "2026-11-12", 2): {"price_night_vnd": 950000, "price_total_vnd": 1900000, "observed_at": "2026-10-28T08:00:00+00:00",
                                       "source": "gtravel", "available": True}}


def test_stays_dated_price_beats_the_reference_and_unpriced_are_counted(recs):
    kk = make(recs, feeds=Feeds(now=lambda: NOW, stay_prices=lambda: PRICES))
    out = kk.more.stays({}, {"check_in": "2026-11-12", "nights": 2}, S)
    by = {s["id"]: s for s in out["stays"]}
    assert by["0xe:0x1"]["price"]["kind"] == "dated" and by["0xe:0x1"]["price"]["night_vnd"] == 950000 and by["0xe:0x1"]["price"]["as_of"] == "2026-10-28"
    assert by["0x10:0x1"]["price"]["kind"] == "reference" and by["0x10:0x1"]["price"]["as_of"] == "2026-10-08" and "note" in by["0x10:0x1"]["price"]
    assert "0xf:0x1" not in by and out["no_price"] == 1
    assert set(by) <= {"0xe:0x1", "0xf:0x1", "0x10:0x1"} and "0xa:0x1" not in by  # only lodging


def test_stays_price_max_and_sort(recs):
    kk = make(recs, feeds=Feeds(now=lambda: NOW, stay_prices=lambda: {}))
    out = kk.more.stays({"price_max": 500000}, None, S)
    assert [s["id"] for s in out["stays"]] == ["0x10:0x1"]
    srt = kk.more.stays({"sort": "price"}, None, S)
    assert [s["id"] for s in srt["stays"]] == ["0x10:0x1", "0xe:0x1"]
    with pytest.raises(ValueError, match="check_in"):
        kk.more.stays({}, {"check_in": "tomorrow"}, S)
    with pytest.raises(ValueError, match="nights"):
        kk.more.stays({}, {"check_in": "2026-11-12", "nights": 0}, S)


def test_estimate_cost_adds_only_stated_prices(recs):
    kk = make(recs, feeds=Feeds(now=lambda: NOW, stay_prices=lambda: {}))
    out = kk.more.cost(["0xa:0x1", "0xd:0x1", "0xc:0x1", "0xe:0x1"], 2, 2, None, S)
    lines = {l["id"]: l for l in out["lines"]}
    assert lines["0xa:0x1"]["spend"]["total"] == [60000, 120000]
    assert lines["0xd:0x1"]["entry"] == {"each": 75000, "kind": "official", "total": 150000}  # official adult price beats the fee estimate
    assert lines["0xe:0x1"]["room_night"]["night_vnd"] == 800000 and lines["0xe:0x1"]["nights"] == 2 and lines["0xe:0x1"]["per"] == "one room"
    assert out["total_vnd"] == [60000 + 150000 + 1600000, 120000 + 150000 + 1600000]
    assert out["unknown"] == [{"id": "0xc:0x1", "n": "Tiệm Không Giá"}] and "leaves out" in out["partial"]


def test_estimate_cost_nothing_known_and_bad_input(recs):
    kk = make(recs)
    out = kk.more.cost(["0xc:0x1"], 3, None, None, S)
    assert out["total_vnd"] == "unknown" and out["lines"] == []
    with pytest.raises(ValueError, match="people"):
        kk.more.cost(["0xa:0x1"], 0, None, None, S)
    with pytest.raises(ValueError, match="1 to 10"):
        kk.more.cost([], 2, None, None, S)


# ---------- local_tips ----------

CLAIMS = [{"claim_id": "c1", "status": "kept", "fact": True, "subject_kind": "poi", "subject": "Đồi Chè Cầu Đất", "kind": "tip",
           "text": "Nên đi trước 8h để không bị sương che", "months": [11, 12], "days": [], "hours": "", "weather": "", "who": "",
           "amount_min_vnd": None, "amount_max_vnd": None, "sources": 2, "domains": ["a.vn"], "confidence": 0.9,
           "evidence_json": '[{"domain": "a.vn", "retrieved_at": "2026-10-28T09:00:00+00:00", "quote": "q"}]', "matched": []},
          {"claim_id": "c2", "status": "unverified", "fact": False, "subject_kind": "city", "subject": "Đà Lạt", "kind": "notice",
           "text": "Cẩn thận giá gửi xe quanh hồ", "months": [], "days": [], "hours": "", "weather": "", "who": "", "amount_min_vnd": 20000,
           "amount_max_vnd": 30000, "sources": 1, "domains": ["b.vn"], "confidence": 0.5,
           "evidence_json": '[{"domain": "b.vn", "retrieved_at": "2026-10-27T09:00:00+00:00"}]', "matched": []}]


def test_tips_for_a_place_mix_the_record_and_labelled_claims(recs):
    kk = make(recs)
    kk.retrieval._region.local_claims = CLAIMS
    out = kk.more.tips("0xd:0x1", None, S)
    kinds = [(t["src"], t["kind"]) for t in out["tips"]]
    assert ("place", "best time") in kinds and ("place", "access") in kinds and ("place", "best months") in kinds
    local = [t for t in out["tips"] if t["src"] == "local"]
    assert local[0]["label"] == "fact" and local[0]["domain"] == "a.vn" and local[0]["date"] == "2026-10-28" and local[0]["months"] == [11, 12]


def test_tips_by_topic_label_unverified_as_reference(recs):
    kk = make(recs)
    kk.retrieval._region.local_claims = CLAIMS
    out = kk.more.tips(None, "gửi xe", S)
    assert [t["label"] for t in out["tips"]] == ["reference"] and out["tips"][0]["vnd"] == [20000, 30000]
    by_kind = kk.more.tips(None, "notice", S)
    assert len(by_kind["tips"]) == 1
    none = kk.more.tips(None, "xyz", S)
    assert none["tips"] == [] and "no local advice" in none["note"]
    with pytest.raises(ValueError, match="place_id or topic"):
        kk.more.tips(None, None, S)


def test_unit_price_reads_stay_person_and_entry():
    assert unit_price({"g": "stay", "night": 700000}) == (700000, "night")
    assert unit_price({"price": [30000, 60000]}) == (30000, "person")
    assert unit_price({"fee": {"min": 40000, "typ": 50000}}) == (40000, "entry")
    assert unit_price({"g": "cafe"}) == (None, None)


def test_unit_price_falls_back_to_the_upper_bound_only_when_the_lower_is_absent():
    """Serving writes Maps' "up to 100K" as min_vnd None + up_to (never 1 VND); the card then holds [None, max]."""
    assert unit_price({"price": [None, 100000]}) == (100000, "person")
    assert unit_price({"price": [None, None]}) == (None, None)
    assert unit_price({"price": [30000, 60000]}) == (30000, "person")


def test_cost_and_compare_keep_a_missing_lower_bound_unknown(recs):
    recs[0]["operation"]["price_per_person"] = {"value": {"min_vnd": None, "max_vnd": 100000, "up_to": True},
                                                "as_of": "2026-10-12", "status": "VERIFIED"}
    kk = make(recs)
    pid = recs[0]["id"]
    line = {ln["id"]: ln for ln in kk.more.cost([pid], 2, None, None, S)["lines"]}[pid]
    assert line["spend"]["each"] == [None, 100000] and line["spend"]["total"] == [0, 200000] and line["spend"]["up_to"] is True
    assert kk.more.compare([pid, recs[1]["id"]], None, S)["rows"][0]["price"] == [None, 100000]


def test_find_cards_keep_an_up_to_price_as_none_and_max(recs):
    recs[0]["operation"]["price_per_person"] = {"value": {"min_vnd": None, "max_vnd": 100000, "up_to": True},
                                                "status": "VERIFIED"}
    out = make(recs).more.find({"groups": ["cafe"]}, S)
    card = next(p for p in out["places"] if p["id"] == recs[0]["id"])
    assert card["price"] == [None, 100000] and card["price_from"] == 100000
    assert all(p["price"][0] is None or p["price"][0] >= 1000 for p in out["places"] if isinstance(p.get("price"), list))

