"""The shared tool loop: the model calls tools until it asks the user, finishes, or runs out of steps.

A stage (Trip, Decision) hands `run_loop` its turn object (a TurnCore subclass). The loop needs from it:
  tool_names / tool / run / log / timings / cache_hits / assistant        (TurnCore and the stage's `run`)
  prefetch(calls, text) / preview_reset() / preview(args) / forget_replies()   what to start while the model writes
  blocked() -> bool                          the rule guard stopped the turn: no further model call
  trim(text) -> str                          the stage's cut of a reply
  on_reply(text)                             a text the model wrote, before it is final (cards first)
  review(text, nudged, state) -> (log, note) | None        a plain reply the stage sends back once (note goes as a `user` message)
  start_calls()                                            a round of calls begins
  after_call(state, out, fails) -> dict | None             a stage rule that ends or nudges the turn after one call
  after_calls(state, out, fails) -> dict                   what follows a round of calls
  note_heads: tuple[str, ...]                the first characters of every note `review` / `after_call` can send
All of them have a default in `LoopHost`.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import operator
import time
import uuid
from dataclasses import dataclass
from typing import Annotated, Awaitable, Callable, Literal, TypedDict

import httpx
import openai
from langchain_core.messages import AIMessage, AIMessageChunk, convert_to_messages
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from corpus.llm import AGENT

from ..runtime import AgentError
from .lc import langchain_tools

log = logging.getLogger(__name__)

# Chat returns the merged LangChain message: `.text` is the reply, `.tool_call_chunks` the calls with raw argument strings.
# A chat may also take `on_args`: it is then handed the record_fact arguments written so far, while the call streams.
Chat = Callable[[list[dict], list[BaseTool], Callable[[str], None]], Awaitable[AIMessageChunk]]
THOUGHT_OPEN, THOUGHT_CLOSE = "<|channel>", "<channel|>"
ASSISTANT_CALLS = 2  # model calls a turn may make with the assistant on: the second is offered no tool
# Error results allowed in one turn before the loop stops calling tools and says the fallback.
MAX_TOOL_FAILS = 4


@dataclass(frozen=True)
class ChatSettings:
    total_s: float = 30
    max_tokens: int = 1500
    service_tier: str = ""  # 9router forwards "priority" to the Codex upstream
    cache_key: str = "trip_turn"  # prompt_cache_key: turns of one stage share the provider's cache


class LoopHost:
    """Defaults for the hooks a stage may leave out. A turn object inherits it next to TurnCore."""
    assistant = False
    note_heads: tuple[str, ...] = ()

    def blocked(self) -> bool:
        return False

    def trim(self, text: str) -> str:
        return text.strip()

    def prefetch(self, calls, text: str) -> None: ...

    def preview_reset(self) -> None: ...

    def preview(self, arguments: str | None) -> None: ...

    def forget_replies(self) -> None: ...

    def on_reply(self, text: str) -> None: ...

    def review(self, text: str, nudged: bool, state: dict) -> tuple[str, str] | None:
        return None

    def start_calls(self) -> None: ...

    def after_call(self, state: dict, out: list[dict], fails: int) -> dict | None:
        return None

    def after_calls(self, state: dict, out: list[dict], fails: int) -> dict:
        return {"messages": out, "fails": fails}


class LoopState(TypedDict):
    """Checkpointed turn state: plain data only. The model, tools, pool and callbacks ride in the nodes'
    closure, never in here (they hold threads and futures and cannot serialize). `nudged` is the turn's
    single second chance."""
    messages: Annotated[list, operator.add]
    steps: int
    fails: int  # error results so far this turn
    nudged: bool
    has_say: bool
    reply_content: str  # the latest assistant reply's text
    reply_calls: list  # its tool calls as plain {id, name, arguments} dicts
    ended: bool  # the turn is over: the routers send it to END
    final: bool  # the next model call is offered no tool (the assistant: its data is all there is)


class Visible:
    """Streamed text minus the reasoning blocks some models (Gemma) write into the content:
    "<|channel>thought ...<channel|>", in front of the reply or after it. A block is held back until it closes, then
    dropped; text that only might be the start of a marker waits for the next delta."""

    def __init__(self):
        self.buf, self.thought = "", False

    def feed(self, delta: str) -> str:
        self.buf += delta
        out = ""
        while True:
            if self.thought:
                i = self.buf.find(THOUGHT_CLOSE)
                if i < 0:
                    return out
                self.buf, self.thought = self.buf[i + len(THOUGHT_CLOSE):].lstrip(), False
                continue
            i = self.buf.find(THOUGHT_OPEN)
            if i >= 0:
                out += self.buf[:i]
                self.buf, self.thought = self.buf[i + len(THOUGHT_OPEN):], True
                continue
            keep = next((k for k in range(min(len(self.buf), len(THOUGHT_OPEN) - 1), 0, -1)
                         if THOUGHT_OPEN.startswith(self.buf[-k:])), 0)  # a marker may be cut between deltas
            out += self.buf[:len(self.buf) - keep]
            self.buf = self.buf[len(self.buf) - keep:]
            return out.replace(THOUGHT_CLOSE, "")

    def end(self) -> str:
        """Held text when the stream ends: a partial marker is text after all; an unclosed thought is dropped."""
        out, self.buf = ("" if self.thought else self.buf), ""
        return out


def langchain_chat(cfg: ChatSettings) -> Chat:
    """One streamed call on langchain_openai. Returns the merged message, not a copy of it: LangChain's `tool_calls`
    would turn broken JSON into {}, hiding the error from the loop, so the raw argument strings are read from
    `tool_call_chunks`. The reasoning block the model writes into the text is filtered here, before the loop sees it.
    The endpoint still comes from AGENT.client(): only the client library changes. The usage (with the cached prompt
    tokens) is kept on the returned message."""
    async def chat(messages: list[dict], tools: list[dict], on_say: Callable[[str], None],
                   on_args: Callable[[str], None] | None = None) -> AIMessageChunk:
        client, model = AGENT.client()
        # an HTTP client of this call's own: each turn runs in a fresh event loop, and LangChain's shared default
        # client stays bound to the loop that first used it
        http = httpx.AsyncClient(timeout=cfg.total_s)
        effort = AGENT.reasoning()
        extra = AGENT.cache_key(cfg.cache_key) if effort else {}
        if cfg.service_tier:
            extra = {**extra, "service_tier": cfg.service_tier}
        llm = ChatOpenAI(model=model, base_url=str(client.base_url), api_key=client.api_key, temperature=0.2,
                         max_tokens=cfg.max_tokens, timeout=cfg.total_s, max_retries=0, http_async_client=http,
                         stream_usage=True,
                         **({"reasoning_effort": effort} if effort else {}), **({"extra_body": extra} if extra else {}))
        full, visible, shown = None, Visible(), ""

        def show(text: str) -> None:
            nonlocal shown
            if text:
                shown += text
                on_say(text)
        try:
            async with asyncio.timeout(cfg.total_s):
                bound = llm.bind_tools(tools, tool_choice="auto") if tools else llm  # no tool: the reply only
                async for chunk in bound.astream(convert_to_messages(messages)):
                    if full is None and on_args is not None:
                        on_args(None)  # the first chunk: the model has read the prompt (timing only)
                    full = chunk if full is None else full + chunk  # merges tool-call pieces by index
                    show(visible.feed(chunk.text))
                    if on_args is not None and chunk.tool_call_chunks:
                        for t in full.tool_call_chunks:
                            if t.get("name") == "record_fact":
                                on_args(t.get("args") or "")
                show(visible.end())
        except (openai.OpenAIError, TimeoutError) as e:
            raise AgentError(f"agent call failed: {type(e).__name__}: {str(e)[:200]}") from e
        finally:
            await http.aclose()
            await client.close()
        # the reasoning markers are gone from the text the loop sees; the tool-call pieces stay raw
        return AIMessageChunk(content=shown, tool_call_chunks=full.tool_call_chunks if full else [],
                              usage_metadata=getattr(full, "usage_metadata", None))
    return chat


def route_from_agent(state: LoopState) -> Literal["execute", "review", "__end__"]:
    """A model reply with tool calls is executed; a plain reply is reviewed; a turn that ended stops."""
    if state["ended"]:
        return END
    return "execute" if state["reply_calls"] else "review"


def route_back_to_agent(state: LoopState) -> Literal["agent", "__end__"]:
    """After tools or review: the model goes again unless the turn ended."""
    return END if state["ended"] else "agent"


def is_error(content: str) -> bool:
    """A tool result counts as failed when it is an error object, or the plain-text error ToolNode writes for an
    unknown tool."""
    try:
        return "error" in json.loads(content)
    except (ValueError, TypeError):
        return True


def cached_tokens(reply) -> tuple[int, int] | None:
    """(prompt tokens the provider's cache served, prompt tokens) of a reply, None when the endpoint sent no usage."""
    usage = getattr(reply, "usage_metadata", None) or {}
    if not usage.get("input_tokens"):
        return None
    return int((usage.get("input_token_details") or {}).get("cache_read") or 0), int(usage["input_tokens"])


async def run_loop(chat: Chat, messages: list[dict], tools, on_say: Callable[[str], None],
                   max_steps: int, on_retry: Callable[[], None] = lambda: None) -> None:
    """Run one turn through the agent graph (agent -> execute | review). `tools` is the stage's turn object (module
    docstring). `messages` grows in place, results stay on `tools`, text streams through `on_say`. The turn gets a
    single second chance (`nudged`). The turn checkpoints to memory after every node; resuming from a checkpoint is
    wired but the engine always starts fresh."""

    async def agent_node(state: LoopState) -> dict:
        if state["steps"] >= max_steps or (tools.assistant and state["steps"] >= ASSISTANT_CALLS):
            tools.log.append("step_cap")
            return {"ended": True}
        if tools.blocked():  # the rule guard answered: no more model calls for this turn
            tools.log.append("guard_stop")
            return {"ended": True}
        steps = state["steps"] + 1
        # the assistant's last allowed call, or one after a response the cache answered whole: no tool is offered
        final = tools.assistant and (state.get("final") or steps == ASSISTANT_CALLS)
        started, hs = False, state["has_say"]

        def on_call_say(delta: str) -> None:
            nonlocal started, hs
            if not delta:
                return
            if not started:
                if hs:
                    on_retry()
                    tools.forget_replies()
                started = hs = True
            on_say(delta)

        started_at = time.monotonic()
        tools.preview_reset()
        use = [] if final else offered
        reply = await (chat(state["messages"], use, lambda delta: None, on_args=tools.preview) if streams_args
                       else chat(state["messages"], use, lambda delta: None))
        tools.timings.append(f"t_call {time.monotonic() - started_at:.1f}")  # where a slow turn spends its time
        if (c := cached_tokens(reply)) is not None:
            tools.timings.append(f"cached_tokens {c[0]}/{c[1]}")
        text = tools.trim(reply.text)
        calls = [{"id": t["id"] or f"call_{uuid.uuid4().hex[:8]}", "name": t["name"] or "",
                  "arguments": t["args"]}
                 for t in sorted(reply.tool_call_chunks, key=lambda t: t["index"] or 0)] if not final else []
        for c in calls:
            try:
                args = json.loads(c["arguments"])
                if not isinstance(args, dict):
                    raise ValueError
                if c["name"] == "record_fact" and isinstance(args.get("say"), str) and args["say"].strip() and not text:
                    text = tools.trim(args["say"])  # the reply written with the facts is the turn's text
            except (ValueError, TypeError):
                c["arguments"] = "{}"
                c["argument_error"] = "arguments were not valid JSON for an object; retry with a JSON object"
        on_call_say(text)
        if text:
            tools.on_reply(text)  # cards for the places it names go out now, not when the text is final
        tools.prefetch(calls, text)  # Clef starts checking now, while the tools run or the review waits
        return {"steps": steps, "has_say": hs, "reply_content": text, "reply_calls": calls,
                "messages": [{"role": "assistant", "content": text or None,
                              "tool_calls": [{"id": c["id"], "type": "function",
                                              "function": {"name": c["name"], "arguments": c["arguments"]}}
                                             for c in calls]}] if calls else []}

    async def review_node(state: LoopState) -> dict:
        """A reply with no tool call: the stage may send it back once (the turn's one second chance, as a `user` note);
        anything else ends the turn."""
        text = state["reply_content"]
        if tools.assistant and state["steps"] >= ASSISTANT_CALLS:  # no call is left for a second chance
            return {"ended": True}
        if (sent := await asyncio.to_thread(tools.review, text, state["nudged"], dict(state))) is not None:
            why, note = sent
            tools.log.append(why)
            on_retry()
            tools.forget_replies()
            return {"nudged": True, "has_say": False,
                    "messages": [{"role": "assistant", "content": text}, {"role": "user", "content": note}]}
        return {"ended": True}

    offered = langchain_tools(tools)
    streams_args = "on_args" in inspect.signature(chat).parameters  # a scripted chat in tests may not take it

    def refuse_call(e: Exception) -> str:
        """A call the input model refuses (an unknown key, a value outside its enum) never reaches the turn: the
        model reads the validation error, and the turn log records it."""
        import re
        text = str(e)
        tool = re.search(r"tool '([^']+)'", text)
        detail = text.split("with error:", 1)[-1]  # the kwargs come before it; the reason is what the bench needs
        detail = " | ".join(x.strip() for x in detail.splitlines() if x.strip() and not x.strip().startswith("Please fix"))
        tools.log.append(f"schema_refused {tool[1] if tool else type(e).__name__}: {detail}"[:300])
        return str(e)
    tool_node = ToolNode(offered, handle_tool_errors=refuse_call)

    async def execute_node(state: LoopState) -> dict:
        """Runs the reply's tool calls one at a time through ToolNode, in the model's order: a fact can depend on the
        one before it, and the turn object is not safe to share between threads. A call whose arguments are not a JSON
        object never reaches a tool: the model gets the error for that call."""
        out: list[dict] = []
        fails = state["fails"]
        tools.start_calls()
        hits = tools.cache_hits
        for c in state["reply_calls"]:
            try:
                if c.get("argument_error"):
                    raise ValueError(c["argument_error"])
                args = json.loads(c["arguments"] or "{}")
                if not isinstance(args, dict):
                    raise ValueError
                done = await tool_node.ainvoke({"messages": [AIMessage(content="", tool_calls=[
                    {"id": c["id"], "name": c["name"], "args": args, "type": "tool_call"}])]})
                content = done["messages"][0].content
            except ValueError:
                content = json.dumps({"error": c.get("argument_error", "arguments are not a JSON object")})
            out.append({"role": "tool", "tool_call_id": c["id"], "content": content})
            if is_error(content):
                fails += 1
                if fails >= MAX_TOOL_FAILS:
                    tools.log.append(f"tool_fail_cap {fails}")
                    return {"messages": out, "fails": fails, "ended": True}
            if (stop := tools.after_call(dict(state), out, fails)) is not None:
                return stop
        if tools.assistant and state["reply_calls"] and tools.cache_hits - hits == len(state["reply_calls"]):
            # every call asked for data CURRENT CONTEXT already held: its reply stands, or one call with no tool
            tools.log.append("cache_only")
            if (state["reply_content"] or "").strip():
                return {"messages": out, "fails": fails, "ended": True}
            return {"messages": out, "fails": fails, "final": True}
        return tools.after_calls(dict(state), out, fails)

    graph = StateGraph(LoopState)
    graph.add_node("agent", agent_node)
    graph.add_node("review", review_node)
    graph.add_node("execute", execute_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_from_agent)
    graph.add_conditional_edges("review", route_back_to_agent)
    graph.add_conditional_edges("execute", route_back_to_agent)
    compiled = graph.compile(checkpointer=MemorySaver())
    # Every agent call counts one step and each execute or review follows one agent call, so the graph never needs
    # more than 2 * max_steps + 1 super-steps. The framework limit is only a backstop against a graph bug.
    final = await compiled.ainvoke({"messages": list(messages), "steps": 0, "fails": 0, "nudged": False,
                                    "has_say": False, "reply_content": "", "reply_calls": [], "ended": False,
                                    "final": False},
                                   {"configurable": {"thread_id": f"{tools.stage}-{uuid.uuid4().hex[:8]}"},
                                    "recursion_limit": 2 * max_steps + 4})
    messages[:] = persisted(final["messages"], tools.note_heads)


def persisted(msgs: list[dict], note_heads: tuple[str, ...] = ()) -> list[dict]:
    """The history the caller keeps: a reply that was sent back, and the note that sent it back, are dropped.
    Notes are only ever appended at the tail of a turn, so the prompt prefix the model saw stays unchanged."""
    out: list[dict] = []
    for m in msgs:
        if m["role"] == "user" and note_heads and (m.get("content") or "").startswith(note_heads):
            if out and out[-1]["role"] == "assistant" and not out[-1].get("tool_calls"):
                out.pop()
            continue
        out.append(m)
    return out
