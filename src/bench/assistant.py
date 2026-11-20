"""python -m bench assistant: the Trip chat's Đà Lạt assistant on 30 messages (spec 2026-10-26 §B.3.7, §2.4).

Each case is one new session seeded with the bench trip (2 adults, 2026-10-30 -> 2026-11-01, motorbike) and one
message. Measured per case: turn seconds, agent calls, the tool groups Clef + keywords prepared against the expected
ones (config/bench_assistant.yaml), numbers in the reply that no message, trip or tool result holds, places shown.
Tiers: offline (scripted agent, no Clef: the shape only), --clef (real Clef, a stub agent: groups and prepare time),
--live (real Agent and Clef: the enable gate). The gate: p50 <= 7.5 s, p90 <= 11 s, ungrounded == 0,
clef_full >= 29/30.

Case families (spec 2026-10-29-assistant-tools-design §6). The 30 cases above stay in config/bench_assistant.yaml. Every
other file config/bench_assistant_<name>.yaml (not `_guard`) adds cases in the v2 format, so each track writes its own file:

    cases:
      - id: followup-more              # optional, shown in the report
        family: followup               # the report counts tool-group accuracy per family
        turns:                         # one session, in order; a turn is a string or {text, photo}
          - "Gợi ý quán cà phê view đồi thông"
          - "Xem thêm kiểu vừa rồi đi"
        links: ["https://..."]         # optional: added to the text of the last turn
        tool_groups: [places]          # Tool.group of the tools the last turn ran (prepared or called by the model)
        cards: true                    # optional: the last turn shows a card (true) or none (false)
        tools: [browse_tags]           # optional: tools the last turn must call / must not call (tools_lack)
        block: tags                    # optional: the last turn sends a result block of this kind (tags | dish | services)
        level: subtags                 # optional, with block: tags: its level (tags = kinds of places, subtags = groups of one interest)
        photo_sure: false              # a photo turn: false = the reply names no place and asks back; true = it names `place`
        place: "Tên quán"              # with photo_sure: true
        reply_has: ["regex"]           # optional regexes the last reply must / must not match
        reply_lacks: ["regex"]
        blocked: R3                    # optional: the rule guard must stop the turn with this label (default: must not)
      - {id: shot, family: photo, turns: [{text: "quán này là gì", photo: tests/fixtures/perceive/app/plan-gate.png}], photo_sure: false}

A case whose photo file is missing is skipped and listed in the report. The guard set (config/bench_assistant_guard.yaml,
`--guard`) is checked against real Clef alone: wrong blocks, R1-R6 recall, exact labels. Model compare: `--model <id>`
sets AGENT_MODEL for the run (terra vs sol).
"""

from __future__ import annotations

import base64
import glob
import json
import os
import re
import time
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

import yaml

from trip import TripState, TurnInput

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "config" / "bench_assistant.yaml"
PREPARED = {"places", "detail", "weather", "distance", "trends"}  # groups the assistant prepares
NO_DATA = re.compile(r"(chưa|không) (có|thấy|biết)[^.?!]{0,30}(dữ liệu|thông tin)|chưa (thể )?(xác nhận|kiểm tra|kiểm chứng)", re.I)
GATE = {"p50_s": 7.5, "p90_s": 11.0, "ungrounded": 0, "clef_full": 29, "nodata_with_cards": 0,
        "photo_p90_s": 15.0, "photo_guesses": 0, "wrong_blocks": 0, "tool_group_min": 0.9, "rule_recall_min": 0.95}
TRIP_NUMBERS = {2026, 10, 30, 11, 1, 3, 2}  # the seeded trip: its dates, days and people may be said
GROUPS_LINE = re.compile(r"prefetch groups=([\w,-]+)")
CACHED = re.compile(r"cached_tokens (\d+)/(\d+)")
RULE_LINE = re.compile(r"rule_guard (R\d)")
GUARD_CASES = ROOT / "config" / "bench_assistant_guard.yaml"


def cases(path: Path = CASES) -> list[tuple[str, set[str]]]:
    return [(c["text"], set(c.get("groups") or ())) for c in yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]]


