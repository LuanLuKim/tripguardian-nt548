"""Log pattern mining for the NT548 stack (#37): Drain3 templates, a window against the window before it.

Lines are grouped into templates with Drain3 (variable parts such as ids, numbers and addresses become <NUM>, <IP>,
<*>). The last `window` minutes before `--at` are counted against the `window` minutes before that (the baseline).
A template is an anomaly when it is new (no line in the baseline, while the baseline itself has lines) or when an
error-level template grows to at least `spike` times its baseline. The output is the input of incident.py --logs (#38):
[{pattern, count, baseline, level, anomaly}], anomalies first, then by growth.

    docker compose -p tg-blue logs --timestamps --no-color --since 30m > blue.log
    python ops/nt548/aiops/log_patterns.py top blue.log --window-min 10 --out patterns.json
    python ops/nt548/aiops/incident.py summarize --series tg.csv --alarm alarm.json --logs patterns.json

Accepted lines: `docker compose logs --timestamps` (`<service>  | <ISO time> <message>`), or `<ISO time> <message>`.
A line with no time (a traceback line) takes the time of the line before it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from drain3 import TemplateMiner
from drain3.masking import MaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

COMPOSE_PREFIX = re.compile(r"^(?P<service>[\w.-]+)\s+\|\s?(?P<rest>.*)$")
ISO_TIME = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<msg>.*)$")
ERROR_WORDS = re.compile(r"\b(ERROR|CRITICAL|FATAL|Traceback|Exception)\b")
WARN_WORDS = re.compile(r"\b(WARN|WARNING)\b")
HTTP_5XX = re.compile(r"\"\s+5\d\d\b|\bstatus=5\d\d\b|\bHTTP/\d(?:\.\d)?\"?\s+5\d\d\b")
LEVELS = ("ERROR", "WARNING", "INFO")


@dataclass
class Line:
    t: datetime
    service: str
    message: str



def parse_time(raw: str) -> datetime:
    raw = raw.replace(",", ".").replace(" ", "T", 1)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    head, dot, frac = raw.partition(".")
    if dot:  # docker prints nanoseconds; fromisoformat takes at most microseconds
        digits = re.match(r"\d+", frac).group(0)
        raw = f"{head}.{digits[:6]}{frac[len(digits):]}"
    t = datetime.fromisoformat(raw)
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def parse(lines: Iterable[str]) -> list[Line]:
    out: list[Line] = []
    for raw in lines:
        raw = raw.rstrip("\r\n")
        if not raw.strip():
            continue
        service, rest = "", raw
        m = COMPOSE_PREFIX.match(raw)
        if m:
            service, rest = m["service"], m["rest"]
        m = ISO_TIME.match(rest)
        if m:
            msg = m["msg"].strip()
            inner = ISO_TIME.match(msg)  # the app's own logging time (asctime) after docker's
            out.append(Line(parse_time(m["ts"]), service, (inner["msg"] if inner else msg).strip()))
        elif out:  # a continuation line (traceback) keeps the time of the line before
            out.append(Line(out[-1].t, service or out[-1].service, rest.strip()))
    return out


def level(message: str) -> str:
    if ERROR_WORDS.search(message) or HTTP_5XX.search(message):
        return "ERROR"
    if WARN_WORDS.search(message):
        return "WARNING"
    return "INFO"


def miner() -> TemplateMiner:
    cfg = TemplateMinerConfig()
    cfg.profiling_enabled = False
    cfg.drain_sim_th = 0.4
    cfg.drain_depth = 4
    cfg.masking_instructions = [
        MaskingInstruction(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "ID"),
        MaskingInstruction(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b", "IP"),
        MaskingInstruction(r"\b0x[0-9a-fA-F]+\b|\b[0-9a-f]{16,}\b", "HEX"),
        # every number but an HTTP status (200, 500, status=503), which tells an error from a success
        MaskingInstruction(r"(?<![\w./])(?![1-5]\d\d(?![\w.]))\d+(?:\.\d+)?(?:ms|s)?(?![\w.])", "NUM"),
    ]
    return TemplateMiner(config=cfg)


def top(lines: list[Line], at: datetime | None = None, window_min: float = 10.0, spike: float = 3.0,
        min_count: int = 3, limit: int = 10) -> list[dict]:
    """Templates of the window (at - window, at] against the baseline (at - 2 window, at - window]."""
    if not lines:
        return []
    at = at or max(x.t for x in lines)
    w = timedelta(minutes=window_min)
    window = [x for x in lines if at - w < x.t <= at]
    base = [x for x in lines if at - 2 * w < x.t <= at - w]
    tm = miner()  # the service stays out of the mined text (compose numbers replicas: web-1, web-2)
    for x in base + window:  # first pass: templates settle on every line
        tm.add_log_message(x.message)
    ids: dict[tuple[str, int], str] = {}
    worst: dict[tuple[str, int], str] = {}

    def cluster(x: Line) -> tuple[str, int]:
        c = tm.match(x.message, full_search_strategy="fallback")
        service = re.sub(r"-\d+$", "", x.service)
        cid = (service, c.cluster_id if c else -1)
        template = c.get_template() if c else x.message
        ids.setdefault(cid, f"[{service}] {template}" if service else template)
        lv = level(x.message)  # a template is as bad as its worst line
        if cid not in worst or LEVELS.index(lv) < LEVELS.index(worst[cid]):
            worst[cid] = lv
        return cid

    now, before = Counter(map(cluster, window)), Counter(map(cluster, base))
    out = []
    for cid in set(now) | set(before):
        count, baseline, lv = now[cid], before[cid], worst[cid]
        anomaly = None
        if count >= min_count and baseline == 0 and base:
            anomaly = "new"
        elif lv == "ERROR" and count >= min_count and count >= spike * max(baseline, 1):
            anomaly = "spike"
        out.append({"pattern": ids[cid], "count": count, "baseline": baseline, "level": lv, "anomaly": anomaly})
    out.sort(key=lambda p: (p["anomaly"] is None, LEVELS.index(p["level"]), -(p["count"] - p["baseline"]),
                            p["pattern"]))
    return out[:limit]


def table(patterns: list[dict]) -> str:
    rows = ["| anomaly | level | count | baseline | pattern |", "|---|---|---:|---:|---|"]
    for p in patterns:
        rows.append(f"| {p['anomaly'] or ''} | {p['level']} | {p['count']} | {p['baseline']} | "
                    f"`{p['pattern'].replace('`', chr(39)).replace('|', '/')}` |")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("top", help="top templates of the last window against the window before")
    t.add_argument("log", type=Path, nargs="?", help="log file (default stdin)")
    t.add_argument("--at", help="end of the window, ISO time (default: the last line)")
    t.add_argument("--window-min", type=float, default=10.0)
    t.add_argument("--spike", type=float, default=3.0, help="an error template this many times its baseline is a spike")
    t.add_argument("--min-count", type=int, default=3)
    t.add_argument("--limit", type=int, default=10)
    t.add_argument("--out", type=Path, help="JSON for incident.py --logs (default: a table on stdout)")
    a = ap.parse_args(argv)

    text = a.log.read_text(encoding="utf-8", errors="replace").splitlines() if a.log else sys.stdin
    patterns = top(parse(text), parse_time(a.at) if a.at else None, a.window_min, a.spike, a.min_count, a.limit)
    if a.out:
        a.out.write_text(json.dumps(patterns, indent=2, ensure_ascii=False), encoding="utf-8")
    print(table(patterns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
