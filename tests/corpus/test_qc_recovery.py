import asyncio
import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from corpus.crawl.gmaps import qc
from corpus.llm import REVIEW_QC, OutOfQuota


REVIEWS = [
    {"review_id": "good", "rating": 5, "text": "A real visit with a beautiful garden."},
    {"review_id": "bad", "rating": 3, "text": "Another visitor describing the cafe."},
]


class Stream:
    def __init__(self, text):
        self.text = text

    def __aiter__(self):
        return self.chunks()

    async def chunks(self):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=self.text))])

    async def close(self):
        pass


class Client:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return Stream(self.answer(kwargs))


def content_failure(kind):
    return {"runaway": "{" + " " * 400, "json": "not JSON", "schema": '{"bad": false}'}[kind]


def screen(client, reviews=None):
    return asyncio.run(qc.screen(client, "fake-qc", {"name": "Garden", "category": "cafe"},
                                REVIEWS if reviews is None else reviews, "Test city", asyncio.Semaphore(1)))


@pytest.mark.parametrize("kind", ["runaway", "json", "schema"])
def test_failed_chunk_retries_each_review_with_safe_options(kind):
    def answer(call):
        if "frequency_penalty" not in call:
            return content_failure(kind)
        reviews = call["messages"][0]["content"].split("Reviews:\n", 1)[1]
        if "Another visitor" in reviews:
            return json.dumps({"bad": [{"ref": "r1", "problem": "owner_reply", "reason": "Staff thanks visitors"}]})
        return '{"bad": []}'

    client = Client(answer)
    assert screen(client) == [{"review_id": "bad", "problem": "owner_reply", "reason": "Staff thanks visitors"}]
    retries = [call for call in client.calls if "frequency_penalty" in call]
    assert len(retries) == 2
    for call in retries:
        assert call["max_tokens"] == min(REVIEW_QC.max_tokens, 1000)
        assert call["frequency_penalty"] == 0.3
        assert call["presence_penalty"] == 0.2
        assert len(call["messages"][0]["content"].split("Reviews:\n", 1)[1].splitlines()) == 1


@pytest.mark.parametrize("kind", ["runaway", "json", "schema"])
def test_failed_singleton_has_explicit_reason_and_only_one_safe_attempt(kind):
    client = Client(lambda call: content_failure(kind))
    flags = screen(client, REVIEWS[:1])
    assert len(flags) == 1
    assert flags[0]["review_id"] == "good"
    assert flags[0]["problem"] == "qc_unscored"
    assert "qc_failed: review_id=good" in flags[0]["reason"]
    assert {"runaway": "Runaway", "json": "JSONDecodeError", "schema": "SchemaError"}[kind] in flags[0]["reason"]
    assert len([call for call in client.calls if "frequency_penalty" in call]) == 1


def test_healthy_chunk_keeps_original_mapping_and_options():
    client = Client(lambda call: '{"bad": [{"ref": "r2", "problem": "spam", "reason": "Promo code"}]}')
    assert screen(client) == [{"review_id": "bad", "problem": "spam", "reason": "Promo code"}]
    assert len(client.calls) == 1
    assert "frequency_penalty" not in client.calls[0]
    assert client.calls[0]["max_tokens"] == REVIEW_QC.max_tokens


def test_short_reviews_do_not_call_client():
    client = Client(lambda call: pytest.fail("Short reviews should not reach the model"))
    assert screen(client, [{"review_id": "short", "text": "ok"}]) == []
    assert client.calls == []


@pytest.mark.parametrize("kind", ["runaway", "json", "schema"])
def test_place_qc_failure_is_not_replaced_with_review_recovery_or_place_booleans(kind):
    client = Client(lambda call: content_failure(kind))
    with pytest.raises(ValueError):
        asyncio.run(qc.judge(client, "fake-qc", {"name": "Garden"}, REVIEWS))
    assert not any("frequency_penalty" in call for call in client.calls)


@pytest.mark.parametrize("during_retry", [False, True])
@pytest.mark.parametrize("kind", ["auth", "network", "config"])
def test_operational_errors_are_not_content_failures(monkeypatch, during_retry, kind):
    request = httpx.Request("POST", "https://fake.invalid")
    errors = {
        "auth": openai.AuthenticationError("Invalid key", response=httpx.Response(401, request=request), body=None),
        "network": openai.APIConnectionError(request=request),
        "config": ValueError("Invalid endpoint configuration"),
    }
    error = errors[kind]
    monkeypatch.setattr(qc, "BUSY_TRIES", 1)
    monkeypatch.setattr("corpus.llm.tasks.RETRY_S", 0)

    def answer(call):
        if during_retry and "frequency_penalty" not in call:
            return content_failure("runaway")
        raise error

    client = Client(answer)
    with pytest.raises(type(error)) as raised:
        screen(client)
    assert raised.value is error
    if not during_retry:
        assert not any("frequency_penalty" in call for call in client.calls)


