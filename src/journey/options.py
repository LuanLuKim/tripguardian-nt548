"""Which ways from the user's home to the lodging are feasible. Code decides (thresholds in config/journey.yaml),
no model. OSRM draws and times the road legs; a coach or a flight is feasible only as far as its source says so."""

import math
from dataclasses import replace
from datetime import date, datetime

import booking
import live

from .settings import Settings, load
from .types import Journey, Leg, Option, Point


def crow_km(a: Point, b: Point) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _line_km(coords: list) -> float:
    return round(sum(crow_km(tuple(a), tuple(b)) for a, b in zip(coords, coords[1:])), 1)


def _pass(coords: list, cfg: Settings) -> str | None:
    """The pass the road comes through: the entry road within entry_snap_km of the drawn road (the city is one end
    either way); None when none is that close. It names the road OSRM took, it does not change it."""
    best = None
    for r in cfg.entry_roads:
        d = min((crow_km((c[0], c[1]), (r["lat"], r["lng"])) for c in coords), default=math.inf)
        if d <= cfg.entry_snap_km and (best is None or d < best[0]):
            best = (d, r["text"])
    return best[1] if best else None


def _road(a: Point, b: Point, mode: str, labels: tuple[str, str], kind: str, route, lcfg, cfg: Settings | None = None) -> Leg:
    """One road leg drawn and timed by OSRM; a road OSRM cannot give is a leg with no minutes, not a guess."""
    try:
        r = route([a, b], mode, lcfg)
    except live.Unavailable:
        return Leg(kind=kind, from_label=labels[0], to_label=labels[1])
    return Leg(kind=kind, from_label=labels[0], to_label=labels[1], minutes=r["minutes"], distance_km=_line_km(r["coords"]),
               coords=r["coords"], source=r["source"], fetched_at=r["fetched_at"],
               via=_pass(r["coords"], cfg) if cfg is not None and kind == "drive" else None)


def _total(legs: list[Leg]) -> int | None:
    return sum(leg.minutes for leg in legs) if legs and all(leg.minutes is not None for leg in legs) else None


def _prices(offers: list) -> tuple[int | None, int | None]:
    p = [o.price_vnd for o in offers if o.price_vnd]
    return (min(p), max(p)) if p else (None, None)


def _drive(mode: str, origin: Point, dest: Point, way: str, dest_label: str, route, lcfg, cfg: Settings) -> Option:
    a, b = (origin, dest) if way == "inbound" else (dest, origin)
    labels = ("origin", dest_label) if way == "inbound" else (dest_label, "origin")
    leg = _road(a, b, mode, labels, "drive", route, lcfg, cfg)
    if leg.minutes is None:
        return Option(mode=mode, feasible=None, reason="no_route", legs=(leg,))
    if mode == "motorbike" and leg.distance_km > cfg.motorbike_max_km:
        return Option(mode=mode, feasible=False, reason="too_far", legs=(leg,), minutes=leg.minutes)
    return Option(mode=mode, feasible=True, reason="road", legs=(leg,), minutes=leg.minutes)


def _coach_minutes(found: list) -> int | None:
    """The shortest ride the crawled coaches state (depart -> arrive, local clock); None when none states both."""
    ride = [round((datetime.fromisoformat(o.arrive_at) - datetime.fromisoformat(o.depart_at)).total_seconds() / 60)
            for o in found if o.depart_at and o.arrive_at]
    return min((m for m in ride if m > 0), default=None)


def _bus(origin: Point, dest: Point, day: date | None, way: str, dest_label: str, route, offers_fn, lcfg,
         cfg: Settings) -> Option:
    near = min(lcfg.vexere_regions, key=lambda r: crow_km(origin, (r["lat"], r["lng"])), default=None)
    if near is None or crow_km(origin, (near["lat"], near["lng"])) > cfg.coach_region_max_km:
        return Option(mode="bus", feasible=False, reason="no_coach_region")
    if day is None:
        return Option(mode="bus", feasible=None, reason="needs_date")
    found = offers_fn("coach", booking.CoachQuery(origin=origin, day=day, way=way))
    if not found:
        return Option(mode="bus", feasible=False, reason="no_trips")
    lo, hi = _prices(found)
    real = any(o.depart_at for o in found)
    legs, minutes = (), None
    home_st, city_st = near.get("station"), lcfg.vexere_city_station
    if real and home_st and city_st:  # both stations located: door to door = road to the station + ride + road from it
        a, b = (home_st, city_st) if way == "inbound" else (city_st, home_st)
        pa, pb = (a["lat"], a["lng"]), (b["lat"], b["lng"])
        ride = Leg(kind="coach", from_label=a["name"], to_label=b["name"], minutes=_coach_minutes(found))
        if way == "inbound":
            legs = (_road(origin, pa, "car", ("origin", a["name"]), "transfer", route, lcfg), ride,
                    _road(pb, dest, "car", (b["name"], dest_label), "transfer", route, lcfg))
        else:
            legs = (_road(dest, pa, "car", (dest_label, a["name"]), "transfer", route, lcfg), ride,
                    _road(pb, origin, "car", (b["name"], "origin"), "transfer", route, lcfg))
        minutes = _total(list(legs))  # waiting at the station is not known: not added
    return Option(mode="bus", feasible=True if real else None, reason="trips" if real else "unchecked", legs=legs,
                  minutes=minutes, price_min_vnd=lo, price_max_vnd=hi, offers=tuple(found))


