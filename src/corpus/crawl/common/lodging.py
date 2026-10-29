"""Lodging price pieces shared by the sources that price a stay for given dates (gtravel, tripcom): the stay dates
from config, name fold + distance match against the corpus lodging, the observation store, and the refresh queue.

Observation row (data/<source>/<city>/observations.jsonl, append-only):
{fid, price_total_vnd, price_night_vnd, currency, available, stay_date (check-in), nights, adults, observed_at, source,
url, matched_name, match_score}. `available` is True when an offer with a price was seen and None when none was: a
page without an offer proves nothing about the room being sold out, so False is never written (RULE.md: unknown, not
false). A result that matches no corpus lodging goes to unmatched.jsonl and is never attached to a place.
"""

import difflib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from .files import STAY, append_jsonl, data_dir, load_config, now

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
GENERIC = {"khach", "san", "hotel", "dalat"}  # words every lodging carries: they say nothing about which one
REQUIRED = ("fid", "stay_date", "nights", "adults", "observed_at", "source")


@dataclass(frozen=True)
class Stay:
    checkin: date
    nights: int
    adults: int

    @property
    def checkout(self) -> date:
        return self.checkin + timedelta(days=self.nights)


@dataclass(frozen=True)
class Match:
    fid: str | None
    score: float
    meters: float | None


def settings(city: str) -> dict:
    """The `lodging_price:` block of config/queries.yaml."""
    cfg = load_config(city)[1].get("lodging_price")
    if not cfg:
        raise SystemExit("config/queries.yaml has no `lodging_price:` block")
    return cfg


def stay_dates(cfg: dict, today: date | None = None) -> list[Stay]:
    """The date set from config rules {weekday, count, nights}: the next `count` such weekdays after today (tonight's
    price is gone by the time anyone plans), in rule order, without duplicates."""
    today = today or date.today()
    out: list[Stay] = []
    for rule in cfg["stays"]:
        first = today + timedelta(days=1)
        first += timedelta(days=(WEEKDAYS[rule["weekday"]] - first.weekday()) % 7)
        for i in range(int(rule["count"])):
            stay = Stay(first + timedelta(days=7 * i), int(rule["nights"]), int(cfg.get("adults", 2)))
            if stay not in out:
                out.append(stay)
    return out


def ascii_fold(text: str) -> str:
    s = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def fold(name: str, city_name: str = "") -> str:
    """Name for comparison: no accents, case or punctuation, without the city name and the words every lodging has."""
    s = re.sub(r"[^a-z0-9]+", " ", ascii_fold(name)).strip()
    city = re.sub(r"[^a-z0-9]+", " ", ascii_fold(city_name)).strip()
    if city:
        s = re.sub(rf"\b{re.escape(city)}\b", " ", s)
    return " ".join(t for t in s.split() if t not in GENERIC)


def similarity(a: str, b: str, city_name: str = "") -> float:
    fa, fb = fold(a, city_name), fold(b, city_name)
    return round(difflib.SequenceMatcher(None, fa, fb).ratio(), 4) if fa and fb else 0.0


def meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(a))


def match(name: str, lat: float | None, lng: float | None, stays: list[dict], city_name: str, cfg: dict) -> Match:
    """The corpus lodging a result is: near by name and distance, never by name alone (branches share names). A pin
    up to far_m away still counts when the name is near-exact (OTA pins drift). Two lodgings that fit equally well,
    or one name that contains the other, are ambiguous: no match."""
    if lat is None or lng is None or not fold(name, city_name):
        return Match(None, 0.0, None)
    found, words = [], set(fold(name, city_name).split())
    for s in stays:
        if s.get("lat") is None or s.get("lng") is None:
            continue
        d = meters(lat, lng, s["lat"], s["lng"])
        if d > cfg["far_m"] or not words & set(fold(s["name"], city_name).split()):
            continue  # a name sharing no word is another lodging, however alike the letters look
        score = similarity(name, s["name"], city_name)
        if (d <= cfg["max_m"] and score >= cfg["min_score"]) or score >= cfg["far_score"]:
            found.append((score, d, s))
    if not found:
        return Match(None, 0.0, None)
    found.sort(key=lambda f: (-f[0], f[1]))
    best = found[0]
    bt = set(fold(best[2]["name"], city_name).split())
    for score, _, s in found[1:]:
        tokens = set(fold(s["name"], city_name).split())
        if score >= best[0] - cfg["margin"] or bt <= tokens or tokens <= bt:
            return Match(None, best[0], best[1])
    return Match(best[2]["fid"], best[0], round(best[1], 1))


