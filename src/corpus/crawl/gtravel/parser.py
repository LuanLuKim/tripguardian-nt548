"""A Google Travel hotel page's text (document.body.innerText, Vietnamese) -> the price for the dates in its URL.

The headline chip above the tabs ("2.078.464 ₫" over "7 – 9 thg 11") is the price a night, taxes included, for the
dates asked: the same stay priced 1.72M / 2.08M / 2.0M a night for 1 / 2 / 3 nights. A lodging with no booking offer
shows "Liên hệ với khách sạn này … để biết giá và tình trạng phòng trống" instead: no price, and nothing about rooms
being sold out. A page whose offers are not drawn yet is "pending": wait, do not guess.
"""

import re
from dataclasses import dataclass
from datetime import date

from ..common.lodging import Stay

_SPACES = re.compile(r"[  \s]+")
_AMOUNT = re.compile(r"^(\d{1,3}(?:\.\d{3})+) ?₫$")
_SAME_MONTH = re.compile(r"^(\d{1,2}) ?– ?(\d{1,2}) thg (\d{1,2})$")
_INPUT_DAY = re.compile(r"(\d{1,2}) thg (\d{1,2})$")
_VS_USUAL = re.compile(r"bình thường|giá thấp|giá cao", re.I)  # the 2026-10 chip: price, then "Rẻ hơn bình thường 30%"
_TWO_MONTHS = re.compile(r"^(\d{1,2}) thg (\d{1,2}) ?– ?(\d{1,2}) thg (\d{1,2})$")
NO_OFFER = "Vui lòng gọi điện hoặc truy cập vào trang web để biết giá và tình trạng phòng trống"


@dataclass(frozen=True)
class Hotel:
    state: str  # "priced" | "no_offer" | "pending"
    name: str | None = None
    price_night_vnd: int | None = None
    dates: str | None = None  # the chip's date line as shown, e.g. "7 – 9 thg 11"


def _lines(text: str) -> list[str]:
    return [l for l in (_SPACES.sub(" ", l).strip() for l in text.splitlines()) if l]


def parse_hotel(text: str) -> Hotel:
    lines = _lines(text)
    tabs = next((i for i, l in enumerate(lines) if l.startswith("Các mức giá")), None)  # the tab bar; photos may be absent
    if tabs is None:
        return Hotel("pending")
    first = tabs + 1 + (lines[tabs + 1] == "Xem tất cả ảnh" if tabs + 1 < len(lines) else 0)
    name = lines[first] if first < len(lines) else None
    end = lines.index("Kiểm tra phòng trống", tabs) if "Kiểm tra phòng trống" in lines[tabs:] else len(lines)
    for i in range(tabs + 1, end - 1):
        if (m := _AMOUNT.match(lines[i])) and (_SAME_MONTH.match(lines[i + 1]) or _TWO_MONTHS.match(lines[i + 1])):
            return Hotel("priced", name, int(m.group(1).replace(".", "")), lines[i + 1])
        if (m := _AMOUNT.match(lines[i])) and _VS_USUAL.search(lines[i + 1]):
            return Hotel("priced", name, int(m.group(1).replace(".", "")), "inputs")  # dates come from the date inputs
    if NO_OFFER in lines:
        return Hotel("no_offer", name)
    return Hotel("pending", name)


def dates_match(shown: str | None, stay: Stay) -> bool:
    """Is the chip's date line the stay that was asked for? Google can fall back to other dates."""
    if not shown:
        return False
    out = stay.checkout
    if "|" in shown:  # "Thứ 7, 21 thg 11|CN, 22 thg 11": the check-in / check-out inputs
        a, b = (_INPUT_DAY.search(x.strip()) for x in shown.split("|", 1))
        return bool(a and b) and (int(a.group(1)), int(a.group(2)), int(b.group(1)), int(b.group(2))) == \
            (stay.checkin.day, stay.checkin.month, out.day, out.month)
    if m := _SAME_MONTH.match(shown):
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))) == (stay.checkin.day, out.day, stay.checkin.month) \
            and out.month == stay.checkin.month
    if m := _TWO_MONTHS.match(shown):
        return tuple(map(int, m.groups())) == (stay.checkin.day, stay.checkin.month, out.day, out.month)
    return False
