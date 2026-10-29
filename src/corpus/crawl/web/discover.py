"""Phase `web search`: each planned query once through SearXNG -> TikTok video URLs, TikTok discover slugs (real
search phrases) and document URLs under data/web/<city>/. Stops cleanly on the day's budget or when the engines keep
blocking; a query is done once its search/<hash>.json exists, so a rerun picks up where the last one stopped."""

import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from ..common.files import append_jsonl, data_dir, load_config, log_error, now, slug, write_json
from .client import BudgetExhausted, Web, WebError
from .links import classify, doc_id, slug_relevant
from .queries import Query, plan, query_hash
from .scoring import hot_groups, yield_row

_VIDEO_ID = re.compile(r'"video_id"\s*:\s*"(\d+)"')


def known_video_ids() -> set[str]:
    """Video ids the tiktok source already has (read as files only: video folders and every "video_id" in its search
    results), so a URL found on the web counts as new only when TikTok's own crawl has not seen it."""
    root = data_dir() / "tiktok"
    ids = {p.name for p in (root / "videos").glob("*") if p.is_dir()} if (root / "videos").exists() else set()
    for pattern in ("place_search/*/*.json", "poi_crawl/*.json", "search/*/*.jsonl"):
        for path in root.glob(pattern):
            try:
                ids.update(_VIDEO_ID.findall(path.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return ids


def _keys(path: Path, key: str) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.add(str(json.loads(line)[key]))
        except (ValueError, KeyError, TypeError):
            continue
    return out


def _domain(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def run(city: str, limit: int | None = None, queries: list[Query] | None = None, web: Web | None = None) -> dict:
    started = time.monotonic()
    name, cfg = load_config(city)
    cfg_web = cfg["web"]
    root = data_dir()
    web_root = root / "web" / city
    web = web or Web.from_config(cfg_web, root / "web", city=city)
    if queries is None:
        queries = plan(city, name, cfg_web, root, hot_groups(web_root / "query_yield.jsonl"))
    seen_videos = _keys(web_root / "tiktok_urls.jsonl", "video_id")
    seen_slugs = _keys(web_root / "discover_slugs.jsonl", "slug")
    seen_docs = _keys(web_root / "doc_urls.jsonl", "doc_id")
    known = known_video_ids()
    stop_after = int(cfg_web.get("stop_after_blocked", 3))
    stats = {"planned": len(queries), "resumed": 0, "network": 0, "cached": 0, "results": 0, "videos_total": 0,
             "videos_new": 0, "videos_known": 0, "slugs_new": 0, "docs_new": 0, "dropped": {}, "blocked_engines": {},
             "stop_reason": None, "per_query": []}
    failures = 0
    for q in queries:
        h = query_hash(q.text)
        search_file = web_root / "search" / f"{h}.json"
        if search_file.exists():
            stats["resumed"] += 1
            continue
        if limit is not None and stats["network"] >= limit:
            stats["stop_reason"] = "limit"
            break
        try:
            page = web.search_page(q.text)
        except BudgetExhausted:
            stats["stop_reason"] = "budget"
            break
        except WebError as err:
            stats["network"] += 1
            log_error(web_root, h, "search", err)
            row = yield_row(q, h, results=0, videos_total=0, videos_new=0, docs_new=0, slugs_new=0, blocked=[],
                            cached=False)
            append_jsonl(web_root / "query_yield.jsonl", row)
            stats["per_query"].append(row)
            print(f"web search: {q.text!r} failed: {err}")
            failures += 1
            if failures >= stop_after:
                stats["stop_reason"] = "engines_blocked"
                break
            continue
        stats["cached" if page.cached else "network"] += 1
        blocked = [engine for engine, _ in page.unresponsive]
        if not page.cached:
            for engine in blocked:
                stats["blocked_engines"][engine] = stats["blocked_engines"].get(engine, 0) + 1
        if page.blocked:
            log_error(web_root, h, "search", WebError("engines blocked: " + ", ".join(
                f"{engine} ({reason})" for engine, reason in page.unresponsive)))
            row = yield_row(q, h, results=0, videos_total=0, videos_new=0, docs_new=0, slugs_new=0, blocked=blocked,
                            cached=page.cached)
            append_jsonl(web_root / "query_yield.jsonl", row)
            stats["per_query"].append(row)
            print(f"web search: {q.text!r} blocked by {', '.join(blocked)}")
            failures += 1
            if failures >= stop_after:
                stats["stop_reason"] = "engines_blocked"
                break
            continue
        failures = 0
        found_at = now()
        counts = {"videos_total": 0, "videos_new": 0, "slugs_new": 0, "docs_new": 0}
        saved = []
        for result in page.results:
            link = classify(result.url)
            reason = link.reason
            if link.kind == "video":
                counts["videos_total"] += 1
                if link.video_id in known:
                    stats["videos_known"] += 1
                elif link.video_id not in seen_videos:
                    seen_videos.add(link.video_id)
                    counts["videos_new"] += 1
                    append_jsonl(web_root / "tiktok_urls.jsonl", {
                        "url": link.url, "video_id": link.video_id, "author": link.author, "title": result.title,
                        "query": q.text, "found_at": found_at})
            elif link.kind == "discover":
                if not slug_relevant(link.text, name):
                    reason = "slug_offtopic"
                else:
                    key = slug(link.text)
                    if key and key not in seen_slugs:
                        seen_slugs.add(key)
                        counts["slugs_new"] += 1
                        append_jsonl(web_root / "discover_slugs.jsonl", {
                            "slug": key, "text": link.text, "query": q.text, "url": result.url, "found_at": found_at})
            elif link.kind == "doc":
                did = doc_id(link.url)
                if did not in seen_docs:
                    seen_docs.add(did)
                    counts["docs_new"] += 1
                    append_jsonl(web_root / "doc_urls.jsonl", {
                        "url": link.url, "doc_id": did, "domain": _domain(link.url), "title": result.title,
                        "snippet": result.snippet, "query": q.text, "found_at": found_at})
            if reason:
                stats["dropped"][reason] = stats["dropped"].get(reason, 0) + 1
            saved.append({"url": result.url, "title": result.title, "snippet": result.snippet,
                          "engines": list(result.engines), "kind": "drop" if reason else link.kind, "reason": reason})
        write_json(search_file, {"query": q.text, "hash": h, "group": q.group, "source": q.source,
                                 "searched_at": found_at, "cached": page.cached, "results": saved,
                                 "unresponsive": [list(u) for u in page.unresponsive]})
        row = yield_row(q, h, results=len(page.results), blocked=blocked, cached=page.cached, **counts)
        append_jsonl(web_root / "query_yield.jsonl", row)
        stats["per_query"].append(row)
        stats["results"] += len(page.results)
        for key, value in counts.items():
            stats[key] += value
        print(f"web search: {q.text!r} {len(page.results)} results, new: {counts['videos_new']} videos, "
              f"{counts['slugs_new']} slugs, {counts['docs_new']} docs{' (cached)' if page.cached else ''}")
    stats["seconds"] = round(time.monotonic() - started, 1)
    summary = {k: v for k, v in stats.items() if k != "per_query"}
    print(f"web search {city}: {summary}")
    return stats
