"""Grouping of gated Document claims into LocalClaims, and the status of sol's general claims (docs/CORPUS.md, Tri thức
bản địa). Code only, no model: dedup by subject + kind + words, independent sources = distinct domains, conflict when
the months or the price ranges of the same topic do not meet, confidence halves with age."""

import hashlib
import re
import unicodedata
from datetime import UTC, datetime

DEDUP = 0.6          # token Jaccard of two claim texts that say the same thing
SUBJECT = 0.6        # token Jaccard of two subject names that are the same subject ("hoa hướng dương" != "hoa oải hương")
MONTH_NEAR = 1       # months this close (circular) are the same period: "nở tháng 12" and "chớm nở tháng 1"
MONTH_GAP = 3        # months at least this far apart disagree; in between nothing is decided
TOPIC = 0.6          # overlap coefficient of two texts about the same thing (a price of what, a tip about what)
HALF_LIFE = {"notice": 30, "event": 30}
HALF_LIFE_DAYS = 365
OFFICIAL = (".gov.vn",)
MONTH_KINDS = {"season", "best_time", "event"}   # a non-city subject of these kinds is its own topic
SUBJECT_TOPIC = MONTH_KINDS | {"specialty"}
_STOP = {"va", "cua", "la", "co", "thi", "nhung", "cac", "mot", "o", "cho", "voi", "khi", "nen", "duoc", "rat",
         "thuong", "khoang", "tai", "tu", "den", "vao", "luc", "nay", "do", "the", "cung", "se", "hay", "hoac", "tp",
         "thanh", "pho", "vung", "khu", "vuc"}
_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+|\d+\s*(?:k|nghìn|ngàn))(?![\d\w])", re.I)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).split())


def tokens(text: str, city: str = "", stop: bool = True) -> frozenset[str]:
    """Folded words without the city's name (as a phrase: "Đà Lạt" must not take the "da" of "dã quỳ"); `stop` drops
    function words (off for names: folded "cỏ" is the stop word "có")."""
    f = fold(text)
    if city and fold(city):
        f = re.sub(rf"\b{re.escape(fold(city))}\b", " ", f)
    return frozenset(t for t in f.split() if len(t) > 1 and not (stop and t in _STOP))


def _jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _overlap(a: frozenset, b: frozenset) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def amounts(text: str) -> tuple[int, int] | None:
    """(min, max) VND of the amounts a text states ("100.000–200.000 đồng", "50k"), None when it states none."""
    found = []
    for m in _AMOUNT.finditer(text or ""):
        s = m.group(1).lower()
        found.append(int(re.sub(r"\D", "", s)) * (1000 if re.search(r"[^\d.,\s]", s) else 1))
    return (min(found), max(found)) if found else None


class _Subjects:
    """Subject keys: a resolved venue by id, the city as one subject, other names by their words without the city's."""

    def __init__(self, city_name: str):
        self.city = city_name

    def key(self, subject_kind: str, subject: str, subject_id: str | None = None):
        if subject_id:
            return ("id", subject_id)
        if subject_kind == "city":
            return ("city",)
        words = tokens(subject, self.city, stop=False)
        return ("words", words) if words else ("city",)

    @staticmethod
    def same(a, b) -> bool:
        if a[0] != "words" or b[0] != "words":
            return a == b
        small, big = sorted((a[1], b[1]), key=len)
        # one name inside the other counts only when the smaller has two words: "hồng" is not "đồi cỏ hồng"
        return small == big or (len(small) >= 2 and small <= big) or _jaccard(a[1], b[1]) >= SUBJECT


def _official(domain: str) -> bool:
    return domain.endswith(OFFICIAL)


def _when(text: str) -> datetime:
    try:
        d = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return datetime(1970, 1, 1, tzinfo=UTC)  # no date: as old as can be, never fresher than it is
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _gap(ma: set[int], mb: set[int]) -> int:
    """Smallest circular distance in months between two sets (0 when they share a month)."""
    return min(min((x - y) % 12, (y - x) % 12) for x in ma for y in mb)


def _disagree(a: dict, b: dict) -> str:
    """"disagree" when the months are MONTH_GAP or more apart or two price_norm ranges do not meet, "agree" when they
    meet, "unclear" when the months are in between, "none" when there is nothing to compare."""
    ma, mb = set(a["when"]["months"]), set(b["when"]["months"])
    if ma and mb:
        gap = _gap(ma, mb)
        return "agree" if gap <= MONTH_NEAR else "disagree" if gap >= MONTH_GAP else "unclear"
    ra, rb = a.get("range"), b.get("range")
    if a["kind"] == "price_norm" and ra and rb:
        return "disagree" if ra[1] < rb[0] or rb[1] < ra[0] else "agree"
    return "none"


def _topic(subjects: _Subjects, a: dict, b: dict, city: str) -> bool:
    """Same subject and kind, and about the same thing: a non-city subject of a season-like kind is its own topic,
    otherwise the texts must share most of their words."""
    if a["kind"] != b["kind"] or not subjects.same(a["_key"], b["_key"]):
        return False
    if a["kind"] in SUBJECT_TOPIC and a["_key"][0] != "city":
        return True
    return _overlap(tokens(a["text"], city), tokens(b["text"], city)) >= TOPIC


