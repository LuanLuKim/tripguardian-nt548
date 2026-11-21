"""config/prod_journey_cases.yaml is a valid, covering matrix (no network, no corpus)."""

from collections import Counter
import importlib.util
from pathlib import Path
import subprocess
import sys

import httpx


spec = importlib.util.spec_from_file_location("prod_journey_e2e", Path(__file__).resolve().parents[2] / "scripts/prod_journey_e2e.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

import pytest

from bench import prod_cases

CASES = prod_cases.load()


@pytest.fixture(autouse=True)
def no_service_corpus(monkeypatch):
    """No corpus here (module docstring): the service listing is empty, like `records` in the tests that stub it."""
    monkeypatch.setattr(runner, "service_records", lambda: {})


def test_loads_about_forty_unique_cases():
    assert 40 <= len(CASES) <= 60
    assert len({c.id for c in CASES}) == len(CASES)


def test_covers_the_traveller_axes_of_the_brief():
    axes = Counter(a for c in CASES for a in c.axes)
    for needed in ("solo_female", "solo_male", "honeymoon", "friends_group", "family_toddler", "family_kid_6_10", "elderly", "wheelchair",
                   "business", "pet", "returning", "dev_account", "first_time", "coach_from_hcm", "plane_from_hanoi", "origin_nhatrang",
                   "motorbike_self_drive", "car_with_driver", "taxi", "student_budget", "luxury", "vegetarian_whole_trip",
                   "vegetarian_one_day", "allergy", "cloud_hunt", "street_food", "no_diacritics", "teencode", "contradiction",
                   "change_mind", "services", "weather_question", "card_challenge", "pick_few", "pick_many", "edit_plan",
                   "rainy_season", "tet_holiday", "late_arrival", "weekend_crowd", "fake_place", "dish_hunter"):
        assert axes[needed] >= 1, f"no case covers {needed}"


def test_length_buckets_and_picks_are_covered():
    days = Counter(c.truth.days for c in CASES)
    assert all(days[d] >= 1 for d in (1, 2, 3, 4, 5))
    assert {c.pick.mode for c in CASES} == {"few", "medium", "many"}


def test_dev_account_cases_are_few_and_marked():
    dev = [c for c in CASES if c.auth == "dev"]
    assert 2 <= len(dev) <= 3
    assert all("QA matrix" in c.chat[0].text for c in dev)


def test_fake_and_real_places_are_named():
    assert any(c.truth.fake_places for c in CASES)
    assert any(c.truth.real_places for c in CASES)
    assert not [c.id for c in CASES if set(c.truth.fake_places) & set(c.truth.real_places)]


def test_hard_flags_follow_the_truth():
    for c in CASES:
        if "vegetarian" in c.expect.hard:
            assert "vegetarian" in c.truth.care
        if "wheelchair" in c.expect.hard:
            assert "wheelchair" in c.truth.care


def test_every_case_is_checkable():
    for c in CASES:
        assert 3 <= len(c.expect.criteria) <= 7
        assert c.chat[0].kind == "opening"


def test_extra_fields_are_refused():
    raw = {"id": "x", "title": "t", "axes": ["a", "b"], "persona": "p", "bogus": 1}
    with pytest.raises(Exception):
        prod_cases.Case.model_validate(raw)


def empty_record():
    return {"plans": {}, "chat": [], "gate": [], "picks": [], "pick_errors": [], "edits": [], "errors": [], "_calls": [], "_steps": []}


def test_unknown_hard_evidence_does_not_pass(monkeypatch):
    case = next(c for c in CASES if "vegetarian" in c.expect.hard)
    monkeypatch.setattr(runner, "records", lambda: {"p": {"identity": {"name": "Quán", "category_group": "restaurant"}}})
    monkeypatch.setattr(runner, "serving_check", lambda *a: "unknown")
    rec = empty_record()
    rec["plans"]["generated"] = {"days": [{"day": 1, "items": [{"kind": "visit", "place_id": "p", "name": "Quán", "start": "12:00", "end": "13:00"}]}], "variants": [], "warnings": []}
    assert runner.check_all(case, rec, [])["hard_constraints"]["status"] == "fail"


def test_gate_missing_end_is_not_a_repeated_answer(monkeypatch):
    monkeypatch.setattr(runner, "records", lambda: {})
    rec = empty_record()
    rec["gate"] = [{"missing": ["trip"], "inputs": {"trip": ["end"]}}]
    case = CASES[0].model_copy(deep=True)
    case.truth.end_hour = None
    assert runner.check_all(case, rec, [])["repeat_question"]["status"] == "pass"


def test_question_in_say_reaches_user_simulator():
    resp = runner.Resp(200, 1, [{"event": "say", "data": {"delta": "Bạn thích view hồ hay rừng hơn?"}}])
    assert runner.open_question(resp) == ["Bạn thích view hồ hay rừng hơn?"]


def test_edit_day_uses_zero_based_api_index():
    class FakeApi:
        def request(self, stage, op, payload):
            assert payload["day"] == 0
            return runner.Resp(200, 0.1, body={"result": {"view": view}})

        def step(self, *args):
            pass

    view = {"itinerary": [{"day": 1, "window": ["10:00", "17:00"], "items": []}]}
    rec = {"edits": [], "plans": {}}
    runner.apply_edit(CASES[0], FakeApi(), prod_cases.Edit(op="set_day_window", day=1, start="10:00", end="17:00"), view, rec, [])


def test_http_trace_saves_redacted_payload_and_response():
    api = runner.Api("fixture")
    api.c.close()
    api.c = httpx.Client(base_url="http://test", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"id": "trip", "ok": True})))
    try:
        api.raw("POST", "/api/auth/login", json={"email": "private@example.test", "password": "secret"})
        assert api.calls[0]["request"] == {"email": "[redacted]", "password": "[redacted]"}
        assert api.calls[0]["response"] == {"id": "trip", "ok": True}
    finally:
        api.close()


