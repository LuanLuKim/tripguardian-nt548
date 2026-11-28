"""Incident summary for the NT548 stack (#38): alarm -> evidence -> summary -> GitHub issue labelled `incident`.

Evidence is gathered first and numbered E1..En: the alarm, the alarming metric before vs since the alarm, the
detectors of detect.py on that metric, top log patterns (#37, optional JSON) and deploys shortly before the alarm
(GitHub runs, optional JSON). An LLM (any OpenAI-compatible endpoint: Workers AI, llm-fake) then writes the summary
and extra cause hypotheses from that evidence only; the rule-based hypotheses always stay, listed first. Every LLM
hypothesis must cite evidence ids that exist; if one does not, or there is no LLM, the whole LLM answer is dropped and
the fixed template summary is used. Suggested commands
always come from the fixed rules and are never run: a person decides (only canary_watch of #3 rolls back on its own).

Agent traces (optional): when the harness traces to LangSmith (LANGSMITH_TRACING in ops/nt548/compose/app.yml), the
runs of the agent before vs since the alarm are evidence too: failed turns, turn time, LLM call time, and which runs
(model call, tool) failed. They tell a failing model behind model-gateway from a failing app.

    python ops/nt548/aiops/incident.py demo deploy_500 --out incident.md        # synthetic incident, no AWS / GitHub
    python ops/nt548/aiops/incident.py summarize --series tg.csv --alarm alarm.json --logs patterns.json --deploys runs.json \
        --traces traces.json
    python ops/nt548/aiops/incident.py watch --prefix nt548- --repo owner/name --post   # runner: alarms now in ALARM

LLM settings (environment): INCIDENT_LLM_BASE_URL (".../v1"), INCIDENT_LLM_API_KEY, INCIDENT_LLM_MODEL.
Traces (environment, watch only): LANGSMITH_API_KEY; the project is --traces-project (default nt548-{color}).
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location("detect", Path(__file__).with_name("detect.py"))
detect = importlib.util.module_from_spec(_spec)
sys.modules.setdefault(_spec.name, detect)  # dataclasses look their module up there
_spec.loader.exec_module(detect)

DEMOS = ("deploy_500", "llm_slow", "traffic", "llm_errors")
DEPLOY_WINDOW_MIN = 30  # a deploy that finished this long before the alarm is a suspect
TRACE_WINDOW_MIN = 30  # agent traces this long before the alarm are the baseline
ROLLBACK_CMD = "gh workflow run nt548-deploy-aws.yml -f action=rollback"
GATEWAY_CMD = ("docker compose -f ops/nt548/compose/app.yml exec model-gateway python -c \"import urllib.request as u; "
               "print(u.urlopen('http://localhost:30000/metrics').read().decode())\" | grep gateway_upstream")
MARKER = "<!-- nt548-incident: {} -->"
EPISODE = "<!-- nt548-incident-at: {} {} -->"  # alarm name + when it entered ALARM: the scheduled watch reports it once



@dataclass
class Evidence:
    id: str
    kind: str  # alarm | metric | detector | log | deploy | trace | trace_error
    text: str
    facts: dict = field(default_factory=dict)  # what the rules read; not shown


@dataclass
class Incident:
    alarm: str  # alarm name, also the key that merges repeated alarms into one open issue
    metric: str  # metric name, e.g. TargetResponseTime
    stat: str
    started: dt.datetime
    evidence: list[Evidence]
    dims: dict = field(default_factory=dict)

    def ids(self) -> set[str]:
        return {e.id for e in self.evidence}

    def of(self, kind: str) -> list[Evidence]:
        return [e for e in self.evidence if e.kind == kind]


def episode(inc: Incident) -> str:
    return EPISODE.format(inc.alarm, inc.started.isoformat(timespec="seconds"))


def utc(ts: str | float | dt.datetime) -> dt.datetime:
    if isinstance(ts, dt.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
    if isinstance(ts, (int, float)):
        return dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    return utc(dt.datetime.fromisoformat(ts.replace("Z", "+00:00")))


def hm(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def code(s: str) -> str:
    """Inline code that text from logs or commits cannot break out of."""
    return "`" + str(s).replace("`", "'").replace("\n", " ")[:200] + "`"


# ---------- evidence ----------

def build(alarm: dict, series: detect.Series | None, logs: list[dict] | None = None,
          deploys: list[dict] | None = None, traces: list[dict] | None = None) -> Incident:
    """alarm: {name, metric, stat, dims, reason?, time?}. Without `time`, the alarm starts at the first `combined`
    alarm of detect.py on `series` (synthetic runs, #39). traces: agent runs, see trace_evidence."""
    ev: list[Evidence] = []

    def add(kind: str, text: str, **facts) -> None:
        ev.append(Evidence(f"E{len(ev) + 1}", kind, text, facts))

    metric, stat = alarm.get("metric", "value"), alarm.get("stat", "")
    label = f"{metric} {stat}".strip()
    start_i = None
    alarms: dict[str, np.ndarray] = {}
    if series is not None and len(series.values) > 40:
        if alarm.get("time"):
            start_i = int(round((utc(alarm["time"]).timestamp() - series.t0) / series.step_s))
            start_i = min(max(start_i, 0), len(series.values) - 1)
            train = max(30, start_i - 5)
        else:
            train = len(series.values) // 2
        if train < len(series.values) - 1:
            alarms = detect.detect(series, train)
            if start_i is None:
                hit = np.flatnonzero(alarms["combined"])
                start_i = int(hit[0]) if hit.size else None
    if alarm.get("time"):
        started = utc(alarm["time"])
    elif start_i is not None:
        started = utc(series.t0 + start_i * series.step_s)
    else:
        raise ValueError("no alarm time given and detect.py found no anomaly in the series")

    add("alarm", f"alarm {code(alarm.get('name', 'detect.py combined'))} on {label} entered ALARM at {hm(started)}"
        + (f": {alarm['reason']}" if alarm.get("reason") else ""), metric=metric)

    if series is not None and start_i is not None and 5 <= start_i < len(series.values):
        before, since = series.values[:start_i], series.values[start_i:]
        b, s = float(np.median(before)), float(np.median(since))
        peak_i = start_i + int(np.argmax(since))
        ratio = s / b if b else float("inf")
        add("metric", f"{label}: median {b:.3g} before the alarm, {s:.3g} since"
            + (f" ({ratio:.1f}x)" if b else "") + f", peak {float(series.values[peak_i]):.3g} at "
            f"{hm(utc(series.t0 + peak_i * series.step_s))}", metric=metric, before=b, since=s, ratio=ratio)

    if alarms and start_i is not None:
        parts = []
        for name in ("static", "ewma", "iforest"):
            hit = np.flatnonzero(alarms[name][max(0, start_i - 30):]) + max(0, start_i - 30)
            parts.append(f"{name} from {hm(utc(series.t0 + hit[0] * series.step_s))}" if hit.size
                         else f"{name} did not fire")
        add("detector", "detect.py on the same metric: " + ", ".join(parts),
            static=bool(alarms["static"][start_i:].any()))

    for p in sorted(logs or [], key=lambda p: p.get("count", 0) - p.get("baseline", 0), reverse=True)[:5]:
        grew = p.get("count", 0) - p.get("baseline", 0)
        if grew <= 0:
            continue
        new = p.get("baseline", 0) == 0
        add("log", f"log pattern {code(p['pattern'])}: {p.get('count', 0)} lines in the window, "
            f"{p.get('baseline', 0)} in the window before" + (" (new pattern)" if new else ""),
            level=str(p.get("level", "")).upper(), new=new, pattern=p["pattern"])

    for d in deploys or []:
        when = utc(d.get("updatedAt") or d.get("createdAt"))
        lead = (started - when).total_seconds() / 60
        if -5 <= lead <= DEPLOY_WINDOW_MIN:
            sha = str(d.get("headSha", ""))[:7]
            add("deploy", f"{d.get('workflowName', 'deploy')} run {d.get('databaseId', '?')} (sha {sha}, "
                f"{code(d.get('displayTitle', ''))}) finished {lead:.0f} min before the alarm, "
                f"conclusion {d.get('conclusion') or 'running'}", sha=sha, lead=lead)

    trace_evidence(add, traces or [], started)
    return Incident(alarm.get("name", f"detect-{metric}"), metric, stat, started, ev, alarm.get("dims", {}))


def _secs(r: dict) -> float | None:
    return (utc(r["end_time"]) - utc(r["start_time"])).total_seconds() if r.get("end_time") else None


def _trace_window(runs: list[dict]) -> dict:
    roots = [r for r in runs if r.get("root")]
    turn = [s for r in roots if (s := _secs(r)) is not None]
    llm = [s for r in runs if r.get("run_type") == "llm" and (s := _secs(r)) is not None]
    return {"turns": len(roots), "failed": sum(1 for r in roots if r.get("error")),
            "p95": float(np.percentile(turn, 95)) if turn else None,
            "llm": float(np.median(llm)) if llm else None}


def trace_evidence(add, runs: list[dict], started: dt.datetime) -> None:
    """Agent runs (LangSmith or a JSON file): [{run_type: chain|llm|tool|..., name, start_time, end_time, error,
    root, url?}], one per run of the trace tree. Adds one `trace` evidence (before vs since the alarm) and up to 3
    `trace_error` evidences (failed runs since the alarm, grouped by run type, name and first line of the error)."""
    lo = started - dt.timedelta(minutes=TRACE_WINDOW_MIN)
    before = [r for r in runs if lo <= utc(r["start_time"]) < started]
    since = [r for r in runs if utc(r["start_time"]) >= started]
    if not before and not since:
        return
    b, s = _trace_window(before), _trace_window(since)

    def rate(w: dict) -> float | None:
        return w["failed"] / w["turns"] if w["turns"] else None

    def pct(x: float | None) -> str:
        return "-" if x is None else f"{100 * x:.0f}%"

    def sec(x: float | None) -> str:
        return "-" if x is None else f"{x:.2g} s"

    add("trace", f"agent traces (LangSmith): {b['turns']} turns in the {TRACE_WINDOW_MIN} min before the alarm, "
        f"{s['turns']} since; failed turns {pct(rate(b))} -> {pct(rate(s))}; p95 turn time {sec(b['p95'])} -> "
        f"{sec(s['p95'])}; median model call {sec(b['llm'])} -> {sec(s['llm'])}",
        fail_before=rate(b) or 0.0, fail_since=rate(s) or 0.0, llm_before=b["llm"], llm_since=s["llm"])

    failed = [r for r in since if r.get("error") and not r.get("root")] or [r for r in since if r.get("error")]
    groups: dict[tuple, list[dict]] = {}
    for r in failed:
        # LangSmith stores the exception, then its traceback with no line break between them
        first = re.split(r"Traceback \(most recent call last\)|\n", str(r["error"]).strip())[0][:120] or "error"
        groups.setdefault((r.get("run_type", "?"), r.get("name", "?"), first), []).append(r)
    for (kind, name, err), rs in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)[:3]:
        url = next((r["url"] for r in rs if r.get("url")), "")
        add("trace_error", f"{len(rs)} {kind} run(s) {code(name)} failed since the alarm: {code(err)}"
            + (f", e.g. {url}" if url else ""), run_type=kind, name=name, count=len(rs))


