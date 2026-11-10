"""Clef prepares the assistant's read tools before the agent's one call (spec 2026-10-26 §B.3, measured §2.4).

Code finds the places a message may name; one Clef request says which tool groups the message needs and which of
those places it means; keyword rules only add groups. The chosen read tools then run at once through TurnTools, so
their results are in the turn's cache when the agent calls them again.
"""

from __future__ import annotations

import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import date

from ..domain.dates import FULL_DATE, day_month, relative_dates
from ..domain.state import TripState
from ..domain.text import fold
from ..infrastructure import clef
from ..infrastructure.catalog import Catalog
from ..infrastructure.settings import Settings
from .services_tool import kind_in, kinds_in

# One yes / no question per tool group (wording measured in logs/clef_prefetch_bench.py GROUPS2)
GROUPS = {
    "places": "Để trả lời, có cần TÌM một danh sách địa điểm (quán, món ăn ở đâu, nơi chơi) không? Tin nhắn có thể hỏi "
              "nhiều ý; chỉ cần một ý cần tìm nơi là có.",
    "detail": "Tin nhắn có hỏi giờ mở cửa, giá, vé, chỗ đậu xe, view hay đặc điểm của một địa điểm CÓ TÊN không? Tin "
              "nhắn có thể hỏi nhiều ý.",
    "weather": "Tin nhắn có hỏi thời tiết, mưa, lạnh của một ngày cụ thể (hôm nay, mai, thứ mấy, ngày X) không? Tin "
               "nhắn có thể hỏi nhiều ý.",
    "distance": "Tin nhắn có hỏi khoảng cách, đi mất bao lâu, bao xa giữa hai nơi không? Tin nhắn có thể hỏi nhiều ý.",
}
# Keyword rules that only add a group Clef missed (on the accented, lowercased message)
DETAIL_WORDS = re.compile(r"mấy giờ|mở cửa|giờ mở|vé|giá|bao nhiêu tiền|đậu xe|đỗ xe|gửi xe|view|có gì")
WEATHER_WORDS = re.compile(r"mưa|trời|thời tiết|lạnh|nắng")
LIST_WORDS = re.compile(r"nào|gợi ý|tìm|ở đâu|chỗ nào|quán gì|ăn gì|đi đâu")
ASKS_LIST = re.compile(r"nào|gợi ý|tìm|ở đâu")
# a message that names a place to eat / drink / see as well as a service keeps the places list
PLACE_WORDS = re.compile(r"quán|cà phê|cafe|nhà hàng|ăn |uống|homestay|khách sạn|check.?in|tham quan|điểm|chơi|món")
CENTER_WORDS = re.compile(r"\bchợ\b|trung tâm")
# trends (Nhịp Đà Lạt) is asked by words alone: no extra Clef question, no cost; one kind when the words name one
TREND_WORDS = re.compile(r"đang hot|\bhot\b|xu hướng|dạo này|gần đây|sự kiện|lễ hội|festival|vào mùa|đang mùa|mùa hoa|mùa gì|"
                         r"mới mở|mới khai trương|nhiều người nhắc|được nhắc|đang được|đang nổi|nổi trên|tiktok|đóng cửa")
TREND_KINDS = (("event", re.compile(r"sự kiện|lễ hội|festival")), ("season", re.compile(r"vào mùa|đang mùa|mùa hoa|mùa gì")),
               ("new", re.compile(r"mới mở|mới khai trương")), ("closed", re.compile(r"đóng cửa")))
CENTER = "center"  # Knowledge.distance's name for the city centre (config/cities.yaml center)
# words too common in place names to tell one place from another (kept with their accents)
GENERIC = set("quán cà phê cafe coffee coffe đà lạt dalat nhà hàng restaurant homestay hotel khách sạn the vườn garden "
              "khu du lịch kdl của tiệm shop house farm and of tại hồ đồi chợ thác đi đỉnh núi villa".split())
MIN_WORD = 3  # a distinctive word has at least this many characters


def vnorm(s: str) -> str:
    """Lower case, accents kept ("lên" is not "len"), punctuation to spaces."""
    return " ".join(re.sub(r"[^\w]", " ", unicodedata.normalize("NFC", (s or "").lower())).split())


