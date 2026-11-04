"""Turn latency spans, constraint-safe reuse and optional preparation deadlines."""
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

from trip.domain.state import TripState


def test_find_cache_does_not_reuse_after_hard_constraints(turn_tools, kids_hard_state):
    tools = turn_tools()
    args = {"criteria": {"groups": ["cafe"]}}
    before = tools.run("find_places", args)
    assert "0xb:0x1" in {p["id"] for p in before["places"]}
    tools.state = kids_hard_state
    after = tools.run("find_places", args)
    assert {p["id"] for p in after["places"]} == {"0xa:0x1"}


def test_find_cache_does_not_reuse_after_hide(turn_tools):
    tools = turn_tools()
    args = {"criteria": {"groups": ["cafe"]}}
    tools.run("find_places", args)
    from trip.domain.state import with_meta
    tools.state = with_meta(tools.state, hidden_ids=("0xa:0x1",))
    assert "0xa:0x1" not in {p["id"] for p in tools.run("find_places", args)["places"]}


def test_find_inflight_preparation_is_reused_only_for_exact_key(turn_tools, monkeypatch):
    tools = turn_tools()
    entered, release = Event(), Event()
    original = tools.knowledge.find
    calls = []

    def slow(criteria, state):
        calls.append(criteria)
        entered.set()
        assert release.wait(2)
        return original(criteria, state)

    monkeypatch.setattr(tools.knowledge, "find", slow)
    args = {"criteria": {"groups": ["cafe"]}}
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(tools.run, "find_places", args)
        assert entered.wait(1)
        second = pool.submit(tools.run, "find_places", args)
        time.sleep(0.03)
        release.set()
        assert first.result() == second.result()
    assert len(calls) == 1
    different = tools.run("find_places", {"criteria": {"groups": ["nature"]}})
    assert {p["id"] for p in different["places"]} == {"0xd:0x1"}
    assert len(calls) == 2


def test_find_inflight_different_state_cannot_join_old_result(turn_tools, kids_hard_state, monkeypatch):
    tools = turn_tools()
    entered, release = Event(), Event()
    original = tools.knowledge.find

    def slow(criteria, state):
        if not state.hard:
            entered.set()
            assert release.wait(2)
        return original(criteria, state)

    monkeypatch.setattr(tools.knowledge, "find", slow)
    args = {"criteria": {"groups": ["cafe"]}}
    with ThreadPoolExecutor(1) as pool:
        prepared = pool.submit(tools.run, "find_places", args)
        assert entered.wait(1)
        tools.state = kids_hard_state
        try:
            assert {p["id"] for p in tools.run("find_places", args)["places"]} == {"0xa:0x1"}
        finally:
            release.set()
        assert "0xb:0x1" in {p["id"] for p in prepared.result()["places"]}
    assert {p["id"] for p in tools.run("find_places", args)["places"]} == {"0xa:0x1"}


def test_prefetch_deadline_includes_slow_clef_and_keeps_ready_weather(make_assistant, turn_tools, monkeypatch):
    from trip.api import engine as module
    from trip.domain.state import Evidence, Update, apply
    from datetime import date

    engine = make_assistant(None)
    engine.cfg = replace(engine.cfg, assistant=replace(engine.cfg.assistant, prefetch_wait_s=0.06))
    engine.judge = object()
    tools = turn_tools()
    state = apply(TripState(), Update(field="start_date", op="set", value=date(2026, 11, 28), source="user",
                                     confidence="high", evidence=Evidence(turn=1, quote="28/11")))
    tools.state = state
    finished = Event()

    def slow(*args):
        time.sleep(0.3)
        finished.set()
        return {"places": {"choice": "A", "probabilities": {"A": 1.0}}}

    monkeypatch.setattr(module.clef, "ask", slow)
    start = time.monotonic()
    data, note = engine._prefetch("xin chào", state, tools)
    elapsed = time.monotonic() - start
    assert elapsed < 0.2
    assert data["thoi_tiet"][0]["date"] == "2026-11-28"
    assert "deadline" in note
    route = tools.route
    assert finished.wait(1)
    assert tools.route is route and "places" not in tools.route.groups


