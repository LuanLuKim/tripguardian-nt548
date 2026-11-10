"""colour_by_model.py <slug> [--model gemma|lan|uit|sol] [--rounds 2] [--effort low|medium] [--no-auto]
Photo recolour of one built place with a vision model as a function (no agent, no sandbox). The script owns every action:
  1. batch/auto_colormap.py --apply (greens, flowers by rule)
  2. build + bridge/shot.py -> review sheet (overview, orbit, up to 3 stops incl. an interior)
  3. model sees contact.jpg + review sheet + the colour table (key, area, objects, current colour) and returns the PHOTO
     colour of each surface that is wrong: {"#key": {"photo": "#hex", "photos": "g03,g05", "why": "..."}}
  4. script converts photo -> input colour (batch/eyedrop.py precomp: undo the viewer's display grade), set_colormap
  5. repeat 2-4 until the model returns {} or rounds run out
Coordinator (Opus) looks only at the final sheet printed at the end. Log: places/<slug>/colour_model_log.json."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA, REPO

import json
import subprocess

from PIL import Image, ImageDraw

D = DATA
sys.path.insert(0, str(CODE / "batch"))
from ask_model import ask  # noqa: E402
from eyedrop import precomp  # noqa: E402

args = sys.argv[1:]
slug = args[0]
opt = lambda f, d: args[args.index(f) + 1] if f in args else d  # noqa: E731
model, rounds, effort = opt("--model", "sol"), int(opt("--rounds", "2")), opt("--effort", "low")
src = D / ("linhson.json" if slug == "linhson" else f"places/{slug}/place.json")
contact = D / ("photo-contact.png" if slug == "linhson" else f"places/{slug}/contact.jpg")
PLINTH = {"#c4bbae", "#efe5d3"}  # cream model base: stays (owner: scale-model look)
PY = str(REPO / ".venv/bin/python")


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=D, capture_output=True, text=True, **kw)


def shoot(tag):
    run(["python3", str(CODE / "build.py"), str(src.relative_to(D)), f"out_{slug}/"], check=True)
    import shutil
    shutil.rmtree(D / "bridge/out" / tag, ignore_errors=True)  # a stale DONE from an earlier run would end the wait at once
    out = run([PY, str(CODE / "bridge/shot.py"), tag, "--out", f"out_{slug}"], timeout=1800)
    pngs = sorted((D / "bridge/out" / tag).glob("*.png"))
    base = [p for p in pngs if "initial" in p.name or "orbit_125" in p.name]
    hs = [p for p in pngs if "_hs_" in p.name]
    inside = [p for p in hs if any(w in p.name for w in ("inside", "trong", "interior", "noi-that"))]
    pick = base + [p for p in hs if p not in inside][:3 - min(1, len(inside))] + inside[:1]
    W, H = 640, 360
    sheet = Image.new("RGB", (W * 2, H * ((len(pick) + 1) // 2)), "white")
    for i, p in enumerate(pick):
        sheet.paste(Image.open(p).convert("RGB").resize((W - 4, H - 4)), ((i % 2) * W + 2, (i // 2) * H + 2))
        ImageDraw.Draw(sheet).text(((i % 2) * W + 8, (i // 2) * H + H - 20), p.stem, fill="black")
    path = D / f"out_{slug}" / f"review_{tag}.jpg"
    sheet.save(path, quality=84)
    return path, out.stdout.strip().splitlines()[-1:] if out.stdout else []


def table():
    rows = json.loads(run(["node", str(CODE / "batch/colour_inventory.mjs"), slug, "0", "--json"], timeout=600).stdout.strip().splitlines()[-1])
    cmap = json.loads(src.read_text()).get("colorMap", {})
    agg = {}
    for r in rows:
        a = agg.setdefault(r["key"], {"share": 0, "objs": set()})
        a["share"] += r["share"]
        a["objs"] |= {t.split(":")[-1] for t in r["types"]} | ({"(instances)"} if r["inst"] else set())
    keep = [(k, a) for k, a in agg.items() if k not in PLINTH and k != "#ffffff" and a["share"] >= .4]
    keep.sort(key=lambda kv: -kv[1]["share"])
    lines = [f"{k} | {a['share']:.1f}% | {', '.join(sorted(a['objs']))[:80] or '-'} | now {cmap.get(k, k)}" for k, a in keep[:40]]
    return "\n".join(lines), {k for k, _ in keep[:40]}


PROMPT = """You recolour an architectural scale model so its colours match the real place in the photos.
Image 1 = contact sheet of real photos (numbered gNN). Image 2 = current render of the model (overview, orbit, stops).
The cream base plinth stays cream. Keep the clean scale-model look; colours must be the real ones from the photos:
walls, roofs, trim, paving, water, rock, wood, awnings, interior surfaces (from interior photos only).
Colour table, one line per built colour: key | share of painted area | objects using it | colour shown now
{table}

Find every surface in image 2 whose colour clearly differs from the photos (wrong hue, too pale, too saturated, khaki/grey
stand-in). For each, give the key and the colour as eyedropped from a SUNLIT spot in a photo of THIS place (ignore
neighbouring buildings, people, sky). The script converts it for the renderer; do not pre-adjust.
Greens and flowers were already set by rule: change them only if clearly wrong.
Return ONLY JSON: {{"#key": {{"photo": "#rrggbb", "photos": "g03,g05", "why": "short"}}}}. Return {{}} if nothing is clearly wrong."""

import time as _t
run_id = _t.strftime("%H%M")
log = {"slug": slug, "model": model, "rounds": []}
if "--no-auto" not in args:
    run(["python3", str(CODE / "batch/auto_colormap.py"), slug, "--apply"], timeout=900)
for r in range(1, rounds + 2):
    tag = f"cbm{run_id}{r}{slug}"
    sheet, console = shoot(tag)
    if r > rounds:
        break
    tab, keys = table()
    fixes, usage = ask(PROMPT.format(table=tab), [contact, sheet], model=model, effort=effort)
    fixes = {k.lower(): v for k, v in (fixes or {}).items() if k.lower() in keys and isinstance(v, dict) and str(v.get("photo", "")).startswith("#")}
    log["rounds"].append({"tag": tag, "usage": usage, "fixes": fixes, "console": console})
    print(f"round {r}: {len(fixes)} fixes, {usage.get('total_tokens', usage.get('prompt_tokens'))} tokens, {usage['seconds']}s")
    for k, v in fixes.items():
        print(f"  {k} -> photo {v['photo']} ({v.get('photos', '')}): {v.get('why', '')[:90]}")
    if not fixes:
        break
    cm = {k: precomp(tuple(int(v["photo"][i:i + 2], 16) for i in (1, 3, 5))) for k, v in fixes.items()}
    run(["python3", str(CODE / "batch/set_colormap.py"), slug, json.dumps(cm)], check=True)
(src.parent if slug != "linhson" else D / "checks_linhson").joinpath("colour_model_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))
print("final sheet:", sheet)
