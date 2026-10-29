"""Phase `local extract`: each web Document is cut into chunks of whole sections and read once by the Extractor
(LOCAL_CLAIM). The raw answers are cached in data/<city>/local/extracted/<doc_id>.json with the chunk text, so the
gate and the grouping (`local group`) re-run without a model call."""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Awaitable, Callable

from ..crawl.common.files import append_jsonl, now, write_json
from ..llm import LOCAL_CLAIM


def _split(text: str, max_chars: int) -> list[str]:
    """A section longer than max_chars, cut at paragraphs (a paragraph longer than that is cut hard)."""
    out, cur = [], ""
    for para in text.split("\n\n"):
        while len(para) > max_chars:
            if cur:
                out.append(cur)
                cur = ""
            out.append(para[:max_chars])
            para = para[max_chars:]
        joined = f"{cur}\n\n{para}" if cur else para
        if len(joined) > max_chars:
            out.append(cur)
            cur = para
        else:
            cur = joined
    if cur.strip():
        out.append(cur)
    return out


def chunks(doc: dict, max_chars: int = 6000) -> list[dict]:
    """[{heading, text}]: whole sections packed in order up to max_chars, the heading of a section as a line."""
    out, cur, first = [], "", ""
    for s in doc.get("sections") or []:
        heading, body = str(s.get("heading") or "").strip(), str(s.get("text") or "").strip()
        for i, piece in enumerate(_split(body, max_chars - len(heading) - 1) if body else []):
            block = f"{heading}\n{piece}" if heading and i == 0 else piece
            if cur and len(cur) + 2 + len(block) > max_chars:
                out.append({"heading": first, "text": cur})
                cur, first = "", ""
            first = first or heading
            cur = f"{cur}\n\n{block}" if cur else block
    if cur:
        out.append({"heading": first, "text": cur})
    return out


def input_hash(doc: dict, max_chars: int) -> str:
    return hashlib.sha256(json.dumps([doc.get("sections"), max_chars, LOCAL_CLAIM.prompt_hash],
                                     ensure_ascii=False).encode()).hexdigest()[:16]


async def extract(docs: list[dict], out: Path, *, city_name: str, ask: Callable[..., Awaitable[dict]], model: str,
                  chunk_chars: int = 6000, parallel: int = 4) -> dict:
    """Read each document not cached under `out` (same input hash). A document with a failed call writes nothing and
    logs to out/../errors.jsonl; the next run retries it."""
    sem = asyncio.Semaphore(parallel)
    stats = {"docs": len(docs), "read": 0, "cached": 0, "failed": 0, "chunks": 0}

    async def call(d: dict, part: dict) -> dict:
        async with sem:
            return await ask(city=city_name, title=d.get("title") or "", url=d.get("source_url") or "",
                             heading=part["heading"] or "-", text=part["text"])

    async def one(d: dict) -> None:
        target, h = out / f"{d['doc_id']}.json", input_hash(d, chunk_chars)
        if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("input_hash") == h:
            stats["cached"] += 1
            return
        parts = chunks(d, chunk_chars)
        try:
            answers = await asyncio.gather(*(call(d, p) for p in parts))
        except Exception as e:  # one bad document must not stop the others
            append_jsonl(out.parent / "errors.jsonl", {"at": now(), "id": d["doc_id"], "stage": "extract",
                                                       "error": f"{type(e).__name__}: {str(e)[:300]}"})
            stats["failed"] += 1
            return
        write_json(target, {"doc_id": d["doc_id"], "input_hash": h, "prompt_hash": LOCAL_CLAIM.prompt_hash,
                            "model": model, "built_at": now(),
                            "chunks": [{**p, "items": a.get("claims") or []} for p, a in zip(parts, answers)]})
        stats["read"] += 1
        stats["chunks"] += len(parts)

    await asyncio.gather(*(one(d) for d in docs))
    return stats
