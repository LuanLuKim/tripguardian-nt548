from datetime import datetime, timedelta

import pytest
from psycopg.types.json import Jsonb

from companion import Companion, load_settings as companion_settings
from notify import Gone, Notify
from notify.plan import TZ

pytestmark = pytest.mark.pg
UID = "c" * 32


def f(value, n=5):
    return {"value": value, "status": "VERIFIED", "n": n, "distribution": {value: n}, "evidence": ["x"]}


RECORDS = [
    {"id": "hill", "identity": {"name": "Đồi Mây", "lat": 11.94, "lng": 108.44},
     "experience": {"sunset_view": f("present"), "cloud_hunting": f("present", 9)}, "service": {}, "operation": {}},
    {"id": "hotpot", "identity": {"name": "Lẩu Gà", "lat": 11.95, "lng": 108.45},
     "experience": {}, "service": {"booking_needed": f("yes")}, "operation": {}},
]
PLAN = {"itinerary": [
    {"day": 1, "date": "2026-11-12", "items": [
        {"kind": "visit", "start": "15:30", "end": "18:00", "place_id": "hill", "name": "Đồi Mây"},
        {"kind": "visit", "start": "19:00", "end": "20:30", "place_id": "hotpot", "name": "Lẩu Gà"}]},
    {"day": 2, "date": "2026-11-13", "items": []}],
    "travel_load": [{"day": 1, "travel_min": 35}], "backups": {"places": [], "on_delay": []}}


class Push:
    def __init__(self):
        self.sent, self.gone = [], set()

    def __call__(self, sub, payload):
        if sub["endpoint"] in self.gone:
            raise Gone()
        self.sent.append((sub["endpoint"], payload))


@pytest.fixture
def world(pg_url):
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    clock = {"now": datetime(2026, 11, 8, 9, 0, tzinfo=TZ)}
    with ConnectionPool(pg_url, min_size=1, max_size=4, kwargs={"row_factory": dict_row}, open=True) as pool:
        with pool.connection() as conn:
            conn.execute("INSERT INTO users (id) VALUES (%s)", (UID,))
            conn.execute("INSERT INTO journeys (id, user_id, stage, revision, envelope) VALUES ('j00000000009', %s, "
                         "'planning', 3, %s)", (UID, Jsonb({"outputs": {"planning": PLAN}})))
        Companion(pool, RECORDS, companion_settings()).sync("j00000000009", UID, PLAN)
        push = Push()
        n = Notify(pool, RECORDS, push=push, now=lambda: clock["now"])
        n.subscribe(UID, {"endpoint": "https://push.example/1", "keys": {"p256dh": "k", "auth": "a"}})
        yield n, push, clock


def rows(n, where="true"):
    with n.pool.connection() as conn:
        return conn.execute(f"SELECT * FROM notifications WHERE {where} ORDER BY scheduled_at").fetchall()


def test_a_trip_gets_its_notes_once_and_only_from_real_data(world):
    n, _, _ = world
    n.schedule()
    kinds = sorted(r["kind"] for r in rows(n, "status = 'scheduled'"))
    assert kinds == ["book_ahead", "checkin_hint", "checkin_hint", "day_brief", "eve_of_trip", "golden_hour", "post_trip"]
    assert n.schedule() == 0  # unchanged plan: nothing new
    book = rows(n, "kind = 'book_ahead'")[0]
    assert book["scheduled_at"] == datetime(2026, 11, 9, 10, 0, tzinfo=TZ)
    assert book["payload"]["data"] == {"place": "Lẩu Gà", "when": "tối thứ Năm"}
    hint = {r["payload"]["data"]["place"]: r["payload"]["data"]["highlight"] for r in rows(n, "kind = 'checkin_hint'")}
    assert hint == {"Đồi Mây": "săn mây, biển mây", "Lẩu Gà": None}  # no highlight -> that note will be skipped


