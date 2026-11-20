import psycopg
import pytest

from db import migrate

pytestmark = pytest.mark.pg


def test_migrate_is_idempotent_and_creates_every_table(pg_url):
    assert migrate(pg_url) == []
    assert migrate(pg_url) == []
    with psycopg.connect(pg_url) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")}
    assert {"users", "auth_sessions", "profiles", "calendar_links", "journeys", "feedback", "events", "trips",
            "trip_stops", "checkins", "calendar_events", "calendar_sync", "push_subscriptions",
            "notification_prefs", "notifications", "schema_migrations"} <= tables


def test_migrate_applies_new_files_once(pg_url, tmp_path):
    (tmp_path / "001_a.sql").write_text("CREATE TABLE extra_a (x int);")
    assert migrate(pg_url, tmp_path) == ["001_a"]
    (tmp_path / "002_b.sql").write_text("CREATE TABLE extra_b (x int);")
    assert migrate(pg_url, tmp_path) == ["002_b"]
    assert migrate(pg_url, tmp_path) == []


def test_failed_migration_records_nothing(pg_url, tmp_path):
    (tmp_path / "001_bad.sql").write_text("CREATE TABLE half (x int); SELECT no_such_function();")
    with pytest.raises(psycopg.Error):
        migrate(pg_url, tmp_path)
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("SELECT to_regclass('half')").fetchone()[0] is None
        assert not conn.execute("SELECT 1 FROM schema_migrations WHERE version = '001_bad'").fetchone()


def test_legacy_guests_become_guests_and_the_role_check_is_restored(pg_url):
    # Prod before 009: role check widened by hand, a pre-`kind` guest stored as role 'guest'.
    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute("ALTER TABLE users DROP CONSTRAINT users_role_check")
        conn.execute("ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('user', 'admin', 'guest'))")
        conn.execute("INSERT INTO users (role) VALUES ('guest')")
        conn.execute("INSERT INTO users (email, role) VALUES ('a@gmail.com', 'admin')")
        conn.execute("DELETE FROM schema_migrations WHERE version = '009_legacy_guests'")
    assert migrate(pg_url) == ["009_legacy_guests"]
    with psycopg.connect(pg_url, autocommit=True) as conn:
        rows = conn.execute("SELECT kind, role FROM users ORDER BY email NULLS FIRST").fetchall()
        assert rows == [("guest", "user"), ("user", "admin")]
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO users (role) VALUES ('guest')")
