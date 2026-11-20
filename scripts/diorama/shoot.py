"""Screenshot the diorama viewer: overview orbits + every hotspot opened. Full Chromium + swiftshader.
Usage: python shoot.py <url> <out_dir> [w h]
Writes orbit_*.png, hs_<id>.png, console.txt into out_dir."""
import json, sys, time
from paths import DATA, REPO
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], DATA / sys.argv[2]; out.mkdir(parents=True, exist_ok=True)
W, H = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1600, 900)
EXE = str(REPO / ".cache/ms-playwright/chromium-1169/chrome-linux/chrome")
ORBITS = [(35, 55, None), (125, 50, None), (215, 60, None), (305, 45, None), (0, 25, None), (90, 72, 55)]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                                     "--ignore-gpu-blocklist", "--no-sandbox"])
    pg = b.new_page(viewport={"width": W, "height": H})
    logs = []
    pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
    t = time.time()
    pg.goto(url, wait_until="load")
    try:
        pg.wait_for_function("window.__ready === true", timeout=240000)
    except Exception as e:  # still save what is on screen
        logs.append(f"not ready: {e}")
        pg.screenshot(path=str(out / "not_ready.png"))
        (out / "console.txt").write_text("\n".join(logs)); b.close(); sys.exit(1)
    logs.append(f"ready in {time.time() - t:.0f}s")
    time.sleep(3)
    pg.screenshot(path=str(out / "initial.png"))
    for i, (az, pol, dist) in enumerate(ORBITS):
        pg.evaluate(f"window.__orbit({az},{pol},{'null' if dist is None else dist})")
        time.sleep(4)
        pg.screenshot(path=str(out / f"orbit_{i}_{az}_{pol}.png"))
    ids = pg.evaluate("window.__hotspots")
    for hid in ids:
        pg.evaluate(f"window.__open({json.dumps(hid)})")
        time.sleep(4)
        pg.screenshot(path=str(out / f"hs_{hid}.png"))
        pg.evaluate("window.__close()")
    (out / "console.txt").write_text("\n".join(logs))
    print("\n".join(logs[-20:]))
    b.close()
