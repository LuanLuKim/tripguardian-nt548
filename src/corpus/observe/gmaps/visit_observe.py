"""gmaps visit_observe: how long reviewers stay at a place -> data/gmaps/visit_observations/<fid_dir>.json.

The same `visit_duration` observation as observe/gmaps/extract.py makes (docs/CORPUS.md §4-5), found by a pass that
reads only the review snippets holding a duration, so the Extractor looks at nothing else. Code, not the model, reads
the minutes: the model says what a duration is about (VISIT_OBSERVE kind), then the quote must stand in the review
and hold exactly one duration (observe/visit_time.py). Kept: own_stay, advised_stay. Not kept: travel, waiting, other
places, the whole trip, clock times. Each observation carries `detail.minutes` [lo, hi] and the bucket value of the
ontology; aggregate/estimates.py turns one stay per author into short / typical / long.
A place is read again only for reviews it has not read with this prompt, gate and ontology.
"""

import asyncio
import collections
import hashlib
import json
import re
from pathlib import Path

from ...categories import defaults, group
from ...crawl.common.files import append_jsonl, data_dir, listed, now, safe_name, write_json
from ...llm import VISIT_OBSERVE, VISIT_VERIFY
from ...ontology import UNKNOWN, load as load_ontology
from .. import keep_stale, observation
from ..visit_time import bucket, parse_minutes, spans
from .details import day_type
from .extract import (BAD_ANSWER, Slots, _providers, bad_review_ids, call, first_line, listed_category, load_samples,
                      prune, text_key)
from .gate import norm
from .prep import batches, clean_text, is_junk, observed_at

GATE_VERSION = "visit_gate@v2"  # in the cache key: a changed gate reads the reviews again
FOLDER = "visit_observations"
KEEP = {"own_stay", "advised_stay"}
BEFORE, AFTER = 200, 140  # characters of the review shown around a duration
SNIPPET_CHARS = 900
BATCH = 12
# groups never read: lodging (nights, not a visit), car / bike rental
SKIP_GROUPS = {"stay", "rental"}


PASSAGE_CHARS = 1200  # review text shown to VISIT_VERIFY around the quote
# words next to a duration that say what people COULD do ("có thể chơi cả ngày", "ngồi cả ngày cũng được"), not how
# long the visit takes
CAPACITY = re.compile(r"cũng được|được luôn|không chán|k chán|ko chán|chẳng chán|hok chán|chưa hết|"
                      r"không biết chán|khó chán|hoàn hảo để", re.I)
NOT_ENOUGH = re.compile(r"không đủ|ko đủ|k đủ|chưa đủ|chẳng đủ|không kịp|ko kịp|chưa kịp|không hết|ko hết|chưa hết|"
                        r"chưa (?:\w+ )?xong|chưa (?:được|đến|tới|đầy)", re.I)  # "30 phút không đủ": a floor, not a stay
# a bare hour ("tầm 3h") with no word of a stay ("dành", "mất", "ở", "hết"...) is a clock time; "happy hour" translated
# to "giờ vui vẻ" is no duration; "thêm 30 phút nữa" is an extension of a session, not its length
WORD_UNIT = re.compile(r"tiếng|giờ|phút|\bph\b|\bp\b|['’]|ngày|buổi|rưỡi", re.I)
STAY_WORD = re.compile(r"dành|mất|ở lại|ở đây|ở đó|hết|chơi|đi |trong|suốt|kéo dài|tham quan|massage|ăn|ngồi|đủ|cần|nên|thời gian", re.I)
HAPPY_HOUR = re.compile(r"giờ vui vẻ|happy hour", re.I)
EXTENSION = re.compile(r"\bthêm\b|\bnữa\b|\bextra\b", re.I)
RULES_VERSION = "visit_rules@v4"  # cheap checks on the verified observations; a change re-applies them without the model
CAN = re.compile(r"có thể", re.I)  # "bạn có thể dành 2 tiếng" is advice; "có thể chơi cả ngày" (a day or more) is capacity
CAN_FROM_MIN = 180


def cache_key() -> str:
    cfg = json.dumps(defaults()["visit_time"], sort_keys=True)
    return hashlib.sha256("|".join((VISIT_OBSERVE.prompt_hash, VISIT_VERIFY.prompt_hash, GATE_VERSION, cfg, str(BEFORE),
                                    str(AFTER))).encode()).hexdigest()[:12]


