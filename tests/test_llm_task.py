import asyncio
import json

import httpx
import openai

from corpus.llm import tasks


class _Msg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class FakeClient:
    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0
        self.chat = type("C", (), {"completions": self})()

    async def create(self, **kw):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return type("R", (), {"choices": [_Msg(json.dumps({"verdict": "supports", "reason": ""}))]})()


def test_server_error_is_retried(monkeypatch):
    monkeypatch.setattr(tasks, "RETRY_S", 0)
    req = httpx.Request("POST", "http://llm")
    err = openai.InternalServerError("Internal error encountered.", response=httpx.Response(500, request=req), body=None)
    client = FakeClient([err])
    out = asyncio.run(tasks.REVIEW_VERIFY.ask(client, "m", name="A", category="c", claim="x", passage="y"))
    assert out["verdict"] == "supports" and client.calls == 2


def test_planning_turn_renders_with_every_field():
    from corpus.llm import PLANNING_TURN
    text = PLANNING_TURN.render(features="noise: quiet|loud", days="Ngày 1: ...", variants="V1 | ...",
                                lodging="L1 | ...", text="bỏ chỗ này đi")
    assert "bỏ chỗ này đi" in text and "V1" in text


class _Stream:
    """An openai-style async stream of text pieces; counts how many were read and whether it was closed."""

    def __init__(self, pieces):
        self.pieces, self.read, self.closed = pieces, 0, False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for p in self.pieces:
            self.read += 1
            yield type("Ch", (), {"choices": [type("D", (), {"delta": type("T", (), {"content": p})()})()]})()

    async def close(self):
        self.closed = True


class StreamClient:
    def __init__(self, streams):
        self.streams, self.calls = list(streams), 0
        self.chat = type("C", (), {"completions": self})()

    async def create(self, **kw):
        assert kw["stream"] is True
        self.calls += 1
        return self.streams.pop(0)


def test_looping_answer_is_cut_and_asked_once_more():
    answer = json.dumps({"verdict": "supports", "reason": ""})
    loop = _Stream(['{"verdict": "supports", "reason": "", "x": '] + ["\n  "] * 1000)
    client = StreamClient([loop, _Stream([answer])])
    out = asyncio.run(tasks.REVIEW_VERIFY.ask(client, "m", name="A", category="c", claim="x", passage="y"))
    assert out["verdict"] == "supports" and client.calls == 2
    assert loop.closed and loop.read < 200  # cut at ~300 chars of whitespace, not read to the end


def test_answer_that_loops_again_fails_after_two_calls():
    client = StreamClient([_Stream(["{"] + [" " * 100] * 10) for _ in range(4)])
    try:
        asyncio.run(tasks.REVIEW_VERIFY.ask(client, "m", name="A", category="c", claim="x", passage="y"))
    except tasks.Runaway:
        pass
    else:
        raise AssertionError("expected Runaway")
    assert client.calls == tasks.RUNAWAYS


def test_pretty_printed_answer_is_not_a_loop():
    pretty = json.dumps({"verdict": "supports", "reason": "ok"}, indent=8)
    client = StreamClient([_Stream(list(pretty))])
    out = asyncio.run(tasks.REVIEW_VERIFY.ask(client, "m", name="A", category="c", claim="x", passage="y"))
    assert out["verdict"] == "supports" and client.calls == 1


def test_asr_check_retries_warmer_then_without_frames(monkeypatch):
    from corpus.crawl.tiktok import asr_check

    calls = []

    async def fake_ask(client, model, images=(), temperature=None, **fields):
        calls.append((temperature, len(images)))
        if len(calls) < 3:
            raise tasks.Runaway("loop")
        return {"segments": [{"i": 0, "status": "ok", "text": "x"}], "quality": "good", "screen_text": ["a"]}

    monkeypatch.setattr(asr_check.ASR_CHECK.__class__, "ask", lambda self, *a, **k: fake_ask(*a, **k))
    out = asyncio.run(asr_check.ask_check(None, "m", [b"x"], 1, city="c"))
    assert out["screen_text"] == [] and out["segments"][0]["i"] == 0
    assert calls == [(None, 1), (asr_check.RETRY_TEMPERATURE, 1), (asr_check.RETRY_TEMPERATURE, 0)]


def test_asr_check_gives_up_after_four_failures(monkeypatch):
    from corpus.crawl.tiktok import asr_check

    calls = []

    async def fake_ask(client, model, images=(), temperature=None, **fields):
        calls.append(temperature)
        raise tasks.SchemaError("$: missing screen_text")

    monkeypatch.setattr(asr_check.ASR_CHECK.__class__, "ask", lambda self, *a, **k: fake_ask(*a, **k))
    try:
        asyncio.run(asr_check.ask_check(None, "m", [b"x"], 1, city="c"))
    except tasks.SchemaError:
        pass
    else:
        raise AssertionError("expected SchemaError")
    assert calls == [None, asr_check.RETRY_TEMPERATURE, asr_check.RETRY_TEMPERATURE, 0.0, 0.0, 0.0]


def test_asr_check_last_resort_is_the_unguided_task(monkeypatch):
    from corpus.crawl.tiktok import asr_check

    guided = []

    async def fake_ask(self, client, model, images=(), temperature=None, **fields):
        guided.append(self.role.guided)
        if self.role.guided:
            raise tasks.Runaway("loop")
        return {"segments": [{"i": 0, "status": "ok", "text": "x"}], "quality": "good", "screen_text": []}

    monkeypatch.setattr(asr_check.ASR_CHECK.__class__, "ask", fake_ask)
    out = asyncio.run(asr_check.ask_check(None, "m", [b"x"], 1, city="c"))
    assert out["quality"] == "good" and guided == [True, True, True, True, False]


def test_asr_check_asks_again_when_the_answer_has_other_segments(monkeypatch):
    from corpus.crawl.tiktok import asr_check

    answers = [[0, 1, 2], [0]]

    async def fake_ask(client, model, images=(), temperature=None, **fields):
        return {"segments": [{"i": i, "status": "ok", "text": "x"} for i in answers.pop(0)], "quality": "good",
                "screen_text": []}

    monkeypatch.setattr(asr_check.ASR_CHECK.__class__, "ask", lambda self, *a, **k: fake_ask(*a, **k))
    out = asyncio.run(asr_check.ask_check(None, "m", [], 1, city="c"))
    assert [a["i"] for a in out["segments"]] == [0]


def test_asr_check_long_transcript_is_checked_in_windows(monkeypatch):
    from corpus.crawl.tiktok import asr_check

    sent = []

    async def fake_ask(client, model, images=(), temperature=None, segments="", **fields):
        n = len(segments.splitlines())
        sent.append(n)
        return {"segments": [{"i": i, "status": "ok", "text": "x"} for i in range(n)],
                "quality": "good" if len(sent) == 1 else "partial", "screen_text": ["Sign"] if len(sent) < 3 else []}

    monkeypatch.setattr(asr_check.ASR_CHECK.__class__, "ask", lambda self, *a, **k: fake_ask(*a, **k))
    segs = [{"start_s": i, "end_s": i + 1, "text": f"t{i}"} for i in range(asr_check.WINDOW * 2 + 5)]
    out = asyncio.run(asr_check.ask_segments(None, "m", [b"x"], segs, city="c"))
    assert sent == [asr_check.WINDOW, asr_check.WINDOW, 5]
    assert [a["i"] for a in out["segments"]] == list(range(len(segs)))
    assert out["quality"] == "partial" and out["screen_text"] == ["Sign"]
