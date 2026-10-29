"""find: filter and rank the places of one snapshot Region by structured criteria, for agents (no model on the hot path).

Hard criteria (`must`) fail closed: only VERIFIED / OUTDATED values pass; an UNCERTAIN value goes to `maybe`; a place with
no evidence for a `must` is counted in `unknown` and never returned. Hours are read from the serving record; a place whose
hours are not VERIFIED / OUTDATED never passes an hours filter. Lodging (`stay`) is returned only when asked for.
"""

from __future__ import annotations

import math
import re
import threading
import weakref
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ..categories import defaults as category_defaults
from ..ontology import Feature, Ontology
from ..serving import dishes as menu
from .card import DAYS, FIRM, card

FIT = "fit."
FIT_VALUES = ("good", "bad", "conditional")
STAY = "stay"
MONTH_BONUS = 0.3
VOICES_WEIGHT = 0.05
NO_CONF_BONUS = 0.5  # a firm prefer match whose row has no confidence (fit.<who>)
LABEL_MAX = 80
EARTH_KM = 6371.0088
KEYS = ("groups", "must", "prefer", "open_at", "opens_by", "dish", "month", "near", "text")


@dataclass(frozen=True)
class Criteria:
    groups: tuple[str, ...] = ()       # category_group; () = every group except stay
    must: tuple[tuple[str, str], ...] = ()    # (fid, value) hard filter; fid may be "fit.<who>"
    prefer: tuple[tuple[str, str], ...] = ()  # (fid, value) adds score
    open_at: tuple[str, str] | None = None    # ("sat", "06:00"): open at that moment
    opens_by: str | None = None        # "06:00": opens at or before this time on at least one day
    dish: str | None = None            # a menu dish name has these words (case ignored; accents ignored unless typed)
    month: int | None = None           # 1..12: + if in best_months, - if in avoid_months
    near: tuple[float, float, float] | None = None  # (lat, lng, km)
    text: str | None = None            # RetrievalEngine.semantic on the filtered set

    @classmethod
    def parse(cls, raw: dict, ont: Ontology) -> "Criteria":
        """Criteria from a plain dict (an agent's tool call); ValueError on any key, feature, value, group, day, time or
        month that is not valid."""
        if not isinstance(raw, dict):
            raise ValueError("criteria must be an object")
        if extra := sorted(set(raw) - set(KEYS)):
            raise ValueError(f"unknown criteria {extra}; valid: {list(KEYS)}")
        known = {g["id"] for g in category_defaults()["groups"]}
        groups = tuple(raw.get("groups") or ())
        if bad := [g for g in groups if g not in known]:
            raise ValueError(f"unknown group {bad}; valid: {sorted(known)}")
        opens_by = raw.get("opens_by")
        if opens_by is not None:
            _minutes(opens_by)
        open_at = raw.get("open_at")
        if open_at is not None:
            if not isinstance(open_at, (list, tuple)) or len(open_at) != 2 or open_at[0] not in DAYS:
                raise ValueError(f"open_at must be [day, 'HH:MM'] with day in {list(DAYS)}")
            _minutes(open_at[1])
            open_at = (open_at[0], open_at[1])
        month = raw.get("month")
        if month is not None and (isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12):
            raise ValueError("month must be an integer 1..12")
        near = raw.get("near")
        if near is not None:
            try:
                lat, lng, km = (float(x) for x in near)
            except (TypeError, ValueError):
                raise ValueError("near must be [lat, lng, km]") from None
            if not (-90 <= lat <= 90 and -180 <= lng <= 180 and km > 0):
                raise ValueError("near: lat -90..90, lng -180..180, km > 0")
            near = (lat, lng, km)
        for key in ("dish", "text"):
            if raw.get(key) is not None and not (isinstance(raw[key], str) and raw[key].strip()):
                raise ValueError(f"{key} must be a non-empty string")
        return cls(groups, _pairs(raw.get("must"), "must", ont), _pairs(raw.get("prefer"), "prefer", ont), open_at,
                   opens_by, raw.get("dish"), month, near, raw.get("text"))


