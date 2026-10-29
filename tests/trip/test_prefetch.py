"""Clef prepares the assistant's read tools (plan 2026-10-28-trip-decision-chatbot Task 3, spec §B.3)."""

import time
from datetime import date

from trip.agent.prefetch import GROUPS, Route, candidates, places_query, prepare, route
from trip.domain.state import Evidence, TripState, Update, apply
from trip.infrastructure.clef import yes_prob


def test_candidates_keeps_accents_and_whole_name_first(served_catalog):
    catalog = served_catalog
    ids = [pid for pid, _ in candidates("Đồi chè Cầu Đất mở cửa mấy giờ", catalog)]
    assert ids and catalog.by_id[ids[0]].name.lower().startswith("đồi chè cầu đất")
    assert "0xe:0x1" not in ids  # a lodging only when its whole name is typed
    assert candidates("mình muốn lên đó", catalog) == []  # "lên" is not "Len Shop"
    assert [pid for pid, _ in candidates("Len Shop có gì", catalog)] == ["0xf:0x1"]
    assert candidates("quán Mơ có gì", catalog) == []


def test_candidates_whole_stay_name_counts(served_catalog):
    assert [pid for pid, _ in candidates("Khách Sạn Đồi Chè còn phòng không", served_catalog)][0] == "0xe:0x1"


def test_yes_prob_reads_the_yes_option_whatever_was_chosen():
    answers = {"g": {"choice": "B", "probabilities": {"A": 0.4, "B": 0.6}}}
    assert yes_prob(answers, "g") == 0.4 and yes_prob({}, "g") == 0.0


def test_route_keywords_only_add(cfg):
    r = route("Ngày 31/10 có mưa không, ăn gì cho ấm?", [], cfg, ask=lambda *a: {})
    assert {"weather", "places"} <= r.groups


def test_route_threshold(cfg):
    fake = lambda s, q, c: {"distance": {"choice": "B", "probabilities": {"A": 0.4, "B": 0.6}}}  # noqa: E731
    assert "distance" in route("đi mất bao lâu", [], cfg, ask=fake).groups
    low = lambda s, q, c: {"distance": {"choice": "B", "probabilities": {"A": 0.2, "B": 0.8}}}  # noqa: E731
    assert "distance" not in route("đi mất bao lâu", [], cfg, ask=low).groups


def test_route_one_request_with_named_places(cfg, served_catalog):
    seen = []

    def fake(state, questions, c):
        seen.append(questions)
        return {"detail": {"choice": "A", "probabilities": {"A": 0.9}}, "place1": {"choice": "P0"}}
    cands = candidates("Đồi chè Cầu Đất mở cửa mấy giờ", served_catalog)
    r = route("Đồi chè Cầu Đất mở cửa mấy giờ", cands, cfg, ask=fake)
    assert len(seen) == 1 and set(GROUPS) | {"place1", "place2"} <= set(seen[0])
    assert r.places == [cands[0][0]] and "detail" in r.groups and "places" not in r.groups


def test_route_center_for_distance(cfg):
    fake = lambda s, q, c: {"distance": {"choice": "A", "probabilities": {"A": 0.9}}}  # noqa: E731
    assert route("Từ chợ lên Langbiang bao xa?", [], cfg, ask=fake).places == ["center"]


def test_places_query_drops_the_weather_clause():
    assert places_query("Tìm quán bánh mì xíu mại, sáng mai trời lạnh không?") == "Tìm quán bánh mì xíu mại"


def test_prepare_runs_the_groups(turn_tools):
    t = turn_tools()
    state = apply(TripState(), Update(field="start_date", op="set", value=date(2026, 10, 30), source="user",
                                      confidence="high", evidence=Evidence(turn=1, quote="30/10")))
    data = prepare(Route({"places", "detail", "weather", "distance"}, ["0xa:0x1", "0xd:0x1"], {}, 0.0),
                   "Gợi ý quán cà phê, mai có mưa không", state, t, date(2026, 10, 28), 1.0)
    assert data["tim_noi"] and data["chi_tiet"][0]["n"] == "Cà Phê Đồi Thông Xanh"
    assert [w["date"] for w in data["thoi_tiet"]] == ["2026-10-29", "2026-10-30"]  # the asked day, and the trip's
    assert data["khoang_cach"]["minutes"] == 25
    assert all("km_line" in x for x in data["tim_noi"])  # distance asked with a list: km from the place named last
    assert "0xa:0x1" in t.told_ids


def test_prepare_times_out_into_cache(turn_tools_slow_weather):
    t = turn_tools_slow_weather  # weather callable sleeps 0.6 s
    started = time.monotonic()
    data = prepare(Route({"weather"}, [], {}, 0.0), "mai có mưa không", TripState(), t, date(2026, 10, 28), 0.1)
    assert "thoi_tiet" not in data and time.monotonic() - started < 0.5
    for _ in range(40):  # the late result still lands in the turn's cache
        if t.cache:
            break
        time.sleep(0.05)
    assert t.run("weather", {"date": "2026-10-29"})["rain_prob"] == 0.7 and t.log[-1] == "weather cached"


# ---------- round 5: does the prepared data answer every group the message needs? ----------

def test_covers_needs_data_for_every_group():
    from trip.agent.prefetch import covers
    places = {"tim_noi": [{"id": "0xa:0x1"}]}
    assert covers(Route({"places"}, []), places)
    assert not covers(Route(set(), []), {})  # nothing asked of the data: the model may look things up
    assert not covers(Route({"places", "weather"}, []), places)  # the weather is missing
    assert not covers(Route({"places"}, []), {"tim_noi": [{"error": "x"}]})
    assert not covers(Route({"places"}, []), {"tim_noi": []})
    detail = {"chi_tiet": [{"id": "0xa:0x1"}]}
    assert covers(Route({"detail"}, ["0xa:0x1"]), detail)
    assert not covers(Route({"detail"}, ["0xa:0x1", "0xd:0x1"]), detail)  # one named place has no data
    assert not covers(Route({"detail"}, []), detail)
    assert covers(Route({"weather"}, []), {"thoi_tiet": [{"date": "2026-10-30", "rain_prob": 0.3}]})
    assert not covers(Route({"weather"}, []), {"thoi_tiet": [{"error": "weather unavailable"}]})
    assert covers(Route({"distance"}, ["center", "0xa:0x1"]), {"khoang_cach": {"minutes": 9}})
    assert not covers(Route({"distance"}, ["center", "0xa:0x1"]), {"khoang_cach": {"error": "distance unavailable"}})
