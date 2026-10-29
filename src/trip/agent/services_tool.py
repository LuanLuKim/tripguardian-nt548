"""find_services: utilities and rental / tour places (ATM, pump, hospital, pharmacy, toilet, charger, bike / car rental,
tour, coach station) for the assistant (spec 2026-10-29 assistant-tools §5.8, §5B G6/G10). They come from
corpus.service_places only. They are NOT PlaceCards: never Decision candidates, never Planning stops, and the result has
no `_cards`, so the place carousel never shows them."""

from __future__ import annotations

import math
from typing import ClassVar

from agents.assistant import read_tool
from corpus import service_places
from pydantic import BaseModel, ConfigDict, Field

from ..domain.text import fold

KINDS = {  # the word the crawl searched -> what the user may call it (folded)
    "ATM": ("atm", "may atm", "rut tien"),
    "cây xăng": ("cay xang", "tram xang", "do xang", "xang"),
    "bệnh viện": ("benh vien", "cap cuu"),
    "phòng khám": ("phong kham", "bac si"),
    "hiệu thuốc": ("hieu thuoc", "nha thuoc", "tiem thuoc"),
    "nhà vệ sinh công cộng": ("nha ve sinh", "toilet", "wc", "ve sinh cong cong"),
    "trạm sạc xe điện": ("tram sac", "sac xe dien", "sac xe"),
    "thuê xe máy": ("thue xe may", "cho thue xe may"),
    "thuê ô tô": ("thue o to", "thue xe oto", "thue oto", "thue xe hoi", "thue xe 4 cho"),
    "tour": ("tour", "du lich tron goi"),
    "bến xe": ("ben xe", "xe khach", "nha xe"),
}
GROUPS = {"utilities": "utilities", "tien ich": "utilities", "rental_tour": "rental_tour", "thue xe": "rental_tour",
          "transport": "transport", "services": None}
LIMIT_MAX = 10


class FindServices(BaseModel):
    """Everyday services in Đà Lạt from Google Maps, NOT tourist places: ATM, cây xăng, bệnh viện, phòng khám, hiệu thuốc,
    nhà vệ sinh công cộng, trạm sạc xe điện, thuê xe máy, thuê ô tô, tour, bến xe. Rows are nearest first from the
    anchor (near_place, else the trip's lodging): name, kind, distance km in a straight line, phone, website, hours (or
    "unknown"), rating, reviews, Maps url. They are not recommendations and show no cards. Nothing found = say there
    is no data. Use it for "gần đây có ATM không", "hiệu thuốc nào gần khách sạn", "thuê xe máy ở đâu", "bến xe Đà Lạt"."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "find_services"

    kind: str = Field(min_length=1, max_length=60, description=(
        'What the user wants, in their words: "atm", "cây xăng", "bệnh viện", "phòng khám", "hiệu thuốc", '
        '"nhà vệ sinh công cộng", "trạm sạc", "thuê xe máy", "thuê ô tô", "tour", "bến xe", or a group: '
        '"utilities", "rental_tour", "services" (all).'))
    near_place: str | None = Field(None, description="A place id or name to measure from. Leave out to use the trip's lodging.")
    limit: int = Field(5, ge=1, le=LIMIT_MAX, description="How many rows, 1 to 10.")


def _words(kind: str) -> tuple[list[str], str | None]:
    """The crawl words and group a user's kind asks for."""
    k = fold(kind).strip()
    if k in GROUPS:
        g = GROUPS[k]
        return [w for w in KINDS if g is None or _group(w) == g], g
    hit = [w for w, names in KINDS.items() if k == fold(w) or any(k == n or n in k for n in names)]
    return hit, None


def _group(word: str) -> str:
    return "utilities" if word in list(KINDS)[:7] else "rental_tour" if word in ("thuê xe máy", "thuê ô tô", "tour") else "transport"


def _km(a, b) -> float:
    la, lb = math.radians(a[0]), math.radians(b[0])
    h = math.sin((lb - la) / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def _anchor(turn, ref: str | None):
    """(label, (lat, lng)) of the near_place or the trip's lodging; None when neither has a point."""
    if ref:
        pid = turn.resolve_place(ref.strip())
        if pid is None:
            raise ValueError(f"no place {ref!r} in the corpus (or more than one fits): there is no data for it; say so, do not guess")
        p = turn.catalog.by_id.get(pid)
        if p is None or p.lat is None or p.lng is None:
            raise ValueError(f"place {ref!r} has no coordinates")
        return p.name, (p.lat, p.lng)
    lodging = turn.state.lodging.value if turn.state.lodging.known else None
    if lodging is not None:
        if lodging.lat is not None and lodging.lng is not None:
            return lodging.text, (lodging.lat, lodging.lng)
        p = turn.catalog.by_id.get(lodging.place_id) if lodging.place_id else None
        if p is not None and p.lat is not None:
            return lodging.text, (p.lat, p.lng)
    return None


def _hours(r: dict) -> list[str] | str:
    return list(r["hours"]) if r.get("hours") else "unknown"


@read_tool(FindServices, group="services")
def find_services(turn, inp: FindServices) -> dict:
    words, group = _words(inp.kind)
    if not words:
        return {"error": f"unknown kind {inp.kind!r}; kinds: " + ", ".join(KINDS) + ". There is no data for it; say so."}
    anchor = _anchor(turn, inp.near_place)
    rows = [r for r in service_places("dalat") if any(w in words for w in r.get("words") or ())]
    if group is None and len(words) == 1:  # a single kind: only the places that word found
        rows = [r for r in rows if words[0] in (r.get("words") or ())]
    out = []
    for r in rows:
        if r.get("lat") is None or r.get("lng") is None:
            continue
        d = round(_km(anchor[1], (r["lat"], r["lng"])), 1) if anchor else None
        out.append((d if d is not None else math.inf, -(r.get("rating") or 0) * math.log1p(r.get("reviews") or 0), r, d))
    out.sort(key=lambda t: t[:2])
    dates = sorted({str(r["fetched_at"])[:10] for _, _, r, _ in out if r.get("fetched_at")})
    result = {
        "anchor": anchor[0] if anchor else "unknown (no near_place and no lodging in the trip: distances are unknown)",
        "rows": [{"name": r["name"], "kind": next((w for w in (r.get("words") or ()) if w in words), r.get("category")),
                  "distance_km": d, "address": r.get("address") or "unknown", "phone": r.get("phone") or "unknown",
                  "website": r.get("website") or "unknown", "hours": _hours(r), "open_status": r.get("status") or "unknown",
                  "rating": r.get("rating"), "reviews": r.get("reviews"), "maps_url": r.get("url")}
                 for _, _, r, d in out[:inp.limit]],
        "found": len(out),
        "sources": ["Google Maps"], "crawled": dates[-1] if dates else "unknown",
        "note": "services, not tourist places: do not propose them as stops or plan places; phone / hours may be out of date",
    }
    if not out:
        result["note"] = "no data for this kind in the crawl: say so, do not guess"
    return result