@dataclass(frozen=True)
class FindHit:
    place_id: str
    score: float
    matched: tuple[str, ...]  # "fid=value" of each prefer that matched, "dish:<name>", "month", "text"
    card: dict


@dataclass(frozen=True)
class FindResult:
    hits: tuple[FindHit, ...]   # pass every `must` with a VERIFIED / OUTDATED value
    maybe: tuple[FindHit, ...]  # pass the other filters; at least one `must` is only UNCERTAIN (at most `limit`)
    unknown: int                # places dropped only because at least one `must` has no evidence
    release_id: str | None


def _minutes(text) -> int:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text) if isinstance(text, str) else None
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        raise ValueError(f"time must be 'HH:MM' 00:00..23:59, got {text!r}")
    return int(m[1]) * 60 + int(m[2])


def _range_minutes(text) -> int | None:
    """Minutes of a stored time; '24:00' is the end of the day. None when unreadable (the range is then ignored)."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text) if isinstance(text, str) else None
    if not m or int(m[2]) > 59 or (int(m[1]) * 60 + int(m[2])) > 1440:
        return None
    return int(m[1]) * 60 + int(m[2])


def _pairs(raw, name: str, ont: Ontology) -> tuple[tuple[str, str], ...]:
    out = []
    for item in raw or ():
        if not isinstance(item, (list, tuple)) or len(item) != 2 or not all(isinstance(x, str) for x in item):
            raise ValueError(f"{name} items must be [feature, value]")
        fid, value = item
        if fid.startswith(FIT):
            if fid[len(FIT):] not in ont.companions or value not in FIT_VALUES:
                raise ValueError(f"{name}: {fid}={value} invalid; who in {list(ont.companions)}, value in {list(FIT_VALUES)}")
        elif not ont.valid(fid, value):
            feature = ont.features.get(fid)
            raise ValueError(f"{name}: unknown feature {fid}" if feature is None
                             else f"{name}: {fid} has no value {value!r}; valid: {list(feature.values)}")
        out.append((fid, value))
    return tuple(out)


# ---------------------------------------------------------------------------
# Per-region cache: what a filter needs from a record, read once
# ---------------------------------------------------------------------------

class _Cache:
    def __init__(self, region):
        ids = region.ids
        n = len(ids)
        self.n = n
        self.group = np.array([g or "" for g in region.column("category_group")])
        self.lat = np.array([np.nan if x is None else x for x in region.column("lat")], dtype=np.float64)
        self.lng = np.array([np.nan if x is None else x for x in region.column("lng")], dtype=np.float64)
        voices = np.array([v or 0 for v in region.column("voices")], dtype=np.float64)
        self.voices = voices
        self.voices_score = VOICES_WEIGHT * np.log1p(voices)
        order = sorted(range(n), key=ids.__getitem__)
        self.id_rank = np.empty(n, dtype=np.int64)
        self.id_rank[order] = np.arange(n)
        self.eq: dict[tuple[str, str], np.ndarray] = {}
        seg = {d: ([], [], []) for d in range(7)}  # per day: place index, start, end (minutes, end exclusive)
        self.first_open = np.full(n, np.inf)
        self.best = np.zeros(n, dtype=np.uint16)
        self.avoid = np.zeros(n, dtype=np.uint16)
        self.dishes: list[tuple[str, ...]] = []  # dish statements as written (corpus.serving.dishes.rows_of)
        self.dish_blob = {False: [], True: []}   # per place, folded (no accents) / accent-kept names, " | " apart
        for i, pid in enumerate(ids):
            rec = region.record(pid) or {}
            hours = (rec.get("operation") or {}).get("hours") or {}
            if hours.get("status") in FIRM:
                for d, day in enumerate(DAYS):
                    for rng in (hours.get("value") or {}).get(day) or ():
                        a, b = (_range_minutes(x) for x in rng) if len(rng) == 2 else (None, None)
                        if a is None or b is None or a == b:
                            continue
                        self.first_open[i] = min(self.first_open[i], a)
                        if a < b:
                            _put(seg[d], i, a, b)
                        else:  # runs past midnight: the rest of today and the start of tomorrow
                            _put(seg[d], i, a, 1440)
                            _put(seg[(d + 1) % 7], i, 0, b)
            timing = (rec.get("details") or {}).get("timing") or {}
            for bits, key in ((self.best, "best_months"), (self.avoid, "avoid_months")):
                for m in timing.get(key) or ():
                    if isinstance(m, int) and 1 <= m <= 12:
                        bits[i] |= 1 << m
            names = tuple(t for _, texts in menu.rows_of(rec) for t in texts)  # menu dishes, a dish-named eatery, orders
            self.dishes.append(names)
            for accented, blobs in self.dish_blob.items():
                blobs.append(" " + " | ".join(menu.key_for(x, accented) for x in names) + " ")
        self.seg = {d: tuple(np.array(x, dtype=dt) for x, dt in zip(cols, (np.int64, np.int32, np.int32)))
                    for d, cols in seg.items()}

    def eq_mask(self, region, fid: str, value: str) -> np.ndarray:
        key = (fid, value)
        if key not in self.eq:
            self.eq[key] = region.feature(fid).eq(value)
        return self.eq[key]


def _put(seg, i, a, b):
    seg[0].append(i)
    seg[1].append(a)
    seg[2].append(b)


_CACHES: dict[int, tuple[weakref.ref, _Cache]] = {}
_LOCK = threading.Lock()


def _cache(region) -> _Cache:
    entry = _CACHES.get(id(region))
    if entry is not None and entry[0]() is region:
        return entry[1]
    with _LOCK:
        entry = _CACHES.get(id(region))
        if entry is None or entry[0]() is not region:
            key = id(region)
            _CACHES[key] = (weakref.ref(region, lambda _r, k=key: _CACHES.pop(k, None)), _Cache(region))
        return _CACHES[id(region)][1]


def warm(region) -> None:
    """Build the region's hours, dish and month cache now, so the first find does not pay for it."""
    _cache(region)


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------

