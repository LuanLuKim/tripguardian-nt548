"""What a chat showed about the user, written by the Agent for their next trips (docs/TRIP_UNDERSTANDING.md §17).

The engine writes a memo when the itinerary is confirmed and when the chat has been quiet for a while, only when the
chat has turns the last memo did not read (Engine.remember). The memo is a prior for later trips, never a fact or a
constraint of one: the next chat reads it in CURRENT CONTEXT remembered and this trip's words win.
"""

import json
import re
from typing import Callable, Literal

from pydantic import Field, ValidationError

from .state import Frozen, TripState

SAID_MAX = 40  # the user's latest lines the memo reads (with the previous memo, it keeps what older lines said)
REMEMBERED_MAX = 4  # memos of earlier chats the next chat reads, newest first


class Taste(Frozen):
    text: str = Field(max_length=100)  # in the user's words where possible: "quán cà phê sân vườn, sáng sớm"
    lean: Literal["love", "like", "avoid"]
    quote: str = Field("", max_length=160)  # what they said or picked that shows it


class Need(Frozen):
    text: str = Field(max_length=100)  # "đau gối, tránh leo dốc", "ăn chay"
    quote: str = Field("", max_length=160)


class Memo(Frozen):
    tastes: tuple[Taste, ...] = Field((), max_length=12)
    looks: tuple[str, ...] = Field((), max_length=6)  # the visual styles of places they chose: "mộc mạc, nhiều cây xanh"
    needs: tuple[Need, ...] = Field((), max_length=6)  # health, body or diet needs of the user themself
    notes: tuple[str, ...] = Field((), max_length=6)  # how they travel: pace, occasion, who they like to go with


PROMPT = """You keep the travel profile of one user of a Đà Lạt trip assistant. Read what this chat shows about them
(CHAT: their own lines, what they picked on photo cards and place cards, the places and kinds they kept with what each
looks like and what reviews confirm of it) and write the memo for their next trips. PREVIOUS is the memo of this same
chat written earlier: keep what still holds, change what the new lines changed, drop what they took back.

- tastes: what they like or avoid in places and experiences, each in their own words where possible, lean love (said
  strongly or picked again and again), like, or avoid, with the quote or pick that shows it.
- looks: the visual styles of what they chose (from looks, looks_like and the kinds), in a few Vietnamese words each.
- needs: health, body or diet needs of the user themself (đau gối, say xe, ăn chay, dị ứng); not of the people with them.
- notes: how they travel (pace, few or many stops, an occasion they mentioned, what they want a trip to feel like).

Only what the chat shows: a skipped card or an unchosen kind is unknown, not dislike; a place visited is not a place
liked; one-off facts of this trip (dates, budget, who comes this time) are not tastes. Write Vietnamese. Reply with one
JSON object {"tastes": [{"text", "lean", "quote"}], "looks": [], "needs": [{"text", "quote"}], "notes": []} and
nothing else."""


def chat_input(state: TripState, transcript: list[dict], name: Callable[[str], str],
               known_for: Callable[[str], list[str]], looks: Callable[[str], list[str]],
               kind_looks: Callable[[tuple[str, ...]], list[str]]) -> dict:
    """The chat as the memo model reads it: the user's latest lines and what they picked, with what each place looks
    like (its photo styles) and what reviews confirm of it."""
    said = [{"turn": t["turn"], "said": t["text"], **({"by": t["kind"]} if t.get("kind") not in (None, "text") else {})}
            for t in transcript if t.get("role") == "user" and t.get("text")][-SAID_MAX:]

    def place(pid: str) -> dict:
        return {"place": name(pid), **({"looks": s} if (s := looks(pid)) else {}),
                **({"known_for": k} if (k := known_for(pid)) else {})}

    picked = {
        "tastes": [{"key": k, "lean": f.value, **({"quote": q} if (q := next((e.quote for e in reversed(f.evidence) if e.quote), None)) else {})}
                   for k, f in state.soft.items() if f.known and f.value in ("love", "avoid") and f.source == "user"],
        "places_kept": [place(a.place_id) for a in state.anchors if a.place_id and a.priority in ("want", "must")],
        "kinds_kept": [{"kind": w.kind, **({"looks": s} if (s := kind_looks(w.place_ids)) else {}),
                        "for_example": [name(p) for p in w.place_ids[:2]]} for w in state.wishes.kinds],
        "dishes": [w.dish for w in state.wishes.dishes],
        "looks_asked": [{"phrase": v.phrase, "looks_like": list(v.cues)} for v in state.vibes],
        "in_their_words": [u.phrase for u in state.unmapped],
        "said_about_themselves": [{"kind": s.kind, "quote": s.quote} for s in state.signals
                                  if s.source == "user" and s.from_companion is None and s.quote],
    }
    return {"said": said, **{k: v for k, v in picked.items() if v}}


def parse(text: str) -> Memo | None:
    """The model's reply -> a memo; anything else (prose, a broken object, a field too long) -> None."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return Memo.model_validate(json.loads(m.group(0)))
    except (ValueError, ValidationError):
        return None


def remembered(memos: list[Memo]) -> dict | None:
    """Earlier chats' memos (newest first) as one short block for CURRENT CONTEXT remembered: newer wins on a repeat."""
    out: dict[str, list] = {"tastes": [], "looks": [], "needs": [], "notes": []}
    seen: set[str] = set()
    for memo in memos[:REMEMBERED_MAX]:
        for t in memo.tastes:
            if (k := t.text.casefold()) not in seen:
                seen.add(k)
                out["tastes"].append(f"{t.text} ({t.lean})")
        for key, rows in (("looks", memo.looks), ("needs", tuple(n.text for n in memo.needs)), ("notes", memo.notes)):
            for x in rows:
                if (k := x.casefold()) not in seen:
                    seen.add(k)
                    out[key].append(x)
    return {k: v[:8] for k, v in out.items() if v} or None