@pytest.mark.parametrize("kind", ["rate_limit", "quota"])
def test_singleton_operational_failure_has_one_call_and_no_outer_wait(monkeypatch, kind):
    request = httpx.Request("POST", "https://fake.invalid")
    error = (openai.RateLimitError("Busy", response=httpx.Response(429, request=request), body=None)
             if kind == "rate_limit" else OutOfQuota("All accounts resting"))

    async def no_wait(seconds):
        pytest.fail(f"Singleton must not wait/retry outside Task.ask: {seconds}")

    monkeypatch.setattr(qc.asyncio, "sleep", no_wait)

    def answer(call):
        if "frequency_penalty" not in call:
            return content_failure("runaway")
        raise error

    client = Client(answer)
    with pytest.raises(type(error)) as raised:
        screen(client)
    assert raised.value is error
    assert len([call for call in client.calls if "frequency_penalty" in call]) == 1


def test_chunk_keeps_outer_quota_wait_and_retry(monkeypatch):
    waits = []

    async def wait(seconds):
        waits.append(seconds)

    monkeypatch.setattr(qc.asyncio, "sleep", wait)

    def answer(call):
        if len(client.calls) == 1:
            raise OutOfQuota("All accounts resting")
        return '{"bad": []}'

    client = Client(answer)
    assert screen(client) == []
    assert len(client.calls) == 2
    assert waits == [120]


@pytest.mark.parametrize("incremental", [False, True])
def test_run_persists_unscored_reviews_after_failed_singleton(tmp_path, monkeypatch, incremental):
    root = tmp_path / "gmaps"
    place_dir = root / "places" / "place"
    place_dir.mkdir(parents=True)
    place = {"fid": "fid", "name": "Garden", "fetched_at": "2026-11-04"}
    (place_dir / "place.json").write_text(json.dumps(place))
    (place_dir / "reviews.json").write_text(json.dumps(REVIEWS))
    if incremental:
        target = root / "qc" / "place.json"
        target.parent.mkdir()
        target.write_text(json.dumps({"fetched_at": place["fetched_at"], "reviews_hash": "old",
                                     "llm": {"verdict": "ok", "tourism_relevant": True, "in_city": True,
                                             "bad_reviews": [{"review_id": "old", "problem": "spam", "reason": "Ad"}]},
                                     "review_qc": {"flagged": 1}, "screened": ["old"]}))
    client = Client(lambda call: content_failure("runaway"))
    monkeypatch.setattr(qc, "load_config", lambda city: (city, {"gmaps": {}}))
    monkeypatch.setattr(qc, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(qc, "listed", lambda city: None)
    monkeypatch.setattr(REVIEW_QC.role.__class__, "client", lambda self: (client, "fake-qc"))
    monkeypatch.setattr(client, "with_options", lambda **kwargs: client, raising=False)

    async def judge(*args):
        assert not incremental, "A review-only update must retain the place verdict"
        return {"verdict": "ok", "tourism_relevant": True, "in_city": True, "bad_reviews": []}

    monkeypatch.setattr(qc, "judge", judge)
    result = asyncio.run(qc.run("Test city"))
    record = json.loads((root / "qc" / "place.json").read_text())
    assert "llm_error" not in record
    flags = record["llm"]["bad_reviews"]
    assert [(b["review_id"], b["problem"]) for b in flags[:2]] == [(r["review_id"], "qc_unscored") for r in REVIEWS]
    assert all("Runaway" in b["reason"] for b in flags[:2])
    assert record["review_qc"]["flagged"] == 2 + incremental
    assert result["bad_reviews"]["qc_unscored"] == 2
    assert result["llm_errors"] == 0
    if incremental:
        assert flags[-1]["review_id"] == "old"
    calls = len(client.calls)
    asyncio.run(qc.run("Test city"))
    assert len(client.calls) == calls


def test_unscored_singleton_does_not_discard_other_review_verdicts():
    def answer(call):
        text = call["messages"][0]["content"].split("Reviews:\n", 1)[1]
        if "frequency_penalty" not in call or "real visit" in text:
            return content_failure("json")
        return '{"bad": [{"ref": "r1", "problem": "spam", "reason": "Ad"}]}'

    flags = screen(Client(answer))
    assert [(b["review_id"], b["problem"]) for b in flags] == [("good", "qc_unscored"), ("bad", "spam")]