def seed() -> TripState:
    """The bench trip, in the user's own words: 2 adults, 30/10 to 1/11 (3 days), motorbike."""
    raw = TripState().model_dump(mode="json")
    ev = [{"turn": 1, "quote": "2 người lớn, 30/10 đến 1/11, xe máy"}]
    for name, value in (("start_date", "2026-10-30"), ("days", 3), ("people", 2), ("mobility", "motorbike")):
        raw[name] = {"value": value, "source": "user", "confidence": "high", "status": "confirmed", "evidence": ev}
    return TripState.model_validate(raw)


class Counted:
    """The engine's chat, counting model calls and timing each one."""

    def __init__(self, chat):
        self.chat, self.calls, self.seconds = chat, 0, []

    async def __call__(self, messages, tools, on_say):
        self.calls += 1
        started = time.monotonic()
        try:
            return await self.chat(messages, tools, on_say)
        finally:
            self.seconds.append(round(time.monotonic() - started, 2))


def _quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return round(s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))], 2) if s else 0.0


def empty_refusal(say: str, shown: list[str], catalog) -> bool:
    """The reply says "no data / not confirmed" while places are shown and it names none of them and says no number: a
    refusal that ignores what was found. A reply that names a place and says one field is unknown is grounded, not this."""
    if not shown or not NO_DATA.search(say) or re.search(r"\d", say):
        return False
    low = say.lower()
    return not any((p := catalog.by_id.get(pid)) is not None and p.name.lower() in low for pid in shown)


def run_case(engine, text: str, expected: set[str]) -> dict:
    sid = engine.create("first", "nothing")["id"]
    session = engine.store.get(sid)
    session.state = seed().model_copy(update={"meta": session.state.meta})
    counted = engine.chat = Counted(engine.chat if not isinstance(engine.chat, Counted) else engine.chat.chat)
    started = time.monotonic()
    engine.turn(sid, TurnInput(kind="text", text=text), lambda *a: None)
    seconds = time.monotonic() - started
    s = engine.store.get(sid)
    log = next((t["text"] for t in reversed(s.transcript) if t["role"] == "system"), "")
    say = next((t["text"] for t in reversed(s.transcript) if t["role"] == "agent" and t.get("kind") == "say"), "")
    m = GROUPS_LINE.search(log)
    groups = set() if not m or m[1] == "-" else set(m[1].split(","))
    said = {int(n) for n in re.findall(r"\d+", text)} | TRIP_NUMBERS | set(s.state.meta.told_numbers)
    extra = [n for n in re.findall(r"\d+", say) if int(n) not in said]
    return {"text": text, "seconds": round(seconds, 2), "calls": counted.calls, "expected": sorted(expected),
            "groups": sorted(groups), "clef_full": (expected & PREPARED) <= groups, "ungrounded": extra,
            "pruned": "say pruned" in log or "say replaced" in log, "shown": list(s.state.meta.shown_ids),
            "nodata_with_cards": empty_refusal(say, s.state.meta.shown_ids, engine.catalog),
            "say": say, "log": log, "call_s": counted.seconds,
            "other_s": round(max(0.0, seconds - sum(counted.seconds)), 2)}  # prefetch, tools, guards: not the model


@dataclass(frozen=True)
class Case:
    """One v2 case (see the module docstring): turns of one session and what the last turn must show."""
    id: str
    family: str
    turns: tuple[tuple[str, str | None], ...]  # (text, photo path or None)
    tool_groups: frozenset[str] = frozenset()
    cards: bool | None = None
    photo_sure: bool | None = None
    place: str = ""
    reply_has: tuple[str, ...] = ()
    reply_lacks: tuple[str, ...] = ()
    blocked: str = ""
    groups: frozenset[str] = frozenset()  # prepared groups (the 30-case metric)
    tools: frozenset[str] = frozenset()   # tools the last turn must call
    tools_lack: frozenset[str] = frozenset()  # ... must not call
    block: str = ""                        # a result block of this kind must come with the last turn ("!tags": must not)
    level: str = ""                        # with block: tags, the block's level (tags = kinds to open, subtags = groups of one interest)

    @property
    def photos(self) -> list[str]:
        return [p for _, p in self.turns if p]


