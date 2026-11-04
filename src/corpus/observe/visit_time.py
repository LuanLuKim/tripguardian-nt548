"""How long a visit lasts, read from the words of a quote (docs/CORPUS.md §5, `visit_duration`).

One deterministic reader shared by every source: a review, a video, a web page. The Extractor only decides WHICH words
of a source say how long people stay at the place; the minutes come from those words, never from the model, so a
number the quote does not hold cannot get in. "45 phút" -> (45, 45); "1-2 tiếng" -> (60, 120); "1h30" -> (90, 90);
"nửa ngày" / "cả buổi" / "cả ngày" -> the ranges of the ontology buckets (config/category_defaults.yaml). A clock time
("7h sáng", "lúc 14h") is no duration, and a quote that holds two different durations has no single reading.
"""

import re
import statistics
import unicodedata

from ..categories import defaults

_WORDS = {"một": 1, "mot": 1, "hai": 2, "ba": 3, "bốn": 4, "bon": 4, "tư": 4, "năm": 5, "nam": 5, "sáu": 6, "sau": 6,
          "bảy": 7, "bay": 7, "tám": 8, "tam": 8, "chín": 9, "chin": 9, "mười": 10, "muoi": 10}
_NUM = r"(?:\d+(?:[.,]\d+)?|" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")"
_UNIT_H = r"(?:tiếng|tieng|giờ|gio|h|tiếng đồng hồ)"
_UNIT_M = r"(?:phút|phut|p|ph|'|’|ʼ)"
_AFTER_CLOCK = r"(?!\s*(?:sáng|chiều|trưa|tối|đêm|khuya|sang|chieu|trua|toi|dem)\b)"
_RANGE_SEP = r"\s*(?:-|–|—|~|đến|tới|den|toi|hoặc|hay|đến khoảng)\s*"

_HM = re.compile(rf"(?<![\w.,:/])({_NUM})\s*(?:{_UNIT_H})\s*(\d{{1,2}})\s*(?:{_UNIT_M})?(?!\w){_AFTER_CLOCK}", re.I)  # 1h30, 1 tiếng 30
_HALF = re.compile(rf"(?<![\w.,:/])({_NUM})\s*(?:{_UNIT_H})\s*rưỡi(?!\w)", re.I)  # 1 tiếng rưỡi
_HALF_H = re.compile(r"(?<![\w])nửa\s*(?:tiếng|giờ)(?:\s*đồng hồ)?(?!\w)", re.I)
_RANGE_H = re.compile(rf"(?<![\w.,:/])({_NUM}){_RANGE_SEP}({_NUM})\s*(?:{_UNIT_H})(?!\w){_AFTER_CLOCK}", re.I)
_RANGE_HM = re.compile(rf"(?<![\w.,:/])(\d{{1,2}})\s*h\s*(\d{{2}})?{_RANGE_SEP}(\d{{1,2}})\s*h\s*(\d{{2}})?(?!\w){_AFTER_CLOCK}", re.I)  # 1h30-2h
_RANGE_M = re.compile(rf"(?<![\w.,:/])({_NUM}){_RANGE_SEP}({_NUM})\s*(?:{_UNIT_M})(?!\w)", re.I)
_ONE_H = re.compile(rf"(?<![\w.,:/])({_NUM})\s*(?:{_UNIT_H})(?!\w){_AFTER_CLOCK}", re.I)
_ONE_M = re.compile(rf"(?<![\w.,:/])({_NUM})\s*(?:{_UNIT_M})(?![\w])", re.I)
_DAYS = [
    (re.compile(r"(?<!\w)(?:nửa ngày|nua ngay|nửa buổi|cả buổi|cả một buổi|nguyên buổi)(?!\w)", re.I), "half_day"),
    (re.compile(r"(?<!\w)(?:cả ngày|cả một ngày|nguyên ngày|nguyên một ngày|trọn ngày|cả ngày trời)(?!\w)(?!\s*rưỡi)", re.I), "full_day"),
]
# "lúc 7h", "trước 5 giờ", "từ 8h": h / giờ after these words is a clock time ("tiếng" never is)
_CLOCK_BEFORE = re.compile(r"(?:lúc|vào lúc|vào|từ|trước|sau|đến|tới|khoảng|tầm|cỡ|hơn|gần|mở cửa|đóng cửa)\s*$", re.I)
_CLOCK_UNIT = re.compile(r"(?:giờ|gio|h)\s*$", re.I)


def _num(token: str) -> float | None:
    token = token.casefold()
    if token in _WORDS:
        return float(_WORDS[token])
    whole, sep, frac = token.replace(",", ".").partition(".")
    if sep and frac not in ("5", "25", "75"):  # "2,3 tiếng" is "2 to 3 hours" as often as 2.3 hours: no reading
        return None
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return None


