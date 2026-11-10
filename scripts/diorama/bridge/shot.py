"""Agent side, token-lean: render the views, write ONE labelled contact sheet out_<slug>/sheet_<tag>.jpg, print its path and any real console error.
Usage: .venv/bin/python scripts/diorama/bridge/shot.py <tag> --out out_<slug> [--stops a,b]   (run after build.py)
Views: overview, 2 orbits, every stop (or only the stops named). The PNGs stay in bridge/out/<tag>/ for a closer look."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA

import json, sys, time
from PIL import Image, ImageDraw, ImageFont
B = DATA / "bridge"
args = sys.argv[1:]
tag = args[0]
outdir = args[args.index("--out") + 1].rstrip("/")
stops = args[args.index("--stops") + 1].split(",") if "--stops" in args else None
slug = outdir.removeprefix("out_")
pf = B.parent / "places" / slug / "place.json"
place = json.loads((pf if pf.exists() else B.parent / f"{slug}.json").read_text())  # linhson.json lives at the root
views = [{"initial": True}, {"orbit": [125, 50, None]}, {"orbit": [305, 45, None]}] if stops is None else []
views += [{"open": h["id"]} for h in place["hotspots"] if stops is None or h["id"] in stops]
out = B / "out" / tag
(B / "req").mkdir(parents=True, exist_ok=True)
(B / "req" / f"{tag}.json").write_text(json.dumps({"tag": tag, "views": views, "out": outdir, "size": [1280, 720]}))
t = time.time()
while not (out / "DONE").exists():
    if time.time() - t > 900:
        sys.exit("timeout: bridge did not answer")
    time.sleep(3)
pngs = sorted(out.glob("*.png"))
W, H, C = 520, 293, 3
sheet = Image.new("RGB", (W * C, (H + 22) * ((len(pngs) + C - 1) // C)), "white")
draw, font = ImageDraw.Draw(sheet), ImageFont.load_default(size=15)
for k, p in enumerate(pngs):
    im = Image.open(p).convert("RGB").resize((W - 4, H - 4))
    x, y = (k % C) * W, (k // C) * (H + 22)
    sheet.paste(im, (x + 2, y + 2))
    draw.text((x + 4, y + H), p.stem, fill="black", font=font)
sheet_path = B.parent / outdir / f"sheet_{tag}.jpg"  # bridge/out is outside the agents' sandbox
sheet_path.parent.mkdir(exist_ok=True)
sheet.save(sheet_path, quality=82)
print(sheet_path)
log = (out / "console.txt").read_text() if (out / "console.txt").exists() else (out / "error.txt").read_text()
bad = [l for l in log.splitlines() if ("error" in l.lower() or "NOT READY" in l or "failed" in l) and "favicon" not in l and "404" not in l]
print("\n".join(bad[:8]) or "console clean")
