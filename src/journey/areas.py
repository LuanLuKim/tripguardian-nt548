"""Which old province (or priced-apart sub-area) a point is in, and which airport it is at (config/provinces.yaml,
config/provinces.geojson; docs/BOOKING.md §Gọi xe). Ride brands price by the 63 provinces before the 2025 merger, so this
is the area a ride's pickup is priced in."""

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .tariffs.common import Provinces, provinces

SHAPES = Path(__file__).resolve().parents[2] / "config" / "provinces.geojson"
_KM_PER_DEG = 111.32


@dataclass(frozen=True)
class _Shape:
    key: str
    box: tuple          # lng_min, lat_min, lng_max, lat_max
    polygons: list      # [[outer ring, hole, …]], rings as [[lng, lat]]


@cache
def _shapes(path: Path = SHAPES) -> tuple[_Shape, ...]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in doc["features"]:
        polys = f["geometry"]["coordinates"]
        xs = [p[0] for poly in polys for p in poly[0]]
        ys = [p[1] for poly in polys for p in poly[0]]
        out.append(_Shape(f["properties"]["key"], (min(xs), min(ys), max(xs), max(ys)), polys))
    return tuple(out)


def _inside(lng: float, lat: float, ring: list) -> bool:
    hit = False
    j = len(ring) - 1
    for i in range(len(ring)):
        (xi, yi), (xj, yj) = ring[i], ring[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def _in_shape(lng: float, lat: float, s: _Shape) -> bool:
    x0, y0, x1, y1 = s.box
    if not (x0 <= lng <= x1 and y0 <= lat <= y1):
        return False
    return any(_inside(lng, lat, poly[0]) and not any(_inside(lng, lat, h) for h in poly[1:]) for poly in s.polygons)


def _edge_km(lng: float, lat: float, s: _Shape) -> float:
    """Distance from the point to the shape's outline, on a plane scaled at the point's latitude."""
    kx, ky = _KM_PER_DEG * math.cos(math.radians(lat)), _KM_PER_DEG
    best = math.inf
    for poly in s.polygons:
        ring = poly[0]
        for (ax, ay), (bx, by) in zip(ring, ring[1:]):
            ax, ay, bx, by = (ax - lng) * kx, (ay - lat) * ky, (bx - lng) * kx, (by - lat) * ky
            dx, dy = bx - ax, by - ay
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def province_of(lat: float, lng: float, prov: Provinces | None = None) -> str | None:
    """The old province the point is in; one within `snap_km` of a coast (the simplified outline misses beach-front
    hotels) belongs to the nearest; None outside Vietnam."""
    prov = prov or provinces()
    shapes = _shapes()
    for s in shapes:
        if _in_shape(lng, lat, s):
            return s.key
    pad = prov.snap_km / _KM_PER_DEG * 1.5
    near = [(d, s.key) for s in shapes if s.box[0] - pad <= lng <= s.box[2] + pad and s.box[1] - pad <= lat <= s.box[3] + pad
            for d in [_edge_km(lng, lat, s)] if d <= prov.snap_km]
    return min(near)[1] if near else None


def area_of(lat: float, lng: float, prov: Provinces | None = None) -> str | None:
    """The priced area of a point: an airport's own area at an airport; a sub-area (Phú Quốc, Sa Pa, Hội An) when the
    point is in its box and its parent province; else the old province."""
    prov = prov or provinces()
    if code := airport_at(lat, lng, prov):
        return prov.airports[code]["area"]
    key = province_of(lat, lng, prov)
    for sub, row in prov.subareas.items():
        lat0, lng0, lat1, lng1 = row["box"]
        if row["parent"] == key and lat0 <= lat <= lat1 and lng0 <= lng <= lng1:
            return sub
    return key


def parent_of(area: str | None, prov: Provinces | None = None) -> str | None:
    """A sub-area's province; an old province is its own parent."""
    prov = prov or provinces()
    return prov.subareas[area]["parent"] if area in prov.subareas else area


def name_of(area: str | None, prov: Provinces | None = None) -> str | None:
    prov = prov or provinces()
    row = prov.subareas.get(area or "") or prov.areas.get(area or "")
    return row["name"] if row else None


def airport_at(lat: float, lng: float, prov: Provinces | None = None) -> str | None:
    """The IATA code of the airport the point is within `airport_km` of; None away from every airport."""
    prov = prov or provinces()
    kx = _KM_PER_DEG * math.cos(math.radians(lat))
    near = [(math.hypot((a["lng"] - lng) * kx, (a["lat"] - lat) * _KM_PER_DEG), code) for code, a in prov.airports.items()]
    near = [x for x in near if x[0] <= prov.airport_km]
    return min(near)[1] if near else None
