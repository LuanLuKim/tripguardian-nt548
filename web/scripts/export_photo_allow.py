"""Write web/public/data/photo_allow.json: the Maps photos a user may be shown, per place (owner rule 2026-10-28: no photo
with a person on it). A photo is listed only when corpus.serving.scenes.allowed() passes: scene label `person = no` with
high confidence, not a crowd scene, not a near-duplicate, not blurry or dark. The web (store.ts coversOf) drops every cover
that is not listed here, so an unlabelled or doubtful old cover never reaches a card. Places without any entry show the
no-photo placeholder.

photo_allow.json maps place id -> ["<file name>.jpg", ...] (the file in gmaps/<place id with : -> _>/photos/).

Usage (repo root): .venv/bin/python web/scripts/export_photo_allow.py   (rerun after `python -m corpus gmaps photo_scenes`)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from corpus.serving import scenes  # noqa: E402

OUT = ROOT / "web/public/data/photo_allow.json"
SNAPSHOT = ROOT / "web/public/data/snapshot-lite.json"


def main() -> None:
    ids = [p["id"] for p in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["places"]]
    out = {}
    for pid in ids:
        files = [f.rsplit("/", 1)[1] for f in scenes.allowed_for_place(pid)]
        if files:
            out[pid] = files
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} of {len(ids)} places keep >= 1 allowed photo, {sum(map(len, out.values()))} photos -> {OUT}")


if __name__ == "__main__":
    main()