def test_trace_summarizes_repeated_views_instead_of_copying_cards():
    value = {"view": {"groups": [{"cards": [{"description": "x" * 1000} for _ in range(100)]}], "selected": ["p"], "state": {"chosen_variant": "main"}}}
    out = runner.trace_summary(value)
    assert out["view"]["selected"] == ["p"]
    assert len(str(out)) < 2000


def test_hidden_plan_note_is_not_reported_as_visible_raw_text():
    texts = []
    runner.collect_plan_texts(texts, {"itinerary": [{"items": [{"kind": "free", "note": "0x123456789:0x123456789"}, {"kind": "visit", "name": "Cafe", "note": "optional"}]}]}, "plan")
    assert not any("0x" in text or "optional" in text for _, text in texts)


def test_judge_receives_card_and_grounding_evidence(monkeypatch):
    def model(system, user, *args):
        assert "Kong Coffee" in user and "ids_in_corpus" in user
        return "[]"

    monkeypatch.setattr(runner, "ask_model", model)
    runner.judge(CASES[0], "lịch", "chat", [], evidence={"picks": [{"name": "Kong Coffee"}], "checks": {"ids_in_corpus": {"status": "pass"}}})


def test_runner_selects_confirmable_variant_before_edits():
    class FakeApi:
        def request(self, stage, op, payload):
            assert (stage, op, payload) == ("planning", "act", {"type": "pick_variant", "id": "keep"})
            return runner.Resp(200, 0.1, body={"result": {"view": {"state": {"chosen_variant": "keep"}}}})

        def step(self, *args):
            pass

    view = {"state": {"chosen_variant": None}, "variants": [{"id": "bad", "confirmable": False}, {"id": "keep", "confirmable": True, "metrics": {"places": 3}}]}
    selected = runner.select_variant(FakeApi(), view)
    assert selected["state"]["chosen_variant"] == "keep"


def test_stated_budget_is_checked_after_chat(monkeypatch):
    monkeypatch.setattr(runner, "records", lambda: {})
    rec = empty_record()
    rec["understanding_after_chat"] = {"_budget_vnd": 1}
    case = next(c for c in CASES if "budget" in c.expect.stated)
    assert runner.check_all(case, rec, [])["facts_chat"]["status"] == "fail"
    assert "budget" in runner.check_all(case, rec, [])["facts_chat"]["evidence"]


