"""Code rules over the Extractor's events (docs/CORPUS.md §Sự kiện sắp tới): an event stands only when its quote is in
the page it was read from, the quote holds the event's name and its first day, and it is not over. Events of several
pages that are the same event merge into one with every page as a source. No model here."""

import re
import unicodedata
from datetime import date, timedelta

_COMBINING = re.compile(r"[̀-ͯ]")
_NOT_WORD = re.compile(r"[^a-z0-9]+")
# a name that is only a place, a ward, a season or a stretch of time is not an event's name
NOT_A_NAME = re.compile(r"^(phuong|xa|quan|thanh pho|tp|tinh|quang truong|thang|mua|tuan|cuoi tuan|ngay|dip)\b")
# words two pages may add or drop around the same event's name ("lần thứ XI", "năm 2026")
LOOSE = {"lan", "thu", "nam", "le", "hoi", "festival", "chuong", "trinh", "su", "kien", "tai", "da", "lat", "dalat",
         "lam", "dong", "quoc", "te", "viet"}
SAME_EVENT = 0.6  # share of the shorter name's own words the other name holds


def fold(text: str) -> str:
    text = _COMBINING.sub("", unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d")))
    return " ".join(_NOT_WORD.sub(" ", text).split())


def _day(text: str) -> date | None:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def _numbers(text: str) -> set[int]:
    """The numbers a quote holds, an English month name as its number ("Fri, Nov 20" -> 20 and 11)."""
    words = {MONTHS[w[:3]] for w in re.findall(r"[a-z]{3,9}", (text or "").lower()) if w[:3] in MONTHS}
    return {int(n) for n in re.findall(r"\d+", text)} | words


def why_not(item: dict, page_text: str, today: date, horizon_days: int, city: str) -> str | None:
    """The rule an extracted event breaks, or None when it stands. `item` = {name, start, end, time, venue, summary,
    quote} as the Extractor wrote it; `page_text` = the text it read."""
    name, quote = (item.get("name") or "").strip(), (item.get("quote") or "").strip()
    if not name or not quote:
        return "no name or quote"
    if fold(quote) not in fold(page_text):
        return "quote not in the page"
    fname = fold(name)
    if fname == fold(city) or NOT_A_NAME.match(fname) or len(fname.split()) < 2:
        return "not an event's name"
    own = [w for w in fname.split() if not w.isdigit()]
    if sum(w in fold(quote).split() for w in own) < SAME_EVENT * len(own):
        return "quote does not name it"
    start, end = _day(item.get("start")), _day(item.get("end")) or _day(item.get("start"))
    if start is None:
        return "no day"
    if end < start:
        return "ends before it starts"
    if not {start.day, start.month} <= _numbers(quote):
        return "quote does not hold its first day"
    if end < today:
        return "over"
    if start > today + timedelta(days=horizon_days):
        return "too far ahead"
    return None


def kept(item: dict, page: dict, today: date) -> dict:
    """The event as stored: its own fields and the page it came from."""
    start = _day(item["start"])
    end = _day(item.get("end")) or start
    time = item.get("time") or ""
    return {"name": item["name"].strip(), "start": start.isoformat(), "end": end.isoformat(),
            "time": time if re.fullmatch(r"\d{1,2}:\d{2}", time) and time not in ("00:00", "0:00") else "",  # 12:00 AM = no hour
            "venue": (item.get("venue") or "").strip()[:120], "summary": (item.get("summary") or "").strip()[:220],
            "image": page.get("image") or "", "images": [page["image"]] if page.get("image") else [],
            "sources": [{"url": page["url"], "domain": page["domain"], "title": page.get("title") or "",
                         "quote": item["quote"].strip()[:300], "read": today.isoformat()}]}


def _words(name: str) -> set[str]:
    return {w for w in fold(name).split() if w not in LOOSE and not w.isdigit()}


def same(a: dict, b: dict) -> bool:
    """Two pages' events are one: the same first day, or overlapping days, and most of the shorter name's own words."""
    wa, wb = _words(a["name"]), _words(b["name"])
    if not wa or not wb:
        return False
    overlap = a["start"] <= b["end"] and b["start"] <= a["end"]
    return overlap and len(wa & wb) >= SAME_EVENT * min(len(wa), len(wb))


def merge(events: list[dict], social: tuple[str, ...] = ()) -> list[dict]:
    """One row per event, its sources together (three at most), the longest summary and the first picture; ordered by
    first day. A page that disagrees on the days does not merge (two rows; the reader sees both), except a row only
    social posts back when a site names the same event: the site's days win (a tour post dates its own trip)."""
    out: list[dict] = []
    for e in events:
        twin = next((o for o in out if same(o, e)), None)
        if twin is None:
            out.append({**e, "sources": list(e["sources"])})
            continue
        if (e["end"], e["start"]) > (twin["end"], twin["start"]) and e["start"] <= twin["start"]:
            # the page with the whole run of days names it best ("13–15/11" over a page about its main night)
            twin.update(name=e["name"], start=e["start"], end=e["end"])
        known = {s["url"] for s in twin["sources"]}
        twin["sources"] += [s for s in e["sources"] if s["url"] not in known]
        twin["sources"] = twin["sources"][:3]
        if len(e["summary"]) > len(twin["summary"]):
            twin["summary"] = e["summary"]
        twin["images"] = twin.get("images", []) + [i for i in e.get("images", []) if i not in twin.get("images", [])]
        for k in ("time", "venue"):
            twin[k] = twin[k] or e[k]
    only_social = lambda e: all(any(s["domain"] == d or s["domain"].endswith("." + d) for d in social)  # noqa: E731
                                for s in e["sources"])
    named = lambda a, b: (wa := _words(a["name"])) and (wb := _words(b["name"])) and (  # noqa: E731
        len(wa & wb) >= SAME_EVENT * min(len(wa), len(wb)))
    out = [e for e in out if not (only_social(e) and any(o is not e and not only_social(o) and named(o, e) for o in out))]
    # a picture on two events' pages is the site's own banner, not the event's: each event takes its first picture no
    # other event shares, else none (the chat shows its day instead)
    used: dict[str, int] = {}
    for e in out:
        for i in set(e.get("images", [])):
            used[i] = used.get(i, 0) + 1
    for e in out:
        e["image"] = next((i for i in e.pop("images", []) if used[i] == 1), "")
    return sorted(out, key=lambda e: (e["start"], e["name"]))
