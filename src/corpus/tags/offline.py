"""Incremental, one-Judge-call-per-place travel-motive membership build."""
from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

from ..llm import JUDGE, Role
from ..serving import dishes as menu
from . import vocab
from .membership import _image_hash, definition_hash, digest, directory, record_hash
from .prompt import TAG_MEMBERSHIP


@dataclass(frozen=True)
class _TrackJudge(Role):
    effort: str = "high"

    def reasoning(self) -> str:
        return self.effort


def reviewer_task(reviewer: str = "primary") -> tuple:
    """A track-local Judge role; never mutates shared model roles or environment."""
    if reviewer == "primary":
        return TAG_MEMBERSHIP, None, ""
    if reviewer != "secondary":
        raise ValueError("reviewer must be primary or secondary")
    cfg = vocab.raw_config()["membership"]["secondary_judge"]
    role = _TrackJudge(name="tags_judge_secondary", purpose="independent offline tag membership review",
                      key_env=cfg["key_env"], base_url_env=cfg["base_url_env"], model_env="AGENT_MODEL",
                      guided=cfg.get("guided", False), default_parallel=8, effort=cfg["reasoning_effort"])
    return (replace(TAG_MEMBERSHIP, role=role, max_tokens=cfg["max_tokens"]), cfg["model"], digest(cfg))


def reviewer_directory(root: Path, reviewer: str) -> Path:
    base = directory(root)
    return base if reviewer == "primary" else base / "judges" / "secondary"


def metered_client(client, usages: list[dict]):
    """Capture the provider's actual streamed usage; no character-to-token or price guesses."""
    class Stream:
        def __init__(self, source):
            self.source = source

        async def __aiter__(self):
            async for chunk in self.source:
                usage = getattr(chunk, "usage", None)
                if usage:
                    usages.append(usage.model_dump())
                yield chunk

        async def close(self):
            await self.source.close()

    async def create(**kwargs):
        source = await client.chat.completions.create(**kwargs, stream_options={"include_usage": True})
        return Stream(source) if hasattr(source, "__aiter__") else source
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def _evidence(items: list[dict]) -> list[dict]:
    unique = {digest(item): item for item in items if item.get("quote")}
    return [unique[k] for k in sorted(unique)]


def candidates(row: dict, *, root: Path | None = None) -> list[dict]:
    """All supported candidates, including split concepts; sorted independently of input order."""
    record = row["record"]
    out = []
    def add(axis, key, evidence):
        evidence = _evidence(evidence)
        out.append({"tag": vocab.ref(axis, key), "evidence": evidence,
                    "evidence_hash": digest(evidence), "record_hash": record_hash(record, axis, key, row.get("styles", ())),
                    "definition_hash": definition_hash(axis, key)})
    for key, cfg in vocab.config()["features"].items():
        source = cfg.get("source", key).partition("=")[0]
        # Include an uncertain/negative source too: a Judge must see negation and conflicts.
        evidence = row.get("features", {}).get(source, [])
        if evidence or any(source in (record.get(section) or {}) for section in ("experience", "environment")):
            add("experience", key, evidence)
    for key, cfg in vocab.dish_kinds().items():
        evidence = []
        for ev, texts in menu.rows_of(record):
            if any(menu.has_phrase(menu.keep(text), menu.keep(p)) for text in texts for p in cfg["phrases"]):
                evidence.append({"quote": ev.get("quote") or ev.get("dish", ""), "source": ev.get("source"),
                                 "dish": ev.get("dish"), "n": ev.get("n")})
        if evidence:
            add("dish", key, evidence)
    if root is not None:
        for key in sorted(row.get("styles", ())):
            if key not in vocab.styles():
                continue
            evidence = []
            for item in row.get("style_evidence", {}).get(key, ()):
                relative = Path(item.get("file", ""))
                path = root / relative
                if relative.is_absolute() or ".." in relative.parts or not path.is_file():
                    continue
                stat = path.stat()
                evidence.append({"quote": item.get("quote") or str(relative), "source": "photo",
                                 "file": str(relative), "image_hash": _image_hash(str(path), stat.st_mtime_ns,
                                                                              stat.st_ctime_ns, stat.st_size)})
            add("style", key, evidence)
    group = vocab.tag_group(record)
    if group in vocab.config()["categories"]:
        context = [e for evidence in row.get("features", {}).values() for e in evidence]
        add("category", group, [{"quote": row.get("name", ""), "source": "identity_name"},
                                {"quote": row.get("category") or "", "source": "identity_category"}, *context])
    return sorted(out, key=lambda c: c["tag"])


