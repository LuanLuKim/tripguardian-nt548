"""The navigator's mining map and general claims (docs/CORPUS.md, sol dẫn đường).

sol answers in a flat strict JSON schema (corpus.llm NAVIGATOR_PLAN); `parse_answer` is the gate that turns the answer
into a MiningMap. Anything that breaks the shape is dropped and listed in `rejected` with the reason: sol decides what
to mine, code decides what is well-formed.
"""

import hashlib
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

from ..llm import NAVIGATOR_ASPECT_SOURCES, NAVIGATOR_DAY_TYPES, NAVIGATOR_SUBJECT_KINDS, NAVIGATOR_WEATHER

ASPECT_LIMIT = 40
CLAIM_LIMIT = 40
QUERY_LIMIT = 8
QUERY_LEN = (3, 120)
NOMINEE_LIMIT = 15
NOMINEE_LEN = (2, 80)
CLAIM_TEXT_MAX = 300
CATEGORY_VALUES = (2, 6)
RATING_VALUES = ["good", "mixed", "poor"]

KEY = re.compile(r"^[a-z][a-z0-9_]{2,39}$")
VALUE = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
HOURS = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d-([01]?\d|2[0-3]):[0-5]\d$")

TargetKind = Literal["feature", "local_claim", "media", "new_feature"]
ClaimKind = Literal["best_time", "crowded_at", "avoid", "specialty", "price_norm", "access", "if_rain", "season",
                    "event", "notice", "tip"]


def fold(text: str) -> str:
    """Lower case, no diacritics, single spaces: the key for comparing what sol wrote with what the corpus holds."""
    nfd = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    plain = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain.lower()).split())


class NewFeature(BaseModel):
    key: str
    type: Literal["presence", "rating", "category"]
    values: list[str]
    hint: str


class Target(BaseModel):
    kind: TargetKind
    ref: str
    new_feature: NewFeature | None = None


class Nominee(BaseModel):
    name: str
    area_hint: str = ""


class Aspect(BaseModel):
    key: str
    name_vi: str
    why: str
    target: Target
    queries: list[str]
    sources: list[str]
    nominees: list[Nominee]
    months: list[int]


class When(BaseModel):
    months: list[int] = Field(default_factory=list)  # [] = all year
    days: list[Literal["weekday", "weekend", "holiday"]] = Field(default_factory=list)
    hours: str = ""  # "" or "05:00-08:00"
    weather: Literal["", "sunny", "rainy", "foggy", "cold"] = ""


class GeneralClaim(BaseModel):
    """What sol knows about the city, kept as a LocalClaim with source = "model" (corpus P4 gives the status). Never a
    fact about one venue: subject_kind has no `poi`."""
    claim_id: str
    subject_kind: Literal["city", "area", "dish", "phenomenon"]
    subject: str
    kind: ClaimKind
    text: str
    when: When
    source: Literal["model"] = "model"


class Rejected(BaseModel):
    path: str
    reason: str


class MiningMap(BaseModel):
    city: str
    generated_at: str
    model: str
    aspects: list[Aspect]
    general_claims: list[GeneralClaim]
    rejected: list[Rejected] = Field(default_factory=list)


def claim_id(subject_kind: str, subject: str, kind: str, text: str) -> str:
    return hashlib.sha1("|".join((subject_kind, fold(subject), kind, fold(text))).encode()).hexdigest()[:12]


def _clean(items, low: int, high: int, limit: int) -> list[str]:
    out, seen = [], set()
    for raw in items or []:
        text = " ".join(str(raw).split())
        if low <= len(text) <= high and fold(text) not in seen:
            seen.add(fold(text))
            out.append(text)
    return out[:limit]


def _months(items) -> list[int]:
    return sorted({m for m in items or [] if isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= 12})


class _Reject(Exception):
    pass


def _new_feature(raw: dict) -> NewFeature:
    key, kind, values = raw.get("key", ""), raw.get("type", "none"), raw.get("values") or []
    hint = " ".join(str(raw.get("hint", "")).split())
    if not KEY.match(key):
        raise _Reject(f"new_feature key {key!r} is not snake_case English")
    if not hint:
        raise _Reject("new_feature has no hint")
    if kind == "presence" and values != ["present"]:
        raise _Reject("a presence feature has values [present] only")
    elif kind == "rating" and values != RATING_VALUES:
        raise _Reject("a rating feature has values [good, mixed, poor]")
    elif kind == "category":
        if not CATEGORY_VALUES[0] <= len(values) <= CATEGORY_VALUES[1] or len(set(values)) != len(values) \
                or not all(VALUE.match(v) for v in values):
            raise _Reject("a category feature has 2-6 distinct snake_case values")
    elif kind not in ("presence", "rating", "category"):
        raise _Reject("new_feature type must be presence, rating or category")
    return NewFeature(key=key, type=kind, values=list(values), hint=hint)