def test_prefetch_tool_wait_uses_only_remaining_budget(make_assistant, turn_tools_slow_weather, monkeypatch):
    from trip.api import engine as module
    engine = make_assistant(None)
    engine.cfg = replace(engine.cfg, assistant=replace(engine.cfg.assistant, prefetch_wait_s=0.06))
    engine.judge = object()

    def clef(*args):
        time.sleep(0.04)
        return {}

    monkeypatch.setattr(module.clef, "ask", clef)
    tools = turn_tools_slow_weather
    started = time.monotonic()
    data, note = engine._prefetch("mai có mưa không", tools.state, tools)
    assert time.monotonic() - started < 0.2
    assert "thoi_tiet" not in data and "deadline=1" in note
    assert "weather" in tools.tool_names()


def test_turn_tool_and_block_spans_cover_cached_and_rendered_paths(turn_tools):
    from trip.api.blocks import watch
    tools = turn_tools()
    watch(tools, lambda *_: None, lambda ids: [])
    args = {"criteria": {"groups": ["cafe"]}}
    result = tools.run("find_places", args)
    tools.model_called("find_places", result, args)
    tools.run("find_places", args)
    assert sum(t.startswith("t_tool name=find_places ") for t in tools.timings) == 2
    assert any(t.startswith("t_find ") for t in tools.timings)
    assert any(t.startswith("t_block name=find_places ") for t in tools.timings)


def test_langchain_transport_reports_local_http_spans_without_inventing_queue(monkeypatch):
    import asyncio
    import httpx
    import json
    from agents.assistant import loop as module
    from agents.assistant.loop import ChatSettings, langchain_chat

    original = httpx.AsyncClient

    async def respond(request):
        chunk = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "fixture",
                 "choices": [{"index": 0, "delta": {"content": "ok"}, "finish_reason": None}]}
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content=f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode())

    class LocalClient(original):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", LocalClient)

    class Client:
        base_url, api_key = "http://fixture/v1", "fixture"

        async def close(self):
            pass

    class Role:
        client = staticmethod(lambda: (Client(), "fixture"))
        reasoning = staticmethod(lambda: None)

    monkeypatch.setattr(module, "AGENT", Role)
    out = asyncio.run(langchain_chat(ChatSettings())([{"role": "user", "content": "x"}], [], lambda _: None))
    latency = out.response_metadata["latency"]
    assert out.text == "ok"
    assert 0 <= latency["dispatch"] <= latency["headers"] <= latency["ttft"]
    assert latency["queue"] == "unknown"


def test_agent_ttft_is_per_call_not_per_turn(turn_tools):
    import asyncio
    from agents.assistant import run_loop
    from langchain_core.messages import AIMessageChunk

    tools = turn_tools()
    calls = []

    async def chat(messages, offered, on_say, on_args=None):
        calls.append(1)
        await asyncio.sleep(0.02)
        on_args(None)
        if len(calls) == 1:
            return AIMessageChunk(content="", tool_call_chunks=[{"name": "find_places", "args": '{"criteria":{"groups":["cafe"]}}', "id": "a", "index": 0}])
        return AIMessageChunk(content="Mình đã tìm được quán.")

    asyncio.run(run_loop(chat, [{"role": "user", "content": "tìm quán"}], tools, lambda _: None, 3))
    spans = [t for t in tools.timings if t.startswith("t_call_span ")]
    assert len(spans) == 2
    for index, span in enumerate(spans, 1):
        assert f"call={index} " in span and "queue=unknown" in span
        ttft = float(span.split("ttft=")[1].split()[0])
        assert 0.015 <= ttft < 0.1
