"""Deterministic, read-only footprint fitting for authored place JSON."""

from __future__ import annotations

from copy import deepcopy
import math


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _point(value, *, xyz: bool = False) -> tuple[float, float] | None:
    if isinstance(value, dict):
        x, z = value.get("x"), value.get("z")
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        x, z = value[0], value[2 if xyz and len(value) >= 3 else 1]
    else:
        return None
    return (x, z) if _number(x) and _number(z) else None


def _points(value, *, xyz: bool = False):
    point = _point(value, xyz=xyz)
    if point is not None:
        yield point
    elif isinstance(value, dict):
        for key in ("points", "paths", "legs", "start", "end"):
            yield from _points(value.get(key), xyz=xyz)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _points(item, xyz=xyz)


def _footprint(obj: dict, route: list) -> list[tuple[float, float]]:
    kind = obj.get("type", "")
    origin = _point(obj.get("position"), xyz=True) or _point(obj) or (0, 0)
    angle = obj.get("rotation", 0)
    angle = angle if _number(angle) else 0
    if not (kind == "villa" or kind.startswith(("villa_", "stay_"))):
        angle = math.radians(angle)
    c, s = math.cos(angle), math.sin(angle)
    local = []
    outline = list(_points(obj.get("outline")))
    size = obj.get("footprint", obj.get("size", obj.get("area")))
    width = obj.get("w", obj.get("width", 0))
    depth = obj.get("d", obj.get("depth", 0))
    if isinstance(size, (list, tuple)) and len(size) >= 2:
        width, depth = size[0], size[2] if len(size) >= 3 else size[1]
    width = abs(width) if _number(width) else 0
    depth = abs(depth) if _number(depth) else 0
    if outline:
        local.extend(outline)
    elif width or depth:
        local.extend((x * width / 2, z * depth / 2) for x in (-1, 1) for z in (-1, 1))
    # Garden points may contain height/yaw after x/z; nature/stay paths and
    # the pagoda dragon instead use x/y/z. Villa drives are already world-space.
    xyz = kind.startswith(("nature_", "stay_")) or kind in ("villa_drive", "pagoda_dragon")
    path_points = []
    for key in ("points", "paths", "path", "legs", "clusters", "positions", "trees", "benches", "lamps"):
        path_points.extend(_points(obj.get(key), xyz=xyz if key in ("points", "paths", "path", "legs") else False))
    if obj.get("followRoute"):
        path_points.extend(_points(route))
    radius = obj.get("radius", 0)
    radius = abs(radius) if _number(radius) else 0
    if path_points:
        if not outline and not depth:
            local.clear()  # A path's width is not a rectangle at the origin.
        padding = max(radius, width / 2 if not depth else 0)
        for x, z in path_points:
            local.extend((x + dx * padding, z + dz * padding) for dx in (-1, 1) for dz in (-1, 1))
    elif radius:
        local.extend((dx * radius, dz * radius) for dx in (-1, 1) for dz in (-1, 1))
    if not local:
        local = [(0, 0)]
    if kind == "villa_drive":
        return local
    return [(origin[0] + x * c + z * s, origin[1] - x * s + z * c) for x, z in local]


def fit_site(place: dict, margin_m: float = 6.0) -> tuple[dict, dict]:
    """Shrink oversized axes, preserving routes and non-site-sized ground.

    Site-sized ground is recognized only within 5% of both site dimensions
    and at the same centre. Explicit paths on such ground are protected by
    retaining its entire footprint; no route/surface association is guessed.
    Tight sites keep their authored centres. The input is never mutated.
    """
    if not _number(margin_m) or margin_m < 0:
        raise ValueError("margin_m must be finite and nonnegative")
    result = deepcopy(place)
    site = result.get("site", {})
    old = {key: site.get(key, 0) for key in ("width", "depth", "centerX", "centerZ")}
    report = {"old": old, "new": dict(old), "changed": False}
    if not all(_number(old[k]) for k in old) or min(old["width"], old["depth"]) <= 0:
        return result, report
    route = place.get("route", [])
    points = []
    ignored = []
    for obj in place.get("objects", []):
        footprint = _footprint(obj, route)
        xs, zs = zip(*footprint)
        ground = obj.get("type", "").endswith(("_ground", "_lawn", "_plinth"))
        whole_site = ground and all(
            abs(span / old[axis] - 1) <= .05 and abs(center - old[centre]) <= old[axis] * .025
            for span, center, axis, centre in (
                (max(xs) - min(xs), (max(xs) + min(xs)) / 2, "width", "centerX"),
                (max(zs) - min(zs), (max(zs) + min(zs)) / 2, "depth", "centerZ"),
            )
        )
        carries_paths = any(obj.get(key) for key in ("paths", "path", "legs", "points", "followRoute"))
        if whole_site and not carries_paths:
            ignored.append(obj.get("id"))
        else:
            points.extend(footprint)
    for hotspot in place.get("hotspots", []):
        points.extend(_points(hotspot.get("target"), xyz=True))
        points.extend(_points(hotspot.get("walk")))
    points.extend(_points(route))
    if not points:
        return result, report
    xs, zs = zip(*points)
    bounds = (min(xs), max(xs), min(zs), max(zs))
    new = dict(old)
    for axis, lo, hi in (("width", bounds[0], bounds[1]), ("depth", bounds[2], bounds[3])):
        desired = hi - lo + 2 * margin_m
        if desired > 0 and old[axis] > desired * 1.25:
            new[axis] = desired
    if new != old:
        new.update(centerX=(bounds[0] + bounds[1]) / 2, centerZ=(bounds[2] + bounds[3]) / 2)
        site.update(new)
    report.update(new=new, changed=new != old, bbox=list(bounds), ignored_ground=ignored)
    return result, report
