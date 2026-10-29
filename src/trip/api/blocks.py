"""Result blocks of the chat: what a read tool found, passed to the web as it is, so the screen shows more than the
reply's words. `dish` = places that serve a dish with the evidence (menu, name, review quote, menu price); `services` =
utilities / rental / tour / coach rows (never place cards). Both are data the tools already computed; nothing is
guessed here. A block with no rows is not sent (the reply says there is no data)."""

from __future__ import annotations

from typing import Callable

from corpus.serving import dishes as corpus_dishes

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

    def called(name, result, args=None):
        out = inner(name, result, args)
        if not tools.cards_blocked:
            try:
                block = block_of(tools, name, args or {}, result, cards_of)
            except Exception:  # noqa: BLE001 - a block is an extra: the reply must not fail for it
                block = None
            if block:
                tools.blocks.append(block)
                emit("block", block)
        return out

    tools.model_called = called
