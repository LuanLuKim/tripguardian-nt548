"""Write web/public/data/photo_allow.json: the Maps photos a user may be shown, per place (owner rule 2026-10-28: no photo
with a person on it; owner 2026-11-16: a place short of photos may show ones with people, person-free first and the least
crowded of the frame first, see scenes.pick). A photo is listed only when corpus.serving.scenes.allowed() passes: scene label `person = no` with
high confidence, not a crowd scene, not a near-duplicate, not blurry or dark. The web (store.ts coversOf) drops every cover
that is not listed here, so an unlabelled or doubtful old cover never reaches a card. Places without any entry show the
no-photo placeholder.

photo_allow.json maps place id -> ["<file name>.jpg", ...] (the file in gmaps/<place id with : -> _>/photos/).

Usage (repo root): .venv/bin/python web/scripts/export_photo_allow.py   (rerun after `python -m corpus gmaps photo_scenes`)
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from corpus.crawl.common.files import safe_name  # noqa: E402
from corpus.serving import scenes  # noqa: E402

OUT = ROOT / "web/public/data/photo_allow.json"
SNAPSHOT = ROOT / "web/public/data/snapshot-lite.json"


def unlabelled(pid: str, cfg: dict) -> list[str]:
    """Last resort for a place the scene labels do not cover (no `photo_scenes` file, or none of its labelled photos usable): the
    crawled photos themselves, sharpest and best exposed first (measured here from the pixels, no model; person unknown, scene
    unknown), at most `show`; fresh photos first, then the old ones the crawl kept `stale` (older than 3 years: only when the place has
    nothing newer). A place with no picture at all is worse than one with a picture that may show a person or be dated."""
    d = ROOT / "data/gmaps/places" / safe_name(pid)
    try:
        rows = json.loads((d / "photos.json").read_text(encoding="utf-8")).get("photos") or []
    except (OSError, ValueError):
        return []
    scored = []
    for e in rows:
        if not (d / e["file"]).exists():
            continue
        try:
            im = Image.open(d / e["file"])
            im.draft("L", (768, 768))
            im = im.convert("L")
            im = im.resize((384, max(1, round(im.height * 384 / im.width))))
        except (OSError, ValueError, ZeroDivisionError):
            continue
        a = np.asarray(im, dtype=np.float32)
        if min(a.shape) < 3:
            continue
        blur = float((a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4 * a[1:-1, 1:-1]).var())
        light = float(a.mean())
        if blur >= cfg["blur_below"] and cfg["dark_below"] <= light <= cfg["bright_above"]:
            scored.append((not e.get("stale"), scenes.quality({"blur": blur, "brightness": light, "owner": e.get("owner")}), e["file"].rsplit("/", 1)[1]))
    return [f for *_, f in sorted(scored, reverse=True)[: cfg["show"]]]


def main() -> None:
    ids = [p["id"] for p in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["places"]]
    out = {}
    for pid in ids:
        files = [f.rsplit("/", 1)[1] for f in scenes.allowed_for_place(pid)]
        if len(files) < scenes.config()["min_photos"]:  # thin place: the card picks add visitor photos with people, after the free ones
            files += [f for f in (p["file"].rsplit("/", 1)[1] for p in scenes.for_place(pid)) if f not in files]
        if not files:
            files = unlabelled(pid, scenes.config())
        if files:
            out[pid] = files
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} of {len(ids)} places keep >= 1 allowed photo, {sum(map(len, out.values()))} photos -> {OUT}")


if __name__ == "__main__":
    main()
