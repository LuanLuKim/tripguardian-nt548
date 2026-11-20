"""Code checks on one written sentence of an introduction, before the Judge reads it (docs/CORPUS.md, Giới thiệu địa
điểm). A sentence that fails is dropped with its reason; nothing is rewritten."""

import re

from .evidence import fold

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
PRICE = re.compile(r"\d+(?:[.,]\d+)*\s*(?:k\b|đ\b|đồng|vnđ|vnd|nghìn|ngàn|triệu)", re.I)


def _digits(text: str) -> set[str]:
    return {re.sub(r"[.,]", "", n) for n in NUMBER.findall(text or "")}


def check(line: dict, items: dict[str, dict], cfg: dict, name: str = "") -> str | None:
    """The reason the sentence cannot be served, or None. line {text, evidence: [id]}; items by id; a number in the
    place's own name ("Gạch Since 1988") is not a fact the sentence states."""
    text = (line.get("text") or "").strip()
    cited = [items[i] for i in dict.fromkeys(line.get("evidence") or []) if i in items]
    if not text:
        return "empty"
    if not cited:
        return "no_evidence"
    if PRICE.search(text):
        return "price"  # the page shows prices from the cost block, with their own sources
    pool = " ".join(c["text"] for c in cited)
    own = _digits(name)
    if not _digits(text) - own <= _digits(pool):
        return "number_not_in_evidence"
    for year in set(YEAR.findall(text)) - own:
        holders = [c for c in cited if year in _digits(c["text"])]
        if not any(c["authority"] for c in holders) and len({c["domain"] for c in holders}) < 2:
            return "year_one_source"
    low, pool_low = fold(text), fold(pool)
    if any(h in low and h not in pool_low for h in cfg["hype"]):
        return "hype"
    if all(c["source"] in ("review", "detail") for c in cited):
        authors = sum(c["n"] for c in cited)
        if authors < cfg["min_review_authors"]:
            return "one_review"
    return None


def sources(line: dict, items: dict[str, dict]) -> list[dict]:
    """Where a served sentence comes from, as the page shows it: one row per site; reviews as one row with the count."""
    out, reviews = {}, 0
    for i in dict.fromkeys(line.get("evidence") or []):
        c = items.get(i)
        if c is None:
            continue
        if c["source"] in ("review", "detail"):
            reviews += c["n"]
            continue
        key = c["domain"] or c["source"]
        out.setdefault(key, {"source": c["source"], "domain": c["domain"], "url": c.get("url"), "title": c.get("title")})
    rows = list(out.values())
    if reviews:
        rows.append({"source": "review", "domain": "google.com/maps", "url": None, "n": reviews})
    return rows