def definition(candidate: dict) -> dict:
    axis, _, key = candidate["tag"].partition(":")
    cfg = vocab.config()
    explicit = cfg.get("definitions", {}).get(candidate["tag"] if axis != "experience" else key)
    if explicit:
        return explicit
    if axis == "category":
        return {"include": f"Địa điểm thực sự thuộc nhóm {vocab.label(axis, key)}; tên và loại nguồn nhất quán.",
                "exclude": "Không suy từ nhãn Maps nếu tên/loại thực tế mâu thuẫn; đại lý bán tour không phải điểm trải nghiệm.",
                "example": vocab.label(axis, key)}
    return {"include": f"{vocab.label(axis, key)} là món đáng đến ăn/uống, có bằng chứng nổi bật, đúng loại phục vụ.",
            "exclude": "Dòng menu đơn lẻ/mô tả/thành phần chỉ là availability; không đủ gu khám phá. "
                       + "; ".join(cfg.get("dish_policy", {}).get("exclude", {}).get(key, ())),
            "example": f"Quán chuyên {vocab.label(axis, key)} hoặc có món được đề xuất cụ thể."}


def prompt_evidence(evidence: list[dict]) -> list[dict]:
    """Deterministic diverse originals within the Judge context window; full evidence stays hashed and saved."""
    ordered = sorted(evidence, key=lambda e: (not str(e.get("source", "")).startswith("identity_"),
                                             -(e.get("n") or len(e.get("observations", ()))), digest(e)))
    kept, size = [], 0
    # Preserve conflicting values before filling the remaining context with repeated praise.
    ordered = [e for i, e in enumerate(ordered) if e.get("value") not in {x.get("value") for x in ordered[:i]}] + ordered
    seen = set()
    for item in ordered:
        identity = digest(item)
        if identity in seen or len(kept) >= 12 or size >= 4200:
            continue
        seen.add(identity)
        text = item["quote"][:min(1200, 4200 - size)]
        kept.append({**{k: item[k] for k in ("source", "value", "dish", "file") if k in item}, "quote": text,
                     "n": item.get("n") or len(item.get("observations", ())) or None})
        size += len(text)
    return kept


def judge_input(row: dict, cs: list[dict], files: list[str]) -> dict:
    """Keep each binding definition adjacent to its indexed evidence, not in a distant parallel lookup."""
    return {"name": row["name"], "category": row.get("category"), "image_files_in_order": files,
            "candidates": [{"tag": c["tag"], "definition": definition(c),
                            "evidence": [{"quote_index": i, **e} for i, e in enumerate(prompt_evidence(c["evidence"]))],
                            "total_quotes": len(c["evidence"])} for c in cs]}


def image_payload(cs: list[dict], root: Path) -> tuple[list[bytes], list[str]]:
    """Decode local evidence files into bounded JPEGs; never fetch external images."""
    from io import BytesIO
    from PIL import Image
    files = list(dict.fromkeys(e["file"] for c in cs for e in c["evidence"] if e.get("source") == "photo"))
    payload = []
    for file in files:
        image = Image.open(root / file).convert("RGB")
        image.thumbnail((640, 640))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        payload.append(buffer.getvalue())
    return payload, files


def cache_key(candidate: dict, reviewer: str = "primary") -> str:
    return digest({k: candidate[k] for k in ("tag", "evidence_hash", "record_hash", "definition_hash")} | {
        "prompt_hash": TAG_MEMBERSHIP.prompt_hash,
        **({"reviewer_hash": reviewer_task(reviewer)[2]} if reviewer != "primary" else {})})


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def _validated(answer: dict, cs: list[dict]) -> tuple[dict, int]:
    items = answer.get("items", []) if isinstance(answer, dict) else []
    if isinstance(items, dict):
        selected = []
        for c in cs:
            item = items.get(c["tag"], {})
            index = item.get("quote_index") if isinstance(item, dict) else None
            evidence = prompt_evidence(c["evidence"])
            quote = evidence[index]["quote"] if type(index) is int and 0 <= index < len(evidence) else ""
            selected.append({**item, "tag": c["tag"], "quote": quote} if isinstance(item, dict) else {})
        items = selected
    counts = Counter(i.get("tag") for i in items if isinstance(i, dict))
    lookup = {i.get("tag"): i for i in items if isinstance(i, dict)}
    out, invalid = {}, 0
    for c in cs:
        item = lookup.get(c["tag"], {})
        verdict, quote = item.get("verdict"), item.get("quote")
        valid = (counts[c["tag"]] == 1 and verdict in {"yes", "no", "unclear"} and isinstance(quote, str)
                 and (not quote or any(quote in e["quote"] for e in c["evidence"]))
                 and (verdict != "yes" or bool(quote and quote.strip())))
        if valid and verdict == "yes" and item.get("support") in {
                "availability_only", "generic_praise", "contradiction", "incidental", "unsupported"}:
            valid = False
        if valid and verdict == "yes" and c["tag"].startswith("dish:"):
            # Availability alone cannot ground a discovery motive. A specialty in the
            # venue name or a popular dish can also ground an exact menu quotation.
            motive_sources = {"name", "menu_popular", "review_order"}
            supports = [e for e in c["evidence"] if e.get("source") in motive_sources]
            valid = any(quote in e["quote"] or e.get("source") in {"name", "menu_popular"} for e in supports)
        if not valid:
            invalid += 1
            item = {"verdict": "unclear", "quote": "", "reason": "invalid_or_missing_judge_evidence"}
        out[c["tag"]] = {k: item.get(k, "") for k in ("verdict", "quote", "reason", "support")}
    return out, invalid


