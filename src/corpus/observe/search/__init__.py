"""search observe: Google search records of a place (corpus.crawl.gsearch places) -> data/gsearch/observations/<fid_dir>.json.

Three sources, each with its own basis, read in order of trust:
  google_panel   the place's knowledge panel (title must be this place): its weekly hours, the ticket line marked
                 "Trang web chính thức" (the operator's own price, standard adult ticket), a box that lists only "Miễn phí".
  official_site  a result snippet from the place's own domain (the Maps `website`), read by the Extractor
                 (corpus.llm.SEARCH_OBSERVE); a fact like an official page's.
  web            a snippet from anyone else's page (blog, news), read the same way; an ESTIMATE, never a fact.
Every Extractor fact passes the official gate (quote in the snippet, amount / times in the quote) and must have the
place's own name words within NEAR chars of the quote. Prices count only for places of a category group that sells
entry. Output carries `place_facts` {hours, tickets_vnd, entry_free} each with an `*_evidence` object {basis, url,
quote, at, dated, domains} and `evidence` (every kept fact), `tried` (what each query kind gave, so a place with
nothing is recorded as tried). aggregate reads place_facts of source `gsearch` after Maps and the official site.
"""

import asyncio
import collections
import hashlib
import json
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, UTC
from urllib.parse import urlparse

import openai

from ...categories import group
from ...crawl import gsearch, web
from ...crawl.common.files import append_jsonl, data_dir, load_config, now, safe_name, write_json
from ...crawl.gsearch import panel as gpanel
from ...llm import OutOfQuota, SEARCH_OBSERVE
from ...ontology import load as load_ontology
from ..details_gate import DAYS, day_in
from ..official import TICKET_GROUPS, fold, gate, hours_of, name_words, norm

GATE_VERSION = "search_gate@v8+panel@2"  # in the input hash: a changed gate reads the places again
BEFORE = 320  # chars before (and inside) a quote that must hold the place's name: a list names a place, then gives its facts
MAX_BLOCK = 7000  # chars of snippets sent to the Extractor for one place
PARALLEL = 12  # this track's share of the UIT lane (docs: common.md of the corpus-fill wave)
MAX_SNIPPET_AGE_DAYS = 730  # a snippet dated older than this says nothing about now
KINDS = gsearch.places.KINDS
_VI_MONTH = re.compile(r"^(\d{1,2}) thg (\d{1,2}), (\d{4}) — ")
_DISTINCT = 1  # distinctive name words a result must carry (all of them when the name has fewer)


def host(url: str) -> str:
    return urlparse(url if "//" in url else "http://" + url).netloc.lower().removeprefix("www.")


SOCIAL = ("facebook.com", "fb.com", "instagram.com", "tiktok.com", "youtube.com", "zalo.me", "linktr.ee")


def site_key(url: str) -> str:
    """Whose page a URL is: its host, and for a social network the page / account (first path segment) too, so a place's
    own Facebook page is told from every other page of Facebook."""
    parts = urlparse(url if "//" in url else "http://" + url)
    h = parts.netloc.lower().removeprefix("www.").removeprefix("m.").removeprefix("web.")
    if h in SOCIAL or h.endswith("." + "facebook.com"):
        seg = [x for x in parts.path.split("/") if x]
        if seg and seg[0].lower() in ("profile.php",):
            return f"{h}/{parts.query}"
        if seg and seg[0].lower() not in ("groups", "watch", "reel", "reels", "p", "share", "people", "photo", "story.php"):
            return f"{h}/{seg[0].lower()}"
        if seg and seg[0].lower() == "@" or h.startswith("tiktok") and seg and seg[0].startswith("@"):
            return f"{h}/{seg[0].lower()}"
    return h


def panel_matches(title: str, name: str) -> bool:
    """The panel is about this place: its title and the Maps name share their distinctive words (one holds the other,
    or at least half of the smaller set is in the larger)."""
    a, b = name_words(title), name_words(name)
    if not a or not b:
        return False
    small, big = sorted((a, b), key=len)
    return small <= big or len(small & big) / len(small) >= 0.5 and len(small & big) >= 2


