"""ops/nt548/data_check.py: sample releases pass; a changed artifact, a 20 % place drop, a place without coordinates
and a missing manifest are refused, each with its reason."""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("lancedb")

OPS = Path(__file__).resolve().parents[2] / "ops/nt548"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


make = _load("sample_make", OPS / "sample-data/make.py")
data_check = _load("data_check", OPS / "data_check.py")


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    out = tmp_path_factory.mktemp("sample")
    make.build(out, seed=548, count=20, broken=True)
    return out


def statuses(report):
    return {r["check"]: r["status"] for r in report.results}


def reason(report, check):
    return next(r["reason"] for r in report.results if r["check"] == check)


def test_sample_releases_pass(sample):
    for alias in ("r-a", "r-b"):
        report = data_check.check(sample / alias, baseline=sample / "r-a")
        assert not report.failed, report.as_dict()
        assert set(statuses(report).values()) == {"pass"}


def test_changed_artifact_is_refused_and_later_checks_skip(sample, tmp_path):
    broken = tmp_path / "r-b"
    shutil.copytree(sample / "r-b", broken)
    places = next((data_check.release_dir(broken) / "serving").glob("places.json"))
    places.write_bytes(places.read_bytes() + b" ")
    report = data_check.check(broken, baseline=sample / "r-a")
    assert report.failed and statuses(report)["hashes"] == "fail"
    assert "serving/places.json: sha256 mismatch" in reason(report, "hashes")
    assert statuses(report)["drop"] == "skip"


def test_twenty_percent_drop_is_refused(sample):
    report = data_check.check(sample / "r-b-drop", baseline=sample / "r-a")
    assert report.failed and statuses(report)["drop"] == "fail"
    assert "20 -> 16 places (20% drop" in reason(report, "drop")
    assert statuses(report)["hashes"] == "pass"  # the release itself is intact; only the gate refuses it


def test_place_without_coordinates_is_refused(sample):
    report = data_check.check(sample / "r-b-nocoords", baseline=sample / "r-a")
    assert report.failed and statuses(report)["schema"] == "fail"
    assert "identity.lat" in reason(report, "schema")


def test_missing_manifest_and_cli_exit_codes(sample, tmp_path):
    report = data_check.check(tmp_path)
    assert report.failed and statuses(report) == {"manifest": "fail"}
    assert data_check.main([str(sample / "r-a")]) == 0
    assert data_check.main([str(sample / "r-b-drop"), "--baseline", str(sample / "r-a")]) == 1
