"""What every tariff parser shares: HTML tables as grids, names folded for matching, VND amounts, the old-province
names of config/provinces.yaml, and the one shape a fare takes (journey.rides.fare reads it)."""

import re
import unicodedata
from html import unescape
from dataclasses import dataclass, field
from functools import cache
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
PROVINCES = ROOT / "config" / "provinces.yaml"


def fold(text: str, decimals: bool = False) -> str:
    """Accents, case, punctuation and spacing aside: "TP. Hồ Chí Minh" -> "tp ho chi minh". With `decimals`, a number's
    decimal mark survives as '.': "0,5 Km đầu" -> "0.5 km dau" (a fare note's distances are decimals, never thousands)."""
    t = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").casefold()
    if decimals:
        t = re.sub(r"(?<=\d)[.,](?=\d)", "\x00", t)
        return " ".join(re.sub(r"[^a-z0-9\x00]+", " ", t).split()).replace("\x00", ".")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def km(text: str) -> float | None:
    """A distance cell: "2" / "0.5" / "1,3" / "2 ₫" (sic) -> 2.0 / 0.5 / 1.3 / 2.0; None without a number."""
    m = re.search(r"\d+(?:[.,]\d+)?", text or "")
    return float(m.group(0).replace(",", ".")) if m else None


def vnd(text: str) -> int | None:
    """"31.201 ₫" / "169,855" / "20.000 VNĐ (Giảm tới …)" -> 31201 / 169855 / 20000; None without a number. The first
    number is the price; '.' and ',' are thousands separators on every page read here (no page states decimals)."""
    m = re.search(r"\d[\d.,]*", text or "")
    if not m:
        return None
    digits = re.sub(r"[.,]", "", m.group(0))
    return int(digits) if digits else None


@dataclass(frozen=True)
class Provinces:
    areas: dict      # key -> {name, new, names}
    subareas: dict   # key -> {name, parent, box, names}
    by_name: dict    # folded name -> key (areas and sub-areas)
    snap_km: float
    airports: dict   # IATA -> {name, lat, lng, names}
    airport_by_name: dict  # folded name -> IATA
    airport_km: float


@cache
def provinces(path: Path = PROVINCES) -> Provinces:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    by_name: dict[str, str] = {}
    for kind in ("areas", "subareas"):
        for key, row in raw[kind].items():
            for name in [row["name"], *row.get("names", [])]:
                f = fold(name)
                if by_name.setdefault(f, key) != key:
                    raise ValueError(f"provinces.yaml: {name!r} names both {by_name[f]} and {key}")
    airports = raw.get("airports") or {}
    by_airport = {fold(n): iata for iata, a in airports.items() for n in [a["name"], *a.get("names", [])]}
    return Provinces(raw["areas"], raw.get("subareas") or {}, by_name, float(raw.get("snap_km", 15)), airports, by_airport,
                     float(raw.get("airport_km", 3)))


def airport_code(name: str, prov: Provinces | None = None) -> str | None:
    """"Tân Sân Nhất" (sic, Grab) / "Sân bay Nội Bài" -> SGN / HAN; None for a name no airport has."""
    prov = prov or provinces()
    f = fold(name)
    return prov.airport_by_name.get(f) or prov.airport_by_name.get(f.removeprefix("san bay "))


def area_key(name: str, prov: Provinces | None = None) -> str | None:
    """The old province (or sub-area) a brand's label names; None when it names none of them."""
    prov = prov or provinces()
    f = fold(name)
    if f in prov.by_name:
        return prov.by_name[f]
    for prefix in ("tp ", "thanh pho ", "tinh "):
        if f.startswith(prefix) and f[len(prefix):] in prov.by_name:
            return prov.by_name[f[len(prefix):]]
    return None


def listed_areas(label: str, prov: Provinces | None = None) -> tuple[list[str], list[str]]:
    """A row label like "Khánh Hòa (Khánh Hòa cũ, Ninh Thuận)" or "Hồ Chí Minh (địa phận TP HCM cũ)" -> the old
    provinces it covers, and the parts no province matched (reported, never guessed). A label without a list covers the
    one old province of that name only: a merged province's other parts are not assumed to share its price."""
    prov = prov or provinces()
    head, _, inner = label.partition("(")
    inner = inner.rsplit(")", 1)[0]
    if not inner.strip():
        k = area_key(head, prov)
        return ([k], []) if k else ([], [head.strip()])
    keys, unknown = [], []
    for part in re.split(r"[,;]| và ", inner):
        part = re.sub(r"^\s*(địa phận|khu vực)\s+", "", part.strip(), flags=re.I)
        if not part:
            continue
        k = area_key(part, prov)
        (keys.append(k) if k else unknown.append(part))
    return list(dict.fromkeys(keys)), unknown


@dataclass
class Fare:
    """One service's price where it is sold: `open` for the first `open_km`, then each further km at the rate of its tier
    ([up_to_km or None, VND/km], by absolute km), plus `per_min` on the minutes after the opening km where a brand states
    one. `night` is the brand's surcharge for a ride at night (not applied: a leg's clock time is not known). `pickup` is
    what this service adds when picked up at an airport ({IATA: VND})."""
    open: int
    open_km: float
    per_km: list
    per_min: int | None = None
    night: int | None = None
    pickup: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = {"open": self.open, "open_km": self.open_km, "per_km": self.per_km}
        if self.per_min:
            d["per_min"] = self.per_min
        if self.night:
            d["night"] = self.night
        if self.pickup:
            d["pickup"] = dict(self.pickup)
        return d


