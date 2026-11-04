"""The assistant's wider read tools (spec 2026-10-29 assistant-tools §5.1, §5.3-5.7): find_places filters and sorts,
evidence, compare, status, dishes, travel by mode and chain, journey, climate, calendar, stays, cost, local tips and
area notices. Every function reads published data only (corpus through corpus.retrieval / corpus.views /
corpus.serving, live through the callables the harness injects) and answers `unknown` when the data does not say.

Lists of places (find, stays, dishes) pass the trip's hard filters and the places the user hid, fail-closed. A place the
user names (evidence, compare, status, cost) is shown as it is, with `fits_trip: false` when a hard limit rules it out.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Callable
from zoneinfo import ZoneInfo

from corpus.retrieval import read_span
from corpus.ontology import load as load_ontology
from corpus.serving import feature as served_feature

from ..domain.state import TripState
from ..domain.text import fold, squash

if TYPE_CHECKING:
    from .knowledge import Knowledge

VN = ZoneInfo("Asia/Ho_Chi_Minh")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
FIRM = ("VERIFIED", "OUTDATED")
FIND_KEYS = ("near_place", "near_km", "price_max", "sort", "exclude", "page")  # find_places keys corpus.retrieval does not know
SORTS = ("fit", "distance", "reputation", "price")
COMPARE_DEFAULT = ("crowd", "noise", "parking", "value_for_money")
QUOTES = 3  # evidence quotes per feature
QUOTE_CHARS = 180
MAX_DAYS = 45  # calendar() window
MAX_ROUTE_POINTS = 6
MODES = ("walk", "motorbike", "car")
LISTS = ("access", "situation", "bring", "avoid", "photo_spot", "order")
CLAIM_KINDS = ("tip", "notice", "access", "avoid", "best_time", "price_norm", "crowded_at", "if_rain", "specialty", "season",
               "event")
LOCAL_MAX = 6
EARTH_KM = 6371.0088


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la, lb = math.radians(a[0]), math.radians(b[0])
    h = math.sin((lb - la) / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(h))


def _line_km(coords: list) -> float:
    return sum(_km(tuple(a), tuple(b)) for a, b in zip(coords, coords[1:]))


def _minutes(hhmm: str) -> int | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", hhmm or "")
    return int(m[1]) * 60 + int(m[2]) if m else None


def open_state(hours: dict | None, now: datetime) -> tuple[bool | None, str | None]:
    """(open now, today's windows "09:00-21:00, ...") from a serving `hours` block. None / None when the hours are not
    VERIFIED / OUTDATED (unknown, never "closed"); a window that runs past midnight counts on the next day too."""
    if not hours or hours.get("status") not in FIRM or not isinstance(hours.get("value"), dict):
        return None, None
    value, d, t = hours["value"], now.weekday(), now.hour * 60 + now.minute
    today = [r for r in value.get(DAYS[d]) or () if len(r) == 2]
    text = ", ".join(f"{a}-{b}" for a, b in today) or "closed"
    for a, b in today:
        lo, hi = _minutes(a), _minutes(b)
        if lo is not None and hi is not None and (lo <= t < hi if lo < hi else t >= lo):
            return True, text
    for a, b in value.get(DAYS[d - 1]) or ():  # yesterday's window that ends after midnight
        lo, hi = _minutes(a), _minutes(b)
        if lo is not None and hi is not None and lo > hi and t < hi:
            return True, text
    return False, text


def unit_price(card: dict) -> tuple[int | None, str | None]:
    """The lowest price a card states, and what it is: a night (stay), per person, or an entry fee. (None, None) = unknown."""
    if card.get("g") == "stay":
        night = card.get("night")
        return (night, "night") if isinstance(night, int) else (None, None)
    price = card.get("price")  # [min, max]; min is None for Maps' "up to X": only the upper bound states a price then
    if isinstance(price, list) and price:
        for bound in price[:2]:
            if isinstance(bound, int):
                return bound, "person"
    fee = card.get("fee") or {}
    for k in ("min", "typ"):
        if isinstance(fee.get(k), int):
            return fee[k], "entry"
    return None, None


@dataclass(frozen=True)
class Feeds:
    """Published data outside the retrieval engine. Each is a callable (None = this source is not offered, and the tool
    says it has no data). `Feeds.corpus()` reads the city's built views and serving files."""
    city: str = "dalat"
    now: Callable[[], datetime] = lambda: datetime.now(VN)  # noqa: E731
    climate: Callable[[], dict | None] | None = None        # {"1".."12": {tmax_c, tmin_c, rain_prob, fog_prob, days, years}}
    calendar: Callable[[], list[dict] | None] | None = None  # [{date, lunar: {year, month, day, leap}, holiday | None}]
    restricted: Callable[[float, float], list[dict] | None] | None = None  # areas holding the point; None = view never built
    stay_prices: Callable[[], dict] | None = None           # (fid, stay_date, nights) -> published price row

    @classmethod
    def corpus(cls, city: str = "dalat") -> "Feeds":
        from corpus import views
        from corpus.serving import stay_prices

        def restricted(lat: float, lng: float) -> list[dict] | None:
            areas = views.restricted_areas(city)
            return None if areas is None else views.restricted_hits(lat, lng, areas)
        return cls(city=city, climate=lambda: views.climate_normals(city), calendar=lambda: views.calendar_days(city),
                   restricted=restricted, stay_prices=lambda: stay_prices.load(city))


def _quote(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= QUOTE_CHARS else text[:QUOTE_CHARS].rsplit(" ", 1)[0] + "…"


class Reads:
    """k: the Knowledge these reads belong to (retrieval, catalog, live, pulse); feeds: the published data."""

    def __init__(self, k: "Knowledge", feeds: Feeds):
        self.k, self.feeds = k, feeds

    # ---------- shared ----------

    def _record(self, pid: str) -> dict | None:
        return self.k.retrieval.get_place(pid)

    def _fits(self, pid: str, state: TripState) -> bool:
        return self.k._admissible(pid, state)

    def _head(self, pid: str, state: TripState) -> dict:
        place = self.k.catalog.by_id[pid]
        return {"id": pid, "n": place.name, **({} if self._fits(pid, state) else {"fits_trip": False})}

    def _need(self, pid: str):
        if pid not in self.k.catalog.by_id:
            raise ValueError(f"unknown place id {pid!r}: use an id a read tool returned")
        record = self._record(pid)
        if not record:
            raise ValueError(f"no record for {pid!r}")
        return record

    def _point(self, pid: str) -> tuple[float, float]:
        place = self.k.catalog.by_id.get(pid)
        if place is None or place.lat is None or place.lng is None:
            raise ValueError(f"unknown place {pid!r}, or it has no coordinates")
        return place.lat, place.lng

    # ---------- find_places: near_place, price_max, sort, exclude, page ----------

    def find(self, criteria: dict, state: TripState, limit: int | None = None) -> dict:
        """Knowledge.find plus: near_place (a place id; near_km radius, default assistant.near_km), price_max (VND; the
        lowest price a place states must not pass it; a place with no price is left out and counted in no_price),
        sort fit | distance | reputation | price, exclude [ids], page (1 = first). ValueError on a bad value."""
        with read_span("reads"):
            k, cfg = self.k, self.k.cfg
            core = {key: v for key, v in criteria.items() if key not in FIND_KEYS}
            sort = criteria.get("sort") or "fit"
            if sort not in SORTS:
                raise ValueError(f"sort must be one of {list(SORTS)}")
            price_max = criteria.get("price_max")
            if price_max is not None and (isinstance(price_max, bool) or not isinstance(price_max, (int, float)) or price_max <= 0):
                raise ValueError("price_max must be a number of VND above 0")
            page = criteria.get("page", 1)
            if isinstance(page, bool) or not isinstance(page, int) or page < 1:
                raise ValueError("page must be an integer from 1")
            exclude = set(criteria.get("exclude") or ())
            if not all(isinstance(x, str) for x in exclude):
                raise ValueError("exclude must be a list of place ids")
            origin = None
            if (ref := criteria.get("near_place")) is not None:
                origin = self._point(str(ref))
                exclude.add(str(ref))
                km = float(criteria.get("near_km") or cfg.near_km)
                core["near"] = [origin[0], origin[1], km]
            elif core.get("near"):
                origin = (float(core["near"][0]), float(core["near"][1]))
            if sort == "distance" and origin is None:
                raise ValueError("sort distance needs near_place or near")
            found = k.retrieval.find(core, limit=cfg.find_pool)
            hits = [h for h in found.hits if h.place_id not in exclude and self._fits(h.place_id, state)]
            no_price = 0
            if price_max is not None:
                kept = []
                for h in hits:
                    price, _ = unit_price(h.card)
                    if price is None:
                        no_price += 1
                    elif price <= price_max:
                        kept.append(h)
                hits = kept
            rows = [(h, self._sort_key(h, sort, origin)) for h in hits]
            if sort != "fit":
                rows.sort(key=lambda r: r[1])
            size = limit or k.data_places
            window = rows[(page - 1) * size: page * size]
            places = []
            for h, _ in window:
                card = {"id": h.place_id, **h.card}
                if origin is not None and (p := k.catalog.by_id.get(h.place_id)) and p.lat is not None:
                    card["km_line"] = round(_km(origin, (p.lat, p.lng)), 1)
                if (price := unit_price(h.card))[0] is not None:
                    card["price_from"] = price[0]
                places.append(card)
            if sort == "distance" and places:
                places = self._by_minutes(origin, places)
            if sort == "fit":
                best = hits[0].score if hits else 0.0
                ranked = [h.place_id for h in hits if best <= 0 or h.score >= k.cards_ratio * best][(page - 1) * size:][:k.cards_max]
            else:
                ranked = [p["id"] for p in places][:k.cards_max]
            out = {"places": places, "maybe": sum(self._fits(h.place_id, state) and h.place_id not in exclude for h in found.maybe),
                   "unknown": found.unknown, "ranked": ranked, "page": page, "more": len(rows) > page * size, "total": len(rows)}
            if price_max is not None:
                out["no_price"] = no_price
            return out

    def _sort_key(self, hit, sort: str, origin) -> tuple:
        if sort == "distance":
            place = self.k.catalog.by_id.get(hit.place_id)
            return (_km(origin, (place.lat, place.lng)) if place and place.lat is not None else math.inf,)
        if sort == "price":
            price, _ = unit_price(hit.card)
            return (price is None, price or 0)
        if sort == "reputation":
            rep = (((self._record(hit.place_id) or {}).get("provenance") or {}).get("reputation") or {}).get("score")
            return (rep is None, -(rep or 0.0))
        return ()

    def _by_minutes(self, origin, places: list[dict]) -> list[dict]:
        """The page ordered by road minutes (OSRM) when live gives them; km_line alone otherwise."""
        live = self.k.live
        pts = [(self.k.catalog.by_id[p["id"]].lat, self.k.catalog.by_id[p["id"]].lng) for p in places]
        if live.matrix is None or len(pts) < 1:
            return places
        try:
            row = live.matrix([origin, *pts])["minutes"][0][1:]
        except Exception:  # OSRM down: the straight-line order stands
            return places
        for p, m in zip(places, row):
            if m is not None:
                p["min"] = m
        return sorted(places, key=lambda p: (p.get("min") is None, p.get("min") or 0, p.get("km_line", 0)))

    # ---------- place_evidence ----------

    def evidence(self, pid: str, question: str, features: list[str] | None, state: TripState,
                 match: Callable[[str], list[str]] | None = None) -> dict:
        """What the corpus says about the features a question asks about: value, how many people said it, short quotes with
        their date and source. Features not given are matched from the question words by `match`. A feature the record
        has no value for is listed in `unknown`, never answered."""
        record = self._need(pid)
        ont = load_ontology()
        fids = [f for f in dict.fromkeys(features or ())]
        if bad := [f for f in fids if f not in ont.features]:
            raise ValueError(f"unknown feature {bad}: use ids from FEATURES")
        if not fids and match is not None:
            fids = [f for f in match(question) if f in ont.features][:4]
        out: dict = {**self._head(pid, state), "answers": [], "unknown": []}
        for fid in fids:
            try:
                f = served_feature(record, fid)
            except KeyError:
                f = None
            if not f or f.get("value") is None or f.get("status") not in ("VERIFIED", "OUTDATED", "UNCERTAIN"):
                out["unknown"].append(fid)
                continue
            quotes = []
            try:
                hits = self.k.retrieval.evidence(pid, fid, limit=QUOTES)
            except Exception:  # no span index: the value stands without quotes
                hits = []
            for h in hits:
                quotes.append({k: v for k, v in (("q", _quote(h.quote)), ("src", h.source),
                                                 ("date", (h.observed_at or "")[:10])) if v})
            n = f.get("n")
            row = {"fid": fid, "meaning": ont.features[fid].hint.split(":")[0][:90], "value": f["value"], "status": f["status"],
                   "n": n, "share": f.get("mention_rate"), "quotes": quotes}
            if f.get("reason") == "silence":
                row["note"] = "nobody mentioned it: this is the absence of a report, not a confirmed fact"
            out["answers"].append({k: v for k, v in row.items() if v not in (None, [], "")})
        words = {w for w in squash(question).split() if len(w) > 2}
        lists = []
        for kind in LISTS:
            items = [(i if isinstance(i, str) else (i or {}).get("text") or "") for i in (record.get("details") or {}).get(kind) or ()]
            hit = [t for t in items if t and words & set(squash(t).split())][:3]
            if hit:
                lists.append({"kind": kind, "items": [_quote(t) for t in hit]})
        if lists:
            out["notes"] = lists
        crowd = (record.get("operation") or {}).get("crowd_by_time")
        if crowd and ("crowd" in fids or words & {"dong", "vang", "gio", "luc", "khi"}):
            out["crowd"] = {k: crowd[k] for k in ("weekday", "weekend", "peak") if crowd.get(k)}
        out["as_of"] = (record.get("provenance") or {}).get("as_of")
        if not out["answers"] and not lists and "crowd" not in out:
            out["note"] = "the corpus has no evidence on this: say it is unknown"
        return out

    # ---------- compare_places ----------

    def compare(self, ids: list[str], aspects: list[str] | None, state: TripState) -> dict:
        """The same fields for 2-4 places: price, rating, hours today, visit time and the aspects (feature ids); a field a
        record lacks is "unknown"."""
        ids = list(dict.fromkeys(ids))
        if not 2 <= len(ids) <= self.k.cfg.max_compare:
            raise ValueError(f"compare 2 to {self.k.cfg.max_compare} different places")
        ont = load_ontology()
        aspects = list(dict.fromkeys(aspects or COMPARE_DEFAULT))
        if bad := [a for a in aspects if a not in ont.features and not a.startswith("fit.")]:
            raise ValueError(f"unknown aspect {bad}: use feature ids from FEATURES")
        now = self.feeds.now()
        rows, groups = [], {}
        for pid in ids:
            rec = self._need(pid)
            ident, op, prov = rec.get("identity") or {}, rec.get("operation") or {}, rec.get("provenance") or {}
            is_open, today = open_state(op.get("hours"), now)
            price = (op.get("price_per_person") or {}).get("value") or {}
            fee = op.get("entry_fee") or {}
            row = {**self._head(pid, state), "cat": ident.get("category"), "area": ident.get("area"),
                   "rating": ident.get("rating"), "reviews": ident.get("reviews"),
                   "reputation": ((prov.get("reputation") or {}).get("score")),
                   "price": [price.get("min_vnd"), price["max_vnd"]] if price.get("max_vnd") is not None else "unknown",
                   "entry": fee.get("typical_vnd", "unknown"), "night": (op.get("price_per_night") or {}).get("value", "unknown"),
                   "open_now": "unknown" if is_open is None else is_open, "hours_today": today or "unknown",
                   "visit_min": (op.get("visit_minutes") or {}).get("typical", "unknown"),
                   "aspects": {a: self._aspect(rec, a) for a in aspects}}
            rows.append(row)
            if (g := rec.get("near_duplicate_group")) is not None:
                groups.setdefault(g, []).append(pid)
        out = {"rows": rows, "aspects": aspects}
        if branches := [g for g in groups.values() if len(g) > 1]:
            out["same_place"] = branches  # near-duplicate listings: branches or the same venue under two names
        return out

    @staticmethod
    def _aspect(record: dict, aspect: str):
        if aspect.startswith("fit."):
            f = (record.get("suitability") or {}).get({"kids": "kids", "parents": "elderly", "wheelchair": "wheelchair"}.get(aspect[4:], ""))
        else:
            try:
                f = served_feature(record, aspect)
            except KeyError:
                f = None
        if not f or f.get("value") is None or f.get("status") not in ("VERIFIED", "OUTDATED", "UNCERTAIN"):
            return "unknown"
        if f.get("reason") == "silence":
            return "unknown"
        return f["value"] if f["status"] != "UNCERTAIN" else f"{f['value']}?"

    # ---------- place_status ----------

    def status(self, ref: str, state: TripState) -> dict:
        """Is the place real and open: the corpus status, a closure Google Maps reported (Nhịp), hours state now."""
        closed = self._closed_report(ref)
        if ref not in self.k.catalog.by_id:
            if closed:
                return {"n": closed["name"], "status": "closed_reported", "closure": closed["closure"]}
            raise ValueError(f"unknown place {ref!r}: no such place in the corpus")
        rec = self._need(ref)
        op, prov = rec.get("operation") or {}, rec.get("provenance") or {}
        hours = op.get("hours") or {}
        is_open, today = open_state(hours, self.feeds.now())
        out = {**self._head(ref, state), "in_corpus": True, "corpus_status": rec.get("status"),
               "open_now": "unknown" if is_open is None else is_open, "hours_today": today or "unknown",
               "hours_source": {k: hours.get(k) for k in ("status", "as_of", "source") if hours.get(k)},
               "last_seen": prov.get("as_of"), "rating_trend": (prov.get("rating_trend") or {}).get("direction")}
        out["closure"] = closed["closure"] if closed else "no closure report in the data"
        return {k: v for k, v in out.items() if v not in (None, {})}

    def _closed_report(self, ref: str) -> dict | None:
        pulse = self.k.pulse
        if pulse is None:
            return None
        try:
            items = pulse(kind="closed", limit=500)["items"]
        except Exception:
            return None
        name = fold((self.k.catalog.by_id[ref].name if ref in self.k.catalog.by_id else ref))
        for it in items:
            if it.get("place_id") == ref or fold(it["name"]) == name:
                return {"name": it["name"], "closure": {"text": it["text"]}}
        return None

    # ---------- find_dishes ----------

    def dishes(self, dish: str, state: TripState, limit: int = 6) -> dict:
        """Places whose menu or reviews name the dish (the corpus' dish search), through the hard filters; the dish
        lines as the menu writes them. Zero places = nothing written down, not "nobody serves it"."""
        if not squash(dish):
            raise ValueError("dish is empty")
        hits = [h for h in self.k.catalog.dishes(dish) if self._fits(h["id"], state)]
        places = []
        for h in hits[:limit]:
            card = self.k.retrieval.card(h["id"]) or {}
            lines = sorted({str(e.get("dish")) for e in h.get("evidence") or () if e.get("dish")})[:3]
            places.append({"id": h["id"], "n": h["name"], "dish": lines, "src": sorted({e["source"] for e in h["evidence"]}),
                           **{k: card[k] for k in ("addr", "price", "h") if k in card}})
        return {"dish": dish, "places": places, "total": len(hits), "ranked": [p["id"] for p in places],
                **({} if places else {"note": "no menu or review in the corpus names this dish: unknown, not absent"})}

    # ---------- distance by mode, route_time ----------

    def leg(self, a: tuple[float, float], b: tuple[float, float], mode: str | None) -> dict:
        """One road leg: minutes, km_road, source, fetched_at. ValueError("distance unavailable") when live gives nothing.
        mode None = the default vehicle (live.matrix); otherwise live.route, and a walk is the road km / walk_kmh."""
        live = self.k.live
        if mode not in (None, *MODES):
            raise ValueError(f"mode must be one of {list(MODES)}")
        try:
            if mode is None:
                out = live.matrix([a, b]) if live.matrix else None
                minutes = out["minutes"][0][1] if out else None
                if minutes is None:
                    raise ValueError("distance unavailable")
                return {"minutes": minutes, "source": out.get("source"), "fetched_at": out.get("fetched_at")}
            if live.route is None:
                raise ValueError("distance unavailable")
            r = live.route([a, b], "car" if mode == "walk" else mode)
            km = round(_line_km(r["coords"]), 1)
            minutes = max(1, round(km / self.k.cfg.walk_kmh * 60)) if mode == "walk" else r["minutes"]
            return {"minutes": minutes, "km_road": km, "source": r.get("source"), "fetched_at": r.get("fetched_at"),
                    **({"estimate": f"walking at {self.k.cfg.walk_kmh} km/h over the road"} if mode == "walk" else {})}
        except ValueError:
            raise
        except Exception as e:  # OSRM down or slow: no minutes, never a guess
            raise ValueError("distance unavailable") from e

    def route_time(self, ids: list[str], start: str | None, mode: str | None, state: TripState) -> dict:
        """Travel time through places in the order given (and from `start`: a place id or "center"), leg by leg. Only
        movement: no visit time, no opening hours."""
        refs = ([start] if start else []) + list(ids)
        if not 2 <= len(refs) <= MAX_ROUTE_POINTS:
            raise ValueError(f"give 2 to {MAX_ROUTE_POINTS} stops")
        pts = [self._ref_point(r) for r in refs]
        legs, total, unknown = [], 0, 0
        for (na, pa), (nb, pb) in zip(pts, pts[1:]):
            try:
                leg = {"from": na, "to": nb, **self.leg(pa, pb, mode)}
                total += leg["minutes"]
            except ValueError:
                leg, unknown = {"from": na, "to": nb, "minutes": "unknown"}, unknown + 1
            legs.append(leg)
        out = {"legs": legs, "mode": mode or "default"}
        out["total_minutes"] = total if not unknown else "unknown"
        if unknown:
            out["partial_minutes"] = total
        return out

    def _ref_point(self, ref: str) -> tuple[str, tuple[float, float]]:
        if ref == "center":
            return self.k.center[0], (self.k.center[1], self.k.center[2])
        return self.k.catalog.by_id[ref].name if ref in self.k.catalog.by_id else ref, self._point(ref)

    # ---------- journey ----------

    def journey(self, origin: str | None, day: str | None, state: TripState) -> dict:
        """How to reach the city from `origin` (a place name; the trip's origin when None) on `day`: road, coach,
        flight. Only a flight or coach with a crawled offer is feasible; anything else is unknown or no."""
        live = self.k.live
        if live.journey is None:
            raise ValueError("journey unavailable")
        o = state.origin.value if state.origin.known else None
        name = origin or (o.text if o else None)
        if not name:
            raise ValueError("origin is unknown: ask the user where they set off from")
        lat, lng = (o.lat, o.lng) if o is not None and not origin and o.lat is not None else (None, None)
        if day is None and state.start_date.known:
            day = state.start_date.value.isoformat()
        try:
            raw = live.journey(name, lat, lng, day)
        except Exception as e:
            raise ValueError("journey unavailable") from e
        return {"origin": raw.get("origin") or name, "day": raw.get("day"), "options": [self._option(o) for o in raw["options"]]}

    @staticmethod
    def _option(o: dict) -> dict:
        row = {"mode": o["mode"], "feasible": "unknown" if o["feasible"] is None else o["feasible"], "reason": o["reason"],
               "minutes": o.get("minutes") if o.get("minutes") is not None else "unknown"}
        if o.get("price_min_vnd"):
            row["price_vnd"] = [o["price_min_vnd"], o["price_max_vnd"]]
        for leg in o.get("legs") or ():
            if leg.get("via"):
                row["via"] = leg["via"]
        offers = [x for x in o.get("offers") or () if x.get("depart_at")][:3]
        if offers:
            row["offers"] = [{k: x[k] for k in ("carrier", "flight_no", "depart_at", "arrive_at", "price_vnd", "stops", "observed_at",
                                                "source") if x.get(k) is not None} for x in offers]
        return row

    # ---------- climate, calendar ----------

    def climate(self, month: int | None) -> dict:
        """Monthly climate normals of the city (many years): temperatures, share of rainy days, share of foggy days."""
        view = self.feeds.climate() if self.feeds.climate else None
        if not view:
            raise ValueError("climate unavailable")
        keep = lambda r: {k: r[k] for k in ("tmax_c", "tmin_c", "rain_prob", "fog_prob", "years") if r.get(k) is not None}  # noqa: E731
        if month is not None:
            row = view.get(str(month))
            if not row:
                raise ValueError(f"no climate for month {month}")
            return {"month": month, **keep(row), "note": "rain_prob = share of days with rain; long-run average, not a forecast"}
        rows = {m: keep(r) for m, r in sorted(view.items(), key=lambda kv: int(kv[0]))}
        wet = sorted(view, key=lambda m: -(view[m].get("rain_prob") or 0))[:5]
        return {"months": rows, "rainiest_months": sorted(int(m) for m in wet),
                "note": "rain_prob = share of days with rain; long-run average, not a forecast"}

    def calendar(self, date_from: date, date_to: date, state: TripState) -> dict:
        """Holidays, lunar dates and events in a range of at most 45 days. No data on how busy a date is."""
        if date_to < date_from or (date_to - date_from).days >= MAX_DAYS:
            raise ValueError(f"the range must be 1 to {MAX_DAYS} days, oldest first")
        days = self.feeds.calendar() if self.feeds.calendar else None
        if days is None:
            raise ValueError("calendar unavailable")
        lo, hi = date_from.isoformat(), date_to.isoformat()
        inside = [d for d in days if lo <= d["date"] <= hi]
        if not inside:
            raise ValueError("the calendar does not cover these dates")
        holidays = [{"date": d["date"], "name": d["holiday"]} for d in inside if d.get("holiday")]
        lunar = lambda d: f"{d['lunar']['day']}/{d['lunar']['month']}" + (" nhuận" if d["lunar"].get("leap") else "")  # noqa: E731
        weekends = sum(1 for d in inside if date.fromisoformat(d["date"]).weekday() >= 5)
        events = []
        months = sorted({(date_from + timedelta(days=i)).month for i in range((date_to - date_from).days + 1)})
        for m in months:
            r = self.k.trends(state, kind="event", month=m, limit=6)
            events += [it for it in r.get("items", []) if it not in events]
        return {"from": lo, "to": hi, "holidays": holidays, "lunar_first": lunar(inside[0]), "lunar_last": lunar(inside[-1]),
                "weekend_days": weekends, "events": events,
                "note": "there is no crowd data per date: do not say a date is busy or quiet"}

    # ---------- find_stays, estimate_cost ----------

    def _stay_price(self, pid: str, card: dict, check_in: str | None, nights: int) -> dict | None:
        """A dated price when the crawl has this stay and date, else the Maps reference price with its age."""
        rows = self.feeds.stay_prices() if self.feeds.stay_prices else {}
        if check_in and (row := rows.get((pid, check_in, nights))) and row.get("price_night_vnd"):
            out = {"night_vnd": row["price_night_vnd"], "kind": "dated", "stay": [check_in, nights], "as_of": (row.get("observed_at") or "")[:10],
                   "src": row.get("source")}
            if row.get("price_total_vnd"):
                out["total_vnd"] = row["price_total_vnd"]
            if row.get("available") is False:
                out["available"] = False
            return out
        night = card.get("night")
        if isinstance(night, int):
            rec = self._record(pid) or {}
            node = (rec.get("operation") or {}).get("price_per_night") or {}
            return {"night_vnd": night, "kind": "reference", "as_of": node.get("as_of"), "src": node.get("source"),
                    **({"note": f"no price crawled for {check_in}"} if check_in else {})}
        return None

    def stays(self, criteria: dict, dates: dict | None, state: TripState, limit: int | None = None) -> dict:
        """Lodging through the hard filters: criteria as find_places (groups is forced to stay), `dates` {check_in, nights}.
        Each stay carries its night price with kind dated (crawled for those dates) or reference (Google Maps listing
        price, with its date). price_max compares the night price; a stay with none is left out and counted."""
        check_in, nights = None, 1
        if dates:
            check_in = str(dates.get("check_in") or "")
            try:
                date.fromisoformat(check_in)
            except ValueError:
                raise ValueError("dates.check_in must be YYYY-MM-DD") from None
            nights = dates.get("nights", 1)
            if isinstance(nights, bool) or not isinstance(nights, int) or not 1 <= nights <= 30:
                raise ValueError("dates.nights must be 1 to 30")
        crit = {**criteria, "groups": ["stay"]}
        sort = crit.get("sort") or "fit"
        price_max, size = crit.pop("price_max", None), limit or self.k.data_places
        page = crit.pop("page", 1)
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError("page must be an integer from 1")
        crit["sort"] = "fit" if sort == "price" else sort
        pool = self.find({k: v for k, v in crit.items() if k != "page"}, state, limit=self.k.cfg.find_pool)
        rows, no_price = [], 0
        for card in pool["places"]:
            price = self._stay_price(card["id"], card, check_in, nights)
            if price is None:
                no_price += 1
                continue
            if price_max is not None and price["night_vnd"] > price_max:
                continue
            ident = (self._record(card["id"]) or {}).get("identity") or {}
            rows.append({"id": card["id"], "n": card["n"], "cat": card.get("cat"), "area": ident.get("area"),
                         "rating": ident.get("rating"), "reviews": ident.get("reviews"), "price": price,
                         **{k: card[k] for k in ("km_line", "min") if k in card}})
        if sort == "price":
            rows.sort(key=lambda r: r["price"]["night_vnd"])
        window = rows[(page - 1) * size: page * size]
        out = {"stays": window, "ranked": [r["id"] for r in window], "page": page, "more": len(rows) > page * size, "total": len(rows)}
        if price_max is not None or no_price:
            out["no_price"] = no_price
        return out

    def cost(self, ids: list[str], people: int, nights: int | None, check_in: str | None, state: TripState) -> dict:
        """What the places cost for `people`: entry (official adult price, else the estimated fee), spend per person
        (menu price range) and, for a stay, the room per night x nights. The sums add only what is stated; a place with
        no price is listed in unknown and never guessed. Child / senior prices are not applied."""
        ids = list(dict.fromkeys(ids))
        if not 1 <= len(ids) <= 10:
            raise ValueError("give 1 to 10 places")
        if isinstance(people, bool) or not isinstance(people, int) or not 1 <= people <= 50:
            raise ValueError("people must be 1 to 50")
        lines, unknown = [], []
        lo = hi = 0
        for pid in ids:
            rec = self._need(pid)
            op, det = rec.get("operation") or {}, rec.get("details") or {}
            card = self.k.retrieval.card(pid) or {}
            line: dict = self._head(pid, state)
            mn = mx = 0
            if card.get("g") == "stay":
                price = self._stay_price(pid, card, check_in, nights or 1)
                if price:
                    n = nights or 1
                    line["room_night"] = price
                    line["nights"] = n
                    mn = mx = price["night_vnd"] * n
                    line["per"] = "one room"
            else:
                adult = (((det.get("cost") or {}).get("entry") or {}).get("adult") or {}).get("vnd")
                fee = op.get("entry_fee") or {}
                if adult is not None:
                    line["entry"] = {"each": adult, "kind": "official", "total": adult * people}
                    mn += adult * people
                    mx += adult * people
                elif fee.get("typical_vnd") is not None:
                    a, b = fee.get("min_vnd", fee["typical_vnd"]), fee.get("max_vnd", fee["typical_vnd"])
                    line["entry"] = {"each": fee["typical_vnd"], "kind": fee.get("kind") or "estimate", "src": fee.get("source"),
                                     "total": [a * people, b * people]}
                    mn += a * people
                    mx += b * people
                spend = (op.get("price_per_person") or {}).get("value") or {}
                if spend.get("max_vnd") is not None:
                    low = spend.get("min_vnd")  # None = Maps' "up to X": unknown below, counted as 0 only in the total
                    floor = low or 0
                    line["spend"] = {"each": [low, spend["max_vnd"]], "total": [floor * people, spend["max_vnd"] * people],
                                     **({"up_to": True} if low is None else {})}
                    mn += floor * people
                    mx += spend["max_vnd"] * people
                if (op.get("price_per_person") or {}).get("as_of"):
                    line["as_of"] = op["price_per_person"]["as_of"]
            if "entry" in line or "spend" in line or "room_night" in line:
                lines.append(line)
                lo += mn
                hi += mx
            else:
                unknown.append({"id": pid, "n": line["n"]})
        out = {"lines": lines, "people": people, "total_vnd": [lo, hi] if lines else "unknown", "unknown": unknown}
        if unknown:
            out["partial"] = "the total leaves out the places in unknown"
        return out

    # ---------- local_tips, area_notice ----------

    def tips(self, pid: str | None, topic: str | None, state: TripState, month: int | None = None) -> dict:
        """Local advice: the place's own timing / access / warnings from its record, and LocalClaims (facts and
        reference claims, each labelled; unverified ones are said as "tham khảo"). Give a place, a topic, or both."""
        if not pid and not topic:
            raise ValueError("give place_id or topic")
        out: dict = {}
        tips: list[dict] = []
        subject = None
        if pid:
            rec = self._need(pid)
            out.update(self._head(pid, state))
            subject = self.k.catalog.by_id[pid].name
            tips += self._place_tips(rec)
        claims = self._claims(subject, topic, month)
        for c in claims[:LOCAL_MAX]:
            ev = (c.get("evidence") or [{}])[0]
            row = {"src": "local", "label": c["label"], "kind": c["kind"], "text": _quote(c["text"]),
                   "domain": ev.get("domain"), "date": (ev.get("retrieved_at") or "")[:10]}
            if c.get("months"):
                row["months"] = list(c["months"])
            if c.get("amount_min_vnd") is not None:
                row["vnd"] = [c["amount_min_vnd"], c.get("amount_max_vnd")]
            tips.append({k: v for k, v in row.items() if v not in (None, "", [])})
        out["tips"] = tips
        if not tips:
            out["note"] = "the corpus has no local advice on this: say so"
        return out

    def _claims(self, subject: str | None, topic: str | None, month: int | None) -> list[dict]:
        read = getattr(self.k.retrieval, "local_claims", None)
        if read is None:
            return []
        kind = topic if topic in CLAIM_KINDS else None
        try:
            rows = read(subject=subject, kind=kind, month=month)
        except Exception:
            return []
        if topic and kind is None:  # free words: the claim's text or subject must use one of them
            words = {w for w in squash(topic).split() if len(w) > 2}
            rows = [r for r in rows if words & set(squash(f"{r['subject']} {r['text']}").split())]
        return rows

    @staticmethod
    def _place_tips(record: dict) -> list[dict]:
        det, svc = record.get("details") or {}, record.get("service") or {}
        out = []
        timing = det.get("timing") or {}
        for key, label in (("best_time", "best time"), ("avoid_time", "avoid time")):
            items = ((timing.get(key) or {}).get("items") or [])
            for i in items[:2]:
                if (i.get("status", "VERIFIED") if isinstance(i, dict) else "VERIFIED") in FIRM + ("UNCERTAIN",):
                    out.append({"src": "place", "kind": label, "text": _quote(i["text"] if isinstance(i, dict) else i)})
        if timing.get("best_months"):
            out.append({"src": "place", "kind": "best months", "months": timing["best_months"]})
        if timing.get("avoid_months"):
            out.append({"src": "place", "kind": "avoid months", "months": timing["avoid_months"]})
        if timing.get("last_entry"):
            out.append({"src": "place", "kind": "last entry", "text": str(timing["last_entry"])})
        for kind in ("access", "situation", "bring", "avoid"):
            for i in (det.get(kind) or [])[:2]:
                text = i if isinstance(i, str) else (i or {}).get("text")
                if text:
                    out.append({"src": "place", "kind": kind, "text": _quote(text)})
        for fid in ("tourist_trap", "scam_stage", "cash_only", "night_road_risk"):
            for group in ("service", "effort"):
                f = (record.get(group) or {}).get(fid)
                if f and f.get("status") in FIRM + ("UNCERTAIN",) and f.get("value") not in (None, "absent") and f.get("reason") != "silence":
                    out.append({"src": "place", "kind": fid, "value": f["value"], "n": f.get("n")})
        return out

    def area(self, pid: str) -> dict:
        """Is the place inside a restricted area (military land, no-access land) the map data lists."""
        self._need(pid)
        lat, lng = self._point(pid)
        read = self.feeds.restricted
        hits = read(lat, lng) if read else None
        if hits is None:
            return {"id": pid, "status": "unknown", "note": "the restricted-area map was never built: say it is unknown"}
        if not hits:
            return {"id": pid, "status": "none_listed",
                    "note": "OpenStreetMap lists no restricted area here; that does not prove the place is open to visit"}
        return {"id": pid, "status": "restricted", "areas": [{k: h[k] for k in ("kind", "name", "operator", "access") if h.get(k)} for h in hits],
                "source": "OpenStreetMap"}
