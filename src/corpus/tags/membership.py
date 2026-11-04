"""Read-only travel-motive decisions, bound to evidence rather than a release id."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from ..crawl.common.files import data_dir
from . import vocab

_REVIEWER = ContextVar("tag_membership_reviewer", default=None)


@contextmanager
def using_reviewer(reviewer: str):
    if reviewer not in {"primary", "secondary", "consensus"}:
        raise ValueError("unknown membership reviewer")
    token = _REVIEWER.set(reviewer)
    try:
        yield
    finally:
        _REVIEWER.reset(token)


def decision_path(root: Path | None = None) -> Path:
    reviewer = _REVIEWER.get() or vocab.config().get("membership", {}).get("reader", "primary")
    base = directory(root)
    if reviewer == "secondary":
        return base / "judges" / "secondary" / "current.json"
    return base / ("consensus.json" if reviewer == "consensus" else "current.json")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def record_hash(record: dict, axis: str, key: str, style_ids=()) -> str:
    """The served inputs a judgement depended on; new evidence invalidates an old yes."""
    identity = record.get("identity") or {}
    common = {k: identity.get(k) for k in ("name", "category", "category_group")}
    if axis == "experience":
        source = vocab.config()["features"].get(key, {}).get("source", key).partition("=")[0]
        common["feature"] = next((record[section][source] for section in ("experience", "environment", "service", "effort", "suitability")
                                  if source in (record.get(section) or {})), None)
    elif axis == "dish":
        common["menu"] = record.get("menu")
        common["review_dishes"] = record.get("review_dishes")
        common["order"] = (record.get("details") or {}).get("order")
    elif axis == "style":
        common["styles"] = sorted(style_ids)
    return digest(common)


def definition_hash(axis: str, key: str) -> str:
    cfg = vocab.config()
    return digest({"version": cfg.get("membership", {}).get("version"), "axis": axis, "key": key,
                   "definition": cfg.get("definitions", {}).get(key if axis == "experience" else vocab.ref(axis, key)),
                   "dish_policy": cfg.get("dish_policy") if axis == "dish" else None})


def directory(root: Path | None = None) -> Path:
    return (root or data_dir()) / vocab.config().get("membership", {}).get("directory", "tag_membership")


@lru_cache(maxsize=8)
def _load(path: str, mtime: int, ctime: int = 0, size: int = 0) -> dict:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return doc.get("places", {}) if doc.get("schema") == 2 else {}
    except (OSError, ValueError):
        return {}


def reader_revision(place_id: str, root: Path | None = None) -> tuple:
    """Cache identity for consumers: legacy is stable; v2 follows snapshots and supporting image metadata."""
    if not vocab.enabled():
        return ("legacy",)
    path = decision_path(root)
    try:
        stat = path.stat()
    except OSError:
        return (str(path), None)
    token = (str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
    images = []
    for ref, item in _load(*token).get(place_id, {}).items():
        if not ref.startswith("style:"):
            continue
        for evidence in item.get("evidence", ()):
            relative = Path(evidence.get("file", ""))
            if evidence.get("source") != "photo" or relative.is_absolute() or ".." in relative.parts:
                continue
            image = (root or data_dir()) / relative
            try:
                stat = image.stat()
                images.append((str(relative), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
            except OSError:
                images.append((str(relative), None))
    return (*token, tuple(images))


@lru_cache(maxsize=8192)
def _image_hash(path: str, mtime: int, ctime: int, size: int) -> str:
    return digest(Path(path).read_bytes().hex())


def _images_fresh(item: dict, root: Path) -> bool:
    for evidence in item.get("evidence", ()):
        if evidence.get("source") != "photo":
            continue
        relative = Path(evidence.get("file", ""))
        if relative.is_absolute() or ".." in relative.parts:
            return False
        path = root / relative
        try:
            if not path.resolve().is_relative_to(root.resolve()):
                return False
            stat = path.stat()
            if _image_hash(str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size) != evidence.get("image_hash"):
                return False
        except (OSError, ValueError):
            return False
    return True


def decisions(record: dict, style_ids=(), root: Path | None = None) -> dict[str, str]:
    """Only fresh, validated decisions; no writes, no model, no release-local cache."""
    path = decision_path(root)
    try:
        stat = path.stat()
        places = _load(str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
    except OSError:
        return {}
    out = {}
    for ref, item in places.get(record.get("id"), {}).items():
        axis, _, key = ref.partition(":")
        if not vocab.known(axis, key) or item.get("definition_hash") != definition_hash(axis, key):
            continue
        from .prompt import TAG_MEMBERSHIP
        if item.get("prompt_hash") != TAG_MEMBERSHIP.prompt_hash:
            continue
        if path.name == "consensus.json" or path.parent.name == "secondary":
            from .offline import reviewer_task
            if item.get("reviewer_hash") != reviewer_task("secondary")[2]:
                continue
        if item.get("record_hash") != record_hash(record, axis, key, style_ids):
            continue
        if axis == "style" and not _images_fresh(item, root or data_dir()):
            continue
        if item.get("verdict") in {"yes", "no", "unclear"}:
            out[ref] = item["verdict"]
    return out
