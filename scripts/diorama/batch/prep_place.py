"""Prepare one place for the 3D batch: photos filtered by scene label, a numbered contact sheet, the OSM footprint.

Usage: python batch/prep_place.py <slug> <fid_dir>
Writes places/<slug>/photos/gNN.jpg (exterior + view first, then interior/room), photos_index.json,
contact.jpg (for the coordinator's one-glance check), osm_footprints.json (from batch/footprints/), meta.json."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA, REPO

import json
import shutil

from PIL import Image, ImageDraw, ImageFont

D = DATA
ROOT = REPO
KEEP = ("exterior", "view", "interior", "room")


def main(slug, fid):
    scenes = json.loads((ROOT / "data/gmaps/photo_scenes" / f"{fid}.json").read_text())["photos"]
    place = json.loads((ROOT / "data/gmaps/places" / fid / "place.json").read_text())
    photos = sorted((p for p in scenes if p.get("scene") in KEEP and p.get("keep", True) and not p.get("stale")),
                    key=lambda p: KEEP.index(p["scene"]))
    out = D / "places" / slug
    (out / "photos").mkdir(parents=True, exist_ok=True)
    index = []
    for i, p in enumerate(photos):
        name = f"g{i:02d}.jpg"
        shutil.copy2(ROOT / "data/gmaps/places" / fid / p["file"], out / "photos" / name)
        index.append({"name": name, "photo_id": p["photo_id"], "scene": p["scene"], "kind": p.get("kind"),
                      "month": p.get("month"), "owner": p.get("owner")})
    (out / "photos_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))
    W, H, C = 380, 300, 6
    rows = (len(index) + C - 1) // C
    sheet = Image.new("RGB", (W * C, (H + 24) * rows), "white")
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default(size=18)
    for k, e in enumerate(index):
        im = Image.open(out / "photos" / e["name"]).convert("RGB")
        im.thumbnail((W - 6, H - 6))
        x, y = (k % C) * W, (k // C) * (H + 24)
        sheet.paste(im, (x + 3, y + 3))
        draw.text((x + 4, y + H), f'{e["name"]} {e["scene"]}', fill="black", font=font)
    sheet.save(out / "contact.jpg", quality=85)
    fp = D / "batch" / "footprints" / f"{fid}.json"
    if fp.exists():
        shutil.copy2(fp, out / "osm_footprints.json")
    meta = {"slug": slug, "fid": fid, "name": place["name"], "category": place.get("category"),
            "lat": place.get("lat"), "lng": place.get("lng"), "reviews": place.get("reviews"),
            "photos": {s: sum(e["scene"] == s for e in index) for s in KEEP}, "osm": fp.exists()}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:3])
