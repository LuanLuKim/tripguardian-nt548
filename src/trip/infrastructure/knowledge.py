"""What the Đà Lạt assistant reads: corpus places through corpus.retrieval, weather and travel time through callables
the harness injects (Trip never imports live). Every place list has passed the trip's hard filters, fail-closed."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Callable, Sequence

from corpus.retrieval import read_span

from ..domain.coverage import admissible
from ..domain.state import TripState
from ..domain.vibes import media_url
from .browse import Browse
from .catalog import Catalog
from .reads import FIND_KEYS, Feeds, Reads
from .settings import Assistant

SIMILAR_MAX = 4  # places a similar_places call averages
SIMILAR_POOL = 120  # nearest places taken before the criteria and the limit are applied
FIND_ALL = 500  # find asked for every place that passes (a filter over a similar list)
FIND_POOL = 40  # places asked of corpus.retrieval before the hard filters keep `limit` of them
WEATHER_KEYS = ("rain_prob", "rain_mm", "tmin_c", "tmax_c", "gust_kmh", "storm", "source", "fetched_at")
EARTH_KM = 6371.0088


@dataclass(frozen=True)
class LiveTools:
    """Live reads the harness passes in. weather(lat, lng, ["YYYY-MM-DD"]) -> {day: {rain_prob, rain_mm?, source,
    fetched_at}}; matrix([(lat, lng), ...]) -> {"minutes": [[int | None]], "source", "fetched_at"};
    route([(lat, lng), ...], mode) -> {"coords": [[lat, lng]], "minutes", "source", "fetched_at"} for mode car | motorbike;
    journey(origin text, lat | None, lng | None, "YYYY-MM-DD" | None) -> journey.Journey.as_dict() of the ways to the city.
    None = not offered."""
    weather: Callable[[float, float, list[str]], dict] | None = None
    matrix: Callable[[list[tuple[float, float]]], dict] | None = None
    route: Callable[[list[tuple[float, float]], str], dict] | None = None
    journey: Callable[[str, float | None, float | None, str | None], dict] | None = None


def _km_line(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line km between two points (not the road)."""
    la, lb = math.radians(a[0]), math.radians(b[0])
    h = math.sin((lb - la) / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return round(2 * EARTH_KM * math.asin(math.sqrt(h)), 1)


class Knowledge:
    """The assistant's read tools. retrieval: corpus.retrieval.RetrievalEngine; center: (name, lat, lng) of the city."""

    def __init__(self, retrieval, catalog: Catalog, live: LiveTools | None, center: tuple[str, float, float],
                 data_places: int = Assistant.data_places, cards_max: int = Assistant.cards_max,
                 cards_ratio: float = Assistant.cards_ratio, trends: Callable[..., dict | None] | None = None,
                 looks=None, cfg: Assistant | None = None, feeds: Feeds | None = None):
        """data_places: places of a find the agent reads; cards_max / cards_ratio: the ranked list for the place
        cards (config/trip.yaml assistant); trends(kind=, month=, limit=) -> corpus.pulse.trends of the city (None = not offered);
        looks: infrastructure.looks.Looks (photo vectors; None = similar uses corpus.retrieval for one place)."""
        self.retrieval, self.catalog, self.live, self.center = retrieval, catalog, live or LiveTools(), center
        self.data_places, self.cards_max, self.cards_ratio = data_places, cards_max, cards_ratio
        self.pulse = trends
        self.looks = looks
        self.perceiver = None  # infrastructure.perceive.Perceiver: photo and link reads (set by api/tools.py)
        self.cfg = cfg or Assistant()  # config/trip.yaml assistant: find_pool, near_km, walk_kmh, max_compare
        self.more = Reads(self, feeds or Feeds.corpus())  # infrastructure/reads.py: the wider read tools
        self.browse = Browse(self)  # infrastructure/browse.py: broad asks and tags -> subtags

    def _admissible(self, pid: str, state: TripState) -> bool:
        place = self.catalog.by_id.get(pid)
        return place is not None and pid not in state.meta.hidden_ids and admissible(place, state.hard, state.activities.get(pid))

    def find(self, criteria: dict, state: TripState, limit: int | None = None) -> dict:
        """Places that pass `criteria` (corpus.retrieval.find keys) and the trip's hard filters, best first: the top
        `limit` (data_places) as cards, and `ranked` = the ids for the place cards, in score order while a place has
        at least cards_ratio of the best score, at most cards_max. ValueError when the criteria are not valid.
        Keys of reads.FIND_KEYS (near_place, price_max, sort, exclude, page) are read by reads.Reads.find."""
        with read_span("knowledge"):
            if set(FIND_KEYS) & set(criteria):
                return self.more.find(criteria, state, limit)
            found = self.retrieval.find(criteria, limit=max(FIND_POOL, self.cards_max))
            hits = [h for h in found.hits if self._admissible(h.place_id, state)]
            best = hits[0].score if hits else 0.0
            ranked = [h.place_id for h in hits if best <= 0 or h.score >= self.cards_ratio * best][:self.cards_max]
            places = [{"id": h.place_id, **h.card} for h in hits[:limit or self.data_places]]
            return {"places": places, "maybe": sum(self._admissible(h.place_id, state) for h in found.maybe),
                    "unknown": found.unknown, "ranked": ranked}

    def place(self, pid: str) -> dict | None:
        card = self.retrieval.card(pid)
        return {"id": pid, **card} if card else None

    def fits(self, pid: str, state: TripState) -> bool:
        """Whether a place passes the trip's hard filters (fail-closed)."""
        return self._admissible(pid, state)

    def similar(self, ids: str | list[str], state: TripState, limit: int = 6, criteria: dict | None = None,
                exclude: set[str] | frozenset[str] = frozenset()) -> list[dict]:
        """Places that look like 1-4 places (the average of their photo vectors, corpus photo index), through the hard
        filters; `criteria` (find_places keys) keeps only places that also pass them; `exclude` ids are left out.
        [] without the index, never a guess. ValueError when `criteria` is not valid."""
        ids = [ids] if isinstance(ids, str) else list(dict.fromkeys(ids))
        ids = [i for i in ids if i in self.catalog.by_id][:SIMILAR_MAX]
        if not ids:
            return []
        gone = set(ids) | set(exclude)
        within = {p.id for p in self.catalog.places if p.id not in gone and self._admissible(p.id, state)}
        if self.looks is not None:
            ranked = [pid for pid, _ in self.looks.similar_to(ids, within, k=SIMILAR_POOL)]
        elif len(ids) == 1:
            ranked = [h.place_id for h in self.retrieval.similar(ids[0], within | {ids[0]}, k=SIMILAR_POOL + 1)
                      if h.place_id in within]
        else:
            ranked = []
        if criteria and ranked:
            allowed = {h.place_id for h in self.retrieval.find(criteria, limit=FIND_ALL).hits}
            ranked = [pid for pid in ranked if pid in allowed]
        return [card for pid in ranked[:limit * 2] if (card := self.place(pid))][:limit]

    def trends(self, state: TripState, kind: str | None = None, month: int | None = None, limit: int = 3) -> dict:
        """What the Nhịp Đà Lạt snapshot says is hot now, each item with its words, date and sources; a place of it passes
        the trip's hard filters (fail-closed) and carries `id`. {"error": "trends unavailable"} when the job never ran."""
        out = self.pulse(kind=kind, month=month, limit=limit) if self.pulse else None
        if out is None:
            return {"error": "trends unavailable"}
        items = []
        for it in out["items"]:
            pid = it["place_id"]
            if pid is not None and not self._admissible(pid, state):
                continue
            # sources: the site or kind and the date only. Their URLs carry long digit ids that would fill the 300 numbers
            # a reply may say (Meta.told_numbers), and the agent does not read links
            srcs = [{k: x[k] for k in ("label", "date") if x.get(k)} for x in it["sources"]]
            items.append({**({"id": pid} if pid is not None else {}),
                          **{k: v for k, v in it.items() if k not in ("place_id", "sources", "image")}, "sources": srcs})
        return {**out, "items": items}

    def trend_rows(self, state: TripState, kinds: tuple[str, ...], limit: int = 6) -> dict:
        """The Nhịp items of `kinds` for the chat's trends block (api/blocks.trends_block), with what the agent does not
        read: the sources' links and an event's picture. Places pass the trip's hard filters, as in `trends`.
        {as_of, items[]} or {} when the job never ran."""
        out, as_of = [], None
        for kind in kinds:
            got = self.pulse(kind=kind, limit=limit) if self.pulse else None
            if not got:
                continue
            as_of = got["as_of"]
            for it in got["items"]:
                pid = it["place_id"]
                if pid is not None and not self._admissible(pid, state):
                    continue
                out.append({**it, "intro": self._intro(pid) if pid else None})
        return {"as_of": as_of, "items": out} if as_of else {}

    def _intro(self, pid: str) -> str | None:
        """The first sentence of the place's checked introduction (corpus.intro), None when it has none."""
        intro = ((self.retrieval.get_place(pid) or {}).get("details") or {}).get("intro") or {}
        first = next(iter(intro.get("summary") or ()), None)
        return first.get("text") if isinstance(first, dict) else None

    def weather(self, day: date) -> dict:
        """Rain chance for `day` at the city centre; {"error": "weather unavailable"} when live gives nothing."""
        iso = day.isoformat()
        try:
            row = self.live.weather(self.center[1], self.center[2], [iso])[iso] if self.live.weather else None
        except Exception:  # live.Unavailable, a timeout, a missing day: the assistant says it has no data
            row = None
        if not isinstance(row, dict):
            return {"error": "weather unavailable"}
        out = {"date": iso, **{k: row[k] for k in WEATHER_KEYS if row.get(k) is not None}}
        for k in ("tmin_c", "tmax_c", "gust_kmh"):  # whole numbers: what a reply says is what the result holds
            if isinstance(out.get(k), float):
                out[k] = round(out[k])
        if "tmin_c" not in out and "tmax_c" not in out:  # beyond the forecast: the month's long-run temperatures, said as such
            try:
                c = self.more.climate(day.month)
                if c.get("tmin_c") is not None or c.get("tmax_c") is not None:
                    out["usual_temp_of_month"] = {k: round(c[k]) for k in ("tmin_c", "tmax_c") if c.get(k) is not None}
            except Exception:  # no climate feed: the rain figures alone
                pass
        return out

    def _point(self, ref: str) -> tuple[str, tuple[float, float]]:
        if ref == "center":
            return self.center[0], (self.center[1], self.center[2])
        place = self.catalog.by_id.get(ref)
        if place is None or place.lat is None or place.lng is None:
            raise ValueError(f"unknown place {ref!r}: use an id a read tool returned, or \"center\"")
        return place.name, (place.lat, place.lng)

    def distance(self, a: str, b: str, mode: str | None = None) -> dict:
        """Travel minutes between two places (ids or "center") by road (OSRM), with the straight-line km. mode walk |
        motorbike | car times that way of travel (a walk is an estimate from the road length); none = the default vehicle."""
        try:
            (na, pa), (nb, pb) = self._point(a), self._point(b)
        except ValueError as e:
            return {"error": str(e)}
        if mode is not None:
            try:
                return {"from": na, "to": nb, "mode": mode, "km_line": _km_line(pa, pb), **self.more.leg(pa, pb, mode)}
            except ValueError as e:
                return {"error": str(e)}
        try:
            out = self.live.matrix([pa, pb]) if self.live.matrix else None
            minutes = out["minutes"][0][1] if out else None
        except Exception:  # OSRM down or slow: no minutes, never a guess
            out, minutes = None, None
        if minutes is None:
            return {"error": "distance unavailable"}
        return {"from": na, "to": nb, "minutes": minutes, "km_line": _km_line(pa, pb), "source": out.get("source")}

    def km_line(self, a: str, b: str) -> float | None:
        """Straight-line km between two places (ids or "center"); None when one has no coordinates."""
        try:
            return _km_line(self._point(a)[1], self._point(b)[1])
        except ValueError:
            return None

    def _scene_urls(self, pid: str, first: str | None = None) -> list[str]:
        """Best photo per scene (no person, not blurry, de-duplicated; corpus.retrieval.scene_photos) as /media urls;
        [] when the place has no scene labels or the engine offers none, so the caller keeps the record photos.
        first: the scene the user asked to see, put in front."""
        read = getattr(self.retrieval, "scene_photos", None)
        if read is None:
            return []
        try:
            # a photo past the 3-year cap (`year`) is a card pick that must show its year: chat cards carry bare urls, so it is left out
            shots = sorted((p for p in read(pid) if not p.get("year")), key=lambda p: p.get("scene") != first)  # stable: the scene order stays after it
            return [media_url(p["file"]) for p in shots[:MAX_PHOTOS] if p.get("file")]
        except Exception:  # labels unreadable: display falls back to the record photos, never an error in chat
            return []

    def scene_cover(self, pid: str, scenes: Sequence[str]) -> str | None:
        """The place's best photo of these scenes as a /media url, None when it has none (a tag card's cover)."""
        read = getattr(self.retrieval, "scene_photos", None)
        if read is None or not scenes:
            return None
        try:
            return next((media_url(p["file"]) for p in read(pid) if p.get("scene") in scenes and p.get("file") and not p.get("year")), None)
        except Exception:  # labels unreadable: the card keeps its plain photo
            return None

    def view(self, pid: str, today: date | None = None, liked: bool = False, scene: str | None = None) -> dict | None:
        """A place card in the chat: every field copied from the serving record, null when the record has none."""
        record = self.retrieval.get_place(pid)
        if not record:
            return None
        ident, op = record.get("identity") or {}, record.get("operation") or {}
        hours = op.get("hours") or {}
        day = DAYS[(today or date.today()).weekday()]
        windows = (hours.get("value") or {}).get(day) if hours.get("status") in ("VERIFIED", "OUTDATED") else None
        price = (op.get("price_per_person") or {}).get("value") or {}
        return {"id": pid, "name": ident.get("name"), "category": ident.get("category"), "area": ident.get("area"),
                "rating": ident.get("rating"), "reviews": ident.get("reviews"), "photos": self._scene_urls(pid, scene) or _photos(record),
                "hours_today": ", ".join(f"{a}-{b}" for a, b in windows) if windows else None,
                "price": [price["min_vnd"], price["max_vnd"]]
                if price.get("min_vnd") is not None and price.get("max_vnd") is not None else None,
                "liked": liked}


DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_PHOTOS = 5


def _photos(record: dict) -> list[str]:
    """Up to MAX_PHOTOS photo urls of the record, one per scene first when the photos carry a scene label."""
    photos = [p for p in ((record.get("media") or {}).get("photos") or []) if isinstance(p, dict) and p.get("url")]
    seen, first, rest = set(), [], []
    for p in photos:
        scene = p.get("scene")
        (first if scene is not None and scene not in seen else rest).append(p["url"])
        seen.add(scene)
    return (first + rest)[:MAX_PHOTOS]