def _aliases(catalog: Catalog) -> list[tuple[str, frozenset[str], int, object]]:
    """(name, distinctive words, voices, place) of every place, built once per catalog."""
    if "_vnames" not in catalog.__dict__:
        out = []
        for p in catalog.places:
            name = vnorm(p.name)
            words = frozenset(w for w in name.split() if w not in GENERIC and len(w) >= MIN_WORD)
            voices = ((p.evidence_record or {}).get("provenance") or {}).get("voices") or p.weight or 0
            out.append((name, words, voices, p))
        catalog.__dict__["_vnames"] = out
    return catalog.__dict__["_vnames"]


def candidates(text: str, catalog: Catalog, k: int = 6) -> list[tuple[str, str]]:
    """(id, name) of the places the message may name: a whole name inside the message first, then a short message
    that is a phrase of a longer name, then names whose distinctive words are all in it; longer, then more reviewed first. A lodging only by its whole name."""
    m = vnorm(text)
    padded, words = f" {m} ", set(m.split())
    hits = []
    for name, distinct, voices, p in _aliases(catalog):
        if not distinct:
            continue  # a city/category-only name is context, not a named POI
        if f" {name} " in padded:
            hits.append((2, len(name), voices, p))
        elif len(words) >= 2 and len(m) <= 40 and f" {m} " in f" {name} " and distinct & words:
            # a generic phrase names no one place; a stay counts here too, so "đồi chè" stays ambiguous with its hotel
            # the whole short reference inside a longer name: "Tao Ngộ" is "Lẩu Gà Lá É Tao Ngộ 5", not "Ngộ coffee"
            hits.append((1.5, len(m), voices, p))
        elif distinct and distinct <= words and p.category_group != "stay":
            hits.append((1, len(" ".join(distinct)), voices, p))
    hits.sort(key=lambda h: (-h[0], -h[1], -h[2]))
    out, seen = [], set()
    for *_, p in hits:
        if p.id not in seen:
            seen.add(p.id)
            out.append((p.id, p.name))
    return out[:k]


def place_id(ref: str, catalog: Catalog, prefer: set[str] = frozenset()) -> str | None:
    """The corpus id a place reference of the model means: an id as it is; "center" for "chợ Đà Lạt / trung tâm";
    a name ("lululola", "Hồ Tuyền Lâm") when it names ONE place (a place this turn's data already holds wins).
    None when it names no place or several: never a guess."""
    if ref == CENTER or ref in catalog.by_id:
        return ref
    r = vnorm(ref)
    if not r:
        return None
    if CENTER_WORDS.search(r) and set(r.split()) <= GENERIC | {"trung", "tâm"}:
        return CENTER
    exact = [p.id for name, _, _, p in _aliases(catalog) if name == r]
    if len(exact) == 1:
        return exact[0]
    wide = [pid for pid, _ in candidates(ref, catalog, 40)] if not exact else exact
    preferred = [pid for pid in wide if pid in prefer]  # a place already shown wins even past the first six names
    if len(preferred) == 1:
        return preferred[0]
    hits = wide[:6]
    return hits[0] if len(hits) == 1 else None


@dataclass
class Route:
    groups: set[str]
    places: list[str]  # ids the message means, in its order; "center" for "chợ / trung tâm"
    probs: dict[str, float] = field(default_factory=dict)
    clef_s: float = 0.0
    services: list[str] = field(default_factory=list)


