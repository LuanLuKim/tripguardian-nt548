"""Agent side: ask the render bridge for screenshots and wait.
Usage: python3 bridge/request.py <tag> [views.json] [--out OUTDIR]   (OUTDIR default "out", e.g. out_camly)
Run `python3 build.py <place>.json <OUTDIR>/` first. Prints the PNG paths when done (timeout 15 min)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA

import json, sys, time
D = DATA / "bridge"
args = sys.argv[1:]
outdir = "out"
if "--out" in args:
    i = args.index("--out"); outdir = args[i + 1].rstrip("/"); del args[i:i + 2]
tag = args[0]
views = json.loads((DATA / args[1]).read_text()) if len(args) > 1 else []
out = D / "out" / tag
(D / "req").mkdir(parents=True, exist_ok=True)
(D / "req" / f"{tag}.json").write_text(json.dumps({"tag": tag, "views": views, "out": outdir}))
t = time.time()
while not (out / "DONE").exists():
    if time.time() - t > 900:
        sys.exit("timeout: bridge did not answer")
    time.sleep(3)
for p in sorted(out.iterdir()):
    print(p)
print((out / "console.txt").read_text() if (out / "console.txt").exists() else (out / "error.txt").read_text())
