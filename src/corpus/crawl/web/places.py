"""Phase `web places`: the ticket-price and opening-hours queries gsearch asks Google per place (corpus.crawl.gsearch
places, kinds fee and hours), asked through SearXNG instead, so no captcha and no signed-in window. The answers are
result snippets of Bing / Yahoo / Yandex, never Google's, so they are kept apart: data/web/<city>/place_snippets.jsonl,
one row per query {at, kind, query, key, n, engines, results: [{rank, url, title, snippet, engines}]}. search observe
reads them (corpus.observe.search) as the "web" basis, an estimate like any page that is not the place's own. The
knowledge panel (kind panel) has no SearXNG counterpart and stays gsearch's.

A query with a row is not asked again; a blocked one (no result, engines say why) is not written. Shards split the todo
list (`--shard i/n`)."""

import json
import time

import httpx

from .. import gsearch
from ..common.files import append_jsonl, data_dir, load_config, now

BASE_URL = "http://127.0.0.1:8888/search"
ENGINES = "bing,yahoo,yandex"  # duckduckgo is access-denied from here; probe 2026-10-30: 12/12 fee and hours queries answered
KINDS = ("fee", "hours")
PAUSE_S = 2.0
TIMEOUT_S = 30.0
BLOCK_WAIT_S = 300.0
STOP_AFTER_BLOCKED = 6  # waits in a row


def path(city: str):
    return data_dir() / "web" / city / "place_snippets.jsonl"


def load(city: str) -> dict[str, dict]:
    """query key (corpus.crawl.gsearch.key) -> its newest row."""
    out: dict[str, dict] = {}
    f = path(city)
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        try:
            row = json.loads(line)
            out[row["key"]] = row
        except (ValueError, KeyError):
            continue
    return out


def ask(client: httpx.Client, query: str) -> tuple[list[dict], bool]:
    """(results, blocked): blocked = no result and the engines say why."""
    r = client.get(BASE_URL, params={"q": query, "format": "json", "language": "vi", "engines": ENGINES}, timeout=TIMEOUT_S)
    r.raise_for_status()
    j = r.json()
    results = [{"rank": i, "url": x["url"], "title": x.get("title") or "", "snippet": x.get("content") or "",
                "engines": x.get("engines") or []} for i, x in enumerate(j.get("results") or [], 1) if x.get("url")]
    return results, not results and bool(j.get("unresponsive_engines"))


def run(city: str, limit: int | None = None, shard: tuple[int, int] | None = None, kinds: tuple[str, ...] = KINDS,
        pause: float = PAUSE_S, sleep=time.sleep) -> dict:
    done = load(city)
    todo = []
    for kind in kinds:
        todo += [(kind, q) for q in gsearch.places.queries(city, kind) if gsearch.key(q) not in done]
    if shard:
        todo = todo[shard[0]::shard[1]]
    todo = todo[:limit]
    stats = {"todo": len(todo), "asked": 0, "with_results": 0, "blocked": 0, "errors": 0}
    print(f"web places {city}: {len(todo)} queries to ask", flush=True)
    blocked_in_a_row = 0
    with httpx.Client() as client:
        for i, (kind, query) in enumerate(todo):
            try:
                results, blocked = ask(client, query)
            except Exception as e:
                stats["errors"] += 1
                print(f"web places: {type(e).__name__}: {str(e)[:120]}", flush=True)
                if stats["errors"] >= 5:
                    break
                sleep(pause * 5)
                continue
            if blocked:
                stats["blocked"] += 1
                blocked_in_a_row += 1
                if blocked_in_a_row >= STOP_AFTER_BLOCKED:
                    print("web places: engines blocked, stopping", flush=True)
                    break
                sleep(BLOCK_WAIT_S)
                continue
            blocked_in_a_row = 0
            stats["asked"] += 1
            stats["with_results"] += bool(results)
            append_jsonl(path(city), {"at": now(), "kind": kind, "query": query, "key": gsearch.key(query), "page": 1,
                                      "n": len(results), "source": "searxng", "results": results})
            if (i + 1) % 50 == 0:
                print(f"web places {city}: {json.dumps(stats)}", flush=True)
            sleep(pause)
    print(f"web places {city}: {json.dumps(stats)}", flush=True)
    return stats
