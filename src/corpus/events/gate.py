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
    if item.get("in_city") is False:  # an answer cached before the field existed has none: it stands as it was
        return "not in the city"
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


HEDGE = re.compile(r"\b(khoảng|gần|hơn|trên|tầm|ước chừng)\s+(?=\d)", re.I)


def clean_name(name: str) -> str:
    """The event's title without a listing's guess in it: "Triển lãm khoảng 150 tranh cổ động" is a count, not a name
    that wavers. Only a hedge word right before a number goes; no word is added."""
    return " ".join(HEDGE.sub("", name).split())


# Words a shouted listing ("JIMMII NGUYỄN & KHÁCH MỜI: …") keeps in lower case when it is written normally; every other word
# of a shouted name is a name and gets its capital.
_SMALL = {"và", "cùng", "với", "tại", "của", "khách", "mời", "lần", "thứ", "năm", "the", "and", "of", "in", "at", "with", "feat"}
_ROMAN_UP = re.compile(r"^(?=[IVXL]+$)L?X{0,3}(IX|IV|V?I{0,3})$")


def _shouted(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) >= 0.8 * len(letters)


def _word_case(word: str, first: bool) -> str:
    if _ROMAN_UP.match(word) or any(c.isdigit() for c in word):
        return word  # "XI", "2026", "K-POP2"
    if not first and word.lower().strip(":,.") in _SMALL:
        return word.lower()
    return "-".join(p[:1].upper() + p[1:].lower() for p in word.split("-"))  # "K-VIETNAM" -> "K-Vietnam"


def tidy_name(name: str) -> str:
    """An event's title as people write it: a shouted listing ("BẠCH CÔNG KHANH - DƯƠNG EDWARD") in name case, the first
    letter a capital ("lễ khai mạc …" -> "Lễ khai mạc …"), a spaced hyphen as a dash. Words are only re-cased, never changed."""
    name = " ".join((name or "").split())
    if _shouted(name):
        name = " ".join(_word_case(w, i == 0) for i, w in enumerate(name.split()))
    name = re.sub(r"\s+[-–—]\s+", " – ", name)
    return name[:1].upper() + name[1:]


def tidy_venue(venue: str, city: str) -> str:
    """The venue as the place's own name: a listing's " | Đà Lạt" tail and a bracketed ward ("(phường Xuân Hương - Đà Lạt)")
    go, so the name can match a place we know. A shouted venue is re-cased like a title."""
    city_f = fold(city)
    parts = [p.strip() for p in re.split(r"\s+\|\s+", " ".join((venue or "").split())) if p.strip()]
    parts = [p for p in parts if fold(p) not in (city_f, city_f.replace(" ", ""))] or parts[:1]
    out = re.sub(r"\s*\((?:[^)]*\b(?:phường|xã|quận|tp\.?|thành phố)\b[^)]*|[^)]*" + re.escape(city) + r"[^)]*)\)\s*$", "",
                 " | ".join(parts), flags=re.I).strip()
    return tidy_name(out) if _shouted(out) else out


def tidy(event: dict, city: str) -> dict:
    """The stored row with its title and venue tidied (tidy_name, tidy_venue), its parts too."""
    out = {**event, "name": tidy_name(event["name"]), "venue": tidy_venue(event.get("venue") or "", city)}
    if event.get("part_of"):
        out["part_of"] = tidy_name(event["part_of"])
    if event.get("parts"):
        out["parts"] = [tidy(p, city) for p in event["parts"]]
    return out


def kept(item: dict, page: dict, today: date) -> dict:
    """The event as stored: its own fields and the page it came from."""
    start = _day(item["start"])
    end = _day(item.get("end")) or start
    time = item.get("time") or ""
    return {"name": clean_name(item["name"].strip()), "start": start.isoformat(), "end": end.isoformat(),
            "time": time if re.fullmatch(r"\d{1,2}:\d{2}", time) and time not in ("00:00", "0:00") else "",  # 12:00 AM = no hour
            "venue": (item.get("venue") or "").strip()[:120], "summary": (item.get("summary") or "").strip()[:220],
            "image": page.get("image") or "", "images": [page["image"]] if page.get("image") else [],
            "sources": [{"url": page["url"], "domain": page["domain"], "title": page.get("title") or "",
                         "quote": item["quote"].strip()[:300], "read": today.isoformat()}],
            **({"part_of": part_of} if (part_of := _named_on(item.get("part_of"), page.get("text") or "", item["name"])) else {})}


def _named_on(part_of: str | None, text: str, name: str) -> str:
    """The larger event the Extractor says this one belongs to, when the page names it (most of its own words are on the
    page) and it is not the event itself; else ""."""
    part_of = clean_name((part_of or "").strip())
    own, page = _words(part_of), set(fold(text).split())
    if not own or fold(part_of) == fold(name) or NOT_A_NAME.match(fold(part_of)):
        return ""
    return part_of if len(own & page) >= SAME_EVENT * len(own) else ""


