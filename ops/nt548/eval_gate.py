"""Eval gate for a model version (#16): a fixed set of prompts to each upstream, a verdict per upstream.

    python ops/nt548/eval_gate.py --upstream v1=http://127.0.0.1:8001 --upstream v2=http://127.0.0.1:8002 --gate v2

Each upstream is called directly (the URLs the model gateway splits between), so one bad version cannot hide behind
a good one. Per upstream: share of valid answers (non-empty text; a JSON object with "answer" when the case needs
JSON), share of errors, p95 latency. Thresholds and cases in ops/nt548/eval_gate.yaml. Exit 0 when every gated
upstream passes; 1 otherwise, and its gateway weight stays 0 (the canary of #17 only raises the weight of a version
that passed).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent


def valid(content: str, needs_json: bool) -> bool:
    if not content.strip():
        return False
    if not needs_json:
        return True
    try:
        obj = json.loads(content)
    except ValueError:
        return False
    return isinstance(obj, dict) and isinstance(obj.get("answer"), str) and bool(obj["answer"].strip())


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, math.ceil(0.95 * len(v)) - 1)]


def evaluate(client: httpx.Client, cfg: dict, model: str = "gemma26b-a4b") -> dict:
    n = errors = ok = 0
    ms: list[float] = []
    for _ in range(cfg.get("repeat", 1)):
        for case in cfg["cases"]:
            body = {"model": model, "messages": [{"role": "user", "content": case["text"]}], "max_tokens": 512}
            if case.get("json"):
                body["response_format"] = {"type": "json_object"}
            n += 1
            t0 = time.perf_counter()
            try:
                r = client.post("/v1/chat/completions", json=body, timeout=cfg.get("timeout_s", 15))
            except httpx.HTTPError:
                errors += 1
                continue
            ms.append(1000 * (time.perf_counter() - t0))
            if r.status_code != 200:
                errors += 1
                continue
            try:
                content = r.json()["choices"][0]["message"]["content"] or ""
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            ok += valid(content, bool(case.get("json")))
    t = cfg["thresholds"]
    res = {"requests": n, "valid": round(ok / n, 4) if n else 0.0, "errors": round(errors / n, 4) if n else 1.0,
           "p95_ms": round(p95(ms), 1) if ms else None}
    fails = []
    if res["valid"] < t["min_valid"]:
        fails.append(f"valid {res['valid']:.0%} < {t['min_valid']:.0%}")
    if res["errors"] > t["max_errors"]:
        fails.append(f"errors {res['errors']:.0%} > {t['max_errors']:.0%}")
    if res["p95_ms"] is None or res["p95_ms"] > t["max_p95_ms"]:
        fails.append(f"p95 {res['p95_ms']} ms > {t['max_p95_ms']} ms")
    return {**res, "pass": not fails, "why": fails}


def main(argv: list[str] | None = None, clients: dict[str, httpx.Client] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", action="append", default=[], help="name=URL, repeatable")
    ap.add_argument("--gate", action="append", help="upstream(s) whose verdict sets the exit code (default: all)")
    ap.add_argument("--config", type=Path, default=HERE / "eval_gate.yaml")
    ap.add_argument("--model", default="gemma26b-a4b")
    ap.add_argument("--out", type=Path, help="JSON verdicts")
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    if clients is None:
        clients = {}
        for spec in a.upstream:
            name, _, url = spec.partition("=")
            if not url:
                ap.error(f"--upstream wants name=URL, got {spec!r}")
            clients[name] = httpx.Client(base_url=url.rstrip("/"))
    if not clients:
        ap.error("no --upstream")
    verdicts = {name: evaluate(c, cfg, a.model) for name, c in clients.items()}
    gated = a.gate or list(verdicts)
    rows = ["| upstream | requests | valid | errors | p95 ms | verdict |", "|---|---|---|---|---|---|"]
    for name, v in verdicts.items():
        verdict = "pass" if v["pass"] else "FAIL: " + "; ".join(v["why"])
        rows.append(f"| {name}{' (gated)' if name in gated else ''} | {v['requests']} | {v['valid']:.0%} | "
                    f"{v['errors']:.0%} | {v['p95_ms']} | {verdict} |")
    print("\n".join(rows))
    if a.out:
        a.out.write_text(json.dumps(verdicts, indent=2), encoding="utf-8")
    failed = [g for g in gated if not verdicts.get(g, {}).get("pass")]
    if failed:
        print(f"gate red for {', '.join(failed)}: keep its gateway weight at 0", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
