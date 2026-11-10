"""auto_colormap.py <slug> [--apply] : rule-based part of the photo recolour (owner 2026-11-04: vivid, true to photos).
Greens: grey-green vegetation (instance colours, or colours on lawn/bed/grove/tree/... objects) -> the approved deep greens
(Linh Phước / Cam Ly pass: value x0.65, saturation x2.7 clamped .30-.62, hue kept). Flowers: colours listed under
colors / flowerColor(s) / petal* in place.json -> same hue at flower saturation. Everything else (walls, roofs, paving,
water, interiors) is NOT touched: eyedrop those from photos (batch/eyedrop.py) and set them with batch/set_colormap.py.
Keys already in the place's colorMap win. Prints the proposed map; --apply merges it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA

import colorsys
import json
import re
import subprocess

D = DATA
slug = sys.argv[1]
src = D / ("linhson.json" if slug == "linhson" else f"places/{slug}/place.json")
rows = json.loads(subprocess.run(["node", str(CODE / "batch/colour_inventory.mjs"), slug, "0", "--json"], cwd=D, capture_output=True,
                                 text=True, timeout=300).stdout.strip().splitlines()[-1])
text = src.read_text()
have = {} if "--ignore-map" in sys.argv else json.loads(text).get("colorMap", {})  # --ignore-map: what the rule alone says
flowers = set()
for k, v in re.findall(r'"((?:colors|flowerColors?|petal[A-Za-z]*|bloomColors?))"\s*:\s*(\[[^\]]*\]|"#[0-9a-fA-F]{6}")', text):
    flowers |= {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}", v)}
structural = set()
for k, v in re.findall(r'"([A-Za-z]*(?:roof|wall|glass|frame|plinth|trim|rail|line|joint|sign|base|rim|kerb|stone|timber|wood|metal|text|seam|edge|cap|door|window|shutter|floor|ceiling|beam|column|post)[A-Za-z]*)"\s*:\s*(\[[^\]]*\]|"#[0-9a-fA-F]{6}")', text, re.I):
    structural |= {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}", v)}
VEG = re.compile(r"lawn|bed|grove|tree|shrub|hedge|topiary|planting|field|terrain|ground|flower|arch|meadow|forest|grass|valley|moss|ivy")


def hsv(h):
    return colorsys.rgb_to_hsv(*(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def hexs(h, s, v):
    return "#%02x%02x%02x" % tuple(round(x * 255) for x in colorsys.hsv_to_rgb(h, s, v))


out = {}
for r in rows:
    k = r["key"]
    if k in have or k in out or k == "#ffffff":
        continue
    h, s, v = hsv(k)
    green = .15 <= h <= .45 and .10 <= s <= .38 and v > .3  # paler = foam, mist, pale stone
    veg = r["inst"] or any(VEG.search(t.split("_", 1)[-1]) for t in r["types"])  # "type:id", kit prefix dropped
    if k in structural:
        continue
    if k in flowers and s < .12:  # near-white blooms (white hydrangea, daisies) stay white
        continue
    if green and (veg or k in flowers) and not r["vtx"]:  # leaves, also leaf colours inside flower lists
        cap = .38 if r["share"] >= 3 else .62  # big lawns/slopes stay at the approved lawn chroma (Cam Ly #7d8656)
        out[k] = hexs(h, max(s, min(cap, max(.30, s * 2.7))) if s < cap else s, v * .65)
    elif k in flowers:
        out[k] = hexs(h, min(.62, max(.38, s * 3.2)), min(1, v * .97))
print(json.dumps(out))
if "--apply" in sys.argv and out:
    subprocess.run([sys.executable, str(CODE / "batch/set_colormap.py"), slug, json.dumps(out)], cwd=D, check=True)