# ---------- writing: fixed rules, then optionally an LLM over the same evidence ----------

def rules(inc: Incident) -> tuple[list[dict], list[dict]]:
    """(hypotheses, commands) from fixed rules. Each hypothesis cites the evidence it rests on."""
    hyp, cmds = [], []
    m = inc.of("metric")
    mid = [e.id for e in m]
    errors = [e for e in inc.of("log") if e.facts.get("level") in ("ERROR", "CRITICAL") or "500" in e.facts["pattern"]
              or "timeout" in e.facts["pattern"].lower()]
    for d in inc.of("deploy"):
        hyp.append({"text": f"The deploy of {d.facts['sha']} {d.facts['lead']:.0f} min before the alarm is the first "
                            "suspect: the metric changed right after it.", "evidence": [d.id] + mid,
                    "confidence": "high" if errors else "medium"})
        cmds.append({"cmd": ROLLBACK_CMD, "why": f"go back to the color that ran before {d.facts['sha']}",
                     "evidence": [d.id]})
    gateway = {"cmd": GATEWAY_CMD, "why": "per-upstream latency and cooldown in the gateway (#15), on an app instance"}
    tid = [e.id for e in inc.of("trace")]
    llm_err = [e for e in inc.of("trace_error") if e.facts["run_type"] == "llm"]
    if llm_err:
        hyp.append({"text": f"The agent's model calls fail ({llm_err[0].facts['count']} failed runs in the traces): "
                            "the LLM behind model-gateway returns errors, and the app fails with it.",
                    "evidence": [llm_err[0].id] + tid + mid, "confidence": "medium" if inc.of("deploy") else "high"})
        cmds.append({**gateway, "evidence": [llm_err[0].id]})
    for e in [e for e in inc.of("trace_error") if e.facts["run_type"] == "tool"][:2]:
        hyp.append({"text": f"Tool {code(e.facts['name'])} fails inside the agent ({e.facts['count']} failed runs).",
                    "evidence": [e.id] + tid, "confidence": "medium"})
    t = inc.of("trace")[0].facts if inc.of("trace") else {}
    if not llm_err and t.get("llm_before") and t.get("llm_since") and t["llm_since"] >= 2 * t["llm_before"]:
        hyp.append({"text": f"Model calls got {t['llm_since'] / t['llm_before']:.1f}x slower in the traces: the time "
                            "goes to the LLM behind model-gateway, not to the app.",
                    "evidence": tid + mid, "confidence": "medium"})
        cmds.append({**gateway, "evidence": tid})
    for e in errors[:2]:
        hyp.append({"text": f"New or growing error lines {code(e.facts['pattern'])} point at where it fails.",
                    "evidence": [e.id] + mid, "confidence": "medium"})
    metric = inc.metric.lower()
    if not inc.of("deploy"):
        if "requestcount" in metric:
            hyp.append({"text": "Traffic rose with no deploy before it: load, not a code change. Check that the ASG "
                                "scaled out.", "evidence": mid or [inc.evidence[0].id], "confidence": "medium"})
            asg = inc.dims.get("AutoScalingGroupName", "<asg-name>")
            cmds.append({"cmd": f"aws autoscaling describe-scaling-activities --auto-scaling-group-name {asg} "
                                "--max-items 5", "why": "did the ASG add instances", "evidence": mid})
        elif "responsetime" in metric or "latency" in metric:
            hyp.append({"text": "Latency rose with no deploy before it: a slow upstream (the LLM behind "
                                "model-gateway) or a saturated app instance.",
                        "evidence": mid or [inc.evidence[0].id], "confidence": "low"})
            if all(c["cmd"] != GATEWAY_CMD for c in cmds):
                cmds.append({**gateway, "evidence": mid})
    if not hyp:
        hyp.append({"text": "The evidence gathered does not point at a cause.", "evidence": [inc.evidence[0].id],
                    "confidence": "low"})
    if m and m[0].facts.get("ratio", 0) and any(e.kind == "detector" and not e.facts.get("static")
                                                for e in inc.evidence):
        hyp.append({"text": "A fixed threshold would not have caught this: only the learned detectors fired.",
                    "evidence": [e.id for e in inc.of("detector")], "confidence": "high"})
    return hyp, cmds


