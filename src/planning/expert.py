"""D.2 Local Expert: one LLM pass after the validator (docs/PLANNING.md §Local Expert).

It reads facts the code hands it (the place's season months, events, calendar days, kept LocalClaims, the plan's own
warnings) and answers findings {slot_ref, message, suggestion}. The model is never a judge and never a source:
a finding stands only when its slot exists and every fact it cites was in the prompt; a repair it hints at runs
through the same validator as any edit (`trial`) and is only offered, never applied. Failure, timeout or an empty
answer leaves the plan exactly as it was. Weather the tool gate doubts goes to the model labelled "nghi ngờ".
"""

import asyncio
import json
from datetime import date as _d

from .settings import Settings

GENERAL_KINDS = ("season", "event", "crowded_at", "best_time", "if_rain")   # city-wide claims that depend on the date

FACT_STATUS = ("kept", "confirmed")      # LocalClaim statuses that are facts (corpus.retrieval.local); the rest is only reference

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["findings"],
    "properties": {"findings": {"type": "array", "maxItems": 6, "items": {
        "type": "object", "additionalProperties": False,
        "required": ["slot_ref", "message", "suggestion", "cites", "fix", "fix_day"],
        "properties": {
            "slot_ref": {"type": "string"},
            "message": {"type": "string"},
            "suggestion": {"type": "string"},
            "cites": {"type": "array", "items": {"type": "string"}},
            "fix": {"type": "string", "enum": ["none", "move", "drop"]},
            "fix_day": {"type": ["integer", "null"]}}}}}}

PROMPT = """You are a local expert on {city} reviewing a travel plan that a validator already accepted.
Report only things a local would warn the traveller about, and ONLY from the FACTS below: a flower season that is
over or has not started on the visit date, a festival or holiday that changes crowds or opening hours, weather the
facts mark as reliable, a kept local claim that applies to a stop. Never use knowledge outside the facts. Never invent
a place, a time, a price or an opening hour. If a fact is marked "nghi ngờ" do not rely on it. If nothing is worth
saying, return {{"findings": []}}.
For each finding: slot_ref = one of the SLOTS refs; message = one short Vietnamese sentence the traveller reads
(no source names, no jargon); suggestion = one short Vietnamese sentence on what to do; cites = the ids of the FACTS
the finding rests on (at least one, copied exactly); fix = "move" (to day fix_day) or "drop" only when that clearly
solves it, else "none" with fix_day null.
At most 6 findings, the most useful first.

TRIP: {trip}
SLOTS: {slots}
FACTS: {facts}
"""


def _slot_ref(day: int, place_id: str) -> str:
    return f"d{day}:{place_id}"


def slots_of(plan: dict) -> dict[str, dict]:
    """{slot_ref: {day, date, place_id, name, start, end}} of every visit of the itinerary."""
    out = {}
    for d in plan.get("itinerary") or []:
        for it in d.get("items") or []:
            if it.get("kind") == "visit" and it.get("place_id"):
                out[_slot_ref(d["day"], it["place_id"])] = {
                    "day": d["day"], "date": d.get("date"), "place_id": it["place_id"],
                    "name": it.get("name") or it["place_id"], "start": it.get("start"), "end": it.get("end")}
    return out


# ---------- tool gate: a weather figure we do not trust ----------

def doubts(w: dict | None, normal: dict | None, cfg: Settings) -> list[str]:
    """Reasons a daily weather figure is "nghi ngờ" (empty = fine or unknown): outside the physical range, far from the
    month's ClimateNormal, or the two Open-Meteo models disagree. A doubtful figure is shown to the model as such and
    is never a fact; missing figures are not a doubt."""
    if not w:
        return []
    g, out = cfg.expert["gate"], []
    p, mm, gust = w.get("rain_prob"), w.get("rain_mm"), w.get("gust_kmh")
    if (p is not None and not 0 <= p <= 1) or (mm is not None and not 0 <= mm <= g["max_rain_mm"]) \
            or (gust is not None and not 0 <= gust <= g["max_gust_kmh"]):
        out.append("ngoài miền vật lý")
    if p is not None and normal and normal.get("rain_prob") is not None and abs(p - normal["rain_prob"]) >= g["normal_gap"]:
        out.append("lệch xa mức thường của tháng")
    if w.get("disagree"):
        out.append("hai model dự báo lệch nhau")
    return out


# ---------- facts ----------

def _named(subject: str, slots: dict) -> bool:
    """Every word of the claim's subject is in the name of some stop (casefolded): the claim is about that stop."""
    words = set((subject or "").casefold().split())
    return bool(words) and any(words <= set(s["name"].casefold().split()) for s in slots.values())


