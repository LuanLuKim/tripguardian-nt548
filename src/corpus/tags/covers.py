"""Offline cover approvals; online reads only exact, fresh, reviewed images."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import vocab
from .membership import decisions, definition_hash, digest, directory, record_hash
from .prompt import TAG_MEMBERSHIP


def _image(root: Path, file: str) -> Path:
    relative = Path(file)
    if not file or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("cover file must be a data-relative path")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("cover file must stay inside data root")
    return path


def save_cover_reviews(rows: list[dict], reviews: list[dict], root: Path, *, merge: bool = False) -> dict:
    """Stamp reviewed images; merging preserves old stamps verbatim, never renewing stale approvals."""
    by_id = {r["place_id"]: r for r in rows}
    stamped = []
    with vocab.pending_vocabulary():
        for review in reviews:
            row = by_id[review["place_id"]]
            tag = review["tag"]
            axis, _, key = tag.partition(":")
            if not vocab.known(axis, key) or review.get("verdict") not in {"yes", "no", "unclear"}:
                raise ValueError("unknown tag or invalid cover verdict")
            if not review.get("reason") or not review.get("reviewed_by"):
                raise ValueError("cover review needs a reason and reviewer")
            path = _image(root, review["file"])
            stamped.append({**review, "image_hash": digest(path.read_bytes().hex()),
                            "definition_hash": definition_hash(axis, key),
                            "record_hash": record_hash(row["record"], axis, key, row.get("styles", ())),
                            "prompt_hash": TAG_MEMBERSHIP.prompt_hash})
    path = directory(root) / "covers.json"
    if merge:
        try:
            old = json.loads(path.read_text())
        except (OSError, ValueError):
            old = {}
        keys = {(r["place_id"], r["tag"], r["file"]) for r in stamped}
        stamped.extend(r for r in old.get("reviews", ()) if old.get("schema") == 1 and isinstance(r, dict)
                       and all(k in r for k in ("place_id", "tag", "file"))
                       and (r["place_id"], r["tag"], r["file"]) not in keys)
    doc = {"schema": 1, "reviews": sorted(stamped, key=lambda r: (r["tag"], r["place_id"], r["file"]))}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True))
    temp.replace(path)
    return {"reviews": len(stamped), "approved": sum(r["verdict"] == "yes" for r in stamped)}


@lru_cache(maxsize=8)
def _load(path: str, mtime: int) -> list[dict]:
    try:
        doc = json.loads(Path(path).read_text())
        return doc.get("reviews", []) if doc.get("schema") == 1 else []
    except (OSError, ValueError):
        return []


def approved_covers(record: dict, style_ids, ref: str, root: Path | None = None) -> list[str]:
    """Data-relative photos for a fresh Judge-yes member; empty never authorizes an arbitrary fallback."""
    if not vocab.enabled():
        return []
    if decisions(record, style_ids, root).get(ref) != "yes":
        return []
    axis, _, key = ref.partition(":")
    if not vocab.of_record(record, style_ids, root=root).carries(axis, key):
        return []
    base = directory(root)
    root = base.parent
    path = base / "covers.json"
    try:
        reviews = _load(str(path), path.stat().st_mtime_ns)
    except OSError:
        return []
    out = []
    for item in reviews:
        if (item.get("place_id") != record.get("id") or item.get("tag") != ref or item.get("verdict") != "yes"
                or item.get("definition_hash") != definition_hash(axis, key)
                or item.get("record_hash") != record_hash(record, axis, key, style_ids)
                or item.get("prompt_hash") != TAG_MEMBERSHIP.prompt_hash):
            continue
        try:
            file = item.get("file", "")
            if digest(_image(root, file).read_bytes().hex()) == item.get("image_hash"):
                out.append(file)
        except (OSError, ValueError, TypeError):
            continue
    return list(dict.fromkeys(out))
