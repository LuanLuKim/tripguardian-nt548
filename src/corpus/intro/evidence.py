"""The evidence one place's introduction may be written from (docs/CORPUS.md, Giới thiệu địa điểm). Pure code, no model.

Every item is {id, source, domain, url, text, authority, n}: `source` web (a crawled article), search (a Google result
snippet of the place's own panel query), official (the place's own site), maps (Google's one-line description),
review (a Maps review: one author) or detail (a served details cluster: `n` authors). `authority` marks a source
that may carry history, dates and names alone: an encyclopedia, a state page or the place's own site.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from ..aggregate.naming import display_name
from ..crawl.common.files import data_dir

HISTORY = re.compile(r"\b(năm|thế kỷ|xây dựng|khởi công|khánh thành|hoàn thành|thành lập|lịch sử|người Pháp|kiến trúc|"
                     r"vua|hoàng|trùng tu|di tích|thời|cổ nhất|ra đời|đặt tên|tên gọi|khai trương|mở cửa từ)\b", re.I)
AUTHORITY = ("wikipedia.org", ".gov.vn")
PREFIX = re.compile(r"^(khu du lịch|kdl|khu vui chơi|quán|tiệm|nhà hàng|khách sạn)\s+", re.I)


def fold(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def host(url: str) -> str:
    h = urlparse(url or "").netloc.casefold()
    return h[4:] if h.startswith("www.") else h


def authoritative(domain: str) -> bool:
    return any(domain.endswith(a) or a in domain for a in AUTHORITY)


def aliases(name: str, also: tuple[str, ...] = ()) -> list[str]:
    """Names a page may call the place by: the Maps name, its part before " - " / "(" / "|", the same without a
    generic prefix, and the names the local-knowledge step resolved to it (`also`). A name of one word or under 7
    characters is left out: it would match other things."""
    out = []
    for raw in (name, *also):
        core = re.split(r" - | \(| \||, ", raw or "")[0].strip()
        for n in (raw, core, PREFIX.sub("", core)):
            n = fold(n)
            if len(n) >= 7 and len(n.split()) >= 2 and n not in out:
                out.append(n)
    return out


def _paragraphs(doc: dict) -> list[tuple[str, str]]:
    out = []
    for s in doc.get("sections") or []:
        for para in re.split(r"\n\s*\n", s.get("text") or ""):
            para = re.sub(r"\*\*|__", "", para).strip()
            if len(para) >= 40:
                out.append((s.get("heading") or "", para))
    return out


class Library:
    """Everything the builder reads once for a city: web Documents, search results, local-knowledge names."""

    def __init__(self, city: str, root: Path | None = None):
        self.root = root or data_dir()
        self.city = city
        self.docs = []  # (doc, folded full text)
        for p in sorted((self.root / "web" / city / "documents").glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            paras = _paragraphs(d)
            d["_paras"] = paras
            self.docs.append((d, fold(d.get("title", "") + " " + " ".join(t for _, t in paras))))
        self.serps: dict[str, list[dict]] = {}
        path = self.root / "gsearch" / city / "results.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    self.serps.setdefault(fold(r["query"]), []).extend(r.get("results") or [])
        self.names: dict[str, set[str]] = {}
        path = self.root / city / "local" / "poi_claims.json"
        if path.exists():
            for c in json.loads(path.read_text(encoding="utf-8")).get("claims") or []:
                if c.get("subject_id"):
                    self.names.setdefault(c["subject_id"], set()).add(c["subject"])


def _cut(text: str, at: int, size: int) -> str:
    """`size` characters of text around position `at`, on word boundaries."""
    if len(text) <= size:
        return text
    start = max(0, min(at - size // 3, len(text) - size))
    out = text[start:start + size]
    if start:
        out = "…" + out.split(" ", 1)[-1]
    if start + size < len(text):
        out = out.rsplit(" ", 1)[0] + "…"
    return out


def web_items(lib: Library, names: list[str], cfg: dict) -> list[dict]:
    """Paragraphs of crawled articles that name the place, the ones about its history and look first, at most
    `per_domain` from one site and `web_items` in all."""
    found = []
    for d, blob in lib.docs:
        if not any(n in blob for n in names):
            continue
        domain = d.get("domain") or host(d.get("source_url"))
        for heading, para in d["_paras"]:
            low = fold(para)
            hit = next((low.find(n) for n in names if n in low), -1)
            head_hit = any(n in fold(heading) for n in names)
            if hit < 0 and not head_hit:
                continue
            score = len(HISTORY.findall(para)) * 2 + (2 if head_hit else 0) + min(len(para), 600) / 300
            text = _cut(para, max(hit, 0), cfg["passage_chars"])
            found.append((score, domain, {"source": "web", "domain": domain, "url": d.get("source_url"),
                                          "title": d.get("title"), "text": (re.sub(r"[*_#]+", "", heading).strip() + ": " if heading else "") + text,
                                          "authority": authoritative(domain), "n": 1}))
    found.sort(key=lambda x: (-x[0], x[1], x[2]["url"] or ""))
    out, per = [], {}
    for _, domain, item in found:
        if per.get(domain, 0) >= cfg["per_domain"] or any(item["text"] == o["text"] for o in out):
            continue
        per[domain] = per.get(domain, 0) + 1
        out.append(item)
        if len(out) >= cfg["web_items"]:
            break
    return out


def search_items(lib: Library, name: str, city_name: str, cfg: dict) -> list[dict]:
    """Snippets of the place's own Google query ("<name> <city>"), the result pages that are not social posts."""
    where = "" if city_name.casefold() in name.casefold() else f" {city_name}"
    out = []
    for r in lib.serps.get(fold(f"{name}{where}"), []):
        domain = host(r.get("url"))
        snippet = re.sub(r"^\d{1,2} thg \d{1,2}, \d{4} — ", "", r.get("snippet") or "").strip()
        if not snippet or "facebook.com" in domain or "tiktok.com" in domain or "instagram.com" in domain:
            continue
        if any(o["text"] == snippet for o in out):
            continue
        out.append({"source": "search", "domain": domain, "url": r.get("url"), "title": r.get("title"),
                    "text": snippet, "authority": authoritative(domain), "n": 1})
    return out[:cfg["search_items"]]


