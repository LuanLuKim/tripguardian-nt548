import asyncio
import importlib
import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from corpus.llm import OBS_AUDIT_GEMMA, REVIEW_VERIFY
from corpus.llm import tasks
from corpus.ontology import load
from corpus.review import label_records, label_verdicts


audit = importlib.import_module("corpus.judge.audit")


class Stream:
    def __init__(self, text):
        self.text, self.closed = text, False

    async def __aiter__(self):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=self.text))])

    async def close(self):
        self.closed = True


class Client:
    def __init__(self, replies):
        self.replies, self.calls, self.streams = iter(replies), [], []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        stream = Stream(reply)
        self.streams.append(stream)
        return stream

    def with_options(self, **kwargs):
        return self


def answer(verdict="correct"):
    return json.dumps({"items": [{"ref": "i1", "doubt": "source is explicit", "verdict": verdict}]})


def rows():
    return [("gmaps", "P", {"place_fid": "P", "place_name": "Place"}, {
        "id": f"x{i}", "place_fid": "P", "feature": "steep_or_stairs", "value": "present",
        "source_type": "gmaps_review", "source_id": f"s{i}", "span": {"quote": f"quote {i}"}})
        for i in (1, 2)]


def setup(monkeypatch, tmp_path, replies):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(audit, "evidence", lambda *a: {
        "text": "quote 1 and quote 2", "image": None, "rating": None, "date": None})
    monkeypatch.setattr(audit, "place_info", lambda *a: {"category": "hill", "address": "unknown"})
    client = Client(replies)
    role = OBS_AUDIT_GEMMA.role.name
    clients = {role: (client, "fake-gemma")}
    sems = {role: audit.Pool([(client, "fake-gemma", 1)])}
    return client, clients, sems


@pytest.mark.parametrize("bad", [" " * 300, "broken JSON", '{"items": "wrong type"}'])
def test_bad_chunk_retries_each_claim_with_bounded_safe_calls(monkeypatch, tmp_path, bad):
    retries = tasks.RUNAWAYS if not bad.strip() else tasks.ATTEMPTS
    client, clients, sems = setup(monkeypatch, tmp_path, [bad] * retries + [answer(), answer("wrong")])
    result = asyncio.run(audit.audit_chunk(rows(), load(), "Dalat", clients, sems))
    assert result["correct"] == result["wrong"] == 1
    assert result["error"] == result["missing"] == 0
    assert len(client.calls) == retries + 2
    for call in client.calls[retries:]:
        assert "<i2>" not in call["messages"][0]["content"]
        assert call["max_tokens"] < OBS_AUDIT_GEMMA.max_tokens
        assert call["frequency_penalty"] > 0 and call["presence_penalty"] > 0
    assert len(label_records()) == 2
    assert all(s.closed for s in client.streams)


def test_still_runaway_is_unsure_look_two_and_excluded_on_resume(monkeypatch, tmp_path):
    client, clients, sems = setup(monkeypatch, tmp_path, [" " * 300] * tasks.RUNAWAYS + [" " * 300, answer()])
    got = asyncio.run(audit.audit_chunk(rows(), load(), "Dalat", clients, sems))
    assert got["runaway_unsure"] == got["unsure"] == got["correct"] == 1
    assert got["error"] == got["missing"] == 0
    records = label_records()
    failed = next(r for r in records.values() if r["label"] == "unsure")
    assert failed["look"] == 2 and "runaway" in failed["note"].lower()
    assert "unsure_again" in label_verdicts().values()
    assert audit.select(rows(), load(), audit.current(records, local=True), read_all=True) == []
    assert len(audit.pending_gemma(records, audit.current(records, local=False))) == 1
    assert len(client.calls) == tasks.RUNAWAYS + 2


def test_single_claim_still_bad_json_fails_closed_once(monkeypatch, tmp_path):
    client, clients, sems = setup(monkeypatch, tmp_path, ["bad"] * (tasks.ATTEMPTS + 1))
    got = asyncio.run(audit.audit_chunk(rows()[:1], load(), "Dalat", clients, sems))
    assert got["unsure"] == 1 and got["missing"] == got["error"] == 0
    failed = next(iter(label_records().values()))
    assert failed["look"] == 2 and "json" in failed["note"].lower()
    assert len(client.calls) == tasks.ATTEMPTS + 1


def test_transport_failure_is_not_persisted_as_a_judgment(monkeypatch, tmp_path):
    error = openai.BadRequestError("invalid model", response=httpx.Response(
        400, request=httpx.Request("POST", "http://fake")), body=None)
    client, clients, sems = setup(monkeypatch, tmp_path, [error])
    with pytest.raises(openai.BadRequestError):
        asyncio.run(audit.audit_chunk(rows(), load(), "Dalat", clients, sems))
    assert label_records() == {} and len(client.calls) == 1


