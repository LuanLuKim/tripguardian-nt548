from datetime import date, datetime, timedelta

from notify import FORBIDDEN, decide, load_settings, render
from notify.plan import SLOT, TZ, rain_phrase

CFG = load_settings()
TRIP = (date(2026, 11, 12), date(2026, 11, 14))


def note(kind="day_brief", at=datetime(2026, 11, 12, 7, 30, tzinfo=TZ), valid_h=3):
    return {"kind": kind, "valid_until": at + timedelta(hours=valid_h)}


def test_every_template_fills_completely_and_never_guilt_trips():
    for kind, k in CFG["kinds"].items():
        for v in k["variants"]:
            data = {slot: "X" for slot in SLOT.findall(v["title"] + v["body"])}
            vid, title, body = render({"variants": [v]}, data, "seed")
            assert "{" not in title + body and vid == v["id"], kind
            assert not any(w in (title + body).lower() for w in FORBIDDEN), kind


def test_a_variant_with_a_missing_slot_is_not_used_and_no_variant_means_none():
    kind = CFG["kinds"]["eve_of_trip"]
    data = {"rain_phrase": "trời ít mưa", "pack": "áo khoác", "t_min": None}
    assert render(kind, data, "s")[0] == "b"  # the °C variant needs t_min
    assert render(kind, {"t_min": None, "rain_phrase": None, "pack": None}, "s") is None
    assert render(CFG["kinds"]["checkin_hint"], {"place": "Đồi chè", "highlight": None}, "s") is None


def test_daily_caps_before_and_during_the_trip():
    during = datetime(2026, 11, 13, 9, 0, tzinfo=TZ)
    n = note(at=during)
    assert decide(n, {}, 2, TRIP, during, CFG) == ("send", None)
    assert decide(n, {}, 3, TRIP, during, CFG) == ("skip", "daily_cap")
    before = datetime(2026, 11, 9, 10, 0, tzinfo=TZ)
    assert decide(note("book_ahead", before), {}, 1, TRIP, before, CFG) == ("skip", "daily_cap")
    assert decide(note("book_ahead", before), {}, 0, TRIP, before, CFG) == ("send", None)


def test_quiet_hours_move_to_seven_or_skip_when_too_late():
    late = datetime(2026, 11, 11, 22, 30, tzinfo=TZ)
    assert decide(note("post_trip", late, valid_h=24), {}, 0, TRIP, late, CFG) == \
        ("later", datetime(2026, 11, 12, 7, 0, tzinfo=TZ))
    dawn = datetime(2026, 11, 13, 5, 15, tzinfo=TZ)  # 45 min before sunrise: over before 07:00
    assert decide(note("golden_hour", dawn, valid_h=0.75), {}, 0, TRIP, dawn, CFG) == ("skip", "quiet_expired")


def test_switched_off_kinds_and_pause():
    now = datetime(2026, 11, 13, 9, 0, tzinfo=TZ)
    assert decide(note(at=now), {"enabled_kinds": ["post_trip"]}, 0, TRIP, now, CFG) == ("skip", "kind_off")
    paused = {"paused_until": now + timedelta(days=999)}
    assert decide(note(at=now), paused, 0, TRIP, now, CFG) == ("skip", "paused")
    assert decide(note("paused", now), paused, 0, TRIP, now, CFG) == ("send", None)
    assert decide(note(at=now - timedelta(hours=5)), {}, 0, TRIP, now, CFG) == ("skip", "expired")


def test_rain_phrase_only_from_a_forecast():
    assert rain_phrase(None) == (None, None)
    assert rain_phrase(0.7)[0] == "khả năng mưa 70%"


def test_bandit_waits_for_enough_sends_then_prefers_the_better_variant():
    import random
    from notify.plan import bandit
    rng = random.Random(1)
    assert bandit({"a": (199, 100), "b": (500, 10)}, 200, rng)(["a", "b"]) is None
    pick = bandit({"a": (400, 200), "b": (400, 20)}, 200, rng)
    assert [pick(["a", "b"]) for _ in range(50)].count("a") >= 48
    kind = {"variants": [{"id": "a", "title": "A", "body": "x"}, {"id": "b", "title": "B", "body": "y"}]}
    assert render(kind, {}, "seed", lambda ids: "b")[0] == "b"


def test_no_notification_opens_the_dropped_today_screen():
    # the product ends at the confirmed plan (/app/plan); /app/today is not a destination any more
    assert all(not link.startswith("/app/today") for link in CFG["links"].values())
    for kind in ("book_ahead", "eve_of_trip", "day_brief", "checkin_hint", "golden_hour", "weather_change"):
        assert CFG["links"][kind] == "/app/plan", kind


def test_the_eve_forecast_point_is_the_trips_own_first_stop_then_its_lodging():
    from notify.plan import trip_point
    recs = {"a": {"identity": {"lat": 11.91, "lng": 108.40}}, "b": {"identity": {"lat": 11.80, "lng": 108.50}},
            "stay1": {"identity": {"lat": 11.95, "lng": 108.43}}, "nocoord": {"identity": {}}}
    stops = [{"day": 2, "seq": 1, "place_id": "b"}, {"day": 1, "seq": 2, "place_id": "a"},
             {"day": 1, "seq": 1, "place_id": "nocoord"}]
    plan = {"lodging": {"chosen": {"id": "stay1"}}}
    assert trip_point(stops, plan, recs, 1) == (11.91, 108.40)   # first stop with coordinates on that day
    assert trip_point(stops, plan, recs, 3) == (11.95, 108.43)   # no stop that day -> the lodging
    assert trip_point([], {}, recs, 1) is None                   # nothing known -> no forecast, never a made-up city point