def template_summary(inc: Incident) -> str:
    m = inc.of("metric")
    head = f"{inc.metric} {inc.stat}".strip()
    if m:
        f = m[0].facts
        head += f" went from a median of {f['before']:.3g} to {f['since']:.3g} at {hm(inc.started)}"
    else:
        head += f" alarmed at {hm(inc.started)}"
    extra = []
    if inc.of("deploy"):
        extra.append(f"{len(inc.of('deploy'))} deploy(s) finished shortly before")
    if inc.of("log"):
        extra.append(f"{len(inc.of('log'))} log pattern(s) grew")
    return head + (" · " + "; ".join(extra) if extra else "") + "."


PROMPT = """You are writing an incident summary for an on-call engineer. Use ONLY the evidence below; do not add
facts. Answer with one JSON object and nothing else:
{"summary": "<2-3 sentences>", "hypotheses": [{"text": "<one likely cause>", "evidence": ["E1"],
"confidence": "high|medium|low"}]}
Every hypothesis cites the evidence ids it rests on. If the evidence does not show a cause, say so in one
hypothesis citing the alarm. At most 4 hypotheses.

Evidence:
"""


MAX_TOKENS = 1024  # Workers AI cuts answers at 256 tokens by default, which leaves the JSON unclosed
FORMAT_SLIPS = ("no JSON in the answer", "answer is not valid JSON")


