"""Result blocks of the chat: what a read tool found, passed to the web as it is, so the screen shows more than the
reply's words. `tags` = a broad ask split into named kinds (subtags), each with its places; `dish` = places that serve
a dish with the evidence (menu, name, review quote, menu price); `services` = utilities / rental / tour / coach rows
(never place cards). All are data the tools already computed; nothing is guessed here. A block with no rows is not
sent (the reply says there is no data)."""

from __future__ import annotations

import time
from typing import Callable

from corpus import tags as corpus_tags
from corpus.serving import dishes as corpus_dishes

from ..domain import covers
from ..domain.text import squash

EVIDENCE_PER_PLACE = 3
SERVICE_KEYS = ("name", "kind", "distance_km", "address", "phone", "website", "hours", "open_status", "rating", "reviews", "maps_url")


def _known(value) -> bool:
    return value not in (None, "", "unknown", [], ())


def _prices(record: dict) -> dict[str, int]:
    return {squash(d["name"]): d["price"] for d in (record.get("menu") or {}).get("dishes") or []
            if isinstance(d.get("price"), int) and d["price"] > 0}


def _evidence(hit: dict, record: dict) -> list[dict]:
    """The place's evidence lines for the dish, best source first: {source, dish, section?, quote?, n?, price_vnd?}."""
    prices = _prices(record)
    lines = sorted(hit.get("evidence") or (), key=lambda e: -corpus_dishes.SOURCE_RANK.get(e["source"], 0))
    out = []
    for e in lines[:EVIDENCE_PER_PLACE]:
        line = {k: e[k] for k in ("source", "dish", "section", "quote", "n") if _known(e.get(k))}
        if (price := prices.get(squash(e.get("dish") or ""))) and e["source"] != "review_order":
            line["price_vnd"] = price
        out.append(line)
    return out


def dish_block(tools, dish: str, ids: list[str], cards_of: Callable) -> dict | None:
    """Evidence for the ids a dish search ranked (already through the trip's hard filters), in their order."""
    if not ids:
        return None
    hits = {h["id"]: h for h in tools.catalog.dishes(dish)}
    records = {r["id"]: r for r in tools.catalog._dish_records()}  # noqa: SLF001 - the records the search read
    places = [{"id": pid, "evidence": _evidence(hits[pid], records.get(pid, {}))} for pid in ids if pid in hits]
    cards = cards_of([p["id"] for p in places])
    shown = {c["id"] for c in cards}
    places = [p for p in places if p["id"] in shown and p["evidence"]]
    return {"kind": "dish", "dish": dish, "places": places, "cards": [c for c in cards if c["id"] in {p["id"] for p in places}]} if places else None


def tags_block(result: dict, cards_of: Callable, title: str | None = None, cover_fit: Callable | None = None) -> dict | None:
    """The tags or subtags of a browse (infrastructure.browse): each with its own cover photo (distinct across the block), its count and its first places;
    `cards` holds the place cards of those places once. `level` = "tags" (kinds to open) or "subtags" (groups of places to
    open); `sig` names the block so the chat does not show it twice; `title` = the tag a drill opened. None when the browse
    found no split or the cards fall short."""
    split = result.get("_split") if isinstance(result, dict) else None
    if not split:
        return None
    per = corpus_tags.config()["group"]["cards_per_subtag"]
    first = {s["id"]: s["place_ids"][:per] for s in split["subtags"]}
    pool = {s["id"]: s["place_ids"][:max(per, covers.POOL)] for s in split["subtags"]}  # a deeper look for the covers
    cards = cards_of(list(dict.fromkeys([p for ids in pool.values() for p in ids] + list(split["ranked"]))))
    by_id = {c["id"]: c for c in cards}
    kept = [s for s in split["subtags"] if len([p for p in first[s["id"]] if p in by_id]) >= 2]
    photo = lambda pid: (by_id[pid].get("photos") or [None])[0] if pid in by_id else None  # noqa: E731
    level = split.get("level", "subtags")
    ranked = [p for p in split["ranked"] if p in by_id] if level == "subtags" else []  # tags open a kind, not a list
    fits = [cover_fit(s["id"]) if cover_fit else None for s in kept] + [None]
    *cover, all_cover = covers.assign([*(pool[s["id"]] for s in kept), ranked], photo, fits=fits)  # each card its own picture, "all" last
    subs = [{"id": s["id"], "axis": s["axis"], "label": s["label"], "count": s["count"],
             "place_ids": [p for p in first[s["id"]] if p in by_id], "cover": [c] if c else []}
            for s, c in zip(kept, cover)]
    if len(subs) < 2:
        return None
    used = {p for s in subs for p in s["place_ids"]} | set(ranked)
    return {"kind": "tags", "level": level, "sig": split.get("sig", ""), **({"title": title} if title else {}),
            "axis": split["axis"], "total": split["total"], "other": split["total"] - split["covered"],
            "subtags": subs, "all": ranked, "all_cover": all_cover, "cards": [c for c in cards if c["id"] in used],
            **({"criteria": split["criteria"]} if split.get("criteria") is not None else {})}


