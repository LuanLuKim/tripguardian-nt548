"""Count usable evidence without calling a model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from paths import DATA, REPO
from . import config


@dataclass
class Gate:
    ok: bool
    ext: int
    view: int
    reason: str


def _check(file: Path, drop: list[str]) -> Gate:
    if not file.exists():
        return Gate(False, 0, 0, "no_photo_scenes")
    data = json.loads(file.read_text())
    photos = data.get("photos", []) if isinstance(data, dict) else data
    excluded = {Path(name).stem for name in drop}
    usable = [p for p in photos if p.get("keep", True) and not p.get("stale")
              and Path(p.get("name", "")).stem not in excluded]
    ext = sum(p.get("scene") == "exterior" for p in usable)
    view = sum(p.get("scene") == "view" for p in usable)
    ok = ext + view >= config()["evidence_min"]
    return Gate(ok, ext, view, "" if ok else "no_exterior_evidence")


def check_fid(fid: str) -> Gate:
    if not fid or Path(fid).name != fid:
        return Gate(False, 0, 0, "no_photo_scenes")
    return _check(REPO / "data/gmaps/photo_scenes" / f"{fid.replace(':', '_')}.json", [])


def check_place(slug: str, drop: list[str]) -> Gate:
    if not slug or Path(slug).name != slug:
        return Gate(False, 0, 0, "no_photo_scenes")
    return _check(DATA / "places" / slug / "photos_index.json", drop)
