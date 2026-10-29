"""A Trip.com hotel list page (server-rendered, Next.js flight data) -> hotels with the price of the dates in its URL.

The page carries `"hotelList":[...]` as JSON: name, WGS84 coordinates, and per hotel the offered room with
`priceInfo.price` (a night before tax) and `priceExplanation` ("Tổng giá: 991.412₫ / 1 phòng × 2 đêm bao gồm thuế &
phí", the total with tax). The total is the figure used; the price a night is the total over the nights. A hotel
without an offered room has no price: unknown.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
_TOTAL = re.compile(r"Tổng[^\d]*?(\d{1,3}(?:\.\d{3})+) ?₫")
DETAIL = "https://vn.trip.com/hotels/detail/?hotelId={id}&checkIn={checkin}&checkOut={checkout}&adult=2&curr=VND"


@dataclass(frozen=True)
class Hotel:
    id: str
    name: str
    lat: float | None
    lng: float | None
    checkin: str | None  # ISO date of the offer, as Trip.com states it
    nights: int | None
    price_total_vnd: int | None
    price_night_vnd: int | None
    url: str


def _flight(html: str) -> str:
    return "".join(json.loads(m.group(1)) for m in _PUSH.finditer(html))


def _point(info: dict) -> tuple[float | None, float | None]:
    for c in (info.get("positionInfo") or {}).get("mapCoordinate") or []:
        if c.get("gcoordType") == "WGS84":
            try:
                return float(c["latitude"]), float(c["longitude"])
            except (KeyError, TypeError, ValueError):
                pass
    return None, None


def _day(s: str | None):
    try:
        return datetime.strptime(s or "", "%Y%m%d").date()
    except ValueError:
        return None


def parse_list(html: str) -> list[Hotel]:
    flight = _flight(html)
    i = flight.find('"hotelList":[')
    if i < 0:
        return []
    try:
        listed, _ = json.JSONDecoder().raw_decode(flight[i + len('"hotelList":'):])
    except ValueError:
        return []
    out = []
    for item in listed:
        info = item.get("hotelInfo") or {}
        hid = str((info.get("summary") or {}).get("hotelId") or "")
        name = (info.get("nameInfo") or {}).get("name")
        if not hid or not name:
            continue
        lat, lng = _point(info)
        checkin = checkout = nights = total = None
        rooms = item.get("roomInfo") or []
        if rooms:
            room = rooms[0]
            stay = room.get("statusInfo") or {}
            a, b = _day(stay.get("checkIn")), _day(stay.get("checkOut"))
            if a and b and b > a:
                checkin, checkout, nights = a.isoformat(), b.isoformat(), (b - a).days
            price = room.get("priceInfo") or {}
            if not price.get("isHiddenPrice") and (m := _TOTAL.search(price.get("priceExplanation") or "")):
                total = int(m.group(1).replace(".", ""))
        night = round(total / nights) if total and nights else None
        out.append(Hotel(hid, name, lat, lng, checkin, nights, total if night else None, night,
                         DETAIL.format(id=hid, checkin=checkin or "", checkout=checkout or "")))
    return out
