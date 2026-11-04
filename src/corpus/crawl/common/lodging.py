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

import yaml

from .files import ROOT, STAY, append_jsonl, data_dir, load_config, now

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
GENERIC = {"khach", "san", "hotel", "dalat"}  # words every lodging carries: they say nothing about which one
KINDS = {"homestay", "house", "home", "villa", "resort", "apartment", "apart", "hostel", "boutique", "motel", "inn",
         "lodge", "bungalow", "spa"}  # kinds of lodging: two names alike only in these are two lodgings
NOT_DRAWN_H = 6  # a page whose offers never drew is looked at again after this many hours
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


def holiday_runs(path=None) -> list[tuple[date, int]]:
    """(first day, length) of each run of consecutive days in config/holidays.yaml, oldest first."""
    path = path or ROOT / "config" / "holidays.yaml"
    days = sorted(date.fromisoformat(str(d)) for d in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("holidays", {}))
    runs: list[list] = []
    for d in days:
        if runs and d - timedelta(days=runs[-1][1]) == runs[-1][0]:
            runs[-1][1] += 1
        else:
            runs.append([d, 1])
    return [(d, n) for d, n in runs]


def stay_dates(cfg: dict, today: date | None = None, holidays: list[tuple[date, int]] | None = None) -> list[Stay]:
    """The date set from config rules, in rule order (= priority: the first is the probe date), without duplicates.
    Tonight's price is gone by the time anyone plans, so no stay starts today. A rule is one of
      {weekday, count, nights}  the next `count` such weekdays after today
      {ahead_days, nights[, weekday]}  the stay that starts that many days from today (the first such weekday on or
                                after it when `weekday` is given)
      {holidays, within_days, nights, count}  the first `count` public-holiday runs that start within that many days;
                                the stay begins the evening before the run and lasts `nights` at most (run length + 1)"""
    today = today or date.today()
    adults = int(cfg.get("adults", 2))
    out: list[Stay] = []

    def add(checkin: date, nights: int) -> None:
        stay = Stay(checkin, nights, adults)
        if checkin > today and stay not in out:
            out.append(stay)

    for rule in cfg["stays"]:
        if "count" in rule and "weekday" in rule:
            first = today + timedelta(days=1)
            first += timedelta(days=(WEEKDAYS[rule["weekday"]] - first.weekday()) % 7)
            for i in range(int(rule["count"])):
                add(first + timedelta(days=7 * i), int(rule["nights"]))
        elif "ahead_days" in rule:
            day = today + timedelta(days=int(rule["ahead_days"]))
            if "weekday" in rule:
                day += timedelta(days=(WEEKDAYS[rule["weekday"]] - day.weekday()) % 7)
            add(day, int(rule["nights"]))
        elif rule.get("holidays"):
            runs = holiday_runs() if holidays is None else holidays
            coming = [(d, n) for d, n in runs if today < d <= today + timedelta(days=int(rule["within_days"]))]
            for d, n in coming[: int(rule.get("count", 1))]:
                add(d - timedelta(days=1), min(int(rule["nights"]), n + 1))
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


def _numbers(name: str, city_name: str) -> set[str]:
    return {t for t in fold(name, city_name).split() if t.isdigit()}