def test_final_budget_value_and_mobility_are_not_just_present(monkeypatch):
    monkeypatch.setattr(runner, "records", lambda: {})
    rec = empty_record()
    rec["outputs_trip"] = {"context": {"start_date": "2026-11-14", "days": 2, "people": 1, "budget_vnd": 1, "mobility": "motorbike"}}
    checks = runner.check_all(CASES[0], rec, [])
    assert checks["facts_final"]["status"] == "fail"
    assert "budget" in checks["facts_final"]["evidence"] and "mobility" in checks["facts_final"]["evidence"]


def score_chat(monkeypatch, understanding, stated, evidence=None, gate=None, text="2 người đi chậm, 9h bắt đầu"):
    monkeypatch.setattr(runner, "records", lambda: {})
    case = CASES[0].model_copy(deep=True)
    case.expect.stated = stated
    case.expect = case.expect.model_copy(update={"chat_evidence": evidence or {}})
    case.truth.people = 2
    case.truth.companions = ["partner"]
    case.truth.pace = "slow"
    case.truth.budget_vnd = 800000
    rec = empty_record()
    rec["chat"] = [{"user": text, "say": "", "places": []}]
    rec["understanding_after_chat"] = understanding
    rec["gate"] = gate or []
    return runner.check_all(case, rec, [])


@pytest.mark.parametrize("budget,pace", [
    (800000, "slow"),
    ({"value": {"amount": 800000, "scope": "per_person_day", "per_person_day": 800000}}, {"value": "slow"}),
    ({"per_person_day": 800000}, {"level": "slow"}),
])
def test_ui_fact_wrappers_preserve_scalar_comparison(monkeypatch, budget, pace):
    checks = score_chat(monkeypatch, {"_budget_vnd": budget, "_pace": pace}, ["budget", "pace"], {"pace": "đi chậm"})
    assert checks["facts_chat"]["status"] == "pass"


@pytest.mark.parametrize("budget,pace", [
    ({"value": {"per_person_day": 1}}, {"value": "slow"}),
    ({"value": {"per_person_day": 800000}}, {"value": "packed"}),
    ({"value": {"amount": 800000, "scope": "whole_trip"}}, {"value": "slow"}),
    (None, None),
])
def test_wrapped_missing_or_wrong_facts_still_fail(monkeypatch, budget, pace):
    checks = score_chat(monkeypatch, {"_budget_vnd": budget, "_pace": pace}, ["budget", "pace"], {"pace": "đi chậm"})
    assert checks["facts_chat"]["status"] == "fail"


def test_hidden_relationship_is_not_implied_by_party_count(monkeypatch):
    checks = score_chat(monkeypatch, {"people": 2}, ["companions"], {"people": "2 người"},
                        [{"missing": ["companions"], "inputs": {"companions": ["who"]}}])
    assert checks["facts_chat"]["status"] == "pass"
    assert checks["repeat_question"]["status"] == "pass"


def test_party_count_and_relationship_remain_independent_requirements(monkeypatch):
    checks = score_chat(monkeypatch, {}, ["companions"], {"people": "2 người"},
                        [{"missing": ["companions"], "inputs": {"companions": ["people"]}}])
    assert "people" in checks["facts_chat"]["evidence"]
    assert checks["repeat_question"]["status"] == "fail"


def test_proven_relationship_missing_still_fails(monkeypatch):
    checks = score_chat(monkeypatch, {"people": 2}, ["companions"], {"people": "vợ chồng", "companions": "vợ chồng"},
                        [{"missing": ["companions"], "inputs": {"companions": ["who"]}}], text="vợ chồng mình")
    assert "companions" in checks["facts_chat"]["evidence"]
    assert checks["repeat_question"]["status"] == "fail"


def test_unspoken_pace_and_gate_only_hours_are_not_repeated(monkeypatch):
    checks = score_chat(monkeypatch, {}, ["pace", "trip"], {},
                        [{"missing": ["pace", "trip"], "inputs": {"pace": [], "trip": ["start"]}}], text="2 người đi chơi")
    assert "pace" not in checks["facts_chat"]["evidence"]
    assert checks["repeat_question"]["status"] == "pass"