def _plane(origin: Point, dest: Point, day: date | None, way: str, dest_label: str, route, offers_fn, lcfg, cfg: Settings) -> Option:
    """The plane option. Every airport within airport_max_km (the nearest `max_airports`) is tried: where the nearest
    has no direct flight (Huế) a farther one may be quicker door to door (Đà Nẵng). The fastest with a crawled flight
    wins; with none, the nearest airport's option says what is unknown."""
    if crow_km(origin, dest) < cfg.plane["min_crow_km"]:
        return Option(mode="plane", feasible=False, reason="too_close")
    near = sorted((a for a in cfg.airports if crow_km(origin, (a["lat"], a["lng"])) <= cfg.plane["airport_max_km"]),
                  key=lambda a: crow_km(origin, (a["lat"], a["lng"])))[: cfg.plane["max_airports"]]
    if not near:
        return Option(mode="plane", feasible=False, reason="no_airport_near")
    tried = [_plane_via(ap, origin, dest, day, way, dest_label, route, offers_fn, lcfg, cfg) for ap in near]
    flying = [o for o in tried if o.feasible]
    return min(flying, key=lambda o: o.minutes if o.minutes is not None else math.inf) if flying else tried[0]


def _plane_via(ap: dict, origin: Point, dest: Point, day: date | None, way: str, dest_label: str, route, offers_fn, lcfg,
               cfg: Settings) -> Option:
    src, dst = ap["iata"], cfg.dest_airport["iata"]
    home_ap, city_ap = (ap["lat"], ap["lng"]), (cfg.dest_airport["lat"], cfg.dest_airport["lng"])
    if way == "inbound":
        legs = [_road(origin, home_ap, "car", ("origin", src), "transfer", route, lcfg),
                Leg(kind="flight", from_label=src, to_label=dst),
                _road(city_ap, dest, "car", (dst, dest_label), "transfer", route, lcfg)]
        query = booking.FlightQuery(src=src, dst=dst, day=day) if day else None
    else:
        legs = [_road(dest, city_ap, "car", (dest_label, dst), "transfer", route, lcfg),
                Leg(kind="flight", from_label=dst, to_label=src),
                _road(home_ap, origin, "car", (src, "origin"), "transfer", route, lcfg)]
        query = booking.FlightQuery(src=dst, dst=src, day=day) if day else None
    if query is None:
        return Option(mode="plane", feasible=None, reason="needs_date", legs=tuple(legs))
    found = offers_fn("flight", query)
    real = [o for o in found if o.depart_at and o.arrive_at]
    if not real:  # a prefilled link cannot say a flight exists that day: unknown, not feasible
        return Option(mode="plane", feasible=None, reason="flights_unchecked", legs=tuple(legs), minutes=_total(legs),
                      offers=tuple(found))
    legs[1] = _flight_leg(legs[1], real)  # a crawled flight exists that day: the only way a plane is feasible
    lo, hi = _prices(real)
    door = _total(legs)  # + check-in before the flight and the bags after it, which the flight time does not include
    door = door + cfg.plane["airport_before_min"] + cfg.plane["airport_after_min"] if door is not None else None
    return Option(mode="plane", feasible=True, reason="flights", legs=tuple(legs), minutes=door, price_min_vnd=lo,
                  price_max_vnd=hi, offers=tuple(found))


def _flight_leg(leg: Leg, flights: list) -> Leg:
    """The air leg timed by the crawled flights: the shortest of those with the fewest stopovers (local clock times)."""
    fewest = min(o.stops if o.stops is not None else 9 for o in flights)
    best = [o for o in flights if (o.stops if o.stops is not None else 9) == fewest]
    minutes = min(round((datetime.fromisoformat(o.arrive_at) - datetime.fromisoformat(o.depart_at)).total_seconds() / 60)
                  for o in best)
    seen = max(o.observed_at for o in flights if o.observed_at) if any(o.observed_at for o in flights) else None
    return replace(leg, minutes=minutes, source="gflights", fetched_at=seen)


def options(origin: Point, day: date | None, dest: Point | None = None, way: str = "inbound", cfg: Settings | None = None,
            route=None, offers=None) -> Journey:
    """The ways from `origin` to `dest` (the lodging; None -> city centre) on `day`; way = inbound (home -> city) |
    outbound (city -> home). `route` / `offers` replace OSRM and booking.offers (tests)."""
    if way not in booking.WAYS:
        raise ValueError(f"way must be inbound or outbound, not {way!r}")
    cfg = cfg or load()
    lcfg = live.load_settings()
    route = route or live.route_shape
    offers_fn = offers or booking.offers
    centre = dest is None
    if centre:
        dest = (cfg.city_centre["lat"], cfg.city_centre["lng"])
    label = "centre" if centre else "lodging"
    opts = (_drive("car", origin, dest, way, label, route, lcfg, cfg),
            _drive("motorbike", origin, dest, way, label, route, lcfg, cfg),
            _bus(origin, dest, day, way, label, route, offers_fn, lcfg, cfg),
            _plane(origin, dest, day, way, label, route, offers_fn, lcfg, cfg))
    return Journey(origin=origin, dest=dest, dest_is_centre=centre, way=way, day=day.isoformat() if day else None, options=opts)