def match(name: str, lat: float | None, lng: float | None, stays: list[dict], city_name: str, cfg: dict) -> Match:
    """The corpus lodging a result is: near by name and distance, never by name alone (branches share names). A pin
    up to far_m away still counts when the name is near-exact (OTA pins drift). Two lodgings that fit equally well,
    or one name that contains the other, are ambiguous: no match, unless one of them is the exact name (the same name
    after folding, within max_m). Branch numbers must agree when both names have one ("Thanh Thanh 2" is not "Thanh Thanh 5"). Names with no word
    in common still count when they are the same letters run together ("Du Parc" / "Duparc")."""
    if lat is None or lng is None or not fold(name, city_name):
        return Match(None, 0.0, None)
    found, words, nums = [], set(fold(name, city_name).split()), _numbers(name, city_name)
    squashed = fold(name, city_name).replace(" ", "")
    for s in stays:
        if s.get("lat") is None or s.get("lng") is None:
            continue
        d = meters(lat, lng, s["lat"], s["lng"])
        their_nums = _numbers(s["name"], city_name)
        if d > cfg["far_m"] or (nums and their_nums and nums != their_nums):
            continue
        theirs = fold(s["name"], city_name)
        if not (words & set(theirs.split()) - KINDS) and difflib.SequenceMatcher(None, squashed, theirs.replace(" ", "")).ratio() < 0.9:
            continue  # a name sharing no word (other than the kind of lodging) is another lodging, however alike the letters look
        score = max(similarity(name, s["name"], city_name),
                    round(difflib.SequenceMatcher(None, squashed, theirs.replace(" ", "")).ratio(), 4))
        if (d <= cfg["max_m"] and score >= cfg["min_score"]) or score >= cfg["far_score"]:
            found.append((score, d, s))
    if not found:
        return Match(None, 0.0, None)
    found.sort(key=lambda f: (-f[0], f[1]))
    best = found[0]
    bt = set(fold(best[2]["name"], city_name).split())
    exact = best[0] == 1.0 and best[1] <= cfg["max_m"] and found[1:] and all(f[0] < 1.0 for f in found[1:])
    for score, _, s in found[1:]:
        tokens = set(fold(s["name"], city_name).split())
        if exact:
            break
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


def queue(fids: list[str], stays: list[Stay], rows: dict, fresh_h: float, no_offer_h: float, dead_h: float,
          now: str | None = None) -> list[tuple[str, Stay]]:
    """(fid, stay) pairs to look at, best first. `fids` come best first (the ones users see), `stays[0]` is the probe
    date; `rows` is latest(source, city). One fid at a time goes through these tiers, tier by tier across all fids:
      0  never looked at: the probe date only (coverage first: every lodging gets one look before any gets two)
      1  looked at but no price yet and fewer than 2 dates with "no offer": one more date, so a lodging that
         simply has no rooms on the probe date is not written off ("Chưa rõ" only after 2 different dates say so)
      2  has a price on some date: its other dates (never-seen first, then oldest) and priced ones older than fresh_h
      3  no price anywhere after 2 dates (no OTA listing): asked again once the last look is older than dead_h
    A page that wants a longer stay ("có phòng trống cho các khách lưu trú 2 đêm") adds that stay for the fid.
    A no-offer pair is asked again after no_offer_h, a page that was not drawn counts as no look (retry later)."""
    at = datetime.fromisoformat(now) if now else datetime.now(UTC)
    by_fid: dict[str, list[dict]] = {}
    for (fid, *_), r in rows.items():
        by_fid.setdefault(fid, []).append(r)
    todo = []
    for i, fid in enumerate(fids):
        mine = by_fid.get(fid, [])
        priced = any(r.get("price_night_vnd") for r in mine)
        looks = [r for r in mine if r.get("note") != "not_drawn"]
        no_offer_days = {r["stay_date"] for r in looks if not r.get("price_night_vnd") and not r.get("min_nights")}
        longer = [Stay(date.fromisoformat(r["stay_date"]), int(r["min_nights"]), int(r["adults"])) for r in mine
                  if r.get("min_nights") and int(r["min_nights"]) > int(r["nights"])]
        for j, stay in enumerate(stays + [x for x in longer if x not in stays]):
            if stay.checkin <= at.date():
                continue
            got = rows.get((fid, stay.checkin.isoformat(), stay.nights))
            age_h = (at - datetime.fromisoformat(got["observed_at"])).total_seconds() / 3600 if got else None
            if not looks:
                tier = 0 if j == 0 else None
            elif not priced and len(no_offer_days) < 2:
                tier = 1 if j > 0 or not got else None
            elif priced:
                tier = 2
            else:
                tier = 3 if j == 0 else None
            if tier is None:
                continue
            if got is not None:
                limit = fresh_h if got.get("price_night_vnd") else NOT_DRAWN_H if got.get("note") == "not_drawn" else no_offer_h
                if tier == 3 and got.get("note") != "not_drawn":
                    limit = dead_h
                if age_h < limit:
                    continue
            todo.append((tier, got["observed_at"] if got else "", i, j, fid, stay))
    todo.sort(key=lambda t: t[:4])
    return [(fid, stay) for *_, fid, stay in todo]