def ask_llm(inc: Incident, base_url: str, api_key: str = "", model: str = "", timeout: float = 60) -> str:
    """One chat completion in JSON mode; an endpoint that rejects response_format (HTTP 400 / 422) is asked again
    without it."""
    body = {"model": model or "default", "temperature": 0, "max_tokens": MAX_TOKENS,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": PROMPT + "\n".join(f"{e.id} ({e.kind}): {e.text}"
                                                                          for e in inc.evidence)}]}
    headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {api_key}"} if api_key else {})}
    url = base_url.rstrip("/") + "/chat/completions"
    try:
        return _complete(url, body, headers, timeout)
    except urllib.error.HTTPError as e:
        if e.code not in (400, 422):
            raise
        return _complete(url, {k: v for k, v in body.items() if k != "response_format"}, headers, timeout)


def _complete(url: str, body: dict, headers: dict, timeout: float) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), headers), timeout=timeout) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def llm_answer(inc: Incident, llm: dict) -> tuple[dict | None, str]:
    """(answer, '') or (None, why). A format slip (no JSON, cut-off JSON) is asked once more; an answer that cites
    evidence that does not exist is not: asking again would only fish for a different made-up cause."""
    why = ""
    for _ in range(2):
        try:
            answer, why = check_llm(ask_llm(inc, **llm), inc.ids())
        except Exception as e:  # network, HTTP, shape: fall back, never fail the incident
            return None, f"LLM call failed: {type(e).__name__}"
        if answer or why not in FORMAT_SLIPS:
            return answer, why
    return None, why


