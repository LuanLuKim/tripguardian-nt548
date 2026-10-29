"""Short, clean place names for cards. Maps names carry the brand, the district, a tagline and a translation in
another script ("ĐÔI DÉP Camellia Tea Spa, Massage | Đà Lạt (달랏 마사지 스파)"); a person wants "ĐÔI DÉP Camellia Tea Spa".
Pure text rules, nothing is looked up or invented: every word kept is in the corpus name."""

import re

FOREIGN = re.compile("[Ѐ-ӿ؀-ۿ฀-๿ᄀ-ᇿ぀-ヿ㄰-㆏"
                     "㐀-䶿一-鿿가-힯]+")      # Cyrillic, Arabic, Thai, Korean, Japanese, Chinese
SEP = re.compile(r"\s+[-–—]\s*|\s*[-–—]\s+|\s*\|\s*|\s+/\s+|,\s+")
CITY = {"đà lạt", "da lat", "dalat", "đà lạt city", "tp đà lạt", "thành phố đà lạt"}
MAX_LEN = 40       # a name on a card; longer is cut at a word
WEAK_LEN = 6       # a head shorter than this (or one word among several parts) is not a name on its own


def _clean(part: str) -> str:
    return part.strip(" \t()[]{}&,.:;*·•")


def _cut(text: str) -> str:
    if len(text) <= MAX_LEN:
        return text
    return text[:MAX_LEN].rsplit(" ", 1)[0].rstrip(" -–—,&")


def short_name(name: str | None) -> str:
    """The name a card shows. Drops text in another script, empty brackets, a district / city part and the tagline
    after the first separator (" - ", " | ", ", ", " / "); a head too thin to be a name keeps the next parts (up to
    MAX_LEN). Nothing usable left -> the original name."""
    raw = (name or "").strip()
    text = re.sub(r"\(\s*\)|\[\s*\]", "", FOREIGN.sub(" ", raw))
    parts = [p for p in (_clean(x) for x in SEP.split(text)) if re.search(r"\w", p)]
    parts = [p for p in parts if p.lower() not in CITY]
    if not parts:
        return raw
    head = parts[0]
    if len(head) >= WEAK_LEN and (len(head.split()) >= 2 or len(parts) == 1):
        return _cut(head)
    out = head
    for p in parts[1:]:
        if len(out) + 3 + len(p) > MAX_LEN:
            break
        out += " – " + p
    return _cut(out)