@dataclass
class Parsed:
    """What a parser read from one page: fares by area and service, fixed routes, airport pickup fees, every row it could
    not place (the build report lists them; nothing unplaced is priced) and every row read other than its label says."""
    fares: dict = field(default_factory=dict)        # area -> service -> Fare
    routes: list = field(default_factory=list)       # {service, label, from, to, both_ways, min_km, price, per_km}
    airport_pickup: dict = field(default_factory=dict)  # IATA -> VND (cars picked up at that airport)
    skipped: list = field(default_factory=list)      # (where, why)
    conflicts: list = field(default_factory=list)    # (area, service, kept, dropped, where)
    reread: list = field(default_factory=list)       # (where, what): a page's own mislabel, read by a stated rule

    def put(self, area: str, service: str, fare: Fare, where: str) -> None:
        old = self.fares.setdefault(area, {}).get(service)
        if old is not None and old.as_dict() != fare.as_dict():
            self.conflicts.append((area, service, old.as_dict(), fare.as_dict(), where))
            return  # the first row read stays: pages list the main row before area extras
        self.fares[area][service] = fare


def problems(f: Fare) -> list[str]:
    """Sanity bounds a published Vietnamese ride fare falls in; a fare outside them is a misread, not a price."""
    out = []
    if not 5_000 <= f.open <= 120_000:
        out.append(f"open {f.open}")
    if not 0 <= f.open_km <= 5:
        out.append(f"open_km {f.open_km}")
    if not f.per_km:
        out.append("no per-km rate")
    last = f.open_km
    for i, (upto, rate) in enumerate(f.per_km):
        if not 2_000 <= rate <= 40_000:
            out.append(f"rate {rate}")
        if upto is None and i != len(f.per_km) - 1:
            out.append("open-ended tier before the last")
        if upto is not None and upto <= last:
            out.append(f"tier {upto} not after {last}")
        last = upto if upto is not None else last
    if f.per_min is not None and not 0 <= f.per_min <= 3_000:
        out.append(f"per_min {f.per_min}")
    return out


def tiers_of(tiers: list[list]) -> tuple[list | None, str]:
    """[kind, km, rate] in page order -> ([[up_to_km or None, rate]], note) or (None, why): a plain rate ends where the
    next tier says the one before it ends ("Từ Km 31" -> 30); an open-ended tier must agree with the end of the tier
    before it. The note says when the last tier had an end and was run on past it."""
    if not tiers:
        return None, "no per-km rate"
    out = []
    for i, (kind, at, rate) in enumerate(tiers):
        nxt = tiers[i + 1] if i + 1 < len(tiers) else None
        if kind == "upto":
            out.append([at, rate])
        elif kind == "plain":
            if nxt is None:
                out.append([None, rate])
            elif nxt[0] == "from":
                out.append([nxt[1], rate])
            else:
                return None, f"a rate without a bound before a bounded one: {tiers}"
        else:  # "from"
            if not out:
                return None, f"an open-ended tier with no tier before it: {tiers}"
            before = out[-1][0]
            if before != at:
                return None, f"tier ends at {before} but the next starts after {at}: {tiers}"
            if nxt is not None:
                return None, f"a tier after an open-ended one: {tiers}"
            out.append([None, rate])
    if out[-1][0] is not None:  # "Km tiếp theo đến Km 30" and nothing after: the page prices no km past 30
        end = out[-1][0]
        out[-1][0] = None
        return out, f"the last tier ends at km {end:g} and nothing follows: its rate is used past it"
    return out, ""


def merge_tiers(per_km: list) -> list:
    """Neighbouring tiers at the same rate as one ("2 - 12 km: 13.494", "sau 12 km: 13.494")."""
    out = []
    for upto, rate in per_km:
        if out and out[-1][1] == rate:
            out[-1][0] = upto
        else:
            out.append([upto, rate])
    return out


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._stack, self._cell, self._row, self._text = [], [], None, None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._stack.append({"rows": [], "before": " ".join(self._text[-8:])})
        elif tag == "tr" and self._stack:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {"text": "", "rs": _span(a.get("rowspan")), "cs": _span(a.get("colspan"))}
        elif tag == "br" and self._cell is not None:
            self._cell["text"] += " "

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._cell["text"] = " ".join(self._cell["text"].split())
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None and self._stack:
            self._stack[-1]["rows"].append(self._row)
            self._row = None
        elif tag == "table" and self._stack:
            t = self._stack.pop()
            self.tables.append({"before": t["before"], "grid": _grid(t["rows"])})

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"] += data
        elif data.strip():
            self._text.append(" ".join(data.split()))


def _span(v) -> int:
    try:
        return max(1, min(int(v), 200))
    except (TypeError, ValueError):
        return 1


def _grid(rows: list) -> list[list[str]]:
    """Rows with rowspan / colspan written out, so every row has its own copy of a merged cell."""
    out, pending = [], {}
    for r in rows:
        line, col, k = [], 0, 0
        while k < len(r) or col in pending:
            if col in pending:
                text, left = pending.pop(col)
                if left > 1:
                    pending[col] = (text, left - 1)
                line.append(text)
                col += 1
                continue
            c = r[k]
            k += 1
            for _ in range(c["cs"]):
                if c["rs"] > 1:
                    pending[col] = (c["text"], c["rs"] - 1)
                line.append(c["text"])
                col += 1
        out.append(line)
    return out


def tables(html: str) -> list[dict]:
    """Every <table> of a page in close order (the page order, as long as tables do not nest, which they do not on the
    pages read here): {"before": the text just above it, "grid": [[cell text]]}."""
    p = _Tables()
    p.feed(html)
    return p.tables


def text_lines(html: str) -> list[str]:
    """A page's visible text, one block per line (scripts and styles dropped)."""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"</(p|div|tr|li|h\d|td|th)>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return [" ".join(line.split()) for line in unescape(t).split("\n") if line.strip()]
