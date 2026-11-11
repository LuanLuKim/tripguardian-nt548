"""Frames of the walking tour, shot on the GPU when headless Chromium reaches one (needs the static server on :8471).
Usage: .venv/bin/python scripts/diorama/checks/walkshots.py <slug> <from>:<to>:<q1,q2,..> [...] [--out DIR]
Stops are 0-based as in window.__walk(from, to, q); each frame is the move frozen at fraction q. Builds the place with
the current template into out_wt<slug>/, prints the camera position per frame and writes one labelled contact sheet."""
import re, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA, REPO
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

EXE = next(p for p in (REPO.parent / "tripguardian-store/cache", REPO / ".cache") if (p / "ms-playwright").exists()) \
    / "ms-playwright/chromium-1169/chrome-linux/chrome"
GPU = ["--use-gl=angle", "--use-angle=gl-egl", "--enable-gpu", "--ignore-gpu-blocklist", "--no-sandbox"]

args = sys.argv[1:]
out_dir = Path(args.pop(args.index("--out") + 1)) if "--out" in args else DATA / "walkshots"
if "--out" in args:
    args.remove("--out")
slug, specs = args[0], args[1:]
source = DATA / "places" / slug / "place.json"
if not source.exists():
    source = DATA / f"{slug}.json"  # linhson.json lives at the root
built, local = DATA / f"out_wt{slug}", DATA / f"out_local_wt{slug}"
subprocess.run([sys.executable, str(CODE / "build.py"), str(source), str(built)], check=True, stdout=subprocess.DEVNULL)
shutil.rmtree(local, ignore_errors=True)
shutil.copytree(built, local)
(local / "vendor").symlink_to(CODE / "vendor", target_is_directory=True)
html = (local / "index.html").read_text().replace("https://cdn.jsdelivr.net/npm/three@0.170.0/", "./vendor/node_modules/three/")
(local / "index.html").write_text(re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>', "", html))
out_dir.mkdir(parents=True, exist_ok=True)
shots, problems = [], []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=str(EXE), args=GPU)
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.goto(f"http://127.0.0.1:8471/{local.name}/index.html?t={time.time()}")
    page.wait_for_function("window.__ready === true", timeout=180000)
    time.sleep(1.5)
    for spec in specs:
        a, b, qs = spec.split(":")
        for q in qs.split(","):
            info = page.evaluate(f"window.__walk({a},{b},{q})")
            time.sleep(.8)
            camera = page.evaluate("window.__inspect().cameraPosition")
            name = f"{a}-{b}@{q}"
            path = out_dir / f"{slug}_{name}.png"
            page.screenshot(path=str(path))
            shots.append((name, path))
            print(name, "walk" if info and info.get("walk") else "flight", [round(v, 1) for v in camera])
    browser.close()
shutil.rmtree(local, ignore_errors=True)
W, H, C = 480, 270, 4
sheet = Image.new("RGB", (W * C, (H + 20) * ((len(shots) + C - 1) // C)), "white")
draw = ImageDraw.Draw(sheet)
for k, (name, path) in enumerate(shots):
    x, y = (k % C) * W, (k // C) * (H + 20)
    sheet.paste(Image.open(path).convert("RGB").resize((W - 4, H - 4)), (x + 2, y + 2))
    draw.text((x + 4, y + H), name, fill="black", font=ImageFont.load_default(size=14))
sheet_path = out_dir / f"sheet_{slug}.jpg"
sheet.save(sheet_path, quality=80)
print(sheet_path)
for line in problems:
    print(line)
sys.exit(1 if problems else 0)