def _turn(t) -> tuple[str, str | None]:
    return (t, None) if isinstance(t, str) else (str(t.get("text") or ""), t.get("photo"))


def load_cases(paths: list[Path] | None = None) -> list[Case]:
    """The v2 cases of config/bench_assistant_*.yaml (the guard set excluded), in file name order."""
    files = paths if paths is not None else sorted(Path(f) for f in glob.glob(str(ROOT / "config" / "bench_assistant_*.yaml"))
                                                    if not f.endswith("_guard.yaml"))
    out: list[Case] = []
    for f in files:
        for i, c in enumerate(yaml.safe_load(f.read_text(encoding="utf-8")).get("cases") or []):
            turns = [_turn(t) for t in (c.get("turns") or [c.get("text") or ""])]
            if c.get("links"):
                turns[-1] = (f"{turns[-1][0]} {' '.join(c['links'])}".strip(), turns[-1][1])
            out.append(Case(str(c.get("id") or f"{f.stem}-{i}"), str(c.get("family") or f.stem.removeprefix("bench_assistant_")),
                            tuple(turns), frozenset(c.get("tool_groups") or ()), c.get("cards"), c.get("photo_sure"),
                            str(c.get("place") or ""), tuple(c.get("reply_has") or ()), tuple(c.get("reply_lacks") or ()),
                            str(c.get("blocked") or ""), frozenset(c.get("groups") or ()), frozenset(c.get("tools") or ()),
                            frozenset(c.get("tools_lack") or ()), str(c.get("block") or ""), str(c.get("level") or "")))
    return out


def tools_called(log: str) -> list[str]:
    """Registered tool names in a turn's log line (a call, a cached repeat and an error all start with the name)."""
    from agents.assistant import REGISTRY
    return [seg.split()[0].rstrip(":") for seg in log.split("; ") if seg and REGISTRY.get(seg.split()[0].rstrip(":")) is not None]


def groups_of(names: list[str]) -> set[str]:
    from agents.assistant import REGISTRY
    return {t.group for n in names if (t := REGISTRY.get(n)) is not None and t.group}


def cached_pair(timings: list[str]) -> tuple[int, int]:
    """(prompt tokens the provider's cache served, prompt tokens) summed over the turn's model calls."""
    pairs = [CACHED.search(t) for t in timings]
    return sum(int(m[1]) for m in pairs if m), sum(int(m[2]) for m in pairs if m)


MIME = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}


def photo_b64(path: str) -> str:
    """The photo as the web sends it: a data URI (Trip's sanitize_photo accepts jpeg, png, webp)."""
    return f"data:image/{MIME[Path(path).suffix.lower()]};base64," + base64.b64encode((ROOT / path).read_bytes()).decode()


def names_in(say: str, catalog) -> list[str]:
    """Names of corpus places the text says."""
    low = say.lower()
    return [p.name for p in catalog.places if len(p.name) >= 4 and p.name.lower() in low]


