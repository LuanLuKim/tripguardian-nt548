"""ops/nt548/eval_gate.py against fake LLMs: a good version passes, one failing 30 % or breaking JSON is gated."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("yaml")
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


fake = load("llm_fake", "ops/nt548/llm_fake/server.py")
gate = load("eval_gate", "ops/nt548/eval_gate.py")


def fake_client(**settings):
    return TestClient(fake.create_app(fake.Settings(seed=7, **settings)))


def test_valid_text_and_json():
    assert gate.valid("hello", False) and not gate.valid("  ", False)
    assert gate.valid(json.dumps({"answer": "x"}), True)
    assert not gate.valid('{"answer": "x"', True) and not gate.valid('["x"]', True) and not gate.valid("text", True)


def test_good_v1_passes_and_v2_with_30_percent_errors_is_gated(tmp_path):
    out = tmp_path / "v.json"
    rc = gate.main(["--gate", "v2", "--out", str(out)],
                   clients={"v1": fake_client(version="v1"), "v2": fake_client(version="v2", error_rate=0.3)})
    v = json.loads(out.read_text())
    assert rc == 1 and v["v1"]["pass"] and not v["v2"]["pass"]
    assert 0.15 <= v["v2"]["errors"] <= 0.45 and any("errors" in w for w in v["v2"]["why"])


def test_broken_json_is_gated():
    assert gate.main(["--gate", "v2"], clients={"v2": fake_client(version="v2", bad_json_rate=0.5)}) == 1


def test_a_good_v2_passes():
    assert gate.main(["--gate", "v2"], clients={"v2": fake_client(version="v2")}) == 0
