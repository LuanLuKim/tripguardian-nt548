"""D.2 Local Expert: facts in, gated findings out, the model never a source (docs/PLANNING.md §Local Expert)."""

import asyncio
from dataclasses import replace
from datetime import date

from planning import expert
from plan_fixtures import CFG, rec

ON = replace(CFG, expert={**CFG.expert, "enabled": True})
DATE = "2026-12-20"
PLAN = {"itinerary": [{"day": 1, "date": DATE, "items": [
            {"kind": "visit", "place_id": "garden", "name": "Vườn hoa", "start": "09:00", "end": "11:00"},
            {"kind": "visit", "place_id": "cafe", "name": "Quán cà phê", "start": "14:00", "end": "15:00"}]}],
        "warnings": [{"code": "x", "text": "Một lưu ý có sẵn."}]}
RECS = {"garden": rec("garden", 11.9, 108.4), "cafe": rec("cafe", 11.91, 108.41)}
CLAIM = {"claim_id": "c1", "status": "kept", "subject_kind": "city", "kind": "season", "subject": "Dã quỳ", "text": "nở từ tháng 11 đến tháng 12",
         "months": [11, 12], "when": {"months": [11, 12], "weather": ""}, "evidence": [{"doc_id": "doc-a", "quote": "q"}]}
OTHER = {**CLAIM, "claim_id": "c2", "months": [3], "when": {"months": [3]}}
UNVER = {**CLAIM, "claim_id": "c3", "status": "unverified"}


def run(answer, *, claims=(CLAIM,), trial=None, cfg=ON, weather=None, **kw):
    async def ask(fields, cfg, client_fn):
        ask.fields = fields
        if isinstance(answer, Exception):
            raise answer
        return answer
    out = expert.review(PLAN, RECS, trip={"month": 12}, weather=weather, events={}, holidays={date(2026, 12, 20): "Lễ"},
                        calendar=None, normals=None, claims=list(claims), trial=trial, cfg=cfg, ask=ask, **kw)
    return out, ask


def finding(**kw):
    return {"slot_ref": "d1:garden", "message": "Dã quỳ đã hết mùa.", "suggestion": "Đi nơi khác.",
            "cites": ["claim:c1"], "fix": "none", "fix_day": None, **kw}


def test_only_kept_claims_of_the_trip_months_reach_the_model():
    out, ask = run({"findings": []}, claims=(CLAIM, OTHER, UNVER))
    assert "claim:c1" in ask.fields["facts"] and "claim:c2" not in ask.fields["facts"] and "claim:c3" not in ask.fields["facts"]
    assert "holiday:2026-12-20" in ask.fields["facts"] and out["status"] == "ok" and out["findings"] == []


def test_a_finding_stands_with_its_doc_ids_and_becomes_a_warning():
    out, _ = run({"findings": [finding()]})
    f = out["findings"][0]
    assert f["docs"] == ["doc-a"] and f["cites"] == ["claim:c1"] and "actions" not in f
    w = expert.as_warnings(out["findings"], expert.slots_of(PLAN))[0]
    assert w["code"] == "local_expert" and w["place_id"] == "garden" and w["text"].startswith("Vườn hoa:")


def test_invented_slots_and_citations_are_dropped():
    bad = [finding(slot_ref="d1:invented"), finding(cites=["claim:zzz"]), finding(cites=[]), finding(message="  "),
           finding(cites=["claim:c1", "claim:zzz"])]
    assert run({"findings": bad})[0]["findings"] == []


def test_a_repair_is_offered_only_when_the_validator_accepts_it():
    seen = []

    def trial(actions):
        seen.append(actions)
        return {"confirmable": actions[0]["type"] == "move_place"}
    out, _ = run({"findings": [finding(fix="move", fix_day=2), finding(message="Khác.", fix="drop")]}, trial=trial)
    assert out["findings"][0]["actions"] == [{"type": "move_place", "place": "garden", "day": 1}]
    assert "actions" not in out["findings"][1] and len(seen) == 2

    def boom(actions):
        raise RuntimeError("no")
    assert "actions" not in run({"findings": [finding(fix="drop")]}, trial=boom)[0]["findings"][0]


def test_a_failing_model_leaves_the_plan_alone_and_the_flag_turns_it_off():
    out, _ = run(RuntimeError("down"))
    assert out == {"status": "failed", "findings": [], "error": "RuntimeError"}
    assert run({"findings": [finding()]}, cfg=replace(CFG, expert={**CFG.expert, "enabled": False}))[0] == {"status": "off", "findings": []}


def test_a_slow_model_is_cut_off_at_the_timeout():
    tight = replace(ON, expert={**ON.expert, "timeout_s": 0.05})

    async def slow(fields, cfg, client_fn):
        await asyncio.sleep(1)
    out = expert.review(PLAN, RECS, trip={}, weather=None, events={}, holidays={date(2026, 12, 20): "Lễ"}, calendar=None,
                        normals=None, claims=[CLAIM], cfg=tight, ask=slow)
    assert out["status"] == "failed" and out["findings"] == []


