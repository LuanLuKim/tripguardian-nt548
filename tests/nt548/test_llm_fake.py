"""ops/nt548/llm_fake/server.py: OpenAI-compatible, deterministic, with injected delay and errors."""

import importlib.util
import sys
import json
import random
import time
from pathlib import Path

import httpx
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

spec = importlib.util.spec_from_file_location("llm_fake", Path(__file__).resolve().parents[2] / "ops/nt548/llm_fake/server.py")
fake = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fake  # dataclasses look their module up there
spec.loader.exec_module(fake)

MSGS = [{"role": "user", "content": "Gợi ý quán cà phê ở Đà Lạt"}]


def client(**over) -> TestClient:
    return TestClient(fake.create_app(fake.Settings(**over)))


def test_models_lists_the_configured_ids():
    body = client(models=("gemma26b-a4b", "clef-flash")).get("/v1/models").json()
    assert body["object"] == "list" and [m["id"] for m in body["data"]] == ["gemma26b-a4b", "clef-flash"]


def test_completion_is_openai_shaped_and_deterministic():
    c = client(version="v1")
    a = c.post("/v1/chat/completions", json={"model": "gemma26b-a4b", "messages": MSGS})
    b = c.post("/v1/chat/completions", json={"model": "gemma26b-a4b", "messages": MSGS})
    assert a.status_code == 200 and a.headers["x-fake-version"] == "v1"
    body = a.json()
    assert body["object"] == "chat.completion" and body["model"] == "gemma26b-a4b"
    assert body["choices"][0]["message"]["role"] == "assistant" and body["choices"][0]["finish_reason"] == "stop"
    assert body["choices"][0]["message"]["content"] == b.json()["choices"][0]["message"]["content"]
    assert body["usage"]["total_tokens"] == body["usage"]["prompt_tokens"] + body["usage"]["completion_tokens"]


def test_reply_changes_with_prompt_model_and_version():
    base = fake.reply_text("v1", "m", MSGS)
    assert base != fake.reply_text("v1", "m", [{"role": "user", "content": "khác"}])
    assert base != fake.reply_text("v1", "other", MSGS)
    assert base != fake.reply_text("v2", "m", MSGS) and "[fake v2]" in fake.reply_text("v2", "m", MSGS)


def test_stream_sends_chunks_that_add_up_to_the_plain_reply():
    c = client()
    plain = c.post("/v1/chat/completions", json={"model": "m", "messages": MSGS}).json()["choices"][0]["message"]["content"]
    with c.stream("POST", "/v1/chat/completions", json={"model": "m", "messages": MSGS, "stream": True}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        lines = [line[len("data: "):] for line in r.iter_lines() if line.startswith("data: ")]
    assert lines[-1] == "[DONE]"
    chunks = [json.loads(x) for x in lines[:-1]]
    assert all(ch["object"] == "chat.completion.chunk" for ch in chunks)
    assert "".join(ch["choices"][0]["delta"].get("content", "") for ch in chunks) == plain
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_error_rate_one_always_fails_and_zero_never():
    bad = client(error_rate=1.0, error_status=503)
    assert all(bad.post("/v1/chat/completions", json={"messages": MSGS}).status_code == 503 for _ in range(5))
    good = client(error_rate=0.0)
    assert all(good.post("/v1/chat/completions", json={"messages": MSGS}).status_code == 200 for _ in range(5))


def test_error_rate_is_about_the_share_asked_and_repeatable_with_a_seed():
    def run():
        c = client(error_rate=0.3, seed=7)
        return [c.post("/v1/chat/completions", json={"messages": MSGS}).status_code for _ in range(200)]
    first = run()
    assert 0.2 <= first.count(500) / len(first) <= 0.4
    assert first == run()


def test_delay_is_added_before_the_reply():
    c = client(delay_ms=200)
    t = time.perf_counter()
    assert c.post("/v1/chat/completions", json={"messages": MSGS}).status_code == 200
    assert time.perf_counter() - t >= 0.2


def test_bad_requests_are_400_not_500():
    c = client()
    assert c.post("/v1/chat/completions", content=b"not json", headers={"content-type": "application/json"}).status_code == 400
    assert c.post("/v1/chat/completions", json={"messages": []}).status_code == 400
    assert c.post("/v1/chat/completions", json=[1, 2]).status_code == 400


def test_settings_from_env_and_bounds():
    s = fake.Settings.from_env({"FAKE_VERSION": "v2", "FAKE_MODELS": "a, b", "FAKE_DELAY_MS": "2000",
                                "FAKE_ERROR_RATE": "0.3", "FAKE_ERROR_STATUS": "502", "FAKE_SEED": "1"})
    assert (s.version, s.models, s.delay_ms, s.error_rate, s.error_status, s.seed) == ("v2", ("a", "b"), 2000, 0.3, 502, 1)
    assert fake.Settings.from_env({}).models == ("gemma26b-a4b",)
    with pytest.raises(ValueError):
        fake.Settings(error_rate=1.5)
    with pytest.raises(ValueError):
        fake.Settings(delay_ms=-1)


class Dispatch(httpx.AsyncBaseTransport):
    """Send each request to the in-process app of its host: the gateway talks to fakes without a network."""

    def __init__(self, apps: dict):
        self.apps = {host: httpx.ASGITransport(app=app) for host, app in apps.items()}

    async def handle_async_request(self, request):
        return await self.apps[request.url.host].handle_async_request(request)


def gateway_over(v1: "fake.Settings", v2: "fake.Settings", weights=(90, 10)):
    spec = importlib.util.spec_from_file_location("model_gateway", Path(__file__).resolve().parents[2] / "scripts/model_gateway.py")
    gw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gw)
    transport = Dispatch({"llm-v1": fake.create_app(v1), "llm-v2": fake.create_app(v2)})
    urls = [f"http://llm-v1:8000@{weights[0]}", f"http://llm-v2:8000@{weights[1]}"]
    return TestClient(gw.build_app("http://clef", urls, "", transport=transport, rng=random.Random(3), clock=lambda: 0.0))


def served_by(c: TestClient, n: int) -> list[str]:
    out = []
    for i in range(n):
        r = c.post("/v1/chat/completions", json={"model": "gemma26b-a4b", "messages": [{"role": "user", "content": f"q{i}"}]})
        out.append(r.json()["choices"][0]["message"]["content"].split("]")[0] + "]" if r.status_code == 200 else str(r.status_code))
    return out


def test_gateway_splits_traffic_between_two_fakes_by_weight():
    got = served_by(gateway_over(fake.Settings(version="v1"), fake.Settings(version="v2")), 300)
    assert set(got) == {"[fake v1]", "[fake v2]"}
    assert 0.05 <= got.count("[fake v2]") / len(got) <= 0.16


def test_gateway_skips_a_canary_fake_that_answers_503():
    """FAKE_ERROR_STATUS=503 on v2: the gateway cools it down and v1 answers, so callers see no error."""
    got = served_by(gateway_over(fake.Settings(version="v1"), fake.Settings(version="v2", error_rate=1.0, error_status=503)), 100)
    assert got == ["[fake v1]"] * 100
