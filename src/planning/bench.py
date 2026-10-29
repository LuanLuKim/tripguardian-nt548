"""python -m planning bench: the Lịch trình chatbot on config/bench_planning_assistant.yaml (spec 2026-10-30
planning-assistant §7; same case idea as src/decision/bench.py, but a Planning session instead of a Decision one).

Each case is a fresh Planning session on the real snapshot (the first hidden trip of config/eval_trips.yaml that Place
Decision confirms, first plan option chosen) and one or more typed turns. `{p1}` `{p2}` are the names of the first two stops
of day 1, `{p3}` the first stop of day 2, `{p4}` the last stop of day 1, so cases need no fixed names.

    - {id: mv-name, family: move, turns: ["Chuyển {p1} sang ngày 2"], tools: [move_place], expect: {changed: true}}
      tools        names the LAST turn must have used (a tool name)
      expect       state after the last turn: changed / unchanged / locked / dropped (at least n) / pace (equals)
      reply_has / reply_lacks   regexes on the last reply
      trip         true: needs a Trip session (shared read tools); skipped without --trip

Always checked: every turn makes at most ONE plan version; no physical violation the plan did not have at the start.
Tiers: no flag = load every case, no model call; --live = the real Agent (9router, `--model` sets AGENT_MODEL) — quota costs
money, use --family / --limit. Gate: p50 <= 7.5 s, p90 <= 11 s, 0 unsourced numbers, 0 broken physical constraints, 0 reply
that blocks or lectures, right tool >= 90 % per family."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import yaml

from .settings import ROOT

CASES = ROOT / "config" / "bench_planning_assistant.yaml"
GATE = {"p50_s": 7.5, "p90_s": 11.0, "unsourced": 0, "physical": 0, "blocking": 0, "tool_min": 0.9}
BLOCKING = re.compile(r"không (nên|được phép)|mình khuyên bạn (không|nên)|bạn nên (chọn|bỏ|đổi|giữ)", re.I)
TOOL_LINE = re.compile(r"^([a-z_]+)(?::error.*)?$")
NOT_TOOLS = ("assistant", "step_cap", "cache_only", "guard_stop", "agent_error_after_acts")


def load_cases(path: Path = CASES, family: str | None = None, limit: int | None = None) -> list[dict]:
    cases = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]
    cases = [c for c in cases if family is None or c["family"] == family]
    return cases[:limit] if limit else cases


def fill(text: str, names: list[str]) -> str:
    """`{p1}` -> the name of the plan's first stop, and so on."""
    return re.sub(r"\{p(\d)\}", lambda m: names[int(m[1]) - 1] if int(m[1]) <= len(names) else m[0], text)


def tools_used(log: list[str]) -> set[str]:
    out = set()
    for x in log:
        if (m := TOOL_LINE.match(x.split(" [", 1)[0])) and m[1] not in NOT_TOOLS and not x.startswith(("say ", "schema_refused")):
            out.add(m[1])
    return out


def stop_names(view: dict) -> list[str]:
    """[p1, p2, p3, p4]: day 1's first two stops, day 2's first stop, day 1's last stop."""
    days = [[it["name"] for it in d["items"] if it["kind"] == "visit" and it.get("place_id")] for d in view["itinerary"]]
    d1, d2 = (days + [[], []])[:2]
    return [*d1[:2], *(d2[:1] or d1[2:3]), *(d1[-1:])]


def physical(view: dict) -> set[tuple]:
    return {(v["kind"], v.get("day"), v.get("place_id")) for v in view.get("violations") or [] if v.get("physical")}


def check(case: dict, before, after, row: dict) -> list[str]:
    """What this case's last turn got wrong (empty = pass)."""
    problems, say = [], row["say"]
    used = set(row["tools"])
    problems += [f"tool {t} not used (used: {sorted(used)})" for t in case.get("tools") or () if t not in used]
    for key, n in (case.get("expect") or {}).items():
        if key == "unchanged" and n and after.model_dump() != before.model_dump():
            problems.append("state changed")
        elif key == "changed" and n and after.model_dump() == before.model_dump():
            problems.append("state did not change")
        elif key == "locked" and len(after.locked) < n:
            problems.append(f"locked {len(after.locked)} < {n}")
        elif key == "dropped" and len(after.dropped) < n:
            problems.append(f"dropped {len(after.dropped)} < {n}")
        elif key == "pace" and after.pace_override != n:
            problems.append(f"pace {after.pace_override!r} != {n!r}")
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
           "unsourced": sum(r.get("unsourced", 0) for r in ran), "physical": sum(r.get("physical", 0) for r in ran),
           "blocking": sum(r.get("blocking", 0) for r in ran),
           "pass_by_family": {f: round(sum(v) / len(v), 2) for f, v in by_family.items()},
           "failed": [{"id": r["id"], "problems": r["problems"]} for r in ran if r["problems"]]}
    out["gate"] = bool(ran) and (not secs or (out["p50_s"] <= GATE["p50_s"] and out["p90_s"] <= GATE["p90_s"])) \
        and out["unsourced"] == 0 and out["physical"] == 0 and out["blocking"] == 0 \
        and all(v >= GATE["tool_min"] for v in out["pass_by_family"].values())
    return out


