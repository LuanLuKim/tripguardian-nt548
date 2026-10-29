"""RestrictedArea: military land and no-access areas inside a city's bounding box, from OpenStreetMap via Overpass.

Output is a GeoJSON FeatureCollection (data/<city>/views/restricted.geojson). It lists what OSM tags as restricted; an
area OSM does not know is simply absent, so "no area here" never means "open to visit".
"""

from .common import ViewError, city_area, config, fetch_json, now, read_json, views_dir, write_json

NOT_AREA = ("highway", "barrier")   # closed ways with these tags are lines that loop (roundabouts, fences), not areas
OSM_TAGS = ("name", "landuse", "military", "access", "operator", "description")


def path(city: str):
    return views_dir(city) / "restricted.geojson"


def query(area: list[float], timeout_s: int) -> str:
    box = ",".join(str(x) for x in area)   # south, west, north, east = [lat_min, lng_min, lat_max, lng_max]
    sel = ['["landuse"="military"]', '["military"]', '["access"="no"]["building"!~"."]["highway"!~"."]']
    body = "".join(f"{kind}{s}({box});" for s in sel for kind in ("way", "relation"))
    return f"[out:json][timeout:{timeout_s}];({body});out geom tags;"


def chain(segments: list[list[tuple]]) -> tuple[list[list[tuple]], int]:
    """Join open ways end to end into closed rings. (rings, number of segments that never closed)."""
    todo, rings, dropped = [list(s) for s in segments if len(s) >= 2], [], 0
    while todo:
        ring = todo.pop()
        grew = True
        while grew and ring[0] != ring[-1]:
            grew = False
            for i, s in enumerate(todo):
                if s[0] == ring[-1]:
                    ring += s[1:]
                elif s[-1] == ring[-1]:
                    ring += s[::-1][1:]
                elif s[-1] == ring[0]:
                    ring = s[:-1] + ring
                elif s[0] == ring[0]:
                    ring = s[::-1][:-1] + ring
                else:
                    continue
                todo.pop(i)
                grew = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            rings.append(ring)
        else:
            dropped += 1
    return rings, dropped


def _pts(geometry) -> list[tuple]:
    return [(round(p["lon"], 7), round(p["lat"], 7)) for p in geometry or []]


def feature(el: dict) -> dict | None:
    """One Overpass element -> GeoJSON Feature, or None when it is not an area."""
    tags = el.get("tags") or {}
    if any(k in tags for k in NOT_AREA) and "military" not in tags and tags.get("landuse") != "military":
        return None
    if el["type"] == "way":
        outer, inner = chain([_pts(el.get("geometry"))]), ([], 0)
    else:
        members = [m for m in el.get("members") or [] if m.get("type") == "way" and m.get("geometry")]
        outer = chain([_pts(m["geometry"]) for m in members if m.get("role") in ("outer", "")])
        inner = chain([_pts(m["geometry"]) for m in members if m.get("role") == "inner"])
    if not outer[0]:
        return None
    holes = inner[0]
    polys = [[o] + [h for h in holes if inside(h[0][1], h[0][0], [o])] for o in outer[0]]
    geometry = ({"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1
                else {"type": "MultiPolygon", "coordinates": polys})
    kind = "military" if tags.get("landuse") == "military" or "military" in tags else "no_access"
    props = {"osm": f"{el['type']}/{el['id']}", "kind": kind, **{k: tags[k] for k in OSM_TAGS if k in tags}}
    flat = [p for poly in polys for ring in poly[:1] for p in ring]
    box = [min(p[0] for p in flat), min(p[1] for p in flat), max(p[0] for p in flat), max(p[1] for p in flat)]
    return {"type": "Feature", "bbox": box, "properties": props, "geometry": geometry}


def _ring_has(ring: list, lat: float, lng: float) -> bool:
    inside_ = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > lat) != (y2 > lat) and lng < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside_ = not inside_
    return inside_


def inside(lat: float, lng: float, polygon: list) -> bool:
    """Inside a GeoJSON polygon's coordinates: in the outer ring and in none of the holes."""
    return _ring_has(polygon[0], lat, lng) and not any(_ring_has(h, lat, lng) for h in polygon[1:])


def hits(lat: float, lng: float, areas: list[dict]) -> list[dict]:
    """Properties of every RestrictedArea feature that contains the point."""
    out = []
    for f in areas:
        box = f.get("bbox")   # [lng_min, lat_min, lng_max, lat_max]: most places are nowhere near an area
        if box and not (box[0] <= lng <= box[2] and box[1] <= lat <= box[3]):
            continue
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        if any(inside(lat, lng, p) for p in polys):
            out.append(f["properties"])
    return out


def build(city: str) -> dict:
    """Ask Overpass once, keep the areas, write data/<city>/views/restricted.geojson (raw answer under raw/)."""
    cfg = config()["restricted"]
    area = city_area(city)
    raw_path = views_dir(city) / "raw" / "restricted_overpass.json"
    doc = read_json(raw_path)
    if doc is None:
        doc = fetch_json(cfg["url"], data={"data": query(area, int(cfg["timeout_s"]))}, timeout_s=cfg["timeout_s"] + 30)
        if "elements" not in doc:   # Overpass answers 200 with a "remark" when it times out; never cache that
            raise ViewError("Overpass answer has no elements")
        write_json(raw_path, doc)
    feats = [f for el in doc["elements"] if (f := feature(el))]
    out = {"type": "FeatureCollection", "city": city, "source": "openstreetmap-overpass", "bbox": area,
           "built_at": now(), "features": feats}
    write_json(path(city), out)
    return out


def load(city: str) -> list[dict] | None:
    """The features of the built view, or None when it was never built."""
    doc = read_json(path(city))
    return None if doc is None else doc["features"]