def route(text: str, cands: list[tuple[str, str]], cfg: Settings, ask=clef.ask, today: date | None = None) -> Route:
    """One Clef request: which tool groups the message needs, which candidate places it names. A group counts from
    cfg.assistant.clef_threshold; keyword rules then only add. Clef off or failing ({}) = the keyword rules alone."""
    questions = {g: {"type": "choice", "instructions": f"Tin nhắn của khách du lịch Đà Lạt. {q}",
                     "criteria": {"A": "có", "B": "không"}} for g, q in GROUPS.items()}
    if cands:
        options = {**{f"P{i}": name for i, (_, name) in enumerate(cands)}, "NONE": "không nhắc tới nơi nào trong danh sách"}
        questions["place1"] = {"type": "choice", "criteria": options,
                               "instructions": "Địa điểm thứ nhất (hoặc duy nhất) tin nhắn nhắc tới là nơi nào?"}
        questions["place2"] = {"type": "choice", "criteria": options,
                               "instructions": "Nếu tin nhắn nhắc tới HAI nơi (ví dụ đi từ A đến B), nơi thứ hai là nơi "
                                               "nào? Không có thì NONE."}
    started = time.monotonic()
    answers = ask({"user_message": text, "today": (today or date.today()).isoformat()}, questions, cfg) or {}
    clef_s = time.monotonic() - started
    probs = {g: clef.yes_prob(answers, g) for g in GROUPS}
    groups = {g for g, p in probs.items() if p >= cfg.assistant.clef_threshold}
    places: list[str] = []
    for q in ("place1", "place2"):
        choice = str((answers.get(q) or {}).get("choice") or "")
        if re.fullmatch(r"P\d+", choice) and int(choice[1:]) < len(cands) and cands[int(choice[1:])][0] not in places:
            places.append(cands[int(choice[1:])][0])
    m = vnorm(text)
    if places and DETAIL_WORDS.search(m):
        groups.add("detail")
    if WEATHER_WORDS.search(m):
        groups.add("weather")
    if LIST_WORDS.search(m) and not (places and not ASKS_LIST.search(m)):
        groups.add("places")
    if "detail" in groups and places and not LIST_WORDS.search(m):
        groups.discard("places")  # a question about one named place needs no list
    if kind_in(text):  # ATM, cây xăng, thuê xe...: find_services answers, find_places has no such place
        groups.add("services")
        if not PLACE_WORDS.search(m):
            groups.discard("places")
    if TREND_WORDS.search(m):
        groups.add("trends")
    if "distance" in groups and len(places) < 2 and CENTER_WORDS.search(m) and CENTER not in places:
        places.append(CENTER)
    return Route(groups, places, probs, clef_s, kinds_in(text))


def covers(route: Route, data: dict | None) -> bool:
    """The prepared data answers every group the message needs: places found, every named place's details, the
    weather, the travel time, none of them an error. Nothing asked of the data (no group) is not covered."""
    data = data or {}
    ok = lambda rows: bool(rows) and all(isinstance(x, dict) and "error" not in x for x in rows)  # noqa: E731
    need = {
        "places": lambda: ok(data.get("tim_noi")),
        "detail": lambda: bool(named := [p for p in route.places if p != CENTER]) and ok(data.get("chi_tiet"))
        and set(named) <= {x.get("id") for x in data["chi_tiet"]},
        "weather": lambda: ok(data.get("thoi_tiet")),
        "distance": lambda: ok([data["khoang_cach"]] if "khoang_cach" in data else []),
        "trends": lambda: bool((data.get("xu_huong") or {}).get("items")) and "error" not in data["xu_huong"],
        "services": lambda: "dich_vu" in data and "error" not in data["dich_vu"]
        and all(k in data["dich_vu"].get("by_kind", {}) and "error" not in data["dich_vu"]["by_kind"][k]
                for k in route.services),
    }
    return bool(route.groups) and all(g in need and need[g]() for g in route.groups)


def places_query(text: str) -> str:
    """The part of the message that asks for places: clauses about the weather are left out."""
    parts = [c.strip() for c in re.split(r"[,.;?]| và ", text) if c.strip() and not WEATHER_WORDS.search(vnorm(c))]
    return " ".join(parts) or text


def asked_day(text: str, today: date) -> date | None:
    """The day the message asks about: "31/10", "mai", "thứ 7"; None when it names none."""
    low = fold(text)
    if m := FULL_DATE.search(low):
        try:
            return day_month(int(m[1]), int(m[2]), today, int(m[3]) if m[3] else None)
        except ValueError:
            return None
    return next((r.value for r in relative_dates(low, unicodedata.normalize("NFC", text).lower(), today)
                 if r.field == "start_date"), None)


def start_weather(state: TripState, tools) -> dict:
    """The trip's start day's weather, started now: it needs no answer from Clef, so it runs while Clef is asked and
    `prepare` takes the running call instead of starting it again. {} when the trip has no start day."""
    if not state.start_date.known:
        return {}
    args = {"date": state.start_date.value.isoformat()}
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prefetch-early")
    future = pool.submit(tools.run, "weather", args)
    pool.shutdown(wait=False)
    return {("weather", state.start_date.value.isoformat()): future}


WEEK = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
HOUR = re.compile(r"\b(\d{1,2})\s*(?:h|giờ|g)\s*(\d{2})?\s*(sáng|trưa|chiều|tối|đêm|khuya)?(?!\w)", re.I)