def facts_for(plan: dict, records: dict, *, weather: dict | None, events: dict, holidays: dict, calendar: list | None,
              normals: dict | None, claims: list[dict], notes: list[dict], cfg: Settings) -> tuple[dict, dict]:
    """(facts, allowed): facts = {fact id: {...}} shown to the model; allowed = {fact id: [doc_id]} (doc ids a claim
    fact stands on, [] for a fact from code). Only kept claims, and only those whose months hold a day of the trip."""
    from .details import timing
    facts, allowed = {}, {}
    cal = {c["date"]: c for c in calendar or []}
    slots = slots_of(plan)
    months = {_d.fromisoformat(s["date"]).month for s in slots.values() if s.get("date")}
    for d in plan.get("itinerary") or []:
        if not d.get("date"):
            continue
        day = _d.fromisoformat(d["date"])
        for ev in events.get(day, []):
            facts[f"event:{d['date']}:{ev['name']}"] = {"date": d["date"], "event": ev["name"], "crowd": ev.get("crowd"),
                                                       "shops_may_close": bool(ev.get("closure_risk"))}
        if name := holidays.get(day) or (cal.get(d["date"]) or {}).get("holiday"):
            facts[f"holiday:{d['date']}"] = {"date": d["date"], "holiday": name}
        w = (weather or {}).get(d["date"])
        if w:
            normal = (normals or {}).get(str(day.month))
            bad = doubts(w, normal, cfg)
            facts[f"weather:{d['date']}"] = {
                "date": d["date"], "rain_prob": w.get("rain_prob"), "rain_mm": w.get("rain_mm"),
                "gust_kmh": w.get("gust_kmh"), "storm": w.get("storm"), **({"nghi ngờ": bad} if bad else {})}
    for ref, s in slots.items():
        t = timing(records.get(s["place_id"]) or {})
        month = _d.fromisoformat(s["date"]).month if s.get("date") else None
        if month and (t.get("best_months") or t.get("avoid_months")):
            facts[f"season:{s['place_id']}"] = {"place": s["name"], "visit_month": month,
                                                "best_months": t.get("best_months") or [],
                                                "avoid_months": t.get("avoid_months") or []}
    wet = any((f.get("rain_prob") or 0) >= cfg.expert["wet_prob"] and "nghi ngờ" not in f
              for k, f in facts.items() if k.startswith("weather:"))
    for c in claims:
        if c.get("status") not in FACT_STATUS:
            continue
        cm = c.get("months") or (c.get("when") or {}).get("months") or []
        named = _named(c["subject"], slots)
        if not named and (c.get("subject_kind") not in ("city", "area") or c.get("kind") not in GENERAL_KINDS):
            continue            # about a flower, dish, tip or place no stop is: the model would pin it on a wrong stop
        if cm and months and not set(cm) & months and not (named and c.get("kind") == "season"):
            continue            # (a season of a stop's own flower stays even out of season: that is the warning)
        if (c.get("when") or {}).get("weather") and not wet:
            continue            # "if it rains ...": only on a trip with reliable heavy-rain weather
        cid = f"claim:{c['claim_id']}"
        facts[cid] = {"kind": c["kind"], "subject": c["subject"], "text": (c.get("text") or "")[:240],
                      "months": cm, "weather": (c.get("when") or {}).get("weather") or None}
        allowed[cid] = [e["doc_id"] for e in c.get("evidence") or [] if e.get("doc_id")]
    for i, n in enumerate(notes):
        facts[f"note:{i}"] = {"note": n.get("text") or n.get("code")}
    for fid in facts:
        allowed.setdefault(fid, [])
    return facts, allowed


# ---------- the gate on the model's answer ----------

def gate(answer: dict, slots: dict, allowed: dict, cfg: Settings) -> list[dict]:
    """Keep a finding only when its slot is in the plan, it has a message and a suggestion, and every id it cites was
    in the prompt (at least one). `docs` = the doc ids the cited claims stand on. Dropped silently: the model is
    not a source."""
    e, out, seen = cfg.expert, [], set()
    for f in (answer or {}).get("findings") or []:
        ref, msg, sug = f.get("slot_ref"), (f.get("message") or "").strip(), (f.get("suggestion") or "").strip()
        cites = [c for c in f.get("cites") or [] if isinstance(c, str)]
        if ref not in slots or not msg or not sug or len(msg) > e["max_chars"] or len(sug) > e["max_chars"]:
            continue
        if not cites or any(c not in allowed for c in cites) or (ref, msg) in seen:
            continue
        seen.add((ref, msg))
        out.append({"slot_ref": ref, "message": msg, "suggestion": sug, "cites": cites,
                    "docs": sorted({d for c in cites for d in allowed[c]}), "fix": f.get("fix") or "none",
                    "fix_day": f.get("fix_day")})
    return out[: e["max_findings"]]


