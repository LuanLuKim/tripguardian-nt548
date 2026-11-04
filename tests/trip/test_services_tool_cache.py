"""Service snapshots avoid repeated detail reads without losing source updates or ordering."""

import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest

from corpus import service_places
from trip.agent import services_tool as tool
from trip.domain.state import TripState


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    root = tmp_path / "gmaps"
    listing = root / "list" / "dalat_svc.json"
    details = root / "services" / "places"
    listing.parent.mkdir(parents=True)
    details.mkdir(parents=True)
    rows = [
        {"fid": "p:1", "name": "Pharmacy A", "lat": 11.94, "lng": 108.43, "group": "utilities",
         "queries": ["hiệu thuốc Đà Lạt"], "category": "Hiệu thuốc", "rating": 4.5, "reviews": 20},
        {"fid": "p:2", "name": "Pharmacy B", "lat": 11.94, "lng": 108.43, "group": "utilities",
         "queries": ["hiệu thuốc Đà Lạt"], "category": "Hiệu thuốc", "rating": 4.5, "reviews": 20},
        {"fid": "a:1", "name": "ATM", "lat": 11.95, "lng": 108.44, "group": "utilities",
         "queries": ["ATM Đà Lạt"], "category": "ATM"},
        {"fid": "r:1", "name": "Repair", "lat": 11.96, "lng": 108.45, "group": "rental_tour",
         "queries": ["thuê ô tô Đà Lạt"], "category": "Xưởng sửa chữa ô tô"},
    ]
    listing.write_text(json.dumps({"items": rows}), encoding="utf-8")
    for i, row in enumerate(rows):
        (details / (row["fid"].replace(":", "_") + ".json")).write_text(json.dumps({
            "phone": f"100{i}", "hours": ["22:00–24:00"], "fetched_at": "2026-11-04",
        }), encoding="utf-8")
    return SimpleNamespace(listing=listing, details=details, rows=rows)


@pytest.fixture
def reads(monkeypatch):
    counts = Counter()
    read = Path.read_text

    def counted(path, *args, **kwargs):
        if "gmaps" in path.parts:
            counts[path.name] += 1
        return read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    return counts


def query(kind="hiệu thuốc"):
    return tool.find_services(SimpleNamespace(state=TripState()), tool.FindServices(kind=kind, limit=10))


def test_second_query_does_not_reread_files_and_filters_group_before_details(source, reads):
    first = query()
    assert [r["name"] for r in first["rows"]] == ["Pharmacy A", "Pharmacy B"]
    assert reads["r_1.json"] == 0
    reads.clear()
    assert query() == first
    assert sum(reads.values()) == 0


def test_cross_group_queries_do_not_lose_places_or_stable_order(source):
    source.rows[-1]["queries"].append("hiệu thuốc Đà Lạt")
    source.listing.write_text(json.dumps({"items": source.rows}), encoding="utf-8")
    assert [r["name"] for r in query()["rows"]] == ["Pharmacy A", "Pharmacy B", "Repair"]


def test_concurrent_queries_single_flight_the_snapshot(source, reads):
    barrier = Barrier(6)

    def one(_):
        barrier.wait()
        return query()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, range(6)))
    assert all(r == results[0] for r in results)
    assert reads["dalat_svc.json"] == 2  # Metadata prefilter plus the public loader, once per flight.
    assert reads["p_1.json"] == 1


def test_list_version_changes_and_cached_results_are_not_mutable(source):
    first = query()
    first["rows"][0]["hours"].append("invented")
    assert query()["rows"][0]["hours"] == ["22:00–24:00"]
    before = source.listing.stat()
    source.rows.reverse()
    source.listing.write_text(json.dumps({"items": source.rows}), encoding="utf-8")
    # Same-size rewrites on NFS can share a timestamp; explicitly publish a new version.
    os.utime(source.listing, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
    assert [r["name"] for r in query()["rows"]] == ["Pharmacy B", "Pharmacy A"]


def test_detail_update_deletion_and_creation_invalidate_snapshot(source):
    assert query()["rows"][0]["phone"] == "1000"
    detail = source.details / "p_1.json"
    before = detail.stat()
    detail.write_text(json.dumps({"phone": "new phone", "fetched_at": "2026-11-05"}), encoding="utf-8")
    os.utime(detail, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
    out = query()
    assert out["rows"][0]["phone"] == "new phone" and out["crawled"] == "2026-11-05"
    detail.unlink()
    assert query()["rows"][0]["phone"] == "unknown"
    detail.write_text(json.dumps({"phone": "returned"}), encoding="utf-8")
    assert query()["rows"][0]["phone"] == "returned"


@pytest.mark.parametrize("kind", [*tool.KINDS, *tool.GROUPS])
def test_snapshot_results_equal_uncached_public_loader(source, monkeypatch, kind):
    # Compare the entire payload, including ties, evidence, unknowns and category-only repairs.
    actual = query(kind)
    with monkeypatch.context() as m:
        m.setattr(tool, "service_places", service_places)
        # The reference loader is called through the original find_services row-provider seam.
        m.setattr(tool, "_service_rows", lambda words: [
            (r, w) for r in service_places("dalat")
            if (w := next((w for w in words if tool._matches(r, w)), None))
        ], raising=False)
        expected = query(kind)
    assert actual == expected