def check_llm(text: str, ids: set[str]) -> tuple[dict | None, str]:
    """(answer, '') when the answer is usable, else (None, why). Usable: JSON with a summary and 1-4 hypotheses
    that each cite only evidence ids that exist."""
    found = re.search(r"\{.*\}", text or "", re.S)
    if not found:
        return None, "no JSON in the answer"
    try:
        a = json.loads(found.group(0))
    except json.JSONDecodeError:
        return None, "answer is not valid JSON"
    hyp = a.get("hypotheses")
    if not isinstance(a.get("summary"), str) or not a["summary"].strip():
        return None, "no summary"
    if not isinstance(hyp, list) or not 1 <= len(hyp) <= 4:
        return None, "needs 1-4 hypotheses"
    for h in hyp:
        cited = h.get("evidence") if isinstance(h, dict) else None
        if not isinstance(h, dict) or not isinstance(h.get("text"), str) or not cited:
            return None, "a hypothesis cites no evidence"
        unknown = set(map(str, cited)) - ids
        if unknown:
            return None, f"cites evidence that does not exist: {', '.join(sorted(unknown))}"
        if h.get("confidence") not in ("high", "medium", "low"):
            h["confidence"] = "low"
    return a, ""


def write(inc: Incident, llm: dict | None = None) -> str:
    """Markdown body of the incident issue. llm: {base_url, api_key, model} or None for the template only."""
    hyp, cmds = rules(inc)
    hyp = [{**h, "by": "rule"} for h in hyp]
    summary, by = template_summary(inc), "fixed template (no LLM configured)"
    if llm and llm.get("base_url"):
        answer, why = llm_answer(inc, llm)
        if answer:
            # the rules stay first: they are tested and decisive, the LLM tends to hedge (tried 24/11)
            summary = answer["summary"].strip()
            hyp += [{**h, "by": "LLM"} for h in answer["hypotheses"]]
            by = (f"LLM `{llm.get('model') or 'default'}` (summary, extra causes checked against the evidence ids)"
                  " + fixed rules")
        else:
            by = f"fixed template (LLM answer rejected: {why})"
    out = [MARKER.format(inc.alarm), episode(inc), f"## Incident: {code(inc.alarm)}", "",
           f"**Started:** {hm(inc.started)} · **Metric:** {inc.metric} {inc.stat} · **Written by:** {by}", "",
           "### Summary", "", summary, "", "### Likely causes (each cites the evidence below)", ""]
    out += [f"{i}. {h['text']} [{', '.join(map(str, h['evidence']))}] ({h['confidence']}, {h['by']})"
            for i, h in enumerate(hyp, 1)]
    out += ["", "### Suggested commands (not run: a person decides)", ""]
    out += [f"- {code(c['cmd'])}: {c['why']} [{', '.join(c['evidence'])}]" for c in cmds] or ["- none"]
    out += ["", "### Evidence", ""] + [f"- **{e.id}** ({e.kind}) {e.text}" for e in inc.evidence]
    return "\n".join(out) + "\n"


# ---------- GitHub: one open issue per alarm ----------

def gh(args: list[str], stdin: str | None = None) -> str:
    return subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=True).stdout


