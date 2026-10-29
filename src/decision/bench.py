"""python -m decision bench: the Lựa chọn chatbot on config/bench_decision_assistant.yaml (spec 2026-10-29
assistant-tools §6; same case idea as src/bench/assistant.py, but a Decision session instead of a Trip one).

Each case is a fresh Decision session on the real snapshot (one eval trip, config/eval_trips.yaml) and one or more typed
turns. `{p1}`, `{p2}`, `{p3}` in a turn are the names of the first places of the shortlist, so cases need no fixed names.

    - {id: sel-name, family: select, turns: ["Chọn {p1} giúp mình"], tools: [select], expect: {selected: 1}}
      tools        names the LAST turn must have used (a tool name, or `heuristic` when no model call is meant)
      expect       state after the last turn: selected / dropped / locked / likes / filters / soft = at least n;
                   `unchanged: true` = the state did not change
      reply_has / reply_lacks   regexes on the last reply
      trip         true: needs a Trip session (shared read tools); skipped without --trip

Tiers: no flag = load and resolve every case, no model call; --live = the real Agent (9router, `--model` sets
AGENT_MODEL) — quota costs money, use --family / --limit. Gate: p50 <= 7.5 s, p90 <= 11 s, 0 unsourced numbers, 0 reply that
blocks or lectures, right tool >= 90 % per family."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import yaml

from .settings import ROOT

CASES = ROOT / "config" / "bench_decision_assistant.yaml"
GATE = {"p50_s": 7.5, "p90_s": 11.0, "unsourced": 0, "blocking": 0, "tool_min": 0.9}
# a reply that refuses or lectures the user's own choice (spec §5.9: never block, never nudge)
BLOCKING = re.compile(r"không (nên|được phép|thể chọn)|mình khuyên bạn (không|nên)|bạn nên (chọn|bỏ|đổi)", re.I)
TOOL_LINE = re.compile(r"^([a-z_]+)(?::error.*)?$")
COUNTS = {"selected": lambda st: len(st.selected), "dropped": lambda st: len(st.dropped), "locked": lambda st: len(st.locked),
          "likes": lambda st: len(st.likes), "filters": lambda st: len(st.filters), "soft": lambda st: len(st.profile.soft)}


def load_cases(path: Path = CASES, family: str | None = None, limit: int | None = None) -> list[dict]:
    cases = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]
    cases = [c for c in cases if family is None or c["family"] == family]
    return cases[:limit] if limit else cases


def fill(text: str, names: list[str]) -> str:
    """`{p1}` -> the name of the shortlist's first place, and so on."""
    return re.sub(r"\{p(\d)\}", lambda m: names[int(m[1]) - 1] if int(m[1]) <= len(names) else m[0], text)


def tools_used(entry: dict) -> set[str]:
    log = (entry.get("action") or {}).get("log") or []
    out = set()
    for x in log:
        if x.startswith("heuristic:"):
            out.add("heuristic")
        elif (m := TOOL_LINE.match(x.split(" [", 1)[0])) and m[1] not in ("assistant", "step_cap", "cache_only"):
            out.add(m[1])
    return out


def check(case: dict, before, after, entry: dict) -> list[str]:
    """What this case's last turn got wrong (empty = pass)."""
    problems, say = [], (entry.get("action") or {}).get("say", "")
    used = tools_used(entry)
    for t in case.get("tools") or ():
        if t not in used:
            problems.append(f"tool {t} not used (used: {sorted(used)})")
    for key, n in (case.get("expect") or {}).items():
        if key == "unchanged":
            if n and after.model_dump() != before.model_dump():
                problems.append("state changed")
        elif COUNTS[key](after) < n:
            problems.append(f"{key} {COUNTS[key](after)} < {n}")
    problems += [f"reply lacks /{r}/" for r in case.get("reply_has") or () if not re.search(r, say, re.I)]
    problems += [f"reply has /{r}/" for r in case.get("reply_lacks") or () if re.search(r, say, re.I)]
    return problems


def quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return round(s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))], 2) if s else 0.0


def report(rows: list[dict]) -> dict:
    ran = [r for r in rows if not r.get("skipped")]
    by_family: dict[str, list[bool]] = {}
    for r in ran:
        by_family.setdefault(r["family"], []).append(not r["problems"])
    secs = [r["seconds"] for r in ran if r.get("seconds") is not None]
    out = {"cases": len(rows), "ran": len(ran), "skipped": [r["id"] for r in rows if r.get("skipped")],
           "p50_s": quantile(secs, 0.5), "p90_s": quantile(secs, 0.9),
           "unsourced": sum(r.get("unsourced", 0) for r in ran), "blocking": sum(r.get("blocking", 0) for r in ran),
           "pass_by_family": {f: round(sum(v) / len(v), 2) for f, v in by_family.items()},
           "failed": [{"id": r["id"], "problems": r["problems"]} for r in ran if r["problems"]]}
    out["gate"] = bool(ran) and (not secs or (out["p50_s"] <= GATE["p50_s"] and out["p90_s"] <= GATE["p90_s"])) \
        and out["unsourced"] == 0 and out["blocking"] == 0 and all(v >= GATE["tool_min"] for v in out["pass_by_family"].values())
    return out


