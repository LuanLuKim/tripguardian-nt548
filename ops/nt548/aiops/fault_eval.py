"""Fault injection and evaluation of the AIOps detectors on the Compose stack (#39, docs/nt548/04-aiops.md).

    python ops/nt548/aiops/fault_eval.py run --out run/                # stack + faults, ~20 min (CI: nt548-fault-eval)
    python ops/nt548/aiops/fault_eval.py analyze run/ --md table.md    # MTTD / MTTR / false alarms from a run

`run` keeps blue (2 replicas) behind nginx under steady traffic (lb_check.py load, a third of it a chat completion
through the model gateway), and for each scenario: a normal phase, the fault, the recovery. It writes run.json (the
times of each phase), nginx's access log and the container logs. `analyze` turns the access log into 5 s series
(5xx count, p95 latency, request count), runs the detectors of detect.py (#36) on the scenario's metric and the log
patterns of log_patterns.py (#37) on the container logs, and measures:
- MTTD: from the injection to the end of the first 5 s bucket where the method alarms;
- MTTR: from the injection to the recovery. `bad_deploy` is recovered by canary_watch.py on its own; the other faults
  are recovered by the script, as a person would after the alarm (MTTD + reaction + the command);
- false alarms: alarm events in a fault-free run (`quiet`), per hour.
CloudWatch Anomaly Detection needs the lab (ALB, #24): not in this table.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

AIOPS = Path(__file__).resolve().parent
NT548 = AIOPS.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, AIOPS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)  # dataclasses look their module up there
    spec.loader.exec_module(mod)
    return mod


detect = _load("detect")
STEP_S = 5.0
PERSIST = 2
DETECTORS = ("static", "ewma", "iforest", "combined")


# ---------- analysis ----------

def read_access(path: Path) -> np.ndarray:
    """nginx JSON lines -> array of (t in s, status, latency in ms)."""
    rows = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                r = json.loads(line)
                rows.append((float(r["msec"]), int(r["status"]), 1000 * float(r.get("ms") or 0)))
            except (ValueError, KeyError, TypeError):
                continue
    return np.array(rows, dtype=float).reshape(-1, 3)


def series(req: np.ndarray, t0: float, t1: float, metric: str, step: float = STEP_S) -> np.ndarray:
    """One value per `step` bucket of [t0, t1): `5xx` count, `p95` latency (ms) or `requests`."""
    n = max(1, int(math.ceil((t1 - t0) / step)))
    out = np.zeros(n)
    if not len(req):
        return out
    sel = req[(req[:, 0] >= t0) & (req[:, 0] < t1)]
    idx = ((sel[:, 0] - t0) // step).astype(int)
    for i in range(n):
        b = sel[idx == i]
        if metric == "5xx":
            out[i] = np.sum((b[:, 1] >= 500) & (b[:, 1] <= 599))
        elif metric == "requests":
            out[i] = len(b)
        elif metric == "p95":
            out[i] = float(np.percentile(b[:, 2], 95)) if len(b) else (out[i - 1] if i else 0.0)
        else:
            raise ValueError(f"unknown metric {metric}")
    return out


def first_alarm_s(alarm: np.ndarray, start: int, t0: float, t_fault: float, step: float = STEP_S) -> float | None:
    """Seconds from the injection to the end of the first alarmed bucket at or after `start`."""
    hit = np.flatnonzero(alarm[start:])
    return None if not hit.size else round(t0 + (start + hit[0] + 1) * step - t_fault, 1)


def metric_methods(req: np.ndarray, sc: dict, step: float = STEP_S) -> dict:
    """detector -> {mttd_s, false_alarms} on the scenario's metric. Training: the normal phase."""
    t0, tf, t1 = sc["t_start"], sc["t_fault"], sc["t_end"]
    v = series(req, t0, t1, sc["metric"], step)
    fault_i = int((tf - t0) // step)
    train = max(4, fault_i)
    alarms = detect.detect(detect.Series(v, None, step), train, PERSIST)
    out = {}
    for name in DETECTORS:
        a = alarms[name]
        out[name] = {"mttd_s": first_alarm_s(a, fault_i, t0, tf, step),
                     "false_alarms": sum(1 for s, _ in detect.runs(a[:fault_i]))}
    out["_series"] = v.tolist()
    return out


def quiet_methods(req: np.ndarray, sc: dict, metric: str, train_s: float = 90, step: float = STEP_S) -> dict:
    """detector -> alarm events after the first `train_s` of a fault-free run."""
    v = series(req, sc["t_start"], sc["t_end"], metric, step)
    train = max(4, int(train_s // step))
    alarms = detect.detect(detect.Series(v, None, step), train, PERSIST)
    return {name: sum(1 for _ in detect.runs(alarms[name][train:])) for name in DETECTORS}


def log_method(log: Path, sc: dict, window_min: float = 0.5, step: float = STEP_S) -> dict:
    """MTTD of the log patterns (#37): the first `at` after the injection where an ERROR template is new or spikes."""
    lp = _load("log_patterns")
    lines = lp.parse(log.read_text(encoding="utf-8", errors="replace").splitlines()) if log.exists() else []
    if not lines:
        return {"mttd_s": None, "false_alarms": None, "top": None}

    def alarm_at(at: float):
        import datetime as dt
        when = dt.datetime.fromtimestamp(at, dt.timezone.utc)
        hits = [p for p in lp.top(lines, when, window_min, limit=5) if p["anomaly"] and p["level"] == "ERROR"]
        return hits[0] if hits else None

    false = 0
    for at in np.arange(sc["t_start"] + 2 * 60 * window_min, sc["t_fault"], step):
        false += alarm_at(float(at)) is not None
    t = sc["t_fault"] + step
    while t <= sc["t_end"]:
        hit = alarm_at(t)
        if hit:
            return {"mttd_s": round(t - sc["t_fault"], 1), "false_alarms": false, "top": hit["pattern"]}
        t += step
    return {"mttd_s": None, "false_alarms": false, "top": None}


def analyze(run_dir: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    req = read_access(run_dir / "access.log")
    results = {"scenarios": [], "quiet": None, "machine": run.get("machine")}
    for sc in run["scenarios"]:
        if sc["name"] == "quiet":
            results["quiet"] = {"hours": round((sc["t_end"] - sc["t_start"]) / 3600, 3),
                                **{metric: quiet_methods(req, sc, metric) for metric in ("5xx", "p95", "requests")},
                                "logs": log_method(run_dir / "quiet.log", {**sc, "t_fault": sc["t_end"]})["false_alarms"]}
            continue
        m = metric_methods(req, sc)
        series_ = m.pop("_series")
        logs = log_method(run_dir / f"{sc['name']}.log", sc)
        t0, tf, tr = sc["t_start"], sc["t_fault"], sc["t_recover"]
        users_5xx = int(np.sum((req[:, 0] >= tf) & (req[:, 0] < sc["t_end"]) & (req[:, 1] >= 500))) if len(req) else 0
        row = {"name": sc["name"], "metric": sc["metric"], "methods": m, "logs": logs,
               "auto": sc["recovered_by"].endswith("(auto)"), "recover_cmd_s": round(sc["t_recovered"] - tr, 1),
               "mttr_s": round(tr - tf, 1), "recovered_by": sc["recovered_by"], "user_5xx": users_5xx,
               "normal": round(float(np.mean(series_[:max(1, int((tf - t0) // STEP_S))])), 1),
               "fault_peak": round(float(np.max(series_[int((tf - t0) // STEP_S):] or [0])), 1)}
        results["scenarios"].append(row)
    return results


def fmt(v) -> str:
    return "–" if v is None else f"{v:g}"


def mttr(r: dict) -> str:
    """Measured when canary_watch recovered on its own; otherwise MTTD + a person's reaction + the command."""
    if r["auto"]:
        return f"{fmt(r['mttr_s'])} s (measured)"
    best = [v["mttd_s"] for v in r["methods"].values() if v["mttd_s"] is not None]
    if r["logs"] and r["logs"]["mttd_s"] is not None:
        best.append(r["logs"]["mttd_s"])
    head = f"{fmt(min(best))} s" if best else "not detected"
    return f"{head} + reaction + {fmt(r['recover_cmd_s'])} s"


def markdown(res: dict) -> str:
    out = ["| Scenario | Metric | normal → peak | static | EWMA | Isolation Forest | log patterns | MTTR | recovered by | 5xx seen by users |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["scenarios"]:
        m = r["methods"]
        out.append(f"| {r['name']} | {r['metric']} | {fmt(r['normal'])} → {fmt(r['fault_peak'])} | "
                   + " | ".join(f"{fmt(m[d]['mttd_s'])} s" if m[d]["mttd_s"] is not None else "–"
                                for d in ("static", "ewma", "iforest"))
                   + f" | {fmt(r['logs']['mttd_s']) + ' s' if r['logs'] and r['logs']['mttd_s'] is not None else '–'}"
                   + f" | {mttr(r)} | {r['recovered_by']} | {r['user_5xx']} |")
    q = res.get("quiet")
    if q:
        out += ["", f"False alarms in {q['hours'] * 60:.0f} min of normal traffic (alarm events, persist {PERSIST} buckets of {STEP_S:g} s):", "",
                "| Metric | static | EWMA | Isolation Forest |", "|---|---|---|---|"]
        for metric in ("5xx", "p95", "requests"):
            out.append(f"| {metric} | " + " | ".join(str(q[metric][d]) for d in ("static", "ewma", "iforest")) + " |")
        out.append(f"| log patterns | {q['logs']} windows with a new or spiking ERROR template | | |")
    return "\n".join(out)


# ---------- run: the stack and the faults (needs Docker, ops/nt548/deploy.sh) ----------

def sh(*cmd: str, env: dict | None = None, check: bool = True) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=check, env={**os.environ, **(env or {})})


def deploy(*args: str, env: dict | None = None) -> None:
    sh("bash", str(NT548 / "deploy.sh"), *args, env=env)


def load(out: Path, stop: Path, workers: int) -> subprocess.Popen:
    paths = ["GET /", "GET /api/harness/nt548-version", "POST /api/harness/nt548-chat"]
    cmd = [sys.executable, str(NT548 / "lb_check.py"), "load", "--until", str(stop), "--out", str(out),
           "--workers", str(workers), "--pause", "0.05"]
    for p in paths:
        cmd += ["--path", p]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL)


def dump_logs(path: Path, since: float) -> None:
    with path.open("w", encoding="utf-8") as f:
        for project in ("tg-blue", "tg-blue-2", "tg-green"):
            subprocess.run(["docker", "compose", "-p", project, "-f", str(NT548 / "compose/app.yml"), "logs", "--timestamps", "--no-color",
                            "--since", str(int(since) - 1), "harness", "llm-fake-v1"],
                           stdout=f, stderr=subprocess.DEVNULL, check=False)


def run(out: Path, tag: str, normal_s: float, fault_s: float, after_s: float, quiet_s: float, only: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    state = Path(os.environ.setdefault("NT548_STATE", str(NT548 / "state")))
    deploy("up", "blue", tag, "2")
    deploy("lb")
    stop = out / "stop"
    stop.unlink(missing_ok=True)
    base = load(out / "load.json", stop, workers=4)
    time.sleep(10)
    blue = lambda **env: deploy("up", "blue", tag, "2", env=env)  # noqa: E731
    extra: list = []

    def spike_on():
        extra.append(load(out / "spike.json", out / "spike-stop", workers=16))

    def spike_off():
        (out / "spike-stop").touch()
        extra.pop().wait()

    def replica2(*args: str) -> None:  # replica 2 of blue, as deploy.sh starts it (host port 8091)
        sh("docker", "compose", "-p", "tg-blue-2", "-f", str(NT548 / "compose/app.yml"), *args,
           env={"COLOR": "blue", "IMAGE_TAG": tag, "HOST_PORT": "8091"})

    def canary_bad():  # green is already up with the fault; canary_watch sets weight 10 at once
        r = subprocess.run([sys.executable, str(NT548 / "canary_watch.py"), "--step-seconds", "20",
                            "--max-wait-seconds", "20", "run"], check=False)
        print("canary_watch exit", r.returncode, flush=True)

    scenarios = {
        # name: (metric, prepare (no user sees it), inject, recover, recovered_by)
        "llm_errors": ("5xx", None, lambda: blue(FAKE_V1_ERROR_RATE="0.3"), lambda: blue(), "script (manual)"),
        "llm_slow": ("p95", None, lambda: blue(FAKE_V1_DELAY_MS="2000"), lambda: blue(), "script (manual)"),
        "instance_down": ("5xx", None, lambda: replica2("stop"),
                          lambda: replica2("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180"),
                          "script (manual)"),
        "bad_deploy": ("5xx", lambda: deploy("up", "green", tag, env={"NT548_FAULT": "500"}), canary_bad,
                       lambda: deploy("down", "green"), "canary_watch (auto)"),
        "traffic_spike": ("requests", None, spike_on, spike_off, "script (manual)"),
    }
    done = []
    names = only or ["quiet", *scenarios]
    for name in names:
        t_start = time.time()
        if name == "quiet":
            time.sleep(quiet_s)
            t = time.time()
            done.append({"name": "quiet", "metric": "5xx", "t_start": t_start, "t_fault": t, "t_recover": t,
                         "t_end": t, "recovered_by": "-"})
        else:
            metric, prepare, inject, recover, by = scenarios[name]
            if prepare:
                prepare()
            time.sleep(normal_s)
            t_fault = time.time()
            inject()
            if name != "bad_deploy":  # canary_watch decides when bad_deploy ends
                time.sleep(fault_s)
            t_recover = time.time()
            recover()
            t_recovered = time.time()
            time.sleep(after_s)
            done.append({"name": name, "metric": metric, "t_start": t_start, "t_fault": t_fault,
                         "t_recover": t_recover, "t_recovered": t_recovered, "t_end": time.time(),
                         "recovered_by": by})
        dump_logs(out / f"{name}.log", t_start)
        print(json.dumps(done[-1]), flush=True)
    stop.touch()
    base.wait()
    (out / "access.log").write_bytes((state / "log" / "access.log").read_bytes())
    machine = {"cpus": os.cpu_count()}
    (out / "run.json").write_text(json.dumps({"scenarios": done, "machine": machine}, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--tag", default="new", help="image tag of ghcr.io/luanlukim/tripguardian-nt548/* (local)")
    r.add_argument("--normal-s", type=float, default=90)
    r.add_argument("--fault-s", type=float, default=60)
    r.add_argument("--after-s", type=float, default=30)
    r.add_argument("--quiet-s", type=float, default=300)
    r.add_argument("--only", action="append", help="scenario (repeatable; default: quiet and all five)")
    a_ = sub.add_parser("analyze")
    a_.add_argument("run_dir", type=Path)
    a_.add_argument("--out", type=Path, help="results JSON")
    a_.add_argument("--md", type=Path, help="markdown table")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.out, a.tag, a.normal_s, a.fault_s, a.after_s, a.quiet_s, a.only or [])
        return 0
    res = analyze(a.run_dir)
    md = markdown(res)
    if a.out:
        a.out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    if a.md:
        a.md.write_text(md + "\n", encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
