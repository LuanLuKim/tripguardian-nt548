"""Place phase, place_web: a web search per place that has no verified clip -> TikTok video URLs naming that place.

TikTok's own search always shows a captcha, so the videos are looked for on the web instead: SearXNG answers
`site:tiktok.com <place name> <city>` (the self-hosted instance of docs/CORPUS.md §Nguồn, plain HTTP, no key, read as
a URL service: this module does not import corpus.crawl.web). A result is kept only when it is a TikTok video and its
title names the place (every distinctive word of the name, accents and case dropped; a name with one distinctive word
needs that word, 4+ letters), at most PER_PLACE videos a place. Kept rows go to data/tiktok/place_web/<city>.jsonl:
{at, fid, name, query, video_id, url, title}; web_videos reads it next to data/web/<city>/tiktok_urls.jsonl and
adds the searched place as a candidate for the video, so place_verify judges it (only a "yes" is evidence).
Every place asked is written to place_web_tried.jsonl: {at, fid, name, query, results, tiktok, kept, blocked}, so a
place with nothing is not asked again (a blocked or failed query is not written and is asked again).
A run waits BLOCK_WAIT_S when every engine is suspended and stops after STOP_AFTER_BLOCKED waits in a row or STOP_AFTER failed requests. Places without a clip are asked in this order:
everything but lodging first, then lodging; `--limit N` caps the places asked per run.

Backend gsearch (`--backend gsearch`): the same query asked of Google through the signed-in browser (corpus.crawl.gsearch,
its public API only), `site:tiktok.com "<name>" <city>`; a result is kept by the same rule, matched against its Google
title plus snippet (that text is stored as `title`), rows go to the same two files (+ `engine: google-browser`). Google
does not report a block: a query whose page could not be read (window closed, captcha nobody solved) is not written and
stops the process; a page with no result is written as tried only after a later query of the run did return results
(an all-empty run is a sign the window is blocked, not that no place has a video). One process per signed-in window:
`--attach url1,url2,...` starts one child per DevTools URL (CORPUS_ATTACH_URL, CORPUS_DEBUG_PORT set), each with
`--shard i/n` (its i-th share of the todo list), so windows never ask the same place; a captcha waits for a person
there (gsearch prints the DevTools port). `data/tiktok/place_web/STOP` ends a run after the chunk in progress.
"""

import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import unicodedata
from urllib.parse import urlsplit

import httpx

from .. import gsearch
from ..common.files import append_jsonl, data_dir, listed, load_config, log_error, now
from ..common.files import slug as fold_slug
from .place_verify import evidence_pairs
from .frames import saved
from .poi_crawl import GENERIC

BASE_URL = "http://127.0.0.1:8888/search"
ENGINES = "yahoo,yandex"  # the only ones that return TikTok video links for `site:tiktok.com` (25 places, 2026-10-30: yahoo 84 video
# results / 36 named, yandex 80 / 11, bing 0; duckduckgo is access-denied). Fewer engines = faster answers, less load on each.
PER_PLACE = 3
MIN_PAUSE_S = 1.5  # searxng backend: the pace never goes below this (an answer takes ~1 s, so ~25 queries/min per process)
MAX_PAUSE_S = 60.0
RAMP_AFTER = 20  # clean queries in a row before the pause shrinks one step
RAMP_DOWN = 0.8  # each step: pause x this
BACK_OFF = 2.0  # an engine that starts refusing: pause x this
INTERVAL_S = 10.0  # between two real queries: the engines behind SearXNG are shared (the web phase, gsearch) and suspend at ~60
BLOCK_WAIT_S = 600.0  # all engines suspended: wait, then ask the same place again
TIMEOUT_S = 30.0
STOP_AFTER = 5  # failed requests in a row
STOP_AFTER_BLOCKED = 6  # waits of BLOCK_WAIT_S in a row
CHUNK = 20  # gsearch backend: queries per browser session (the STOP file is looked at between two chunks)
PAUSE_S = 10.0  # gsearch backend: seconds between two result pages of a window (a random 1x-1.8x of it); 6 s drew a
# captcha every ~20-40 pages per window with 3 windows on one IP (2026-10-30)
REST_S = (90.0, 180.0)  # gsearch backend: a random rest after each chunk, so a window never asks Google without a break
STAGGER_S = 45.0  # gsearch backend: window i starts i x this later, so the windows' bursts do not line up
FORBIDDEN_WAIT_S = (600.0, 900.0)  # gsearch backend: unread pages (Google's 403 lasts minutes): rest, then ask them again
FORBIDDEN_TRIES = 3  # rests per chunk before the window stops
STOP_AFTER_EMPTY = 20  # gsearch backend: result pages with no result in a row = the window is blocked, not "no video"
QUOTED_WORDS = 6  # a longer name is quoted by its first words only
GOOGLE = "google-browser"
VIDEO = re.compile(r"^/@([^/]+)/video/(\d+)")
# words that any place of a kind can have: they do not tell this place from the next
STOP = GENERIC | {"khach", "san", "resort", "villa", "apartment", "can", "ho", "nha", "nghi", "phong", "bar", "pub",
                  "tiem", "banh", "com", "bun", "pho", "lau", "nuong", "cua", "hang", "dich", "vu", "spa", "massage",
                  "tour", "cho", "thue", "xe", "may", "dalat", "vietnam", "dl", "boutique", "luxury", "inn", "hostel",
                  "motel", "dorm", "stay", "house", "home", "the", "of", "at", "in", "by", "ten", "so"}