def load_stays(city: str) -> list[dict]:
    """The city's lodging from the Maps stay list, best score first."""
    path = data_dir() / "gmaps" / "list" / f"{city}{STAY}.json"
    if not path.exists():
        raise SystemExit(f"no {path}; run `python -m corpus gmaps list --city {city}_stay` first")
    items = json.loads(path.read_text(encoding="utf-8"))["items"]
    return sorted(items, key=lambda r: -(r.get("score") or 0))


def _dir(source: str, city: str):
    return data_dir() / source / city


def check(row: dict) -> None:
    missing = [k for k in REQUIRED if row.get(k) in (None, "")]
    if missing:
        raise ValueError(f"observation without {', '.join(missing)}")
    total, night = row.get("price_total_vnd"), row.get("price_night_vnd")
    if total is None and night is None:
        if row.get("available") is not None:
            raise ValueError("an observation without a price has available=None: no offer is not 'sold out'")
        return
    if not (isinstance(total, int) and isinstance(night, int) and total > 0 and night > 0):
        raise ValueError("a priced observation has integer price_total_vnd and price_night_vnd > 0")
    if row.get("available") is not True:
        raise ValueError("a priced observation has available=True")


def append_observation(source: str, city: str, row: dict) -> None:
    check(row)
    append_jsonl(_dir(source, city) / "observations.jsonl", row)


def append_unmatched(source: str, city: str, row: dict) -> None:
    append_jsonl(_dir(source, city) / "unmatched.jsonl", {"at": now(), **row})


def latest(source: str, city: str) -> dict[tuple[str, str, int], dict]:
    """(fid, stay_date, nights) -> the newest observation (a later line wins a tie)."""
    path, out = _dir(source, city) / "observations.jsonl", {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            key = (r["fid"], r["stay_date"], int(r["nights"]))
            if key not in out or r["observed_at"] >= out[key]["observed_at"]:
                out[key] = r
        except (ValueError, KeyError, TypeError):
            continue
    return out


def seen(source: str, city: str) -> dict[tuple[str, str, int], tuple[str, bool | None]]:
    return {k: (r["observed_at"], r.get("available")) for k, r in latest(source, city).items()}


def due(fids: list[str], stays: list[Stay], seen_: dict, fresh_h: float, no_offer_h: float,
        now: str | None = None) -> list[tuple[str, Stay]]:
    """(fid, stay) pairs to look at again, never-seen first, then the oldest. A priced pair is due after fresh_h; one
    with no offer is asked again after no_offer_h (most such lodgings list no booking offer at all)."""
    at = datetime.fromisoformat(now) if now else datetime.now(UTC)
    todo = []
    for i, fid in enumerate(fids):
        for j, stay in enumerate(stays):
            got = seen_.get((fid, stay.checkin.isoformat(), stay.nights))
            if got is not None:
                age_h = (at - datetime.fromisoformat(got[0])).total_seconds() / 3600
                if age_h < (fresh_h if got[1] else no_offer_h):
                    continue
            todo.append(((got[0] if got else ""), i, j, fid, stay))
    todo.sort(key=lambda t: t[:3])
    return [(fid, stay) for *_, fid, stay in todo]
