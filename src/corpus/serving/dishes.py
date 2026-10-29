"""Dish lookup: "which places serve bánh bèo / sữa đậu nành / bánh canh" (data/gmaps/places/*/menu.json -> record["menu"]).

A dish name is matched as a whole phrase after folding case, accents and `đ` ("Bánh Bèo" == "banh beo"), so
"bánh canh" finds "Bánh canh giò heo" but "canh" alone finds "Canh chua", never "Bánh canh" by substring of a word.
The owner's own dish list (the Maps menu tab) is evidence from the place itself; so is a name that says the dish
("Bánh bèo Bà Hường", eatery groups only, `config/dishes.yaml` `name_groups`); the dishes review authors say to
order (`details.order`, served only when its measured precision passes the gate) are a weaker source. A dish nobody
wrote down is `unknown`, not absent.

`attach(records)` adds `menu` to each serving record that has dishes; `search(records, query)` ranks places through
`index(records)` (built once per list, token -> places); `report(records, queries)` is the hit-rate evidence.
"""

import json
import re
import unicodedata
from functools import cache

import yaml

from ..crawl.common.files import ROOT, data_dir, safe_name

ALIASES = ROOT / "config" / "dishes.yaml"
SOURCE_RANK = {"menu_popular": 5, "name": 4, "menu": 3, "menu_photo": 2, "review_order": 1}
MIN_PRICES = 3  # agreed menu-photo prices a place needs before they say anything about its price per person


