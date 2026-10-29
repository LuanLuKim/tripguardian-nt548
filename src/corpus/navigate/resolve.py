"""Resolve nominees (spec A.1, "sol đề cử, Maps quyết định"): which nominees still need a Maps lookup, and what a Maps
result list says about one of them. No browser here; `corpus.crawl.gmaps.resolve` does the lookup and calls these.

`pending` = nominees `navigate compare` could not place in the corpus (resolve_queue.jsonl) plus the `maybe` ones of
the latest compare report, minus names already in `resolved.jsonl`. `decide` takes one nominee and the places Maps
listed for it and returns a verdict. A place is `resolved` only when exactly one clear place matches the name, lies in
the city area and clears the review bar; anything else is a recorded proposal. There is no verdict that a place does
not exist: `unresolved` only says Maps showed nothing that matches.
"""

import json
import math
from datetime import UTC, datetime
from typing import Callable

from ..retrieval import name_score
from .common import config, navigate_dir
from .compare import _covered
from .schema import fold

STATUSES = ("resolved", "pending_count", "already_held", "ambiguous", "unresolved", "rejected")

def search_limit() -> int:
    """Maps results read per nominee (config/navigate.yaml resolve.limit)."""
    return config()["resolve"]["limit"]


HELPER_KEYS = ("inside", "lodging")  # added by the caller to each Maps row, not part of the search-file row


def _lines(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pending(city: str) -> list[dict]:
    """Nominees to look up on Maps, in order: the queue, then `maybe` nominees of the newest compare report."""
    nav = navigate_dir(city)
    rows = [{"name": r["name"], "area_hint": r.get("area_hint", ""), "aspect": r.get("aspect", "")}
            for r in _lines(nav / "resolve_queue.jsonl")]
    reports = sorted(nav.glob("compare_*.json")) if nav.exists() else []
    if reports:
        for a in json.loads(reports[-1].read_text(encoding="utf-8")).get("aspects", []):
            rows += [{"name": n["name"], "area_hint": n.get("area_hint", ""), "aspect": a["key"]}
                     for n in a.get("nominees", []) if n.get("status") == "maybe"]
    done = {fold(r["name"]) for r in _lines(nav / "resolved.jsonl")}
    out = []
    for r in rows:
        if fold(r["name"]) not in done:
            done.add(fold(r["name"]))
            out.append(r)
    return out


def record(city: str, row: dict) -> None:
    """Append one verdict to data/<city>/navigate/resolved.jsonl (the ledger `pending` reads)."""
    path = navigate_dir(city) / "resolved.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = {**row, "city": city, "at": datetime.now(UTC).isoformat(timespec="seconds")}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(stamped, ensure_ascii=False) + "\n")


def _meters(a: dict, b: dict) -> float:
    if None in (a.get("lat"), a.get("lng"), b.get("lat"), b.get("lng")):
        return math.inf
    dx = math.radians(b["lng"] - a["lng"]) * math.cos(math.radians(a["lat"]))
    return 6371000 * math.hypot(dx, math.radians(b["lat"] - a["lat"]))


def _clusters(matches: list[dict], radius_m: float) -> list[list[dict]]:
    """Rows that are one place listed under several fids (same plain name, within radius_m); each cluster starts with
    the row that has the most reviews."""
    clusters: list[list[dict]] = []
    for r in sorted(matches, key=lambda r: -(r["reviews"] or 0)):
        same = next((c for c in clusters if fold(c[0]["name"]) == fold(r["name"])
                     and any(_meters(r, x) <= radius_m for x in c)), None)
        if same:
            same.append(r)
        else:
            clusters.append([r])
    return clusters


def decide(nominee: dict, rows: list[dict], *, min_reviews: int, min_reviews_stay: int, same_name_m: float,
           held_fids: set[str], city_words: set[str] = frozenset(),
           score_of: Callable[[str, str], float] = name_score) -> dict:
    """The verdict for one nominee. rows: Maps results (search-file rows) each with `inside` (in the city area) and
    `lodging` (lodging category) added. Returns {status, reason, fid?, matched_name?, candidates, item?}; `item` is the
    search-file row to write, present only for `resolved` and `pending_count`."""
    cfg = config()
    held, cover, margin = cfg["nominee"]["held"], cfg["nominee"]["covered"], cfg["resolve"]["margin"]
    name = nominee["name"]
    scored = sorted(({"row": r, "score": round(score_of(name, r["name"]), 2)} for r in rows), key=lambda s: -s["score"])
    candidates = [{"fid": s["row"]["fid"], "name": s["row"]["name"], "score": s["score"]} for s in scored[:3]]
    out = lambda status, reason, **kw: {"status": status, "reason": reason, "candidates": candidates, **kw}  # noqa: E731
    matches = [s for s in scored if s["score"] >= held and _covered(name, s["row"]["name"], set(city_words)) >= cover]
    if not matches:
        return out("unresolved", "no_name_match")
    inside = [s for s in matches if s["row"]["inside"]]
    if not inside:
        return out("rejected", "outside_area", fid=matches[0]["row"]["fid"], matched_name=matches[0]["row"]["name"])
    groups = _clusters([s["row"] for s in inside], same_name_m)
    best = {s["row"]["fid"]: s["score"] for s in inside}
    groups.sort(key=lambda g: -best[g[0]["fid"]])
    if len(groups) > 1 and round(best[groups[0][0]["fid"]] - best[groups[1][0]["fid"]], 2) < margin:
        return out("ambiguous", "several_places", candidates=[
            {"fid": g[0]["fid"], "name": g[0]["name"], "score": best[g[0]["fid"]]} for g in groups[:3]])
    chosen = groups[0][0]
    ref = {"fid": chosen["fid"], "matched_name": chosen["name"]}
    if chosen["fid"] in held_fids:
        return out("already_held", "in_list", **ref)
    item = {k: v for k, v in chosen.items() if k not in HELPER_KEYS}
    if chosen.get("rating") is None:
        return out("rejected", "no_rating", **ref)
    if chosen.get("reviews") is None:
        return out("pending_count", "review_count_hidden", item=item, **ref)
    if chosen["reviews"] < (min_reviews_stay if chosen["lodging"] else min_reviews):
        return out("rejected", "few_reviews", **ref)
    return out("resolved", "one_clear_place", item=item, **ref)
