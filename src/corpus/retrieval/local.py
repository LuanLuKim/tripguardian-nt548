"""local_knowledge: the city's LocalClaims of a snapshot Region (docs/CORPUS.md, Tri thức bản địa), filtered for an
agent. No I/O, no model. A `contradicted` claim of sol is never returned (the evidence that contradicts it is); only
`kept` and `confirmed` are facts, everything else carries `label` so the chat says it as such."""

import json
from typing import Iterable

from .names import _name

LABELS = {"kept": "fact", "confirmed": "fact", "unverified": "reference", "conflict": "disputed"}


def local_knowledge(claims: Iterable[dict], subject: str | None = None, kind: str | None = None,
                    month: int | None = None, *, facts_only: bool = False) -> list[dict]:
    """Rows of Region.local_claims matching subject (its words in the claim's subject, accents folded), kind and
    month (a claim with no months holds all year); facts first, then by independent sources and confidence. Each row
    gets `label` (fact | reference | disputed) and `evidence` (doc_id, source_url, domain, retrieved_at, quote)."""
    want = set(_name(subject).split()) if subject else set()
    out = []
    for c in claims:
        status = c["status"]
        if status not in LABELS or (facts_only and not c["fact"]):
            continue
        if kind and c["kind"] != kind:
            continue
        if month is not None and c["months"] and month not in c["months"]:
            continue
        if want and not want <= set(_name(c["subject"]).split()):
            continue
        row = {k: v for k, v in c.items() if k != "evidence_json"}
        row["evidence"] = json.loads(c.get("evidence_json") or "[]")
        row["label"] = LABELS[status]
        out.append(row)
    return sorted(out, key=lambda r: (not r["fact"], -(r["sources"] or 0), -(r["confidence"] or 0.0), r["claim_id"]))
