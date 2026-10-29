"""gmaps menu_read: Gemma reads each Maps menu photo twice -> data/gmaps/places/<fid_dir>/menu_photo.json.

A dish is kept only when both reads (MENU_READ at temperature 0, MENU_READ_AGAIN at 0.4) write the same name after
folding case and accents; a price is kept only when both reads give the same price for it (`price_vnd` 0 = unknown).
A photo the model calls "not a menu" gives nothing. Results are cached per photo (sha256 + prompt hash), so a second
run reads only new photos. Offline writes Place Intelligence only; serving.dishes decides what is shown.
"""

import asyncio
import collections
import hashlib
import json
from pathlib import Path

from ...crawl.common.files import append_jsonl, data_dir, load_config, now, safe_name, write_json
from ...llm import MENU_READ, MENU_READ_AGAIN
from ...serving import dishes

FILE = "menu_photo.json"
MIN_NAME = 3  # characters of a folded dish name
PRICE_RANGE = (5_000, 5_000_000)  # a printed price outside this is a misread (đồng)


def prompt_hash() -> str:
    return hashlib.sha256((MENU_READ.prompt_hash + MENU_READ_AGAIN.prompt_hash + str(MENU_READ_AGAIN.temperature)).encode()).hexdigest()[:12]


def _price(item: dict) -> int:
    p = int(item.get("price_vnd") or 0)
    return p if PRICE_RANGE[0] <= p <= PRICE_RANGE[1] else 0


def agree(a: dict, b: dict) -> list[dict]:
    """Dishes both reads of one photo have: [{name, price_vnd}] (name as read first; price 0 unless both reads match)."""
    if not (a.get("is_menu") and b.get("is_menu")):
        return []
    second: dict[str, list[dict]] = collections.defaultdict(list)
    for it in b.get("items") or []:
        second[dishes.fold(it.get("name"))].append(it)
    out, seen = [], set()
    for it in a.get("items") or []:
        key = dishes.fold(it.get("name"))
        if len(key) < MIN_NAME or key in seen or key not in second:
            continue
        seen.add(key)
        price = _price(it)
        out.append({"name": it["name"].strip(), "price_vnd": price if price and any(_price(o) == price for o in second[key]) else 0})
    return out


def merge(per_photo: list[list[dict]]) -> list[dict]:
    """One dish list for a place from its photos' agreed dishes; a dish on several photos keeps a price any of them has."""
    by_key: dict[str, dict] = {}
    for items in per_photo:
        for it in items:
            key = dishes.fold(it["name"])
            if key not in by_key:
                by_key[key] = dict(it)
            elif not by_key[key]["price_vnd"]:
                by_key[key]["price_vnd"] = it["price_vnd"]
    return list(by_key.values())


async def read_photo(client, model: str, sem: asyncio.Semaphore, raw: bytes) -> dict:
    async def once(task):
        async with sem:
            return await task.ask(client, model, images=[raw])
    a, b = await asyncio.gather(once(MENU_READ), once(MENU_READ_AGAIN))
    return {"reads": [a, b], "agreed": agree(a, b)}


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


async def read_place(client, model: str, sem: asyncio.Semaphore, d: Path, status: collections.Counter) -> dict | None:
    menu = _json(d / "menu.json") or {}
    photos = menu.get("photos") or []
    old = _json(d / FILE) or {}
    cached = old.get("photos") or {} if old.get("prompt_hash") == prompt_hash() else {}
    out: dict[str, dict] = {}

    async def one(p: dict) -> None:
        f = d / p["file"]
        if not f.exists():
            return
        raw = f.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if (c := cached.get(p["photo_id"])) and c.get("sha256") == sha:
            out[p["photo_id"]] = c
            status["photo_cached"] += 1
            return
        try:
            res = await read_photo(client, model, sem, raw)
        except Exception as e:
            append_jsonl(d.parent.parent / "menu_read_errors.jsonl", {"at": now(), "place": d.name, "photo": p["photo_id"],
                                                                      "error": f"{type(e).__name__}: {e}"[:300]})
            status["photo_failed"] += 1
            return
        out[p["photo_id"]] = {"sha256": sha, **res}
        status["photo_read"] += 1

    await asyncio.gather(*(one(p) for p in photos))
    if not photos:
        return None
    return {"prompt_hash": prompt_hash(), "model": model, "built_at": now(), "photos": out,
            "dishes": merge([v["agreed"] for v in out.values()])}


async def run(city: str, limit: int | None = None, shard: tuple[int, int] | None = None, only_photo_only: bool = False,
              stop_file: str | None = None, reverse: bool = False, workers: int = 8, skip_done: bool = False, parallel: int | None = None) -> dict:
    """Places of data/gmaps/places that have menu photos. only_photo_only: just those whose Maps menu tab lists no dish."""
    load_config(city)
    gm = data_dir() / "gmaps"
    dirs = sorted(p.parent for p in (gm / "places").glob("*/menu.json"))
    todo = []
    for d in dirs:
        menu = _json(d / "menu.json") or {}
        if not menu.get("photos"):
            continue
        if only_photo_only and (menu.get("sections") or menu.get("highlights")):
            continue
        todo.append(d)
    todo = todo[shard[0]::shard[1]] if shard else todo
    if reverse:  # a second worker starts from the end, where the forward run arrives last
        todo = todo[::-1]
    if skip_done:  # places a worker already finished with the current prompts
        todo = [d for d in todo if (_json(d / FILE) or {}).get("prompt_hash") != prompt_hash()]
    todo = todo[:limit] if limit is not None else todo
    client, model = MENU_READ.role.client()
    client = client.with_options(timeout=240, max_retries=0)
    sem = asyncio.Semaphore(parallel or (MENU_READ.role.own_parallel() if not MENU_READ.role._on_uit() else MENU_READ.role.parallel()))
    status: collections.Counter = collections.Counter()
    gate = asyncio.Semaphore(workers)

    async def one(d: Path) -> None:
        async with gate:
            if stop_file and Path(stop_file).exists():  # checked when the place's turn comes, not when all are queued
                status["stopped"] += 1
                return
            res = await read_place(client, model, sem, d, status)
        if res is not None:
            write_json(d / FILE, res)
            status["places"] += 1
        if status["places"] and status["places"] % 25 == 0:
            print(f"gmaps menu_read {city}: {dict(status)} of {len(todo)}", flush=True)

    await asyncio.gather(*(one(d) for d in todo))
    summary = {"at": now(), "places": len(todo), "status": dict(status)}
    print(f"gmaps menu_read {city}: {json.dumps(summary, ensure_ascii=False)}")
    return summary
