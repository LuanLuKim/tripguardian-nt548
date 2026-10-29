"""Phase `web documents`: each URL of doc_urls.jsonl read once into data/web/<city>/documents/<doc_id>.json, split by
heading and cut at doc_max_chars. A Document is input for local knowledge (P4), never an observation about a place;
nothing here calls a model."""

import json
import re
import time

from ..common.files import data_dir, load_config, log_error, now, write_json
from .client import Web, WebError
from .links import doc_id

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_sleep = time.sleep


class TooShort(WebError):
    """The page has less text than doc_min_chars."""


def split_sections(text: str) -> list[dict]:
    sections, heading, body = [], "", []

    def close():
        joined = "\n".join(body).strip("\n")
        if joined.strip():
            sections.append({"heading": heading, "text": joined})

    for line in text.splitlines():
        if m := _HEADING.match(line):
            close()
            heading, body = m.group(1), []
        else:
            body.append(line)
    close()
    return sections


def _failures(path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("stage") == "document":
            counts[str(row.get("id"))] = counts.get(str(row.get("id")), 0) + 1
    return counts


def run(city: str, limit: int | None = None, web: Web | None = None) -> dict:
    started = time.monotonic()
    _, cfg = load_config(city)
    cfg_web = cfg["web"]
    web_root = data_dir() / "web" / city
    web = web or Web.from_config(cfg_web, data_dir() / "web")
    max_chars, min_chars = int(cfg_web.get("doc_max_chars", 40_000)), int(cfg_web.get("doc_min_chars", 300))
    pause = float(cfg_web.get("page_pause_s", 1.0))
    rows, seen = [], set()
    path = web_root / "doc_urls.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        try:
            row = json.loads(line)
            url = row["url"]
        except (ValueError, KeyError, TypeError):
            continue
        did = doc_id(url)
        if did not in seen:
            seen.add(did)
            rows.append((did, row))
    failed = _failures(web_root / "errors.jsonl")
    stats = {"todo": 0, "ok": 0, "failed": 0, "too_short": 0, "cut": 0, "skipped_failed": 0}
    tried = 0
    for did, row in rows:
        target = web_root / "documents" / f"{did}.json"
        if target.exists():
            continue
        stats["todo"] += 1
        if failed.get(did, 0) >= 2:
            stats["skipped_failed"] += 1
            continue
        if limit is not None and tried >= limit:
            continue
        if tried and pause > 0:
            _sleep(pause)
        tried += 1
        try:
            doc = web.read_document(row["url"], max_chars=max_chars)
            if doc.chars < min_chars:
                raise TooShort(f"{doc.chars} chars < {min_chars}")
        except TooShort as err:
            log_error(web_root, did, "document", err)
            stats["too_short"] += 1
            continue
        except (WebError, ValueError) as err:
            log_error(web_root, did, "document", err)
            stats["failed"] += 1
            continue
        write_json(target, {"doc_id": did, "source_url": row["url"], "domain": doc.domain,
                            "title": doc.title or str(row.get("title") or ""), "retrieved_at": now(), "lang": doc.lang,
                            "kind": "web", "sections": split_sections(doc.text), "chars": doc.chars, "cut": doc.cut,
                            "query": str(row.get("query") or "")})
        stats["ok"] += 1
        stats["cut"] += doc.cut
        print(f"web documents: {row['url']} {doc.chars} chars{' (cut)' if doc.cut else ''}")
    stats["seconds"] = round(time.monotonic() - started, 1)
    print(f"web documents {city}: {stats}")
    return stats
