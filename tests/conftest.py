import os
import uuid
from pathlib import Path

import pytest

SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "snapshot" / "current"


def pytest_runtest_setup(item):
    """Marker corpus: skipped without data/snapshot/current (pyproject markers); data/ is not in git."""
    if item.get_closest_marker("corpus") and not SNAPSHOT.exists():
        pytest.skip("no data/snapshot/current: python -m corpus snapshot")


@pytest.fixture
def pg_url():
    """A throwaway schema with every migration applied; skipped without TEST_DATABASE_URL (marker pg)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg
    from psycopg.conninfo import make_conninfo
    from db import migrate
    schema = "test_" + uuid.uuid4().hex[:12]
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {schema}")
    scoped = make_conninfo(url, options=f"-csearch_path={schema},public")
    migrate(scoped)
    yield scoped
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA {schema} CASCADE")
