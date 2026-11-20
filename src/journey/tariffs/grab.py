"""Grab's published fares (grab.com "Bảng thông tin các dịch vụ trên ứng dụng Grab"): GrabCar / GrabBike per km by
province and area, the fixed routes (to an airport, between two cities), the platform fee and the airport fee.

Only the base services are kept (GrabBike, GrabCar 4 chỗ, GrabCar 6 chỗ): Plus, English-speaking, pet, electric and
industrial-zone variants cost the same or more, so they never change the cheapest ride."""

import re
from datetime import date

from .common import Fare, Parsed, airport_code, area_key, fold, problems, tables, text_lines, vnd

URL = "https://www.grab.com/vn/en/blog/bang-thong-tin-cac-dich-vu-tren-ung-dung-grab/"
NAME = "Grab"
SERVICES = {
    "bike": {"label": "GrabBike", "vehicle": "motorbike", "seats": 1},
    "car4": {"label": "GrabCar 4 chỗ", "vehicle": "car", "seats": 4},
    "car6": {"label": "GrabCar 6 chỗ", "vehicle": "car", "seats": 6},
}
_SERVICE = {"grabbike": "bike", "grabcar 4 cho": "car4", "grabcar 6 cho": "car6"}


def _area(province: str, area: str) -> str | None:
    # "Khu vực" names the old province (or a town priced apart); empty means the whole of the named province
    return area_key(area) if area.strip() else area_key(province)


def _header(grid: list) -> str:
    return " | ".join(fold(c) for row in grid[:2] for c in row)


def parse(html: str) -> tuple[Parsed, dict]:
    """(fares, routes, airport fees; meta: platform fee, page date). Rows that name no known area or service go to
    `skipped`; a fare outside sane bounds is dropped and reported, never kept."""
    out = Parsed()
    for t in tables(html):
        g, head = t["grid"], _header(t["grid"])
        if len(g) < 3:
            continue
        if "for cheaper fare" not in head:
            continue  # GrabExpress / GrabFood (delivery): no service column, no rides
        if "gia cuoc toi thieu 2km dau tien" in head and "theo thoi gian" in head and "tieng" not in head:
            _per_km(g, out)
        elif "km toi thieu" in head and ("gia toi thieu" in head or "gia cuoc toi thieu" in head) and "theo thoi gian" not in head:
            _routes(g, out, airport_col="san bay" in head)
    meta = _meta(text_lines(html))
    if meta["fee"] is None:
        out.skipped.append(("page", "platform fee sentence not found: check the page"))
    if not meta["airport_fee"]:
        out.skipped.append(("page", "airport fee sentence not found: check the page"))
    for iata in meta["airport_fee"]:
        out.airport_pickup[iata] = meta["airport_fee"][iata]
    return out, meta


def _per_km(grid: list, out: Parsed) -> None:
    for row in grid[2:]:
        if len(row) < 6:
            continue
        province, area, label, opening, rate, per_min = row[:6]
        sid = _SERVICE.get(fold(label))
        if sid is None:
            continue  # a variant (Plus, Tiếng Anh, Xe Điện, …): never the cheapest
        key = _area(province, area)
        where = f"{province} | {area} | {label}"
        if key is None:
            out.skipped.append((where, "area not in config/provinces.yaml"))
            continue
        fare = Fare(open=vnd(opening) or 0, open_km=2, per_km=[[None, vnd(rate) or 0]], per_min=vnd(per_min))
        if bad := problems(fare):
            out.skipped.append((where, "out of bounds: " + ", ".join(bad)))
            continue
        out.put(key, sid, fare, where)


def _routes(grid: list, out: Parsed, airport_col: bool) -> None:
    """A route is priced as a package: `price` for the first `min_km`, then `per_km`. Grab names its ends in the label
    ("Tuyến Vũng Tàu đi TP. HCM", "Hà Nội – Sân bay; và Sân bay – Hà Nội") or in an airport column."""
    for row in grid[2:]:
        cells = row[:7] if airport_col else row[:6]
        if len(cells) < (7 if airport_col else 6):
            continue
        if airport_col:
            province, area, label, airport, min_km, price, rate = cells
        else:
            (province, area, label, min_km, price, rate), airport = cells, ""
        where = f"{province} | {area} | {label}"
        if "di ghep" in fold(label):
            out.skipped.append((where, "shared ride (Đi Ghép): the price depends on who else rides"))
            continue
        start = _area(province, area)
        seats = 6 if "6 cho" in fold(label) else 4
        sid = "car6" if seats == 6 else "car4"
        f = fold(label)
        to, both = None, False
        if airport_col:
            to = {"airport": airport_code(airport)}
        elif "san bay" in f:  # "Hà Nội – Sân bay; và Sân bay – Hà Nội": the city's own airport, both ways
            code = {"ha_noi": "HAN", "ho_chi_minh": "SGN", "da_nang": "DAD"}.get(start or "")
            to, both = ({"airport": code}, f.count("san bay") >= 2) if code else (None, False)
        elif m := re.search(r"di (tp hcm|ha noi)$", f):  # "Tuyến Vũng Tàu đi TP. HCM": to the whole city
            to = {"area": "ho_chi_minh" if m.group(1) == "tp hcm" else "ha_noi"}
        elif "hoi an" in f and start == "da_nang":  # "Đà Nẵng ⇔ Hội An …": both ways
            to, both = {"area": "hoi_an"}, True
        if start is None or to is None or None in to.values():
            out.skipped.append((where, "route ends not understood"))
            continue
        route = {"service": sid, "label": label, "from": [start], "to": to, "both_ways": both,
                 "min_km": float(vnd(min_km) or 0), "price": vnd(price), "per_km": vnd(rate)}
        if not route["price"] or not 50_000 <= route["price"] <= 2_000_000 or not 1 <= route["min_km"] <= 200 \
                or not (route["per_km"] or 0) <= 40_000:
            out.skipped.append((where, f"route out of bounds: {route}"))
            continue
        out.routes.append(route)


def _meta(lines: list[str]) -> dict:
    """The platform fee in force and after its end date, the airport fee and the airports it applies to, the page's
    own "Cập nhật lần cuối" date. Each is None / empty when the sentence is not on the page."""
    text = " ".join(lines)
    fee = None
    m = re.search(r"đến (\d\d)/(\d\d)/(\d{4}):\s*Đối với các dịch vụ GrabBike, mức phí nền tảng sẽ từ ([\d.]+)đ đến ([\d.]+)đ\. "
                  r"Đối với các dịch vụ Grab 4 bánh[^.]*?từ ([\d.]+)đ đến ([\d.]+)đ", text)
    if m:
        until = date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        after = re.search(r"Từ \d\d/\d\d/\d{4} đến khi có thông báo mới:.*?là (\d+)% trên giá cước", text)
        fee = {"until": until, "motorbike": [vnd(m[4]), vnd(m[5])], "car": [vnd(m[6]), vnd(m[7])],
               "after_pct": int(after[1]) if after else None}
    airport_fee = {}
    m = re.search(r"Phí vận hành Sân bay: ([\d.]+)đ.*?Các Sân bay đang được áp dụng bao gồm: ([^.(]+)", text)
    if m:
        for name in m[2].split(","):
            if code := airport_code(name.strip()) or airport_code("Sân bay " + name.strip()):
                airport_fee[code] = vnd(m[1])
    updated = re.search(r"Cập nhật lần cuối: (\d\d)/(\d\d)/(\d{4})", text)
    return {"fee": fee, "airport_fee": airport_fee,
            "page_updated": date(int(updated[3]), int(updated[2]), int(updated[1])).isoformat() if updated else None}
