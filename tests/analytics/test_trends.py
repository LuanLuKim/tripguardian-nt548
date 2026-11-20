from datetime import datetime, timedelta, timezone

import pytest
from psycopg.types.json import Jsonb

import analytics

pytestmark = pytest.mark.pg

NOW = datetime.now(timezone.utc)
A, B, C = "0xa:0x1", "0xb:0x2", "0xc:0x3"


@pytest.fixture
def pool(pg_url):
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    with ConnectionPool(pg_url, min_size=1, max_size=4, kwargs={"row_factory": dict_row}, open=True) as p:
        yield p


def journey(pool, jid, trip=None, *events, synthetic=False, days_ago=1):
    at = NOW - timedelta(days=days_ago)
    env = {"outputs": {"trip": trip}} if trip else {}
    with pool.connection() as conn:
        conn.execute("INSERT INTO journeys (id, stage, revision, envelope, created_at, updated_at) "
                     "VALUES (%s, 'trip', 0, %s, %s, %s)", (jid, Jsonb(env), at, at))
        conn.execute("INSERT INTO events (at, journey_id, source, name, props) VALUES (%s, %s, 'server', "
                     "'journey.create', %s)", (at, jid, Jsonb({"synthetic": True} if synthetic else {})))
        for i, (name, props) in enumerate(events):
            conn.execute("INSERT INTO events (at, journey_id, source, name, props) VALUES (%s, %s, 'server', %s, %s)",
                         (at + timedelta(minutes=i + 1), jid, name, Jsonb(props)))


def plan(pool, jid, *days):
    with pool.connection() as conn:
        tid = conn.execute("INSERT INTO trips (journey_id, start_date, plan_hash, created_at) VALUES (%s, %s, 'h', %s) "
                           "RETURNING id", (jid, (NOW + timedelta(days=10)).date(), NOW - timedelta(hours=1))).fetchone()["id"]
        for d, places in enumerate(days, 1):
            for s, pid in enumerate(places):
                conn.execute("INSERT INTO trip_stops (trip_id, day, seq, place_id, name, planned_arrive) "
                             "VALUES (%s, %s, %s, %s, %s, %s)", (tid, d, s, pid, f"Nơi {pid}",
                                                                 NOW.replace(hour=1 + s) + timedelta(days=d)))


def test_places_plans_and_what_people_ask_for(pool):
    trip = {"sources": {"companions": "user", "days": "user", "mobility": "default"},
            "context": {"companions": ["partner"], "days": 2, "mobility": "car"},
            "soft_weights": [{"feature": "cloud_hunting", "source": "user"}, {"feature": "noise", "source": "inferred"}],
            "liked_groups": ["chill"], "wishes": {"kinds": [{"kind": "Cà phê"}], "dishes": [{"dish": "bánh căn"}]},
            "vibes": [{"phrase": "săn mây"}, {"phrase": "ảnh bạn gửi"}]}
    journey(pool, "j00000000001", trip, ("decision.act.select", {"place_id": A}), ("decision.act.select", {"place_id": A}),
            ("detail_open", {"place_id": B}), ("place_like", {"place_id": B, "value": "on"}),
            ("place_like", {"place_id": C, "value": "off"}), ("decision.act.drop", {"place_id": C, "reason": "far"}),
            ("theme_open", {"theme": "cloud"}), ("places.search", {"q": "Bánh căn", "hits": 0}))
    journey(pool, "j00000000002", trip, ("card_impression", {"place_id": A, "rank": 1}), ("decision.act.select", {"place_id": A}))
    journey(pool, "j00000000003", trip, ("decision.act.select", {"place_id": B}), synthetic=True)
    plan(pool, "j00000000001", [A, B], [C])
    plan(pool, "j00000000002", [A, B])
    plan(pool, "j00000000003", [A, B])  # a synthetic journey's plan is left out

    out = analytics.trends(pool, {})
    places = {p["place_id"]: p for p in out["places"]}
    assert places[A]["chosen"] == 2 and places[A]["planned"] == 2 and places[A]["name"] == f"Nơi {A}"
    assert places[B]["viewed"] == 1 and places[B]["liked"] == 1 and places[C]["liked"] == 0
    assert places[C]["dropped"] == 1 and out["places"][0]["place_id"] == A
    assert places[A]["recent"] == 2  # two journeys chose it in the last 7 days
    assert places[A]["shown"] == 1 and places[A]["chosen_seen"] == 1  # the other pick came without a card
    p = out["plans"]
    assert p["trips"] == 2 and p["pairs"][0] == {"a": A, "b": B, "n": 2, "a_name": f"Nơi {A}", "b_name": f"Nơi {B}"}
    assert p["chains"][0]["n"] == 2 and p["days"] == [{"key": 1, "n": 1}, {"key": 2, "n": 1}]
    i = out["intent"]
    assert i["journeys"] == 2 and i["companions"] == [{"key": "partner", "n": 2}] and i["mobility"] == []
    assert i["interests"] == [{"key": "cloud_hunting", "n": 2}] and i["kinds"] == [{"key": "cà phê", "n": 2}]
    assert i["vibes"] == [{"key": "săn mây", "n": 2}] and i["dishes"][0]["key"] == "bánh căn"
    assert out["themes"] == [{"key": "cloud", "n": 1}] and out["searches"] == [{"q": "bánh căn", "n": 1, "misses": 1}]
    assert out["drop_reasons"] == [{"key": "far", "n": 1}]

    # A journey that changed is read again; the others come from the per-process cache.
    with pool.connection() as conn:
        conn.execute("UPDATE journeys SET envelope = %s, updated_at = now() WHERE id = 'j00000000002'",
                     (Jsonb({"outputs": {"trip": {**trip, "context": {"companions": ["kids"]}}}}),))
    assert {c["key"] for c in analytics.trends(pool, {})["intent"]["companions"]} == {"partner", "kids"}


def test_server_serves_the_people_routes(pool):
    import json
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.error import HTTPError
    from urllib.request import urlopen

    from urllib.request import Request

    from analytics.auth import AdminAuth
    from analytics.server import handler
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler(pool, AdminAuth("a@x.vn", "pw")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api/analytics"
    try:
        with urlopen(Request(f"{base}/login", json.dumps({"email": "a@x.vn", "password": "pw"}).encode(),
                             {"Content-Type": "application/json"})) as r:
            cookie = r.headers["Set-Cookie"].split(";")[0]
        for path in ("trends", "users", "users/list"):
            with urlopen(Request(f"{base}/{path}", headers={"Cookie": cookie})) as r:
                assert r.status == 200 and json.load(r) is not None
        with pytest.raises(HTTPError) as e:
            urlopen(Request(f"{base}/users/{'0' * 32}", headers={"Cookie": cookie}))
        assert e.value.code == 404
    finally:
        srv.shutdown()