def test_sending_respects_the_cap_and_keeps_an_inbox_copy(world):
    n, push, clock = world
    n.schedule()
    clock["now"] = datetime(2026, 11, 9, 10, 1, tzinfo=TZ)
    assert n.send_due() == {"sent": 1, "skipped": 0, "later": 0}
    assert push.sent[0][1]["body"].startswith(("Psst… Lẩu Gà", "Lẩu Gà thường"))
    assert "/app/plan?journey=j00000000009&n=" in push.sent[0][1]["url"]
    inbox = n.inbox(UID)
    assert len(inbox) == 1 and not inbox[0]["opened"]


def test_missing_data_is_skipped_with_a_reason(world):
    n, push, clock = world
    n.schedule()
    clock["now"] = datetime(2026, 11, 12, 19, 0, tzinfo=TZ)
    n.send_due()
    hint = [r for r in rows(n, "kind = 'checkin_hint'") if r["payload"]["data"]["place"] == "Lẩu Gà"][0]
    assert hint["status"] == "skipped" and hint["skip_reason"] == "no_data"


def test_three_ignored_in_a_row_pause_until_the_app_is_opened(world):
    n, push, clock = world
    t = datetime(2026, 11, 13, 9, 0, tzinfo=TZ)
    with n.pool.connection() as conn:
        for i in range(5):
            conn.execute("INSERT INTO notifications (user_id, kind, payload, scheduled_at) VALUES (%s, 'post_trip', %s, %s)",
                         (UID, Jsonb({"key": f"k{i}", "data": {}, "valid_until": (t + timedelta(days=9)).isoformat()}),
                          t + timedelta(days=i)))
    for i in range(5):
        clock["now"] = t + timedelta(days=i, minutes=1)
        n.send_due()
        n.send_due()  # the "paused" note, when one was made
    sent = [r["kind"] for r in rows(n, "status = 'sent'")]
    assert sent == ["post_trip", "post_trip", "post_trip", "paused"]
    assert [r["skip_reason"] for r in rows(n, "status = 'skipped'")] == ["paused", "paused"]
    assert n.prefs(UID)["paused"]
    n.open(UID, n.inbox(UID)[0]["id"])
    assert not n.prefs(UID)["paused"]


def test_a_gone_subscription_is_removed_and_kinds_can_be_switched_off(world):
    n, push, clock = world
    push.gone.add("https://push.example/1")
    n.schedule()
    clock["now"] = datetime(2026, 11, 9, 10, 1, tzinfo=TZ)
    n.send_due()
    assert n.prefs(UID)["push_devices"] == 0 and len(n.inbox(UID)) == 1
    out = n.set_prefs(UID, {"enabled_kinds": ["post_trip"]})
    assert out["enabled_kinds"] == ["post_trip"]
    with pytest.raises(ValueError):
        n.set_prefs(UID, {"enabled_kinds": ["spam"]})
    with pytest.raises(ValueError):
        n.subscribe(UID, {"endpoint": "http://not-https", "keys": {"p256dh": "k", "auth": "a"}})


def test_a_new_plan_replaces_unsent_notes(world):
    n, _, _ = world
    n.schedule()
    moved = {**PLAN, "itinerary": [{**PLAN["itinerary"][0], "items": PLAN["itinerary"][0]["items"][:1]},
                                   PLAN["itinerary"][1]]}
    Companion(n.pool, RECORDS, companion_settings()).sync("j00000000009", UID, moved)
    with n.pool.connection() as conn:
        conn.execute("UPDATE journeys SET envelope = %s WHERE id = 'j00000000009'", (Jsonb({"outputs": {"planning": moved}}),))
    n.schedule()
    assert "book_ahead" not in {r["kind"] for r in rows(n, "status = 'scheduled'")}
    assert {r["kind"] for r in rows(n, "status = 'cancelled'")} >= {"book_ahead"}


def test_a_trip_with_nothing_left_to_send_is_not_planned_every_minute(world):
    n, _, clock = world
    clock["now"] = datetime(2026, 11, 15, 12, 0, tzinfo=TZ)  # just after the trip: every note has expired
    n.schedule()
    assert n.schedule() == 0
    with n.pool.connection() as conn:
        assert conn.execute("SELECT count(*) AS c FROM notifications").fetchone()["c"] == 1  # one marker only


