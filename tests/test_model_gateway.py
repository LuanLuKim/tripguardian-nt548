"""Gemma and Clef routes of scripts/model_gateway.py: several upstreams, least outstanding requests, cooldown on failure."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

SPEC = importlib.util.spec_from_file_location("model_gateway", Path(__file__).resolve().parent.parent / "scripts" / "model_gateway.py")
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)

BODY = {"model": "gemma26b-a4b", "messages": [{"role": "user", "content": "hi"}]}


def resp(status=200, payload=None):
    """A response whose body is still an unread stream, like a real upstream."""
    data = json.dumps(payload if payload is not None else {}).encode()
    return httpx.Response(status, headers={"content-type": "application/json"}, stream=httpx.ByteStream(data))


def make_app(handlers, cooldown=30.0, clock=None):
    """handlers: {"http://a": fn(request) -> httpx.Response}"""
    calls = []

    def route(request: httpx.Request) -> httpx.Response:
        base = f"{request.url.scheme}://{request.url.host}:{request.url.port}"
        calls.append(base)
        return handlers[base](request)

    app = gateway.build_app(
        "http://clef", list(handlers), "", transport=httpx.MockTransport(route), cooldown_s=cooldown, clock=clock or (lambda: 0.0)
    )
    return app, calls


def ok(name):
    return lambda request: resp(200, {"served_by": name})


def test_single_url_string_still_works():
    app = gateway.build_app("http://clef", "http://x:1", "", transport=httpx.MockTransport(lambda r: resp(200, {"ok": 1})))
    assert TestClient(app).post("/v1/chat/completions", json=BODY).json() == {"ok": 1}


def test_failed_upstream_is_skipped_and_request_retried_on_the_other():
    app, calls = make_app({"http://a:1": lambda r: resp(503, {"error": "down"}), "http://b:2": ok("b")})
    client = TestClient(app)
    assert client.post("/v1/chat/completions", json=BODY).json() == {"served_by": "b"}
    calls.clear()
    # a is cooling down: the next requests do not even try it
    for _ in range(3):
        assert client.post("/v1/chat/completions", json=BODY).json() == {"served_by": "b"}
    assert set(calls) == {"http://b:2"}


def test_connection_error_marks_upstream_down_then_recovers_after_cooldown():
    now = [0.0]

    def refuse(request):
        raise httpx.ConnectError("refused")

    healthy = [False]
    app, calls = make_app(
        {"http://a:1": lambda r: resp(200, {"served_by": "a"}) if healthy[0] else refuse(r), "http://b:2": ok("b")},
        cooldown=10.0, clock=lambda: now[0],
    )
    client = TestClient(app)
    assert client.post("/v1/chat/completions", json=BODY).json() == {"served_by": "b"}
    healthy[0] = True
    now[0] = 5.0
    calls.clear()
    client.post("/v1/chat/completions", json=BODY)
    assert "http://a:1" not in calls
    now[0] = 11.0
    seen = {client.post("/v1/chat/completions", json=BODY).json()["served_by"] for _ in range(4)}
    assert "a" in seen


def test_all_upstreams_down_returns_502_not_hang():
    app, _ = make_app({"http://a:1": lambda r: resp(503), "http://b:2": lambda r: resp(503)})
    assert TestClient(app).post("/v1/chat/completions", json=BODY).status_code in (502, 503)


def test_client_errors_are_not_retried_or_cooled():
    app, calls = make_app({"http://a:1": lambda r: resp(400, {"error": "too long"}), "http://b:2": ok("b")})
    response = TestClient(app).post("/v1/chat/completions", json=BODY)
    assert response.status_code == 400 and calls == ["http://a:1"]


def test_least_outstanding_picks_the_idle_upstream():
    upstreams = gateway.Upstreams(["http://a", "http://b"], cooldown_s=30.0, clock=lambda: 0.0)
    first = upstreams.acquire()
    second = upstreams.acquire()
    assert {first.url, second.url} == {"http://a", "http://b"}
    upstreams.release(first)
    assert upstreams.acquire().url == first.url


CLEF_BODY = {"model": "clef-flash", "state": {"message": "hi"}, "questions": {"q": {"type": "noul", "instructions": "yes?"}}}
CLEF_ANSWER = {"model": "clef-flash", "answers": {"q": {"type": "noul", "noul": 0.9}}, "usage": {"input_tokens": 5}}


def make_clef_app(handlers, clock=None):
    calls = []

    def route(request: httpx.Request) -> httpx.Response:
        base = f"{request.url.scheme}://{request.url.host}:{request.url.port}"
        calls.append(base)
        return handlers[base](request)

    app = gateway.build_app(list(handlers), ["http://gemma:1"], "", transport=httpx.MockTransport(route), clock=clock or (lambda: 0.0))
    return app, calls


def test_clef_replicas_share_requests_and_skip_a_down_one():
    app, calls = make_clef_app({"http://c1:1": lambda r: resp(503, {"error": "down"}), "http://c2:2": lambda r: resp(200, CLEF_ANSWER)})
    client = TestClient(app)
    for _ in range(3):
        out = client.post("/v1/clef-flash", json=CLEF_BODY).json()
        assert out["systemone"]["answers"]["q"]["noul"] == 0.9
    assert calls.count("http://c1:1") == 1  # tried once, then cooling down


def test_clef_single_url_string_still_works():
    app = gateway.build_app("http://c:1", "http://gemma:1", "", transport=httpx.MockTransport(lambda r: resp(200, CLEF_ANSWER)))
    assert TestClient(app).post("/v1/clef-flash", json=CLEF_BODY).json()["systemone"]["answers"]["q"]["noul"] == 0.9
