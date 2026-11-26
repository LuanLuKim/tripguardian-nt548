"""ops/nt548/aiops/fault_eval.py analyze on a synthetic run: a 5xx burst is detected, a quiet run stays quiet."""

import datetime as dt
import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

pytest.importorskip("sklearn")
pytest.importorskip("drain3")

spec = importlib.util.spec_from_file_location("fault_eval", Path(__file__).resolve().parents[2] / "ops/nt548/aiops/fault_eval.py")
fe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fe
spec.loader.exec_module(fe)

T0 = 1_764_150_000.0


def make_run(tmp_path, fault_rate=0.3, quiet=True, seed=0):
    rng = random.Random(seed)
    access, logs, scenarios = [], [], []
    t = T0

    def traffic(t_from, t_to, name, faulty):
        x = t_from
        while x < t_to:
            bad = faulty(x) and rng.random() < fault_rate
            ms = rng.uniform(2, 6) / 1000
            access.append(json.dumps({"msec": x, "color": "blue", "status": 502 if bad else 200, "ms": ms}))
            ts = dt.datetime.fromtimestamp(x, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "000Z"
            status = 502 if bad else 200
            logs.setdefault(name, []).append(
                f'harness-1  | {ts} harness-stub POST /api/harness/nt548-chat "POST /api/harness/nt548-chat HTTP/1.1" {status} -')
            x += 0.1

    logs = {}
    if quiet:
        traffic(t, t + 240, "quiet", lambda x: False)
        scenarios.append({"name": "quiet", "metric": "5xx", "t_start": t, "t_fault": t + 240, "t_recover": t + 240,
                          "t_recovered": t + 240, "t_end": t + 240, "recovered_by": "-"})
        t += 240
    tf = t + 90
    traffic(t, t + 180, "llm_errors", lambda x: tf <= x < tf + 60)
    scenarios.append({"name": "llm_errors", "metric": "5xx", "t_start": t, "t_fault": tf, "t_recover": tf + 60,
                      "t_recovered": tf + 62, "t_end": t + 180, "recovered_by": "script (manual)"})
    (tmp_path / "access.log").write_text("\n".join(access) + "\n", encoding="utf-8")
    for name, lines in logs.items():
        (tmp_path / f"{name}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "run.json").write_text(json.dumps({"scenarios": scenarios}), encoding="utf-8")
    return tmp_path


def test_series_buckets():
    req = fe.read_access(Path(__file__))  # not JSON: empty
    assert req.shape == (0, 3)
    import numpy as np
    req = np.array([[0.0, 200, 5], [1.0, 502, 7], [6.0, 500, 9], [7.0, 200, 100]])
    assert fe.series(req, 0, 10, "5xx").tolist() == [1, 1]
    assert fe.series(req, 0, 10, "requests").tolist() == [2, 2]
    assert fe.series(req, 0, 10, "p95")[1] > 90


def test_burst_is_detected_within_seconds_and_quiet_run_is_quiet(tmp_path):
    res = fe.analyze(make_run(tmp_path))
    row = res["scenarios"][0]
    assert row["name"] == "llm_errors" and row["user_5xx"] > 100
    for d in ("static", "ewma", "combined"):
        assert row["methods"][d]["mttd_s"] is not None and row["methods"][d]["mttd_s"] <= 15
    assert row["logs"]["mttd_s"] is not None and row["logs"]["mttd_s"] <= 15 and "502" in row["logs"]["top"]
    assert res["quiet"]["5xx"]["static"] == 0 and res["quiet"]["logs"] == 0
    md = fe.markdown(res)
    assert "llm_errors" in md and "reaction + 2 s" in md and "False alarms" in md


def test_auto_recovery_reports_the_measured_mttr():
    r = {"auto": True, "mttr_s": 23.4, "methods": {}, "logs": None, "recover_cmd_s": 1}
    assert fe.mttr(r) == "23.4 s (measured)"
    r = {"auto": False, "methods": {"ewma": {"mttd_s": None}}, "logs": None, "recover_cmd_s": 3}
    assert fe.mttr(r) == "not detected + reaction + 3 s"
