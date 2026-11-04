"""Grouping of gated Document claims into LocalClaims, and the status of sol's general claims (docs/CORPUS.md, Tri thức
bản địa). Code only, no model: dedup by subject + kind + words, two claims merge only when their months, amounts and
distances agree, independent sources = distinct domains (a sentence copied on two sites is one source), conflict when
the months, price ranges or distances of the same topic do not meet, confidence halves with age."""

import hashlib
import math
import re
import unicodedata
from collections import defaultdict
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
_QTY = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)(?:\s*(?:-|~|den|toi)\s*(\d+(?:[.,]\d+)?))?\s*(km|m|phut|gio)\b")
QTY_SLACK = 0.25     # two distances / durations meet when their ranges, widened by this share, overlap
_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+|\d+\s*(?:k|nghìn|ngàn))(?![\d\w])", re.I)


_COMBINING = re.compile(r"[\u0300-\u036f]")
_NOT_WORD = re.compile(r"[^a-z0-9]+")


def fold(text: str) -> str:
    text = _COMBINING.sub("", unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d")))
    return " ".join(_NOT_WORD.sub(" ", text).split())


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


def _plain(text: str) -> str:
    """Lower case without diacritics, punctuation kept (the digits of "3,8km" stay one number)."""
    text = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    return "".join(c for c in text if not unicodedata.combining(c)).replace("–", "-").replace("—", "-")


def quantities(text: str) -> dict[str, tuple[float, float]]:
    """{unit: (low, high)} of the distances and durations a text states ("cách trung tâm 5–6 km" -> km: 5-6)."""
    out: dict[str, tuple[float, float]] = {}
    for m in _QTY.finditer(_plain(text)):
        lo = float(m.group(1).replace(",", "."))
        hi = float((m.group(2) or m.group(1)).replace(",", "."))
        lo, hi = min(lo, hi), max(lo, hi)
        old = out.get(m.group(3))
        out[m.group(3)] = (min(lo, old[0]), max(hi, old[1])) if old else (lo, hi)
    return out


def _qty_apart(a: dict, b: dict) -> bool:
    """True when the two share a unit and no shared unit's ranges meet (5-6 km vs 10 km)."""
    shared = set(a) & set(b)
    return bool(shared) and all(a[u][1] * (1 + QTY_SLACK) < b[u][0] or b[u][1] * (1 + QTY_SLACK) < a[u][0]
                                for u in shared)


def months_agree(a: set[int], b: set[int]) -> bool:
    """Both name no month, or both name months that are the same period: they touch (within MONTH_NEAR) and together
    cover at most one month more than the smaller one ("nở tháng 12" and "chớm nở tháng 1" agree; "tháng 6-10" and
    "tháng 1-10", "tháng 6-9" and "tháng 5-10", or "tháng 6-10" and "tháng 11-4", do not)."""
    if not a and not b:
        return True
    if not a or not b:
        return False
    return _gap(a, b) <= MONTH_NEAR and len(a | b) <= min(len(a), len(b)) + 1


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


def _ranges_meet(ra, rb) -> bool:
    return not (ra[1] < rb[0] or rb[1] < ra[0])


def _disagree(a: dict, b: dict) -> str:
    """"disagree" when the months are MONTH_GAP or more apart, two price_norm ranges do not meet or two distances do not
    meet, "agree" when they meet, "unclear" when the months are in between, "none" when there is nothing to compare."""
    ma, mb = set(a["when"]["months"]), set(b["when"]["months"])
    if ma and mb:
        gap = _gap(ma, mb)
        return "agree" if gap <= MONTH_NEAR else "disagree" if gap >= MONTH_GAP else "unclear"
    ra, rb = a.get("range"), b.get("range")
    if a["kind"] == "price_norm" and ra and rb:
        return "agree" if _ranges_meet(ra, rb) else "disagree"
    qa, qb = a.get("qty"), b.get("qty")
    if qa and qb and set(qa) & set(qb):
        return "disagree" if _qty_apart(qa, qb) else "agree"
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
    """Stable id: a subject key holds a frozenset of words, whose str() order changes with every Python process
    (hash randomisation), so words are sorted first."""
    flat = [("words", tuple(sorted(p[1]))) if isinstance(p, tuple) and len(p) == 2 and isinstance(p[1], frozenset)
            else p for p in parts]
    return hashlib.sha1("|".join(map(str, flat)).encode()).hexdigest()[:12]


def _anchor_range(r: dict):
    lo, hi = r.get("amount_min_vnd"), r.get("amount_max_vnd")
    return (lo, hi) if lo and hi else None


def _joins(subjects: _Subjects, c: dict, r: dict, key, words, months, qty) -> bool:
    """A row joins a cluster only when it says the same thing as the cluster's first row (its anchor): the same subject,
    the same period, a price range and distances that meet, and either almost the same words or, for a season-like kind
    of a named subject, a period that is the same."""
    if not subjects.same(c["_key"], key) or not months_agree(c["_months0"], months):
        return False
    ra, rb = c["_range"], _anchor_range(r)
    if ra and rb and not _ranges_meet(ra, rb):
        return False
    if c["_qty"] and qty and _qty_apart(c["_qty"], qty):
        return False
    seasonal = r["kind"] in MONTH_KINDS and key[0] != "city" and months
    return seasonal or _jaccard(c["_words"], words) >= DEDUP


def _cluster(rows: list[dict], subjects: "_Subjects", city: str) -> list[dict]:
    """Rows that say the same thing -> clusters (anchored on their first row)."""
    clusters: dict[str, list[dict]] = defaultdict(list)
    by_text: dict[tuple, list[dict]] = defaultdict(list)    # (kind, rare word of the first row's text) -> clusters
    by_subject: dict[tuple, list[dict]] = defaultdict(list)  # (kind, subject key) -> clusters, for period-only joins
    prepared = []
    freq: dict[str, int] = defaultdict(int)
    for r in sorted(rows, key=lambda r: (r["domain"], r["doc_id"], r["text"])):
        words = tokens(r["text"], city)
        prepared.append((r, subjects.key(r["subject_kind"], r["subject"], r.get("subject_id")), words))
        for w in words:
            freq[w] += 1

    def prefix(words) -> list[str]:
        """The rarest words of a text that two texts with Jaccard >= DEDUP must share one of (prefix filtering)."""
        ordered = sorted(words, key=lambda w: (freq[w], w))
        return ordered[: len(ordered) - math.ceil(DEDUP * len(ordered)) + 1]

    n = 0
    for r, key, words in prepared:
        months, qty = set(r["when"]["months"]), quantities(r["text"])
        seasonal = r["kind"] in MONTH_KINDS and key[0] != "city" and months
        cands: dict[int, dict] = {}
        for w in prefix(words):
            for c in by_text.get((r["kind"], w), ()):
                cands[c["_n"]] = c
        if seasonal:
            for k in _index_keys(key):
                for c in by_subject.get((r["kind"], k), ()):
                    cands[c["_n"]] = c
        for _, c in sorted(cands.items()):
            if _joins(subjects, c, r, key, words, months, qty):
                c["_rows"].append(r)
                c["_months"] |= months
                break
        else:
            c = {"kind": r["kind"], "_key": key, "_words": words, "_months": set(months), "_months0": set(months),
                 "_range": _anchor_range(r), "_qty": qty, "_rows": [r], "_n": n}
            n += 1
            clusters[r["kind"]].append(c)
            for w in prefix(words):
                by_text[(r["kind"], w)].append(c)
            for k in _index_keys(key):
                by_subject[(r["kind"], k)].append(c)
    return [c for kind_clusters in clusters.values() for c in kind_clusters]


def candidate_rows(rows: list[dict], *, city_name: str) -> list[dict]:
    """The rows of every cluster that would be kept (>= 2 domains or one official): what `local verify` has to check."""
    out = []
    for c in _cluster(rows, _Subjects(city_name), city_name):
        if _stands([r["domain"] for r in c["_rows"]], c["kind"], subject_kind=c["_rows"][0]["subject_kind"]):
            out.extend(c["_rows"])
    return out


def _stands(domains, kind: str, copies=(), subject_kind: str = "") -> bool:
    """>= 2 independent domains keep a claim; one official (.gov.vn) page keeps it for the kinds an official page is the
    authority on and about a known place or the city (config/local.yaml official_alone_*), not for a specialty, a tip
    or an unresolved name."""
    from .gate import rules
    return len(set(domains)) >= 2 or (any(_official(d) for d in (*domains, *copies)) and kind in rules()["official_alone"]
                                    and subject_kind in rules()["official_alone_subjects"])


def group_claims(rows: list[dict], *, now: datetime, city_name: str, verdicts: dict[str, str] | None = None,
                 vkey=None, claim_verdicts: dict[str, str] | None = None, ckey=None) -> list[dict]:
    """Gated claims, each with its document's doc_id, source_url, domain and retrieved_at -> LocalClaims
    (origin "document") with status kept (>= 2 independent domains or one official), unverified (one source) or
    conflict (a claim on the same topic from other domains, with at least as many sources, gives months MONTH_GAP or
    more apart, a price_norm range that does not meet or a distance that does not meet). Rows merge only when their
    months, amounts and distances agree with the cluster's first row, so a claim's text, months and amount are one
    source's statement; the same sentence on two sites is one source (`mirrors` lists the copies).
    `verdicts` ({vkey(row): problem}, see corpus.local.verify) is the Extractor's second look at each row against its
    quote in context: a row with a problem is dropped before grouping, and a claim is `kept` only on rows that were
    checked and passed (a row nobody checked is no evidence for kept: fail closed). `claim_verdicts` ({ckey(claim):
    problem}) is the same for the grouped claim against all its quotes: a claim that would be kept stays `kept` only
    with the verdict "none" (a claim whose quotes were never compared is `unverified`)."""
    subjects, city = _Subjects(city_name), city_name
    if verdicts is not None:
        rows = [r for r in rows if verdicts.get(vkey(r), "none") == "none"]
    out = []
    for c in _cluster(rows, subjects, city):
        claim = _claim(c, now, verdicts, vkey)
        if claim:
            out.append(claim)
    _mark_conflicts(out, subjects, city)
    for a in out:
        del a["_key"], a["range"], a["qty"]
        if claim_verdicts is not None and a["status"] == "kept" and claim_verdicts.get(ckey(a)) != "none":
            a["status"] = "unverified"
    return out


def _claim(c: dict, now: datetime, verdicts: dict[str, str] | None = None, vkey=None) -> dict:
    """One cluster -> one LocalClaim: evidence without a page's repeats, a sentence copied on another site counted once.
    With `verdicts`, a cluster of >= 2 domains is `kept` only on its checked-and-passed rows."""
    rows = c["_rows"]
    verified = False
    if verdicts is not None:
        ok = [r for r in rows if verdicts.get(vkey(r)) == "none"]
        if _stands([r["domain"] for r in ok], c["kind"], subject_kind=c["_rows"][0]["subject_kind"]):
            rows, verified = ok, True
    first = rows[0]
    months = set().union(*(set(r["when"]["months"]) for r in rows)) if verified else c["_months"]
    cid = _cid("document", c["_key"], c["kind"], first["text"])
    evidence, pairs, by_fp, mirrors = [], set(), {}, set()
    for r in rows:
        fp = fold(r["quote"])
        if (r["doc_id"], fp) in pairs:   # a page repeating itself
            continue
        pairs.add((r["doc_id"], fp))
        if fp in by_fp:                  # the same sentence on another site: a copy, not a second source
            if by_fp[fp] != r["domain"]:
                mirrors.add(r["domain"])
            continue
        by_fp[fp] = r["domain"]
        evidence.append({"doc_id": r["doc_id"], "source_url": r["source_url"], "domain": r["domain"],
                         "retrieved_at": r["retrieved_at"], "quote": r["quote"]})
    domains = sorted({e["domain"] for e in evidence})
    mirrors = sorted(mirrors - set(domains))
    rs = [r for r in rows if r["domain"] in domains]
    newest = max(_when(r["retrieved_at"]) for r in rs)
    age = max(0.0, (now - newest).total_seconds() / 86400)
    official = any(_official(d) for d in domains + mirrors)
    rng = _anchor_range(first)
    claim = {"claim_id": cid, "origin": "document",
             "status": ("kept" if _stands(domains, c["kind"], mirrors, first["subject_kind"]) else "unverified")
             if verdicts is None or verified else "unverified",
             "subject_kind": first["subject_kind"], "subject": first["subject"],
             "subject_id": first.get("subject_id"), "kind": c["kind"], "text": first["text"],
             "when": {"months": sorted(months),
                      "days": sorted({d for r in rs for d in r["when"]["days"]}),
                      "hours": next((r["when"]["hours"] for r in rs if r["when"]["hours"]), ""),
                      "weather": next((r["when"]["weather"] for r in rs if r["when"]["weather"]), "")},
             "who": next((r["who"] for r in rs if r.get("who")), ""),
             "amount_min_vnd": first.get("amount_min_vnd") or None, "amount_max_vnd": first.get("amount_max_vnd") or None,
             "domains": domains, "mirrors": mirrors, "sources": len(domains), "official": official,
             "confidence": round(0.5 ** (age / HALF_LIFE.get(c["kind"], HALF_LIFE_DAYS)), 3),
             "evidence": evidence, "conflicts_with": [], "matched": [], "_key": c["_key"]}
    claim["range"] = rng
    claim["qty"] = c["_qty"]
    return claim


def _index_keys(k) -> list:
    """Where a subject key is listed so that two claims about the same subject share an entry (a name by each word)."""
    return [("w", w) for w in k[1]] if k[0] == "words" else [k]


def _mark_conflicts(out: list[dict], subjects: _Subjects, city: str) -> None:
    """A claim is `conflict` when another claim on the same topic from other domains, with at least as many sources,
    disagrees. Only claims that state months, a price range or a distance can disagree; they are found through their
    subject's words so the pairs compared stay few."""
    comparable = [a for a in out if a["when"]["months"] or a["range"] or a["qty"]]
    index: dict[tuple, list[dict]] = defaultdict(list)
    for a in comparable:
        for k in _index_keys(a["_key"]):
            index[(a["kind"], k)].append(a)
    for a in comparable:
        cands = {id(b): b for k in _index_keys(a["_key"]) for b in index.get((a["kind"], k), ())}
        for b in cands.values():
            independent = not (set(a["domains"]) | set(a["mirrors"])) & (set(b["domains"]) | set(b["mirrors"]))
            if (a is not b and independent and _topic(subjects, a, b, city) and _disagree(a, b) == "disagree"
                    and b["sources"] >= a["sources"] and b["claim_id"] not in a["conflicts_with"]):
                a["conflicts_with"].append(b["claim_id"])
    for a in out:
        if a["conflicts_with"]:
            a["status"] = "conflict"


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
                         "range": (lo, hi) if lo and hi else None, "qty": quantities(c["text"])})
    out = []
    for g in general:
        g = dict(g)
        m = {**g, "_key": subjects.key(g["subject_kind"], g["subject"]), "range": amounts(g["text"]),
             "qty": quantities(g["text"])}
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