def recent_signatures(transcript: list[dict]) -> list[str]:
    """`sig` of the tags blocks a chat showed, newest first (domain/tag_policy.repeated)."""
    return [t["block"]["sig"] for t in reversed(transcript)
            if t.get("kind") == "block" and (t.get("block") or {}).get("kind") == "tags" and t["block"].get("sig")]


def picked_tags(transcript: list[dict]) -> list[str]:
    """Tag refs the user opened in this chat (a tap on a tag card, kind "tag")."""
    return [t["ref"] for t in transcript if t.get("kind") == "tag" and t.get("ref")]


def services_block(result: dict) -> dict | None:
    rows = [{k: r[k] for k in SERVICE_KEYS if _known(r.get(k))} for r in result.get("rows") or ()]
    if not rows:
        return None
    return {"kind": "services", "rows": rows, "found": result.get("found") or len(rows),
            **({"anchor": result["anchor"]} if _known(result.get("anchor")) and not str(result["anchor"]).startswith("unknown") else {}),
            "sources": result.get("sources") or [], **({"crawled": result["crawled"]} if _known(result.get("crawled")) else {})}


def block_of(tools, name: str, args: dict, result, cards_of: Callable) -> dict | None:
    if not isinstance(result, dict) or "error" in result:
        return None
    if name == "find_services":
        return services_block(result)
    if name == "browse_tags":
        return tags_block(result, cards_of)
    if name == "find_dishes":
        return dish_block(tools, str(args.get("dish") or result.get("dish") or ""), list(result.get("ranked") or ()), cards_of)
    if name == "record_fact" and args.get("field") == "dish" and tools.knowledge is not None:
        dish = str(args.get("value") or "").strip()
        if not dish or not any(squash(w.dish) == squash(dish) for w in tools.state.wishes.dishes):
            return None  # the fact was refused or written another way
        found = tools.knowledge.more.dishes(dish, tools.state)
        return dish_block(tools, dish, list(found.get("ranked") or ()), cards_of)
    return None


def prepared_dish_block(tools, found: dict, cards_of: Callable) -> dict | None:
    """The reply answered a dish question from the prepared data, so no tool result made a block (QA 2026-10-30 B2):
    the dish the corpus lookups found in the message (agent.tools.lookups) is shown with its evidence all the same.
    None when a dish block is already out, the guard blocked the turn, or the dish has no place the trip allows."""
    dishes = (found or {}).get("dishes") or ()
    if not dishes or tools.cards_blocked or any(b.get("kind") == "dish" for b in getattr(tools, "blocks", ())):
        return None
    dish = str(dishes[0].get("dish") or "").strip()
    if not dish or tools.knowledge is None:
        return None
    ranked = list(tools.knowledge.more.dishes(dish, tools.state).get("ranked") or ())
    return dish_block(tools, dish, ranked, cards_of)


def watch(tools, emit: Callable, cards_of: Callable) -> None:
    """Send a `block` event for each read tool result that has one, right after its cards; blocks[] keeps them for the
    transcript. A turn the guard blocked sends none."""
    tools.blocks = []
    inner = tools.model_called

    def timed_cards(ids):
        started = time.monotonic()
        try:
            return cards_of(ids)
        finally:
            tools.timings.append(f"t_cards source=block count={len(ids)} seconds={time.monotonic() - started:.3f}")

    def called(name, result, args=None):
        started = time.monotonic()
        try:
            out = inner(name, result, args)
        finally:
            tools.timings.append(f"t_cards_hook name={name} seconds={time.monotonic() - started:.3f}")
        started = time.monotonic()
        try:
            if not tools.cards_blocked:
                try:
                    block = block_of(tools, name, args or {}, result, timed_cards)
                except Exception:  # noqa: BLE001 - a block is an extra: the reply must not fail for it
                    block = None
                if block:
                    tools.blocks.append(block)
                    emit("block", block)
            return out
        finally:
            tools.timings.append(f"t_block name={name} seconds={time.monotonic() - started:.3f}")

    tools.model_called = called
