"""ops/nt548/canary_watch.py on fake nginx access logs: good new color promotes, 500s or slowness roll back."""

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("canary_watch", Path(__file__).resolve().parents[2] / "ops/nt548/canary_watch.py")
cw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cw  # dataclasses look their module up there
spec.loader.exec_module(cw)

CFG = cw.load_config(Path(cw.HERE / "canary.yaml"))
T0 = 1_764_150_000.0  # epoch s


def write_log(path, n_old=200, n_new=60, new_5xx=0.0, new_ms=5.0, old_ms=5.0, seed=0, t0=T0):
    """nginx JSON lines: n_old on blue and n_new on green, mixed, 10 ms apart from t0; one broken line."""
    rng = random.Random(seed)
    colors = ["blue"] * n_old + ["green"] * n_new
    rng.shuffle(colors)
    rows = []
    for i, color in enumerate(colors):
        bad = color == "green" and rng.random() < new_5xx
        ms = (new_ms if color == "green" else old_ms) * rng.uniform(0.8, 1.2)
        rows.append(json.dumps({"t": "x", "msec": t0 + i * 0.01, "color": color, "status": 500 if bad else 200,
                                "ms": ms / 1000, "up": "h:8081", "up_status": "200", "method": "GET", "path": "/"}))
    rows.insert(3, "not json")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def check(log, **kw):
    return cw.evaluate(log, "blue", "green", CFG, kw.get("since", 0))


def test_config_has_the_guide_thresholds():
    assert CFG["min_requests"] == 50 and CFG["max_5xx_ratio"] == 0.02 and CFG["steps"] == [10, 50, 100]


def test_flat_parser_matches_yaml(monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", None)  # import yaml -> ImportError
    assert cw.load_config(cw.HERE / "canary.yaml") == CFG


def test_good_new_color_promotes(tmp_path):
    res = check(write_log(tmp_path / "a.log"))
    assert res["decision"] == "promote" and res["new"]["n"] >= 50 and res["old"]["n"] >= 50


def test_many_500s_roll_back(tmp_path):
    res = check(write_log(tmp_path / "a.log", new_5xx=0.3))
    assert res["decision"] == "rollback" and "5xx" in res["reason"] and res["old"]["n5xx"] == 0


def test_few_requests_wait(tmp_path):
    res = check(write_log(tmp_path / "a.log", n_new=10))
    assert res["decision"] == "wait"
    assert cw.EXIT[res["decision"]] == 2


def test_slow_new_color_rolls_back_on_p95(tmp_path):
    res = check(write_log(tmp_path / "a.log", new_ms=900, old_ms=20))
    assert res["decision"] == "rollback" and "p95" in res["reason"]


def test_small_slowdown_on_a_fast_stub_is_noise(tmp_path):
    assert check(write_log(tmp_path / "a.log", new_ms=6, old_ms=2))["decision"] == "promote"


def test_since_ignores_older_requests(tmp_path):
    log = write_log(tmp_path / "a.log", new_5xx=1.0)
    assert check(log, since=(T0 + 1000) * 1000)["decision"] == "wait"


@pytest.mark.parametrize("new_5xx, code, calls", [
    (0.0, 0, [("weight", "10"), ("weight", "50"), ("weight", "100"), ("promote",)]),
    (0.5, 1, [("weight", "10"), ("rollback",)]),
])
def test_run_walks_the_steps(tmp_path, monkeypatch, new_5xx, code, calls):
    monkeypatch.setenv("NT548_STATE", str(tmp_path))
    log = tmp_path / "access.log"
    done = []
    def sh(*args):
        done.append(args)
        if args[0] == "weight":  # traffic of this step lands after its start
            write_log(log, new_5xx=new_5xx, t0=T0 + 100 * len(done))

    rc, history = cw.run(CFG, log, sleep=lambda s: None, clock=lambda: T0 + 100 * len(done) - 1, sh=sh)
    assert rc == code and done == calls
    assert history[-1]["decision"] == ("promote" if code == 0 else "rollback")


def test_run_rolls_back_without_traffic(tmp_path, monkeypatch):
    monkeypatch.setenv("NT548_STATE", str(tmp_path))
    log = tmp_path / "access.log"
    log.write_text("")
    done = []
    rc, history = cw.run({**CFG, "max_wait_seconds": 10}, log, poll=5, sleep=lambda s: None, clock=lambda: T0,
                         sh=lambda *a: done.append(a))
    assert rc == 1 and done == [("weight", "10"), ("rollback",)] and "not enough traffic" in history[0]["reason"]


# ---------- AWS: CloudWatch source (#29) ----------

class FakeCloudWatch:
    """get_metric_data stand-in: per target group, per-minute RequestCount / 5xx sums and p95 seconds."""

    def __init__(self, series):
        self.series, self.calls = series, []

    def get_metric_data(self, MetricDataQueries, StartTime, EndTime):
        self.calls.append((MetricDataQueries, StartTime, EndTime))
        tg = MetricDataQueries[0]["MetricStat"]["Metric"]["Dimensions"][1]["Value"]
        n, e, p = self.series[tg]
        return {"MetricDataResults": [{"Id": "n", "Values": n}, {"Id": "e", "Values": e}, {"Id": "p", "Values": p}]}


def test_cloudwatch_stats_sums_counts_and_takes_the_worst_minute_p95():
    fake = FakeCloudWatch({"targetgroup/g/2": ([40, 60], [1, 2], [0.020, 0.050])})
    s = cw.cloudwatch_stats(fake, "app/alb/1", "targetgroup/g/2", T0, T0 + 120)
    assert (s.n, s.n5xx, s.p95_ms) == (100, 3, 50.0)
    q = fake.calls[0][0]
    assert {x["MetricStat"]["Metric"]["MetricName"] for x in q} == {"RequestCount", "HTTPCode_Target_5XX_Count",
                                                                    "TargetResponseTime"}
    assert q[0]["MetricStat"]["Metric"]["Dimensions"][0] == {"Name": "LoadBalancer", "Value": "app/alb/1"}


def test_cloudwatch_stats_without_data():
    s = cw.cloudwatch_stats(FakeCloudWatch({"tg": ([], [], [])}), "lb", "tg", T0, T0 + 60)
    assert (s.n, s.n5xx, s.p95_ms) == (0, 0, None)


def watch(stats, cfg=None, **kw):
    slept = []
    code, res = cw.watch_cloudwatch({**CFG, "step_seconds": 300, "max_wait_seconds": 60, **(cfg or {})},
                                    lambda tg, s, e: stats[tg], "old", "new", poll=30, sleep=slept.append,
                                    clock=lambda: T0, **kw)
    return code, res, slept


def test_cloudwatch_watch_promotes_a_good_canary():
    code, res, slept = watch({"old": cw.Stats(900, 1, 40.0), "new": cw.Stats(100, 0, 45.0)})
    assert code == 0 and res["decision"] == "promote" and slept == [300]


def test_cloudwatch_watch_rolls_back_on_5xx():
    code, res, _ = watch({"old": cw.Stats(900, 0, 40.0), "new": cw.Stats(100, 30, 45.0)})
    assert code == 1 and "5xx" in res["reason"]


def test_cloudwatch_watch_rolls_back_when_traffic_never_comes():
    code, res, slept = watch({"old": cw.Stats(900, 0, 40.0), "new": cw.Stats(3, 0, 45.0)})
    assert code == 1 and res["reason"].startswith("not enough traffic")
    assert slept == [300, 30, 30]  # the step, then polls until max_wait_seconds
