"""ops/nt548/sample-data/make.py: synthetic inputs are deterministic, both releases pass corpus' own validation."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("lancedb")

spec = importlib.util.spec_from_file_location("sample_make", Path(__file__).resolve().parents[2] / "ops/nt548/sample-data/make.py")
make = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = make
spec.loader.exec_module(make)


def test_same_seed_gives_same_inputs_other_seed_does_not(tmp_path):
    def digest(seed, name):
        root = tmp_path / name
        make.write_inputs(root, make.places(seed, 12)["r-a"], "v-test")
        return make.inputs_digest(root)
    assert digest(7, "a") == digest(7, "b")
    assert digest(7, "a") != digest(8, "c")


def test_r_b_differs_from_r_a_by_a_few_places():
    lists = make.places(548, 40)
    a, b = ({p["fid"] for p in lists[k]} for k in ("r-a", "r-b"))
    assert len(a) == 40 and len(a - b) == len(make.DROPPED) and len(b - a) == make.ADDED
    assert all("(mẫu" in p["name"] for p in lists["r-a"] + lists["r-b"])  # synthetic names are marked as such


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("sample")
    return out, make.build(out, seed=548, count=12)


def test_build_writes_two_valid_published_releases(built):
    from corpus.releases import resolve, validate
    from corpus.snapshot import Snapshot
    out, summary = built
    assert json.loads((out / "releases.json").read_text(encoding="utf-8")) == summary
    ids = {}
    for alias in ("r-a", "r-b"):
        release = resolve(out / alias)
        assert release.name == summary["releases"][alias]["release_id"]
        manifest = validate(release)
        ids[alias] = set(manifest["eligible_ids"])
        records = Snapshot.open(release / "snapshot").region("dalat").records()
        assert {r["id"] for r in records} == ids[alias]
        assert all(r["identity"]["name"] and r["identity"]["lat"] is not None for r in records)
    assert len(ids["r-a"]) == 12 and ids["r-a"] - ids["r-b"] and ids["r-b"] - ids["r-a"]


def test_harness_binds_to_each_release(built):
    from corpus.releases import bind, resolve_binding
    out, summary = built
    for alias in ("r-a", "r-b"):
        binding = bind(out / alias)
        assert binding.release_id == summary["releases"][alias]["release_id"] and binding.region == "dalat"
        assert resolve_binding(out / alias, binding).name == binding.release_id
