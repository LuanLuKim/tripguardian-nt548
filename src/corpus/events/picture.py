"""A picture for an event or a season from an image search (docs/CORPUS.md §Sự kiện sắp tới): SearXNG `categories=images`
by the name and the city, kept only when code rules pass. No model here.

A result stands when its page title holds the name's own words (most of them), names no other year, an event's
picture was not uploaded years before the event (a year in its address), the picture is
https, large enough and not a tall poster strip or a thin banner, and neither the picture nor its page is a social post
(behind a login, or a stranger's photo). A picture already used for another row is skipped: the same picture on two
events is a site's banner."""

import re

from .gate import LOOSE, fold

TITLE_WORDS = 0.75      # share of the name's own words the result's page title must hold
MIN_SIDE = 480          # px, the shorter side
RATIO = (0.6, 2.4)      # width / height
SKIP_URL = re.compile(r"(logo|icon|avatar|favicon|banner|sprite|placeholder|default)", re.I)
SOCIAL_IMG = ("fbsbx.com", "fbcdn.net", "pinimg.com", "cdninstagram.com", "tiktokcdn.com", "twimg.com", "ytimg.com")
_SIZE = re.compile(r"(\d{2,5})\s*[x×]\s*(\d{2,5})")
_YEAR = re.compile(r"\b(20\d\d)\b")
_URL_YEAR = re.compile(r"(?<!\d)(20[0-3]\d)(?!\d)")


def own_words(name: str) -> set[str]:
    """The words that name this event or season, without the loose ones two pages add or drop."""
    return {w for w in fold(name).split() if w not in LOOSE and not w.isdigit() and len(w) > 1}


def size(resolution: str) -> tuple[int, int] | None:
    m = _SIZE.search(resolution or "")
    return (int(m[1]), int(m[2])) if m else None


def _host(url: str) -> str:
    return re.sub(r"^www\.", "", (re.match(r"https?://([^/:?#]+)", url or "") or [None, ""])[1].lower())


def _on(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def why_not(result: dict, name: str, year: int | None, social: tuple[str, ...], taken: set[str]) -> str | None:
    """Why one image result does not picture `name`, or None when it does."""
    src, page, title = result.get("img_src") or "", result.get("url") or "", result.get("title") or ""
    if not src.startswith("https://"):
        return "not https"
    if src in taken:
        return "used by another row"
    if _on(_host(src), SOCIAL_IMG) or _on(_host(page), social):
        return "social"
    if SKIP_URL.search(src.rsplit("/", 1)[-1]):
        return "logo or banner"
    want = own_words(name)
    if not want or len(want & set(fold(title).split())) < TITLE_WORDS * len(want):
        return "title does not name it"
    if year and any(int(y) != year for y in _YEAR.findall(title)):
        return "another year"
    if year and (years := [int(y) for y in _URL_YEAR.findall(src + " " + page)]) and max(years) < year - 1:
        return "an old picture"     # uploaded years ago ("/2018/11/", "năm2024"): another year's event, or another place's
    wh = size(result.get("resolution") or "")
    if wh is None:
        return "no size"
    w, h = wh
    if min(w, h) < MIN_SIDE or not RATIO[0] <= w / h <= RATIO[1]:
        return "too small or out of shape"
    return None


def pick(results: list[dict], name: str, year: int | None, social: tuple[str, ...], taken: set[str]) -> dict | None:
    """The first result that pictures `name`: {image, page, domain}, or None."""
    for r in results:
        if not isinstance(r, dict):
            continue
        if why_not(r, name, year, social, taken) is None:
            return {"image": r["img_src"], "page": r.get("url") or "", "domain": _host(r.get("url") or "")}
    return None
