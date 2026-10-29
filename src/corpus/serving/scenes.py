"""Best photo per scene of a place, for cards (docs/CORPUS.md, Ảnh Google Maps: scene labels). Reads the observation files
of `python -m corpus gmaps photo_scenes` (data/gmaps/photo_scenes); thresholds in config/scenes.yaml. Display only: a place
without labels returns an empty list and the caller keeps the photos it has. Nothing here is evidence about the place.

A photo is shown only when: it is the sharpest of its near-duplicate cluster, no person is in the frame (label `no` with
confidence `high`; yes / unknown / a doubtful no / scene crowd never pass), it is not blurry, too dark or washed out, and its scene is one the
place's kind lists. One photo per scene, scenes in the order of the place's kind.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

from ..crawl.common.files import ROOT, data_dir, safe_name

CONFIG_FILE = ROOT / "config" / "scenes.yaml"
OUT_DIR = "photo_scenes"


@lru_cache(maxsize=1)
def config() -> dict:
    """config/scenes.yaml `pick`, read once per process (cards call this per place); treat as read-only."""
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))["pick"]


def kind_of(category_group: str | None, cfg: dict | None = None) -> str:
    """"stay" | "eat" | "sight" | "default": which scene order a place of this corpus category_group gets."""
    for kind, groups in ((cfg or config())["groups"]).items():
        if category_group in groups:
            return kind
    return "default"


def load(place_id: str, data: Path | None = None) -> dict | None:
    """The photo_scenes observation file of a place, or None (not labelled yet)."""
    try:
        return json.loads(((data or data_dir()) / "gmaps" / OUT_DIR / f"{safe_name(place_id)}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def person_free(e: dict, cfg: dict) -> bool:
    """The strict no-people rule (owner 2026-10-28): the label is `no` with a confidence at or above
    `person_min_confidence`. `yes`, `unknown`/null, a low-confidence `no` and a missing label are all "maybe a person"."""
    person = e.get("person") or {}
    rank = CONFIDENCE_RANK.get(person.get("confidence"), -1)
    return (person.get("value") is False and "no" in cfg["person_free"]
            and rank >= CONFIDENCE_RANK[cfg["person_min_confidence"]]
            and e.get("scene") not in (None, *cfg["never_scenes"]))


def allowed(e: dict, cfg: dict) -> bool:
    """Whether a labelled photo may be shown to a user anywhere: person-free (see `person_free`), not a crowd scene, not
    a near-duplicate, not blurry, dark or washed out. Any scene qualifies (the gallery); cards also want `shown`."""
    blur, light = e.get("blur"), e.get("brightness")
    return bool(e.get("keep") and person_free(e, cfg)
                and blur is not None and blur >= cfg["blur_below"]
                and light is not None and cfg["dark_below"] <= light <= cfg["bright_above"])


def shown(e: dict, cfg: dict) -> bool:
    """Whether a labelled photo may be a scene pick of a card (allowed, and a scene that says something of the place)."""
    return allowed(e, cfg) and e.get("scene") not in ("other", "menu")


def allowed_files(doc: dict | None, cfg: dict | None = None) -> list[str]:
    """Data-relative files (gmaps/places/<fid_dir>/photos/<id>.jpg) of every allowed photo of a place; [] without labels.
    The one list every user-facing photo path is filtered through (covers gallery, Trip look cards)."""
    if not doc:
        return []
    cfg = cfg or config()
    d = f"gmaps/places/{safe_name(doc['place_fid'])}/"
    return [d + e["file"] for e in doc.get("photos") or [] if allowed(e, cfg)]


def quality(e: dict) -> float:
    """Order inside one scene: sharper and better exposed first (the sharpness counts up to a cap, so texture alone does
    not win); the business's own photo loses ties to a visitor's."""
    return min(e["blur"], 3000.0) / 3000.0 - abs(e["brightness"] - 125.0) / 250.0 - (0.05 if e.get("owner") else 0.0)


def pick(doc: dict | None, category_group: str | None = None, cfg: dict | None = None) -> list[dict]:
    """[{"scene", "photo_id", "file", "w", "h"}] one per scene, in the scene order of the place's kind. `file` is relative to the
    data directory (gmaps/places/<fid_dir>/photos/<id>.jpg). Empty without labels."""
    if not doc:
        return []
    cfg = cfg or config()
    order = cfg["scene_order"].get(kind_of(category_group, cfg)) or cfg["scene_order"]["default"]
    best: dict[str, dict] = {}
    for e in doc.get("photos") or []:
        if e["scene"] in order and shown(e, cfg) and (e["scene"] not in best or quality(e) > quality(best[e["scene"]])):
            best[e["scene"]] = e
    d = f"gmaps/places/{safe_name(doc['place_fid'])}/"
    return [{"scene": s, "photo_id": best[s]["photo_id"], "file": d + best[s]["file"], "w": best[s].get("w"),
             "h": best[s].get("h")} for s in order if s in best]


def allowed_for_place(place_id: str, data: Path | None = None) -> list[str]:
    """`allowed_files` of one place by id."""
    return allowed_files(load(place_id, data))


def for_place(place_id: str, category_group: str | None = None, data: Path | None = None) -> list[dict]:
    """The best photo per scene of one place (see `pick`); [] when it has no labels."""
    return pick(load(place_id, data), category_group)


def coverage(place_ids: list[str], data: Path | None = None) -> dict:
    """{"places", "labelled_places", "photos", "labelled_photos", "with_min_scenes", "scene_counts"}: how much of the
    given places' photos carry labels and how many places can show config `min_scenes` distinct scenes (category group
    unknown here, so the `default` order; a stay or a sight is counted by the scenes it has at all)."""
    cfg = config()
    root = data or data_dir()
    labelled = photos = labelled_photos = enough = 0
    scenes: dict[int, int] = {}
    for pid in place_ids:
        d = root / "gmaps" / "places" / safe_name(pid)
        try:
            n = sum(1 for p in json.loads((d / "photos.json").read_text(encoding="utf-8")).get("photos", [])
                    if not p.get("stale") and (d / p["file"]).exists())
        except (OSError, ValueError):
            n = 0
        photos += n
        doc = load(pid, root)
        if not doc:
            continue
        labelled += 1
        labelled_photos += len(doc.get("photos") or [])
        flat = {**cfg, "scene_order": {"default": sorted({e["scene"] for e in doc["photos"]})}, "groups": {}}
        k = len(pick(doc, None, flat))
        scenes[k] = scenes.get(k, 0) + 1
        enough += k >= cfg["min_scenes"]
    return {"places": len(place_ids), "labelled_places": labelled, "photos": photos, "labelled_photos": labelled_photos,
            "with_min_scenes": enough, "scenes_per_place": dict(sorted(scenes.items()))}