def official_items(root: Path, fid: str, cfg: dict) -> list[dict]:
    p = root / "official" / "pages" / f"{fid.replace(':', '_')}.json"
    if not p.exists():
        return []
    doc = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for page in (doc.get("pages") or [])[:2]:
        text = re.sub(r"\s+", " ", page.get("text") or "").strip()
        if len(text) >= 80:
            out.append({"source": "official", "domain": host(page.get("url")), "url": page.get("url"),
                        "title": page.get("title"), "text": text[:cfg["official_chars"]], "authority": True, "n": 1})
    return out


def maps_items(root: Path, fid: str, cfg: dict) -> tuple[list[dict], list[dict]]:
    """(Google's description, the most relevant Maps reviews)."""
    base = root / "gmaps" / "places" / fid.replace(":", "_")
    desc, reviews = [], []
    p = base / "place.json"
    if p.exists() and (d := (json.loads(p.read_text(encoding="utf-8")).get("description") or "").strip()):
        desc.append({"source": "maps", "domain": "google.com/maps", "url": None, "text": d, "authority": False, "n": 1})
    p = base / "reviews_relevant.json"
    if p.exists():
        rows = json.loads(p.read_text(encoding="utf-8")).get("reviews") or []
    else:  # no relevance order was crawled: the longest reviews say the most about the place
        p = base / "reviews.json"
        rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        rows = sorted(rows, key=lambda r: (-min(len(r.get("text") or ""), 600), r.get("review_id") or ""))
    authors = set()
    for r in rows:
        text = re.sub(r"\s+", " ", r.get("text") or "").strip()
        who = r.get("author_hash") or r.get("review_id")
        if len(text) >= cfg["review_min_chars"] and who not in authors:
            authors.add(who)
            reviews.append({"source": "review", "domain": "google.com/maps", "url": None,
                            "text": _cut(text, 0, cfg["review_chars"]), "authority": False, "n": 1})
        if len(reviews) >= cfg["review_items"]:
            break
    return desc, reviews


def detail_items(record: dict) -> list[dict]:
    """The served details clusters (what several visitors said), with how many said it."""
    d = record.get("details") or {}
    rows = []
    kf = d.get("known_for") or {}
    for c in ([kf["headline"]] if kf.get("headline") else []) + list(kf.get("more") or []):
        rows.append(("nổi tiếng vì", c))
    for kind, label in (("order", "hay gọi"), ("activity", "hay làm"), ("photo_spot", "góc chụp"), ("avoid", "nên tránh"),
                        ("bring", "nên mang")):
        rows += [(label, c) for c in d.get(kind) or []]
    for c in ((d.get("timing") or {}).get("best_time") or {}).get("items") or []:
        rows.append(("giờ đẹp", c))
    out = []
    for label, c in rows:
        if isinstance(c, dict) and c.get("text") and c.get("n", 0) >= 1:
            out.append({"source": "detail", "domain": "review", "url": None, "text": f"{label}: {c['text']}",
                        "authority": False, "n": int(c["n"])})
    return out[:12]


def pack(lib: Library, record: dict, city_name: str, cfg: dict) -> list[dict]:
    """Every evidence item for one serving record, numbered e1, e2, ... in a fixed order."""
    fid, ident = record["id"], record["identity"]
    names = aliases(ident["name"], (display_name(ident["name"]), *sorted(lib.names.get(fid, ()))))
    desc, reviews = maps_items(lib.root, fid, cfg)
    items = (official_items(lib.root, fid, cfg) + search_items(lib, ident["name"], city_name, cfg)
             + web_items(lib, names, cfg) + desc + detail_items(record) + reviews)
    for i, it in enumerate(items, 1):
        it["id"] = f"e{i}"
    return items

