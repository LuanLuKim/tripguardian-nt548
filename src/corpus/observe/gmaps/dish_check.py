"""gmaps dish_check: which dishes do reviews say an eatery serves -> data/gmaps/places/<fid_dir>/dish_review.json.

Input: the `detail.order` observations of gmaps reviews (data/gmaps/observations). A dish is kept only when
  1. its quote is an exact piece of the review text (whitespace and case folded),
  2. the quote contains the dish as whole words, and
  3. the Judge (DISH_REVIEW_CHECK) reads the review passage and says the reviewer was served that dish here.
Everything the Judge calls anything else stays out. Checks are cached per observation (prompt hash), so a re-run asks
only about new observations. Offline writes Place Intelligence; serving.dishes decides whether the source is shown.
"""

import asyncio
import collections
import json
from pathlib import Path

from ...crawl.common.files import append_jsonl, data_dir, load_config, now, write_json
from ...llm import DISH_REVIEW_CHECK
from ...review import evidence
from ...serving import dishes

FILE = "dish_review.json"
FEATURE = "detail.order"
MAX_PER_PLACE = 60  # observations checked per place (the most recent first)


def squash(text: str | None) -> str:
    return " ".join((text or "").casefold().split())


def quote_in(quote: str, passage: str) -> bool:
    """The quote is exact words of the review (the passage the Judge sees is a window of the same text)."""
    q = squash(quote)
    return len(q) >= 6 and q in squash(passage)


def names_dish(quote: str, dish: str) -> bool:
    d = dishes.fold(dish)
    return len(d) >= 3 and dishes.has_phrase(dishes.fold(quote), d)


def pre_check(o: dict, passage: str) -> str | None:
    """None when the observation may go to the Judge, else why not."""
    if not quote_in(o["span"]["quote"], passage):
        return "quote_not_in_review"
    if not names_dish(o["span"]["quote"], o["value"]):
        return "quote_lacks_dish"
    return None


def collect(checks: dict[str, dict]) -> list[dict]:
    """Dishes with at least one 'serves' check: {dish, n (distinct authors), quote (the shortest one), judge}."""
    by: dict[str, dict] = {}
    for c in checks.values():
        if c.get("verdict") != "serves":
            continue
        e = by.setdefault(dishes.fold(c["dish"]), {"dish": c["dish"], "authors": set(), "quote": c["quote"], "judge": "serves"})
        e["authors"].add(c.get("author"))
        if len(c["quote"]) < len(e["quote"]):
            e["quote"] = c["quote"]
    return sorted(({"dish": e["dish"], "n": len(e["authors"]), "quote": e["quote"], "judge": "serves"} for e in by.values()),
                  key=lambda x: (-x["n"], x["dish"]))


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def eatery(stem: str) -> bool:
    intel = _json(data_dir() / "intel" / "places" / f"{stem}.json") or {}
    return ((intel.get("estimates") or {}).get("category_group")) in (dishes.config().get("name_groups") or ())


async def check_place(client, model: str, sem: asyncio.Semaphore, stem: str, status: collections.Counter) -> dict | None:
    doc = _json(data_dir() / "gmaps" / "observations" / f"{stem}.json") or {}
    obs = [o for o in (doc.get("details") or []) if o["feature"] == FEATURE and o["source_type"] == "gmaps_review"]
    if not obs:
        return None
    obs = sorted(obs, key=lambda o: o.get("observed_at") or "", reverse=True)[:MAX_PER_PLACE]
    old = _json(data_dir() / "gmaps" / "places" / stem / FILE) or {}
    cached = old.get("checks") or {} if old.get("prompt_hash") == DISH_REVIEW_CHECK.prompt_hash else {}
    checks: dict[str, dict] = {}

    async def one(o: dict) -> None:
        if o["id"] in cached:
            checks[o["id"]] = cached[o["id"]]
            status["cached"] += 1
            return
        passage = evidence(stem, o, "gmaps")["text"]
        base = {"dish": o["value"], "quote": o["span"]["quote"], "author": o.get("author"), "review": o["source_id"]}
        why = pre_check(o, passage)
        if why:
            checks[o["id"]] = {**base, "verdict": why}
            status[why] += 1
            return
        try:
            async with sem:
                got = await DISH_REVIEW_CHECK.ask(client, model, name=doc.get("place_name") or "", dish=o["value"],
                                                  quote=o["span"]["quote"], passage=passage)
        except Exception as e:
            append_jsonl(data_dir() / "gmaps" / "dish_check_errors.jsonl",
                         {"at": now(), "place": stem, "obs": o["id"], "error": f"{type(e).__name__}: {e}"[:300]})
            status["failed"] += 1
            return
        checks[o["id"]] = {**base, "verdict": got["verdict"], "reason": got["reason"][:200]}
        status["judged"] += 1

    await asyncio.gather(*(one(o) for o in obs))
    return {"prompt_hash": DISH_REVIEW_CHECK.prompt_hash, "built_at": now(), "checks": checks, "dishes": collect(checks)}


async def run(city: str, limit: int | None = None, shard: tuple[int, int] | None = None, stop_file: str | None = None,
              workers: int = 12, parallel: int | None = None) -> dict:
    """Eatery places with order observations; Judge calls at the Judge role's parallel (UIT: 38)."""
    load_config(city)
    stems = sorted(p.stem for p in (data_dir() / "gmaps" / "observations").glob("*.json"))
    stems = [s for s in stems if (data_dir() / "gmaps" / "places" / s).is_dir() and eatery(s)]
    stems = stems[shard[0]::shard[1]] if shard else stems
    stems = stems[:limit] if limit is not None else stems
    client, model = DISH_REVIEW_CHECK.role.client()
    client = client.with_options(timeout=120, max_retries=0)
    sem = asyncio.Semaphore(parallel or DISH_REVIEW_CHECK.parallel)
    gate = asyncio.Semaphore(workers)
    status: collections.Counter = collections.Counter()

    async def one(stem: str) -> None:
        async with gate:
            if stop_file and Path(stop_file).exists():  # checked when the place's turn comes, not when all are queued
                status["stopped"] += 1
                return
            res = await check_place(client, model, sem, stem, status)
        if res is not None:
            write_json(data_dir() / "gmaps" / "places" / stem / FILE, res)
            status["places"] += 1
            if status["places"] % 50 == 0:
                print(f"gmaps dish_check {city}: {dict(status)} of {len(stems)}", flush=True)

    await asyncio.gather(*(one(s) for s in stems))
    summary = {"at": now(), "eateries": len(stems), "status": dict(status)}
    print(f"gmaps dish_check {city}: {json.dumps(summary, ensure_ascii=False)}")
    return summary
