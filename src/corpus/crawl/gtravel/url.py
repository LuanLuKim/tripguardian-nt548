"""Google Travel hotel page for one lodging and one stay.

The page id is the Maps place id's second half (the CID) as a protobuf varint, base64url; the stay is the `ts`
parameter, a protobuf of check-in / check-out (y, m, d) and the night count. Both were checked byte for byte against
what Google Travel emits for the same lodging and dates (tests/crawl/gtravel), so no date has to be typed in.
"""

import base64
from datetime import date

from ..common.lodging import Stay

BASE = "https://www.google.com/travel/hotels/entity/{entity}?hl=vi&gl=vn&curr=VND&ts={ts}"


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(number: int, data: bytes) -> bytes:
    return bytes([number << 3 | 2]) + _varint(len(data)) + data


def _day(d: date) -> bytes:
    return b"\x08" + _varint(d.year) + b"\x10" + _varint(d.month) + b"\x18" + _varint(d.day)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def entity_id(fid: str) -> str:
    """Maps fid "0x<feature>:0x<cid>" -> Google Travel's hotel id."""
    cid = int(fid.split(":")[1], 16)
    return _b64(_field(1, b"\x08" + _varint(cid)) + b"\x10\x01")


def stay_param(stay: Stay) -> str:
    """The `ts` parameter. Two adults is Google's default party and the only one built here."""
    if stay.adults != 2:
        raise ValueError("the ts parameter is built for 2 adults only")
    dates = _field(1, _day(stay.checkin)) + _field(2, _day(stay.checkout)) + b"\x18" + _varint(stay.nights)
    raw = b"\x08\x01" + _field(3, _field(1, b"\x1a\x00") + _field(2, _field(2, dates) + _field(6, b"\x10\x00"))) \
        + _field(5, _field(1, _field(7, b"VND")) + _field(3, b""))
    return _b64(raw)


def hotel_url(fid: str, stay: Stay) -> str:
    return BASE.format(entity=entity_id(fid), ts=stay_param(stay))