def _aspect(raw: dict, seen: set[str]) -> Aspect:
    key = raw.get("key", "")
    if not isinstance(key, str) or not KEY.match(key):
        raise _Reject(f"key {key!r} is not snake_case English (3-40 chars)")
    if key in seen:
        raise _Reject(f"duplicate key {key!r}")
    name_vi, why = " ".join(str(raw.get("name_vi", "")).split()), " ".join(str(raw.get("why", "")).split())
    if not name_vi or not why:
        raise _Reject("name_vi and why must not be empty")
    t = raw.get("target") or {}
    kind, ref = t.get("kind"), " ".join(str(t.get("ref", "")).split())
    feature = None
    if kind == "new_feature":
        feature = _new_feature(t.get("new_feature") or {})
        ref = feature.key
    elif kind == "feature":
        if not KEY.match(ref):
            raise _Reject(f"feature ref {ref!r} is not snake_case English")
    elif kind == "local_claim":
        if ref not in ClaimKind.__args__:
            raise _Reject(f"local_claim ref {ref!r} is not a LocalClaim kind")
    elif kind == "media":
        if not ref:
            raise _Reject("media target has no scene name")
    else:
        raise _Reject(f"target kind {kind!r} is not one of {TargetKind.__args__}")
    queries = _clean(raw.get("queries"), *QUERY_LEN, QUERY_LIMIT)
    if not queries:
        raise _Reject("no usable query left")
    names = [(n or {}) for n in raw.get("nominees") or [] if isinstance(n, dict)]
    nominee_names = _clean([n.get("name", "") for n in names], *NOMINEE_LEN, NOMINEE_LIMIT)
    hints = {fold(n.get("name", "")): " ".join(str(n.get("area_hint", "")).split())[:NOMINEE_LEN[1]] for n in names}
    sources = [s for s in dict.fromkeys(raw.get("sources") or []) if s in NAVIGATOR_ASPECT_SOURCES]
    return Aspect(key=key, name_vi=name_vi, why=why, target=Target(kind=kind, ref=ref, new_feature=feature),
                  queries=queries, sources=sources,
                  nominees=[Nominee(name=n, area_hint=hints.get(fold(n), "")) for n in nominee_names],
                  months=_months(raw.get("months")))


def _claim(raw: dict, nominees: set[str], seen: set[str]) -> GeneralClaim:
    subject_kind, subject, kind = raw.get("subject_kind"), " ".join(str(raw.get("subject", "")).split()), raw.get("kind")
    text = " ".join(str(raw.get("text", "")).split())
    if subject_kind not in NAVIGATOR_SUBJECT_KINDS:
        raise _Reject(f"subject_kind {subject_kind!r} is not city, area, dish or phenomenon")
    if kind not in ClaimKind.__args__:
        raise _Reject(f"kind {kind!r} is not a LocalClaim kind")
    if not subject or not text or len(text) > CLAIM_TEXT_MAX:
        raise _Reject(f"subject and text are required, text at most {CLAIM_TEXT_MAX} characters")
    if fold(subject) in nominees:
        raise _Reject("the subject is a nominated venue, not general knowledge")
    w = raw.get("when") or {}
    hours = str(w.get("hours", "")).strip()
    if hours and not HOURS.match(hours):
        raise _Reject(f"hours {hours!r} is not HH:MM-HH:MM")
    weather = w.get("weather", "")
    if weather not in NAVIGATOR_WEATHER:
        raise _Reject(f"weather {weather!r} is not allowed")
    cid = claim_id(subject_kind, subject, kind, text)
    if cid in seen:
        raise _Reject("duplicate claim")
    return GeneralClaim(claim_id=cid, subject_kind=subject_kind, subject=subject, kind=kind, text=text,
                        when=When(months=_months(w.get("months")), hours=hours, weather=weather,
                                  days=[d for d in dict.fromkeys(w.get("days") or []) if d in NAVIGATOR_DAY_TYPES]))


def parse_answer(city: str, raw: dict, model: str, generated_at: str) -> MiningMap:
    """The gate: sol's answer -> MiningMap. Raises nothing for a malformed item; the item is listed in `rejected`."""
    aspects, claims, rejected, keys = [], [], [], set()
    for i, item in enumerate(raw.get("aspects") or []):
        path = f"aspects[{i}]"
        if len(aspects) >= ASPECT_LIMIT:
            rejected.append(Rejected(path=path, reason=f"over the limit of {ASPECT_LIMIT} aspects"))
            continue
        try:
            aspect = _aspect(item, keys)
        except _Reject as e:
            rejected.append(Rejected(path=path, reason=str(e)))
            continue
        keys.add(aspect.key)
        aspects.append(aspect)
    nominees = {fold(n.name) for a in aspects for n in a.nominees}
    seen: set[str] = set()
    for i, item in enumerate(raw.get("general_claims") or []):
        path = f"general_claims[{i}]"
        if len(claims) >= CLAIM_LIMIT:
            rejected.append(Rejected(path=path, reason=f"over the limit of {CLAIM_LIMIT} claims"))
            continue
        try:
            claim = _claim(item, nominees, seen)
        except _Reject as e:
            rejected.append(Rejected(path=path, reason=str(e)))
            continue
        seen.add(claim.claim_id)
        claims.append(claim)
    return MiningMap(city=city, generated_at=generated_at, model=model, aspects=aspects, general_claims=claims,
                     rejected=rejected)
