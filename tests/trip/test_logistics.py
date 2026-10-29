from datetime import date

from trip.domain.compile import day_window
from trip.domain.logistics import entry_road, nearest_airport, pick_transit
from trip.domain.state import Base, Transit, TripState
from trip.infrastructure.settings import load

REAL = load()  # the shipped entry_roads and airports
NHA_TRANG = Base(text="Nha Trang", lat=12.2388, lng=109.1967)
FLIGHT_IN = Transit(mode="plane", carrier="Vietjet Air VJ361", depart_at="2026-12-14T07:05", arrive_at="2026-12-14T08:00",
                    from_point="Tân Sơn Nhất", to_point="Sân bay Liên Khương", price_vnd=890000,
                    source="google_flights", fetched_at="2026-12-01T03:00:00+00:00")
FLIGHT_OUT = Transit(mode="plane", carrier="Vietjet Air VJ362", depart_at="2026-12-16T18:40", arrive_at="2026-12-16T19:35",
                     from_point="Sân bay Liên Khương", to_point="Tân Sơn Nhất", price_vnd=890000,
                     source="google_flights", fetched_at="2026-12-01T03:00:00+00:00")


def test_entry_road_follows_the_direction_of_the_origin():
    assert entry_road(Base(text="HCM", lat=10.78, lng=106.70), REAL).text == "Đèo Prenn"
    assert entry_road(NHA_TRANG, REAL).text == "Đèo Khánh Lê"
    assert entry_road(Base(text="Phan Rang", lat=11.56, lng=108.99), REAL).text == "Đèo Ngoạn Mục"


def test_an_origin_without_a_point_has_no_road_and_no_airport():
    assert entry_road(Base(text="đâu đó"), REAL) is None
    assert nearest_airport(Base(text="đâu đó"), REAL) is None


def test_a_chosen_flight_sets_the_day_window_and_the_city_entry_and_exit():
    st = pick_transit(TripState(), "inbound", FLIGHT_IN, REAL, 1)
    st = pick_transit(st, "outbound", FLIGHT_OUT, REAL, 2)
    assert day_window(st) == ("08:45", "17:55")  # arrival 08:00 + 45 min, departure 18:40 - 45 min
    assert st.entry_point.value.text == "Sân bay Liên Khương" and st.exit_point.value.text == "Sân bay Liên Khương"


def test_the_quiz_asks_how_and_from_where_but_never_for_a_coach_or_a_flight(catalog, cfg):
    from trip.domain.questions import quiz_queue
    from trip.domain.state import Field
    st = TripState()
    for mode in ("plane", "bus", "self"):
        s = st.model_copy(update={"arrival_mode": Field(value=mode), "start_date": Field(value=date(2026, 12, 14)),
                                  "days": Field(value=3)})
        qids = [q.qid for q in quiz_queue(s, catalog, cfg)]
        assert "origin" in qids and not {"inbound", "outbound"} & set(qids)


# ---------- B1/B2: home origin prior, trade-off sentences ----------

def _state(**fields):
    from trip.domain.state import Evidence, Update, apply
    st = TripState()
    for f, (v, op) in fields.items():
        st = apply(st, Update(field=f, value=v, op=op, source="user", confidence="high", evidence=Evidence(turn=1, quote="q")))
    return st


def test_home_point_in_the_profile_seeds_the_origin_as_a_prior_only():
    from trip.domain.patterns import seed_profile
    home = {"text": "Huế", "lat": 16.46, "lng": 107.59, "province": "Thừa Thiên Huế"}
    s = seed_profile(TripState(), {"home": home})
    assert (s.origin.value.text, s.origin.value.lat, s.origin.source) == ("Huế", 16.46, "profile")
    told = seed_profile(_state(origin=(NHA_TRANG, "set")), {"home": home})
    assert told.origin.value.text == "Nha Trang"  # this trip's own answer is never replaced


def test_motion_sick_party_driving_over_a_pass_is_told_so():
    from trip.domain.logistics import tradeoffs
    hcm = Base(text="HCM", lat=10.78, lng=106.70)
    from trip.domain.state import Evidence, Update, apply
    st = apply(TripState(), Update(field="origin", value=hcm, source="user", confidence="high", evidence=Evidence(turn=1, quote="q")))
    st = apply(st, Update(field="arrival_mode", value="self", source="user", confidence="high", evidence=Evidence(turn=1, quote="q")))
    assert tradeoffs(st, REAL) == []  # no fact about motion sickness: nothing is said
    st = apply(st, Update(field="signal", value="motion_sick", source="user", confidence="high", evidence=Evidence(turn=2, quote="tôi say xe")))
    [t] = tradeoffs(st, REAL)
    assert t["code"] == "pass_motion_sick" and "Đèo Prenn" in t["text"]


def test_overnight_coach_and_small_kids_are_told():
    from trip.domain.logistics import tradeoffs
    from trip.domain.state import Evidence, Update, apply
    night = Transit(mode="bus", carrier="Phương Trang", depart_at="2026-12-13T22:00", arrive_at="2026-12-14T04:30",
                    from_point="Miền Đông", to_point="Bến xe Đà Lạt", source="vexere", fetched_at="2026-12-01T03:00:00+00:00")
    ev = Evidence(turn=1, quote="q")
    st = apply(TripState(), Update(field="arrival_mode", value="bus", source="user", confidence="high", evidence=ev))
    st = apply(st, Update(field="companions", value="kids", op="add", source="user", confidence="high", evidence=ev))
    st = apply(st, Update(field="inbound", value=night, source="user", confidence="high", evidence=ev))
    codes = {t["code"] for t in tradeoffs(st, REAL)}
    assert codes == {"overnight_bus", "small_kids_long_ride"}
