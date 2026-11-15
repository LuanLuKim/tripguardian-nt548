from datetime import datetime, timedelta, timezone

import pytest
from psycopg.types.json import Jsonb

import analytics

pytestmark = pytest.mark.pg


@pytest.fixture
def pool(pg_url):
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    with ConnectionPool(pg_url, min_size=1, max_size=4, kwargs={"row_factory": dict_row}, open=True) as p:
        yield p


NOW = datetime.now(timezone.utc)


def user(pool, email=None, kind="user", role="user", days_ago=3, **profile):
    with pool.connection() as conn:
        uid = conn.execute("INSERT INTO users (email, kind, role, google_sub, created_at) VALUES (%s, %s, %s, %s, %s) "
                           "RETURNING id", (email, kind, role, email, NOW - timedelta(days=days_ago))).fetchone()["id"]
        conn.execute("INSERT INTO profiles (user_id, usual_mobility, consents) VALUES (%s, %s, %s)",
                     (uid, profile.get("mobility"), Jsonb(profile.get("consents", {}))))
    return uid


def journey(pool, jid, owner, *names, event_user=None, days_ago=1, **props):
    at = NOW - timedelta(days=days_ago)
    with pool.connection() as conn:
        conn.execute("INSERT INTO journeys (id, user_id, stage, revision, envelope, created_at, updated_at) "
                     "VALUES (%s, %s, 'trip', 0, '{}', %s, %s)", (jid, owner, at, at))
        for i, name in enumerate(names):
            conn.execute("INSERT INTO events (at, user_id, journey_id, source, name, props) VALUES (%s, %s, %s, 'server', "
                         "%s, %s)", (at + timedelta(minutes=i), event_user, jid, name, Jsonb(props.get(name, {}))))


def test_people_follow_the_journey_owner_and_climb_the_ladder(pool):
    full = ("journey.create", "trip.turn", "decision.act.select", "planning.confirm", "feedback.submit")
    a = user(pool, "a@gmail.com", mobility="car")
    b = user(pool, "b@gmail.com")
    user(pool, "walker@test.local")  # test sign-in: left out unless test=1
    user(pool, None, kind="guest")
    # a's first trip was made as a guest (events carry no user), then adopted; a second trip on another day.
    journey(pool, "aaaaaaaaaaa1", a, *full, **{"trip.turn": {"compiled": True}})
    journey(pool, "aaaaaaaaaaa2", a, "journey.create", "trip.turn", event_user=a, days_ago=2,
            **{"trip.turn": {"error": "Conflict"}})
    with pool.connection() as conn:
        conn.execute("INSERT INTO feedback (journey_id, scores) VALUES ('aaaaaaaaaaa1', %s)", (Jsonb({"fit": 2}),))
        conn.execute("INSERT INTO events (user_id, source, name) VALUES (NULL, 'server', 'auth.guest')")
    out = analytics.users_overview(pool, {})
    k = out["kpis"]
    assert (k["accounts"]["n"], k["active_accounts"]["n"], k["with_errors"]["n"]) == (2, 1, 1)
    assert k["journeys"]["n"] == 2 and k["confirmed"]["n"] == 1 and k["guest_sessions"]["n"] == 1
    ladder = {s["key"]: s["n"] for s in out["ladder"]}
    assert ladder == {"signup": 2, "journey": 1, "compiled": 1, "chose": 1, "confirm": 1, "feedback": 1, "again": 1}
    assert next(s for s in out["ladder"] if s["key"] == "again")["kept"] == 1.0
    gaps = out["gaps"]
    assert gaps["never_journey"] == {"n": 1, "of": 2} and gaps["low_feedback"] == {"n": 1, "of": 1}
    assert gaps["no_prior"] == {"n": 1, "of": 2}
    assert "Google Calendar" in gaps["unused"] and "Chốt lịch" not in gaps["unused"]
    assert out["cohorts"][-1]["size"] == 2 and out["cohorts"][-1]["cells"][0] == 0.5

    rows = {r["email"]: r for r in analytics.users_list(pool, {})}
    assert set(rows) == {"a@gmail.com", "b@gmail.com", None}
    assert rows["a@gmail.com"]["journeys"] == 2 and rows["a@gmail.com"]["furthest"] == 6
    assert rows["b@gmail.com"]["furthest"] == 0 and rows[None]["type"] == "guest"
    assert "walker@test.local" in {r["email"] for r in analytics.users_list(pool, {"test": "1"})}

    one = analytics.user(pool, a.hex)
    assert one["reached"][-1] == "again" and len(one["journey_list"]) == 2 and one["feedback_list"][0]["scores"] == {"fit": 2}
    assert next(f for f in one["features"] if f["key"] == "confirm")["uses"] == 1
    with pytest.raises(KeyError):
        analytics.user(pool, "0" * 32)