def _cid(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def group_claims(rows: list[dict], *, now: datetime, city_name: str) -> list[dict]:
    """Gated claims, each with its document's doc_id, source_url, domain and retrieved_at -> LocalClaims
    (origin "document") with status kept (>= 2 independent domains or one official), unverified (one source) or
    conflict (a claim on the same topic from other domains, with at least as many sources, gives months MONTH_GAP or
    more apart, or a price_norm range that does not meet)."""
    subjects, city = _Subjects(city_name), city_name
    clusters: list[dict] = []
    for r in sorted(rows, key=lambda r: (r["domain"], r["doc_id"], r["text"])):
        key, words = subjects.key(r["subject_kind"], r["subject"], r.get("subject_id")), tokens(r["text"], city)
        months = set(r["when"]["months"])
        for c in clusters:
            if c["kind"] != r["kind"] or not subjects.same(c["_key"], key):
                continue
            seasonal = (r["kind"] in MONTH_KINDS and key[0] != "city" and months and c["_months"]
                        and _gap(c["_months"], months) <= MONTH_NEAR)
            if _jaccard(c["_words"], words) >= DEDUP or seasonal:
                c["_rows"].append(r)
                c["_months"] |= months
                break
        else:
            clusters.append({"kind": r["kind"], "_key": key, "_words": words, "_months": set(months), "_rows": [r]})
    out = []
    for c in clusters:
        first, rs = c["_rows"][0], c["_rows"]
        domains = sorted({r["domain"] for r in rs})
        lows = [r["amount_min_vnd"] for r in rs if r.get("amount_min_vnd")]
        highs = [r["amount_max_vnd"] for r in rs if r.get("amount_max_vnd")]
        newest = max(_when(r["retrieved_at"]) for r in rs)
        age = max(0.0, (now - newest).total_seconds() / 86400)
        official = any(_official(d) for d in domains)
        claim = {"claim_id": _cid("document", c["_key"], c["kind"], first["text"]), "origin": "document",
                 "status": "kept" if len(domains) >= 2 or official else "unverified",
                 "subject_kind": first["subject_kind"], "subject": first["subject"],
                 "subject_id": first.get("subject_id"), "kind": c["kind"], "text": first["text"],
                 "when": {"months": sorted(c["_months"]),
                          "days": sorted({d for r in rs for d in r["when"]["days"]}),
                          "hours": next((r["when"]["hours"] for r in rs if r["when"]["hours"]), ""),
                          "weather": next((r["when"]["weather"] for r in rs if r["when"]["weather"]), "")},
                 "who": next((r["who"] for r in rs if r.get("who")), ""),
                 "amount_min_vnd": min(lows) if lows else None, "amount_max_vnd": max(highs) if highs else None,
                 "domains": domains, "sources": len(domains), "official": official,
                 "confidence": round(0.5 ** (age / HALF_LIFE.get(c["kind"], HALF_LIFE_DAYS)), 3),
                 "evidence": [{"doc_id": r["doc_id"], "source_url": r["source_url"], "domain": r["domain"],
                               "retrieved_at": r["retrieved_at"], "quote": r["quote"]} for r in rs],
                 "conflicts_with": [], "matched": [], "_key": c["_key"]}
        claim["range"] = (claim["amount_min_vnd"], claim["amount_max_vnd"]) if lows and highs else None
        out.append(claim)
    for a in out:
        for b in out:
            independent = not set(a["domains"]) & set(b["domains"])  # a page never contradicts itself
            if (a is not b and independent and _topic(subjects, a, b, city) and _disagree(a, b) == "disagree"
                    and b["sources"] >= a["sources"]):
                a["conflicts_with"].append(b["claim_id"])
    for a in out:
        if a["conflicts_with"]:
            a["status"] = "conflict"
    for a in out:
        del a["_key"], a["range"]
    return out


def check_model(general: list[dict], claims: list[dict], *, city_name: str) -> list[dict]:
    """sol's general claims (origin "model") -> confirmed when a kept Document claim on the same topic agrees,
    contradicted when kept claims only disagree (other months, a price range that does not meet), unverified when no
    kept claim is about it or the kept ones disagree with each other. Never evidence of its own."""
    subjects, city = _Subjects(city_name), city_name
    kept = []
    for c in claims:
        if c["status"] == "kept":
            lo, hi = c.get("amount_min_vnd"), c.get("amount_max_vnd")
            kept.append({**c, "_key": subjects.key(c["subject_kind"], c["subject"], c.get("subject_id")),
                         "range": (lo, hi) if lo and hi else None})
    out = []
    for g in general:
        g = dict(g)
        m = {**g, "_key": subjects.key(g["subject_kind"], g["subject"]), "range": amounts(g["text"])}
        agree, disagree = [], []
        for c in kept:
            if not _topic(subjects, m, c, city):
                continue
            verdict = _disagree(m, c)
            if verdict != "unclear":
                (disagree if verdict == "disagree" else agree).append(c["claim_id"])
        status = "confirmed" if agree and not disagree else "contradicted" if disagree and not agree else "unverified"
        out.append({"claim_id": g["claim_id"], "origin": "model", "status": status,
                    "subject_kind": g["subject_kind"], "subject": g["subject"], "subject_id": None, "kind": g["kind"],
                    "text": g["text"], "when": g["when"], "who": "", "amount_min_vnd": None, "amount_max_vnd": None,
                    "domains": [], "sources": 0, "official": False, "confidence": None, "evidence": [],
                    "conflicts_with": [], "matched": agree + disagree})
    return out
