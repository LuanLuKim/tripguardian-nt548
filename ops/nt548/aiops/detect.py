"""Metric anomaly detection for the NT548 stack (#36): static threshold vs EWMA z-score vs Isolation Forest (and either).

A series is evenly spaced points (one per `step_s` seconds, e.g. a CloudWatch period). Every detector learns what
normal is from the first `train` points only, then flags each later point; an alarm fires after `persist`
consecutive flagged points (CloudWatch's "M out of M datapoints"). Labelled series (synthetic, or a fault-injection
run of #39) are scored: how many points after the fault each detector fired (delay), how many faults it missed,
how many alarms fired with no fault (false alarms).

    python ops/nt548/aiops/detect.py synth spike --seed 1 --out spike.csv     # t,value,label
    python ops/nt548/aiops/detect.py run spike.csv                             # alarms of each detector
    python ops/nt548/aiops/detect.py compare --seeds 20                        # table over every synthetic scenario
    python ops/nt548/aiops/detect.py cloudwatch --metric TargetResponseTime --stat p95 \
        --dim TargetGroup=targetgroup/x/y --dim LoadBalancer=app/z/w --minutes 180 --out tg.csv

No AWS is needed except for `cloudwatch` (boto3 on the runner, credentials from LabInstanceProfile).
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCENARIOS = ("spike", "drift", "seasonal_spike", "level_shift", "quiet")


# ---------- series ----------

@dataclass
class Series:
    values: np.ndarray
    labels: np.ndarray | None = None  # 1 where a fault is active
    step_s: float = 60.0
    t0: float = 0.0

    def faults(self) -> list[tuple[int, int]]:
        """[start, end) index ranges where labels are 1."""
        return runs(self.labels) if self.labels is not None else []


def runs(flags: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, f in enumerate(np.asarray(flags).astype(bool)):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(flags)))
    return out


def synth(scenario: str, seed: int = 0, n: int = 720, period: int = 120, step_s: float = 60.0) -> Series:
    """A latency-like series (base 200, noise sd 10) with one labelled fault after the first third.

    spike: +150 for 5 points · drift: +0.5 per point for 200 points, then stays +100 (slow leak) · seasonal_spike: a cycle of
    amplitude 60 every `period` points plus a +120 spike at a trough · level_shift: +60 from then on · quiet: no fault.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario}; one of {', '.join(SCENARIOS)}")
    rng = np.random.default_rng(seed)
    i = np.arange(n)
    values = 200.0 + rng.normal(0.0, 10.0, n)
    labels = np.zeros(n, dtype=int)
    at = n // 3 + int(rng.integers(0, n // 6))
    if scenario == "spike":
        values[at:at + 5] += 150
        labels[at:at + 5] = 1
    elif scenario == "drift":
        ramp = np.clip(i - at, 0, 200) * 0.5
        values += ramp
        labels[at:] = 1
    elif scenario == "seasonal_spike":
        values += 60 * np.sin(2 * np.pi * i / period)
        at = (at // period) * period + int(period * 0.75)  # a trough: the spike stays under the cycle's peak
        values[at:at + 5] += 120
        labels[at:at + 5] = 1
    elif scenario == "level_shift":
        values[at:] += 60
        labels[at:] = 1
    return Series(np.maximum(values, 0.0), labels, step_s)


# ---------- detectors: flags[i] is True when point i looks anomalous ----------

def static_flags(values: np.ndarray, train: int, threshold: float | None = None, factor: float = 1.5) -> np.ndarray:
    """What an operator would set by hand: a fixed line, by default `factor` x the training max."""
    limit = threshold if threshold is not None else factor * float(np.max(values[:train]))
    flags = values > limit
    flags[:train] = False
    return flags


def ewma_flags(values: np.ndarray, train: int, alpha: float = 0.05, k: float = 4.0) -> np.ndarray:
    """EWMA mean and variance; a point is flagged when |x - mean| > k * sd. Flagged points do not update the
    estimates (a fault must not become the new normal while it lasts)."""
    mean = float(np.mean(values[:train]))
    var = float(np.var(values[:train])) or 1e-9
    flags = np.zeros(len(values), dtype=bool)
    for i in range(train, len(values)):
        x = float(values[i])
        if abs(x - mean) > k * math.sqrt(var):
            flags[i] = True
            continue
        d = x - mean
        mean += alpha * d
        var = (1 - alpha) * (var + alpha * d * d)
    return flags


def features(values: np.ndarray, period: int | None, window: int = 5) -> np.ndarray:
    """Per point: the value, its change, its gap to the trailing mean, and the phase of the cycle (when known)."""
    diff = np.diff(values, prepend=values[0])
    trail = np.convolve(values, np.ones(window) / window, mode="full")[:len(values)]
    trail[:window] = values[:window]
    cols = [values, diff, values - trail]
    if period:
        phase = 2 * np.pi * (np.arange(len(values)) % period) / period
        scale = float(np.std(values)) or 1.0
        cols += [np.sin(phase) * scale, np.cos(phase) * scale]
    return np.column_stack(cols)


def iforest_flags(values: np.ndarray, train: int, period: int | None = None, contamination: float = 0.01,
                  seed: int = 0) -> np.ndarray:
    """Isolation Forest fitted on the training points; later points scoring below the training cut are flagged."""
    from sklearn.ensemble import IsolationForest

    x = features(values, period)
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=seed).fit(x[:train])
    flags = model.predict(x) == -1
    flags[:train] = False
    return flags