def repair(findings: list[dict], slots: dict, trial, must: frozenset | set = frozenset()) -> list[dict]:
    """The model's hint ("move" to a day / "drop") as engine actions, run through `trial` (the same validator as any
    edit). Offered as `actions` only when the result is confirmable; otherwise the finding stays a note. Nothing is
    applied here. A trial that raises is a note too (fail-closed). A must-go place (`must`) is never offered a drop
    or a move: the user said they will go there."""
    out = []
    for f in findings:
        s, actions = slots[f["slot_ref"]], None
        if s["place_id"] in must:
            f = {**f, "fix": "none"}
        if f["fix"] == "move" and isinstance(f["fix_day"], int) and f["fix_day"] != s["day"]:
            actions = [{"type": "move_place", "place": s["place_id"], "day": f["fix_day"] - 1}]
        elif f["fix"] == "drop":
            actions = [{"type": "drop_place", "place": s["place_id"]}]
        ok = False
        if actions and trial is not None:
            try:
                ok = bool(trial(actions)["confirmable"])
            except Exception:
                ok = False
        out.append({**{k: v for k, v in f.items() if k not in ("fix", "fix_day")}, **({"actions": actions} if ok else {})})
    return out


# ---------- the one model pass ----------

async def _ask(prompt_fields: dict, cfg: Settings, client_fn) -> dict:
    from corpus.llm import EXTRACTOR, Task
    task = Task(name="local_expert", role=EXTRACTOR, prompt=PROMPT, schema=SCHEMA, max_tokens=cfg.expert["max_tokens"])
    client, model = client_fn()
    try:
        return await task.ask(client, model, **prompt_fields)
    finally:
        await client.close()


def _lan():
    from corpus.llm import EXTRACTOR
    return EXTRACTOR.client()


def _uit():
    from corpus.llm import Role
    return Role.uit_client()


async def _pass(fields: dict, cfg: Settings, ask) -> dict:
    """LAN Gemma first (Extractor role), UIT Gemma when it errors or runs out the time."""
    ask = ask or _ask
    half = cfg.expert["timeout_s"]
    try:
        return await asyncio.wait_for(ask(fields, cfg, _lan), half)
    except Exception:
        return await asyncio.wait_for(ask(fields, cfg, _uit), half)


def review(plan: dict, records: dict, *, trip: dict, weather: dict | None, events: dict, holidays: dict,
           calendar: list | None, normals: dict | None, claims: list[dict], trial=None, cfg: Settings, ask=None,
           city: str = "Đà Lạt", must: frozenset | set = frozenset()) -> dict:
    """{"status": ok | off | skipped | failed, "findings": [...]}. Never raises, never longer than twice
    expert.timeout_s plus the validator trials; a failure leaves findings empty (the plan stands)."""
    if not cfg.expert.get("enabled"):
        return {"status": "off", "findings": []}
    slots = slots_of(plan)
    notes = [w for w in plan.get("warnings") or [] if w.get("text")]
    facts, allowed = facts_for(plan, records, weather=weather, events=events, holidays=holidays, calendar=calendar,
                               normals=normals, claims=claims, notes=notes, cfg=cfg)
    if not slots or not facts:
        return {"status": "skipped", "findings": []}
    fields = {"city": city, "trip": json.dumps(trip, ensure_ascii=False),
              "slots": json.dumps({r: {k: s[k] for k in ("day", "date", "name", "start", "end")} for r, s in slots.items()},
                                  ensure_ascii=False),
              "facts": json.dumps(facts, ensure_ascii=False)}
    try:
        answer = asyncio.run(_pass(fields, cfg, ask))
    except Exception as exc:
        return {"status": "failed", "findings": [], "error": type(exc).__name__}
    return {"status": "ok", "findings": repair(gate(answer, slots, allowed, cfg), slots, trial, must)}


def as_warnings(findings: list[dict], slots: dict) -> list[dict]:
    """The plan warnings a finding becomes: code local_expert, the message the traveller reads, and (when the
    validator approved a repair) the actions to offer."""
    return [{"code": "local_expert", "text": f"{slots[f['slot_ref']]['name']}: {f['message']} {f['suggestion']}".strip(),
             "day": slots[f["slot_ref"]]["day"], "place_id": slots[f["slot_ref"]]["place_id"], "cites": f["cites"],
             "docs": f["docs"], **({"actions": f["actions"]} if f.get("actions") else {})} for f in findings]


