"""Places still without a 3D model, by kit, most reviewed first (batch/inventory.json minus web/space3d/places.json and batch/skip.json).
Usage: python3 batch/next_places.py [kit] [n]   -> slug suggestion, fid, name, reviews, exterior/interior photo counts"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA, REPO

import json
import re
import unicodedata

D = DATA
done = {p["id"].replace(":", "_") for p in json.loads((REPO / "web/space3d/places.json").read_text())}
skip = json.loads((D / "batch/skip.json").read_text()) if (D / "batch/skip.json").exists() else {}
started = {json.loads(m.read_text())["fid"] for m in D.glob("places/*/meta.json")}
kit = sys.argv[1] if len(sys.argv) > 1 else None
n = int(sys.argv[2]) if len(sys.argv) > 2 else 20


def slug(name):
    ascii_ = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_.lower())[:14]


rows = [x for x in json.loads((D / "batch/inventory.json").read_text()) if x["fid"] not in done and x["fid"] not in skip and (kit is None or x.get("kit") == kit)]
rows.sort(key=lambda x: -(x.get("reviews") or 0))
for x in rows[:n]:
    mark = " (started: places/ exists)" if x["fid"] in started else ""
    print(f'{slug(x["name"]):14} {x["fid"]}  {x.get("kit")!s:10} {x.get("reviews")!s:>6}  ext={x["ext"]} int={x["int"]}  {x["name"]}{mark}')
print(f"-- {len(rows)} left" + (f" for kit {kit}" if kit else ""))
