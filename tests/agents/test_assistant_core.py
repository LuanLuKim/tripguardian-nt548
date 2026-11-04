"""The shared assistant core: registry, per-turn cards, history window, last_shown."""

import asyncio
from typing import ClassVar

import pytest
from langchain_core.messages import AIMessageChunk
from pydantic import BaseModel, ConfigDict

from agents.assistant import LoopHost, Registry, TurnCore, action_tool, context_block, last_shown, read_tool, run_loop, window


class Ping(BaseModel):
    """Answer with a place."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "ping"
    q: str


class Act(BaseModel):
    """Do something."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "act"


def fresh():
    reg = Registry()

    @read_tool(Ping, group="places", registry=reg)
    def ping(turn, inp):
        return {"places": [{"id": "p1"}], "_cards": ["p1", "p2"], "q": inp.q}

    @action_tool("decision", Act, registry=reg)
    def act(turn, inp):
        return {"ok": True}

    @context_block("decision", "view", registry=reg)
    def view(turn):
        return {"n": 1}
    return reg


def test_tools_are_listed_per_stage_and_flag():
    reg = fresh()
    assert reg.names("trip", set()) == []  # a read tool needs the assistant flag
    assert reg.names("decision", {"assistant"}) == ["ping", "act"]
    assert reg.get("ping").description == "Answer with a place." and reg.is_read("ping") and not reg.is_read("act")


def test_trip_stage_does_not_see_decision_actions():
    reg = fresh()
    assert "act" not in reg.names("trip", {"assistant"}) and "ping" in reg.names("trip", {"assistant"})


def test_the_function_gets_the_validated_model():
    reg = fresh()
    assert reg.get("ping").run(None, {"q": "x"})["q"] == "x"


def test_context_blocks_skip_a_failing_block():
    reg = fresh()
    reg.add_context("decision", "bad", lambda t: 1 / 0)
    assert reg.context("decision", None) == {"view": {"n": 1}}


def test_cards_go_out_once_at_the_models_call_and_never_in_a_blocked_turn():
    reg = fresh()
    sent = []
    t = TurnCore("trip", {"assistant"}, known_ids=lambda i: True, on_cards=lambda ids, why: sent.append(ids), registry=reg)
    result = reg.get("ping").run(t, {"q": "a"})
    assert sent == []  # a prepared result is not shown: nobody has read it yet
    shown = t.model_called("ping", result, {"q": "a"})
    assert sent == [["p1", "p2"]] and "_cards" not in shown and shown["places"] == [{"id": "p1"}]
    t.model_called("ping", result, {"q": "a"})
    assert sent == [["p1", "p2"]] and t.card_lists[0]["tool"] == "ping" and t.card_lists[0]["args"] == {"q": "a"}
    t.emit_cards(["p2", "p3"], "vì sao")
    assert sent[-1] == ["p3"]
    blocked = TurnCore("trip", {"assistant"}, on_cards=lambda ids, why: sent.append(ids), registry=reg)
    blocked.cards_blocked = True
    blocked.model_called("ping", result)
    assert blocked.card_lists == []


def test_curation_words_ride_with_cards_already_out():
    t = TurnCore("trip", on_cards=lambda *_: None)
    t.emit_cards(["a", "b", "c"])
    assert t.emit_cards(["b"], "gần hồ") == [] and t.card_lists[0]["why"] == "gần hồ"


def msgs(n):
    out = []
    for i in range(n):
        out += [{"role": "user", "content": f"u{i}"}, {"role": "assistant", "content": f"a{i}"}]
    return out


def users(m):
    return [x["content"] for x in m if x["role"] == "user"]


def test_history_window_drops_twelve_at_once():
    assert len(users(window(msgs(24)))) == 24
    assert users(window(msgs(25)))[0] == "u12" and len(users(window(msgs(25)))) == 13
    assert users(window(msgs(36)))[0] == "u12" and users(window(msgs(36)))[-1] == "u35"
    assert users(window(msgs(37)))[0] == "u24"
    # the start of the history is the same for twelve turns in a row: the prompt cache holds
    assert {users(window(msgs(n)))[0] for n in range(25, 37)} == {"u12"}


def test_last_shown_keeps_the_last_two_turns_with_their_query():
    tr = [{"role": "agent", "kind": "places", "turn": 1, "ids": ["a"], "why": ""},
          {"role": "agent", "kind": "places", "turn": 2, "ids": ["b", "c"], "why": "", "tool": "find_places", "args": {"criteria": {}}},
          {"role": "agent", "kind": "places", "turn": 5, "ids": ["d"], "why": ""},
          {"role": "agent", "kind": "say", "turn": 5, "text": "x"}]
    out = last_shown(tr, lambda i: i.upper())
    assert [e["turn"] for e in out] == [2, 5] and out[0]["names"] == ["B", "C"] and out[0]["tool"] == "find_places"
    assert "tool" not in out[1]


@pytest.mark.parametrize("stage", ["trip", "decision", "planning"])
def test_last_assistant_call_executes_actions_but_never_another_read_or_model_call(stage):
    reg = Registry()

    @read_tool(Ping, registry=reg)
    def ping(turn, inp):
        turn.reads.append(inp.q)
        return {"q": inp.q}

    @action_tool(stage, Act, registry=reg)
    def act(turn, inp):
        turn.written = True
        return {"ok": True}

    class Turn(TurnCore, LoopHost):
        assistant = True

        def run(self, name, args):
            return self.tool(name).run(self, args)

    turn = Turn(stage, {"assistant"}, registry=reg)
    turn.reads, turn.written = [], False
    seen = []

    async def chat(messages, tools, on_say):
        seen.append({t.name for t in tools})
        assert len(seen) <= 2, "the action must not add a third model call"
        calls = [("ping", '{"q":"first"}')] if len(seen) == 1 else [
            ("ping", '{"q":"forbidden last read"}'), ("act", "{}")]
        return AIMessageChunk(content="", tool_call_chunks=[
            {"id": f"c{len(seen)}-{i}", "name": name, "args": args, "index": i}
            for i, (name, args) in enumerate(calls)])

    asyncio.run(run_loop(chat, [{"role": "user", "content": "keep my facts"}], turn, lambda _: None, 6))
    assert turn.written
    assert turn.reads == ["first"]
    assert len(seen) == 2 and seen[1] == {"act"}