# An English page names the same event in English ("Da Lat Flower Festival" = "Festival Hoa Đà Lạt"): its words are read
# as the Vietnamese ones before two names are compared. Only words a festival name of the city uses.
ENGLISH = {"flower": "hoa", "flowers": "hoa", "coffee": "ca phe", "tea": "tra", "wine": "ruou vang", "music": "am nhac",
           "night": "dem", "lantern": "den", "lanterns": "den", "culture": "van hoa", "cultural": "van hoa",
           "food": "am thuc", "cuisine": "am thuc", "strawberry": "dau tay", "persimmon": "hong", "cherry": "mai anh dao",
           "blossom": "", "blossoms": "", "of": "", "the": "", "and": "", "in": "", "international": "quoc te"}
ROMAN = re.compile(r"^(?=[ivxl]+$)l?x{0,3}(ix|iv|v?i{0,3})$")  # "lần thứ XI": the edition, not the event


def _words(name: str) -> set[str]:
    words = " ".join(ENGLISH.get(w, w) for w in fold(name).split()).split()
    return {w for w in words if w not in LOOSE and not w.isdigit() and not (w != "vi" and ROMAN.match(w))}  # "vị" stays


def same(a: dict, b: dict) -> bool:
    """Two pages' events are one: overlapping days and most of the shorter name's own words."""
    wa, wb = _words(a["name"]), _words(b["name"])
    if not wa or not wb:
        return False
    overlap = a["start"] <= b["end"] and b["start"] <= a["end"]
    return overlap and len(wa & wb) >= SAME_EVENT * min(len(wa), len(wb))


def _domains(rows: list[dict]) -> int:
    return len({s["domain"] for r in rows for s in r["sources"]})


def merge(events: list[dict], social: tuple[str, ...] = ()) -> list[dict]:
    """One row per event, its sources together (three at most), the longest summary and the first picture; ordered by
    first day. The days (and the name that goes with them) are those the most independent sites give, so one page's
    vague "December to January" does not stretch a festival two sites date to the 19th-31st; on a tie the page with the
    whole run of days names it best ("13–15/11" over a page about its main night). A row that is the same event under
    other words of its own ("Không gian hoa" inside "Festival Hoa Đà Lạt") is kept as one of its `parts`; a translation
    of its name is not. A row only social posts back gives way to a site naming the same event (a tour post dates its own
    trip). Ceremonies and the rows the Extractor puts in a larger event then join it (`fold_parts`)."""
    clusters: list[list[dict]] = []
    for e in events:  # a programme (part_of) meets only its own repeats: it never votes on its festival's days
        home = next((c for c in clusters if bool(c[0].get("part_of")) == bool(e.get("part_of"))
                     and any(same(o, e) for o in c)), None)
        if home is None:
            clusters.append([e])
        else:
            home.append(e)
    out: list[dict] = []
    for rows in clusters:
        spans: dict[tuple[str, str], list[dict]] = {}
        for r in rows:
            spans.setdefault((r["start"], r["end"]), []).append(r)
        (start, end), lead = max(spans.items(), key=lambda kv: (_domains(kv[1]), _run(*kv[0]), -date.fromisoformat(kv[0][0]).toordinal()))
        head = lead[0]
        row = {**head, "sources": [], "images": []}
        own = _words(head["name"])
        parts = []
        for r in sorted(rows, key=lambda r: r is not head):
            known = {s["url"] for s in row["sources"]}
            row["sources"] += [s for s in r["sources"] if s["url"] not in known]
            row["images"] += [i for i in r.get("images", []) if i not in row["images"]]
            if len(r["summary"]) > len(row["summary"]):
                row["summary"] = r["summary"]
            for k in ("time", "venue"):
                row[k] = row[k] or r[k]
            if r is not head and not _words(r["name"]) <= own and not any(same(p, r) for p in parts):
                parts.append(_part(r))
        row["sources"] = row["sources"][:3]
        if parts:
            row["parts"] = parts
        out.append(row)
    only_social = lambda e: all(any(s["domain"] == d or s["domain"].endswith("." + d) for d in social)  # noqa: E731
                                for s in e["sources"])
    named = lambda a, b: (wa := _words(a["name"])) and (wb := _words(b["name"])) and (  # noqa: E731
        len(wa & wb) >= SAME_EVENT * min(len(wa), len(wb)))
    out = [e for e in out if not (only_social(e) and any(o is not e and not only_social(o) and named(o, e) for o in out))]
    out = fold_parts(out)
    # a picture on two events' pages is the site's own banner, not the event's: each event takes its first picture no
    # other event shares, else none (the chat shows its day instead)
    used: dict[str, int] = {}
    for e in out:
        for i in set(e.get("images", [])):
            used[i] = used.get(i, 0) + 1
    for e in out:
        e["image"] = next((i for i in e.pop("images", []) if used[i] == 1), "")
    return sorted(out, key=lambda e: (e["start"], e["name"]))


