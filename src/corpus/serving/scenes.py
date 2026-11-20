"""The photos a card shows for a place (docs/CORPUS.md, Ảnh Google Maps: scene labels). Reads the observation files of
`python -m corpus gmaps photo_scenes` (data/gmaps/photo_scenes) and `gmaps photo_appeal` (data/gmaps/photo_appeal);
thresholds in config/scenes.yaml. Display only: a place without labels returns an empty list and the caller keeps the
photos it has. Nothing here is evidence about the place.

A photo is shown only when: it is the sharpest of its near-duplicate cluster, no person is in the frame unless the
business posted it (see `person_free`), it is not blurry, too dark or washed out, and
its scene is one the place's kind lists (a restaurant may show only dishes) or the model says it shows the place. A
place short of photos may add a visitor's photo with people when the model says it shows the place. Among those the most appealing come first
(owner 2026-10-30: right for the place, the most attractive; no need for distinct scenes); a scene already shown costs a
little, so variety only breaks near ties.
"""

from __future__ import annotations

import collections
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from ..crawl.common.files import ROOT, data_dir, safe_name

CONFIG_FILE = ROOT / "config" / "scenes.yaml"
OUT_DIR = "photo_scenes"
APPEAL_DIR = "photo_appeal"


@lru_cache(maxsize=1)
def full_config() -> dict:
    """config/scenes.yaml, read once per process; treat as read-only."""
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))


def config() -> dict:
    """config/scenes.yaml `pick` (cards call this per place); treat as read-only."""
    return full_config()["pick"]


def kind_of(category_group: str | None, cfg: dict | None = None) -> str:
    """"stay" | "eat" | "sight" | "default": which scene order a place of this corpus category_group gets."""
    for kind, groups in ((cfg or config())["groups"]).items():
        if category_group in groups:
            return kind
    return "default"


