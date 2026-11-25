"""ops/nt548/aiops/incident.py on synthetic incidents: the right cause comes first, the LLM cannot cite made-up
evidence, and a repeated alarm comments on its open issue instead of opening another."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

spec = importlib.util.spec_from_file_location("incident", Path(__file__).resolve().parents[2] / "ops/nt548/aiops/incident.py")
incident = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = incident
spec.loader.exec_module(incident)


def case(name):
    return incident.build(*incident.demo(name))


def test_deploy_before_errors_is_the_first_suspect():
    inc = case("deploy_500")
    assert [e.kind for e in inc.evidence][:2] == ["alarm", "metric"]
    hyp, cmds = incident.rules(inc)
    deploy = inc.of("deploy")[0]
    assert deploy.id in hyp[0]["evidence"] and "a1b2c3d" in hyp[0]["text"] and hyp[0]["confidence"] == "high"
    assert cmds[0]["cmd"] == incident.ROLLBACK_CMD
    assert any("500 upstream error" in h["text"] for h in hyp)


def test_an_old_deploy_is_not_blamed():
    inc = case("llm_slow")
    assert inc.of("deploy") == []  # 3 hours before the alarm: outside the window
    hyp, cmds = incident.rules(inc)
    assert not any("first suspect" in h["text"] or "0ff1ce0" in h["text"] for h in hyp)
    assert any("timeout" in h["text"] for h in hyp) and any("Latency" in h["text"] for h in hyp)
    assert all(c["cmd"] != incident.ROLLBACK_CMD for c in cmds)


def test_traffic_points_at_scaling():
    hyp, cmds = incident.rules(case("traffic"))
    assert "Traffic" in hyp[0]["text"]
    assert "nt548-blue" in cmds[0]["cmd"]


def test_alarm_time_comes_from_the_detector_near_the_fault():
    alarm, series, *_ = incident.demo("llm_slow")
    inc = incident.build(alarm, series)
    fault_at = series.t0 + 180 * series.step_s
    assert 0 <= inc.started.timestamp() - fault_at <= 3 * series.step_s


def test_every_hypothesis_cites_existing_evidence():
    for name in incident.DEMOS:
        inc = case(name)
        hyp, cmds = incident.rules(inc)
        for h in hyp + cmds:
            assert h["evidence"] and set(h["evidence"]) <= inc.ids()


def test_llm_answer_is_checked_against_the_evidence_ids():
    ids = {"E1", "E2"}
    ok = json.dumps({"summary": "5xx rose.", "hypotheses": [{"text": "bad deploy", "evidence": ["E2"],
                                                             "confidence": "high"}]})
    assert incident.check_llm("Sure:\n" + ok, ids)[0]["hypotheses"][0]["evidence"] == ["E2"]
    made_up = ok.replace('"E2"', '"E9"')
    assert incident.check_llm(made_up, ids) == (None, "cites evidence that does not exist: E9")
    uncited = ok.replace('["E2"]', "[]")
    assert incident.check_llm(uncited, ids)[1] == "a hypothesis cites no evidence"
    assert incident.check_llm("I think it is the database.", ids)[1] == "no JSON in the answer"


def test_rejected_llm_falls_back_to_the_template(monkeypatch):
    inc = case("deploy_500")
    monkeypatch.setattr(incident, "ask_llm", lambda *a, **k: '{"summary": "DNS.", "hypotheses": '
                        '[{"text": "DNS is down", "evidence": ["E42"]}]}')
    body = incident.write(inc, {"base_url": "http://llm", "api_key": "", "model": "m"})
    assert "LLM answer rejected: cites evidence that does not exist: E42" in body
    assert "DNS" not in body and "a1b2c3d" in body


def test_valid_llm_answer_is_used(monkeypatch):
    inc = case("deploy_500")
    answer = {"summary": "Errors since the deploy.", "hypotheses": [{"text": "the deploy", "evidence": ["E1", "E2"],
                                                                     "confidence": "high"}]}
    monkeypatch.setattr(incident, "ask_llm", lambda *a, **k: json.dumps(answer))
    body = incident.write(inc, {"base_url": "http://llm", "api_key": "", "model": "m"})
    assert "Errors since the deploy." in body and ". the deploy [E1, E2] (high, LLM)" in body
    # the rule hypotheses stay first, so a hedging LLM cannot push the deploy out of first place
    assert "1. The deploy of a1b2c3d" in body and "(high, rule)" in body
    assert body.index("(high, rule)") < body.index("(high, LLM)")
    assert incident.ROLLBACK_CMD in body  # commands still come from the fixed rules


def test_a_format_slip_is_asked_again_a_made_up_cause_is_not(monkeypatch):
    good = json.dumps({"summary": "5xx rose.", "hypotheses": [{"text": "x", "evidence": ["E2"], "confidence": "low"}]})
    llm = {"base_url": "http://llm"}
    for answers, calls, why in (([good[:60], good], 2, ""),                      # cut off, then whole
                                (['{"summary": "s", "hypotheses": [{"text": "x", "evidence": ["E99"]}]}', good], 1,
                                 "cites evidence that does not exist: E99"),
                                (["no json", "still no json"], 2, "no JSON in the answer")):
        seen = []
        monkeypatch.setattr(incident, "ask_llm", lambda *a, _q=list(answers), **k: seen.append(1) or _q.pop(0))
        answer, got = incident.llm_answer(case("deploy_500"), llm)
        assert (len(seen), got, answer is not None) == (calls, why, not why)


def test_request_uses_json_mode_and_drops_it_when_the_endpoint_refuses(monkeypatch):
    sent = []

    def fake(url, body, headers, timeout):
        sent.append(body)
        if "response_format" in body:
            raise incident.urllib.error.HTTPError(url, 400, "unsupported", {}, None)
        return "{}"
    monkeypatch.setattr(incident, "_complete", fake)
    assert incident.ask_llm(case("traffic"), "http://llm/v1", "k", "m") == "{}"
    assert sent[0]["response_format"] == {"type": "json_object"} and sent[0]["max_tokens"] == incident.MAX_TOKENS
    assert "response_format" not in sent[1] and sent[1]["max_tokens"] == incident.MAX_TOKENS


def test_llm_failure_does_not_fail_the_incident(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(incident, "ask_llm", boom)
    body = incident.write(case("traffic"), {"base_url": "http://llm"})
    assert "LLM call failed: OSError" in body and "### Evidence" in body


def test_log_text_cannot_break_the_markdown():
    assert incident.code("a`b\nc") == "`a'b c`"


class FakeGh:
    def __init__(self, issues):
        self.issues, self.calls = issues, []

    def __call__(self, args, stdin=None):
        self.calls.append(args)
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.issues)
        if args[:2] == ["issue", "create"]:
            return "https://github.com/o/r/issues/7\n"
        return ""


def test_new_alarm_opens_an_issue_and_a_repeat_comments():
    inc = case("deploy_500")
    body = incident.write(inc)
    gh = FakeGh([{"number": 3, "body": "another alarm"}])
    assert incident.post(inc, body, "o/r", gh) == "opened https://github.com/o/r/issues/7"
    gh = FakeGh([{"number": 3, "body": body}])
    assert incident.post(inc, body, "o/r", gh) == "commented on #3"
    assert not any(c[:2] == ["issue", "create"] for c in gh.calls)


def test_cloudwatch_anomaly_alarm_is_read_from_its_metric_math():
    a = {"AlarmName": "nt548-blue-latency-anomaly", "StateReason": "outside the band",
         "StateUpdatedTimestamp": "2026-11-28T09:00:00+00:00",
         "Metrics": [{"Id": "ad1", "Expression": "ANOMALY_DETECTION_BAND(m1, 3)"},
                     {"Id": "m1", "MetricStat": {"Metric": {"Namespace": "AWS/ApplicationELB",
                                                            "MetricName": "TargetResponseTime",
                                                            "Dimensions": [{"Name": "TargetGroup", "Value": "tg/x"}]},
                                                 "Period": 60, "Stat": "p95"}}]}
    got = incident.from_cloudwatch(a)
    assert (got["metric"], got["stat"], got["dims"]) == ("TargetResponseTime", "p95", {"TargetGroup": "tg/x"})


def test_cli_demo_writes_markdown(tmp_path):
    out = tmp_path / "i.md"
    assert incident.main(["demo", "deploy_500", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!-- nt548-incident: nt548-demo-5xx -->") and "### Suggested commands" in text