def spans(text: str) -> list[tuple[int, int, tuple[int, int]]]:
    """Every duration written in `text` as (start, end, (lo, hi) minutes); overlapping readings keep the widest match."""
    found = []
    for m in _HM.finditer(text):
        h, mm = _num(m.group(1)), int(m.group(2))
        if h is not None and mm < 60:
            found.append((m.start(), m.end(), (round(h * 60 + mm),) * 2))
    for m in _HALF.finditer(text):
        h = _num(m.group(1))
        if h is not None:
            found.append((m.start(), m.end(), (round(h * 60 + 30),) * 2))
    for m in _HALF_H.finditer(text):
        found.append((m.start(), m.end(), (30, 30)))
    for m in _RANGE_HM.finditer(text):
        a = int(m.group(1)) * 60 + int(m.group(2) or 0)
        b = int(m.group(3)) * 60 + int(m.group(4) or 0)
        if 0 < a < b:
            found.append((m.start(), m.end(), (a, b)))
    for rx, unit in ((_RANGE_H, 60), (_RANGE_M, 1)):
        for m in rx.finditer(text):
            a, b = _num(m.group(1)), _num(m.group(2))
            if a is not None and b is not None and 0 < a < b:
                found.append((m.start(), m.end(), (round(a * unit), round(b * unit))))
    for rx, unit in ((_ONE_H, 60), (_ONE_M, 1)):
        for m in rx.finditer(text):
            a = _num(m.group(1))
            if a is not None and a > 0:
                found.append((m.start(), m.end(), (round(a * unit),) * 2))
    buckets = defaults()["visit_duration_minutes"]
    for rx, name in _DAYS:
        for m in rx.finditer(text):
            lo, hi = buckets[name]
            found.append((m.start(), m.end(), (lo, hi)))
    found = [s for s in found if not _clock_like(text, s[0], s[1])]
    found.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    out = []
    for s in found:
        if out and s[0] < out[-1][1]:  # inside / overlapping the previous reading: keep the longer match
            if s[1] - s[0] > out[-1][1] - out[-1][0]:
                out[-1] = s
            continue
        out.append(s)
    return out


def _clock_like(text: str, start: int, end: int) -> bool:
    """A bare hour ("7h", "2 giờ") right after a word that introduces a clock time; "1h30" / "2 tiếng" never are."""
    piece = text[start:end]
    if not _CLOCK_UNIT.search(piece) or re.search(r"\d\s*(?:giờ|gio|h)\s*\d", piece, re.I) or "-" in piece:
        return False
    if re.match(r"\s*(?:-|–|đến|tới)\s*\d{1,2}\s*(?:h|giờ)", text[end:end + 12], re.I):
        return True  # the start of a clock range "7h-9h"
    return bool(_CLOCK_BEFORE.search(text[max(0, start - 14):start]) and
                re.search(r"(?:lúc|vào|từ|trước|sau|đến|tới|mở cửa|đóng cửa)\s*$", text[max(0, start - 14):start], re.I))


def durations(text: str) -> list[tuple[int, int]]:
    """Every duration the text writes, in order, as (lo, hi) minutes; clock times are not durations."""
    t = unicodedata.normalize("NFC", text or "")
    return [d for *_, d in spans(t)]


def parse_minutes(quote: str) -> tuple[int, int] | None:
    """(lo, hi) minutes of the one duration a quote states, else None (no duration, or two different ones)."""
    found = set(durations(quote))
    if len(found) != 1:
        return None
    lo, hi = next(iter(found))
    return (lo, hi) if 0 < lo <= hi else None


def bucket(minutes: float) -> str:
    """The ontology `visit_duration` value of a stay of this many minutes (config visit_duration_minutes)."""
    if minutes <= 60:
        return "under_1h"
    if minutes <= 120:
        return "1_to_2h"
    if minutes <= 330:
        return "half_day"
    return "full_day"


def midpoint(span: tuple[int, int]) -> float:
    return (span[0] + span[1]) / 2


def distribution(stays: list[tuple[int, int]], cfg: dict | None = None) -> dict | None:
    """Short / typical / long minutes of a place from the stays its visitors reported (one (lo, hi) per author).

    Typical = the median of the midpoints; short / long = the lower / upper quartile of the lowest / highest figures
    people gave (a range "1-2 tiếng" counts at both ends). Outliers: with >= `outlier_min_n` stays, a midpoint more than
    `outlier_ratio` times the median, or below its `1/outlier_ratio`, is left out and counted. None when no stay is
    left or fewer than `min_n` remain."""
    cfg = cfg or defaults()["visit_time"]
    if not stays:
        return None
    mids = [midpoint(s) for s in stays]
    med = statistics.median(mids)
    kept = stays
    if len(stays) >= cfg["outlier_min_n"]:
        kept = [s for s, m in zip(stays, mids) if med / cfg["outlier_ratio"] <= m <= med * cfg["outlier_ratio"]]
    outliers = len(stays) - len(kept)
    if len(kept) < cfg["min_n"]:
        return None
    mids = sorted(midpoint(s) for s in kept)
    typical = statistics.median(mids)
    if len(kept) == 1:
        lo, hi = kept[0]
        short, long = (lo, hi) if lo != hi else (typical * cfg["single_short"], typical * cfg["single_long"])
    else:
        lows, highs = sorted(s[0] for s in kept), sorted(s[1] for s in kept)
        short, long = _quantile(lows, 0.25), _quantile(highs, 0.75)
    def r(x: float) -> int:  # 5 minutes below an hour, `round_to` above: a 20-minute stay stays 20
        step = 5 if x < 60 else cfg["round_to"]
        return max(5, int(round(x / step) * step))

    short, typical, long = r(short), r(typical), r(long)
    return {"short": min(short, typical), "typical": typical, "long": max(long, typical), "n": len(kept),
            "outliers": outliers}


def _quantile(xs: list[float], q: float) -> float:
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (pos - lo)