def _haversine_km(lat0: float, lng0: float, lat: np.ndarray, lng: np.ndarray) -> np.ndarray:
    p0, p = math.radians(lat0), np.radians(lat)
    a = np.sin((p - p0) / 2) ** 2 + math.cos(p0) * np.cos(p) * np.sin(np.radians(lng - lng0) / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(a))


def _candidates(region, c: _Cache, q: Criteria) -> np.ndarray:
    mask = np.isin(c.group, q.groups) if q.groups else c.group != STAY
    if q.near is not None:
        lat, lng, km = q.near
        with np.errstate(invalid="ignore"):
            mask &= _haversine_km(lat, lng, c.lat, c.lng) <= km  # NaN (no coordinates) compares False
    if q.open_at is not None:
        day, hhmm = q.open_at
        idx, a, b = c.seg[DAYS.index(day)]
        t = _minutes(hhmm)
        open_now = np.zeros(c.n, dtype=bool)
        open_now[idx[(a <= t) & (t < b)]] = True
        mask &= open_now
    if q.opens_by is not None:
        mask &= c.first_open <= _minutes(q.opens_by)
    if q.dish is not None:
        wanted, accented = menu.phrases(q.dish)
        blobs = c.dish_blob[accented]
        keep = np.flatnonzero(mask)
        mask = np.zeros(c.n, dtype=bool)
        mask[[i for i in keep if any(f" {w} " in blobs[i] for w in wanted)]] = True
    return mask


def _rank(c: _Cache, idx: np.ndarray, score: np.ndarray, limit: int) -> np.ndarray:
    order = np.lexsort((c.id_rank[idx], -c.voices[idx], -score[idx]))
    return idx[order[:limit]]