def detect(series: Series, train: int, persist: int = 2, period: int | None = None,
           static_threshold: float | None = None, seed: int = 0) -> dict[str, np.ndarray]:
    """name -> alarm array (True from the `persist`-th consecutive flagged point while flags last)."""
    v = series.values.astype(float)
    flags = {
        "static": static_flags(v, train, static_threshold),
        "ewma": ewma_flags(v, train),
        "iforest": iforest_flags(v, train, period, seed=seed),
    }
    flags["combined"] = flags["ewma"] | flags["iforest"]  # either one: what the alarm of #38 listens to
    return {name: alarms(f, persist) for name, f in flags.items()}


def alarms(flags: np.ndarray, persist: int) -> np.ndarray:
    out = np.zeros(len(flags), dtype=bool)
    streak = 0
    for i, f in enumerate(flags):
        streak = streak + 1 if f else 0
        out[i] = streak >= persist
    return out


# ---------- scoring ----------

@dataclass
class Score:
    faults: int = 0
    detected: int = 0
    delays: list[int] | None = None  # points from fault start to first alarm, per detected fault
    false_alarms: int = 0  # alarm events that start outside every fault

    def __post_init__(self) -> None:
        self.delays = self.delays or []


def score(alarm: np.ndarray, faults: list[tuple[int, int]], grace: int = 10) -> Score:
    """A fault counts as detected if an alarm is on within it or `grace` points after it ends (CloudWatch periods
    lag). An alarm event that starts outside every fault (and its grace) is a false alarm."""
    s = Score(faults=len(faults))
    covered = np.zeros(len(alarm), dtype=bool)
    for a, b in faults:
        covered[a:min(b + grace, len(alarm))] = True
        hit = np.flatnonzero(alarm[a:min(b + grace, len(alarm))])
        if hit.size:
            s.detected += 1
            s.delays.append(int(hit[0]))
    s.false_alarms = sum(1 for a, _ in runs(alarm) if not covered[a])
    return s


def compare(seeds: int = 20, train: int = 200, persist: int = 2, period: int = 120) -> list[dict]:
    """One row per scenario x detector over `seeds` synthetic series."""
    rows = []
    for scenario in SCENARIOS:
        totals: dict[str, Score] = {}
        for seed in range(seeds):
            series = synth(scenario, seed, period=period)
            per = period if scenario == "seasonal_spike" else None
            for name, alarm in detect(series, train, persist, per, seed=seed).items():
                s = score(alarm, series.faults())
                t = totals.setdefault(name, Score())
                t.faults += s.faults
                t.detected += s.detected
                t.delays += s.delays
                t.false_alarms += s.false_alarms
        for name, t in totals.items():
            rows.append({
                "scenario": scenario, "detector": name, "faults": t.faults, "detected": t.detected,
                "median_delay": float(np.median(t.delays)) if t.delays else None,
                "false_alarms": t.false_alarms,
            })
    return rows


def table(rows: list[dict]) -> str:
    out = ["| scenario | detector | detected / faults | median delay (points) | false alarms |", "|---|---|---|---|---|"]
    for r in rows:
        delay = "-" if r["median_delay"] is None else f"{r['median_delay']:g}"
        out.append(f"| {r['scenario']} | {r['detector']} | {r['detected']} / {r['faults']} | {delay} | {r['false_alarms']} |")
    return "\n".join(out)


# ---------- I/O ----------