def load(place_id: str, data: Path | None = None, folder: str = OUT_DIR) -> dict | None:
    """The photo_scenes (or, with folder=APPEAL_DIR, photo_appeal) observation file of a place, or None (not there yet)."""
    try:
        return json.loads(((data or data_dir()) / "gmaps" / folder / f"{safe_name(place_id)}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_appeal(place_id: str, data: Path | None = None) -> dict[str, dict]:
    """photo_id -> {"beauty", "shows_place"} (1-10 each) from `gmaps photo_appeal`; {} when the place is not scored."""
    return (load(place_id, data, APPEAL_DIR) or {}).get("photos") or {}


CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def person_free(e: dict, cfg: dict) -> bool:
    """The no-people rule (owner 2026-10-28, eased 2026-10-30): a visitor's photo passes when its label is `no` with a
    confidence at or above `person_min_confidence`; `yes`, `unknown`/null, a doubtful `no` and a missing label are all
    "maybe a person". The business's own photos (`owner`) may show people when config `owner_people` is on (its
    staff, its guests posed for it). Scenes in `never_scenes` never pass."""
    if e.get("scene") in (None, *cfg["never_scenes"]):
        return False
    if e.get("owner") and cfg.get("owner_people"):
        return True
    person = e.get("person") or {}
    rank = CONFIDENCE_RANK.get(person.get("confidence"), -1)
    return person.get("value") is False and "no" in cfg["person_free"] and rank >= CONFIDENCE_RANK[cfg["person_min_confidence"]]


def _clean(e: dict, cfg: dict, people: bool = False) -> bool:
    """Kept of its cluster, sharp, well exposed and person-free (`people`: whatever the person label says)."""
    blur, light = e.get("blur"), e.get("brightness")
    return bool(e.get("keep") and (person_free(e, cfg) or people and e.get("scene") not in (None, *cfg["never_scenes"]))
                and blur is not None and blur >= cfg["blur_below"]
                and light is not None and cfg["dark_below"] <= light <= cfg["bright_above"])


def allowed(e: dict, cfg: dict) -> bool:
    """Whether a labelled photo may be shown to a user anywhere: person-free (see `person_free`), not a crowd scene, not
    a near-duplicate, not blurry, dark or washed out, and inside the crawl's 3-year age cap. Any scene qualifies (the
    gallery); cards also want `shown`. A photo older than that (`old`, kept by the crawl for outdoor scenes only) never
    passes here: it is a card pick only (`old_shown`), where its year is shown."""
    return _clean(e, cfg) and not e.get("old")


def year_of(e: dict) -> int | None:
    month = e.get("month")
    try:
        return int(str(month)[:4])
    except (TypeError, ValueError):
        return None


def old_shown(e: dict, cfg: dict, category_group: str | None, today: date | None = None) -> bool:
    """A photo past the 3-year cap that a card may still show (config `pick.old`): outdoor scene (view / exterior) of a
    sight group, at most `max_age_years` old by its month, otherwise as clean as any shown photo."""
    old = cfg.get("old") or {}
    if not (e.get("old") and old and _clean(e, cfg) and category_group in old["groups"] and e.get("scene") in old["scenes"]):
        return False
    y, m = year_of(e), str(e.get("month") or "")[5:7]
    if y is None:
        return False
    t = today or date.today()
    months = (t.year - y) * 12 + t.month - (int(m) if m.isdigit() else 1)
    return months <= old["max_age_years"] * 12


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
    """Sharper and better exposed is better (the sharpness counts up to a cap, so texture alone does not win); the
    business's own photo loses ties to a visitor's. At most 1: it only orders photos the model scored alike."""
    return min(e["blur"], 3000.0) / 3000.0 - abs(e["brightness"] - 125.0) / 250.0 - (0.05 if e.get("owner") else 0.0)


def score(e: dict, appeal: dict[str, dict]) -> float:
    """beauty + shows_place (2-20) of the model, 0 when it did not score the photo, plus `quality`."""
    a = appeal.get(e["photo_id"]) or {}
    return (a.get("beauty") or 0) + (a.get("shows_place") or 0) + quality(e)


def _order(category_group: str | None, cfg: dict) -> list[str]:
    return cfg["scene_order"].get(kind_of(category_group, cfg)) or cfg["scene_order"]["default"]


def candidates(doc: dict | None, category_group: str | None = None, cfg: dict | None = None,
               appeal: dict[str, dict] | None = None) -> list[dict]:
    """The photos a card of this place may show (see the module doc), in the scene order of the place's kind (less those
    the model scored under `min_shows` for shows_place: a hair dryer, a hand with a glass), then the
    `off_kind` photos the model scored at least `off_kind_min_shows` for shows_place (a stay's breakfast, a shop's sign);
    a place still short of `min_photos` adds its `with_people` photos (owner 2026-11-16: a place short of photos may show
    one with people; unscored ones count, the ones the model scored under `min_shows` do not). They carry
    `with_people: True`, and `pick` shows them only after every person-free photo, the ones with the least of the frame taken by people first (`shows_place`)."""
    if not doc:
        return []
    cfg = cfg or config()
    rank = {s: i for i, s in enumerate(_order(category_group, cfg))}
    ok = [e for e in doc.get("photos") or []
          if e.get("scene") in rank and (shown(e, cfg) or old_shown(e, cfg, category_group))]
    appeal = appeal or {}
    shows = lambda e: (appeal.get(e["photo_id"]) or {}).get("shows_place", 0) >= cfg["off_kind_min_shows"]  # noqa: E731
    on_topic = lambda e: (appeal.get(e["photo_id"]) or {}).get("shows_place", 10) >= cfg["min_shows"]  # noqa: E731
    ok = sorted((e for e in ok if on_topic(e)), key=lambda e: rank[e["scene"]]) \
        + [e for e in off_kind(doc, category_group, cfg) if shows(e)]
    if len(ok) < cfg["min_photos"]:
        ok += [{**e, "with_people": True} for e in with_people(doc, cfg) if on_topic(e)]
    return ok


def with_people(doc: dict | None, cfg: dict | None = None) -> list[dict]:
    """A visitor's photos that may show a person (label yes / unknown / doubtful no) but are otherwise clean, fresh and
    not a crowd: card photos of a place short of `min_photos` (owner 2026-10-30, widened 2026-11-16 to photos the
    model has not scored); never in the gallery lists."""
    if not doc:
        return []
    cfg = cfg or config()
    return [e for e in doc.get("photos") or []
            if not e.get("old") and not person_free(e, cfg) and _clean(e, cfg, people=True)]


def off_kind(doc: dict | None, category_group: str | None = None, cfg: dict | None = None) -> list[dict]:
    """Photos allowed anywhere (`allowed`) whose scene the place's kind does not list: card photos only when the model
    says they show the place (`candidates`); `gmaps photo_appeal` sends them when the kind's own scenes are few."""
    if not doc:
        return []
    cfg = cfg or config()
    order = set(_order(category_group, cfg))
    return [e for e in doc.get("photos") or [] if e.get("scene") not in order and allowed(e, cfg)]


def pick(doc: dict | None, category_group: str | None = None, cfg: dict | None = None,
         appeal: dict[str, dict] | None = None) -> list[dict]:
    """[{"scene", "photo_id", "file", "w", "h"[, "year"]}], at most config `show`, best first: highest `score` less
    `repeat_penalty` per photo of its scene already picked; ties go to the scene order of the kind. A photo past the
    3-year cap (`year` set) waits until every fresh photo of its scene is picked. `file` is relative to the data
    directory (gmaps/places/<fid_dir>/photos/<id>.jpg). Empty without labels."""
    cfg = cfg or config()
    appeal = appeal or {}
    left = candidates(doc, category_group, cfg, appeal)
    picked: list[dict] = []
    while left and len(picked) < cfg["show"]:
        fresh = {e["scene"] for e in left if not e.get("old")}
        repeats = collections.Counter(e["scene"] for e in picked)
        free = any(not e.get("with_people") for e in left)  # a photo with people waits for every person-free one
        # Among photos with people the one where they take the least of the frame comes first: the model's `shows_place`
        # already gives "a person filling the frame" 1, so it leads the order there (owner 2026-11-16); unscored ones last.
        fresh_first = [e for e in left if not (e.get("old") and e["scene"] in fresh)]
        # the two waits can empty the list (a fresh photo with people, and the only person-free one is old, in the same scene): then the people wait is dropped
        eligible = [e for e in fresh_first if not (free and e.get("with_people"))] or fresh_first
        best = max(eligible,
                   key=lambda e: ((appeal.get(e["photo_id"]) or {}).get("shows_place", 0) if e.get("with_people") else 0,
                                  score(e, appeal) - cfg["repeat_penalty"] * repeats[e["scene"]]))
        picked.append(best)
        left.remove(best)
    d = f"gmaps/places/{safe_name(doc['place_fid'])}/" if doc else ""
    return [{"scene": e["scene"], "photo_id": e["photo_id"], "file": d + e["file"], "w": e.get("w"), "h": e.get("h"),
             **({"year": year_of(e)} if e.get("old") else {})} for e in picked]


def allowed_for_place(place_id: str, data: Path | None = None) -> list[str]:
    """`allowed_files` of one place by id."""
    return allowed_files(load(place_id, data))


def for_place(place_id: str, category_group: str | None = None, data: Path | None = None) -> list[dict]:
    """The card photos of one place (see `pick`); [] when it has no labels."""
    return pick(load(place_id, data), category_group, appeal=load_appeal(place_id, data))


def coverage(place_ids: list[str], data: Path | None = None) -> dict:
    """{"places", "labelled_places", "photos", "labelled_photos", "with_min_photos", "shown_per_place"}: how much of the
    given places' photos carry labels and how many places can show config `min_photos` photos (category group unknown
    here, so every scene but other/menu counts)."""
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
        k = len(pick(doc, None, flat, appeal=load_appeal(pid, root)))
        scenes[k] = scenes.get(k, 0) + 1
        enough += k >= cfg["min_photos"]
    return {"places": len(place_ids), "labelled_places": labelled, "photos": photos, "labelled_photos": labelled_photos,
            "with_min_photos": enough, "shown_per_place": dict(sorted(scenes.items()))}