def _run(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _part(e: dict) -> dict:
    return {k: e[k] for k in ("name", "start", "end", "time", "venue")}


# A ceremony of a larger event, named by the page only as the ceremony ("Đêm Khai mạc", "Lễ bế mạc"): alone it says nothing
CEREMONY = re.compile(r"^(?:(?:dem|le|buoi|chuong trinh)\s+)?(?:khai mac|be mac|bai mac|ket thuc)\b")


def fold_parts(events: list[dict]) -> list[dict]:
    """A programme of a larger event is not an event of its own on the list: it joins that event as one of its `parts`
    (name, days, hour, venue) and brings its sources and pictures. A row is a programme when the Extractor read on its
    page that it belongs to a larger event (`part_of`) and a row on the list is that event (the same words, days that
    meet), or when it is a ceremony ("Đêm Khai mạc", "Đêm Bế mạc …") on a day of a multi-day event held at its venue
    (the tightest such run). Rows the page puts in the same larger event that is not on the list stay, their title saying
    which event they belong to ("Đêm Khai mạc – Festival Hoa Đà Lạt 2026")."""
    def parent_of(e: dict) -> dict | None:
        if e.get("part_of"):
            target = {"name": e["part_of"], "start": e["start"], "end": e["end"]}
            found = [o for o in events if o is not e and not o.get("part_of") and same(o, target)
                     and o["start"] <= e["end"] and e["start"] <= o["end"]]
            if found:
                return max(found, key=lambda o: (_domains([o]), _run(o["start"], o["end"])))
        if not CEREMONY.match(fold(e["name"])) or not e.get("venue"):
            return None
        venue = fold(e["venue"])
        found = [o for o in events if o is not e and o["start"] < o["end"] and o["start"] <= e["start"] <= o["end"]
                 and not CEREMONY.match(fold(o["name"])) and o.get("venue") and not o.get("part_of")
                 and (fold(o["venue"]) in venue or venue in fold(o["venue"]))]
        return min(found, key=lambda o: (_run(o["start"], o["end"]), -len(o["name"]))) if found else None

    joined = {}
    for e in events:
        if (top := parent_of(e)) is not None:
            joined[id(e)] = top
    for e in events:
        top = joined.get(id(e))
        if top is None:
            if e.get("part_of") and _words(e["part_of"]) - _words(e["name"]):
                e["name"] = f"{e['name']} – {e['part_of']}"
            continue
        top.setdefault("parts", [])
        for p in (_part(e), *e.get("parts", [])):
            if not any(same(q, p) for q in top["parts"]):
                top["parts"].append(p)
        known = {s["url"] for s in top["sources"]}
        top["sources"] = (top["sources"] + [s for s in e["sources"] if s["url"] not in known])[:3]
        top["images"] = top.get("images", []) + [i for i in e.get("images", []) if i not in top.get("images", [])]
    for e in events:
        if e.get("parts"):
            e["parts"] = sorted(({**p, "name": _short(p["name"], e["name"])} for p in e["parts"]), key=lambda p: (p["start"], p["name"]))
    return [e for e in events if id(e) not in joined]


CARRY_DAYS = 7  # an event a page dated within this many days stays on the list while it is not over


def carried(previous: list[dict], events: list[dict], today: date, days: int = CARRY_DAYS,
            programmes: tuple[tuple[str, str], ...] = ()) -> list[dict]:
    """Last night's events that tonight's pages did not name again: one night's search finds other pages, and an event
    still to come does not stop being true because no page repeated it. Kept while not over and while a page dated it
    within `days` (the newest `read` of its sources); one that tonight's list holds under the same name is not doubled.
    `programmes`: (name, festival) pairs tonight's pages state without a day ("Lễ hội nhạc Jazz" in Festival Hoa's
    programme): a carried row of that name, on the festival's days, becomes one of its parts."""
    out = []
    for e in previous:
        seen = max((s.get("read") or "" for s in e.get("sources", [])), default="")
        if not seen or e["end"] < today.isoformat() or (today - date.fromisoformat(seen)).days > days:
            continue
        if any(same(o, e) for o in events) or any(same(p, e) for o in events for p in o.get("parts", [])):
            continue
        # a page tonight lists it, undated, as a programme of a festival on the list: it joins that festival
        festival = next((o["name"] for name, parent in programmes for o in events
                         if same({"name": name, "start": e["start"], "end": e["end"]}, e)
                         and same({"name": parent, "start": o["start"], "end": o["end"]}, o)
                         and o["start"] <= e["end"] and e["start"] <= o["end"]), None)
        out.append({**e, "part_of": festival} if festival else e)
    return fold_parts(sorted(events + out, key=lambda e: (e["start"], e["name"])))  # a carried ceremony joins its festival


def _short(name: str, parent: str) -> str:
    """A programme's name without its festival's ("Lễ khai mạc Festival Hoa Đà Lạt lần thứ XI" -> "Lễ khai mạc"); the
    post already says which festival it belongs to. A name that is only the festival's stays whole."""
    words, head = name.split(), fold(parent).split()[:2]
    for k in range(1, len(words)):
        if [fold(w) for w in words[k:k + len(head)]] == head:
            cut = " ".join(words[:k]).rstrip(" –-:,")
            return cut[:1].upper() + cut[1:]
    return name[:1].upper() + name[1:]
