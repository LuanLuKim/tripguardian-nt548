"""write_colour_notes.py <tag> <slug>... : after a colorMap pass, write places/<slug>/COLOURS.md (old -> new, which objects,
rule or photo) and record the pass in summary.json (colour_pass, colour_rounds). Run from scripts/diorama."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA

import json
import subprocess
from datetime import date

D = DATA
tag, slugs = sys.argv[1], sys.argv[2:]
for slug in slugs:
    src = D / ("linhson.json" if slug == "linhson" else f"places/{slug}/place.json")
    cmap = json.loads(src.read_text()).get("colorMap", {})
    rows = json.loads(subprocess.run(["node", str(CODE / "batch/colour_inventory.mjs"), slug, "0", "--json"], cwd=D, capture_output=True,
                                     text=True, timeout=300).stdout.strip().splitlines()[-1])
    use = {}
    for r in rows:
        u = use.setdefault(r["key"], {"share": 0, "types": set()})
        u["share"] += r["share"]
        u["types"] |= {t.split(":")[-1] for t in r["types"]} or ({"instances"} if r["inst"] else set())
    auto = json.loads(subprocess.run([sys.executable, str(CODE / "batch/auto_colormap.py"), slug, "--ignore-map"], cwd=D, capture_output=True, text=True,
                                     timeout=300).stdout.strip().splitlines()[-1] or "{}")
    lines = [f"# Màu {json.loads(src.read_text())['name']}", "",
             f"Lượt `{tag}` ({date.today().isoformat()}): `colorMap` trong place file, áp sau khi dựng (`index.template.html` applyColorMap).",
             "Nguồn: `quy tắc` = batch/auto_colormap.py (cây cỏ, hoa); `ảnh` = lấy mẫu ảnh + bù grade (batch/eyedrop.py) hoặc chỉnh theo ảnh sau khi xem render.", "",
             "| Cũ | Mới | Diện tích | Đồ vật | Nguồn |", "|---|---|---|---|---|"]
    for k, v in sorted(cmap.items(), key=lambda kv: -use.get(kv[0], {"share": 0})["share"]):
        u = use.get(k, {"share": 0, "types": set()})
        objs = ", ".join(sorted(u["types"]))[:70] or "—"
        lines.append(f"| `{k}` | `{v}` | {u['share']:.1f} % | {objs} | {'quy tắc' if auto.get(k) == v else 'ảnh'} |")
    out = (D / "checks_linhson" if slug == "linhson" else src.parent) / "COLOURS.md"
    out.write_text("\n".join(lines) + "\n")
    sp = src.parent / "summary.json" if slug != "linhson" else None
    if sp and sp.exists():
        s = json.loads(sp.read_text())
        s["colour_pass"] = tag
        s.setdefault("colour_rounds", []).append({"tag": tag, "method": "colorMap (rule + photo)", "keys": len(cmap)})
        sp.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n")
    print(slug, len(cmap), out.relative_to(D))
