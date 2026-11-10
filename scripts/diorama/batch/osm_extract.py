"""Cut the Da Lat box out of a Geofabrik .osm.pbf once, then attach local footprints to every 3D-eligible place.

Usage: python osm_extract.py <vietnam.osm.pbf>
Writes batch/osm_dalat.json (all kept ways, lat/lng) and batch/footprints/<fid>.json per place in inventory.json:
{"origin": {lat, lng}, "main": osm id or null, "main_how": "contains" | "nearest" | null, "buildings": [...],
 "ways": [...]} in metres (x = east, y = north) around the place's main building centroid (or its Maps point)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA

import json
import math

import osmium

D = DATA / "batch"
BOX = (11.83, 108.36, 12.02, 108.53)  # lat_min, lng_min, lat_max, lng_max (city + Tuyen Lam + Prenn)
KEYS = ("building", "highway", "leisure", "landuse", "natural", "amenity", "tourism", "historic")
RADIUS = 140  # metres of context kept around a place
NEAREST_MAX = 45  # a building farther than this from the Maps point is not taken as the place's main building


class Ways(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.out = []

    def way(self, w):
        tags = {t.k: t.v for t in w.tags}
        if not any(k in tags for k in KEYS):
            return
        try:
            pts = [(n.lat, n.lon) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if not any(BOX[0] <= a <= BOX[2] and BOX[1] <= b <= BOX[3] for a, b in pts):
            return
        keep = {k: v for k, v in tags.items() if k in KEYS or k in ("name", "building:levels", "roof:shape", "height")}
        self.out.append({"id": w.id, "tags": keep, "pts": [[round(a, 7), round(b, 7)] for a, b in pts]})


def metres(origin):
    lat0, lng0 = origin
    kx = 111320 * math.cos(math.radians(lat0))
    return lambda p: ((p[1] - lng0) * kx, (p[0] - lat0) * 110540)


def inside(pt, poly):
    x, y, hit = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def main():
    cache = D / "osm_dalat.json"
    if cache.exists():
        ways = json.loads(cache.read_text())
    else:
        h = Ways()
        h.apply_file(sys.argv[1], locations=True)
        ways = h.out
        cache.write_text(json.dumps(ways, ensure_ascii=False, separators=(",", ":")))
    print("ways in box", len(ways))
    buildings = [w for w in ways if "building" in w["tags"] and len(w["pts"]) >= 4]
    inv = json.loads((D / "inventory.json").read_text())
    out_dir = D / "footprints"
    out_dir.mkdir(exist_ok=True)
    stats = {"contains": 0, "nearest": 0, "none": 0}
    for place in inv:
        to_m = metres((place["lat"], place["lng"]))
        main, how, best = None, None, NEAREST_MAX
        for b in buildings:
            poly = [to_m(p) for p in b["pts"]]
            if max(abs(c) for q in poly for c in q) > 400:
                continue
            if inside((0.0, 0.0), poly):
                main, how = b, "contains"
                break
            cx, cy = sum(q[0] for q in poly) / len(poly), sum(q[1] for q in poly) / len(poly)
            if math.hypot(cx, cy) < best:
                main, how, best = b, "nearest", math.hypot(cx, cy)
        stats[how or "none"] += 1
        origin = (place["lat"], place["lng"])
        if main:
            origin = (sum(p[0] for p in main["pts"]) / len(main["pts"]), sum(p[1] for p in main["pts"]) / len(main["pts"]))
        to_m = metres(origin)
        near = []
        for w in ways:
            poly = [to_m(p) for p in w["pts"]]
            if min(math.hypot(*q) for q in poly) <= RADIUS:
                near.append({"osm_id": w["id"], "tags": w["tags"], "poly_m": [[round(a, 1), round(b, 1)] for a, b in poly]})
        doc = {"place": place["name"], "origin": {"lat": origin[0], "lng": origin[1]}, "note": "x=east, y=north metres",
               "main": main["id"] if main else None, "main_how": how,
               "buildings": [w for w in near if "building" in w["tags"]],
               "ways": [w for w in near if "building" not in w["tags"]]}
        (out_dir / f"{place['fid']}.json").write_text(json.dumps(doc, ensure_ascii=False))
        place["osm_main"], place["osm_how"], place["osm_buildings"] = doc["main"], how, len(doc["buildings"])
    (D / "inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1))
    print("main footprint", stats)


if __name__ == "__main__":
    main()
