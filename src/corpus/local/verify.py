"""Second look at the rows the gate passed and the grouping would keep (docs/CORPUS.md, Tri thức bản địa): the Extractor
reads each row's claim against its own quote in the page context (LOCAL_VERIFY) and says whether the quote, in its
passage, states the claim about that subject in the city. A row that fails is dropped by `group_claims(verdicts=...)`
before grouping, so the independent sources are counted again from the rows that passed. Verdicts are cached in
data/<city>/local/verified.jsonl by (row, prompt): re-running costs nothing for what was seen."""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Awaitable, Callable

from ..crawl.common.files import append_jsonl, now
from ..llm import LOCAL_VERIFY, LOCAL_VERIFY_CLAIM
from .gate import norm, rules
from .group import fold


def vkey(row: dict) -> str:
    """Cache key of one row's check: the claim it states, its document and quote, and the prompt (a new prompt re-asks)."""
    w = row["when"]
    raw = "|".join(map(str, (row["doc_id"], fold(row["quote"]), fold(row["text"]), fold(row["subject"]), row["kind"],
                             row["subject_kind"], w["months"], row.get("amount_min_vnd"), row.get("amount_max_vnd"),
                             w["days"], w["hours"], w["weather"], LOCAL_VERIFY.prompt_hash)))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def passage(chunk: str, quote: str, before: int, after: int) -> str:
    """The chunk around the quote, the quote between << and >>, as the model reads it."""
    i = chunk.find(quote)
    if i < 0:  # the gate matched after folding markdown and quote marks: find it the same way
        n = norm(chunk).find(norm(quote))
        i = max(0, n)
    start = max(0, i - before)
    return f"{'…' if start else ''}{chunk[start:i]}<<{quote}>>{chunk[i + len(quote): i + len(quote) + after]}…"


def load_cache(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["key"]] = r
    return out


def todo(rows: list[dict], cache: dict[str, dict]) -> list[dict]:
    """Checks still to ask, one per distinct row that is not in the cache (`rows` = group.candidate_rows)."""
    out, seen = [], set()
    for r in rows:
        k = vkey(r)
        if k not in cache and k not in seen:
            seen.add(k)
            out.append({"key": k, "row": r})
    return out


def _fields(city_name: str, item: dict) -> dict:
    r, v = item["row"], rules()["verify"]
    amount = "-" if not r.get("amount_min_vnd") else f"{r['amount_min_vnd']}-{r['amount_max_vnd']}"
    w = r["when"]
    return {"city": city_name, "title": r.get("title") or "-", "kind": r["kind"], "subject": r["subject"],
            "subject_kind": r["subject_kind"], "text": r["text"], "months": w["months"] or "-", "amount": amount,
            "days": w["days"] or "-", "hours": w["hours"] or "-", "weather": w["weather"] or "-",
            "passage": passage(r.get("chunk") or r["quote"], r["quote"], v.get("context_before", 900),
                               v.get("context_after", 200))}


async def verify(items: list[dict], *, city_name: str, ask: Callable[..., Awaitable[dict]],
                 model: str, out: Path, parallel: int | None = None) -> dict:
    """Ask LOCAL_VERIFY for each item and append the answers to `out`. A failed call writes nothing (asked again next
    run) and is counted."""
    sem = asyncio.Semaphore(parallel or rules()["verify"].get("parallel", 16))
    stats = {"asked": 0, "failed": 0, "ok": 0, "rejected": 0}

    async def one(item: dict) -> None:
        async with sem:
            try:
                a = await ask(**_fields(city_name, item))
            except Exception as e:  # one bad call must not stop the others
                append_jsonl(out.parent / "errors.jsonl", {"at": now(), "id": item["key"], "stage": "verify",
                                                           "error": f"{type(e).__name__}: {str(e)[:300]}"})
                stats["failed"] += 1
                return
        problem = str(a.get("problem") or "not_stated")
        append_jsonl(out, {"key": item["key"], "doc_id": item["row"]["doc_id"], "problem": problem,
                           "model": model, "at": now()})
        stats["asked"] += 1
        stats["ok" if problem == "none" else "rejected"] += 1

    await asyncio.gather(*(one(i) for i in items))
    return stats


def ckey(claim: dict) -> str:
    """Cache key of a grouped claim's check: the claim, the quotes it stands on and the prompt."""
    w = claim["when"]
    raw = "|".join(map(str, (claim["claim_id"], claim["kind"], fold(claim["text"]), w["months"],
                             claim.get("amount_min_vnd"), claim.get("amount_max_vnd"),
                             sorted((e["doc_id"], fold(e["quote"])) for e in claim["evidence"]),
                             LOCAL_VERIFY_CLAIM.prompt_hash)))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def claim_todo(claims: list[dict], cache: dict[str, dict]) -> list[dict]:
    """Grouped claims that would be kept and have no verdict yet."""
    return [{"key": ckey(c), "claim": c} for c in claims if c["status"] == "kept" and ckey(c) not in cache]


def _claim_fields(city_name: str, item: dict, chunks: dict[tuple[str, str], str]) -> dict:
    c, v = item["claim"], rules()["verify"]
    amount = "-" if not c["amount_min_vnd"] else f"{c['amount_min_vnd']}-{c['amount_max_vnd']}"
    quotes = []
    for n, e in enumerate(c["evidence"][: v.get("claim_quotes", 4)], 1):
        chunk = chunks.get((e["doc_id"], fold(e["quote"]))) or e["quote"]
        quotes.append(f"[{n}] ({e['domain']}) " + passage(chunk, e["quote"], v.get("claim_context", 250), 60))
    return {"city": city_name, "kind": c["kind"], "subject": c["subject"], "subject_kind": c["subject_kind"],
            "text": c["text"], "months": c["when"]["months"] or "-", "amount": amount, "quotes": "\n".join(quotes)}


async def verify_claims(items: list[dict], *, city_name: str, chunks: dict, ask: Callable[..., Awaitable[dict]],
                        model: str, out: Path, parallel: int | None = None) -> dict:
    """Ask LOCAL_VERIFY_CLAIM for each grouped claim and append the answers to `out` (verified_claims.jsonl)."""
    sem = asyncio.Semaphore(parallel or rules()["verify"].get("parallel", 16))
    stats = {"asked": 0, "failed": 0, "ok": 0, "rejected": 0}

    async def one(item: dict) -> None:
        async with sem:
            try:
                a = await ask(**_claim_fields(city_name, item, chunks))
            except Exception as e:
                append_jsonl(out.parent / "errors.jsonl", {"at": now(), "id": item["key"], "stage": "verify_claim",
                                                           "error": f"{type(e).__name__}: {str(e)[:300]}"})
                stats["failed"] += 1
                return
        problem = str(a.get("problem") or "not_stated")
        append_jsonl(out, {"key": item["key"], "claim_id": item["claim"]["claim_id"], "problem": problem,
                           "model": model, "at": now()})
        stats["asked"] += 1
        stats["ok" if problem == "none" else "rejected"] += 1

    await asyncio.gather(*(one(i) for i in items))
    return stats
