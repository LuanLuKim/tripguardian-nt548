"""Lado Taxi's published fares (ladotaxi.com, "Bảng giá dịch vụ"): in Lâm Đồng, Xanh SM's cars are Lado's electric
taxis on the Green SM platform, priced at Lado's own board (greensm.com/vn-vi/news/trien-khai-chuoi-chuong-trinh-thuong-
cho-bac-tai-xanh-tai-lam-dong, 08/10/2026). The fares go under brand `xanhsm`, area `lam_dong`.

Kept: Taxi 4 chỗ and Taxi 7 chỗ (one `boardprice-item` each: the per-km price, "Giá mở cửa", "Vượt ngưỡng 26 km"), and
the fixed route "Đà Lạt -> Sân Bay (35km)" (one way, to Liên Khương). The board states no distance for the opening
price, so every km is charged from the start (`open_km` 0: a few thousand over, never under). "Xe hợp đồng" (contract
hire) and the intercity routes are left out."""

import re

from .common import Fare, Parsed, fold, problems, vnd

URL = "https://ladotaxi.com"
AREA = "lam_dong"
SERVICES = {
    "lado4": {"label": "Xanh SM · taxi Lado 4 chỗ", "vehicle": "car", "seats": 4},
    "lado7": {"label": "Xanh SM · taxi Lado 7 chỗ", "vehicle": "car", "seats": 6},
}
_SERVICE = {"taxi 4 cho": "lado4", "taxi 7 cho": "lado7"}


def _text(h: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", h).split())


def parse(html: str) -> tuple[Parsed, dict]:
    out = Parsed()
    items = re.split(r'class="boardprice-item', html)[1:]
    if not items:
        out.skipped.append(("page", "no boardprice-item: the page layout changed"))
    for item in items:
        name = re.search(r'<p class="name">(.*?)</p>', item, re.S)
        title = _text(name[1]) if name else ""
        sid = _SERVICE.get(fold(title))
        if sid is None:
            out.skipped.append((title or "?", "not a metered taxi (contract hire or unknown)"))
            continue
        rate = re.search(r'<div class="price">(.*?)</div>\s*<div class="unit">(.*?)</div>', item, re.S)
        more = [(fold(_text(t)), _text(p)) for t, p in
                re.findall(r'<div class="pricemore-tt">(.*?)</div>\s*<div class="pricemore-price">(.*?)</div>', item, re.S)]
        if not rate or fold(_text(rate[2])) != "vnd km":
            out.skipped.append((title, "no VNĐ/km price"))
            continue
        open_, tiers, unread = None, [[None, vnd(_text(rate[1]))]], []
        for what, price in more:
            if what == "gia mo cua":
                open_ = vnd(price)
            elif m := re.fullmatch(r"vuot nguong (\d+) km", what):  # "Vượt ngưỡng 26 km": the rate past km 26
                tiers = [[float(m[1]), tiers[0][1]], [None, vnd(price)]]
            else:
                unread.append((what, price))
        if unread or open_ is None:
            out.skipped.append((title, f"lines not read: {unread}" if unread else "no opening price"))
            continue
        fare = Fare(open=open_, open_km=0.0, per_km=tiers)
        if bad := problems(fare):
            out.skipped.append((title, "out of bounds: " + ", ".join(bad)))
            continue
        out.put(AREA, sid, fare, title)
        out.reread.append((title, "opening km not stated: every km charged from the start"))
    _routes(html, out)
    return out, {}


def _routes(html: str, out: Parsed) -> None:
    """The fixed route from Đà Lạt to the airport, one way: 4 chỗ / 7 chỗ prices for its stated km."""
    found = False
    for slide in re.split(r'class="swiper-slide"', html)[1:]:
        name = re.search(r'<div class="route-name">(.*?)</div>', slide, re.S)
        if not name:
            continue
        label = _text(name[1])
        m = re.fullmatch(r"da lat dalat san bay airport (\d+)km", fold(label))
        if not m:
            continue
        found = True
        prices = {int(s): vnd(p) for s, p in re.findall(r"(\d+) chỗ\(seats\):\s*([\d.]+)", _text(slide), re.I)}
        for seats, sid in ((4, "lado4"), (7, "lado7")):
            price = prices.get(seats)
            if not price or not 50_000 <= price <= 2_000_000:
                out.skipped.append((label, f"no sane {seats}-seat price: {prices}"))
                continue
            out.routes.append({"service": sid, "label": label, "from": [AREA], "to": {"airport": "DLI"},
                               "both_ways": False, "min_km": float(m[1]), "price": price, "per_km": None})
    if not found:
        out.skipped.append(("routes", "the Đà Lạt -> airport route is not on the page: check it"))
