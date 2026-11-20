"""config/provinces.geojson from geoBoundaries gbOpen VNM ADM1 (public domain, the 63 provinces before the 2025 merger
plus Côn Đảo): one feature per area key of config/provinces.yaml, names cleaned ("Hà Nội\\t", "Ho Chi Minh"),
coordinates rounded to 4 decimals (about 11 m). The download is untrusted input: every key must get exactly one shape."""

import json
from pathlib import Path

from .common import ROOT, area_key, provinces

SOURCE = ("https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/VNM/ADM1/"
          "geoBoundaries-VNM-ADM1.geojson")
OUT = ROOT / "config" / "provinces.geojson"
_ALIAS = {"ho chi minh": "ho_chi_minh"}  # the one name the source writes in English


def _ring(ring: list) -> list:
    out = []
    for x, y in ring:
        p = [round(float(x), 4), round(float(y), 4)]
        if not (102 <= p[0] <= 117.5 and 6 <= p[1] <= 23.5):  # Hoàng Sa and Trường Sa included
            raise ValueError(f"point outside Vietnam: {p}")
        if not out or out[-1] != p:
            out.append(p)
    if len(out) < 4:
        return []
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def _polygons(geom: dict) -> list:
    """Any Polygon / MultiPolygon as a list of polygons (each a list of rings, the outer one first)."""
    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        raise ValueError(f"unexpected geometry {geom['type']}")
    out = []
    for poly in polys:
        rings = [r for r in (_ring(r) for r in poly) if r]
        if rings:
            out.append(rings)
    return out


def build(src: Path, out: Path = OUT) -> dict:
    """Write the cleaned boundaries; returns {key: number of polygons}. ValueError (and nothing written) when a shape
    names no area, two shapes name one area, or an area has no shape."""
    prov = provinces()
    raw = json.loads(Path(src).read_text(encoding="utf-8"))
    feats, seen = [], {}
    for f in raw["features"]:
        name = " ".join(str(f["properties"].get("shapeName", "")).split())
        key = area_key(name, prov) or _ALIAS.get(name.casefold())
        if key is None or key not in prov.areas:
            raise ValueError(f"shape {name!r} names no area of config/provinces.yaml")
        if key in seen:
            raise ValueError(f"two shapes for {key}: {seen[key]!r} and {name!r}")
        seen[key] = name
        polys = _polygons(f["geometry"])
        if not polys:
            raise ValueError(f"{key}: no polygon left after rounding")
        feats.append({"type": "Feature", "properties": {"key": key, "name": prov.areas[key]["name"]},
                      "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    missing = sorted(set(prov.areas) - set(seen))
    if missing:
        raise ValueError(f"areas without a shape: {missing}")
    feats.sort(key=lambda f: f["properties"]["key"])
    doc = {"type": "FeatureCollection",
           "source": f"geoBoundaries gbOpen VNM ADM1 (public domain), {SOURCE}; rounded to 4 decimals",
           "features": feats}
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return {f["properties"]["key"]: len(f["geometry"]["coordinates"]) for f in feats}
