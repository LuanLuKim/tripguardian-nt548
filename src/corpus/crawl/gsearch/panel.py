"""Google's knowledge panel of a place (the box right of / above the results) -> title, address, opening hours and the
"Vé vào cửa" box. Pure: html in, facts out; no browser. A panel that is not there gives `Panel.present = False`.

Hours come as Google prints them ("Thứ Sáu 07:30–17:00"), the same weekday structure as Maps' own hours: {day: [[open,
close], ...]}, [] = closed that day, [["00:00", "24:00"]] = open all day; a day Google does not list is absent. The
ticket box lists sellers; only the line marked "Trang web chính thức" is the operator's own price (Google reads it off
the place's ticket page, and says it is the standard adult ticket); other sellers are resellers and are kept apart.
"Miễn phí" in the box is kept as `free`.
"""

import re
import unicodedata
from dataclasses import dataclass

import lxml.html

DAY_NAMES = {"Chủ Nhật": "sun", "Thứ Hai": "mon", "Thứ Ba": "tue", "Thứ Tư": "wed", "Thứ Năm": "thu", "Thứ Sáu": "fri",
             "Thứ Bảy": "sat"}
_RANGE = re.compile(r"(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})")
_PRICE = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+)\s*₫")
OFFICIAL = "Trang web chính thức"


@dataclass(frozen=True)
class Admission:
    seller: str  # "Trang web chính thức" for the operator's own ticket page, else the reseller's name
    title: str  # the ticket's name when the box names one, else the place
    price_vnd: int | None  # None when the line shows no amount ("Miễn phí" -> free)
    free: bool
    official: bool
    url: str = ""  # where the line leads (the operator's ticket page for the official line)


@dataclass(frozen=True)
class Panel:
    present: bool
    title: str = ""
    category: str = ""  # "Điểm thu hút khách du lịch": the line under the title, Maps' category as Google shows it
    address: str = ""
    hours: dict | None = None
    hours_text: str = ""  # the hours block as printed, kept as the quote of the hours fact
    admissions: tuple[Admission, ...] = ()
    admissions_text: str = ""


def _text(node) -> str:
    return " ".join(unicodedata.normalize("NFC", node.text_content()).split())


def _attr(root, name: str):
    found = root.xpath(f"(//*[@data-attrid={name!r}])[1]")
    return found[0] if found else None


def _hours(block) -> tuple[dict | None, str]:
    days, lines = {}, []
    for row in block.xpath(".//tr"):
        cells = [_text(c) for c in row.xpath("./td")]
        if len(cells) != 2 or cells[0] not in DAY_NAMES:
            continue
        name, value = cells
        lines.append(f"{name} {value}")
        if value == "Mở cửa cả ngày":
            days[DAY_NAMES[name]] = [["00:00", "24:00"]]
        elif value == "Đóng cửa":
            days[DAY_NAMES[name]] = []
        else:
            ranges = _RANGE.findall(value)
            if ranges and not _RANGE.sub("", value).strip(" ,;"):  # nothing else in the cell: it is only hours
                days[DAY_NAMES[name]] = [[a.zfill(5), b.zfill(5)] for a, b in ranges]
    return (days or None), "; ".join(lines)


def _vnd(text: str) -> int | None:
    m = _PRICE.search(text)
    return int(re.sub(r"[.,]", "", m.group(1))) if m else None


def _admissions(box) -> tuple[Admission, ...]:
    """The seller lines of the ticket box: a name (the seller, or the ticket's), an amount, a "Trang web chính thức"
    badge on the operator's own line, and the line's link when it is one."""
    out = []
    for price_node in box.xpath(".//span[contains(@class,'oKZEk')]"):
        row = price_node.getparent()
        while row is not None and not row.xpath("./span[contains(@class,'gyWzge')] | ./*/span[contains(@class,'gyWzge')]"):
            row = row.getparent()
        if row is None:
            continue
        name = row.xpath("(./span[contains(@class,'gyWzge')] | ./*/span[contains(@class,'gyWzge')])[1]")[0]
        badge = " ".join(_text(b) for b in name.xpath(".//span[contains(@class,'lR8hw')]"))
        label = _text(name).replace(badge, "").strip() if badge else _text(name)
        price_text = _text(price_node)
        price = _vnd(price_text)
        if price is None and not re.fullmatch(r"Miễn phí", price_text, re.I):
            continue
        link = row.xpath("ancestor-or-self::a[@href][1]/@href")
        out.append(Admission(seller=label, title=label, price_vnd=price, free=price is None,
                             official=badge == OFFICIAL, url=link[0] if link else ""))
    return tuple(out)


def parse(html: str) -> Panel:
    root = lxml.html.fromstring(html or "<html></html>")
    title = _attr(root, "title")
    if title is None:
        return Panel(present=False)
    sub = _attr(root, "subtitle")
    cat = ""
    if sub is not None:
        cat = _text(sub)
        cat = cat.split("Google", 1)[-1].strip() if "Google" in cat else cat
    address = _attr(root, "kc:/location/location:address")
    hours_block = _attr(root, "kc:/location/location:hours")
    hours, hours_text = _hours(hours_block) if hours_block is not None else (None, "")
    box = _attr(root, "kc:/local:attraction_admissions")
    adm = _admissions(box) if box is not None else ()
    return Panel(present=True, title=_text(title), category=cat,
                 address=_text(address).removeprefix("Địa chỉ:").strip() if address is not None else "",
                 hours=hours, hours_text=hours_text, admissions=adm,
                 admissions_text="; ".join(f"{a.seller}{' (Trang web chính thức)' if a.official else ''} {'Miễn phí' if a.free else a.price_vnd}"
                                           for a in adm))
