"""Ride-hailing fares (Grab, Be, Xanh SM) for one road leg, estimated from each brand's published tariff
(config/rides_tariffs.json, built by `python -m journey.tariffs`; docs/BOOKING.md §Gọi xe). No brand has a public price
API, so every number is an estimate without surge or promotion; an area a brand publishes no table for gives that brand
no price, never a borrowed one.

A leg is priced where it starts: the old province (or sub-area) of the pickup point (journey.areas). A sub-area a brand
has no row for falls back to the brand's row for its province. On top of the per-km fare: a fixed route when the leg
runs between its ends, the platform fee, and the airport pickup fee where the brand charges one."""

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import areas

PATH = Path(__file__).resolve().parents[2] / "config" / "rides_tariffs.json"
MAX_LEGS = 200
ROUND_VND = 1000          # a quote is shown to the thousand, rounded up
ROUTE_SLACK = 1.15        # a fixed price with no per-km rate covers a leg up to its km × this (the brand's own km)
VN = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class Table:
    version: int
    brands: dict
    built_at: str | None = None


_loaded: dict = {}


def load(path: Path = PATH) -> Table:
    """The table, read again whenever the file changes (prod reads config/ live)."""
    mtime = path.stat().st_mtime
    hit = _loaded.get(path)
    if hit is None or hit[0] != mtime:
        raw = json.loads(path.read_text(encoding="utf-8"))
        hit = (mtime, Table(version=raw["version"], brands=raw["brands"], built_at=raw.get("built_at")))
        _loaded[path] = hit
    return hit[1]


def fare(km: float, minutes: int | None, t: dict) -> float:
    """The published formula: the opening price covers open_km; each further km at its tier's rate (tiers by absolute
    km); the time charge, where stated, on the minutes after the opening km (in proportion to the distance)."""
    total, done = float(t["open"]), float(t["open_km"])
    for upto, rate in t["per_km"]:
        end = km if upto is None else min(km, float(upto))
        if end > done:
            total += (end - done) * rate
            done = end
    if t.get("per_min") and minutes and km > t["open_km"]:
        total += minutes * (km - t["open_km"]) / km * t["per_min"]
    return total


def _round(v: float) -> int:
    return int(math.ceil(v / ROUND_VND) * ROUND_VND)


def _fees(base: float, vehicle: str, brand: dict, day: date) -> tuple[float, float]:
    """The platform fee range a brand adds per ride (Grab: a fixed range until its end date, then a share of the fare)."""
    fee = brand.get("platform_fee")
    if not fee:
        return 0.0, 0.0
    if day <= date.fromisoformat(fee["until"]):
        lo, hi = fee["motorbike" if vehicle == "motorbike" else "car"]
        return float(lo), float(hi)
    pct = fee.get("after_pct") or 0
    return base * pct / 100, base * pct / 100


def _pickup_fee(vehicle: str, airport: str | None, brand: dict, t: dict) -> int:
    """What a car picked up at an airport pays on top: the service's own fee (Be) or the brand's (Grab)."""
    if airport is None or vehicle != "car":
        return 0
    return int((t.get("pickup") or {}).get(airport) or (brand.get("airport_pickup") or {}).get(airport) or 0)


@dataclass(frozen=True)
class Place:
    area: str | None
    parent: str | None
    airport: str | None


def place(lat: float, lng: float) -> Place:
    a = areas.area_of(lat, lng)
    return Place(a, areas.parent_of(a), areas.airport_at(lat, lng))


def _at(end: dict, p: Place) -> bool:
    if "airport" in end:
        return p.airport == end["airport"]
    return end.get("area") in (p.area, p.parent)


def _route_price(r: dict, km: float, minutes: int | None) -> float | None:
    if "fare" in r:  # beAirport: a per-km price of its own
        return fare(km, minutes, r["fare"])
    if r.get("per_km"):
        return r["price"] + max(0.0, km - r["min_km"]) * r["per_km"]
    return float(r["price"]) if km <= r["min_km"] * ROUTE_SLACK else None


def _routes(brand: dict, km: float, minutes: int | None, a: Place, b: Place | None) -> list[tuple[int, dict, float]]:
    """(index, route, price) for every fixed route of the brand the leg runs on: from one of its `from` areas to its
    `to`, or back when it runs both ways. A leg with no drop-off point runs on no route."""
    if b is None:
        return []
    out = []
    for i, r in enumerate(brand.get("routes") or []):
        forward = any(_at({"area": x}, a) for x in r["from"]) and _at(r["to"], b)
        back = r.get("both_ways") and _at(r["to"], a) and any(_at({"area": x}, b) for x in r["from"])
        if forward or back:
            price = _route_price(r, km, minutes)
            if price is not None:
                out.append((i, r, price))
    return out


