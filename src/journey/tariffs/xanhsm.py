"""Xanh SM's published fares (now Green SM; greensm.com "Green SM Car" and "Green SM Bike" pages). The price tables are
the JSON the pages are built from (`__NEXT_DATA__` -> props.pageProps.priceData): rows of {city, items: [{value1: what,
value2: price, value3: …}]}.

Kept: Green SM Car (`taxi`, the standard car) and Green SM Bike (`value2`; `value3` is Bike Plus). Premium, Luxury,
two-way and Mini are left out: the first three cost more, and the Mini page states no seat count. A row names the new
province and, in brackets, the old provinces it covers ("Khánh Hòa (Khánh Hòa cũ, Ninh Thuận)"); a row without a list
covers the one old province of its name."""

import json
import re

from .common import Fare, Parsed, fold, listed_areas, merge_tiers, problems, tiers_of, vnd

URLS = {"car": "https://www.greensm.com/vn-vi/greensm-car", "bike": "https://www.greensm.com/vn-vi/greensm-bike"}
NAME = "Xanh SM"
SERVICES = {
    "bike": {"label": "Green SM Bike", "vehicle": "motorbike", "seats": 1},
    "car4": {"label": "Green SM Car", "vehicle": "car", "seats": 4},
}
N = r"(\d+(?:\.\d+)?)"


def price_data(html: str) -> dict:
    """The page's price tables; {} when the page carries none (its layout changed: reported by the caller)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return {}
    try:
        return json.loads(m[1])["props"]["pageProps"].get("priceData") or {}
    except (ValueError, KeyError, TypeError):
        return {}


def fare_of(items: list[tuple[str, str]]) -> tuple[Fare | None, str]:
    """(what, price) lines of one city as a Fare, or None and why; every line with a number must be read."""
    open_, open_km, per_min, tiers = None, None, None, []
    for what, price in items:
        n, v = fold(what, decimals=True), vnd(price)
        if v is None:
            continue
        if m := re.match(rf"^(?:gia mo cua|gia khoi hanh) 0?{N} km dau$", n):  # "Giá mở cửa (2 km đầu)"
            open_, open_km = v, float(m[1])
        elif m := re.match(rf"^gia cuoc tu km tiep theo den km {N}$", n):
            tiers.append(["upto", float(m[1]), v])
        elif m := re.match(rf"^gia(?: cuoc)? tu km(?: thu)? {N} tro di$", n):  # "Giá cước từ km 26 trở đi": 25 before
            tiers.append(["from", float(m[1]) - 1, v])
        elif n == "gia tiep theo tu km tiep theo":
            tiers.append(["plain", None, v])
        elif n == "phi thoi gian di chuyen vnd phut":
            per_min = v
        else:
            return None, f"a line no rule reads: {what!r} = {price!r}"
    if open_ is None:
        return None, "no opening price"
    per_km, why = tiers_of(tiers)
    if per_km is None:
        return None, why
    return Fare(open=open_, open_km=open_km, per_km=merge_tiers(per_km), per_min=per_min), ""


def _put(out: Parsed, label: str, sid: str, items: list, where: str, specific: set) -> None:
    keys, unknown = listed_areas(label.strip())
    if unknown or not keys:
        out.skipped.append((where, f"names no province in config/provinces.yaml: {unknown or label!r}"))
        return
    fare, why = fare_of(items)
    if fare is None:
        out.skipped.append((where, why))
        return
    if bad := problems(fare):
        out.skipped.append((where, "out of bounds: " + ", ".join(bad)))
        return
    for key in keys:
        if len(keys) > 1 and key in specific:
            # "Bình Phước" has a row of its own and is listed in "Đồng Nai (Đồng Nai cũ, Bình Phước)": the own row wins
            out.reread.append((where, f"{key} left to its own row"))
            continue
        out.put(key, sid, fare, where)


def parse(pages: dict) -> tuple[Parsed, dict]:
    """`pages`: {"car": html, "bike": html}."""
    out = Parsed()
    meta = {}
    car = price_data(pages.get("car", "")).get("taxi") or {}
    rows = car.get("rows") or []
    if not rows:
        out.skipped.append(("car page", "no Green SM Car table (priceData.taxi): the page layout changed"))
    single = set()  # old provinces with a row of their own
    for r in rows:
        keys, _ = listed_areas(r["city"].strip())
        if "(" not in r["city"] and len(keys) == 1:
            single.add(keys[0])
    for r in rows:
        items = [(i.get("value1") or "", i.get("value2") or "") for i in r.get("items") or []]
        _put(out, r["city"], "car4", items, f"Green SM Car | {r['city'].strip()}", single)
    meta["car_cities"] = [r["city"].strip() for r in rows]

    bike = price_data(pages.get("bike", "")).get("gia_niem_yet") or {}
    rows = bike.get("rows") or []
    if not rows:
        out.skipped.append(("bike page", "no Green SM Bike table (priceData.gia_niem_yet): the page layout changed"))
    if rows and "green sm bike vnd" not in fold(bike.get("columns", "")).replace("green sm bike plus", ""):
        out.skipped.append(("bike page", f"columns changed: {bike.get('columns')!r}"))
        rows = []
    for r in rows:
        items = [(i.get("value1") or "", i.get("value2") or "") for i in r.get("items") or [] if i.get("value1")]
        where = f"Green SM Bike | {r['city'].strip()}"
        if all(vnd(p) is None for _, p in items):
            out.skipped.append((where, "Bike Plus only (no Green SM Bike price)"))
            continue
        _put(out, r["city"], "bike", items, where, set())
    meta["bike_cities"] = [r["city"].strip() for r in rows]
    return out, meta
