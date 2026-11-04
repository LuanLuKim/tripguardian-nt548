"""Estimates of one place (docs/CORPUS.md §5): category group, visit time as a range, entry fee in VND.

config/category_defaults.yaml holds the per-category defaults. An estimate always says where it came from
(`source`): review evidence when enough people said it, the category default otherwise. Never a fact, never a hard
filter.
"""

import re
import statistics
from datetime import date, timedelta
from functools import cache

import yaml

from ..categories import defaults, group
from ..crawl.common.files import ROOT
from ..observe import distribution

# 150k, 150.000đ, 160.000 đồng, 50 nghìn, 120.000 vnd; a bare number is no price
_VND = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d{1,4})\s*(k\b|nghìn|ngàn|n\b|đ|đồng|vnđ|vnd|000)", re.I)
VND_MIN, VND_MAX = 5_000, 5_000_000



def amounts_vnd(text: str) -> list[int]:
    out = []
    for num, unit in _VND.findall(text or ""):
        digits = int(re.sub(r"[.,]", "", num))
        unit = unit.casefold()
        value = digits * 1000 if unit in ("k", "nghìn", "ngàn", "n") else digits * 1000 if unit == "000" else digits
        if unit in ("đ", "đồng", "vnđ", "vnd") and digits < 1000:  # "50đ" in speech means 50k
            value = digits * 1000
        if VND_MIN <= value <= VND_MAX:
            out.append(value)
    return out


TICKET = re.compile(r"vé|vào cổng|vào cửa|phí vào|phí tham quan|tham quan|cổng|ticket|entrance|admission|entry", re.I)
NOT_TICKET = re.compile(r"chụp|quay phim|gửi xe|giữ xe|đậu xe|thuê|massage|gội|/\s*kg|\d\s*kg", re.I)
CLAUSE = re.compile(r"[;\n]|[,.](?=\s)| - ")  # "160.000" and "50,000" stay whole
RECENT_DAYS = 730  # prices change: when enough recent quotes exist, older ones are left out
RECENT_MIN = 2


def ticket_amounts(quote: str) -> list[int]:
    """Amounts said next to a ticket word, clause by clause; a clause about photos, parking, rentals, a massage or
    food by weight is not an entry price."""
    out = []
    for clause in CLAUSE.split(quote or ""):
        if TICKET.search(clause) and not NOT_TICKET.search(clause):
            out += amounts_vnd(clause)
    return out


@cache
def enabled_bases() -> frozenset[str]:
    """Search evidence bases aggregate reads at all (config/gsearch.yaml: only those that passed the label gate)."""
    return frozenset(yaml.safe_load((ROOT / "config" / "gsearch.yaml").read_text(encoding="utf-8")).get("enabled_bases") or ())


@cache
def fact_bases() -> frozenset[str]:
    """Search evidence bases served as facts (config/gsearch.yaml: only those that passed the label gate)."""
    return frozenset(yaml.safe_load((ROOT / "config" / "gsearch.yaml").read_text(encoding="utf-8")).get("fact_bases") or ())


def _searched_price(searched: dict) -> dict:
    t, ev = searched["tickets"], searched["evidence"]
    adult = t["adult"]
    every = adult + (t.get("child") or [])
    return {"min_vnd": min(every), "typical_vnd": int(statistics.median_low(adult)), "max_vnd": max(adult), "n": len(adult),
            "source": ev["basis"], "fact": ev["basis"] in fact_bases(), "evidence": ev}


def entry_fee(observations: list[dict], ticket_usd: float | None = None,
              official: dict | None = None, searched: dict | None = None) -> dict | None:
    """Ticket price from the place's own website (official: {adult: [...], child: [...]} VND; typical = the median
    adult ticket, as sites also list combos and tours; min = the lowest ticket of anyone), else from the entry_fee paid quotes (per author the highest ticket amount: adults pay the most), the
    last RECENT_DAYS only when RECENT_MIN authors said it then, or, without any, from the Maps ticket box (US$)."""
    adult = (official or {}).get("adult") or []
    if adult:
        every = adult + ((official or {}).get("child") or [])
        return {"min_vnd": min(every), "typical_vnd": int(statistics.median_low(adult)), "max_vnd": max(adult), "n": len(adult),
                "source": "official"}
    if searched and searched.get("tickets") and searched["evidence"]["basis"] in fact_bases():
        return _searched_price(searched)
    found = {}
    for o in observations:
        if o["feature"] == "entry_fee" and o["value"] == "paid":
            xs = ticket_amounts(o["span"]["quote"])
            if xs:
                who = o.get("author") or o["id"]
                observed = o.get("observed_at") or ""
                observed = observed if len(observed) == 10 else ""
                found[who] = max(found.get(who, (0, ""))[0], max(xs)), max(found.get(who, (0, ""))[1], observed)
    if found:
        newest = max(d for _, d in found.values())
        if newest:
            cut = (date.fromisoformat(newest) - timedelta(days=RECENT_DAYS)).isoformat()
            recent = {w: v for w, v in found.items() if v[1] >= cut}
            found = recent if len(recent) >= RECENT_MIN else found
        xs = sorted(v for v, _ in found.values())
        if searched and searched.get("tickets") and searched["evidence"].get("domains", 1) >= 2:
            return _searched_price(searched)  # two pages agree on a price: better than a few reviewers' words
        return {"min_vnd": xs[0], "typical_vnd": int(statistics.median(xs)), "max_vnd": xs[-1], "n": len(xs),
                "source": "reviews"}
    if searched and searched.get("tickets"):
        return _searched_price(searched)
    if ticket_usd and defaults().get("maps_tickets_entry_fee"):  # off: failed its precision gate (category_defaults.yaml)
        vnd = round(ticket_usd * defaults()["usd_vnd"], -3)
        return {"min_vnd": int(vnd), "typical_vnd": int(vnd), "max_vnd": int(vnd), "n": 1, "source": "maps_tickets"}
    if searched and searched.get("free"):  # only when nothing says there is a price
        ev = searched["evidence"]
        return {"min_vnd": 0, "typical_vnd": 0, "max_vnd": 0, "n": ev.get("domains", 1), "source": ev["basis"],
                "free": True, "fact": ev["basis"] in fact_bases(), "evidence": ev}
    return None