def test_proven_start_hour_is_a_repeat_even_when_only_end_is_unknown(monkeypatch):
    checks = score_chat(monkeypatch, {}, ["trip"], {"start_hour": "9h bắt đầu"},
                        [{"missing": ["trip"], "inputs": {"trip": ["start", "end"]}}])
    assert checks["repeat_question"]["status"] == "fail"


def test_partial_relationship_match_does_not_hide_a_missing_companion(monkeypatch):
    case = CASES[0].model_copy(deep=True)
    case.truth.companions = ["kids", "parents"]
    case.expect.stated = ["companions"]
    case.expect.chat_evidence = {"companions": "bé và mẹ"}
    rec = empty_record()
    rec["chat"] = [{"user": "bé và mẹ", "say": "", "places": []}]
    rec["understanding_after_chat"] = {"companions": ["kids"]}
    monkeypatch.setattr(runner, "records", lambda: {})
    assert runner.check_all(case, rec, [])["facts_chat"]["status"] == "fail"


def test_evidence_from_simulator_reply_is_also_user_evidence(monkeypatch):
    case = next(c for c in CASES if c.id == "tet_holiday_big_family")
    rec = empty_record()
    rec["chat"] = [{"user": c.text, "say": "", "places": []} for c in case.chat]
    rec["chat"].append({"user": "Nhà chị có 6 người, đi cùng các bé và bố mẹ nhé.", "say": "", "places": []})
    rec["understanding_after_chat"] = {"start_date": "2027-02-05", "days": 4, "people": 6, "mobility": "car"}
    monkeypatch.setattr(runner, "records", lambda: {})
    checks = runner.check_all(case, rec, [])
    assert "companions" in checks["facts_chat"]["evidence"]


def test_evidence_must_occur_in_actual_user_text(monkeypatch):
    checks = score_chat(monkeypatch, {"people": 2}, ["companions", "pace"],
                        {"companions": "vợ chồng", "pace": "đi chậm"}, text="2 người")
    assert checks["facts_chat"]["status"] == "pass"


def test_offline_recheck_preserves_other_checks_and_source(monkeypatch, tmp_path):
    import json

    if not (runner.OUT / "recheck.py").is_file():
        pytest.skip("prod e2e matrix is not in git (.superpowers/ is ignored)")
    spec = importlib.util.spec_from_file_location("matrix_recheck", runner.OUT / "recheck.py")
    offline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(offline)
    source = runner.ROOT / tmp_path / "source"
    source.mkdir()
    case = next(c for c in CASES if c.id == "first_timer_coach_cold")
    row = {"id": case.id, "chat": [{"user": t.text} for t in case.chat], "gate": [],
           "understanding_after_chat": {"start_date": "2026-11-14", "days": 3, "people": 2,
                                        "companions": ["partner"], "mobility": "car",
                                        "_budget_vnd": {"value": {"per_person_day": 800000}}},
           "checks": {"facts_chat": {"status": "fail"}, "repeat_question": {"status": "fail"},
                      "hard_constraints": {"status": "fail", "evidence": "unknown"}},
           "satisfaction": [{"verdict": "không"}]}
    saved = source / f"{case.id}.json"
    original = json.dumps(row)
    saved.write_text(original)

    def forbidden(*args, **kwargs):
        pytest.fail("offline recheck must not call network, model or current corpus")

    monkeypatch.setattr(offline.r, "ask_model", forbidden)
    monkeypatch.setattr(offline.r.Api, "raw", forbidden)
    monkeypatch.setattr(offline.r, "records", forbidden)
    result = offline.recheck(source, tmp_path / "out")
    assert result["before"]["pass"] == 0
    assert result["after"]["pass"] == 2
    assert result["before"]["total"] == result["after"]["total"] == 3
    assert result["results"][0]["checks"]["hard_constraints"] == row["checks"]["hard_constraints"]
    assert saved.read_text() == original


@pytest.mark.parametrize("jobs", [0, 5])
def test_runner_rejects_parallelism_outside_one_to_four(jobs):
    result = subprocess.run([sys.executable, str(runner.ROOT / "scripts/prod_journey_e2e.py"), "--jobs", str(jobs), "--only", "not_a_case"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "1..4" in result.stderr
