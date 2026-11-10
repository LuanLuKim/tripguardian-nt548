"""Render bridge (runs OUTSIDE the agent sandbox). Polls bridge/req/*.json; for each request converts out/ into a
local-vendor copy out_local/ and screenshots it, writing PNGs + console.txt into bridge/out/<tag>/ and DONE last.
Request JSON: {"tag": "v2a", "size": [1600, 900], "views": [{"orbit": [az, polar, dist_or_null]}, {"open": "id"},
{"initial": true}, {"pin_hover": "id"}], "out": "out"}  (empty views = default set: initial, 6 orbits, every hotspot).
"out" = build dir under diorama/ (default "out"); it is shot from out_local[_<suffix>]/ so places can run in parallel."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA, REPO

import json, os, re, shutil, sys, time, traceback
from playwright.sync_api import sync_playwright

D = DATA
# The store itself: other sessions sometimes remove or re-point the repo's .cache symlink.
EXE = str(next(p for p in (REPO.parent / "tripguardian-store/cache", REPO / ".cache")
               if (p / "ms-playwright").exists()) / "ms-playwright/chromium-1169/chrome-linux/chrome")
URL = "http://127.0.0.1:8471/{}/index.html"
DEFAULT_ORBITS = [[35, 55, None], [125, 50, None], [215, 60, None], [305, 45, None], [0, 30, None], [90, 70, None]]
# swiftshader renders on the CPU; with the machine at ~50 load one view of a 300-600k triangle scene can take > 30 s
# (Playwright's default), which failed whole places at `shoot`. Callers wait up to 15 min per request.
SHOT_TIMEOUT_MS = 90000


def local_name(src):
    if not re.fullmatch(r"out(_[\w-]+)?", src):
        raise ValueError(f"bad out dir: {src}")
    return "out_local" + src[3:]


def localize(src="out", tag=""):
    dst = D / (local_name(src) + (f"__{tag}" if tag else ""))
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(D / src, dst)
    (dst / "vendor").symlink_to(CODE / "vendor", target_is_directory=True)
    s = (dst / "index.html").read_text()
    s = s.replace("https://cdn.jsdelivr.net/npm/three@0.170.0/", "./vendor/node_modules/three/")
    s = re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>', "", s)
    (dst / "index.html").write_text(s)
    return dst.name


def shoot(req, out):
    W, H = req.get("size", [1600, 900])
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=EXE, args=["--use-gl=angle", "--use-angle=swiftshader",
                              "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"])
        pg = b.new_page(viewport={"width": W, "height": H})
        logs = []
        pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
        pg.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
        t = time.time()
        pg.goto(URL.format(req["_local"]) + f"?t={time.time()}", wait_until="load")
        try:
            pg.wait_for_function("window.__ready === true", timeout=180000)
            logs.append(f"ready in {time.time() - t:.1f}s")
        except Exception as e:
            logs.append(f"NOT READY: {e}")
            pg.screenshot(path=str(out / "not_ready.png"))
            (out / "console.txt").write_text("\n".join(logs)); b.close(); return
        views = req.get("views") or ([{"initial": True}] + [{"orbit": o} for o in DEFAULT_ORBITS] +
                                     [{"open": h} for h in pg.evaluate("window.__hotspots")])
        time.sleep(2)
        for i, v in enumerate(views):
            try:
                if "orbit" in v:
                    az, pol, dist = v["orbit"]
                    pg.evaluate(f"window.__close && window.__close(); window.__orbit({az},{pol},{json.dumps(dist)})")
                    name = f"{i:02d}_orbit_{az}_{pol}"
                elif "open" in v:
                    pg.evaluate(f"window.__open({json.dumps(v['open'])})"); name = f"{i:02d}_hs_{v['open']}"
                elif "pin_hover" in v:
                    pg.evaluate(f"window.__close && window.__close()")
                    el = pg.query_selector(f"[data-hotspot='{v['pin_hover']}']")
                    if el: el.hover()
                    name = f"{i:02d}_hover_{v['pin_hover']}"
                else:
                    pg.evaluate("window.__close && window.__close()"); name = f"{i:02d}_initial"
                time.sleep(v.get("wait", 3))
                pg.screenshot(path=str(out / f"{name}.png"), timeout=SHOT_TIMEOUT_MS)
            except Exception as e:
                logs.append(f"view {v} failed: {e}")
        (out / "console.txt").write_text("\n".join(logs))
        b.close()


(D / "bridge" / "req").mkdir(parents=True, exist_ok=True)
SOURCE_MTIME = Path(__file__).stat().st_mtime
while True:
    # Pick up an edited serve.py between requests (same pid, so stack.sh still owns the worker).
    if Path(__file__).stat().st_mtime != SOURCE_MTIME:
        print("serve.py changed, re-exec", flush=True)
        os.execv(sys.executable, [sys.executable, *sys.argv])
    for f in sorted((D / "bridge" / "req").glob("*.json")):
        # Several bridge processes may run: the one whose rename succeeds owns the request.
        claimed = f.with_name(f"{f.stem}.taken{os.getpid()}")
        try:
            req = json.loads(f.read_text()); tag = re.sub(r"[^\w.-]", "_", req.get("tag", f.stem))
            os.rename(f, claimed); f = claimed
        except Exception:
            time.sleep(1); continue
        out = D / "bridge" / "out" / tag
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        try:
            req["_local"] = localize(req.get("out", "out"), tag); shoot(req, out)
        except Exception:
            (out / "error.txt").write_text(traceback.format_exc())
        if req.get("_local"):
            shutil.rmtree(D / req["_local"], ignore_errors=True)
        try:  # the out dir may have been removed by a caller meanwhile; one bad request must never kill the worker
            out.mkdir(parents=True, exist_ok=True)
            (out / "DONE").write_text("1")
            f.unlink()
        except Exception:
            traceback.print_exc()
        print("done", tag, flush=True)
    time.sleep(2)
