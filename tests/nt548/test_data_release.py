"""ops/nt548/data_release.py stage: data_check gates the switch. A broken release never moves the pointer, the good one
does, rolling back passes the same gate, and --skip-check is the only way around it."""

import importlib.util
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
data_release = _load("data_release", OPS / "data_release.py")


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    out = tmp_path_factory.mktemp("sample")
    make.build(out, seed=548, count=20, broken=True)
    return out


def current(data):
    return (data / "releases" / "current").read_text(encoding="utf-8").strip()


def test_switch_and_rollback_pass_the_gate(sample, tmp_path):
    data = tmp_path / "green"
    a = data_release.stage(data, [], sample / "r-a")  # first release: nothing to compare with, checks still run
    b = data_release.stage(data, [], sample / "r-b")
    assert current(data) == b != a
    assert data_release.stage(data, [], sample / "r-a") == a and current(data) == a  # rollback
    assert {p.name for p in (data / "releases").iterdir() if p.is_dir()} == {a, b}


def test_broken_release_never_moves_the_pointer(sample, tmp_path, capsys):
    data = tmp_path / "green"
    a = data_release.stage(data, [], sample / "r-a")
    for bad, check in (("r-b-drop", "drop"), ("r-b-nocoords", "schema")):
        with pytest.raises(SystemExit, match=f"data_check refused .*; {data} still serves {a}"):
            data_release.stage(data, [], sample / bad)
        assert current(data) == a
        assert f"fail  {check}" in capsys.readouterr().out


def test_skip_check_is_the_explicit_way_around(sample, tmp_path, capsys):
    data = tmp_path / "green"
    data_release.stage(data, [], sample / "r-a")
    bad = data_release.stage(data, [], sample / "r-b-drop", check=False)
    assert current(data) == bad
    assert "WARNING: data_check skipped" in capsys.readouterr().out


def test_cli_exit_codes(sample, tmp_path):
    data = tmp_path / "blue"
    assert data_release.main(["stage", str(data), "--current", str(sample / "r-a")]) == 0
    with pytest.raises(SystemExit) as refused:
        data_release.main(["stage", str(data), "--current", str(sample / "r-b-drop")])
    assert "data_check refused" in str(refused.value.code)
