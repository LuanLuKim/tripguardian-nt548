"""Automated canary for the blue/green stack (#3, docs/nt548/03-canary-scale.md).

Reads the JSON access log of nginx (ops/nt548/lb/nginx.conf), compares the new color with the old one over the same
window and decides: promote, rollback, or wait for more requests. Thresholds in ops/nt548/canary.yaml.

    python ops/nt548/canary_watch.py check --since 1764150000000            # one decision, JSON; exit 0 / 1 / 2
    python ops/nt548/canary_watch.py run                                     # drive deploy.sh through the steps
    python ops/nt548/canary_watch.py --step-seconds 300 cloudwatch --lb app/x/1 --old-tg targetgroup/b/1 \
        --new-tg targetgroup/g/2                                             # AWS: one step on ALB metrics (#29)

`run` sets each step's weight (deploy.sh weight), watches it, and at the end promotes (exit 0) or rolls back as soon
as a step fails (exit 1). Not enough traffic after max_wait_seconds rolls back too: no data is no proof.
Exit codes of `check`: 0 promote (new is as good as old), 1 rollback, 2 wait (fewer than min_requests on a color).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULTS = {"min_requests": 50, "max_5xx_ratio": 0.02, "max_5xx_vs_old": 2.0, "max_p95_vs_old": 1.5,
            "min_p95_gap_ms": 100, "steps": [10, 50, 100], "step_seconds": 120, "max_wait_seconds": 120}
EXIT = {"promote": 0, "rollback": 1, "wait": 2}


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        data = yaml.safe_load(text) or {}
    except ImportError:  # a flat `key: value  # comment` file needs no PyYAML (runner's system python)
        data = {}
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" in line:
                k, v = (x.strip() for x in line.split(":", 1))
                data[k] = json.loads(v)
    return {**DEFAULTS, **data}


@dataclass
class Stats:
    n: int = 0
    n5xx: int = 0
    p95_ms: float | None = None

    @property
    def ratio(self) -> float:
        return self.n5xx / self.n if self.n else 0.0


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, math.ceil(0.95 * len(v)) - 1)]


def read(log: Path, since_ms: float = 0, until_ms: float = math.inf) -> dict[str, Stats]:
    """Per-color stats of the requests in [since, until) from nginx's JSON lines; bad lines are skipped."""
    ms: dict[str, list[float]] = {}
    out: dict[str, Stats] = {}
    with log.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                r = json.loads(line)
                t, color, status = float(r["msec"]) * 1000, r["color"], int(r["status"])
            except (ValueError, KeyError, TypeError):
                continue
            if not (since_ms <= t < until_ms) or not color:
                continue
            s = out.setdefault(color, Stats())
            s.n += 1
            s.n5xx += 500 <= status <= 599
            ms.setdefault(color, []).append(float(r.get("ms") or 0) * 1000)
    for color, s in out.items():
        s.p95_ms = p95(ms[color])
    return out


def decide(old: Stats, new: Stats, cfg: dict) -> tuple[str, str]:
    if old.n < cfg["min_requests"] or new.n < cfg["min_requests"]:
        return "wait", f"{new.n} requests on the new color, {old.n} on the old one, need {cfg['min_requests']} each"
    if new.ratio > cfg["max_5xx_ratio"] and new.ratio > cfg["max_5xx_vs_old"] * old.ratio:
        return "rollback", (f"5xx {new.ratio:.1%} on the new color against {old.ratio:.1%} on the old one "
                            f"(limit {cfg['max_5xx_ratio']:.0%} and {cfg['max_5xx_vs_old']}x old)")
    if (new.p95_ms is not None and old.p95_ms is not None and new.p95_ms > cfg["max_p95_vs_old"] * old.p95_ms
            and new.p95_ms - old.p95_ms >= cfg["min_p95_gap_ms"]):
        return "rollback", (f"p95 {new.p95_ms:.0f} ms on the new color against {old.p95_ms:.0f} ms "
                            f"(limit {cfg['max_p95_vs_old']}x old and +{cfg['min_p95_gap_ms']} ms)")
    return "promote", f"5xx {new.ratio:.1%} vs {old.ratio:.1%}, p95 {new.p95_ms:.0f} vs {old.p95_ms:.0f} ms"


def evaluate(log: Path, old: str, new: str, cfg: dict, since_ms: float, until_ms: float = math.inf) -> dict:
    stats = read(log, since_ms, until_ms)
    o, n = stats.get(old, Stats()), stats.get(new, Stats())
    decision, reason = decide(o, n, cfg)
    return {"decision": decision, "reason": reason, "old": {"color": old, **asdict(o), "ratio": round(o.ratio, 4)},
            "new": {"color": new, **asdict(n), "ratio": round(n.ratio, 4)}}


# ---------- AWS: the same decision on the ALB's CloudWatch metrics (ops/nt548/deploy_aws.sh, #29) ----------

