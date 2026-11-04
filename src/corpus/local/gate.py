"""Gate of one LocalClaim the Extractor read in a Document section (docs/CORPUS.md, Tri thức bản địa). A claim stands
only when its quote is in the section, its text in the quote and every amount, month, day type, hour and weather it
carries is stated in the quote. Nothing here guesses a value the page did not state."""

import re
from functools import lru_cache
from typing import Callable

import yaml

from ..crawl.common.files import ROOT
from ..llm import LOCAL_CLAIM_KINDS, LOCAL_SUBJECT_KINDS
from ..observe import amount_in, hour_in
from ..ontology import fold_text
from .group import fold, tokens

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


@lru_cache(maxsize=1)
def rules() -> dict:
    """config/local.yaml: word lists and thresholds of the gate (the folded patterns are compiled here)."""
    cfg = yaml.safe_load((ROOT / "config" / "local.yaml").read_text(encoding="utf-8"))
    gate = dict(cfg["gate"])
    gate["epithets"] = [re.compile(p) for p in gate["epithets"]]
    return {"gate": gate, "topic": cfg["topic"], "verify": cfg.get("verify") or {},
            "official_alone": set(cfg.get("official_alone_kinds") or ()),
            "official_alone_subjects": set(cfg.get("official_alone_subjects") or ())}


def doc_on_topic(title: str, texts: list[str], city_name: str, markers: list[str] | None = None) -> bool:
    """A Document is about the city when its title names the city (or a marker of its region) or its text names them at
    least `topic.min_mentions` times. A health page, a page about another city, mentions Dalat once or never."""
    names = {n for n in (fold(city_name), fold(city_name).replace(" ", ""), *(fold(m) for m in markers or ())) if n}
    pattern = re.compile(r"\b(?:" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b") \
        if names else None
    if pattern is None:
        return True
    if pattern.search(fold(title)):
        return True
    return len(pattern.findall(fold(" ".join(texts)))) >= rules()["topic"]["min_mentions"]


_MARKS = str.maketrans({"–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'"})


@lru_cache(maxsize=256)
def norm(text: str) -> str:
    """fold_text plus what a model changes when it copies: markdown emphasis, dash and quote marks. Cached: a chunk is
    normalised once for all the items read from it."""
    text = re.sub(r"[*_`]+", "", text or "")
    return fold_text(text.translate(_MARKS))


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


def _grounded(subject: str, quote: str, section: str, title: str, city_name: str) -> bool:
    """The subject's words are in the quote, the page title or `window_chars` of the page before the quote's end
    (a venue is often named in the heading and the quote says "nơi đây")."""
    g = rules()["gate"]
    words = tokens(subject, city_name, stop=False)
    if not words:
        return True
    ns, nq = norm(section), norm(quote)
    end = ns.find(nq) + len(nq)
    window = ns[max(0, end - len(nq) - g["window_chars"]):end]
    have = tokens(f"{title} {window}", stop=False)
    return len(words & have) / len(words) >= (g["subject_cover"] if len(words) > 1 else 1.0)


def _check_text(item: dict, subject: str, text: str, subject_kind: str, section: str, quote: str, title: str,
                city_name: str, has_number: bool) -> str | None:
    """Reason a gated claim is noise, None when it says something about a named subject."""
    g, t = rules()["gate"], rules()["topic"]
    folded = fold(text)
    if any(p.search(folded) for p in g["epithets"]):
        return "epithet"
    sw = tokens(subject, city_name, stop=False)
    if sw and sw <= set(g["vague_words"]) or fold(subject).split()[:1] and fold(subject).split()[0] in g["vague_starts"]:
        return "vague_subject"
    if subject_kind == "city" and city_name:
        markers = {w for m in t["markers"].get(_city_key(city_name), []) for w in tokens(m, stop=False)}
        if tokens(subject, city_name) - markers:
            return "subject_not_city"
    elif subject_kind != "city" and not _grounded(subject, quote, section, title, city_name):
        return "subject_not_in_text"
    if fold(subject).split()[-1:] and fold(subject).split()[-1] in g["vague_ends"]:
        return "vague_subject"
    if len(fold(subject).split()) > g["max_subject_words"] or ("," in subject and subject_kind != "city"):
        return "vague_subject"
    if not has_number:
        extra = tokens(text, city_name) - sw - set(g["filler_words"])
        if len(extra) < g["min_extra_words"]:
            return "empty_claim"
    elif item.get("kind") == "price_norm" and not {w for w in tokens(text, city_name) - sw - set(g["price_filler"]) if not any(ch.isdigit() for ch in w)}:
        return "empty_claim"   # "dao động từ 400.000 đến 1.000.000đ/người": a price of what?
    return None


def _states(text: str, lo: int, hi: int, months: list[int], days: list[str], hours: str, weather: str) -> bool:
    """True when the claim's own text states its amounts, months, day types, hours and weather."""
    q = norm(text)
    if any(a and not amount_in(text, a) for a in {lo, hi}) or not set(months) <= months_in(text):
        return False
    if any(not _words(q, _DAY_WORDS[d]) for d in days):
        return False
    if hours and not all(hour_in(text, h) for h in re.findall(r"\d\d:\d\d", hours)):
        return False
    return not weather or _words(q, _WEATHER_WORDS[weather])


def _city_key(city_name: str) -> str:
    return fold(city_name).replace(" ", "")


def gate_claim(item: dict, section: str, resolve: Callable[[str], str | None] | None = None, *, city_name: str = "",
               title: str = "") -> tuple[dict | None, str | None]:
    """(claim, None) when the claim stands, else (None, the reason it is dropped). `resolve(name)` gives the place id
    of a named venue or None; a venue that does not resolve is kept as `poi_unresolved` (a nominee, never a fact about
    a place we hold). `city_name` and `title` (the Document's) switch on the rules that need them: the subject of a
    city claim is the city, every other subject is named near its quote."""
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

    has_number = bool(lo or hi or months or hours or days or weather or re.search(r"\d", text))
    bad = _check_text(item, subject, text, subject_kind, section, quote, title, city_name, has_number)
    if bad:
        return None, bad

    if not _states(text, lo, hi, months, days, hours, weather):
        text = quote  # the text must itself say every number it carries: when it does not, the whole quote is the text

    subject_id = None
    if subject_kind == "poi":
        subject_id = resolve(subject) if resolve else None
        subject_kind = "poi" if subject_id else "poi_unresolved"
    return {"subject_kind": subject_kind, "subject": subject, "subject_id": subject_id, "kind": kind, "text": text,
            "quote": quote, "amount_min_vnd": lo or None, "amount_max_vnd": hi or None,
            "when": {"months": months, "days": days, "hours": hours, "weather": weather},
            "who": " ".join(str(item.get("who") or "").split())}, None
