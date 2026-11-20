"""Be's published fares (be.com.vn "Dịch vụ vận chuyển"): one tab per province, one block per service, each block a
list of (note, price) pairs whose wording says what the price is ("Từ 0-2km", "1km tiếp theo với quãng đường 2km-12km",
"Giá mở cửa", "Kilomet mở cửa", "Ngưỡng km 1", …).

Kept: beBike, beCar 4 / 7 chỗ, beCar Tiết Kiệm, beCar Economy, beTaxi 4 / 7 chỗ, and beAirport (a per-km price for
rides to and from the airport). Plus, long-distance packages, two-way and hourly rentals are left out: they cost more
for a single ride or are not one. A tab names an old province; a merged province's other parts are not assumed to
share its price.

Every priced line of a kept block must be understood (`fare_of`): one line no rule reads drops the whole block into the
report, so a tier is never lost without a trace."""

import re

from .common import Fare, Parsed, airport_code, area_key, fold, km, merge_tiers, problems, tiers_of, vnd

URL = "https://be.com.vn/consumer/be-transport/"
NAME = "Be"
SERVICES = {
    "bike": {"label": "beBike", "vehicle": "motorbike", "seats": 1},
    "car4": {"label": "beCar 4 chỗ", "vehicle": "car", "seats": 4},
    "car7": {"label": "beCar 7 chỗ", "vehicle": "car", "seats": 6},
    "saver": {"label": "beCar Tiết Kiệm", "vehicle": "car", "seats": 4},
    "economy": {"label": "beCar Economy", "vehicle": "car", "seats": 4},
    "taxi4": {"label": "beTaxi 4 chỗ", "vehicle": "car", "seats": 4},
    "taxi7": {"label": "beTaxi 7 chỗ", "vehicle": "car", "seats": 6},
}
SKIP = ("plus", "duong dai", "befar", "2 chieu", "1 chieu", "thue", "rental", "theo gio", "tieng anh", "ban uong")
CITY_AIRPORT = {"ha_noi": "HAN", "ho_chi_minh": "SGN", "da_nang": "DAD"}


def _service(title: str) -> str | None:
    """The kept service a block title names; None for a variant left out (or a title naming no service)."""
    f = fold(title)
    if any(s in f for s in SKIP):
        return None
    if "tuyen co dinh" in f:
        return "route"
    if f.startswith(("beairport", "becar airport")):
        return "airport"
    if f.startswith("bebike"):
        return "bike"
    if "tiet kiem" in f:
        return "saver"
    if f.startswith("becar economy"):
        return "economy"
    if m := re.match(r"(becar|betaxi) ([47])(?: ?c| cho| seats)?$", f):
        return ("car" if m[1] == "becar" else "taxi") + m[2]
    if f == "betaxi":
        return "unseated"
    return None


def _tabs(html: str) -> list[tuple[str, str]]:
    """(tab name, pane html) for every province tab, in page order."""
    names = {m[1]: " ".join(m[2].split()) for m in re.finditer(r"id=['\"](pills-\d+)-tab['\"][^>]*>\s*([^<]+?)\s*</a>", html)}
    starts = [(m.start(), m[1]) for m in re.finditer(r"id=['\"](pills-\d+)['\"]\s+role=['\"]tabpanel['\"]", html)]
    out = []
    for i, (at, pid) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(html)
        if pid in names:
            out.append((names[pid], html[at:end]))
    return out