def stays(observations: list[dict], cfg: dict | None = None) -> dict[str, dict]:
    """author -> {"span": (lo, hi) minutes, "quote"}: one stay per author from the `visit_duration` observations that
    carry `detail.minutes` (read from their quote by observe/visit_time.py, after the Extractor said the quote is a stay).
    An author who gave several figures contributes their lowest and highest. Only the sources of config
    visit_time.sources; a figure out of the plausible range is left out. `vague`: the figure is a word ("nửa ngày",
    "cả buổi"), i.e. exactly an ontology bucket range, not a number someone wrote."""
    cfg = cfg or defaults()["visit_time"]
    words = {tuple(v) for v in defaults()["visit_duration_minutes"].values()}
    out: dict[str, dict] = {}
    for o in observations:
        if o["feature"] != "visit_duration" or o["source_type"] not in cfg["sources"]:
            continue
        span = (o.get("detail") or {}).get("minutes")
        if not span or len(span) != 2 or span[0] < cfg["min_minutes"] or span[1] > cfg["max_minutes"]:
            continue
        span = tuple(span)
        who = o.get("author") or o["id"]
        old = out.get(who)
        out[who] = {"span": (min(old["span"][0], span[0]), max(old["span"][1], span[1])) if old else tuple(span),
                    "quote": old["quote"] if old and len(old["quote"]) <= len(o["span"]["quote"]) else o["span"]["quote"],
                    "vague": (old["vague"] if old else True) and span in words}
    return out


def visit_minutes(category: str | None, signal: dict | None, time_spent: dict | None = None, name: str | None = None,
                  observations: list[dict] | None = None) -> dict:
    """[short, typical, long] minutes. Maps' "people typically spend" (many visitors' time on site) wins; then the
    durations visitors wrote ("đi hết 2 tiếng", one per author, outliers left out, observe/visit_time.py); then review
    evidence of a `visit_duration` bucket when it has enough authors and agrees; then the category default."""
    cfg = defaults()
    if time_spent:
        lo, hi = time_spent["min_minutes"], time_spent["max_minutes"]
        return {"short": lo, "typical": (lo + hi) // 2, "long": hi, "source": "maps_time_spent", "n": 0}
    said = stays(observations or [], cfg["visit_time"])
    if len(said) < cfg["visit_duration_min_n"]:  # a word ("cả ngày") is no number: it counts with as many authors as the bucket signal needs
        said = {a: v for a, v in said.items() if not v["vague"]}
    dist = distribution([v["span"] for v in said.values()], cfg["visit_time"])
    if dist:
        mid = lambda v: abs((v["span"][0] + v["span"][1]) / 2 - dist["typical"])  # noqa: E731
        quotes = [{"quote": v["quote"], "minutes": list(v["span"])} for v in sorted(said.values(), key=mid)[:3]]
        return {"short": dist["short"], "typical": dist["typical"], "long": dist["long"], "source": "reviews",
                "basis": "durations", "n": dist["n"], "outliers": dist["outliers"], "quotes": quotes}
    if signal and signal["n"] >= cfg["visit_duration_min_n"] and signal["status"] == "signal":
        lo, hi = cfg["visit_duration_minutes"][signal["top_value"]]
        return {"short": lo, "typical": (lo + hi) // 2, "long": hi, "source": "reviews", "n": signal["n"]}
    short, typical, long = group(category, name)["visit_minutes"]
    return {"short": short, "typical": typical, "long": long, "source": "category_default", "n": 0}


def estimates(category: str | None, features: dict, observations: list[dict], ticket_usd: float | None = None,
              official_tickets: dict | None = None, time_spent: dict | None = None, name: str | None = None,
              searched: dict | None = None) -> dict:
    g = group(category, name)
    return {"category_group": g["id"], "usable_as_default": g["usable_as"], "effort_hint": g["effort_hint"],
            "visit_minutes": visit_minutes(category, features.get("visit_duration"), time_spent, name, observations),
            "entry_fee": entry_fee(observations, ticket_usd, official_tickets, searched)}