def post(inc: Incident, body: str, repo: str, run=gh) -> str:
    """Comment on the open `incident` issue of this alarm, or open one. Returns what was done. The same ALARM episode
    (alarm + time it entered ALARM) already on the issue is skipped, so a watch every few minutes does not repeat it."""
    run(["label", "create", "incident", "--repo", repo, "--color", "B60205", "--force",
         "--description", "opened by ops/nt548/aiops/incident.py"])
    issues = json.loads(run(["issue", "list", "--repo", repo, "--label", "incident", "--state", "open",
                             "--json", "number,body,comments", "--limit", "100"]) or "[]")
    for i in issues:
        if MARKER.format(inc.alarm) in (i.get("body") or ""):
            seen = [i.get("body") or ""] + [c.get("body") or "" for c in i.get("comments") or []]
            if any(episode(inc) in b for b in seen):
                return f"already reported on #{i['number']}"
            run(["issue", "comment", str(i["number"]), "--repo", repo, "--body-file", "-"], body)
            return f"commented on #{i['number']}"
    url = run(["issue", "create", "--repo", repo, "--label", "incident", "--title",
               f"incident: {inc.alarm} ({inc.metric}) at {hm(inc.started)}", "--body-file", "-"], body)
    return f"opened {url.strip()}"


def recent_deploys(repo: str, workflow: str = "nt548-deploy-aws.yml", run=gh) -> list[dict]:
    try:
        return json.loads(run(["run", "list", "--repo", repo, "--workflow", workflow, "--limit", "10", "--json",
                               "databaseId,displayTitle,headSha,createdAt,updatedAt,conclusion,workflowName"]))
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return []  # workflow not there yet, or no gh: summarize without deploys


# ---------- sources ----------

def from_cloudwatch(a: dict) -> dict:
    """describe_alarms entry -> the alarm dict of build(); handles plain and anomaly-detection (metric math) alarms."""
    stat_of = a.get("ExtendedStatistic") or a.get("Statistic") or ""
    metric, ns, dims, period = a.get("MetricName"), a.get("Namespace"), a.get("Dimensions") or [], a.get("Period", 60)
    for q in a.get("Metrics") or []:
        if "MetricStat" in q:
            ms = q["MetricStat"]
            metric, ns, dims = ms["Metric"]["MetricName"], ms["Metric"]["Namespace"], ms["Metric"].get("Dimensions", [])
            stat_of, period = ms["Stat"], ms["Period"]
            break
    return {"name": a["AlarmName"], "metric": metric, "namespace": ns, "stat": stat_of, "period": period,
            "dims": {d["Name"]: d["Value"] for d in dims}, "reason": a.get("StateReason", ""),
            "time": a["StateUpdatedTimestamp"]}


def demo_traces(rng: np.random.Generator, t0: float, n: int, at: int, llm_s: tuple[float, float],
                fail_since: float = 0.0, error: str = "") -> list[dict]:
    """One agent turn a minute over the last 90 points: a root chain, one model call, one tool call. Since point
    `at` the model call takes llm_s[1] s instead of llm_s[0] and fails with probability fail_since."""
    runs = []
    for i in range(n - 90, n):
        start = t0 + i * 60.0 + float(rng.uniform(0, 30))
        after = i >= at
        llm = max(0.05, float(rng.normal(llm_s[after], 0.1 * llm_s[after])))
        err = error if after and rng.random() < fail_since else None
        tool = 0.0 if err else 0.1  # a failed model call ends the turn before any tool
        iso = lambda x: utc(x).isoformat()
        runs.append({"run_type": "chain", "name": "LangGraph", "root": True, "start_time": iso(start),
                     "end_time": iso(start + llm + tool + 0.05), "error": err})
        runs.append({"run_type": "llm", "name": "ChatOpenAI", "root": False, "start_time": iso(start + 0.01),
                     "end_time": iso(start + 0.01 + llm), "error": err})
        if not err:
            runs.append({"run_type": "tool", "name": "search_places", "root": False, "start_time": iso(start + llm),
                         "end_time": iso(start + llm + tool), "error": None})
    return runs