def fold(text: str | None) -> str:
    """Lowercase, no accents, `đ` -> d, words joined by single spaces: the key two spellings of a dish share."""
    s = unicodedata.normalize("NFD", (text or "").casefold().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", s))


def keep(text: str | None) -> str:
    """Case-folded words with the accents kept: "phở" != "phô" (fold would join them)."""
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFC", (text or "").casefold())))


def key_for(text: str | None, accented: bool) -> str:
    return keep(text) if accented else fold(text)


@cache
def config() -> dict:
    return (yaml.safe_load(ALIASES.read_text(encoding="utf-8")) or {}) if ALIASES.exists() else {}


def enabled(source: str) -> bool:
    """config/dishes.yaml `sources.<source>.enabled`: a source serves only after its measured precision passed the gate."""
    return bool(((config().get("sources") or {}).get(source) or {}).get("enabled"))


def groups() -> list[list[str]]:
    """config/dishes.yaml `same`: lists of phrases that are one dish."""
    return config().get("same") or []


def phrases(query: str) -> tuple[frozenset[str], bool]:
    """(wanted keys, accented). A query typed with accents ("phở") is compared with accents kept, one without
    ("pho", "banh beo") compared folded: folding alone would make "phở" find "phô mai"."""
    k = fold(query)
    if not k:
        return frozenset(), False
    accented = keep(query) != k
    same = {query}
    for g in groups():
        if k in {fold(x) for x in g}:
            same.update(g)
    return frozenset(key_for(x, accented) for x in same), accented


def has_phrase(haystack: str, needle: str) -> bool:
    """needle as whole words inside haystack (both already keyed the same way)."""
    return f" {needle} " in f" {haystack} "


def menu_of(doc: dict) -> dict | None:
    """The served `menu` block of one menu.json, or None when the place has no dish list and no menu photo."""
    if not doc.get("has_menu_tab"):
        return None
    dishes, seen = [], set()

    def add(item: dict, section: str | None, popular: bool) -> None:
        key = fold(item.get("name"))
        if key and key not in seen:
            seen.add(key)
            dishes.append({k: v for k, v in {"name": item["name"], "name_en": item.get("name_en"), "section": section,
                                              "popular": popular, "price": item.get("price")}.items() if v})

    for it in doc.get("highlights") or []:
        add(it, None, bool(it.get("popular")))
    for sec in doc.get("sections") or []:
        for it in sec.get("items") or []:
            add(it, sec["name"], bool(it.get("popular")))
    photos = [p["file"] for p in doc.get("photos") or []]
    if not dishes and not photos:
        return None
    return {"dishes": dishes, "photos": photos, "fetched_at": doc.get("fetched_at")}


def _json(f):
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except (OSError, ValueError):
        return None


def photo_dishes(menu: dict | None, doc: dict | None) -> dict | None:
    """Add the dishes two reads of the menu photos agreed on (menu_photo.json) that the owner's list lacks, as
    source `menu_photo`; the agreed prices become `price_evidence` (a spread of the place's prices, not a quote)."""
    if not doc or not doc.get("dishes"):
        return menu
    menu = menu or {"dishes": [], "photos": [], "fetched_at": None}
    seen = {fold(d["name"]) for d in menu["dishes"]}
    prices = []
    for it in doc["dishes"]:
        price = int(it.get("price_vnd") or 0)
        if price:
            prices.append(price)
        key = fold(it.get("name"))
        if key and key not in seen:
            seen.add(key)
            menu["dishes"].append({"name": it["name"], "popular": False, "via": "menu_photo", **({"price": price} if price else {})})
    if len(prices) >= MIN_PRICES:
        prices.sort()
        menu["price_evidence"] = {"min_vnd": prices[len(prices) // 4], "max_vnd": prices[(3 * len(prices) - 1) // 4],
                                  "n": len(prices), "source": "menu_photo"}
    return menu


def usable_review_dish(item: dict) -> bool:
    """A Judge-approved review dish that is a dish: not a generic word ("đồ uống", "bữa sáng") nor a wish ("muốn ăn ...")."""
    key = fold(item.get("dish"))
    return (item.get("judge") == "serves" and bool(item.get("quote")) and key not in {fold(g) for g in config().get("generic") or ()}
            and not any(key.startswith(fold(w) + " ") for w in config().get("wish_prefix") or ()))


def attach(records: list[dict], root=None) -> int:
    """Set record["menu"] from each place's menu.json (+ menu_photo.json when that source is enabled) and
    record["review_dishes"] from dish_review.json (when review_order is enabled); returns records with a menu."""
    base = (root or data_dir()) / "gmaps" / "places"
    n = 0
    for rec in records:
        d = base / safe_name(rec["id"])
        doc = _json(d / "menu.json")
        menu = menu_of(doc) if doc else None
        if menu:
            menu["photos"] = [f"gmaps/places/{safe_name(rec['id'])}/{p}" for p in menu["photos"]]
        if enabled("menu_photo"):
            menu = photo_dishes(menu, _json(d / "menu_photo.json"))
        rec["menu"] = menu
        rec["review_dishes"] = ([x for x in (_json(d / "dish_review.json") or {}).get("dishes") or []
                                 if usable_review_dish(x)] if enabled("review_order") else [])
        n += bool(menu)
    return n


def statements(record: dict):
    """Every dish statement one place makes, as (texts a query can match, source, dish, section, n)."""
    for d in (record.get("menu") or {}).get("dishes") or []:
        yield ((d["name"], d["name_en"]) if d.get("name_en") else (d["name"],),
               "menu_photo" if d.get("via") == "menu_photo" else "menu_popular" if d.get("popular") else "menu",
               d["name"], d.get("section"), None)
    ident = record.get("identity") or {}
    if ident.get("name") and ident.get("category_group") in (config().get("name_groups") or ()):
        yield (ident["name"],), "name", ident["name"], None, None
    for o in record.get("review_dishes") or []:  # exact quote + Judge check done offline (observe.gmaps.dish_check)
        if o.get("dish"):
            yield (o["dish"],), "review_order", o["dish"], None, (o.get("n"), o.get("quote"))


def evidence_of(source: str, dish: str, section: str | None, n) -> dict:
    """n is (authors, exact quote) for review_order, else None."""
    n, quote = n if isinstance(n, tuple) else (n, None)
    return {"source": source, "dish": dish, **({"section": section} if section else {}),
            **({"n": n} if source == "review_order" and n else {}), **({"quote": quote} if quote else {})}


def rows_of(record: dict) -> list[tuple[dict, tuple[str, ...]]]:
    """(evidence {source, dish, section?, n?}, texts a query can match) for every statement of one place."""
    return [(evidence_of(src, dish, sec, n), texts) for texts, src, dish, sec, n in statements(record)]


def matches(record: dict, wanted: frozenset[str], accented: bool = False) -> list[dict]:
    """Every way this place serves one of the wanted phrases: {source, dish, section?}."""
    return [evidence_of(src, dish, sec, n) for texts, src, dish, sec, n in statements(record)
            if any(has_phrase(key_for(t, accented), w) for t in texts for w in wanted)]


SMALL = 8  # lists this short are searched directly


def _hit(record: dict, evidence: list[dict]) -> dict:
    score = max(SOURCE_RANK[e["source"]] for e in evidence) * 100 + min(len(evidence), 9) * 10 + min(
        sum(e.get("n") or 0 for e in evidence), 9)
    return {"id": record["id"], "name": record["identity"]["name"], "score": score, "evidence": evidence}


class Index:
    """Dish statements of a list of serving records, keyed once (folded and accent-kept) with a token -> places map,
    so a query looks at the few places holding all its words instead of re-folding every dish of every place."""

    def __init__(self, records: list[dict]):
        self.records = records
        self.keyed: list[list[tuple[dict, dict[bool, tuple[str, ...]]]]] = []
        self.post: dict[bool, dict[str, set[int]]] = {False: {}, True: {}}
        for i, rec in enumerate(records):
            row = []
            for ev, texts in rows_of(rec):
                keys = {a: tuple(key_for(t, a) for t in texts) for a in (False, True)}
                row.append((ev, keys))
                for a in (False, True):
                    for k in keys[a]:
                        for tok in k.split():
                            self.post[a].setdefault(tok, set()).add(i)
            self.keyed.append(row)

    def candidates(self, wanted: frozenset[str], accented: bool) -> list[int]:
        out: set[int] = set()
        for w in wanted:
            sets = [self.post[accented].get(tok, set()) for tok in w.split()]
            if sets and all(sets):
                out |= set.intersection(*sets)
        return sorted(out)

    def search(self, query: str, limit: int = 20) -> list[dict]:
        wanted, accented = phrases(query)
        if not wanted:
            return []
        hits = []
        for i in self.candidates(wanted, accented):
            ev = [e for e, keys in self.keyed[i] if any(has_phrase(k, w) for k in keys[accented] for w in wanted)]
            if ev:
                hits.append(_hit(self.records[i], ev))
        return sorted(hits, key=lambda h: -h["score"])[:limit]


_INDEXES: dict[int, tuple[list[dict], tuple, Index]] = {}  # id(list) -> (the list, fingerprint, its index)


def index(records: list[dict]) -> Index:
    """The Index of this list, built once; rebuilt when a record's menu / name / order block was replaced."""
    stamp = tuple((id(r), id(r.get("menu")), id(r.get("review_dishes")),
                   (r.get("identity") or {}).get("name")) for r in records)
    cached = _INDEXES.get(id(records))
    if cached is None or cached[0] is not records or cached[1] != stamp:
        if len(_INDEXES) >= 8:
            _INDEXES.pop(next(iter(_INDEXES)))
        cached = _INDEXES[id(records)] = (records, stamp, Index(records))
    return cached[2]


def search(records: list[dict], query: str, limit: int = 20) -> list[dict]:
    """Places that serve the dish, best first: owner-listed popular > place named for it > owner-listed > review
    authors' orders. [{id, name, score, evidence:[{source, dish, ...}]}]; [] when nothing was written down (that is
    not "none")."""
    if len(records) > SMALL:
        return index(records).search(query, limit)
    wanted, accented = phrases(query)  # one or two records (a card): building an index costs more than looking
    hits = [_hit(r, ev) for r in records if wanted and (ev := matches(r, wanted, accented))]
    return sorted(hits, key=lambda h: -h["score"])[:limit]


def report(records: list[dict], queries: list[str]) -> list[dict]:
    """Hit-rate evidence per dish: {query, places, sources: {source: places}, eateries_unknown}. `eateries_unknown` =
    eatery places with no dish statement at all (no menu list): for those the dish is unknown, never "not served"."""
    names = config().get("name_groups") or ()
    unknown = sum(1 for r in records if (r.get("identity") or {}).get("category_group") in names
                  and not (r.get("menu") or {}).get("dishes"))
    out = []
    for q in queries:
        hits = search(records, q, limit=len(records) or 1)
        sources = {}
        for h in hits:
            for src in {e["source"] for e in h["evidence"]}:
                sources[src] = sources.get(src, 0) + 1
        out.append({"query": q, "places": len(hits), "sources": sources, "eateries_unknown": unknown})
    return out