def _blocks(pane: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """(service title, [(note, price text)]) for every service block of a tab."""
    out = []
    for chunk in re.split(r'class="box-detail"', pane)[1:]:
        title = re.search(r'class="sub-detail[^"]*">\s*(.*?)\s*</div>', chunk, re.S)
        pairs = re.findall(r'<p class="note">(.*?)</p>\s*<p class="price[^"]*">(.*?)</p>', chunk, re.S)
        clean = lambda h: " ".join(re.sub(r"<[^>]+>", " ", h).split())  # noqa: E731
        out.append((clean(title[1]) if title else "", [(clean(n), clean(p)) for n, p in pairs]))
    return out


# How a note reads once folded with decimals kept ("1km tiếp theo với quãng đường 2 - 12km" -> "1km tiep theo voi quang
# duong 2 12km"). N is a distance. Each rule's first group is the km it names.
N = r"(\d+(?:\.\d+)?)"
_FEES = ("thay doi diem", "nhieu diem", "dat lich", "phi cho", "cuoc phi cho", "waiting", "multi", "change dest",
         "destination change", "pick up point", "qua dem", "overnight")
_NIGHT = ("phu phi dem khuya", "phu thu dem khuya", "phu phi ban dem", "phu thu ban dem", "phu phi dem", "phi dem khuya",
          "late night", "night surcharge", "night fee", "cuoc phi 1 dem")
_PACKAGE = ("goi", "package", "duong dai", "quay dau", "1 chieu")
_OPEN = [  # (pattern, km from the note: group 1, or None when the note states no distance)
    re.compile(rf"^(?:tu |from |first )?0 ?{N} ?km\b"),                          # "Từ 0-2km", "First 0-2 km"
    re.compile(rf"^(?:gia cuoc toi thieu )?{N} ?k[mn] (?:dau|day)\b"),               # "2km đầu tiên", "2kn đầu tiên"
    re.compile(rf"^first {N} ?km\b"),                                              # "First 2 km(*)"
    re.compile(rf"^(?:gia|phi) mo cua(?: {N} ?km dau)?\b"),                       # "Giá mở cửa (1.4km đầu)"
    re.compile(rf"^opening price(?: first {N} ?km)?\b"),                           # "Opening price (first 2km)"
]
_UPTO = [  # a tier that ends at the km named
    re.compile(rf"(?:den|to) km ?{N}$"),                                           # "Km tiếp theo đến Km 30"
    re.compile(rf"den {N} ?km$"),                                                  # "0.5km đến 30km"
    re.compile(rf"(?:quang duong|distance from|tu) (?:tu )?{N}(?: ?km)? {N} ?km$"),  # "… quãng đường 2 - 12km" (2nd)
    re.compile(rf"tiep cho quang duong {N} ?km$"),                                 # "1km tiếp cho quãng đường 12km"
]
_FROM = [  # (pattern, offset): an open-ended tier; the tier before it ends at km + offset
    (re.compile(rf"\bsau {N} ?km$"), 0),                                          # "1 km tiếp theo sau 12km"
    (re.compile(rf"(?:lon hon|greater than) {N} ?km$"), 0),                       # "… lớn hơn 12km"
    (re.compile(rf"^1 ?k?m tiep theo tu {N} ?km$"), 0),                           # "1m tiếp theo từ 12km" ("1m" = 1km)
    (re.compile(rf"^(?:tu|from) km ?{N}$"), -1),                                  # "Từ Km 31": km 30 is the last before
    (re.compile(rf"^km {N} tro di$"), -1),                                        # "Km 31 trở đi"
    (re.compile(rf"km thu {N} tro di$"), -1),                                     # "Giá km thứ 30 trở đi"
    (re.compile(rf"^(?:price )?from {N}(?:st|nd|rd|th) km onwards$"), -1),       # "Price from 21st km onwards"
]
_PLAIN = re.compile(r"^(?:1 ?km tiep theo|next 1 ?km|kilomet tiep theo|gia km tiep theo|price per additional km|"
                    r"each subsequent km)$")


def _first(rules, n: str):
    for rule in rules:
        if m := rule.search(n):
            return m
    return None


def fare_of(pairs: list[tuple[str, str]]) -> tuple[Fare | None, str, list[str]]:
    """The block's (note, price) pairs as a Fare, or None and why. Every line with a number must be read by a rule here;
    the third item lists each line read other than its label says (a mislabel of the page, by the rule named)."""
    open_, open_km, night, pickup, reread = None, None, None, {}, []
    tiers: list[list] = []   # [kind, km, rate]: kind "upto" (ends at km), "from" (ends the one before at km), "plain"
    thresholds: dict = {}    # "Ngưỡng km 1 / Giá mỗi km 1 / …": index -> [km, rate]
    for note, price in pairs:
        n, v = fold(note, decimals=True), vnd(price)
        if v is None:
            continue  # an empty line ("" / "₫"): nothing to read
        if any(s in n for s in _FEES):
            continue  # destination change, multi-stop, booking ahead, waiting, overnight stay: not part of a ride's fare
        if any(n.startswith(s) for s in _NIGHT):
            night = v
            continue
        if m := re.match(r"^don tai san bay (.+)$", n):  # "Đón tại sân bay TSN"
            code = airport_code(m[1])
            if code is None:
                return None, f"airport pickup fee for an airport not in config/provinces.yaml: {note!r}", reread
            pickup[code] = v
            continue
        if n.startswith("kilomet goi") and (km(price) or 99) <= 5 and not any(fold(x).startswith(("goi", "package"))
                                                                                 for x, _ in pairs):
            open_km = km(price)  # "Kilomet gói 1" beside "Giá mở cửa", with no package price: the opening km
            reread.append(f"{note!r} = {price!r} read as the opening km (no package price in the block)")
            continue
        if any(re.search(rf"\b{s}\b", n) for s in _PACKAGE):
            return None, f"a package, not a per-km fare: {note!r}", reread
        if n.startswith("kilomet mo cua"):
            open_km = km(price)
            continue
        if m := re.match(r"^(nguong km|gia moi km) ([12])$", n):
            slot = thresholds.setdefault(int(m[2]), [None, None])
            if m[1] == "nguong km":
                slot[0] = km(price)
            else:
                slot[1] = v
            continue
        if re.match(rf"^{N} ?km dau tien$", n) and v < 100:  # "1km đầu tiên" = "1": the opening km in a km column
            open_km = km(price)
            continue
        if (m := _first(_OPEN, n)) and not (open_ is not None and re.match(rf"^{N} ?km dau tien$", n)):
            if open_ is not None:
                return None, f"two opening prices: {note!r}", reread
            open_ = v
            if m.groups() and m[1] is not None:
                open_km = float(m[1])
            if (open_km or 0) > 5:
                return None, f"a package, not a per-km fare: {note!r}", reread
            continue
        if open_ is not None and re.match(rf"^{N} ?km dau tien$", n):
            # Đà Nẵng beCar: "Từ 0-2km 29.188" then "1km đầu tiên 14.090": the opening is already stated, so this line
            # can only be the price of each further km
            tiers.append(["plain", None, v])
            reread.append(f"{note!r} = {price!r} read as each further km (the opening price is stated above it)")
            continue
        if m := _first(_UPTO, n):
            tiers.append(["upto", float(m.groups()[-1]), v])
            continue
        hit = next(((m, off) for rule, off in _FROM if (m := rule.search(n))), None)
        if hit:
            tiers.append(["from", float(hit[0][1]) + hit[1], v])
            continue
        if _PLAIN.match(n):
            tiers.append(["plain", None, v])
            continue
        return None, f"a line no rule reads: {note!r} = {price!r}", reread
    if open_ is None:
        return None, "no opening price (the page states none: a flexible price)" if not tiers else "no opening price", reread
    if thresholds:
        if tiers or sorted(thresholds) != [1, 2] or None in thresholds[1] + thresholds[2]:
            return None, f"threshold lines not as expected: {thresholds}", reread
        (k1, r1), (k2, r2) = thresholds[1], thresholds[2]
        if open_km is not None and open_km != k1:
            return None, f"opening km {open_km} and threshold 1 {k1} disagree", reread
        open_km = k1  # the opening price covers the km up to threshold 1; rate 1 up to threshold 2, rate 2 after
        per_km = [[k2, r1], [None, r2]]
    else:
        per_km, why = tiers_of(tiers)
        if per_km is None:
            return None, why, reread
        if why:
            reread.append(why)
    if open_km is None:
        open_km = 0.0  # "Giá mở cửa" with no distance: every km is charged on top (an upper bound, never under)
        reread.append("opening km not stated: every km charged from the start")
    return Fare(open=open_, open_km=open_km, per_km=merge_tiers(per_km), night=night or None, pickup=pickup), "", reread


def parse(html: str) -> tuple[Parsed, dict]:
    out = Parsed()
    tabs = _tabs(html)
    for name, pane in tabs:
        key = area_key(name)
        if key is None:
            out.skipped.append((name, "tab names no province in config/provinces.yaml"))
            continue
        for title, pairs in _blocks(pane):
            sid = _service(title)
            where = f"{name} | {title}"
            if sid is None:
                continue
            if sid == "unseated":
                out.skipped.append((where, "the title states no seat count"))
                continue
            if sid == "route":
                out.skipped.append((where, "fixed route to an airport the page does not name"))
                continue
            if not pairs:
                out.skipped.append((where, "empty block"))
                continue
            fare, why, reread = fare_of(pairs)
            if fare is None:
                out.skipped.append((where, why))
                continue
            if bad := problems(fare):
                out.skipped.append((where, "out of bounds: " + ", ".join(bad)))
                continue
            out.reread += [(where, r) for r in reread]
            if sid == "airport":  # beAirport: the city's airport, both ways, at a per-km price of its own
                code = CITY_AIRPORT.get(key)
                if code is None:
                    out.skipped.append((where, "beAirport for a city without a known airport"))
                    continue
                route = {"service": "car4", "name": "beAirport", "label": title, "from": [key], "to": {"airport": code},
                         "both_ways": True, "fare": fare.as_dict()}
                same = lambda r: {k: v for k, v in r.items() if k != "label"}  # noqa: E731
                if all(same(r) != same(route) for r in out.routes):  # the English tab repeats the Vietnamese one
                    out.routes.append(route)
                continue
            out.put(key, sid, fare, where)
    if not tabs:
        out.skipped.append(("page", "no province tab found: the page layout changed"))
    return out, {"tabs": [n for n, _ in tabs]}