def read_csv(path: Path, step_s: float = 60.0) -> Series:
    """t,value[,label]: t in seconds (or any increasing number); only the order and the values are used."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or "value" not in rows[0]:
        raise ValueError(f"{path}: needs a header with at least t,value")
    values = np.array([float(r["value"]) for r in rows])
    labels = np.array([int(r["label"]) for r in rows]) if "label" in rows[0] and rows[0]["label"] != "" else None
    t0 = float(rows[0].get("t") or 0)
    return Series(values, labels, step_s, t0)


def write_csv(series: Series, path: Path | None) -> None:
    out = sys.stdout if path is None else path.open("w", newline="", encoding="utf-8")
    w = csv.writer(out)
    w.writerow(["t", "value", "label"] if series.labels is not None else ["t", "value"])
    for i, v in enumerate(series.values):
        t = series.t0 + i * series.step_s
        w.writerow([f"{t:g}", f"{v:.4f}"] + ([int(series.labels[i])] if series.labels is not None else []))
    if path is not None:
        out.close()


def cloudwatch(metric: str, dims: dict[str, str], minutes: int, stat: str = "Average", period: int = 60,
               namespace: str = "AWS/ApplicationELB") -> Series:
    """GetMetricData for the last `minutes`; missing periods become 0 (no request, no error)."""
    import datetime as dt

    import boto3

    end = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    start = end - dt.timedelta(minutes=minutes)
    query = {"Id": "m", "MetricStat": {"Metric": {"Namespace": namespace, "MetricName": metric,
                                                  "Dimensions": [{"Name": k, "Value": v} for k, v in dims.items()]},
                                       "Period": period, "Stat": stat}}
    got: dict[float, float] = {}
    for page in boto3.client("cloudwatch").get_paginator("get_metric_data").paginate(
            MetricDataQueries=[query], StartTime=start, EndTime=end, ScanBy="TimestampAscending"):
        for r in page["MetricDataResults"]:
            got.update({ts.timestamp(): v for ts, v in zip(r["Timestamps"], r["Values"])})
    t0 = start.timestamp()
    values = np.array([got.get(t0 + i * period, 0.0) for i in range(minutes * 60 // period)])
    return Series(values, None, float(period), t0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("synth", help="write a labelled synthetic series")
    s.add_argument("scenario", choices=SCENARIOS)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", type=Path)
    r = sub.add_parser("run", help="alarms of each detector on a CSV series (scored if it has labels)")
    r.add_argument("csv", type=Path)
    c = sub.add_parser("compare", help="markdown table over every synthetic scenario")
    c.add_argument("--seeds", type=int, default=20)
    w = sub.add_parser("cloudwatch", help="fetch a CloudWatch metric as CSV")
    w.add_argument("--metric", required=True)
    w.add_argument("--namespace", default="AWS/ApplicationELB")
    w.add_argument("--stat", default="Average", help="Average, Sum, p95, ...")
    w.add_argument("--dim", action="append", default=[], help="Name=Value, repeatable")
    w.add_argument("--minutes", type=int, default=180)
    w.add_argument("--period", type=int, default=60)
    w.add_argument("--out", type=Path)
    for sp in (r, c):
        sp.add_argument("--train", type=int, default=200, help="leading points taken as normal")
        sp.add_argument("--persist", type=int, default=2, help="consecutive flagged points before an alarm")
    r.add_argument("--period", type=int, help="cycle length in points, if the series has one")
    r.add_argument("--static", type=float, help="static threshold (default 1.5 x training max)")
    a = p.parse_args(argv)

    if a.cmd == "synth":
        write_csv(synth(a.scenario, a.seed), a.out)
    elif a.cmd == "cloudwatch":
        dims = dict(d.split("=", 1) for d in a.dim)
        write_csv(cloudwatch(a.metric, dims, a.minutes, a.stat, a.period, a.namespace), a.out)
    elif a.cmd == "compare":
        print(table(compare(a.seeds, a.train, a.persist)))
    else:
        series = read_csv(a.csv)
        if len(series.values) <= a.train:
            print(f"need more than --train {a.train} points, got {len(series.values)}", file=sys.stderr)
            return 2
        for name, alarm in detect(series, a.train, a.persist, a.period, a.static).items():
            events = runs(alarm)
            line = f"{name}: {len(events)} alarm(s)" + "".join(f" [{x},{y})" for x, y in events[:10])
            if series.labels is not None:
                sc = score(alarm, series.faults())
                line += f" · detected {sc.detected}/{sc.faults}, delays {sc.delays}, false alarms {sc.false_alarms}"
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