def test_run_summary_counts_runaway_unsure_and_resume_does_not_reask(monkeypatch, tmp_path):
    client, _, _ = setup(monkeypatch, tmp_path, [" " * 300] * (tasks.RUNAWAYS + 1) + [answer()])
    monkeypatch.setattr(audit, "gemma", lambda: True)
    monkeypatch.setattr(audit, "also_lan", lambda: False)
    monkeypatch.setattr(audit, "load_config", lambda city: ("Dalat", {}))
    monkeypatch.setattr(audit, "load_rows", lambda ont: rows())
    monkeypatch.setattr(type(OBS_AUDIT_GEMMA.role), "client", lambda self: (client, "fake-gemma"))
    summary = asyncio.run(audit.run("dalat"))
    assert summary["runaway_unsure"] == summary["labels"]["runaway_unsure"] == 1
    assert summary["labels"].get("error", 0) == summary["labels"]["missing"] == 0
    call_count = len(client.calls)
    resumed = asyncio.run(audit.run("dalat"))
    assert resumed["rounds"] == resumed["runaway_unsure"] == 0
    assert len(client.calls) == call_count


def test_task_call_options_reach_the_client_without_mutating_defaults():
    client = Client([json.dumps({"verdict": "supports", "reason": "ok"})])
    asyncio.run(REVIEW_VERIFY.ask(client, "fake", name="A", category="c", claim="x", passage="y",
                                 max_tokens=123, frequency_penalty=0.3, presence_penalty=0.2, attempts=1))
    call = client.calls[0]
    assert call["max_tokens"] == 123
    assert call["frequency_penalty"] == 0.3 and call["presence_penalty"] == 0.2
    assert REVIEW_VERIFY.max_tokens != 123


@pytest.mark.parametrize("bad", [" " * 300, "bad", '{"verdict": "invalid"}'])
def test_task_attempts_one_never_sends_the_same_content_again(bad):
    client = Client([bad, bad, bad, bad])
    with pytest.raises((tasks.Runaway, json.JSONDecodeError, tasks.SchemaError)):
        asyncio.run(REVIEW_VERIFY.ask(client, "fake", name="A", category="c", claim="x", passage="y", attempts=1))
    assert len(client.calls) == 1


def test_singleton_transport_failure_is_one_call_even_through_audit_wrapper(monkeypatch):
    error = openai.RateLimitError("busy", response=httpx.Response(
        429, request=httpx.Request("POST", "http://fake")), body=None)
    client = Client([error, answer()])

    async def no_wait(*args):
        pytest.fail("A singleton retry must not enter another retry loop")

    monkeypatch.setattr(audit.asyncio, "sleep", no_wait)
    with pytest.raises(openai.RateLimitError):
        asyncio.run(audit.ask(OBS_AUDIT_GEMMA, client, "fake", attempts=1,
                              city="Dalat", places="P", features="F", items="i1"))
    assert len(client.calls) == 1


def test_attempts_one_does_not_rotate_a_quota_exhausted_model_pool(monkeypatch):
    error = openai.RateLimitError("quota exhausted", response=httpx.Response(
        429, request=httpx.Request("POST", "http://fake")), body=None)
    client = Client([error, json.dumps({"verdict": "supports", "reason": "ok"})])
    monkeypatch.setattr(tasks, "_REST", {})
    with pytest.raises(openai.RateLimitError):
        asyncio.run(REVIEW_VERIFY.ask(client, "fake-one,fake-two", name="A", category="c", claim="x",
                                     passage="y", attempts=1))
    assert len(client.calls) == 1


def test_default_attempts_still_rotate_quota_pool_on_the_last_attempt(monkeypatch):
    error = openai.RateLimitError("quota exhausted", response=httpx.Response(
        429, request=httpx.Request("POST", "http://fake")), body=None)
    client = Client(["bad JSON"] * (tasks.ATTEMPTS - 1) + [
        error, json.dumps({"verdict": "supports", "reason": "ok"})])
    monkeypatch.setattr(tasks, "_REST", {})
    got = asyncio.run(REVIEW_VERIFY.ask(client, "fake-one,fake-two", name="A", category="c", claim="x",
                                       passage="y"))
    assert got["verdict"] == "supports" and got["_model"] == "fake-two"
    assert len(client.calls) == tasks.ATTEMPTS + 1


def test_singleton_missing_its_item_is_also_fail_closed(monkeypatch, tmp_path):
    client, clients, sems = setup(monkeypatch, tmp_path,
                                 [" " * 300] * tasks.RUNAWAYS + ['{"items": []}', answer()])
    got = asyncio.run(audit.audit_chunk(rows(), load(), "Dalat", clients, sems))
    assert got["unsure"] == got["runaway_unsure"] == got["correct"] == 1
    assert got["missing"] == got["error"] == 0
    assert "unsure_again" in label_verdicts().values()
    assert len(client.calls) == tasks.RUNAWAYS + 2


def test_chunk_with_missing_refs_is_isolated_before_any_label_is_written(monkeypatch, tmp_path):
    client, clients, sems = setup(monkeypatch, tmp_path, [answer(), answer(), answer("wrong")])
    got = asyncio.run(audit.audit_chunk(rows(), load(), "Dalat", clients, sems))
    assert got["correct"] == got["wrong"] == 1
    assert got["missing"] == got["error"] == 0
    assert len(client.calls) == 3 and len(label_records()) == 2