def test_the_tool_gate_marks_doubtful_weather_and_the_model_sees_the_mark():
    normal = {"rain_prob": 0.1}
    assert expert.doubts({"rain_prob": 1.4}, normal, ON) == ["ngoài miền vật lý", "lệch xa mức thường của tháng"]
    assert expert.doubts({"rain_mm": 900}, None, ON) == ["ngoài miền vật lý"]
    assert expert.doubts({"rain_prob": 0.95}, normal, ON) == ["lệch xa mức thường của tháng"]
    assert expert.doubts({"rain_prob": 0.3, "disagree": True}, normal, ON) == ["hai model dự báo lệch nhau"]
    assert expert.doubts({"rain_prob": 0.15, "rain_mm": 1}, normal, ON) == [] and expert.doubts(None, normal, ON) == []
    _, ask = run({"findings": []}, weather={DATE: {"rain_prob": 0.9, "rain_mm": 3, "disagree": True}})
    assert "nghi ngờ" in ask.fields["facts"]


def test_annotate_is_a_no_op_while_the_flag_is_off_and_never_raises():
    class E:
        cfg = CFG

    plan = {"itinerary": [], "warnings": []}
    assert expert.annotate(E(), "sid", plan) is plan

    class Broken:
        cfg = ON
    assert expert.annotate(Broken(), "sid", plan) is plan          # no engine attributes: swallowed, the plan stands


def test_a_season_claim_naming_a_stop_reaches_the_model_even_out_of_season():
    plan = {"itinerary": [{"day": 1, "date": "2026-03-14", "items": [
        {"kind": "visit", "place_id": "garden", "name": "Đồi Dã quỳ", "start": "09:00", "end": "10:00"}]}], "warnings": []}
    seen = {}

    async def ask(fields, cfg, client_fn):
        seen.update(fields)
        return {"findings": []}
    expert.review(plan, RECS, trip={}, weather=None, events={}, holidays={}, calendar=None, normals=None,
                  claims=[CLAIM, {**CLAIM, "claim_id": "c9", "subject": "hoa khác"}], cfg=ON, ask=ask)
    assert "claim:c1" in seen["facts"] and "claim:c9" not in seen["facts"]


def test_claims_about_something_no_stop_is_and_rain_claims_on_dry_days_stay_out():
    stray = {**CLAIM, "claim_id": "s1", "subject_kind": "phenomenon", "subject": "Dã quỳ", "months": [12], "when": {"months": [12]}}
    rain = {**CLAIM, "claim_id": "r1", "months": [], "when": {"months": [], "weather": "rainy"}}
    out, ask = run({"findings": []}, claims=(stray, rain))
    assert "claim:s1" not in ask.fields["facts"] and "claim:r1" not in ask.fields["facts"]
    _, ask = run({"findings": []}, claims=(stray, rain), weather={DATE: {"rain_prob": 0.9, "rain_mm": 8.0}})
    assert "claim:r1" in ask.fields["facts"] and "claim:s1" not in ask.fields["facts"]


def test_a_must_go_place_is_never_offered_a_drop_or_a_move():
    def trial(actions):
        return {"confirmable": True}
    out = expert.review(PLAN, RECS, trip={}, weather=None, events={}, holidays={date(2026, 12, 20): "Lễ"}, calendar=None,
                        normals=None, claims=[CLAIM], trial=trial, cfg=ON, must={"garden"},
                        ask=lambda *a: _answer({"findings": [finding(fix="drop"), finding(message="Khác.", slot_ref="d1:cafe", fix="drop")]}))
    assert "actions" not in out["findings"][0] and out["findings"][1]["actions"][0]["place"] == "cafe"


async def _answer(x):
    return x


def test_annotate_on_a_real_engine_adds_only_gated_findings_and_checks_a_repair_with_the_engine(monkeypatch):
    from planning import Engine
    from planning.session import Store
    from plan_fixtures import CENTRE, decision, fake_matrix, no_geocode, spot, FakeLive as LiveCfg
    recs = [spot("a", CENTRE, 0), spot("b", CENTRE, 1), spot("c", CENTRE, 2)]
    e = Engine(recs, cfg=ON, live_cfg=LiveCfg(), store=Store(None), geocode_fn=no_geocode, matrix_fn=fake_matrix,
               sun_fn=lambda *a: (360, 1050), background=False)
    e.route_fn = lambda *a: None
    sid = e.create(decision(["a", "b", "c"], days=1, roles={"a": "anchor"},
                            base={"place_id": None, "text": "home", "lat": CENTRE[0], "lng": CENTRE[1]}))["id"]
    view = e.load(sid)["view"]
    if view["state"]["chosen_variant"] is None:
        e.act(sid, {"type": "pick_variant", "id": view["variants"][0]["id"]})
    plan = e.confirm(sid)
    when = plan["itinerary"][0]["date"]
    monkeypatch.setattr(expert, "load_inputs", lambda *a, **k: {"events": {}, "holidays": {_d(when): "Lễ"}, "calendar": None,
                                                                 "normals": None, "claims": [CLAIM]})
    ref = next(iter(expert.slots_of(plan)))
    pid = expert.slots_of(plan)[ref]["place_id"]

    async def ask(fields, cfg, client_fn):
        return {"findings": [finding(slot_ref=ref, fix="drop"), finding(slot_ref="d1:invented", message="Bịa.")]}
    monkeypatch.setattr(expert, "_ask", ask)
    out = expert.annotate(e, sid, plan)
    local = [w for w in out["warnings"] if w["code"] == "local_expert"]
    assert len(local) == 1 and local[0]["place_id"] == pid                      # the invented slot never became a warning
    assert ("actions" in local[0]) == (pid != "a")                              # the anchor "a" is never offered a drop
    assert out["itinerary"] == plan["itinerary"]                                # annotate never edits the plan


