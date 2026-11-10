"""What every assistant turn keeps, whatever the stage: the per-turn tool cache, the places and numbers the reply may
say, the cards sent so far, the log. A stage's turn (Trip's TurnTools, Decision's) extends it and adds its own state."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from .registry import REGISTRY, Registry, Tool

PRIVATE = "_"  # a result key starting with it is for code (card ids); the model never reads it


def public(result: Any) -> Any:
    """`result` as the model reads it: private keys removed."""
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if not str(k).startswith(PRIVATE)}
    return result


class TurnCore:
    stage = ""

    def __init__(self, stage: str, flags: set[str] | frozenset[str] = frozenset(),
                 known_ids: Callable[[str], bool] = lambda _: False, on_cards: Callable[[list[str], str], None] | None = None,
                 registry: Registry = REGISTRY):
        self.stage, self.flags, self.registry = stage, frozenset(flags), registry
        self.known_id = known_ids
        self.on_cards = on_cards  # (ids, why): the stage's way to show cards at once; None = cards only at the end
        self.log: list[str] = []
        self.timings: list[str] = []  # how long each model call took (the turn log, not the agent)
        self.started = time.monotonic()
        self.marked: set[str] = set()
        self.cache: dict[tuple[str, str], dict] = {}  # (read tool, its args as sorted json) -> result, this turn
        self.cache_hits = 0  # read-tool calls answered from the cache this turn
        self.told_ids: set[str] = set()  # places a read tool returned this turn: the reply may name them
        self.told_numbers: set[int] = set()  # numbers in those results: the reply may say them
        self.hidden: set[str] = set()  # tools not offered this turn (what the prepared data already answers)
        self.card_lists: list[dict] = []  # cards sent this turn: {ids, why}, in sending order
        self.cards_sent: list[str] = []  # their ids
        self.cards_blocked = False  # the guard blocked the turn: no card goes out
        self.verdict: Callable[[], bool] | None = None  # the rule guard: waits a little for its answer; True = the turn is stopped
        self.slots: dict = {}  # what the stage's engine hands the turn for its context blocks (photos, links, ...)
        self.current: tuple[str, dict] | None = None  # the model's call being answered: (tool, args)

    # ---------- tools ----------

    def tool_names(self) -> list[str]:
        """The tools this turn offers. The list stays the same from turn to turn on one screen (it heads the prompt, so a
        change would lose the prompt cache): a tool that does not fit the state now refuses when called."""
        return [n for n in self.registry.names(self.stage, self.flags) if n not in self.hidden]

    def tool(self, name: str) -> Tool | None:
        return self.registry.get(name)

    def read_key(self, name: str, args: dict) -> tuple[str, str]:
        return (name, json.dumps(args, sort_keys=True, ensure_ascii=False, default=str))

    def resolve_place(self, ref: str) -> str | None:
        """A place reference the model wrote (an id or a name) as a corpus id; None when it names none or several."""
        return ref if self.known_id(ref) else None

    def map_places(self, tool: Tool, args: dict) -> tuple[dict, str | None]:
        """Place arguments as ids; (args, error) when one names no place (or several): never a guess."""
        if not tool.place_args or not isinstance(args, dict):
            return args, None
        out = dict(args)
        for f in tool.place_args:
            ref = out.get(f)
            if not isinstance(ref, str):
                continue
            pid = self.resolve_place(ref.strip())
            if pid is None:
                return args, (f"no place {ref!r} in the corpus (or more than one fits): there is no data for it; "
                              "say so, do not guess")
            out[f] = pid
        return out, None

    # ---------- timing ----------

    def mark(self, what: str) -> None:
        """The first time `what` happens this turn, logged as seconds since the turn started (where a slow turn waits)."""
        if what not in self.marked:
            self.marked.add(what)
            self.timings.append(f"{what} {time.monotonic() - self.started:.1f}")

    # ---------- cards first ----------

    def emit_cards(self, ids: list[str], why: str = "") -> list[str]:
        """Send cards for the ids not sent yet, at once. -> the ids sent now. A blocked turn sends none."""
        fresh = [i for i in dict.fromkeys(ids) if i not in self.cards_sent]
        if why and (known := [i for i in ids if i in self.cards_sent]):
            # curation of cards already out: the words ride with the list that holds the first of them
            for entry in self.card_lists:
                if known[0] in entry["ids"] and not entry["why"]:
                    entry["why"] = why
                    break
        if not fresh:
            return []
        if not self.cards_blocked and self.verdict is not None:
            self.cards_blocked = self.verdict()  # the guard answers in a fraction of a second; asked once cards are due
        if self.cards_blocked:
            return []
        self.cards_sent += fresh
        self.card_lists.append({"ids": fresh, "why": why,
                                **({"tool": self.current[0], "args": self.current[1]} if self.current else {})})
        if self.on_cards is not None:
            self.on_cards(fresh, why)
        return fresh

    def model_called(self, name: str, result: Any, args: dict | None = None) -> Any:
        """The model's own call of tool `name` returned `result` (not a prepared one that nobody read): its places are
        sent as cards now. -> the result as the model reads it."""
        tool = self.tool(name)
        self.current = (name, args or {}) if tool is not None and tool.kind == "read" else None
        if tool is not None and isinstance(result, dict) and "error" not in result:
            ids = result.get("_cards")
            if ids is None and tool.cards is not None:
                try:
                    ids = tool.cards(self, result)
                except Exception:  # noqa: BLE001 - a card extractor must not kill the turn
                    ids = []
            if ids:
                self.emit_cards([i for i in ids if isinstance(i, str)])
        self.current = None
        return public(result)

    # ---------- what the reply may say ----------

    def remember(self, result: Any) -> None:
        """Every place id and number in a read tool's result: the reply may name and say them. A sum in VND is also kept
        as it is written ("100.000" -> 100 and 0; "100k" -> 100); a share 0..1 as a percent."""
        if isinstance(result, dict):
            if isinstance(result.get("id"), str) and self.known_id(result["id"]):
                self.told_ids.add(result["id"])
            for k, v in result.items():
                if str(k).startswith(PRIVATE):
                    continue
                self.remember(k)  # hours are keys: {"07:00-22:00": "mon,tue"}
                self.remember(v)
        elif isinstance(result, (list, tuple)):
            for v in result:
                self.remember(v)
        elif isinstance(result, bool):
            return
        elif isinstance(result, (int, float)):
            n = int(result)
            self.told_numbers.add(n)
            if isinstance(result, float):
                self.told_numbers.add(round(result))
                if 0 <= result <= 1:
                    self.told_numbers.add(round(result * 100))
            if n >= 1000:
                self.told_numbers.update(int(x) for x in f"{n:,}".split(","))
        elif isinstance(result, str):
            if self.known_id(result):  # a place id anywhere in a result (a list of ids, a row's id) may be named
                self.told_ids.add(result)
                return
            for x in re.findall(r"\d+", result):
                self.remember(int(x))