def passage(text: str, quote: str) -> str:
    if len(text) <= PASSAGE_CHARS:
        return text
    at = max(0, norm(text).find(norm(quote)[:40]))
    start = max(0, at - PASSAGE_CHARS // 2)
    return text[start:start + PASSAGE_CHARS]


def near(text: str, quote: str) -> str:
    """The words right around the quote in the review: the clause that decides what the duration is about."""
    at = norm(text).find(norm(quote))
    return norm(text)[max(0, at - 45):at + len(norm(quote)) + 35] if at >= 0 else norm(quote)


def snippet(text: str) -> str | None:
    """The windows of the review around its durations, joined; None when it holds no duration."""
    found = spans(text)
    if not found:
        return None
    windows = []
    for start, end, _ in found:
        a, b = max(0, start - BEFORE), min(len(text), end + AFTER)
        if windows and a <= windows[-1][1]:
            windows[-1][1] = b
        else:
            windows.append([a, b])
    return " ... ".join(text[a:b] for a, b in windows)[:SNIPPET_CHARS]


def gate(item: dict, text: str, cfg: dict) -> tuple[dict | None, str | None]:
    """(observation fields, None) when the model's item stands, else (None, why not)."""
    if item.get("kind") not in KEEP:
        return None, f"kind_{item.get('kind')}"
    quote = str(item.get("quote") or "").strip()
    if not quote or norm(quote) not in norm(text):
        return None, "quote_not_in_review"
    span = parse_minutes(quote)
    if span is None:
        return None, "no_single_duration"
    if span[0] < cfg["min_minutes"] or span[1] > cfg["max_minutes"]:
        return None, "implausible"
    return {"quote": quote, "minutes": list(span), "value": bucket((span[0] + span[1]) / 2), "kind": item["kind"]}, None


def rule_drop(text: str, o: dict) -> str | None:
    """Why a verified observation is not kept (what people could do; a figure called too short), else None."""
    if parse_minutes(o["span"]["quote"]) != tuple(o["detail"]["minutes"]):
        return "reparse"  # the reader changed since this observation was made
    around = near(text, o["span"]["quote"])
    if CAPACITY.search(around) or (o["detail"]["minutes"][0] >= CAN_FROM_MIN and CAN.search(around)):
        return "capacity"
    if NOT_ENOUGH.search(around):
        return "not_enough"
    quote = o["span"]["quote"]
    if re.search(r"\d\s*h(?:\s*rưỡi)?", quote, re.I):
        at = norm(text).find(norm(quote))
        before = norm(text)[max(0, at - 35):at] if at >= 0 else ""
        after = norm(text)[at + len(norm(quote)):at + len(norm(quote)) + 20] if at >= 0 else ""
        if (re.search(r"\d\s*h(?:\s*\d{1,2}|\s*rưỡi)?\s+(?:mới|tới|đến|sáng|chiều|tối)", quote + after, re.I)
                or re.search(r"\b(?:đến|tới|lúc)\s*$", before, re.I)):
            return "clock_like"
        bare_half = re.fullmatch(r"\s*\d+\s*h\s*rưỡi\s*", quote, re.I)
        if not bare_half and not STAY_WORD.search(quote) and not re.search(r"(?:dành|mất|hết|ngồi|ở lại|trong|suốt)\s*(?:khoảng|tầm|chừng)?\s*$", before, re.I):
            return "clock_like"
    if not WORD_UNIT.search(quote) and not STAY_WORD.search(quote):
        return "clock_like"
    if HAPPY_HOUR.search(quote):
        return "happy_hour"
    if EXTENSION.search(quote):
        return "extension"
    return None


def apply_rules(verified: list[dict], texts: dict[str, str]) -> tuple[list[dict], collections.Counter]:
    kept, dropped = [], collections.Counter()
    for o in verified:
        why = rule_drop(texts.get(o["source_id"], ""), o)
        if why:
            dropped[why] += 1
        else:
            kept.append(o)
    return kept, dropped


async def read_batch(slots: Slots, city: str, place: dict, batch: list[tuple[str, str]]) -> list[dict]:
    """The model's items for a batch of (ref, snippet). A bad answer splits the batch; a single snippet is tried twice."""
    nums = {ref: i for i, (ref, _) in enumerate(batch, 1)}
    numbered = "\n".join(f"[{nums[ref]}] {' '.join(s.split())}" for ref, s in batch)
    for attempt in range(1 if len(batch) > 1 else 2):
        try:
            answer = await call(slots, lambda client, model: VISIT_OBSERVE.ask(
                client, model, city=city, name=place.get("name"), category=place.get("category") or "none",
                snippets=numbered))
            by_num = {v: k for k, v in nums.items()}
            return [{**i, "ref": by_num[i["ref"]]} for i in answer["items"] if i["ref"] in by_num]
        except BAD_ANSWER:
            continue
    if len(batch) == 1:
        raise ValueError("bad answer")
    mid = len(batch) // 2
    return await read_batch(slots, city, place, batch[:mid]) + await read_batch(slots, city, place, batch[mid:])


async def check(slots: Slots, place: dict, text: str, quote: str) -> str:
    try:
        answer = await call(slots, lambda client, model: VISIT_VERIFY.ask(
            client, model, name=place.get("name"), category=place.get("category") or "none", quote=quote,
            passage=passage(text, quote)))
    except BAD_ANSWER:
        return "error"
    return answer.get("verdict") if answer.get("verdict") in ("supports", "contradicts", "insufficient") else "error"


async def observe_place(slots: Slots, place_dir: Path, ont, city: str, bad_ids: set[str], category: str | None,
                        previous: dict | None) -> dict:
    cfg = defaults()["visit_time"]
    place = json.loads((place_dir / "place.json").read_text(encoding="utf-8"))
    if not place.get("category") and category:
        place["category"] = category
    reviews, samples = load_samples(place_dir)
    fid, fetched = place["fid"], place["fetched_at"]
    read, verified, dropped, texts = {}, [], collections.Counter(), {}
    todo = {}  # ref -> (review, cleaned text, snippet)
    seen = set()
    for r in reviews:
        text = clean_text(r.get("text"))
        key = (r.get("author_hash"), text)
        if r["review_id"] in bad_ids or is_junk(text) or key in seen:
            read[r["review_id"]] = ""  # looked at, nothing to read: not "new" next time
            continue
        seen.add(key)
        read[r["review_id"]] = text_key(text)
        texts[r["review_id"]] = text
        if previous and previous.get("read", {}).get(r["review_id"]) == read[r["review_id"]]:
            verified += [o for o in previous.get("verified", previous["observations"]) if o["source_id"] == r["review_id"]]
            continue
        s = snippet(text)
        if s is not None:
            todo[f"r{len(todo) + 1}"] = (r, text, s)
    if todo:
        parts = batches([(ref, {"text": s}) for ref, (_, _, s) in todo.items()], max_n=BATCH, max_chars=6000)
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(read_batch(slots, city, place, [(ref, r["text"]) for ref, r in part]))
                     for part in parts]
        kept = []
        for item in (i for t in tasks for i in t.result()):
            r, text, _ = todo[item["ref"]]
            fields, why = gate(item, text, cfg)
            if why:
                dropped[why] += 1
                continue
            kept.append((r, text, fields))
        async with asyncio.TaskGroup() as tg:  # a second read of each kept duration: one review, one claim
            checks = [tg.create_task(check(slots, place, text, f["quote"])) for _, text, f in kept]
        for (r, text, fields), verdict in zip(kept, (c.result() for c in checks)):
            if verdict != "supports":
                dropped[f"verify_{verdict}"] += 1
                continue
            seq = sum(1 for o in verified if o["source_id"] == r["review_id"])
            sample = samples.get(r["review_id"])
            verified.append(observation(
                id=f"gmaps_visit:{r['review_id']}:{seq}", place_fid=fid, feature="visit_duration", value=fields["value"],
                context={"time_of_day": UNKNOWN, "day_type": day_type(r), "weather": UNKNOWN},
                source_type="gmaps_review", source_id=r["review_id"], author=r.get("author_hash"),
                observed_at=observed_at(r.get("published_text"), fetched), quote=fields["quote"], field="text",
                extractor=f"visit_observe@{cache_key()}", ontology_version=ont.version, sample=sample,
                detail={"minutes": fields["minutes"], "kind": fields["kind"]}))
    dedup = sorted({(o["source_id"], o["span"]["quote"]): o for o in verified}.values(), key=lambda o: o["id"])
    obs, by_rule = apply_rules(dedup, texts)  # the model may return a quote twice
    return {"place_fid": fid, "place_name": place.get("name"), "as_of": fetched[:10],
            "observations": obs, "verified": dedup, "details": [], "proposed": [], "ratings": [],
            "place": {}, "place_facts": {}, "voices": 0, "read": read, "rules_version": RULES_VERSION,
            "stats": {"reviews": len(read), "asked": len(todo), "dropped": dict(dropped), "rules": dict(by_rule)}}