def build(trip: bool):
    """(engine, trip reader or None, a Decision Output the first confirmable hidden trip made). Real snapshot; AGENT_* from
    .env for --live."""
    from dotenv import load_dotenv

    import live
    from agents.assistant import ChatSettings, langchain_chat
    from corpus.serving import load as load_records

    from . import evaluate
    from .conditions import fetch_live
    from .engine import Engine
    from .session import Store
    from .settings import load

    load_dotenv(ROOT / ".env")
    cfg = load()
    records = load_records()
    configured = all(os.environ.get(k) for k in ("AGENT_API_KEY", "AGENT_BASE_URL", "AGENT_MODEL"))
    chat = langchain_chat(ChatSettings(total_s=cfg.total_s, max_tokens=cfg.assistant.get("max_tokens", 900), cache_key="planning_turn"))
    engine = Engine(records, cfg=cfg, live_cfg=live.load_settings(), store=Store(None), conditions_fn=fetch_live(live.load_settings()),
                    background=False, assistant=chat if configured else None)
    reader = None
    if trip:
        from trip import Tools as TripTools, create_engine
        data_root = Path(os.environ.get("DATA_DIR", "data"))
        tools = TripTools(create_engine(data_root if data_root.is_absolute() else ROOT / data_root))
        sid = tools.create({"experience": "first", "start_with": "nothing"})["id"]
        reader = lambda _s, text: tools.read_turn(sid, text)  # noqa: E731
    decision = next(out for _, out in evaluate.decision_outputs(records) if out and out["confirmed"])
    return engine, reader, decision


def start(engine, decision: dict) -> str:
    created = engine.create(decision)
    sid = created["id"]
    engine.act(sid, {"type": "pick_variant", "id": next(v["id"] for v in created["view"]["variants"] if v.get("status", "available") == "available")})
    return sid


def run_case(engine, reader, decision: dict, case: dict) -> dict:
    if case.get("trip") and reader is None:
        return {"id": case["id"], "family": case["family"], "skipped": "needs --trip"}
    engine.trip_reader = reader
    sid = start(engine, decision)
    view = engine.load(sid)["view"]
    names = stop_names(view)
    case = {**case, "reply_has": [fill(x, [re.escape(n) for n in names]) for x in case.get("reply_has") or ()]}
    row = {"id": case["id"], "family": case["family"], "seconds": None, "unsourced": 0, "physical": 0, "blocking": 0, "problems": []}
    start_physical = physical(view)
    before = after = engine._get(sid).state
    for text in case["turns"]:
        s = engine._get(sid)
        before, position = s.state.model_copy(deep=True), s.position
        started = time.monotonic()
        engine.turn(sid, fill(text, names), lambda *a: None, trip_session="0123456789ab" if reader else None)
        row["seconds"] = round(time.monotonic() - started, 2)
        after = engine._get(sid).state
        if engine._get(sid).position - position > 1:
            row["problems"].append(f"{engine._get(sid).position - position} versions in one turn")
    log = engine.turn_log.get(sid, [])
    row["unsourced"] = sum(1 for x in log if x.startswith(("say replaced: numbers", "say retry: numbers", "say pruned: numbers")))
    row["physical"] = len(physical(engine.load(sid)["view"]) - start_physical)
    say = engine._get(sid).chat[-1]["say"]
    row["blocking"] = 1 if BLOCKING.search(say) else 0
    row["say"], row["tools"], row["log"] = say, sorted(tools_used(log)), log
    row["problems"] += check(case, before, after, row)
    if row["physical"]:
        row["problems"].append("a physical violation the plan did not have")
    return row


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m planning bench")
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
    engine, reader, decision = build(args.trip)
    if engine.assistant is None:
        raise SystemExit("AGENT_API_KEY / AGENT_BASE_URL / AGENT_MODEL missing in .env")
    rows = [run_case(engine, reader, decision, c) for c in cases]
    print(json.dumps({"model": os.environ.get("AGENT_MODEL"), **report(rows), "rows": rows}, ensure_ascii=False, indent=1))