def test_the_eve_note_reads_the_forecast_at_the_trips_own_first_stop(world):
    n, push, clock = world
    asked = []
    n.weather = lambda lat, lng, dates: asked.append((lat, lng, dates)) or {dates[0]: {"rain_prob": 0.7, "source": "open-meteo"}}
    n.schedule()
    clock["now"] = datetime(2026, 11, 11, 20, 1, tzinfo=TZ)
    n.send_due()
    assert asked == [(11.94, 108.44, ["2026-11-12"])]   # Đồi Mây, the first stop of day 1, not a hard-coded city point
    eve = rows(n, "kind = 'eve_of_trip'")[0]
    assert eve["status"] == "sent" and "70%" in eve["payload"]["body"]


def test_the_evening_check_runs_once_per_evening_and_notes_only_what_it_asks(world):
    n, push, clock = world
    calls = []
    asked = {"notify": True, "ask": [{"name": "Đồi Mây", "cause": {"text": "dự báo mưa 85% lúc 15–18h"}}]}
    n.eve = lambda j, snap, plan, h, today, trip=None: calls.append((j, today)) or asked
    with n.pool.connection() as conn:
        conn.execute("UPDATE journeys SET envelope = %s WHERE id = 'j00000000009'",
                     (Jsonb({"outputs": {"planning": PLAN}, "snapshots": {"planning": {"id": "abc"}}}),))
    clock["now"] = datetime(2026, 11, 11, 19, 30, tzinfo=TZ)
    assert n.check_eve() == 0 and calls == []                 # before eve_at
    clock["now"] = datetime(2026, 11, 11, 20, 5, tzinfo=TZ)
    assert n.check_eve() == 1 and calls == [("j00000000009", "2026-11-11")]
    assert n.check_eve() == 0 and len(calls) == 1             # once per evening
    note = rows(n, "kind = 'eve_replan'")[0]
    assert note["payload"]["key"] == "eve_replan:2026-11-12" and note["status"] == "scheduled"
    n.send_due()
    sent = [p for _, p in push.sent if "ngày mai" in p["title"]]
    assert sent and "/app/plan?journey=j00000000009" in sent[0]["url"] and "Đồi Mây" in sent[0]["body"]
    clock["now"] = datetime(2026, 11, 12, 20, 5, tzinfo=TZ)    # tomorrow is day 2: asked, nothing to say
    n.eve = lambda *a, **k: {"notify": False, "ask": []}
    assert n.check_eve() == 0
    assert rows(n, "payload->>'key' = 'eve_replan:2026-11-13'")[0]["status"] == "cancelled"


def test_no_evening_check_without_the_flag(world):
    n, _, clock = world
    clock["now"] = datetime(2026, 11, 11, 20, 5, tzinfo=TZ)
    assert n.eve is None and n.check_eve() == 0


def test_the_expert_runs_in_the_background_for_a_confirmed_trip_and_is_off_without_the_flag(world):
    n, _, clock = world
    calls = []
    assert n.expert is None and n.check_expert() == 0
    n.expert = lambda j, snap, plan, h: calls.append(j) or 2
    with n.pool.connection() as conn:
        conn.execute("UPDATE journeys SET envelope = %s WHERE id = 'j00000000009'",
                     (Jsonb({"outputs": {"planning": PLAN}, "snapshots": {"planning": {"id": "abc"}}}),))
    assert n.check_expert() == 1 and calls == ["j00000000009"]
    n.expert = lambda *a: None                       # the runner says this plan was already reviewed
    assert n.check_expert() == 0
    n.expert = lambda *a: (_ for _ in ()).throw(RuntimeError("model down"))
    assert n.check_expert() == 0                     # one bad trip never stops the worker
    clock["now"] = datetime(2026, 12, 1, 9, 0, tzinfo=TZ)   # the trip is over
    calls.clear()
    n.expert = lambda j, *a: calls.append(j) or 1
    assert n.check_expert() == 0 and calls == []