def demo(case: str, seed: int = 0, now: dt.datetime | None = None) -> tuple[dict, detect.Series, list, list, list]:
    """A synthetic incident (alarm, series, log patterns, deploys, agent traces) for each case in DEMOS; the fault
    starts at point 180 of 240 (one per minute)."""
    if case not in DEMOS:
        raise ValueError(f"unknown demo {case}; one of {', '.join(DEMOS)}")
    rng = np.random.default_rng(seed)
    n, at, step = 240, 180, 60.0
    now = now or dt.datetime(2026, 11, 28, 10, 0, tzinfo=dt.timezone.utc)
    t0 = now.timestamp() - n * step
    at_t = utc(t0 + at * step)
    deploys, logs, traces = [], [], []
    if case == "deploy_500":
        v = rng.poisson(1.0, n).astype(float)
        v[at:] += rng.poisson(30.0, n - at)
        alarm = {"name": "nt548-demo-5xx", "metric": "HTTPCode_Target_5XX_Count", "stat": "Sum"}
        deploys = [{"databaseId": 1001, "workflowName": "nt548-deploy-aws", "headSha": "a1b2c3d4e5",
                    "displayTitle": "feat: new planner prompt", "conclusion": "success",
                    "updatedAt": (at_t - dt.timedelta(minutes=6)).isoformat()}]
        logs = [{"pattern": "POST /api/plan <*> 500 upstream error", "count": 1740, "baseline": 0, "level": "ERROR"},
                {"pattern": "GET / 200", "count": 5200, "baseline": 5050, "level": "INFO"}]
    elif case == "llm_slow":
        v = 0.2 + rng.normal(0, 0.02, n)
        v[at:] += 1.8
        alarm = {"name": "nt548-demo-latency", "metric": "TargetResponseTime", "stat": "p95"}
        deploys = [{"databaseId": 990, "workflowName": "nt548-deploy-aws", "headSha": "0ff1ce0ff1",
                    "displayTitle": "chore: bump", "conclusion": "success",
                    "updatedAt": (at_t - dt.timedelta(hours=3)).isoformat()}]  # too early to be a suspect
        logs = [{"pattern": "model-gateway upstream <*> timeout after <*> s", "count": 310, "baseline": 2,
                 "level": "WARNING"}]
        traces = demo_traces(rng, t0, n, at, (0.8, 2.6))
    elif case == "llm_errors":  # #39: the fake LLM fails 30 % of calls; no deploy, no log pattern explains it
        v = rng.poisson(0.5, n).astype(float)
        v[at:] += rng.poisson(12.0, n - at)
        alarm = {"name": "nt548-demo-blue-errors", "metric": "HTTPCode_Target_5XX_Count", "stat": "Sum"}
        traces = demo_traces(rng, t0, n, at, (0.8, 0.8), 0.3, "OpenAIAPIError('Error code: 500 - injected "
                                                              "failure (FAKE_ERROR_RATE)')Traceback (most recent call "
                                                              "last):\n  File ...")  # as LangSmith stored it, 25/11
    else:  # traffic
        v = 100 + rng.normal(0, 8, n)
        v[at:] += 300
        alarm = {"name": "nt548-demo-requests", "metric": "RequestCount", "stat": "Sum",
                 "dims": {"AutoScalingGroupName": "nt548-blue"}}
    return alarm, detect.Series(np.maximum(v, 0), None, step, t0), logs, deploys, traces


def trace_project(template: str, alarm_name: str) -> str:
    """The LangSmith project of the color an alarm is about: nt548-{color} + nt548-blue-latency-anomaly ->
    nt548-blue. '' when the template wants a color and the alarm name has none."""
    if "{color}" not in template:
        return template
    m = re.search(r"-(blue|green)-", alarm_name)
    return template.format(color=m.group(1)) if m else ""


def langsmith_runs(project: str, since: dt.datetime, limit: int = 2000) -> list[dict]:
    """Runs of a LangSmith project started since `since`, in the shape trace_evidence reads. [] on any failure:
    the incident is written without traces."""
    try:
        from langsmith import Client

        return [{"run_type": r.run_type, "name": r.name, "start_time": utc(r.start_time).isoformat(),
                 "end_time": utc(r.end_time).isoformat() if r.end_time else None, "error": r.error,
                 "root": r.parent_run_id is None, "url": getattr(r, "url", None)}
                for r in Client().list_runs(project_name=project, start_time=since, limit=limit)]
    except Exception as e:  # no package, no project yet, network, auth
        print(f"LangSmith traces of {project} not read: {type(e).__name__}", file=sys.stderr)
        return []


def llm_env() -> dict | None:
    base = os.environ.get("INCIDENT_LLM_BASE_URL", "")
    return {"base_url": base, "api_key": os.environ.get("INCIDENT_LLM_API_KEY", ""),
            "model": os.environ.get("INCIDENT_LLM_MODEL", "")} if base else None


