"""The name a place carries in Place Intelligence (docs/CORPUS.md §5).

Google lists the name the owner typed: all capitals, a tagline after a dash, hashtags, a Korean copy in brackets, a
lower-case first letter. `display_name` only removes, re-cases and shortens; it never adds a word. The raw name stays in
the observation files and in the intel file as `place_name_raw`. web/src/data/placeName.ts is the same function, kept
in step (tests/corpus/test_place_naming.py reads its test table); the web applies it again, harmlessly, on older releases.
"""

from __future__ import annotations

import re
import unicodedata

MAX = 44  # characters; a longer name is cut at a word boundary
_LOWER_WORDS = {"và", "của", "cho", "ở", "tại", "the", "of", "and", "&"}
_NON_LATIN_PREFIXES = ("HANGUL", "CJK", "HIRAGANA", "KATAKANA", "THAI")
_TRIM_END = " \t\r\n,;:.-–—|/&"
_TRIM_START = " \t\r\n,;:.-–—|/"
_CUT = re.compile(r"\s[-–—|/•·:]\s|\s[-–—](?=\S)|(?<=\S)[-–—]\s|\s:|:\s|\|")
_SPACE_DOT = re.compile(r"\s\.(?=[^\W\d_])")
_ACRONYM = re.compile(r"^[A-Z]{2,4}$|[0-9]")


def _non_latin(ch: str) -> bool:
    if ch.isascii():
        return False
    try:
        return unicodedata.name(ch).startswith(_NON_LATIN_PREFIXES)
    except ValueError:
        return False


def _letters(s: str) -> str:
    return "".join(c for c in s if c.isalpha())


def _is_upper(s: str) -> bool:
    letters = _letters(s)
    return len(letters) >= 3 and letters == letters.upper()


def _is_lower(s: str) -> bool:
    letters = _letters(s)
    return len(letters) >= 3 and letters == letters.lower()


def _cap(w: str) -> str:
    return w[:1].upper() + w[1:] if w else w


def _title(s: str) -> str:
    out = []
    for i, w in enumerate(re.split(r"(\s+)", s)):
        if i % 2 or re.search(r"[0-9]|\.", w):
            out.append(w)
        elif i > 0 and w.lower() in _LOWER_WORDS:
            out.append(w.lower())
        else:
            out.append(_cap(w.lower()))
    return "".join(out)


def _retitle_shouting(s: str) -> str:
    """Two or more capital words in a row inside a mixed-case name are shouting; a short ASCII word or a token with a digit is an acronym."""
    words = s.split(" ")

    def shout(w: str) -> bool:
        return bool(w) and not _ACRONYM.search(w) and len(_letters(w)) >= 2 and _letters(w) == _letters(w).upper()

    return " ".join(_cap(w.lower()) if shout(w) and (shout(words[i - 1] if i else "") or shout(words[i + 1] if i + 1 < len(words) else "")) else w
                    for i, w in enumerate(words))


def _dot_cut(s: str) -> int:
    """First index of a dot that starts a new sentence: "CS2 .lẩu", "tầm.Gà", "stayDuong.dalat"."""
    hits = [m.start() for m in _SPACE_DOT.finditer(s)]
    hits += [i for i, ch in enumerate(s) if ch == "." and i >= 2 and s[i - 2].islower() and s[i - 1].islower()
             and s[i - 2].isalpha() and s[i - 1].isalpha() and i + 1 < len(s) and s[i + 1].isalpha()]
    return min(hits) if hits else -1


def display_name(raw: str) -> str:
    s = unicodedata.normalize("NFC", raw)
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", lambda m: " " if any(_non_latin(c) for c in m.group(0)) else m.group(0), s)
    s = "".join(" " if _non_latin(c) else c for c in s)
    s = re.sub(r"#\S+", " ", s).replace("_", " ")
    s = s.lstrip(_TRIM_START + "&")
    bare = re.sub(r"\s*\([^)]*\)?", " ", s)  # a bracketed description after the name
    if len(_letters(bare)) >= 4:
        s = bare
    m = _CUT.search(s)
    if m and m.start() > 2:
        s = s[:m.start()]
    dot = _dot_cut(s)
    if dot > 2:
        s = s[:dot]
    if len(s) > 28:
        comma = s.find(",")
        if comma > 8:
            s = s[:comma]
    s = re.sub(r"\s+", " ", s).rstrip(_TRIM_END).lstrip(_TRIM_START).strip()
    if not s:
        return raw.strip()
    s = _title(s) if _is_upper(s) or _is_lower(s) else _cap(_retitle_shouting(s))
    if len(s) > MAX:
        at = s.rfind(" ", 0, MAX)
        s = s[:at if at > 12 else MAX - 1].rstrip(_TRIM_END) + "…"
    return s
