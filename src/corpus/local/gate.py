"""Gate of one LocalClaim the Extractor read in a Document section (docs/CORPUS.md, Tri thức bản địa). A claim stands
only when its quote is in the section, its text in the quote and every amount, month, day type, hour and weather it
carries is stated in the quote. Nothing here guesses a value the page did not state."""

import re
from typing import Callable

from ..llm import LOCAL_CLAIM_KINDS, LOCAL_SUBJECT_KINDS
from ..observe import amount_in, hour_in
from ..ontology import fold_text

MAX_QUOTE = 400
_HOURS = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-4]):([0-5]\d)$")
_MONTH = r"(?:tháng|thg|th)\s*0?(\d{1,2})(?!\d)"
_LINK = r"\s*(?:-|đến|tới|sang|->)\s*"
_RANGE = re.compile(_MONTH + _LINK + r"(?:(?:tháng|thg|th)\s*)?0?(\d{1,2})(?!\d)")
_LIST = re.compile(r"(?:tháng|thg|th)\s*(\d{1,2}(?:\s*(?:,|và|hoặc|/)\s*\d{1,2})+)(?!\d)")
_EN = {m: i + 1 for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                          "september", "october", "november", "december"))}
_DAY_WORDS = {"weekend": r"cuối tuần|thứ\s*(?:7|bảy)|chủ\s*nhật|weekend",
              "weekday": r"ngày thường|trong tuần|thứ\s*(?:2|hai|3|ba|4|tư|5|năm|6|sáu)|weekday",
              "holiday": r"lễ|tết|holiday"}
# A venue's opening hours belong to Maps and the official site (docs/CORPUS.md §Chi tiết địa điểm), not to a blog's list
_VENUE_HOURS = re.compile(r"giờ mở cửa|giờ hoạt động|mở cửa từ|opening hours|open daily")
_WEATHER_WORDS = {"rainy": r"mưa|rain", "foggy": r"sương|mù|fog|mist", "cold": r"lạnh|rét|cold",
                  "sunny": r"nắng|sunny"}


def norm(text: str) -> str:
    """fold_text plus what a model changes when it copies: markdown emphasis, dash and quote marks."""
    text = re.sub(r"[*_`]+", "", text or "")
    text = text.translate(str.maketrans({"–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'"}))
    return fold_text(text)


def months_in(quote: str) -> set[int]:
    """Months a text states: "tháng N", ranges "tháng A đến (tháng) B" (wrapping the year), lists "tháng 1, 2 và 3",
    English month names."""
    q = norm(quote)
    out: set[int] = set()
    for m in re.finditer(_MONTH, q):
        out.add(int(m.group(1)))
    for m in _RANGE.finditer(q):
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= 12 and 1 <= b <= 12:
            out.update(range(a, b + 1) if a <= b else [*range(a, 13), *range(1, b + 1)])
    for m in _LIST.finditer(q):
        out.update(int(x) for x in re.findall(r"\d{1,2}", m.group(1)))
    out.update(n for word, n in _EN.items() if re.search(rf"\b{word}\b", q))
    return {m for m in out if 1 <= m <= 12}


def _words(q: str, pattern: str) -> bool:
    return bool(re.search(rf"(?<!\w)(?:{pattern})(?!\w)", q))


def _int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def gate_claim(item: dict, section: str,
               resolve: Callable[[str], str | None] | None = None) -> tuple[dict | None, str | None]:
    """(claim, None) when the claim stands, else (None, the reason it is dropped). `resolve(name)` gives the place id
    of a named venue or None; a venue that does not resolve is kept as `poi_unresolved` (a nominee, never a fact about
    a place we hold)."""
    kind, subject_kind = str(item.get("kind") or ""), str(item.get("subject_kind") or "")
    if kind not in LOCAL_CLAIM_KINDS or subject_kind not in LOCAL_SUBJECT_KINDS:
        return None, "bad_kind"
    subject = " ".join(str(item.get("subject_text") or "").split())
    if not subject:
        return None, "no_subject"
    quote, text = str(item.get("quote") or "").strip(), " ".join(str(item.get("text") or "").split())
    q = norm(quote)
    if not q or len(quote) > MAX_QUOTE or q not in norm(section):
        return None, "quote_not_in_source"
    if not text or norm(text) not in q:
        return None, "text_not_in_quote"
    if _VENUE_HOURS.search(q):
        return None, "venue_hours"

    lo, hi = sorted((_int(item.get("amount_min_vnd")), _int(item.get("amount_max_vnd"))))
    lo = lo or hi
    if any(a and not amount_in(quote, a) for a in {lo, hi}):
        return None, "amount_not_in_quote"
    when = item  # the model answers the when-fields flat (months, days, hours, weather; see LOCAL_CLAIM)
    months = sorted({m for m in (when.get("months") or ()) if isinstance(m, int)})
    stated = months_in(quote)
    if any(not 1 <= m <= 12 or m not in stated for m in months) or len(months) != len(when.get("months") or ()):
        return None, "month_not_in_quote"
    days = [d for d in ("weekday", "weekend", "holiday") if d in (when.get("days") or ())]
    if any(not _words(q, _DAY_WORDS[d]) for d in days):
        return None, "day_not_in_quote"
    hours = str(when.get("hours") or "").strip()
    if hours:
        m = _HOURS.match(hours)
        if not m:
            return None, "bad_hours"
        if not (hour_in(quote, f"{m.group(1)}:{m.group(2)}") and hour_in(quote, f"{m.group(3)}:{m.group(4)}")):
            return None, "hour_not_in_quote"
    weather = str(when.get("weather") or "")
    if weather and (weather not in _WEATHER_WORDS or not _words(q, _WEATHER_WORDS[weather])):
        return None, "weather_not_in_quote"

    subject_id = None
    if subject_kind == "poi":
        subject_id = resolve(subject) if resolve else None
        subject_kind = "poi" if subject_id else "poi_unresolved"
    return {"subject_kind": subject_kind, "subject": subject, "subject_id": subject_id, "kind": kind, "text": text,
            "quote": quote, "amount_min_vnd": lo or None, "amount_max_vnd": hi or None,
            "when": {"months": months, "days": days, "hours": hours, "weather": weather},
            "who": " ".join(str(item.get("who") or "").split())}, None