def _d(s):
    return date.fromisoformat(s)


def _confirmed(monkeypatch, confirm=True):
    from planning import Engine
    from planning.session import Store
    from plan_fixtures import CENTRE, decision, fake_matrix, no_geocode, spot, FakeLive as LiveCfg
    recs = [spot("a", CENTRE, 0), spot("b", CENTRE, 1), spot("c", CENTRE, 2)]
    e = Engine(recs, cfg=ON, live_cfg=LiveCfg(), store=Store(None), geocode_fn=no_geocode, matrix_fn=fake_matrix,
               sun_fn=lambda *a, **k: (360, 1050), background=False)
    e.route_fn = lambda *a: None
    sid = e.create(decision(["a", "b", "c"], days=1, roles={"a": "anchor"},
                            base={"place_id": None, "text": "home", "lat": CENTRE[0], "lng": CENTRE[1]}))["id"]
    view = e.load(sid)["view"]
    if view["state"]["chosen_variant"] is None:
        e.act(sid, {"type": "pick_variant", "id": view["variants"][0]["id"]})
    return e, sid, (e.confirm(sid) if confirm else None)


def test_confirm_never_waits_for_the_expert(monkeypatch):
    from planning import Tools
    e, sid, _ = _confirmed(monkeypatch, confirm=False)

    def boom(*a, **k):
        raise AssertionError("the expert ran inside confirm")
    monkeypatch.setattr(expert, "review", boom)
    monkeypatch.setattr(expert, "annotate", boom)
    monkeypatch.setattr(expert, "findings_for", boom)
    plan = Tools(e).apply(sid, "confirm", {}, lambda *a, **k: None)         # expert.enabled is ON here
    assert plan["itinerary"] and not [w for w in plan.get("warnings") or [] if w.get("code") == "local_expert"]


def test_the_background_pass_saves_notes_once_per_plan(monkeypatch, tmp_path):
    from planning import EveStore
    e, sid, plan = _confirmed(monkeypatch)
    when = plan["itinerary"][0]["date"]
    monkeypatch.setattr(expert, "load_inputs", lambda *a, **k: {"events": {}, "holidays": {date.fromisoformat(when): "Lễ"},
                                                                 "calendar": None, "normals": None, "claims": [CLAIM]})
    ref = next(iter(expert.slots_of(plan)))

    async def ask(fields, cfg, client_fn):
        return {"findings": [finding(slot_ref=ref), finding(slot_ref="d1:invented", message="Bịa.")]}
    monkeypatch.setattr(expert, "_ask", ask)
    snap = e.store.get(sid).model_dump(mode="json")
    out = expert.run_expert(e, snap, plan, journey="j1", plan_hash="h1", store_root=tmp_path)
    assert out == 1
    notes = EveStore(tmp_path).get("j1", "h1")["notes"]
    assert len(notes) == 1 and notes[0]["factor"] == "local_expert" and notes[0]["date"] == when and notes[0]["level"] == 1
    assert expert.run_expert(e, snap, plan, journey="j1", plan_hash="h1", store_root=tmp_path) is None   # once per plan


def test_a_failed_background_pass_is_retried_a_few_times_then_left(monkeypatch, tmp_path):
    e, sid, plan = _confirmed(monkeypatch)
    monkeypatch.setattr(expert, "load_inputs", lambda *a, **k: {"events": {}, "holidays": {date.fromisoformat(plan["itinerary"][0]["date"]): "Lễ"},
                                                                 "calendar": None, "normals": None, "claims": [CLAIM]})

    async def ask(fields, cfg, client_fn):
        raise RuntimeError("down")
    monkeypatch.setattr(expert, "_ask", ask)
    snap = e.store.get(sid).model_dump(mode="json")
    runs = [expert.run_expert(e, snap, plan, journey="j1", plan_hash="h1", store_root=tmp_path) for _ in range(5)]
    assert runs == [0, 0, 0, None, None]
