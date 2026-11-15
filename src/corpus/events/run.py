"""`python -m corpus events --city <key>`: this month's and next month's events from the web -> data/<city>/events/
(docs/CORPUS.md §Sự kiện sắp tới). Searches SearXNG with dated queries, reads the best pages (a social post only as its
search snippet), asks the Extractor for each page's events, keeps what the code gate passes and merges the same event
across pages. Offline writes; online reads latest.json through corpus.pulse."""

import asyncio
import hashlib
import json
import os
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from ..crawl.common.files import ROOT, data_dir, load_config, now, write_json
from ..crawl.web import Web
from ..llm import EVENT_EXTRACT
from .gate import kept, merge, why_not


def events_dir(city: str, root: Path | None = None) -> Path:
    return (root or data_dir()) / city / "events"


def config() -> dict:
    return yaml.safe_load((ROOT / "config" / "web_events.yaml").read_text(encoding="utf-8"))


def queries(city_name: str, today: date, templates: list[str]) -> list[str]:
    nxt = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
    return [t.format(city=city_name, month=today.month, year=today.year, next_month=nxt.month, next_year=nxt.year)
            for t in templates]


def pages(web, qs: list[str], cfg: dict) -> list[dict]:
    """Every result of the queries once, best-ranked first: the first `pages` readable ones in full (text, og:image), the
    rest and every social post as title + snippet. A page that cannot be read falls back to its snippet."""
    hits, seen = [], set()
    for q in qs:
        try:
            found = web.search(q, k=cfg["results_per_query"], per_domain=2)
        except Exception as e:  # a blocked or failed query: the others still run
            print(f"events: search failed {q!r}: {type(e).__name__}", flush=True)
            continue
        for h in found:
            if h.url not in seen:
                seen.add(h.url)
                hits.append(h)
    out, read = [], 0
    for h in hits:
        snippet = {"url": h.url, "domain": h.domain, "title": h.title, "text": f"{h.title}\n{h.snippet}", "image": h.image,
                   "read": "snippet"}
        if read >= cfg["pages"] or any(h.domain == s or h.domain.endswith("." + s) for s in cfg["social"]):
            out.append(snippet)
            continue
        try:
            p = web.read(h.url, max_chars=cfg["page_chars"])
            out.append({"url": p.url, "domain": p.domain, "title": p.title or h.title, "text": p.text,
                        "image": p.image or h.image, "read": "page"})
            read += 1
        except Exception:  # paywall, timeout, not HTML
            out.append(snippet)
    return out


async def extract(todo: list[dict], cache: Path, city_name: str, today: date, ask) -> tuple[list[dict], Counter]:
    """[(page, item)] of every event the Extractor found; answers are cached by page text and prompt."""
    stats: Counter = Counter()
    sem = asyncio.Semaphore(EVENT_EXTRACT.parallel)

    async def one(page: dict) -> list[tuple[dict, dict]]:
        key = hashlib.sha256(json.dumps([page["url"], page["text"], EVENT_EXTRACT.prompt_hash, today.isoformat()],
                                        ensure_ascii=False).encode()).hexdigest()[:20]
        target = cache / f"{key}.json"
        if target.exists():
            items = json.loads(target.read_text(encoding="utf-8"))["events"]
            stats["cached"] += 1
        else:
            async with sem:
                try:
                    answer = await ask(city=city_name, today=today.isoformat(), year=today.year, title=page["title"],
                                       url=page["url"], text=page["text"])
                except Exception as e:  # one page must not stop the night: it is asked again tomorrow
                    print(f"events: extract failed {page['url']}: {type(e).__name__}", flush=True)
                    stats["failed"] += 1
                    return []
            items = answer.get("events") or []
            write_json(target, {"url": page["url"], "events": items})
            stats["asked"] += 1
        return [(page, it) for it in items]

    found = [x for xs in await asyncio.gather(*(one(p) for p in todo)) for x in xs]
    return found, stats


def write(city: str, snapshot: dict, keep: int, root: Path | None = None) -> Path:
    d = events_dir(city, root)
    d.mkdir(parents=True, exist_ok=True)
    name = snapshot["built_at"].replace("-", "").replace(":", "")[:15] + "Z.json"
    body = json.dumps(snapshot, ensure_ascii=False, indent=1).encode("utf-8")
    for target in (d / name, d / "latest.json"):
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, target)
    for old in sorted(d.glob("2*.json"))[:-keep]:
        old.unlink()
    return d / name


def run(city: str, today: date | None = None, web=None, ask=None) -> dict:
    today = today or date.today()
    cfg = config()
    city_name, qcfg = load_config(city)
    w = qcfg["web"]
    web = web or Web(w["base_url"], events_dir(city) / "cache", timeout_s=w["timeout_s"], ttl_days=1,
                     min_interval_s=w["min_interval_s"])
    if ask is None:
        client, model = EVENT_EXTRACT.role.client()
        client = client.with_options(timeout=120, max_retries=0)

        async def ask(**fields):
            return await EVENT_EXTRACT.ask(client, model, **fields)
    qs = queries(city_name, today, cfg["queries"])
    todo = pages(web, qs, cfg)
    found, stats = asyncio.run(extract(todo, events_dir(city) / "extracted", city_name, today, ask))
    passed, reasons = [], Counter()
    for page, item in found:
        if why := why_not(item, page["text"], today, cfg["horizon_days"], city_name):
            reasons[why] += 1
        else:
            passed.append(kept(item, page, today))
    events = merge(passed, tuple(cfg["social"]))
    snapshot = {"city": city, "day": today.isoformat(), "built_at": now(), "queries": qs,
                "pages": {"read": sum(p["read"] == "page" for p in todo), "snippets": sum(p["read"] == "snippet" for p in todo)},
                "extract": dict(stats), "found": len(found), "dropped": dict(reasons), "events": events}
    path = write(city, snapshot, cfg["keep_snapshots"])
    print(f"events {city}: {len(events)} events from {len(found)} found {dict(reasons)} {snapshot['pages']} -> {path}", flush=True)
    return snapshot


def load(city: str, root: Path | None = None) -> dict | None:
    """The newest events snapshot, or None when the job never ran."""
    try:
        return json.loads((events_dir(city, root) / "latest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
