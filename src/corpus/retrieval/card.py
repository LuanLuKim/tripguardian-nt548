"""card: a compact, evidence-only view of one serving record for LLM agents.

Every value is copied from the record; a key with no value is left out. Features that are not VERIFIED / OUTDATED /
UNCERTAIN (NEEDS_REVIEW, DISABLED) are never in the record, and the card does not go looking for them.
"""

from __future__ import annotations

from ..serving import feature

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GROUPS = ("experience", "environment", "service", "effort", "suitability")
LISTS = ("order", "avoid", "activity", "photo_spot", "access", "booking", "bring", "situation")
PER_LIST = 3
MAX_DISHES = 8
FEE_CONFLICT = "conflicts_entry_fee_estimate"
FIRM = ("VERIFIED", "OUTDATED")


def _text(x) -> str | None:
    return x if isinstance(x, str) else (x or {}).get("text")


def _texts(items, statuses: tuple[str, ...] | None = None, limit: int | None = None) -> list[str]:
    """Texts of the items, at most `limit`; with `statuses`, only items with one of those statuses (an item without a
    status, such as a plain string, counts as VERIFIED)."""
    status = lambda x: x.get("status", "VERIFIED") if isinstance(x, dict) else "VERIFIED"
    return [t for x in (items or []) if (statuses is None or status(x) in statuses) and (t := _text(x))][:limit]


def _hours(value: dict) -> dict[str, str]:
    """{"06:30-21:30": "mon,tue"}: days that share the same opening ranges, in week order."""
    out: dict[str, list[str]] = {}
    for day in DAYS:
        ranges = (value or {}).get(day)
        if ranges:
            out.setdefault(",".join(f"{a}-{b}" for a, b in ranges), []).append(day)
    return {k: ",".join(v) for k, v in out.items()}


def _features(record: dict, statuses: tuple[str, ...]) -> list[str]:
    out = []
    for group in GROUPS:
        for fid in (record.get(group) or {}):
            try:
                f = feature(record, fid)
            except KeyError:
                continue
            if f and f.get("status") in statuses and f.get("value") is not None:
                out.append(f"{fid}={f['value']}")
    return out


def card(record: dict) -> dict:
    """The compact card of one serving record (keys: see docs/CORPUS.md retrieval); empty values are omitted."""
    ident, op = record.get("identity") or {}, record.get("operation") or {}
    det = record.get("details") or {}
    timing, prov = det.get("timing") or {}, record.get("provenance") or {}
    out: dict = {"id": record.get("id"), "n": ident.get("name"), "cat": ident.get("category"),
                 "g": ident.get("category_group"), "addr": ident.get("address")}
    hours = op.get("hours") or {}
    out["h"] = _hours(hours.get("value"))
    if hours.get("status") not in (None, "VERIFIED"):
        out["h_status"] = hours["status"]
    if fee := op.get("entry_fee"):
        out["fee"] = {k: fee.get(src) for k, src in (("min", "min_vnd"), ("typ", "typical_vnd"), ("max", "max_vnd"),
                                                      ("src", "source"), ("kind", "kind"))}
        if (feature(record, "entry_fee") or {}).get("reason") == FEE_CONFLICT:
            out["fee"]["conflict"] = True
    price = (op.get("price_per_person") or {}).get("value") or {}
    if price.get("max_vnd") is not None:
        out["price"] = [price.get("min_vnd"), price["max_vnd"]]  # min None = Maps' "up to X": no lower bound known
    out["night"] = (op.get("price_per_night") or {}).get("value")
    visit = op.get("visit_minutes") or {}
    if all(visit.get(k) is not None for k in ("short", "typical", "long")):
        out["visit"] = [visit["short"], visit["typical"], visit["long"]]
        out["visit_src"] = visit.get("source")
    out["f"] = _features(record, ("VERIFIED", "OUTDATED"))
    out["f?"] = _features(record, ("UNCERTAIN",))
    known = det.get("known_for") or {}
    out["known"] = _texts([known.get("headline"), *(known.get("more") or [])])
    for kind in LISTS:  # an UNCERTAIN item goes under "<kind>?", like the f / f? split of features
        out[kind] = _texts(det.get(kind), FIRM, PER_LIST)
        out[f"{kind}?"] = _texts(det.get(kind), ("UNCERTAIN",), PER_LIST)
    for key, kind in (("best", "best_time"), ("avoid_t", "avoid_time")):
        items = (timing.get(kind) or {}).get("items")
        out[key], out[f"{key}?"] = _texts(items, FIRM), _texts(items, ("UNCERTAIN",))
    out["months"] = timing.get("best_months")
    out["months_avoid"] = timing.get("avoid_months")
    out["dishes"] = [d["name"] for d in (record.get("menu") or {}).get("dishes", [])[:MAX_DISHES] if d.get("name")]
    out["peak"] = (op.get("crowd_by_time") or {}).get("peak")
    out["trend"] = (prov.get("rating_trend") or {}).get("direction")
    out["voices"] = prov.get("voices")
    if record.get("status") not in (None, "VERIFIED"):
        out["status"] = record["status"]
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}