def log_patterns():
    """ops/nt548/aiops/log_patterns.py (#37), loaded only by `watch --log-group` (it needs drain3)."""
    spec = importlib.util.spec_from_file_location("log_patterns", Path(__file__).with_name("log_patterns.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, mod)
    spec.loader.exec_module(mod)
    return mod


def load_json(path: Path | None) -> list | dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def emit(body: str, out: Path | None) -> None:
    if out:
        out.write_text(body, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to a code page without "·"
        sys.stdout.write(body)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="summary of a synthetic incident")
    d.add_argument("case", choices=DEMOS)
    d.add_argument("--seed", type=int, default=0)
    s = sub.add_parser("summarize", help="summary from files")
    s.add_argument("--series", type=Path, required=True, help="t,value CSV (detect.py cloudwatch / synth)")
    s.add_argument("--alarm", type=Path, help="JSON {name, metric, stat, time?, reason?, dims?}")
    s.add_argument("--logs", type=Path, help="JSON [{pattern, count, baseline, level}] (#37)")
    s.add_argument("--deploys", type=Path, help="JSON of gh run list --json databaseId,displayTitle,headSha,...")
    s.add_argument("--traces", type=Path, help="JSON [{run_type, name, start_time, end_time, error, root, url?}]")
    w = sub.add_parser("watch", help="every CloudWatch alarm now in ALARM -> one incident each (runner)")
    w.add_argument("--prefix", default="nt548-")
    w.add_argument("--minutes", type=int, default=180)
    w.add_argument("--logs", type=Path)
    w.add_argument("--log-group", help="CloudWatch Logs group of the color ({color} from the alarm name): top log "
                                       "patterns of the last --log-window-min minutes (log_patterns.py, #37)")
    w.add_argument("--log-window-min", type=float, default=10)
    w.add_argument("--traces-project", default="nt548-{color}",
                   help="LangSmith project of the harness ({color} from the alarm name); read when LANGSMITH_API_KEY is set")
    for sp in (d, s, w):
        sp.add_argument("--repo", help="owner/name; with --post the summary goes to an `incident` issue there")
        sp.add_argument("--post", action="store_true")
        sp.add_argument("--out", type=Path, help="also write the markdown here (default: stdout)")
    a = p.parse_args(argv)
    if a.post and not a.repo:
        p.error("--post needs --repo")

    work: list[tuple[dict, detect.Series | None, list | None, list | None, list | None]] = []
    if a.cmd == "demo":
        work.append(demo(a.case, a.seed))
    elif a.cmd == "summarize":
        alarm = load_json(a.alarm) or {"name": f"detect-{a.series.stem}", "metric": a.series.stem}
        work.append((alarm, detect.read_csv(a.series), load_json(a.logs), load_json(a.deploys), load_json(a.traces)))
    else:
        import boto3

        cw = boto3.client("cloudwatch")
        found = [x for page in cw.get_paginator("describe_alarms").paginate(AlarmNamePrefix=a.prefix,
                                                                            StateValue="ALARM")
                 for x in page["MetricAlarms"]]
        deploys = recent_deploys(a.repo) if a.repo else []
        for x in found:
            alarm = from_cloudwatch(x)
            series = detect.cloudwatch(alarm["metric"], alarm["dims"], a.minutes, alarm["stat"], alarm["period"],
                                       alarm["namespace"])
            project = trace_project(a.traces_project, alarm["name"])
            traces = (langsmith_runs(project, utc(alarm["time"]) - dt.timedelta(minutes=TRACE_WINDOW_MIN))
                      if project and os.environ.get("LANGSMITH_API_KEY") else [])
            logs = load_json(a.logs)
            group = trace_project(a.log_group, alarm["name"]) if a.log_group else None
            if group:
                lp = log_patterns()
                now = dt.datetime.now(dt.timezone.utc)
                try:
                    lines = lp.cloudwatch_lines(group, now - dt.timedelta(minutes=2 * a.log_window_min), now)
                    logs = lp.top(lines, now, a.log_window_min)
                except Exception as e:  # group not there yet or not readable: summarize without log patterns
                    print(f"log patterns of {group} skipped: {e}", file=sys.stderr)
            work.append((alarm, series, logs, deploys, traces))
        if not found:
            print(f"no alarm with prefix {a.prefix} in ALARM", file=sys.stderr)

    bodies = []
    for alarm, series, logs, deploys, traces in work:
        inc = build(alarm, series, logs, deploys, traces)
        bodies.append(write(inc, llm_env()))
        if a.post:
            print(post(inc, bodies[-1], a.repo), file=sys.stderr)
    emit("\n---\n\n".join(bodies), a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