def quote(km: float, minutes: int | None, a: Place, b: Place | None = None, day: date | None = None,
          table: Table | None = None) -> list[dict]:
    """One row per brand service priced where the leg starts ({brand, service, label, vehicle, seats, vnd_min,
    vnd_max}), one per fixed route the leg runs on (service "<id>@route<n>", route True), and one per brand with no
    table there (service None, vnd_min None, reason "no_table")."""
    table = table or load()
    day = day or datetime.now(VN).date()
    out = []
    for key, brand in table.brands.items():
        fares = brand["fares"].get(a.area or "") or brand["fares"].get(a.parent or "") or {}
        priced = []  # (service id, label, service, its per-km table (for the pickup fee), base price)
        for sid, t in fares.items():
            s = brand["services"][sid]
            priced.append((sid, s["label"], s, t, fare(km, minutes, t)))
        for i, r, price in _routes(brand, km, minutes, a, b):
            s = brand["services"][r["service"]]
            priced.append((f"{r['service']}@route{i}", r["label"], s, fares.get(r["service"]) or {}, price))
        if not priced:
            out.append({"brand": key, "service": None, "label": brand["name"], "vehicle": None, "seats": None,
                        "vnd_min": None, "vnd_max": None, "reason": "no_table"})
            continue
        for sid, label, s, t, base in priced:
            lo, hi = _fees(base, s["vehicle"], brand, day)
            extra = _pickup_fee(s["vehicle"], a.airport, brand, t)
            row = {"brand": key, "service": sid, "label": label, "vehicle": s["vehicle"], "seats": s["seats"],
                   "vnd_min": _round(base + lo + extra), "vnd_max": _round(base + hi + extra)}
            if "@" in sid:
                row["route"] = True
            out.append(row)
    return out


Leg = tuple  # (km, minutes, lat, lng, drop lat or None, drop lng or None)


def parse_legs(raw: str) -> list[Leg]:
    """`km:minutes:lat:lng[:lat2:lng2];…` from a query string (untrusted): ValueError on anything malformed or out of
    range. lat2, lng2 is where the leg ends (a fixed route needs both ends)."""
    legs = []
    for part in (p for p in (raw or "").split(";") if p):
        bits = part.split(":")
        if len(bits) not in (4, 6):
            raise ValueError("leg must be km:minutes:lat:lng[:lat2:lng2]")
        km, minutes = float(bits[0]), (int(bits[1]) if bits[1] else None)
        pts = [float(x) for x in bits[2:]]
        if not (0 < km <= 2000) or (minutes is not None and not 0 <= minutes <= 3000):
            raise ValueError("leg out of range")
        if any(not math.isfinite(x) for x in pts) or any(not -90 <= y <= 90 for y in pts[0::2]) \
                or any(not -180 <= x <= 180 for x in pts[1::2]):
            raise ValueError("leg out of range")
        legs.append((km, minutes, pts[0], pts[1], *(pts[2:] or [None, None])))
    if not legs or len(legs) > MAX_LEGS:
        raise ValueError(f"need 1 to {MAX_LEGS} legs")
    return legs


def brands(table: Table | None = None) -> dict:
    """Where each brand's numbers come from: {key: {name, source, as_of, note}}."""
    table = table or load()
    return {k: {"name": b["name"], "source": " ; ".join(b["sources"]), "as_of": b["as_of"], "note": b.get("note")}
            for k, b in table.brands.items()}


def leg_quote(km: float, minutes: int | None, start: tuple, end: tuple | None = None, day: date | None = None,
              table: Table | None = None) -> dict:
    """One leg's quotes with where it starts: {km, minutes, region, region_name, quotes}."""
    a = place(*start)
    b = place(*end) if end and None not in end else None
    return {"km": round(km, 1), "minutes": minutes, "region": a.area, "region_name": areas.name_of(a.area),
            "quotes": quote(km, minutes, a, b, day, table)}


def quotes(legs: list[Leg], day: date | None = None, table: Table | None = None) -> dict:
    """Quotes for every leg plus where each brand's numbers come from."""
    table = table or load()
    rows = [leg_quote(km, minutes, (lat, lng), (lat2, lng2), day, table) for km, minutes, lat, lng, lat2, lng2 in legs]
    return {"legs": rows, "brands": brands(table)}
