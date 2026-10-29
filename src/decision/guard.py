"""Checks an agent TurnPlan before it touches the session (docs/PLACE_DECISION.md §18): quotes come from the message, aliases are on
screen, values are in the allowed sets; `say` holds no number or place name the user and the screen do not hold."""

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from corpus.ontology import load as load_ontology
from trip import contains, squash

Op = Literal["select", "drop", "lock", "travel", "crowd", "price", "trip", "visited", "prefer", "filter", "unfilter",
             "like"]
FEEDBACK = {"travel": "far", "crowd": "crowded", "price": "pricey"}
REASONS = ("far", "crowded", "pricey", "dislike", "visited")
PLACE_OPS = {"select", "lock", "drop", "visited", "like"}
OPENS_BY = "opens_by"  # the one filter key that is not an ontology feature: "opens at or before HH:MM"
HHMM = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PlanUpdate(Frozen):
    op: Op
    place: str = ""
    value: str = ""
    quote: str

    @model_validator(mode="before")
    @classmethod
    def _tolerant(cls, data):
        """The live model (sol via 9router) does not hold to the JSON schema: it writes the op as "type" or "action"
        and drops empty keys (2026-10-16: every chat turn fell back). The guard still checks every quote and alias."""
        if isinstance(data, dict):
            data = dict(data)
            if "op" not in data:
                data["op"] = data.get("type") or data.get("action")
            data = {k: v for k, v in data.items() if k in cls.model_fields}
        return data


class TurnPlan(Frozen):
    say: str
    updates: tuple[PlanUpdate, ...] = ()


@dataclass
class Guarded:
    actions: list[dict]
    say: str
    log: list[str] = field(default_factory=list)


def filter_ok(key, value) -> bool:
    """A filter the session may hold: opens_by=HH:MM, or an ontology feature with one of its values."""
    if key == OPENS_BY:
        return isinstance(value, str) and bool(HHMM.fullmatch(value))
    return bool(load_ontology().valid(key, value))


def _pair(value: str) -> tuple[str, str] | None:
    key, sep, val = value.partition("=")
    return (key.strip(), val.strip()) if sep and key.strip() and val.strip() else None


def names_in(text: str, name: str) -> bool:
    """The user named this place: its whole name, or its last two words (the distinctive part of most names)."""
    words = squash(name).split()
    return contains(text, name) or (len(words) >= 2 and contains(text, " ".join(words[-2:])))


def _named(quote: str, name: str, name_keys) -> bool:
    """The quote names this place: the whole name, or its last two words when no other place ends the same way."""
    if contains(quote, name):
        return True
    words = squash(name).split()
    if len(words) < 2 or not contains(quote, " ".join(words[-2:])):
        return False
    tail = " ".join(words[-2:])
    return sum(1 for k, _ in name_keys if k == tail or k.endswith(" " + tail)) <= 1


def guard(plan: TurnPlan, text: str, aliases: dict[str, dict], screen_text: str,
          name_keys: list[tuple[str, str]]) -> Guarded:
    """aliases: "P1" -> {"id", "name", ...}; screen_text: what the user sees (its numbers may be repeated);
    name_keys: (squashed name, id) of every place whose name is long enough to recognise in text."""
    log, actions = [], []
    for u in plan.updates:
        if not contains(text, u.quote):
            log.append(f"drop {u.op}: quote {u.quote!r} not in the message")
            continue
        place = aliases.get(u.place) if u.place else None
        if u.place and place is None:
            log.append(f"drop {u.op}: unknown alias {u.place!r}")
            continue
        if u.op in PLACE_OPS and place is None:
            log.append(f"drop {u.op}: needs a place")
            continue
        if u.op in ("select", "lock") and not _named(u.quote, place["name"], name_keys):
            log.append(f"drop {u.op}: the user did not name {place['name']!r}")
            continue
        if u.op in ("select", "lock"):
            actions.append({"type": u.op, "place_id": place["id"]})
        elif u.op == "drop":
            actions.append({"type": "drop", "place_id": place["id"], "reason": u.value if u.value in REASONS else None})
        elif u.op == "visited":
            actions.append({"type": "drop", "place_id": place["id"], "reason": "visited"})
        elif u.op in FEEDBACK:
            actions.append({"type": "feedback", "reason": FEEDBACK[u.op]})
        elif u.op == "trip":
            actions.append({"type": "trip", "text": u.quote.strip()})
        elif u.op == "like":
            actions.append({"type": "like", "place_id": place["id"]})
        elif u.op == "unfilter":
            actions.append({"type": "unfilter"})
        elif u.op in ("prefer", "filter"):
            avoid = u.op == "prefer" and u.value.endswith(":avoid")
            pair = _pair(u.value[:-len(":avoid")] if avoid else u.value)
            if pair is None:
                log.append(f"drop {u.op}: value {u.value!r} is not <feature>=<value>")
            elif u.op == "prefer" and not load_ontology().valid(*pair):
                log.append(f"drop prefer: {pair[0]}={pair[1]} is not in the ontology")
            elif u.op == "filter" and not filter_ok(*pair):
                log.append(f"drop filter: {pair[0]}={pair[1]} is not a filter")
            elif u.op == "prefer":
                actions.append({"type": "prefer", "feature": pair[0], "value": pair[1], "weight": -1 if avoid else 1})
            else:
                actions.append({"type": "filter", "key": pair[0], "value": pair[1]})
    say = plan.say.strip()
    why = _bad_say(say, f"{text} {screen_text}", aliases, name_keys)
    if why:
        log.append(f"say replaced: {why}")
        say = ""
    return Guarded(actions, say, log)


def _bad_say(say: str, heard: str, aliases: dict[str, dict], name_keys) -> str | None:
    said = set(re.findall(r"\d+", heard))
    extra = [n for n in re.findall(r"\d+", say) if n not in said]
    if extra:
        return f"numbers {extra} not said or shown"
    shown = {a["id"] for a in aliases.values()}
    s = f" {squash(say)} "
    for key, pid in name_keys:
        if pid not in shown and f" {key} " in s:
            return f"names place {pid}"
    return None