def build(trip: bool):
    """(engine, trip reader or None, the eval trip's Search Input). Real snapshot; AGENT_* from .env for --live."""
    from dotenv import load_dotenv

    from agents.assistant import ChatSettings, langchain_chat

    from . import evaluate
    from .engine import Engine
    from .pipeline import Data
    from .session import Store
    from .settings import default

    load_dotenv(ROOT / ".env")
    cfg = default()
    data = Data.load()
    live = all(os.environ.get(k) for k in ("AGENT_API_KEY", "AGENT_BASE_URL", "AGENT_MODEL"))
    chat = langchain_chat(ChatSettings(total_s=cfg.total_s, max_tokens=cfg.assistant.get("max_tokens", 800), cache_key="decision_turn"))
    engine = Engine(data, cfg, Store(None), None, assistant=chat if live else None)
    reader = None
    if trip:
        from trip import Tools as TripTools, create_engine
        data_root = Path(os.environ.get("DATA_DIR", "data"))
        tools = TripTools(create_engine(data_root if data_root.is_absolute() else ROOT / data_root))
        sid = tools.create({"experience": "first", "start_with": "nothing"})["id"]
        reader = lambda _s, text: tools.read_turn(sid, text)  # noqa: E731
    from corpus.ontology import load as load_ontology

    _, trips = evaluate.trips()
    return engine, reader, evaluate.search_input(trips[0], load_ontology().version)


def run_case(engine, reader, si, case: dict) -> dict:
    if case.get("trip") and reader is None:
        return {"id": case["id"], "family": case["family"], "skipped": "needs --trip"}
    engine.trip_reader = reader
    created = engine.create(si.model_dump(mode="json"), "0123456789ab" if reader else None)
    sid = created["id"]
    names = [c["name"] for g in created["view"]["groups"] for c in g["cards"]][:3]
    escaped = [re.escape(n) for n in names]
    case = {**case, "reply_has": [fill(x, escaped) for x in case.get("reply_has") or ()]}
    row = {"id": case["id"], "family": case["family"], "seconds": None, "unsourced": 0, "blocking": 0, "problems": []}
    before = after = engine.store.get(sid).state
    started = time.monotonic()
    for text in case["turns"]:
        before = engine.store.get(sid).state.model_copy(deep=True)
        started = time.monotonic()
        engine.turn(sid, fill(text, names), lambda *a: None)
        after = engine.store.get(sid).state
    row["seconds"] = round(time.monotonic() - started, 2)
    entry = engine.store.get(sid).log[-1]
    log = (entry.get("action") or {}).get("log") or []
    row["unsourced"] = sum(1 for x in log if x.startswith(("say replaced: numbers", "say retry: numbers")))
    say = (entry.get("action") or {}).get("say", "")
    row["blocking"] = 1 if BLOCKING.search(say) else 0
    row["say"], row["tools"] = say, sorted(tools_used(entry))
    row["problems"] = check(case, before, after, entry)
    return row


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m decision bench")
    ap.add_argument("--live", action="store_true", help="call the real Agent (costs quota)")
    ap.add_argument("--model", help="AGENT_MODEL for this run (e.g. cx/gpt-6.1-terra)")
    ap.add_argument("--family")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--trip", action="store_true", help="also build the Trip engine for the shared read tools")
    args = ap.parse_args(argv)
    if args.model:
        os.environ["AGENT_MODEL"] = args.model
    cases = load_cases(family=args.family, limit=args.limit)
    if not args.live:
        for c in cases:
            assert c.get("turns") and c.get("family") and c.get("id"), c
        print(json.dumps({"cases": len(cases), "families": sorted({c["family"] for c in cases}), "live": False}, ensure_ascii=False))
        return
    engine, reader, si = build(args.trip)
    if engine.assistant is None:
        raise SystemExit("AGENT_API_KEY / AGENT_BASE_URL / AGENT_MODEL missing in .env")
    rows = [run_case(engine, reader, si, c) for c in cases]
    print(json.dumps({"model": os.environ.get("AGENT_MODEL"), **report(rows), "rows": rows}, ensure_ascii=False, indent=1))