def cloudwatch_stats(cw, lb: str, tg: str, start: float, end: float, period: int = 60) -> Stats:
    """Stats of one target group over [start, end) (epoch s) from AWS/ApplicationELB: requests, target 5xx, p95."""
    dims = [{"Name": "LoadBalancer", "Value": lb}, {"Name": "TargetGroup", "Value": tg}]

    def q(qid: str, metric: str, stat: str) -> dict:
        return {"Id": qid, "ReturnData": True, "MetricStat": {
            "Metric": {"Namespace": "AWS/ApplicationELB", "MetricName": metric, "Dimensions": dims},
            "Period": period, "Stat": stat}}

    from datetime import datetime, timezone
    res = cw.get_metric_data(
        MetricDataQueries=[q("n", "RequestCount", "Sum"), q("e", "HTTPCode_Target_5XX_Count", "Sum"),
                           q("p", "TargetResponseTime", "p95")],
        StartTime=datetime.fromtimestamp(start, timezone.utc), EndTime=datetime.fromtimestamp(end, timezone.utc))
    values = {r["Id"]: r.get("Values", []) for r in res.get("MetricDataResults", [])}
    p = values.get("p", [])
    # p95 per minute -> the worst minute of the window (a conservative p95 of the whole window)
    return Stats(n=int(sum(values.get("n", []))), n5xx=int(sum(values.get("e", []))),
                 p95_ms=max(p) * 1000 if p else None)


def watch_cloudwatch(cfg: dict, fetch, old_tg: str, new_tg: str, poll: float = 30.0, sleep=time.sleep,
                     clock=time.time) -> tuple[int, dict]:
    """Watch the new target group for step_seconds, then decide against the old one over the same window; wait up to
    max_wait_seconds for min_requests, and roll back when they never come (no data is no proof).
    fetch(tg, start, end) -> Stats. Returns (exit code, result) with 0 = promote, 1 = roll back."""
    start = clock()
    sleep(cfg["step_seconds"])
    waited = 0.0
    while True:
        end = clock() + 60  # the minute in progress
        o, n = fetch(old_tg, start, end), fetch(new_tg, start, end)
        decision, reason = decide(o, n, cfg)
        if decision != "wait" or waited >= cfg["max_wait_seconds"]:
            break
        sleep(poll)
        waited += poll
    if decision == "wait":
        decision, reason = "rollback", "not enough traffic: " + reason
    res = {"decision": decision, "reason": reason, "old": {"tg": old_tg, **asdict(o), "ratio": round(o.ratio, 4)},
           "new": {"tg": new_tg, **asdict(n), "ratio": round(n.ratio, 4)}}
    return EXIT[decision], res


def state_dir() -> Path:
    return Path(os.environ.get("NT548_STATE", HERE / "state"))


def colors() -> tuple[str, str]:
    active = (state_dir() / "active").read_text().strip() if (state_dir() / "active").exists() else "blue"
    return active, "green" if active == "blue" else "blue"


def deploy(*args: str) -> None:
    subprocess.run(["bash", str(HERE / "deploy.sh"), *args], check=True)


def run(cfg: dict, log: Path, poll: float = 5.0, sleep=time.sleep, clock=time.time, sh=deploy) -> tuple[int, list]:
    old, new = colors()
    history = []
    for pct in cfg["steps"]:
        if pct >= 100:
            break
        sh("weight", str(pct))
        start = clock() * 1000
        sleep(cfg["step_seconds"])
        waited = 0.0
        while True:
            res = evaluate(log, old, new, cfg, start)
            if res["decision"] != "wait" or waited >= cfg["max_wait_seconds"]:
                break
            sleep(poll)
            waited += poll
        if res["decision"] == "wait":
            res = {**res, "decision": "rollback", "reason": "not enough traffic: " + res["reason"]}
        history.append({"weight": pct, **res})
        print(json.dumps(history[-1]), flush=True)
        if res["decision"] == "rollback":
            sh("rollback")
            return 1, history
    sh("weight", "100")
    sh("promote")
    return 0, history


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=HERE / "canary.yaml")
    ap.add_argument("--log", type=Path, help="nginx JSON access log (default $NT548_STATE/log/access.log)")
    ap.add_argument("--step-seconds", type=float, help="override step_seconds (CI)")
    ap.add_argument("--max-wait-seconds", type=float, help="override max_wait_seconds (CI)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="one decision over the requests since --since")
    c.add_argument("--since", type=float, default=0, help="epoch ms (default: the whole log)")
    c.add_argument("--old")
    c.add_argument("--new")
    r = sub.add_parser("run", help="weight steps, then promote or roll back")
    r.add_argument("--out", type=Path, help="JSON history of the steps")
    w = sub.add_parser("cloudwatch", help="AWS: watch one canary step on the ALB metrics (deploy_aws.sh sets weights)")
    w.add_argument("--lb", required=True, help="ALB arn suffix (app/<name>/<id>)")
    w.add_argument("--old-tg", required=True, help="target group arn suffix of the live color")
    w.add_argument("--new-tg", required=True, help="target group arn suffix of the canary color")
    w.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    a = ap.parse_args(argv)

    cfg = load_config(a.config)
    for key in ("step_seconds", "max_wait_seconds"):
        if getattr(a, key) is not None:
            cfg[key] = getattr(a, key)
    if a.cmd == "cloudwatch":
        import boto3
        cw = boto3.client("cloudwatch", region_name=a.region)
        code, res = watch_cloudwatch(cfg, lambda tg, s, e: cloudwatch_stats(cw, a.lb, tg, s, e), a.old_tg, a.new_tg)
        print(json.dumps(res))
        return code
    log = a.log or state_dir() / "log" / "access.log"
    if a.cmd == "check":
        active, other = colors()
        res = evaluate(log, a.old or active, a.new or other, cfg, a.since)
        print(json.dumps(res))
        return EXIT[res["decision"]]
    code, history = run(cfg, log)
    print(json.dumps({"result": "promoted" if code == 0 else "rolled back", "steps": len(history)}))
    if a.out:
        a.out.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