def load_inputs(live_cfg, city: str, dates: list[str], cfg: Settings) -> dict:
    """The I/O edge: events / holidays from live, CalendarDay and ClimateNormal views, kept LocalClaims of the city.
    A source that is missing or fails is simply absent (unknown)."""
    import live
    from corpus.views import calendar_days, climate_normals
    days = [_d.fromisoformat(x) for x in dates]
    out = {"events": {}, "holidays": {}, "calendar": None, "normals": None, "claims": []}
    for key, fn in (("events", lambda: live.events(days)), ("holidays", lambda: live.holidays(days)),
                    ("calendar", lambda: calendar_days(city)), ("normals", lambda: climate_normals(city))):
        try:
            out[key] = fn()
        except Exception:
            pass
    try:
        from corpus.local import local_dir
        doc = json.loads((local_dir(city) / "local_claims.json").read_text(encoding="utf-8"))
        out["claims"] = [c for c in doc.get("claims") or [] if c.get("status") in FACT_STATUS]
    except Exception:
        pass
    return out


def findings_for(engine, sid: str, plan: dict) -> dict:
    """The review of one confirmed plan whose Planning session is in engine: {"status", "findings"}. Never raises."""
    cfg = engine.cfg
    if not cfg.expert.get("enabled"):
        return {"status": "off", "findings": []}
    try:
        s = engine._get(sid)
        ctx = s.decision["trip_context"]["context"]
        dates = [d["date"] for d in plan.get("itinerary") or [] if d.get("date")]
        if not dates:
            return {"status": "skipped", "findings": []}
        inputs = load_inputs(engine.live_cfg, getattr(engine.live_cfg, "views_city", "dalat"), dates, cfg)
        weather = getattr(engine._ensure_base(sid).trip, "weather", None)
        return review(plan, engine.by_id, trip={"days": ctx.get("days"), "start_date": ctx.get("start_date"),
                                                "companions": ctx.get("companions"), "mobility": ctx.get("mobility")},
                      weather=weather, trial=lambda acts: engine.eve_trial(sid, acts), cfg=cfg,
                      must={c["id"] for c in s.decision.get("confirmed") or [] if c.get("role") == "anchor"}, **inputs)
    except Exception as exc:
        return {"status": "failed", "findings": [], "error": type(exc).__name__}


def annotate(engine, sid: str, plan: dict) -> dict:
    """The plan with the Local Expert's findings added to its warnings (the plan keeps every other field). Synchronous;
    the product no longer calls it at confirm (run_expert does it in the background), kept for tools and tests."""
    out = findings_for(engine, sid, plan)
    if out["findings"]:
        return {**plan, "warnings": [*(plan.get("warnings") or []), *as_warnings(out["findings"], slots_of(plan))]}
    return plan


def as_notes(findings: list[dict], slots: dict) -> list[dict]:
    """The eve notes a finding becomes (what the plan screen lists as good to know): {date, place_id, name, level 1,
    factor local_expert, text}. A repair is not offered here: the evening check owns the change flow."""
    return [{"date": slots[f["slot_ref"]]["date"], "place_id": slots[f["slot_ref"]]["place_id"],
             "name": slots[f["slot_ref"]]["name"], "level": 1, "factor": "local_expert",
             "text": f"{f['message']} {f['suggestion']}".strip()} for f in findings]


def run_expert(engine, snapshot: dict, plan: dict, *, journey: str, plan_hash: str, store_root) -> int | None:
    """The Local Expert for one confirmed journey, in the background (notify worker), never in front of the user.
    Restores its Planning session, reviews, keeps the findings as eve notes of this plan_hash. Runs once per plan; a
    failed pass is retried up to expert.retries times. Returns the number of notes saved, None when nothing was run."""
    from .eve import Store
    from .session import Session
    cfg = engine.cfg
    store = Store(store_root)
    done = store.expert(journey, plan_hash)
    if done and (done.get("status") != "failed" or done.get("tries", 1) >= cfg.expert.get("retries", 3)):
        return None
    session = Session.model_validate(snapshot)
    engine.store.restore(session)
    engine._base.pop(session.id, None)
    engine._schedules.pop(session.id, None)
    out = findings_for(engine, session.id, plan)
    notes = as_notes(out["findings"], slots_of(plan))
    store.save_expert(journey, plan_hash, {"status": out["status"], "tries": done.get("tries", 0) + 1}, notes)
    return len(notes)


def expert_runner(records: list[dict], live_cfg, store_root, cfg: Settings | None = None):
    """For the notify worker: (journey, snapshot, plan, plan_hash) -> run_expert(...), one Engine over the served records;
    None while config/planning.yaml expert.enabled is false."""
    from .conditions import fetch_live
    from .engine import Engine
    from .session import Store as SessionStore
    from .settings import load
    cfg = cfg or load()
    if not cfg.expert.get("enabled"):
        return None
    engine = Engine(list(records), cfg=cfg, live_cfg=live_cfg, store=SessionStore(None),
                    conditions_fn=fetch_live(live_cfg), background=False)
    return lambda journey, snap, plan, plan_hash: run_expert(
        engine, snap, plan, journey=journey, plan_hash=plan_hash, store_root=store_root)