def snippet_date(snippet: str) -> str | None:
    m = _VI_MONTH.match(snippet or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def relevant(result: dict, words: set[str]) -> bool:
    """A result is about the place when its title or snippet holds a distinctive word of its name (all of them when the
    name has at most two)."""
    text = fold(f"{result['title']} {result['snippet']}")
    hit = {w for w in words if re.search(rf"\b{w}\b", text)}
    return bool(words) and len(hit) >= (len(words) if len(words) <= 2 else max(2, -(-3 * len(words) // 5)))


def near(block: str, quote: str, name: str) -> bool:
    """The place's distinctive name (its words in the order of the name, one other word allowed between two) stands in
    the quote or within BEFORE chars before it. A name only AFTER the quote does not count: in a list the facts follow
    their place, so an amount ahead of a name is the previous place's."""
    keep = name_words(name)
    order = [w for w in re.findall(r"[a-z0-9]+", fold(name)) if w in keep]
    text = fold1(clean(block))
    at = text.find(fold1(clean(quote)))
    if not order or at < 0:
        return False
    window = text[max(0, at - BEFORE):at + len(quote)]
    if re.search(r"\b" + r"\W+(?:\w+\W+)?".join(map(re.escape, order)) + r"\b", window):
        return True
    rare = max(order, key=len)  # a long, distinctive word ("datanla") names the place by itself
    return len(rare) >= 6 and bool(re.search(rf"\b{rare}\b", window))


PARTIAL = re.compile(r"\b(?:khung|buổi|ca|giờ|giấc)\s+(?:sáng|chiều|tối|trưa|đêm)\b|cao điểm|happy hour|biểu diễn|\bshow\b|\btour\b|bắt đầu từ|check-?in", re.I)  # a part of the day, not the opening hours
FROM = re.compile(r"\btừ\s+\d", re.I)  # "từ 75.000": the lowest ticket, not the adult price
COMBO = re.compile(r"combo|trọn gói|gói |kèm|bao gồm|nếu (?:bạn )?chọn|buffet|\btour\b|\+", re.I)
CLOSED = re.compile(r"đóng cửa (?:vĩnh viễn|hẳn)|rào chắn|cấm (?:tham quan|vào)|ngừng hoạt động|dừng hoạt động|tạm (?:ngưng|đóng|dừng)|không còn hoạt động", re.I)
CLOSED_WINDOW = 250  # chars either side of the quote that may say the place is shut
PLAIN = {"vui", "choi", "san", "quang", "truong", "ho", "nui", "doi", "thac", "cho", "chua", "dinh", "bao", "tang", "tho", "hoa",
         "cam", "trai", "nong", "trang", "vong", "cau", "duong", "pho", "dao", "suoi", "rung", "thung", "lung", "bien", "cay"}  # ordinary words: a name made of them only ("Khu Vui Chơi") is any such place
RANGE = re.compile(r"\d[\d.,]*\s*(?:k|đ|đồng|vnđ|vnd|nghìn)?\s*(?:-|–|—|đến|tới)\s*\d[\d.,]*", re.I)
_MD = re.compile(r"[*_`#>|\\]+")


def clean(text: str) -> str:
    """Page text without Markdown marks (a model quotes "Giá vé: 100.000" for "**Giá vé:** 100.000"): runs of spaces and
    marks become one space; lines stay."""
    return "\n".join(" ".join(_MD.sub(" ", line).split()) for line in unicodedata.normalize("NFC", text).splitlines()).strip()


def fold1(text: str) -> str:
    """fold() that keeps every position: one output character per input character (accents dropped, đ -> d)."""
    out = []
    for ch in unicodedata.normalize("NFC", text):
        base = unicodedata.normalize("NFD", ch)[:1].lower()
        out.append("d" if base == "đ" else base)
    return "".join(out)


WINDOW = 350  # chars either side of a place's name in a web document


class Documents:
    """The city's web Documents (data/web/<city>/documents, phase `web documents`) as one text each, folded for search."""

    def __init__(self, city: str):
        self.docs = []
        for f in sorted((data_dir() / "web" / city / "documents").glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                text = "\n".join(f"{s['heading']}\n{s['text']}" if s.get("heading") else s["text"] for s in d["sections"])
                text = clean(text)
                self.docs.append({"url": d["source_url"], "host": site_key(d["source_url"]), "at": d["retrieved_at"][:10],
                                  "text": text, "fold": fold1(text), "title": d.get("title") or ""})
            except (OSError, ValueError, KeyError, TypeError):
                continue

    def windows(self, name: str, limit: int = 12) -> list[dict]:
        """Blocks of text around the place's name: where its distinctive words stand in the order of the name (one other
        word allowed between two) and a price / hours cue stands in the window. At most two windows a document, `limit`
        blocks in all."""
        keep = name_words(name)
        order = [w for w in re.findall(r"[a-z0-9]+", fold(name)) if w in keep]
        if not order:
            return []
        pattern = re.compile(r"\b" + r"\W+(?:\w+\W+)?".join(map(re.escape, order)) + r"\b")
        out = []
        for d in self.docs:
            if len(out) >= limit:
                break
            got, last = 0, -10 ** 9
            for m in pattern.finditer(d["fold"]):
                if m.start() < last + WINDOW or got >= 2:
                    continue
                win = d["text"][max(0, m.start() - WINDOW):min(len(d["text"]), m.end() + WINDOW)]
                if WANT_RE.search(win):
                    out.append({"url": d["url"], "host": d["host"], "at": d["at"], "dated": None, "text": win.strip(), "doc": True})
                    got, last = got + 1, m.start()
        return out


def _records(city: str, name: str, city_name: str, snippets: dict[str, dict] | None = None) -> dict[str, dict | None]:
    """Per query kind the Google record, else (fee / hours) the SearXNG one (corpus.crawl.web places): Bing / Yahoo / Yandex
    snippets, kept apart in data/web and read here as the same "web" basis."""
    done = gsearch.load(city, max_age_days=10 ** 5)
    snippets = web.places.load(city) if snippets is None else snippets
    out = {}
    for k in KINDS:
        q = gsearch.places.query_for(k, name, city_name)
        out[k] = done.get((gsearch.key(q), 1)) or snippets.get(gsearch.key(q))
    return out


def _panel(city: str, rec: dict | None) -> gpanel.Panel:
    if not rec or not rec.get("raw"):
        return gpanel.Panel(present=False)
    path = data_dir() / "gsearch" / city / rec["raw"]
    return gpanel.parse(path.read_text(encoding="utf-8")) if path.exists() else gpanel.Panel(present=False)


def _negate(at: str) -> list[int]:
    """Sort key that puts the newest timestamp first."""
    return [-ord(c) for c in at]


def blocks_of(recs: dict[str, dict | None], words: set[str]) -> list[dict]:
    """[{url, text, at, dated, host}] of the relevant results over all query kinds, a URL once, newest record first."""
    out, seen = [], set()
    # Google's records first (their snippets passed the earlier gate), then the SearXNG ones, each newest first
    for rec in sorted((r for r in recs.values() if r), key=lambda r: (r.get("source") == "searxng", _negate(r["at"]))):
        for r in rec["results"]:
            if r["url"] in seen or not relevant(r, words):
                continue
            seen.add(r["url"])
            out.append({"url": r["url"], "host": host(r["url"]), "at": rec["at"][:10], "dated": snippet_date(r["snippet"]),
                        "text": clean(f"{r['title']}\n{r['snippet']}"), "via": rec.get("source") or "google"})
    return out


def batches(blocks: list[dict], size: int = MAX_BLOCK, most: int = 3) -> list[tuple[str, list[dict]]]:
    """(text, its blocks) groups of at most `size` chars, the first `most` of them: one Extractor call each."""
    out, cur, used = [], [], 0
    for b in blocks:
        piece = f"[{b['url']}]\n{b['text']}"
        if cur and used + len(piece) > size:
            out.append(("\n\n".join(f"[{x['url']}]\n{x['text']}" for x in cur), cur))
            cur, used = [], 0
        cur.append(b)
        used += len(piece) + 2
    if cur:
        out.append(("\n\n".join(f"[{x['url']}]\n{x['text']}" for x in cur), cur))
    return out[:most]


def _block_of(blocks: list[dict], quote: str) -> dict | None:
    return next((b for b in blocks if norm(quote) in norm(b["text"])), None)


def _closed_near(text: str, quote: str) -> bool:
    at = text.find(quote)
    return at >= 0 and bool(CLOSED.search(text[max(0, at - CLOSED_WINDOW):at + len(quote) + CLOSED_WINDOW]))


def _old(block: dict, today: date) -> bool:
    return bool(block["dated"]) and date.fromisoformat(block["dated"]) < today - timedelta(days=MAX_SNIPPET_AGE_DAYS)


def read_facts(answer: dict, blocks: list[dict], text: str, name: str, tickets: bool, official_host: str | None,
               today: date) -> tuple[list[dict], collections.Counter]:
    """Kept facts [{fact, block, basis}] and why the others went."""
    kept, why = [], collections.Counter()
    for f in answer["facts"]:
        if f["kind"] == "hours" and not f["days"] and not any(day_in(f["quote"], d) for d in DAYS):
            f = {**f, "days": list(DAYS)}  # no day named in the quote: every day (the prompt asks the same)
        block = _block_of(blocks, f["quote"])
        if block is None:
            why["quote_not_in_snippet"] += 1
            continue
        reason = gate(f, block["text"], None, tickets)
        if not reason and f["kind"] == "hours" and block.get("via") == "searxng":
            reason = "searxng_hours"  # hours from Bing / Yahoo / Yandex snippets failed the label gate (2 rounds, 2026-10-30); tickets and free passed
        if not reason and name_words(name) <= PLAIN:
            reason = "generic_name"  # a page about "a play area" is not about this one
        if not reason and not near(block["text"], f["quote"], name):
            reason = "name_not_before_quote"
        if not reason and _closed_near(block["text"], f["quote"]):
            reason = "closed_nearby"  # a place fenced off or shut for good keeps no price or hours
        if not reason and f["kind"] == "ticket" and (COMBO.search(f["quote"]) or RANGE.search(f["quote"])
                                                     or FROM.search(f["quote"])):
            reason = "combo_or_range"  # a package is not the entry ticket; a range gives no one price
        if not reason and f["kind"] == "hours" and PARTIAL.search(f["quote"]):
            reason = "partial_hours"
        if not reason and _old(block, today):
            reason = "snippet_too_old"
        if not reason and f["kind"] == "free" and re.search(r"trẻ|dưới|người già|cao tuổi|sinh viên|học sinh|người dân|địa phương", f["quote"], re.I):
            reason = "free_for_some"
        if reason:
            why[reason] += 1
            continue
        basis = "official_site" if official_host and site_key(block["url"]) == official_host else "web"
        if basis == "web" and block.get("via") == "searxng":
            basis = "web_searxng"  # its own basis: aggregate ignores it until config/gsearch.yaml enables it (label gate failed 2026-10-30)
        kept.append({"fact": f, "block": block, "basis": basis})
    return kept, why


def _evidence(k: dict) -> dict:
    f, b = k["fact"], k["block"]
    at = norm(b["text"]).find(norm(f["quote"]))
    return {"kind": f["kind"], "basis": k["basis"], "url": b["url"], "host": b["host"], "quote": f["quote"].strip(),
            "context": norm(b["text"])[max(0, at - 220):at + len(norm(f["quote"])) + 220] if at >= 0 else "",
            "used": bool(k.get("used")), "at": b["at"], "dated": b["dated"], **{x: f[x] for x in ("amount_vnd", "audience", "open", "close", "days", "item", "unit")
                                                   if f.get(x) not in (None, "", [], 0, "none")}}


def pick_hours(pan: gpanel.Panel, matched: bool, kept: list[dict], rec_at: str) -> tuple[dict | None, dict | None, str | None]:
    """(hours, evidence, conflict): the panel's when it is this place's, else the own site's, else what the pages agree
    on; pages that differ give no hours and say so."""
    if matched and pan.hours:
        return pan.hours, {"basis": "google_panel", "url": None, "quote": pan.hours_text[:300], "at": rec_at,
                           "dated": None, "domains": 1}, None
    for basis in ("official_site", "web", "web_searxng"):
        by_host = collections.defaultdict(list)
        for k in kept:
            if k["fact"]["kind"] == "hours" and k["basis"] == basis:
                by_host[k["block"]["host"]].append(k)
        per = {}
        for h, ks in by_host.items():
            hrs = hours_of([k["fact"] for k in ks])
            if hrs:
                per[h] = (hrs, ks)
        if not per:
            continue
        distinct = {json.dumps(v[0], sort_keys=True) for v in per.values()}
        if len(distinct) > 1:
            return None, None, "pages_differ"
        hrs, ks = next(iter(per.values()))
        for x in (y for v in per.values() for y in v[1]):
            x["used"] = True
        k = ks[0]
        return hrs, {"basis": basis, "url": k["block"]["url"], "quote": " | ".join(x["fact"]["quote"].strip() for x in ks)[:400],
                     "at": k["block"]["at"], "dated": k["block"]["dated"], "domains": len(per)}, None
    return None, None, None


AGREE = 0.2  # two pages agree on a price when they are within 20 % of each other


def agreeing(per: dict[str, int]) -> list[str]:
    """Hosts whose amounts agree: the biggest group of hosts whose amounts lie within AGREE of the group's lowest."""
    best: list[str] = []
    for h, v in per.items():
        group_ = [x for x, w in per.items() if v <= w <= v * (1 + AGREE)]
        if len(group_) > len(best):
            best = group_
    return best


def pick_tickets(pan: gpanel.Panel, matched: bool, kept: list[dict], rec_at: str) -> tuple[dict | None, dict | None]:
    """tickets_vnd {adult, child, senior} and its evidence. Own price line of the panel, else the own site's snippets,
    else the pages: at least two page domains must agree on the adult price (a blog that lists many places
    mixes them up), one adult amount per domain; the aggregate takes the median."""
    if matched:
        own = [a for a in pan.admissions if a.official and a.price_vnd]
        if own:
            return ({"adult": sorted({a.price_vnd for a in own})},
                    {"basis": "google_panel", "url": None, "quote": pan.admissions_text[:300], "at": rec_at, "dated": None, "domains": 1})
    for basis in ("official_site", "web", "web_searxng"):
        ks = [k for k in kept if k["fact"]["kind"] == "ticket" and k["basis"] == basis]
        adult = {}
        for k in ks:
            if k["fact"]["audience"] == "adult":
                adult[k["block"]["host"]] = max(adult.get(k["block"]["host"], 0), k["fact"]["amount_vnd"])
        if not adult:
            continue
        hosts = agreeing(adult) if basis.startswith("web") else list(adult)
        if basis.startswith("web") and len(hosts) < 2:
            continue
        used = [k for k in ks if k["block"]["host"] in hosts and (k["fact"]["audience"] != "adult" or k["fact"]["amount_vnd"] == adult[k["block"]["host"]])]
        out = {"adult": sorted(adult[h] for h in hosts)}
        for aud in ("child", "senior"):
            per = {}
            for k in used:
                if k["fact"]["audience"] == aud:
                    per[k["block"]["host"]] = max(per.get(k["block"]["host"], 0), k["fact"]["amount_vnd"])
            if per:
                out[aud] = sorted(per.values())
        for k in used:
            k["used"] = True
        k0 = next(k for k in used if k["fact"]["audience"] == "adult")
        return out, {"basis": basis, "url": k0["block"]["url"], "quote": " | ".join(x["fact"]["quote"].strip() for x in used)[:400],
                     "at": k0["block"]["at"], "dated": k0["block"]["dated"], "domains": len(hosts)}
    return None, None


def pick_free(pan: gpanel.Panel, matched: bool, kept: list[dict], rec_at: str) -> dict | None:
    if matched and pan.admissions and all(a.free for a in pan.admissions):
        return {"basis": "google_panel", "url": None, "quote": pan.admissions_text[:300], "at": rec_at, "dated": None, "domains": 1}
    for basis in ("official_site", "web", "web_searxng"):
        ks = [k for k in kept if k["fact"]["kind"] == "free" and k["basis"] == basis]
        if ks:
            hosts = {k["block"]["host"] for k in ks}
            k = ks[0]
            for x in ks:
                x["used"] = True
            return {"basis": basis, "url": k["block"]["url"], "quote": k["fact"]["quote"].strip(), "at": k["block"]["at"],
                    "dated": k["block"]["dated"], "domains": len(hosts)}
    return None


def build(place: dict, recs: dict, pan: gpanel.Panel, matched: bool, kept: list[dict], why: collections.Counter,
          blocks: list[dict], ticket_group: bool) -> dict:
    rec_at = max((r["at"] for r in recs.values() if r), default=now())[:10]
    hours, hours_ev, conflict = pick_hours(pan, matched, kept, (recs.get("panel") or {}).get("at", rec_at)[:10])
    tickets, tickets_ev = pick_tickets(pan, matched, kept, (recs.get("panel") or {}).get("at", rec_at)[:10]) if ticket_group else (None, None)
    free = pick_free(pan, matched, kept, (recs.get("panel") or {}).get("at", rec_at)[:10]) if ticket_group else None
    if tickets and free:  # a paid price and a free claim in one place's evidence: neither is served
        free = None
        for k in kept:
            if k["fact"]["kind"] == "free":
                k["used"] = False
    facts = {"hours": hours, "hours_evidence": hours_ev, "tickets_vnd": tickets, "tickets_evidence": tickets_ev,
             "entry_free": free}
    return {"place_fid": place["fid"], "place_name": place["name"], "as_of": rec_at, "source": "gsearch",
            "observations": [], "details": [], "ratings": [], "proposed": [], "place": {}, "voices": 0,
            "place_facts": {k: v for k, v in facts.items() if v is not None},
            "evidence": [_evidence(k) for k in kept],
            "tried": {"panel": ("matched" if matched else "other_place" if pan.present else "none"),
                      "panel_title": pan.title or None, "queries": {k: (len(r["results"]) if r else None) for k, r in recs.items()},
                      "relevant_results": len(blocks), "dropped": dict(why), "hours_conflict": conflict}}


async def run(city: str, limit: int | None = None) -> dict:
    name_of_city, _ = load_config(city)
    root = data_dir() / "gsearch" / "observations"
    ont = load_ontology()
    todo, today, docs = [], datetime.now(UTC).date(), Documents(city)
    fingerprint = [len(docs.docs), max((d["at"] for d in docs.docs), default="")]
    snippets = web.places.load(city)
    for p in gsearch.places.places(city):
        recs = _records(city, p["name"], name_of_city, snippets)
        in_docs = p["group"] in TICKET_GROUPS or not p["hours"]
        if not any(recs.values()) and not (in_docs and docs.windows(p["name"], 1)):
            continue
        pan = _panel(city, recs["panel"])
        h = hashlib.sha256(json.dumps([{k: r and r["at"] for k, r in recs.items()}, SEARCH_OBSERVE.prompt_hash, GATE_VERSION,
                                       ont.version, p["website"], fingerprint]).encode()).hexdigest()[:16]
        target = root / f"{safe_name(p['fid'])}.json"
        if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("input_hash") == h:
            continue
        todo.append((p, recs, pan, h, target))
    todo = todo[:limit]
    print(f"search observe {city}: {len(todo)} places to read", flush=True)
    if not todo:
        return {"read": 0}
    client, model = SEARCH_OBSERVE.role.client()
    client = client.with_options(timeout=240, max_retries=0)
    sem = asyncio.Semaphore(min(PARALLEL, int(os.environ.get("UIT_EXTRACTOR_PARALLEL") or PARALLEL)))
    status, dropped = collections.Counter(), collections.Counter()

    async def ask(place, text, category, address):
        for tries in range(30):
            try:
                async with sem:
                    return await SEARCH_OBSERVE.ask(client, model, city=name_of_city, name=place["name"],
                                                    category=category, address=address, note="",
                                                    url="Google search results", text=text)
            except (OutOfQuota, openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError):
                if tries == 29:
                    raise
                await asyncio.sleep(20)

    async def one(place, recs, pan, h, target):
        pf = data_dir() / "gmaps" / "places" / safe_name(place["fid"]) / "place.json"
        raw = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
        words = name_words(place["name"])
        matched = pan.present and panel_matches(pan.title, place["name"])
        blocks = blocks_of(recs, words) + (docs.windows(place["name"]) if place["group"] in TICKET_GROUPS or not place["hours"] else [])
        ticket_group = group(raw.get("category"), place["name"])["id"] in TICKET_GROUPS
        kept, why = [], collections.Counter()
        try:
            for text, part in batches(blocks):
                if not WANT_RE.search(text):
                    continue
                answer = await ask(place, text, raw.get("category") or "unknown", raw.get("address") or "unknown")
                official_host = site_key(place["website"]) if place.get("website") else None
                official_host = None if official_host in SOCIAL else official_host  # a bare network address is nobody's page
                got, lost = read_facts(answer, part, text, place["name"], ticket_group, official_host, today)
                kept += got
                why.update(lost)
        except Exception as e:
            append_jsonl(data_dir() / "gsearch" / "observe_errors.jsonl",
                         {"at": now(), "place": safe_name(place["fid"]), "error": f"{type(e).__name__}: {str(e)[:300]}"})
            status["failed"] += 1
            return
        dropped.update(why)
        write_json(target, {**build(place, recs, pan, matched, kept, why, blocks, ticket_group), "input_hash": h,
                            "prompt_hash": SEARCH_OBSERVE.prompt_hash, "model": model, "built_at": now()})
        status["done"] += 1

    await asyncio.gather(*(one(*t) for t in todo))
    summary = {"at": now(), "status": dict(status), "dropped": dict(dropped)}
    print(f"search observe {city}: {json.dumps(summary, ensure_ascii=False)}", flush=True)
    return summary


WANT_RE = re.compile(r"\d\s*(?:k|đ|đồng|vnđ|vnd|nghìn|ngàn|000)\b|\d{1,2}\s*(?:h|giờ|:)\s*\d{0,2}|vé|giá|miễn phí|free|"
                     r"mở cửa|giờ hoạt động|opening|ticket", re.I)