async def run(city: str, limit: int | None = None) -> dict:
    root = data_dir() / "gmaps"
    out = root / FOLDER
    ont = load_ontology()
    dirs = sorted(p.parent for p in (root / "places").glob("*/place.json"))
    items = listed(city)
    categories = {}
    if items is not None:
        keep = {safe_name(r["fid"]) for r in items}
        categories = {safe_name(r["fid"]): listed_category(r) for r in items}
        dirs = [d for d in dirs if d.name in keep]
        for stale in out.glob("*.json") if out.exists() else []:
            if stale.stem not in keep:
                stale.unlink()
    order = {g: i for i, g in enumerate(defaults()["visit_time"]["priority"])}

    def kind_of(d: Path) -> str:
        try:
            place = json.loads((d / "place.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "other"
        return group(place.get("category") or categories.get(d.name), place.get("name"))["id"]

    kinds = {d: kind_of(d) for d in dirs}
    dirs = [d for d in dirs if kinds[d] not in SKIP_GROUPS]
    dirs.sort(key=lambda d: (order.get(kinds[d], len(order)), d.name))
    if limit is not None:
        dirs = dirs[:limit]
    key = cache_key()
    todo, status = [], collections.Counter()
    for d in dirs:
        target = out / f"{d.name}.json"
        if target.exists():
            old = json.loads(target.read_text(encoding="utf-8"))
            bad_ids = bad_review_ids(root / "qc" / f"{d.name}.json")
            verified = old.get("verified", old["observations"])
            pruned = bool(bad_ids - set(old.get("qc_dropped") or []) or
                          any(o["source_id"] in bad_ids for o in old["observations"] + verified))
            if pruned:
                # QC overrides every cache shortcut, including keep_stale and later rule reapplication.
                old = {**prune(old, load_samples(d)[0], bad_ids),
                       "observations": [o for o in old["observations"] if o["source_id"] not in bad_ids],
                       "verified": [o for o in verified if o["source_id"] not in bad_ids],
                       "read": {rid: "" if rid in bad_ids else text for rid, text in old.get("read", {}).items()},
                       "built_at": now()}
                write_json(target, old)
            if old.get("prompt_hash") == key and old.get("ontology_version") == ont.version:
                fresh = {r["review_id"] for r in load_samples(d)[0]} - bad_ids - set(old.get("read", {}))
                if not fresh or keep_stale():
                    if old.get("rules_version") != RULES_VERSION:  # only the cheap checks changed: no model call
                        texts = {r["review_id"]: clean_text(r.get("text")) for r in load_samples(d)[0]}
                        verified = old.get("verified", old["observations"])
                        obs, by_rule = apply_rules(verified, texts)
                        write_json(target, {**old, "observations": obs, "verified": verified,
                                            "rules_version": RULES_VERSION, "built_at": now(),
                                            "stats": {**old["stats"], "rules": dict(by_rule)}})
                        status["rules"] += 1
                        continue
                    status["pruned" if pruned else "cached"] += 1
                    continue
        todo.append(d)
    if todo:
        providers = await _providers()
        if not providers:
            raise SystemExit("no LLM endpoint reachable")
        slots = Slots(providers)
        in_flight = asyncio.Semaphore(max(1, sum(p[2] for p in providers) // 3))
        print(f"visit_observe {city}: {len(todo)} places, endpoints {', '.join(f'{p[1]} x{p[2]}' for p in providers)}")

        async def one(d: Path) -> str:
            target = out / f"{d.name}.json"
            bad_ids = bad_review_ids(root / "qc" / f"{d.name}.json")
            previous = None
            if target.exists():
                old = json.loads(target.read_text(encoding="utf-8"))
                if old.get("prompt_hash") == key and old.get("ontology_version") == ont.version:
                    previous = old
            try:
                async with in_flight:
                    res = await observe_place(slots, d, ont, city, bad_ids, categories.get(d.name), previous)
            except Exception as e:
                if isinstance(e, ExceptionGroup):
                    e = e.exceptions[0]
                append_jsonl(root / "visit_observe_errors.jsonl", {"at": now(), "place": d.name, "error": first_line(e)})
                return "failed"
            write_json(target, {**res, "prompt_hash": key, "ontology_version": ont.version, "built_at": now(),
                                "qc_dropped": sorted(bad_ids)})
            return "done"

        status.update(await asyncio.gather(*(one(d) for d in todo)))
    files = [json.loads(p.read_text(encoding="utf-8")) for p in out.glob("*.json")] if out.exists() else []
    summary = {"at": now(), "places": len(dirs), "status": dict(status),
               "observations": sum(len(f["observations"]) for f in files),
               "places_with": sum(1 for f in files if f["observations"]),
               "dropped": dict(sum((collections.Counter(f["stats"]["dropped"]) for f in files), collections.Counter())),
               "rules": dict(sum((collections.Counter(f["stats"].get("rules", {})) for f in files), collections.Counter()))}
    if dirs:
        write_json(root / "visit_observe_summary.json", summary)
    print(f"visit_observe {city}: {json.dumps(summary, ensure_ascii=False)}")
    return summary