def run_v2(engine, case: Case) -> dict:
    """One v2 case: a new seeded session, its turns in order; measured on the last turn."""
    sid = engine.create("first", "nothing")["id"]
    session = engine.store.get(sid)
    session.state = seed().model_copy(update={"meta": session.state.meta})
    counted = engine.chat = Counted(engine.chat if not isinstance(engine.chat, Counted) else engine.chat.chat)
    seconds, calls_before = 0.0, 0
    for text, photo in case.turns:
        calls_before = counted.calls
        started = time.monotonic()
        inp = TurnInput(kind="image", value=photo_b64(photo), text=text) if photo else TurnInput(kind="text", text=text)
        engine.turn(sid, inp, lambda *a: None)
        seconds = time.monotonic() - started
    s = engine.store.get(sid)
    sys_line = next((t for t in reversed(s.transcript) if t["role"] == "system"), {})
    log = sys_line.get("text", "")
    say = next((t["text"] for t in reversed(s.transcript) if t["role"] == "agent" and t.get("kind") == "say"), "")
    cards = [i for t in s.transcript if t.get("turn") == sys_line.get("turn") and t.get("kind") == "places" for i in t.get("ids", [])]
    called = tools_called(log)
    got = groups_of(called)
    rule = RULE_LINE.search(log)
    named = names_in(say, engine.catalog)
    cached, prompt = cached_pair(sys_line.get("timings", []))
    problems = []
    if case.blocked and (rule[1] if rule else "") != case.blocked:
        problems.append(f"expected block {case.blocked}")
    if not case.blocked and rule:
        problems.append(f"wrong block {rule[1]}")
    kinds = {(t.get("block") or {}).get("kind") for t in s.transcript if t.get("turn") == sys_line.get("turn") and t.get("kind") == "block"}
    if case.tools - set(called):
        problems.append(f"tool not called: {sorted(case.tools - set(called))}")
    if case.tools_lack & set(called):
        problems.append(f"tool called: {sorted(case.tools_lack & set(called))}")
    if case.block and (case.block.lstrip("!") in kinds) == case.block.startswith("!"):
        problems.append(f"block {case.block}: got {sorted(k for k in kinds if k)}")
    levels = {(t.get("block") or {}).get("level") for t in s.transcript if t.get("turn") == sys_line.get("turn") and t.get("kind") == "block"}
    if case.level and case.level not in levels:
        problems.append(f"block level {case.level}: got {sorted(k for k in levels if k)}")
    if case.cards is not None and bool(cards) != case.cards:
        problems.append("cards shown" if cards else "no card shown")
    for rx in case.reply_has:
        if not re.search(rx, say, re.I):
            problems.append(f"reply lacks /{rx}/")
    for rx in case.reply_lacks:
        if re.search(rx, say, re.I):
            problems.append(f"reply has /{rx}/")
    guess = case.photo_sure is False and bool(named or cards)  # an unsure photo must be asked back, never named
    if case.photo_sure is False and "?" not in say and not guess:
        problems.append("unsure photo not asked back")
    if case.photo_sure and case.place and case.place.lower() not in say.lower():
        problems.append(f"sure photo does not name {case.place}")
    said = {int(n) for t, _ in case.turns for n in re.findall(r"\d+", t)} | TRIP_NUMBERS | set(s.state.meta.told_numbers)
    extra = [n for n in re.findall(r"\d+", say) if int(n) not in said]
    return {"id": case.id, "family": case.family, "turns": [t for t, _ in case.turns], "photo": bool(case.photos), "seconds": round(seconds, 2),
            "calls": counted.calls - calls_before, "tools": called, "groups": sorted(got), "expected_groups": sorted(case.tool_groups),
            "tool_group_ok": case.tool_groups <= got, "shown": cards, "named": named, "photo_guess": guess,
            "wrong_block": bool(rule) and not case.blocked, "blocked": rule[1] if rule else "", "ungrounded": extra,
            "nodata_with_cards": empty_refusal(say, cards, engine.catalog), "cached": cached, "prompt_tokens": prompt,
            "problems": problems, "say": say, "log": log}


def summary_v2(rows: list[dict], skipped: list[str] | None = None) -> dict:
    secs = [r["seconds"] for r in rows if not r["photo"]]
    photo = [r["seconds"] for r in rows if r["photo"]]
    fams: dict[str, list[bool]] = {}
    for r in rows:
        if r["expected_groups"]:
            fams.setdefault(r["family"], []).append(r["tool_group_ok"])
    prompt = sum(r["prompt_tokens"] for r in rows)
    return {"cases": len(rows), "p50_s": _quantile(secs, 0.5), "p90_s": _quantile(secs, 0.9), "photo_p90_s": _quantile(photo, 0.9),
            "ungrounded": sum(bool(r["ungrounded"]) for r in rows), "nodata_with_cards": sum(r["nodata_with_cards"] for r in rows),
            "photo_guesses": sum(r["photo_guess"] for r in rows), "wrong_blocks": sum(r["wrong_block"] for r in rows),
            "tool_group_by_family": {f: round(sum(v) / len(v), 2) for f, v in sorted(fams.items())},
            "cached_ratio": round(sum(r["cached"] for r in rows) / prompt, 3) if prompt else None,
            "failed": [r["id"] for r in rows if r["problems"]], "skipped": skipped or []}


