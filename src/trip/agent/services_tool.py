"""find_services: utilities and rental / tour places (ATM, pump, hospital, pharmacy, toilet, charger, bike / car rental,
tour, coach station) for the assistant (spec 2026-10-29 assistant-tools §5.8, §5B G6/G10). They come from
corpus.service_places only. They are NOT PlaceCards: never Decision candidates, never Planning stops, and the result has
no `_cards`, so the place carousel never shows them."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import ClassVar

from agents.assistant import read_tool
from corpus import data_root, service_places
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
    "sửa xe": ("sua xe", "sua chua xe", "tiem sua xe", "tiem va xe", "gara", "garage", "bao duong xe", "bao tri xe"),
}
UTILITIES = ("ATM", "cây xăng", "bệnh viện", "phòng khám", "hiệu thuốc", "nhà vệ sinh công cộng", "trạm sạc xe điện", "sửa xe")
# A kind the crawl did not search by name is found by the place's Maps category (nothing is made up: no such category = no rows).
CATEGORY_OF = {"sửa xe": re.compile(r"sửa chữa|bảo trì|bảo dưỡng"), "cây xăng": re.compile(r"xăng|nhiên liệu")}
VEHICLE = re.compile(r"\bxe\b|ô tô|mô tô|xe máy", re.I)
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


def kind_in(text: str) -> str | None:
    """The first kind (a KINDS key) a free message names, e.g. "cây xăng trên đường đi Tà Nung"; None when it names none."""
    return next(iter(kinds_in(text)), None)


def kinds_in(text: str) -> list[str]:
    """Every service kind explicitly named in a free message, without duplicate aliases."""
    t = f" {fold(text)} "
    return [word for word, names in KINDS.items()
            if any(re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", t) for n in names)]


def _matches(r: dict, word: str) -> bool:
    """Is this crawled row a `word` place? A word the crawl searched is not enough alone for "cây xăng" (a cafe named
    "Cây Xăng" came up too) and "sửa xe" was never searched, so those two also go by the Maps category."""
    cat = r.get("category") or ""
    if word == "sửa xe":
        return bool(CATEGORY_OF[word].search(cat) and VEHICLE.search(cat))
    if word not in (r.get("words") or ()):
        return False
    return word not in CATEGORY_OF or bool(CATEGORY_OF[word].search(cat.lower()))


def _group(word: str) -> str:
    return "utilities" if word in UTILITIES else "rental_tour" if word in ("thuê xe máy", "thuê ô tô", "tour") else "transport"


def _km(a, b) -> float:
    la, lb = math.radians(a[0]), math.radians(b[0])
    h = math.sin((lb - la) / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def _anchor(turn, ref: str | None):
    """(label, (lat, lng)) of the near_place or the trip's lodging; None when neither has a point."""
    if ref:
        pid = turn.resolve_place(ref.strip())
        if pid == "center" and turn.knowledge is not None:  # "gần chợ / trung tâm": the city centre of config/cities.yaml
            name, lat, lng = turn.knowledge.center
            return name, (lat, lng)
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


@dataclass
class _Snapshot:
    rows: list[dict]
    versions: dict[str, tuple | None]
    by_word: dict[str, set[int]]


_snapshot_lock = RLock()
_snapshot_source = None
_snapshots: dict[str | None, _Snapshot] = {}
_source_groups: dict[str, set[str | None]] = {}


def _version(path: Path) -> tuple | None:
    try:
        s = path.stat()
    except FileNotFoundError:
        return None
    return s.st_mtime_ns, s.st_ctime_ns, s.st_size, s.st_ino


def _detail_path(root: Path, fid: str) -> Path:
    return root / "gmaps" / "services" / "places" / (fid.replace(":", "_") + ".json")


def _service_rows(words: list[str]) -> list[tuple[dict, str]]:
    """Single-flight snapshots via the public loader; check only matching details on warm reads."""
    global _snapshot_source, _source_groups
    root = data_root()
    listing = root / "gmaps" / "list" / "dalat_svc.json"
    with _snapshot_lock:
        source = (root, service_places, _version(listing))
        if source != _snapshot_source:
            _snapshots.clear()
            # A place may be tagged with one group but have queries from another.
            # Inspect the cheap list once before narrowing the public loader's detail reads.
            items = json.loads(listing.read_text(encoding="utf-8"))["items"] if source[2] else []
            _source_groups = {w: {r.get("group") for r in items
                                  if (w == "sửa xe" and _matches(r, w)) or any(
                                      q == w or q.startswith(w + " ") for q in r.get("queries") or ())}
                              for w in KINDS}
            _snapshot_source = source
        groups = {g for w in words for g in _source_groups[w]}
        group = next(iter(groups)) if len(groups) == 1 else None
        snapshot = _snapshots.get(group)
        if snapshot is not None:
            candidates = sorted({i for w in words for i in snapshot.by_word[w]})
            if any(_version(_detail_path(root, snapshot.rows[i]["fid"])) != snapshot.versions[snapshot.rows[i]["fid"]]
                   for i in candidates):
                snapshot = None
        if snapshot is None:
            rows = service_places("dalat", group=group)
            snapshot = _Snapshot(
                rows, {r["fid"]: _version(_detail_path(root, r["fid"])) for r in rows},
                {w: {i for i, r in enumerate(rows) if _matches(r, w)} for w in KINDS},
            )
            _snapshots[group] = snapshot
            candidates = sorted({i for w in words for i in snapshot.by_word[w]})
        # Preserve source order and the first requested matching kind, including stable ranking ties.
        return [(snapshot.rows[i], next(w for w in words if i in snapshot.by_word[w])) for i in candidates]


@read_tool(FindServices, group="services")
def find_services(turn, inp: FindServices) -> dict:
    words, group = _words(inp.kind)
    if not words:
        return {"error": f"unknown kind {inp.kind!r}; kinds: " + ", ".join(KINDS) + ". There is no data for it; say so."}
    anchor = _anchor(turn, inp.near_place)
    rows = _service_rows(words)
    out = []
    for r, w in rows:
        if r.get("lat") is None or r.get("lng") is None:
            continue
        d = round(_km(anchor[1], (r["lat"], r["lng"])), 1) if anchor else None
        out.append((d if d is not None else math.inf, -(r.get("rating") or 0) * math.log1p(r.get("reviews") or 0), r, d, w))
    out.sort(key=lambda t: t[:2])
    dates = sorted({str(r["fetched_at"])[:10] for _, _, r, _, _ in out if r.get("fetched_at")})
    result = {
        "anchor": anchor[0] if anchor else "unknown (no near_place and no lodging in the trip: distances are unknown)",
        "rows": [{"name": r["name"], "kind": w, "category": r.get("category"),
                  "distance_km": d, "address": r.get("address") or "unknown", "phone": r.get("phone") or "unknown",
                  "website": r.get("website") or "unknown", "hours": _hours(r), "open_status": r.get("status") or "unknown",
                  "rating": r.get("rating"), "reviews": r.get("reviews"), "maps_url": r.get("url")}
                 for _, _, r, d, w in out[:inp.limit]],
        "found": len(out),
        "sources": ["Google Maps"], "crawled": dates[-1] if dates else "unknown",
        "note": "services, not tourist places: do not propose them as stops or plan places; phone / hours may be out of date",
    }
    if not out:
        result["note"] = "no data for this kind in the crawl: say so, do not guess"
    return result