def words(text: str) -> list[str]:
    return [w for w in fold_slug(text or "").split("-") if w]


def distinctive(name: str) -> list[str]:
    return [w for w in dict.fromkeys(words(name)) if w not in STOP and (len(w) > 1 or w.isdigit())]


def clean_name(name: str) -> str:
    """The name a person would type: no bracket notes, no tagline after a bar / dash."""
    name = re.sub(r"[\(\[].*?[\)\]]", " ", name or "")
    name = re.split(r"\s[|\-–—]\s|\s[|]\s?|[|]", name)[0]
    return " ".join(name.split())


def names_place(title: str, name: str) -> bool:
    """The title carries every distinctive word of the name (one-word names: that word, 4+ letters)."""
    keys = distinctive(name)
    if not keys or (len(keys) == 1 and len(keys[0]) < 4):
        return False
    have = set(words(title))
    return all(k in have for k in keys)


def out_path(city: str):
    return data_dir() / "tiktok" / "place_web" / f"{city}.jsonl"


def tried_path(city: str):
    return data_dir() / "tiktok" / "place_web" / f"{city}_tried.jsonl"


def read(path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def load(city: str) -> list[dict]:
    return read(out_path(city))


def search(client: httpx.Client, query: str) -> tuple[list[dict], bool, bool]:
    """(results, blocked, refused): blocked = no result and the engines say why; refused = an engine began refusing on
    this query ("Suspended: ..." is one SearXNG already holds off, not ours to slow down for)."""
    r = client.get(BASE_URL, params={"q": query, "format": "json", "language": "vi", "engines": ENGINES}, timeout=TIMEOUT_S)
    r.raise_for_status()
    j = r.json()
    results = j.get("results") or []
    down = j.get("unresponsive_engines") or []
    return results, not results and bool(down), any(not str(why).startswith("Suspended") for _, why in down)


class Pace:
    """Seconds between two queries of one process: shrinks after a clean run, doubles when an engine starts refusing,
    so the crawl goes as fast as the engines allow and backs off before they suspend."""

    def __init__(self, pause: float, floor: float = MIN_PAUSE_S):
        self.pause, self.floor, self.clean = max(pause, floor), floor, 0

    def ok(self) -> None:
        self.clean += 1
        if self.clean >= RAMP_AFTER:
            self.pause, self.clean = max(self.floor, self.pause * RAMP_DOWN), 0

    def refused(self) -> None:
        self.pause, self.clean = min(MAX_PAUSE_S, self.pause * BACK_OFF), 0


def videos_of(results: list[dict], name: str) -> tuple[int, list[dict]]:
    """(TikTok video results, those whose title names the place), in the engines' order, one per video."""
    seen, found, kept = set(), 0, []
    for r in results:
        parts = urlsplit(r.get("url") or "")
        host = (parts.hostname or "").lower()
        m = VIDEO.match(parts.path) if host == "tiktok.com" or host.endswith(".tiktok.com") else None
        if not m or m.group(2) in seen:
            continue
        seen.add(m.group(2))
        found += 1
        title = unicodedata.normalize("NFC", r.get("title") or "")
        if names_place(title, name):
            kept.append({"video_id": m.group(2), "url": f"https://www.tiktok.com/@{m.group(1)}/video/{m.group(2)}",
                         "title": title})
    return found, kept[:PER_PLACE]


def targets(city: str) -> list[dict]:
    """Listed places with no verified clip and no earlier query, non-lodging first."""
    stay: set[str] = set()
    f = data_dir() / "gmaps" / "list" / f"{city}_stay.json"
    if f.exists():
        stay = {r["fid"] for r in json.loads(f.read_text(encoding="utf-8"))["items"]}
    has = {fid for video_id, fid in evidence_pairs() if saved(data_dir() / "tiktok" / "videos" / video_id)}
    asked = {r["fid"] for r in read(tried_path(city))}
    rows = [r for r in listed(city) or [] if r.get("fid") and r.get("name") and r["fid"] not in has
            and r["fid"] not in asked and distinctive(r["name"])]
    return sorted(rows, key=lambda r: (r["fid"] in stay, -(r.get("reviews") or 0)))


def run(city: str, limit: int | None = None, sleep=time.sleep, backend: str = "searxng",
        shard: tuple[int, int] | None = None, attach: list[str] | None = None, pause: float = PAUSE_S) -> dict:
    if backend == "gsearch":
        if attach:
            return run_windows(city, attach, limit, pause)
        return run_gsearch(city, limit, shard, pause)
    if backend != "searxng":
        raise ValueError(f"place_web backend {backend!r}: searxng | gsearch")
    name, _ = load_config(city)
    root = data_dir() / "tiktok"
    todo = shard_of(targets(city), shard)
    stats = {"todo": len(todo), "asked": 0, "with_video": 0, "kept": 0, "blocked": 0, "errors": 0}
    print(f"place_web {city}: {len(todo)} places without a clip left" + (f", asking {limit}" if limit else ""),
          flush=True)
    seen = {(r["video_id"], r["fid"]) for r in load(city)}
    failures = 0
    pace = Pace(pause)
    with httpx.Client() as client:
        for i, p in enumerate(todo[:limit] if limit else todo):
            clean = clean_name(p["name"])
            query = f"site:tiktok.com {clean}" + ("" if fold_slug(name) in fold_slug(clean) else f" {name}")
            try:
                results, blocked, refused = search(client, query)
            except Exception as e:
                stats["errors"] += 1
                failures += 1
                log_error(root, p["fid"], "place_web", e)
                if failures >= STOP_AFTER:
                    break
                sleep(INTERVAL_S * 3)
                continue
            pace.refused() if refused else pace.ok()
            if blocked:
                stats["blocked"] += 1
                failures += 1
                if failures >= STOP_AFTER_BLOCKED:
                    print("place_web: engines blocked, stopping", flush=True)
                    break
                sleep(BLOCK_WAIT_S)
                continue
            failures = 0
            found, kept = videos_of(results, p["name"])
            stats["asked"] += 1
            stats["with_video"] += bool(found)
            for v in kept:
                if (v["video_id"], p["fid"]) in seen:
                    continue
                seen.add((v["video_id"], p["fid"]))
                stats["kept"] += 1
                append_jsonl(out_path(city), {"at": now(), "fid": p["fid"], "name": p["name"], "query": query, **v})
            append_jsonl(tried_path(city), {"at": now(), "fid": p["fid"], "name": p["name"], "query": query,
                                            "results": len(results), "tiktok": found, "kept": len(kept)})
            if (i + 1) % 50 == 0:
                print(f"place_web {city}: {json.dumps(stats)} pause {pace.pause:.1f}s", flush=True)
            sleep(pace.pause)
    print(f"place_web {city}: {json.dumps(stats)}", flush=True)
    return stats


def gsearch_query(name: str, city_name: str) -> str:
    """`site:tiktok.com "<name a person would type>" <city>`; the city is left out when the name already has it."""
    clean = " ".join(clean_name(name).replace('"', " ").split()[:QUOTED_WORDS])
    return f'site:tiktok.com "{clean}"' + ("" if fold_slug(city_name) in fold_slug(clean) else f" {city_name}")


def shard_of(rows: list, shard: tuple[int, int] | None) -> list:
    """The i-th of n interleaved shares (most reviewed places are spread over the shards)."""
    return rows if not shard else rows[shard[0]::shard[1]]


def stop_file(city: str):
    return out_path(city).parent / "STOP"


def run_gsearch(city: str, limit: int | None = None, shard: tuple[int, int] | None = None, pause: float = PAUSE_S,
                chunk: int = CHUNK, rest: tuple[float, float] = REST_S, sleep=time.sleep,
                forbidden_wait: tuple[float, float] = FORBIDDEN_WAIT_S) -> dict:
    """The gsearch backend, one process = one browser window (CORPUS_ATTACH_URL), see the module docstring."""
    name, _ = load_config(city)
    todo = shard_of(targets(city), shard)
    todo = todo[:limit] if limit else todo
    stats = {"todo": len(todo), "asked": 0, "with_video": 0, "kept": 0, "blocked": 0}
    tag = f" shard {shard[0]}/{shard[1]}" if shard else ""
    print(f"place_web gsearch {city}{tag}: {len(todo)} places to ask", flush=True)
    seen = {(r["video_id"], r["fid"]) for r in load(city)}
    pending: list[dict] = []  # tried rows of pages with no result, written once a later page proves the window reads results
    proven = False

    def flush() -> None:
        for row in pending:
            append_jsonl(tried_path(city), row)
        pending.clear()

    if shard and shard[0]:
        sleep(shard[0] * STAGGER_S)
    for i in range(0, len(todo), chunk):
        if i:
            sleep(random.uniform(*rest))
        if stop_file(city).exists():
            print(f"place_web gsearch: {stop_file(city)} exists, stopping", flush=True)
            break
        part = todo[i:i + chunk]
        queries = [gsearch_query(p["name"], name) for p in part]
        for attempt in range(FORBIDDEN_TRIES + 1):  # pages read on an earlier try come from the gsearch cache
            pages = gsearch.search_pages(queries, city, 1, False, pause_s=(pause, pause * 1.8))
            if attempt == FORBIDDEN_TRIES or not any(page.blocked for page in pages) or stop_file(city).exists():
                break
            wait = random.uniform(*forbidden_wait)
            print(f"place_web gsearch{tag}: unread pages, resting {wait:.0f} s before asking again", flush=True)
            sleep(wait)
        unread = 0
        for p, query, page in zip(part, queries, pages):
            if page.blocked:
                unread += 1
                continue
            results = [{"url": r.url, "title": f"{r.title} {r.snippet}".strip()} for r in page.results]
            found, kept = videos_of(results, p["name"])
            stats["asked"] += 1
            stats["with_video"] += bool(found)
            for v in kept:
                if (v["video_id"], p["fid"]) in seen:
                    continue
                seen.add((v["video_id"], p["fid"]))
                stats["kept"] += 1
                append_jsonl(out_path(city), {"at": now(), "fid": p["fid"], "name": p["name"], "query": query,
                                              "engine": GOOGLE, **v})
            row = {"at": now(), "fid": p["fid"], "name": p["name"], "query": query, "engine": GOOGLE,
                   "results": len(results), "tiktok": found, "kept": len(kept)}
            if results:
                proven = True
                flush()
                append_jsonl(tried_path(city), row)
            else:
                pending.append(row)
        stats["blocked"] += unread
        print(f"place_web gsearch {city}{tag}: {i + len(part)}/{len(todo)} {json.dumps(stats)}", flush=True)
        if unread:
            print("place_web gsearch: a page could not be read (captcha unsolved or the window closed), "
                  "stopping this window; run again to go on", flush=True)
            break
        if len(pending) >= STOP_AFTER_EMPTY:
            print(f"place_web gsearch: {len(pending)} pages in a row with no result, the window looks blocked; "
                  "stopping (those places are asked again next run)", flush=True)
            pending.clear()
            break
    if proven:
        flush()
    return stats


def run_windows(city: str, urls: list[str], limit: int | None = None, pause: float = PAUSE_S,
                popen=subprocess.Popen, emit=print) -> dict[str, int]:
    """One child process per DevTools URL: `python -m corpus tiktok place_web --backend gsearch --shard i/n`, attached
    to that window. Output lines are prefixed with the window's port. -> {url: exit code}."""
    n = len(urls)
    kids = []
    for i, url in enumerate(urls):
        port = urlsplit(url).port
        cmd = [sys.executable, "-u", "-m", "corpus", "tiktok", "place_web", "--backend", "gsearch", "--city", city,
               "--shard", f"{i}/{n}", "--pause", str(pause)] + (["--limit", str(-(-limit // n))] if limit else [])
        env = {**os.environ, "CORPUS_ATTACH_URL": url, "CORPUS_DEBUG_PORT": str(port), "CORPUS_PROFILE_STATE": "1",
               "PYTHONIOENCODING": "utf-8"}
        proc = popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True, encoding="utf-8")
        t = threading.Thread(target=lambda p=proc, port=port: [emit(f"[{port}] {line.rstrip()}") for line in p.stdout],
                             daemon=True)
        t.start()
        kids.append((url, proc, t))
    codes = {}
    try:
        for url, proc, t in kids:
            codes[url] = proc.wait()
            t.join()
    finally:  # a Ctrl-C ends the windows' children too
        for url, proc, t in kids:
            if proc.poll() is None:
                proc.terminate()
    return codes