def passes_v2(s: dict) -> bool:
    return (s["p50_s"] <= GATE["p50_s"] and s["p90_s"] <= GATE["p90_s"] and s["photo_p90_s"] <= GATE["photo_p90_s"]
            and s["ungrounded"] <= GATE["ungrounded"] and s["nodata_with_cards"] <= GATE["nodata_with_cards"]
            and s["photo_guesses"] <= GATE["photo_guesses"] and s["wrong_blocks"] <= GATE["wrong_blocks"]
            and all(v >= GATE["tool_group_min"] for v in s["tool_group_by_family"].values()))


def runnable(items: list[Case]) -> tuple[list[Case], list[str]]:
    """Cases whose photo files exist; the others are skipped by name (a fixture missing is not a failed case)."""
    have = [c for c in items if all((ROOT / p).is_file() for p in c.photos)]
    return have, [c.id for c in items if c not in have]


def run_guard_set(ask, threshold: float, path: Path = GUARD_CASES, workers: int = 4) -> dict:
    """The labelled guard sentences against Clef alone: wrong blocks of ok sentences, R1-R6 recall, exact labels."""
    from concurrent.futures import ThreadPoolExecutor

    from agents.assistant import check_rules
    from agents.assistant.guard import BLOCKS
    items = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]

    def one(c):
        return check_rules(ask, c["text"], prev_user=c.get("prev", ""), prev_reply=c.get("reply", ""), shown=c.get("shown", ()), threshold=threshold)
    with ThreadPoolExecutor(workers) as ex:
        verdicts = list(ex.map(one, items))
    rows = [{"text": c["text"], "label": c["label"], "got": v.label, "prob": round(v.prob, 2)} for c, v in zip(items, verdicts)]
    ok = [r for r in rows if r["label"] == "ok"]
    rule = [r for r in rows if r["label"] in BLOCKS]
    wrong = [r for r in ok if r["got"] != "ok"]
    recall = sum(r["got"] in BLOCKS for r in rule) / len(rule) if rule else 1.0
    return {"sentences": len(rows), "threshold": threshold, "wrong_blocks": len(wrong), "rule_recall": round(recall, 3),
            "exact": sum(r["got"] == r["label"] for r in rows), "wrong": wrong,
            "missed": [r for r in rule if r["got"] not in BLOCKS],
            "passes": not wrong and recall >= GATE["rule_recall_min"]}


def summary(rows: list[dict]) -> dict:
    secs = [r["seconds"] for r in rows]
    calls = [r["calls"] for r in rows]
    return {"cases": len(rows), "p50_s": _quantile(secs, 0.5), "p90_s": _quantile(secs, 0.9),
            "calls_per_turn": round(sum(calls) / len(calls), 2) if calls else 0.0,
            "single_call_rate": round(sum(c == 1 for c in calls) / len(calls), 2) if calls else 0.0,
            "clef_full": sum(r["clef_full"] for r in rows), "ungrounded": sum(bool(r["ungrounded"]) for r in rows),
            "nodata_with_cards": sum(r["nodata_with_cards"] for r in rows),
            "pruned": sum(r["pruned"] for r in rows), "shown_turns": sum(bool(r["shown"]) for r in rows)}


def passes(s: dict) -> bool:
    return (s["p50_s"] <= GATE["p50_s"] and s["p90_s"] <= GATE["p90_s"] and s["ungrounded"] <= GATE["ungrounded"]
            and s["clef_full"] >= GATE["clef_full"]
            and s["nodata_with_cards"] <= GATE["nodata_with_cards"])


