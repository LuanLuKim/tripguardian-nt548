"""Tool registry of the shared assistant core (docs/TRIP_UNDERSTANDING.md §Lõi trợ lý).

A tool is one input model (`tool_name` ClassVar, docstring = the words the model reads, fields = its schema) plus a
function. Read tools are shared by every chat; action tools belong to one stage ("trip", "decision"). A context block is
one key of the turn's CURRENT CONTEXT message. Registering is the only way to give the assistant a tool.

    @read_tool(FindPlaces, group="places", place_args=("near_place",))
    def find_places(turn, inp: FindPlaces) -> dict: ...

    @action_tool("decision", SelectPlace)
    def select(turn, inp: SelectPlace) -> dict: ...

    @context_block("decision", "view")
    def view(turn) -> dict: ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel

Kind = Literal["read", "action"]
# Flags a turn carries; a tool with `requires` is offered only when the turn has that flag.
FLAGS = ("assistant", "cards", "web")


@dataclass(frozen=True)
class Tool:
    name: str
    model: type[BaseModel]
    run: Callable[[Any, dict], dict]  # (turn, raw arguments) -> result; an error is {"error": "..."} or a raised ValueError
    kind: Kind
    stage: str | None = None  # None: offered in every stage (read tools); "trip" / "decision": action tools of that stage
    group: str | None = None  # the bench's tool-group name for the case family (places, detail, weather, ...)
    cache: bool = True  # read tools: the result is kept for the turn, a repeat of the same arguments reads it
    cards: Callable[[Any, dict], list[str]] | None = None  # place ids a result shows as cards (sent when the model's call returns)
    place_args: tuple[str, ...] = ()  # arguments that are place references; the turn maps a written name to an id
    requires: str | None = None
    offered: bool = True  # False: runnable by the turn itself (record_fact runs a dish lookup) but never listed to the model

    @property
    def description(self) -> str:
        return " ".join((self.model.__doc__ or self.name).split())


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._context: dict[str, dict[str, Callable[[Any], Any]]] = {}

    def add(self, tool: Tool) -> Tool:
        old = self._tools.get(tool.name)
        if old is not None and old.run is not tool.run and old.model is not tool.model:
            raise ValueError(f"tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool  # a module reloaded in tests registers again: the later one wins
        return tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def names(self, stage: str, flags: frozenset[str] | set[str] = frozenset()) -> list[str]:
        """The tools a turn of `stage` offers with `flags`, in registration order (stable, so the prompt prefix is)."""
        return [t.name for t in self._tools.values()
                if t.offered and (t.stage in (None, stage)) and (t.requires is None or t.requires in flags)]

    def is_read(self, name: str) -> bool:
        t = self._tools.get(name)
        return t is not None and t.kind == "read"

    def reads(self) -> list[Tool]:
        return [t for t in self._tools.values() if t.kind == "read"]

    def add_context(self, stage: str, key: str, fn: Callable[[Any], Any]) -> None:
        self._context.setdefault(stage, {})[key] = fn

    def context(self, stage: str, turn: Any) -> dict:
        """The registered blocks of `stage` for `turn`; a block that returns None is left out, one that raises is
        left out too (a bad block must not kill the turn)."""
        out: dict = {}
        for key, fn in self._context.get(stage, {}).items():
            try:
                value = fn(turn)
            except Exception:  # noqa: BLE001 - the model works without the block
                continue
            if value is not None:
                out[key] = value
        return out


REGISTRY = Registry()


def _validated(model: type[BaseModel], fn: Callable) -> Callable[[Any, dict], dict]:
    def run(turn, args: dict) -> dict:
        return fn(turn, model.model_validate(args))
    run.__name__ = getattr(fn, "__name__", "tool")
    return run


def read_tool(model: type[BaseModel], *, group: str | None = None, cards: Callable[[Any, dict], list[str]] | None = None,
              place_args: tuple[str, ...] = (), cache: bool = True, requires: str | None = "assistant",
              registry: Registry = REGISTRY):
    """Register `fn(turn, inp)` as a read-only tool of every stage. Its result is cached for the turn by its arguments,
    its place ids (`cards`) are sent as cards the moment the model's call returns."""
    def deco(fn: Callable) -> Callable:
        registry.add(Tool(model.tool_name, model, _validated(model, fn), "read", None, group, cache, cards, place_args, requires))
        return fn
    return deco


def action_tool(stage: str, model: type[BaseModel], *, requires: str | None = None, offered: bool = True,
                registry: Registry = REGISTRY):
    """Register `fn(turn, inp)` as an action tool of one stage. It may change the stage's state; it is never cached."""
    def deco(fn: Callable) -> Callable:
        registry.add(Tool(model.tool_name, model, _validated(model, fn), "action", stage, None, False, None, (), requires, offered))
        return fn
    return deco


def context_block(stage: str, key: str, registry: Registry = REGISTRY):
    """Register `fn(turn) -> json-able | None` as the `key` of the stage's CURRENT CONTEXT."""
    def deco(fn: Callable) -> Callable:
        registry.add_context(stage, key, fn)
        return fn
    return deco
