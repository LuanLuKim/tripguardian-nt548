"""Google Flights result page -> flights. Pure functions on the page's HTML / text, no browser.

Each result row carries an aria-label with everything the row shows ("Từ 1210781 đồng Việt Nam trở lên. Chuyến bay
thẳng của Vietjet. Rời … lúc 06:30 vào Thứ Năm, tháng 11 5 và đến … lúc 07:25 vào …"). The flight number is not in
the label: it shows only when the row is expanded ("VietjetHạng phổ thôngAirbus A321VJ 360"), see flight_numbers.
A label that does not read as a flight is skipped, never guessed.
"""

import html as htmllib
import re
from dataclasses import dataclass
from datetime import date

LABEL = re.compile(r'aria-label="(Từ [^"]*?Rời [^"]*?)"')
FLIGHT = re.compile(r"Từ (?P<price>[\d.,]+) đồng.*?Chuyến bay (?:(?P<direct>thẳng)|có (?P<stops>\d+) điểm dừng) của (?P<carrier>.+?)\. Rời (?P<src>.+?) lúc (?P<dep>\d{1,2}:\d{2}) "
                    r"vào [^.]*?tháng (?P<dm>\d{1,2}) (?P<dd>\d{1,2}) và đến (?P<dst>.+?) lúc (?P<arr>\d{1,2}:\d{2}) "
                    r"vào [^.]*?tháng (?P<am>\d{1,2}) (?P<ad>\d{1,2})\.")
NUMBER = re.compile(r"(?<![A-Za-z])([A-Z][A-Z0-9])\s(\d{1,4})\s*$")  # "VJ 360" closing a segment line ("…Airbus A321VJ 360"); the page prints a non-breaking space


@dataclass(frozen=True)
class Flight:
    carrier: str
    depart_at: str  # local "YYYY-MM-DDTHH:MM"
    arrive_at: str
    from_point: str  # the airport as Google names it
    to_point: str
    price_vnd: int | None
    stops: int


def _stamp(day: date, month: int, dom: int, clock: str) -> str:
    """The label has no year: the one that puts the date nearest the searched day (a flight landing on 1 Jan)."""
    d = min((date(y, month, dom) for y in (day.year - 1, day.year, day.year + 1)), key=lambda x: abs((x - day).days))
    h, m = clock.split(":")
    return f"{d.isoformat()}T{int(h):02d}:{m}"


def parse_list(page_html: str, day: date) -> list[Flight]:
    """The flights leaving on `day`, earliest first. One carrier, one departure and arrival, two fares: one flight."""
    out, seen = [], set()
    for raw in LABEL.findall(page_html):
        m = FLIGHT.search(htmllib.unescape(raw))
        if not m:
            continue
        try:
            depart = _stamp(day, int(m["dm"]), int(m["dd"]), m["dep"])
            arrive = _stamp(day, int(m["am"]), int(m["ad"]), m["arr"])
        except ValueError:
            continue
        if depart[:10] != day.isoformat():
            continue
        price = int(re.sub(r"\D", "", m["price"]) or 0) or None
        f = Flight(carrier=m["carrier"].split(". ")[0].strip(), depart_at=depart, arrive_at=arrive, from_point=m["src"].strip(),
                   to_point=m["dst"].strip(), price_vnd=price, stops=0 if m["direct"] else int(m["stops"]))
        key = (f.carrier, f.depart_at, f.arrive_at)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return sorted(out, key=lambda f: f.depart_at)


def flight_numbers(detail_text: str) -> list[str]:
    """The flight numbers of an expanded row, one per segment in order ("VJ 360"); [] when none is shown."""
    out = []
    for line in detail_text.splitlines():
        if "Hạng" in line and (m := NUMBER.search(line.strip())):
            out.append(f"{m[1]} {m[2]}")
    return out