def run(engine, items: list[tuple[str, set[str]]]) -> tuple[list[dict], dict]:
    rows = [run_case(engine, text, expected) for text, expected in items]
    return rows, summary(rows)


def _stub_chat():
    """--clef: an agent that answers at once without tools, so only Clef and the prepared tools are timed."""
    from langchain_core.messages import AIMessageChunk

    async def chat(messages, tools, on_say):
        text = "Tham khảo: mình xem dữ liệu rồi trả lời bạn nhé."
        on_say(text)
        return AIMessageChunk(content=text)
    return chat


def assistant_overrides(raw: str, base) -> dict:
    """`BENCH_ASSISTANT_SET="covered_tools=all,hide_prepared_lookup=false"` -> typed Assistant field overrides (a bench
    run can compare two settings without editing config/trip.yaml)."""
    out = {}
    for part in filter(None, (x.strip() for x in raw.split(","))):
        key, _, val = part.partition("=")
        key, val = key.strip(), val.strip()
        if not hasattr(base, key):
            raise ValueError(f"unknown assistant setting {key!r}")
        cur = getattr(base, key)
        out[key] = (val.lower() in ("1", "true", "yes", "on")) if isinstance(cur, bool) else type(cur)(val)
    return out


def engine_for(tier: str):
    """A Trip engine on the active corpus release with the assistant on; live weather and travel time."""
    import live
    from harness import trip_live_tools
    from trip import create_engine
    data = ROOT / "data"
    engine = create_engine(data, live=trip_live_tools(live.load_settings()))
    engine.cfg = replace(engine.cfg, assistant=replace(engine.cfg.assistant, enabled=True,
                         **assistant_overrides(os.environ.get("BENCH_ASSISTANT_SET", ""), engine.cfg.assistant)))
    if tier != "live":
        engine.chat = _stub_chat()
    if tier == "offline":
        engine.judge = None  # no Clef: the keyword rules alone, nothing leaves the machine
    return engine


def guard_main(out: Path | None = None) -> int:
    """--guard: the labelled set against real Clef at the configured threshold."""
    from trip import clef_ask, load_settings
    cfg = load_settings()
    result = run_guard_set(lambda st, qs: clef_ask(st, qs, cfg), cfg.assistant.guard_threshold)
    out = out or ROOT / "data" / "bench" / "assistant" / f"{datetime.now():%Y%m%d-%H%M%S}-guard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("wrong", "missed")}, ensure_ascii=False))
    print(f"wrote {out}")
    return 0 if result["passes"] else 1


def main(tier: str, out: Path | None = None, family: str = "", model: str = "", legacy: bool = True) -> int:
    """tier: offline | clef | live. family: only the v2 cases of that family ("legacy" = only the 30 legacy messages). model: Agent model id for this run."""
    if model:
        os.environ["AGENT_MODEL"] = model
    engine = engine_for(tier)
    started = time.monotonic()
    engine.warmed.wait(900)  # timed like a user after the start has warmed the search (api/tools.warm_assistant)
    print(f"warm {time.monotonic() - started:.1f}s", flush=True)
    items, skipped = runnable([c for c in load_cases() if not family or c.family == family])
    rows, s = run(engine, cases()) if legacy and family in ("", "legacy") else ([], {})
    rows2 = [run_v2(engine, c) for c in items]
    s2 = summary_v2(rows2, skipped) if rows2 or skipped else {}
    out = out or ROOT / "data" / "bench" / "assistant" / f"{datetime.now():%Y%m%d-%H%M%S}-{tier}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    ok = (passes(s) if s else True) and (passes_v2(s2) if s2 else True)
    out.write_text(json.dumps({"tier": tier, "model": os.environ.get("AGENT_MODEL", ""), "date": date.today().isoformat(), "summary": s,
                               "summary_v2": s2, "gate": GATE, "passes": ok if tier == "live" else None,
                               "rows": rows, "rows_v2": rows2}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False))
    if s2:
        print(json.dumps(s2, ensure_ascii=False))
    print(f"wrote {out}")
    return 0 if tier != "live" or ok else 1
