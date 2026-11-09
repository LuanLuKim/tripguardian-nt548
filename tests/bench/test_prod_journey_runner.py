"""Offline regressions for matrix scoring and gate orchestration."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from bench import prod_cases

spec = importlib.util.spec_from_file_location("journey_runner_checks", Path(__file__).resolve().parents[2] / "scripts/prod_journey_e2e.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
CASES = prod_cases.load()
PID = "0x123456789:0xabcdef123"
SVC = "0x234567890:0xbcdef1234"


@pytest.fixture
def case():
    return CASES[0].model_copy(deep=True)


@pytest.fixture(autouse=True)
def corpus(monkeypatch):
    monkeypatch.setattr(runner, "records", lambda: {PID: {"identity": {"name": "Cafe", "category_group": "cafe"}}})
    monkeypatch.setattr(runner, "service_records", lambda: {SVC: {"fid": SVC, "name": "Sửa xe", "url": "https://maps.test/service"}}, raising=False)


def record():
    return {"plans": {}, "chat": [], "gate": [], "picks": [], "pick_errors": [], "edits": [], "errors": [], "_calls": [], "_steps": []}


def summary(ids=(PID,)):
    return {"days": [{"day": 1, "date": "2026-11-14", "window": ["09:00", "18:00"],
                      "items": [{"kind": "visit", "place_id": pid, "name": "Tao Ngộ", "start": "10:00", "end": "11:00"} for pid in ids]}],
            "variants": [], "warnings": [], "chosen_variant": "main", "ok": True}


@pytest.mark.parametrize("pid,want", [(SVC, "pass"), ("0x999999999:0x999999999", "fail")])
def test_service_chat_is_grounded_but_unknown_id_is_not(case, pid, want):
    rec = record()
    rec["chat"] = [{"user": "Sửa xe ở đâu?", "say": "", "places": [pid]}]
    assert runner.check_all(case, rec, [])["ids_in_corpus"]["status"] == want


def test_service_cannot_leak_into_itinerary(case):
    rec = record()
    rec["plans"]["generated"] = summary((SVC,))
    assert runner.check_all(case, rec, [])["ids_in_corpus"]["status"] == "fail"


def test_service_loader_requires_identity_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    path = tmp_path / "data/gmaps/list/dalat_svc.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"items": [{"fid": SVC, "name": "Sửa xe", "url": "https://maps.test"}, {"fid": PID}]}))
    # Exercise the real loader, not the fixture's IO replacement.
    assert set(runner.load_service_records(path)) == {SVC}


@pytest.mark.parametrize("reply,want", [("Mình chưa chắc chắn nên chưa trả lời được.", "pass"), ("Có nhé, nơi này rất đẹp.", "fail")])
def test_fake_place_uncertainty_is_not_fabrication(case, reply, want):
    case.truth.fake_places = ["Đồi Kẹo Cầu Vồng"]
    rec = record()
    rec["chat"] = [{"user": "Đồi Kẹo Cầu Vồng ở đâu?", "say": reply, "places": []}]
    assert runner.check_all(case, rec, [])["fake_place"]["status"] == want


def test_negation_does_not_excuse_a_fabricated_card(case, monkeypatch):
    monkeypatch.setattr(runner, "records", lambda: {PID: {"identity": {"name": "Đồi Kẹo Cầu Vồng"}}})
    case.truth.fake_places = ["Đồi Kẹo Cầu Vồng"]
    rec = record()
    rec["chat"] = [{"user": "Đồi Kẹo Cầu Vồng ở đâu?", "say": "Chưa chắc chắn.", "places": [PID]}]
    assert runner.check_all(case, rec, [])["fake_place"]["status"] == "fail"


@pytest.mark.parametrize("remaining,want", [((SVC,), True), ((PID, SVC), False)])
def test_drop_verifies_exact_sent_id_not_duplicate_name(remaining, want):
    edit = prod_cases.Edit(op="drop_name", name="Tao Ngộ", verify="absent")
    out = {"applied": True, "name": "Tao Ngộ 5", "place_id": PID}
    assert runner.verify_edit(edit, out, summary((PID, SVC)), summary(remaining))["ok"] is want


@pytest.mark.parametrize("visible,want", [([], "pass"), (["Bạn đã chọn quá nhiều, hãy bỏ bớt."], "fail")])
def test_no_nudge_uses_rendered_surface_not_hidden_feasibility(case, visible, want):
    rec = record()
    rec["choose_after_picks"] = {"conflicts": [{"place_id": PID}], "warnings": ["Too much"], "visible_nudges": visible}
    assert runner.check_all(case, rec, [])["no_nudge_choose"]["status"] == want


def test_refused_pick_still_fails_no_nudge(case):
    rec = record()
    rec["pick_errors"] = [{"status": 409}]
    assert runner.check_all(case, rec, [])["no_nudge_choose"]["status"] == "fail"


@pytest.mark.parametrize("where,text,want", [("choose.conflict", PID, "pass"), ("chat.1.say", PID, "fail"), ("plan.dropped", "Cafe: None", "pass"), ("chat.1.say", "None", "fail")])
def test_rescore_does_not_scan_hidden_or_python_synthetic_strings(case, where, text, want):
    rec = record()
    rec["visible_texts"] = [(where, text)]
    if where == "plan.dropped":
        rec["plans"]["generated"] = summary()
        rec["plans"]["generated"]["variants"] = [{"dropped": [{"name": "Cafe", "reason": None}]}]
    original = copy.deepcopy(rec)
    rescored = runner.rescore_record(case, rec)
    assert rescored["checks"]["raw_text"]["status"] == want
    assert rec == original


@pytest.mark.parametrize("text,want", [(None, "pass"), ("None", "fail"), (PID, "fail")])
def test_plan_null_is_empty_but_literal_null_and_raw_ids_are_caught(case, text, want):
    texts = []
    runner.collect_plan_texts(texts, {"variants": [{"dropped_by_plan": [{"name": "Cafe", "text": text}]}]}, "plan")
    assert runner.check_all(case, record(), texts)["raw_text"]["status"] == want


def test_rescore_null_drop_among_other_variants_is_not_python_text(case):
    rec = record()
    rec["visible_texts"] = [("edit.dropped", "Cafe: None")]
    rec["plans"]["generated"] = summary()
    rec["plans"]["generated"]["variants"] = [{"dropped": [{"name": "Cafe", "reason": "Ít hợp gu"}, {"name": "Cafe", "reason": None}]}]
    assert runner.rescore_record(case, rec)["checks"]["raw_text"]["status"] == "pass"


def test_rescore_keeps_literal_none_drop_reason(case):
    rec = record()
    rec["visible_texts"] = [("plan.dropped", "Cafe: None")]
    rec["plans"]["generated"] = summary()
    rec["plans"]["generated"]["variants"] = [{"dropped": [{"name": "Cafe", "reason": "None"}]}]
    assert runner.rescore_record(case, rec)["checks"]["raw_text"]["status"] == "fail"


def test_tradeoff_projects_labels_but_still_catches_raw_visible_reason(case):
    texts = []
    runner.collect_plan_texts(texts, {"tradeoffs": [{"kind": "unplaced", "place_id": PID, "reason": "no_record"}]}, "plan")
    assert runner.check_all(case, record(), texts)["raw_text"]["status"] == "pass"
    texts = []
    runner.collect_plan_texts(texts, {"tradeoffs": [{"kind": "unplaced", "place_id": PID, "reason": "bad_reason_key"}]}, "plan")
    assert runner.check_all(case, record(), texts)["raw_text"]["status"] == "fail"


def test_rendered_pending_nudge_is_not_hidden_feasibility(case):
    rec = record()
    rec["choose_after_picks"] = {"pending": {"text": "Bạn chọn quá nhiều, hãy bỏ bớt nơi."}}
    assert runner.check_all(case, rec, [])["no_nudge_choose"]["status"] == "fail"


@pytest.mark.parametrize("status,want", [(403, "pass"), (200, "fail"), (500, "fail")])
def test_legacy_guest_eve_probe_checks_denial(case, status, want):
    case.auth = "guest"
    rec = record()
    rec["_calls"] = [{"m": "GET", "p": "/api/harness/sessions/:id/eve", "s": status, "note": "guest"}]
    assert runner.check_all(case, rec, [])["eve_guest"]["status"] == want


@pytest.mark.parametrize("ctx,want", [({"origin": "TP.HCM", "arrival_mode": "bus"}, "pass"), ({"entry_point": {"text": "Bến xe"}, "arrival_mode": "bus"}, "fail"), ({"origin": "Hà Nội", "arrival_mode": "bus"}, "fail")])
def test_origin_is_not_invented_from_entry_point(case, ctx, want):
    case.truth.origin, case.truth.arrive = "TP.HCM", "bus"
    rec = record()
    rec["chat"] = [{"user": "Đi xe khách từ TP.HCM", "say": "", "places": []}]
    rec["outputs_trip"] = {"context": ctx}
    assert runner.check_all(case, rec, [])["origin_recorded"]["status"] == want


def test_arrival_time_reads_frame_separately_from_origin(case):
    case.truth.origin, case.truth.arrive = "TP.HCM", "bus"
    case.truth.start_hour = "07:00"
    rec = record()
    rec["chat"] = [{"user": "Từ TP.HCM tới lúc 7h", "say": "", "places": []}]
    rec["outputs_trip"] = {"context": {"origin": "TP.HCM", "arrival_mode": "bus", "frame": {"arrive": {"at": "2026-11-14T07:00"}}}}
    assert runner.check_all(case, rec, [])["origin_recorded"]["status"] == "pass"


def test_hidden_origin_truth_is_not_a_user_requirement(case):
    case.truth.origin = "TP.HCM"
    rec = record()
    rec["chat"] = [{"user": "Đi Đà Lạt bằng xe khách", "say": "", "places": []}]
    assert runner.check_all(case, rec, [])["origin_recorded"]["status"] == "na"


@pytest.mark.parametrize("confirming,want", [(True, "pass"), (False, "fail")])
def test_repeat_distinguishes_confirmation_from_reasking(case, confirming, want):
    case.expect.stated = ["mobility"]
    rec = record()
    rec["gate"] = [{"missing": ["mobility"], "inputs": {"mobility": []}, "tabs": [{"qid": "mobility", "question": "Mình đoán bạn đi xe máy, đúng không?" if confirming else "Bạn đi bằng gì?", "options": [{"id": "motorbike", "prefilled": confirming}]}]}]
    assert runner.check_chat(case, rec)["repeat_question"]["status"] == want


def test_gate_only_other_requires_typed_answer(case):
    case.truth.care = ["vegetarian"]
    deck = {"tabs": [{"qid": "care", "options": [{"id": "other"}], "inputs": [], "question": "Ngày ăn chay?"}]}
    answers, _ = runner.gate_answers(case, deck, None)
    assert "care" not in answers  # other is a text action, never a selectable id or skip
    payload = runner.gate_payload(case, deck, None)
    assert payload["kind"] == "text" and "chay" in payload["text"]


def test_gate_real_skip_is_still_valid(case):
    case.truth.care = []
    answers, _ = runner.gate_answers(case, {"tabs": [{"qid": "care", "options": [{"id": "skip"}], "inputs": []}]}, None)
    assert answers == {"care": ["skip"]}


class GateApi:
    def __init__(self, progresses=False):
        self.requests = []
        self.reads = 0
        self.progresses = progresses
        self.rb = {"missing": ["care"], "digest": "one", "deck": {"tabs": [{"qid": "care", "options": [{"id": "other"}], "inputs": []}]}}

    def request(self, stage, op, payload=None, **kwargs):
        self.requests.append((stage, op, payload))
        return runner.Resp(200, 0, [])

    def read(self, path):
        self.reads += 1
        rb = {"missing": [], "digest": "two"} if self.progresses else copy.deepcopy(self.rb)
        return runner.Resp(200, 0, body=rb)

    def step(self, *args):
        pass


@pytest.mark.parametrize("progresses,want", [(False, False), (True, True)])
def test_gate_stops_on_unchanged_state_but_allows_progress(case, progresses, want):
    api = GateApi(progresses)
    rec = record()
    ready = runner.resolve_gate(case, api, api.rb, rec, [])
    assert ready is want
    assert api.reads == 1
    assert sum(p[2].get("kind") == "readback_ok" for p in api.requests) == int(want)
    if not want:
        assert rec["blocked"]["planning"]


def test_missing_plan_blocks_downstream_not_a_cascade(case):
    rec = record()
    rec["errors"] = ["no plan was produced"]
    rec["gate"] = [{"missing": ["care"]}]
    checks = runner.check_all(case, rec, [])
    for key in ("plan_nonempty", "plan_days_dates", "chosen_kept", "confirm_reload", "trips_count"):
        assert checks[key]["status"] == "blocked"
    assert checks["session_errors"]["status"] == "fail"


def test_real_confirm_reload_mismatch_is_still_caught(case):
    rec = record()
    rec["plans"] = {"generated": summary(), "reloaded": summary((SVC,))}
    rec["confirm_status"] = 200
    assert runner.check_all(case, rec, [])["confirm_reload"]["status"] == "fail"


@pytest.mark.parametrize("view,want", [({"state": {"chosen_variant": None}, "variants": [{"id": "draft", "confirmable": False}]}, False), ({"state": {"chosen_variant": "main"}, "violations": [{"kind": "timed"}]}, False), ({"state": {"chosen_variant": "main"}, "variants": [{"id": "main", "confirmable": False}]}, False), ({"state": {"chosen_variant": "main"}, "violations": []}, True)])
def test_runner_never_confirms_invalid_or_unselected_draft(view, want):
    assert runner.plan_ready(view) is want


@pytest.mark.parametrize("window,want", [("10:15", "pass"), ("08:00", "fail")])
def test_start_uses_physical_frame_not_arrival_clock(case, window, want):
    case.expect.start_hour = "09:00"
    rec = record()
    rec["plans"]["generated"] = summary()
    rec["plans"]["generated"]["days"][0]["window"][0] = window
    rec["outputs_trip"] = {"context": {"frame": {"arrive": {"at": "2026-11-14T09:00", "how": "plane"}, "days": [{"start": "10:15", "end": "18:00"}]}}}
    assert runner.check_all(case, rec, [])["start_hour"]["status"] == want


@pytest.mark.parametrize("status,note,want", [(409, "plan_violations", "pass"), (400, "no_variant", "pass"), (400, "unrecognized", "fail"), (500, "plan_violations", "fail")])
def test_http_business_rejections_are_not_infrastructure_errors(case, status, note, want):
    rec = record()
    rec["_calls"] = [{"m": "POST", "p": "/api/harness/sessions/:id/request", "s": status, "note": note,
                      "request": {"stage": "planning", "operation": "confirm"}, "response": {"error": note}}]
    assert runner.check_all(case, rec, [])["http_clean"]["status"] == want


def test_balance_without_feasible_alternative_is_inconclusive(case):
    rec = record()
    p = summary((PID,) * 8)
    p["days"].append({"day": 2, "window": ["08:00", "12:00"], "items": []})
    rec["plans"]["generated"] = p
    assert runner.check_all(case, rec, [])["balance"]["status"] == "blocked"


def test_chosen_drop_null_reason_is_still_a_real_failure(case):
    rec = record()
    rec["selected"] = [{"id": PID}]
    rec["plans"]["generated"] = summary(())
    rec["plans"]["generated"]["variants"] = [{"dropped": [{"place_id": PID, "name": "Cafe", "reason": None}]}]
    assert runner.check_all(case, rec, [])["chosen_kept"]["status"] == "fail"


@pytest.mark.parametrize("reason,want", [(None, "fail"), ("Ít hợp gu nhất", "pass")])
def test_missing_drop_reason_remains_failure_not_raw_text(case, reason, want):
    rec = record()
    rec["plans"]["generated"] = summary()
    rec["plans"]["generated"]["variants"] = [{"dropped": [{"place_id": SVC, "name": "Quán", "reason": reason}]}]
    assert runner.check_all(case, rec, [])["drop_reason"]["status"] == want


def test_card_projection_limits_alerts_without_scanning_hidden_payload():
    texts = []
    view = {"groups": [{"id": "cafe", "cards": [{"name": "Cafe", "why": [{"text": "Hợp bạn"}], "warnings": ["một", "hai", "ba", PID], "tradeoffs": [], "failed": [], "unverified": []}]}], "pending": None}
    runner.collect_choose_texts(texts, view)
    assert ("choose.card.name", "Cafe") in texts
    assert ("choose.card.why", "Hợp bạn") in texts
    assert not any(PID in text for _, text in texts)
    view["groups"][0]["cards"][0]["warnings"] = [PID]
    texts = []
    runner.collect_choose_texts(texts, view)
    assert ("choose.card.alert", PID) in texts


def test_plan_variant_projection_uses_definition_precedence(case):
    texts = []
    runner.collect_plan_texts(texts, {"variants": [{"definition": "Lịch hợp bạn", "why": "hidden_reason_key", "status": "available", "unavailable_reason": "hidden_reason_key"}]}, "plan")
    assert runner.check_all(case, record(), texts)["raw_text"]["status"] == "pass"
    texts = []
    runner.collect_plan_texts(texts, {"variants": [{"definition": "visible_reason_key"}]}, "plan")
    assert runner.check_all(case, record(), texts)["raw_text"]["status"] == "fail"


def test_blocked_case_is_not_reported_as_all_pass():
    rec = record() | {"checks": {"planning": {"status": "blocked"}}, "satisfaction": []}
    assert runner.summarize([rec])["cases_all_pass"] == 0
    assert runner.summarize([rec])["checks_blocked"] == 1


def test_legacy_tradeoff_json_is_projected_not_hidden_id_scanned(case):
    rec = record()
    rec["plans"]["generated"] = summary()
    tradeoff = {"kind": "unplaced", "place_id": PID, "reason": "no_record"}
    rec["plans"]["generated"]["tradeoffs"] = [tradeoff]
    rec["visible_texts"] = [("plan.tradeoff", json.dumps(tradeoff))]
    assert runner.rescore_record(case, rec)["checks"]["raw_text"]["status"] == "pass"
    tradeoff["reason"] = "untranslated_reason"
    rec["visible_texts"] = [("plan.tradeoff", json.dumps(tradeoff))]
    assert runner.rescore_record(case, rec)["checks"]["raw_text"]["status"] == "fail"


@pytest.mark.parametrize("valid", [True, False])
def test_run_case_guest_skips_eve_and_invalid_draft_stops_before_edits(case, monkeypatch, tmp_path, valid):
    case.chat = [case.chat[0]]
    case.sim_replies = 0
    case.edits = [prod_cases.Edit(op="set_pace", level="slow")]
    calls = []
    view = {"ok": valid, "state": {"chosen_variant": "main" if valid else None}, "variants": [], "itinerary": [], "groups": [], "selected": [], "feasibility": {}}

    class Api:
        sid = "session"

        def guest(self):
            pass

        def create(self):
            return {"result": {"transcript": []}}

        def request(self, stage, op, payload=None, **kwargs):
            calls.append((stage, op, payload))
            events = [{"event": "done", "data": {"search_input": {"context": {}}}}] if op == "turn" and payload.get("kind") == "show" else []
            return runner.Resp(200, 0, events=events, body={"result": {"view": view}})

        def load(self, stage):
            return runner.Resp(200, 0, body={"result": {"view": view}, "stage": "planning"})

        def raw(self, method, path, **kwargs):
            assert not path.endswith("/eve"), "guest flow called Eve"
            return 200, [], 0

        def step(self, *args):
            pass

    monkeypatch.setattr(runner, "Api", lambda *args: Api())
    monkeypatch.setattr(runner, "pick_places", lambda case, api, view, rec: view)
    monkeypatch.setattr(runner, "finish", lambda case, api, rec, *args: rec)
    rec = runner.run_case(case, tmp_path)
    assert any(op == "confirm" for stage, op, _ in calls) is valid
    assert any(op == "act" for stage, op, _ in calls) is valid
    if not valid:
        assert rec["blocked"]["confirmation"]


def test_run_case_confirms_an_edited_draft_that_only_has_warnings(case, monkeypatch, tmp_path):
    # Violations are warnings, not a gate (owner 2026-11-08): the runner confirms like the web and records them.
    case.chat = [case.chat[0]]
    case.sim_replies = 0
    case.edits = [prod_cases.Edit(op="set_pace", level="slow")]
    calls = []
    base = {"ok": True, "state": {"chosen_variant": "main"}, "variants": [], "itinerary": [], "groups": [],
            "selected": [], "feasibility": {}}
    edited = base | {"violations": [{"code": "day_window"}]}

    class Api:
        sid = "session"

        def guest(self):
            pass

        def create(self):
            return {"result": {"transcript": []}}

        def request(self, stage, op, payload=None, **kwargs):
            calls.append((stage, op, payload))
            events = [{"event": "done", "data": {"search_input": {"context": {}}}}] if op == "turn" and payload.get("kind") == "show" else []
            return runner.Resp(200, 0, events=events, body={"result": {"view": edited if op == "act" else base}})

        def load(self, stage):
            return runner.Resp(200, 0, body={"result": {"view": base}, "stage": "planning"})

        def raw(self, method, path, **kwargs):
            return 200, [], 0

        def step(self, *args):
            pass

    monkeypatch.setattr(runner, "Api", lambda *args: Api())
    monkeypatch.setattr(runner, "pick_places", lambda case, api, view, rec: view)
    monkeypatch.setattr(runner, "finish", lambda case, api, rec, *args: rec)
    rec = runner.run_case(case, tmp_path)
    assert any(op == "confirm" for stage, op, _ in calls)
    assert rec["confirmed_with_warnings"] == ["day_window"]
    assert "edited draft is not confirmable" not in rec["errors"]


def test_repeated_outer_gate_stops_even_if_readback_digest_changes(case, monkeypatch, tmp_path):
    case.chat = [case.chat[0]]
    case.sim_replies = 0
    advances = []
    view = {"groups": [], "selected": [], "feasibility": {}}
    rb = {"missing": ["care"], "deck": {"tabs": []}}

    class Api:
        sid = "session"

        def guest(self):
            pass

        def create(self):
            return {"result": {"transcript": []}}

        def request(self, stage, op, payload=None, **kwargs):
            if stage == "decision" and op == "advance":
                advances.append(op)
                return runner.Resp(409, 0, body={"error": "trip_incomplete", "missing": ["care"], "readback": dict(rb, digest=str(len(advances)))})
            events = [{"event": "done", "data": {"search_input": {"context": {}}}}] if op == "turn" and payload.get("kind") == "show" else []
            return runner.Resp(200, 0, events=events, body={"result": {"view": view}})

        def load(self, stage):
            return runner.Resp(200, 0, body={"result": {"view": view}})

        def step(self, *args):
            pass

    monkeypatch.setattr(runner, "Api", lambda *a: Api())
    monkeypatch.setattr(runner, "pick_places", lambda case, api, view, rec: view)
    monkeypatch.setattr(runner, "resolve_gate", lambda *a: True)
    monkeypatch.setattr(runner, "finish", lambda case, api, rec, *a: rec)
    rec = runner.run_case(case, tmp_path)
    assert len(advances) == 2
    assert rec["blocked"]["planning"]


def test_rescore_reports_are_offline_and_keep_source_receipts(case, tmp_path, monkeypatch):
    src, dst = tmp_path / "run", tmp_path / "rescore"
    src.mkdir()
    rec = record() | {"id": case.id, "visible_texts": [("choose.conflict", PID)], "satisfaction": [], "secs_total": 1}
    original = json.dumps(rec)
    (src / f"{case.id}.json").write_text(original)
    monkeypatch.setattr(runner.httpx, "Client", lambda *a, **k: pytest.fail("rescore made a network client"))
    monkeypatch.setattr(runner, "ask_model", lambda *a, **k: pytest.fail("rescore called a model"))
    rows = runner.rescore_run(src, dst, [case])
    assert rows[0]["checks"]["raw_text"]["status"] == "pass"
    assert (src / f"{case.id}.json").read_text() == original
    assert (dst / "summary.json").exists()