async def judge_places(rows: list[dict], root: Path, *, parallel: int = 1, ask=None, reviewer: str = "primary") -> dict:
    """Write durable per-place/tag/evidence caches and atomically materialize the online read file.

    parallel is a track budget, not the endpoint's total capacity. The caller must reserve it first.
    A changed place is asked once for all candidates; unchanged per-tag results are reused verbatim.
    """
    if not 1 <= parallel <= 8:
        raise ValueError("tags lane budget must be between 1 and 8")
    task, override_model, reviewer_hash = reviewer_task(reviewer)
    base = reviewer_directory(root, reviewer)
    current = base / "current.json"
    try:
        places = json.loads(current.read_text()).get("places", {})
    except (OSError, ValueError):
        places = {}
    client = model = None
    if ask is None:
        client, model = task.role.client()
        model = override_model or model
        client = client.with_options(timeout=240.0, max_retries=0)
        async def ask(row, cs):
            images, files = image_payload(cs, root)
            from .prompt import VERDICT
            schema = {"type": "object", "properties": {"items": {"type": "object",
                      "properties": {c["tag"]: VERDICT for c in cs}, "required": [c["tag"] for c in cs],
                      "additionalProperties": False}}, "required": ["items"], "additionalProperties": False}
            usages = []
            try:
                answer = await replace(task, schema=schema).ask(
                    metered_client(client, usages) if reviewer == "secondary" else client,
                    model, images=images, place=json.dumps(judge_input(row, cs, files), ensure_ascii=False))
                if usages:
                    answer["_provider_usage"] = usages
                return answer
            finally:
                if usages:
                    counts["metered_calls"] += 1
                    for usage in usages:
                        counts["prompt_tokens"] += usage.get("prompt_tokens") or 0
                        counts["completion_tokens"] += usage.get("completion_tokens") or 0
                        counts["cached_tokens"] += (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    sem = asyncio.Semaphore(parallel)
    counts = Counter(calls=0, cached=0, places=0, invalid=0, errors=0)
    started = time.monotonic()
    async def one(row):
        async with sem:
            cs = candidates(row, root=root)
            pid = row["place_id"]
            folder = base / "cache" / digest(pid)[:24]
            saved, pending = {}, []
            for c in cs:
                path = folder / f"{cache_key(c, reviewer)}.json"
                try:
                    item = json.loads(path.read_text())
                    checked, invalid = _validated({"items": [{"tag": c["tag"], **item}]}, [c])
                    counts["invalid"] += invalid
                    saved[c["tag"]] = {**item, **checked[c["tag"]]}
                    counts["cached"] += 1
                except (OSError, ValueError):
                    pending.append(c)
            if pending:
                try:
                    counts["calls"] += 1
                    answer = await ask(row, cs)
                    _write(base / "answers" / digest(pid)[:24] / f"{digest([cache_key(c, reviewer) for c in cs])}.json", answer)
                    validated, invalid = _validated(answer, cs)
                    counts["invalid"] += invalid
                    for c in pending:
                        item = {**{k: c[k] for k in ("evidence_hash", "record_hash", "definition_hash")},
                                **validated[c["tag"]], "evidence": c["evidence"], "prompt_hash": task.prompt_hash,
                                **({"reviewer_hash": reviewer_hash, "model": override_model,
                                    "reasoning_effort": task.role.reasoning()} if reviewer_hash else {})}
                        _write(folder / f"{cache_key(c, reviewer)}.json", item)
                        saved[c["tag"]] = item
                except Exception as exc:
                    counts["errors"] += 1
                    _write(base / "errors" / f"{digest(pid)[:24]}.json", {"place_id": pid, "error": str(exc)[:1000]})
                    print(f"tag error {pid}: {type(exc).__name__}", flush=True)
            places[pid] = saved
            counts["places"] += 1
            # Per-tag files are already durable. Avoid rewriting the large snapshot for every place.
            if counts["places"] % 25 == 0:
                _write(current, {"schema": 2, "places": places})
                print(json.dumps(dict(counts)), flush=True)
    try:
        with vocab.pending_vocabulary():
            await asyncio.gather(*(one(row) for row in sorted(rows, key=lambda r: r["place_id"])))
    finally:
        _write(current, {"schema": 2, "places": places})
        if client is not None:
            await client.close()
    return {**dict(counts), "seconds": round(time.monotonic() - started, 2), "prompt_hash": TAG_MEMBERSHIP.prompt_hash,
            "model": model or override_model, "reviewer": reviewer,
            "cost_usd": None, "cost_note": "Provider billing unavailable; token counts only when reported",
            "estimated_input_chars": sum(len(json.dumps(candidates(r), ensure_ascii=False)) for r in rows)}