def find(region, criteria: Criteria, *, limit: int = 8, semantic: Callable | None = None,
         release_id: str | None = None) -> FindResult:
    """Places of `region` that pass `criteria`, best first. `semantic(text, within=ids, limit=k)` ranks the filtered set
    when `criteria.text` is given; it is never called for an empty set."""
    c = _cache(region)
    alive = _candidates(region, c, criteria)
    uncertain = np.zeros(c.n, dtype=bool)
    unmeasured = np.zeros(c.n, dtype=bool)
    dead = np.zeros(c.n, dtype=bool)
    for fid, value in criteria.must:
        col, eq = region.feature(fid), c.eq_mask(region, fid, value)
        unc_eq = col.uncertain & eq
        dead |= col.exists & ~((col.firm & eq) | unc_eq)
        unmeasured |= ~col.exists
        uncertain |= unc_eq
    alive &= ~dead
    unknown = int((alive & unmeasured).sum())
    alive &= ~unmeasured
    score = c.voices_score.copy()
    prefer_hit: list[tuple[str, np.ndarray]] = []
    for fid, value in criteria.prefer:
        col = region.feature(fid)
        match = col.firm & c.eq_mask(region, fid, value)
        score += np.where(match, np.where(col.conf > 0, col.conf, NO_CONF_BONUS), 0.0)
        prefer_hit.append((f"{fid}={value}", match))
    month_hit = None
    if criteria.month is not None:
        month_hit = (c.best >> criteria.month) & 1 == 1
        score += MONTH_BONUS * month_hit - MONTH_BONUS * (((c.avoid >> criteria.month) & 1) == 1)
    text_hit: set[int] = set()
    scope = np.flatnonzero(alive)
    if criteria.text and semantic is not None and len(scope):
        best: dict[str, float] = {}
        for h in semantic(criteria.text, within={region.ids[i] for i in scope}, limit=max(limit * 4, 32)):
            best[h.place_id] = max(best.get(h.place_id, 0.0), h.score)
        for pid, s in best.items():
            i = region.index.get(pid)
            if i is not None and alive[i]:
                score[i] += s
                text_hit.add(i)

    def hits(idx: np.ndarray) -> tuple[FindHit, ...]:
        out = []
        wanted, accented = menu.phrases(criteria.dish) if criteria.dish else (frozenset(), False)
        for i in _rank(c, idx, score, limit):
            matched = [label for label, m in prefer_hit if m[i]]
            if wanted:
                matched += [f"dish:{x}" for x in c.dishes[i]
                            if any(menu.has_phrase(menu.key_for(x, accented), w) for w in wanted)][:1]
            if month_hit is not None and month_hit[i]:
                matched.append("month")
            if i in text_hit:
                matched.append("text")
            pid = region.ids[i]
            out.append(FindHit(pid, float(score[i]), tuple(matched), card(region.record(pid))))
        return tuple(out)

    return FindResult(hits(np.flatnonzero(alive & ~uncertain)), hits(np.flatnonzero(alive & uncertain)), unknown,
                      release_id)


# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------

def _label(feature: Feature) -> str:
    """What the feature means, in a few words: its only claim, else the hint up to the first '.' or ':'."""
    text = next(iter(feature.claims.values())) if len(feature.claims) == 1 else re.split(r"[.:]", feature.hint, 1)[0]
    text = text.strip()
    return text if len(text) <= LABEL_MAX else text[:LABEL_MAX - 1].rstrip() + "…"


def vocabulary(ont: Ontology, region) -> dict:
    """What `find` accepts for this region: groups with their place counts, features with values and a short label, and
    the companions behind `fit.<who>`."""
    counts = Counter(g for g in region.column("category_group") if g)
    return {"groups": dict(counts.most_common()),
            "features": {fid: {"values": list(f.values), "label": _label(f)} for fid, f in ont.features.items()},
            "companions": {cid: comp.vi for cid, comp in ont.companions.items()}}
