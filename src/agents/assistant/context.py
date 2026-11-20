"""The turn's messages around the model call (docs/LLM_ARCHITECTURE.md §6.3).

Order: static system prompt, the history window, CURRENT CONTEXT (a `user` message: 9router drops a second `system`
message), the user's new words. Nothing in the first two changes from turn to turn except by whole blocks, so the
provider's prompt cache holds.
"""

from __future__ import annotations

import json
from typing import Callable

HISTORY_KEEP = 24  # user turns kept word for word
HISTORY_DROP = 12  # when more than HISTORY_KEEP, this many of the oldest go at once (the cache breaks once per 12 turns)
SLOT_KEEP = 2  # last_shown turns and photos kept in CURRENT CONTEXT
CONTEXT_HEAD = "CURRENT CONTEXT\n"


def window(messages: list[dict], keep: int = HISTORY_KEEP, drop: int = HISTORY_DROP) -> list[dict]:
    """The history the model reads: all of it up to `keep` user turns; past that the oldest `drop` turns go in one step
    (and again every `drop` turns), so the start of the history stays the same for `drop` turns in a row. What was said
    in the dropped turns stays in the TripState, which CURRENT CONTEXT carries."""
    starts = [i for i, m in enumerate(messages) if m["role"] == "user"]
    if len(starts) <= keep:
        return list(messages)
    cut = -(-(len(starts) - keep) // drop) * drop  # whole blocks of `drop` turns
    return list(messages[starts[cut]:]) if cut < len(starts) else []


def context_message(context: dict) -> dict:
    """CURRENT CONTEXT as the `user` message that carries it."""
    return {"role": "user", "content": CONTEXT_HEAD + json.dumps(context, ensure_ascii=False)}


def last_shown(transcript: list[dict], name_of: Callable[[str], str | None], keep: int = SLOT_KEEP) -> list[dict]:
    """The cards of the last `keep` turns that showed some: [{turn, ids, names, tool, args}], newest last. `tool` and `args`
    are the read call that produced them (so "xem thêm kiểu vừa rồi" can run it again); absent when a turn sent
    cards some other way."""
    by_turn: dict[int, dict] = {}
    for t in transcript:
        if t.get("role") != "agent" or t.get("kind") != "places":
            continue
        turn = int(t.get("turn") or 0)
        entry = by_turn.setdefault(turn, {"turn": turn, "ids": [], "tool": None, "args": None})
        entry["ids"] += [i for i in t.get("ids") or () if i not in entry["ids"]]
        if t.get("tool") and not entry["tool"]:
            entry["tool"], entry["args"] = t["tool"], t.get("args")
    out = []
    for turn in sorted(by_turn)[-keep:]:
        e = by_turn[turn]
        out.append({"turn": turn, "ids": e["ids"], "names": [n for i in e["ids"] if (n := name_of(i))],
                    **({"tool": e["tool"], "args": e["args"]} if e["tool"] else {})})
    return out