def asked_hour(text: str) -> str | None:
    """The clock time a message asks places to be open at ("11h đêm" -> 23:00, "10 giờ tối" -> 22:00, "23h" -> 23:00,
    "ăn khuya" -> 22:00), or None. Only an hour the user wrote, or "khuya"; never a guess from other words."""
    t = unicodedata.normalize("NFC", text).lower()
    if not re.search(r"\b(mở|mở cửa|còn|ăn|uống|đi|chỗ|quán|nơi)\b", t):
        return None
    if m := HOUR.search(t):
        h, mm, part = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if part in ("chiều", "tối", "đêm", "khuya") and h < 12:
            h += 12
        if part in ("đêm", "khuya") and h == 24:
            h = 23
        if 0 <= h <= 23 and 0 <= mm < 60:
            return f"{h:02d}:{mm:02d}"
        return None
    return "22:00" if re.search(r"\bkhuya\b|\băn đêm\b", t) else None


def prepare(route: Route, text: str, state: TripState, tools, today: date, wait_s: float, early: dict | None = None) -> dict:
    """Run the read tools the route needs at once through `tools` (TurnTools), wait at most `wait_s`, and return what
    is ready as the agent's data: {"tim_noi", "chi_tiet", "thoi_tiet", "khoang_cach", "xu_huong"} (only keys with data). A tool
    still running is left out here and lands in the turn's cache when it ends. The trip's start day's weather is
    always prepared when it is known."""
    named = [p for p in route.places if p != CENTER]
    jobs: list[tuple[str, str, dict]] = []
    if "places" in route.groups:
        criteria: dict = {"text": places_query(text)}
        if (hhmm := asked_hour(text)) is not None:  # "11h đêm còn chỗ nào ăn": only places open then, not any place
            criteria["open_at"] = [WEEK[today.weekday()], hhmm]
        jobs.append(("tim_noi", "find_places", {"criteria": criteria}))
    if "detail" in route.groups:
        jobs += [("chi_tiet", "get_place", {"id": pid}) for pid in named]
    days = []
    if "weather" in route.groups and (day := asked_day(text, today)) is not None:
        days.append(day)
    if state.start_date.known and state.start_date.value not in days:
        days.append(state.start_date.value)
    elif "weather" in route.groups and not days:
        days.append(today)
    jobs += [("thoi_tiet", "weather", {"date": d.isoformat()}) for d in days]
    if "distance" in route.groups and len(route.places) >= 2:
        jobs.append(("khoang_cach", "distance", {"a": route.places[0], "b": route.places[1]}))
    if "services" in route.groups:
        near = route.places[-1] if route.places else (CENTER if CENTER_WORDS.search(vnorm(text)) else None)
        jobs += [("dich_vu", "find_services", {"kind": kind, **({"near_place": near} if near else {})})
                 for kind in route.services or kinds_in(text)]
    if "trends" in route.groups:
        kinds = [k for k, rx in TREND_KINDS if rx.search(vnorm(text))]
        jobs.append(("xu_huong", "trends", {"kind": kinds[0]} if len(kinds) == 1 else {}))
    if not jobs:
        return {}
    pool = ThreadPoolExecutor(max_workers=min(8, len(jobs)), thread_name_prefix="prefetch")
    early = early or {}
    futures = [(key, early.get((name, args.get("date"))) or pool.submit(tools.run, name, args)) for key, name, args in jobs]
    wait([f for _, f in futures], timeout=wait_s)
    pool.shutdown(wait=False)  # a tool still running finishes into tools.cache
    data: dict = {}
    for (_, _, args), (key, f) in zip(jobs, futures):
        if not f.done() or f.exception() is not None:
            continue
        result = f.result()
        if key == "dich_vu":
            merged = data.setdefault(key, {**result, "rows": [], "found": 0, "by_kind": {}})
            merged["by_kind"][args["kind"]] = result
            merged["rows"] += result.get("rows") or []
            merged["found"] += result.get("found", 0)
        elif key == "tim_noi":  # copies: km below must not change the cached result
            data[key] = [dict(x) for x in result.get("places") or []] if "error" not in result else [result]
        elif key == "chi_tiet":
            data.setdefault(key, []).append(result.get("place") or result)
        elif key == "thoi_tiet":
            data.setdefault(key, []).append(result)
        else:
            data[key] = result
    if "tim_noi" in data and "distance" in route.groups and route.places and tools.knowledge is not None:
        origin = route.places[-1]  # "quán nào … cách chợ bao xa": the straight-line km from the place named last
        for x in data["tim_noi"]:
            if "id" in x:
                d = tools.knowledge.km_line(origin, x["id"])
                if d is not None:
                    x["km_line"] = d
                    tools._remember(d)  # the reply may say it
    return data
