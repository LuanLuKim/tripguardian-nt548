"""Offline check of Place Decision on the serving records (docs/PLACE_DECISION.md §17).

python -m decision evaluate  ->  data/decision/eval.json

Each hidden trip of config/eval_trips.yaml becomes a Search Input (hard -> "!=", soft -> love the feature's first,
good value) and the real pipeline runs. Measured on the shortlist of the trip's role:
- violations: shortlist places whose evidence has ANY author naming a forbidden value, read from the raw
  distribution, not from check() (target 0);
- unknown_in_main: shortlist places with a hard filter that is not a `pass` by the screen's own rule (target 0,
  fail-closed); uncertain_in_main: places the screen passed with a warning because the value is UNCERTAIN outside the
  safety groups (shown, not hidden);
- near_duplicate_rate, filled (shortlist reached the trip's size), unverified, excluded, ms (pipeline time).

C.3 metrics (docs/PLACE_DECISION.md §17), for trips with `wishes` (dish | kind | like) in eval_trips.yaml:
- wish_hit_rate: of the said wishes that have a place passing the screen, the share with one in "Hợp nhất" (`top`);
  target 1.0, warn below 0.9. wish_rank_median: the median over those wishes of the best rank a meeting place has in
  its tab (target <= page_size). wishes_unresolved: wishes the corpus has no place for (left out, not counted);
- drop_one_changes: share of Search Input items (each soft weight, each wish) whose removal changes a tab's ranking
  or a card's `why` (target 1.0; `drop_one_unchanged` names the others);
- wish_penalized: places the wishes remove from the lists, give another status, or score lower (target 0);
- rebase_ms (Tools.rebase on a live session) and text_turn_ms (a typed message the keywords answer, no model)
  as p50 / p95 (targets rebase < 1000, text turn < 300).
"""

import itertools
import json
import math
import os
import statistics
import time
from datetime import date
from functools import cache
from pathlib import Path

import yaml

from corpus.ontology import load as load_ontology
from corpus.serving import dishes, feature
from trip import SearchInput, squash

from .engine import Engine
from .pipeline import Data
from .pipeline import run as run_pipeline
from .screen import hard_result
from .session import Session, State, Store
from .settings import ROOT, default
from .tools import Tools

TRIPS = ROOT / "config" / "eval_trips.yaml"
START = date(2026, 12, 14)  # a Monday
HIT_WARN = 0.9
TIMING_TRIPS = 10  # trips whose sessions time rebase
# typed messages the keywords answer without the model; "{1}".."{3}" are the names of the first places on screen
TEXT_TURNS = ("ít đông thôi", "rẻ hơn một chút", "gần trung tâm hơn", "yên tĩnh nhé", "chỉ xem quán mở trước 7h", "bỏ lọc",
              "mình thích chỗ có view đẹp", "chọn {1}", "bỏ {2}", "khóa {3}")


@cache
def trips() -> tuple[int, list[dict]]:
    raw = yaml.safe_load(TRIPS.read_text(encoding="utf-8"))
    out = list(raw["trips"])
    for i, (hard, soft) in enumerate(itertools.product(raw["cross"]["filters"], raw["cross"]["prefs"])):
        out.append({"id": f"cross_{i}", "role": "experience", "hard": hard, "soft": soft})
    return raw["shortlist"], out


def search_input(trip: dict, version: int, wishes: dict | None = None) -> SearchInput:
    """wishes: the Search Input `wishes` of the trip (see resolve_wishes); none = the trip says none."""
    ont = load_ontology()
    return SearchInput.model_validate({
        "wishes": wishes or {"dishes": [], "kinds": [], "like": []},
        "ontology_version": version,
        "context": {"start_date": START.isoformat(), "month": None, "days": 2, "base": None, "mobility": "motorbike",
                    "companions": [], "people": 2, "arrive_at": None, "leave_at": None, "day_end": None,
                    "budget_vnd": None, "experience": None},
        "hard_filters": [{"feature": f, "op": "ne", "value": v, "unknown_policy": "exclude"}
                         for f, v in trip["hard"].items()],
        "anchors": [],
        "soft_weights": [{"feature": f, "value": ont.features[f].values[0], "context": None, "weight": 1,
                          "source": "user"} for f in trip["soft"]],
        "pace": {"level": "normal", "max_leg_min": None, "crowd_tolerance": None},
        "novelty": {"level": None, "visited": []}, "unknowns": [], "unmapped": []})


def resolve_wishes(trip: dict, data: Data) -> tuple[dict, list[dict]]:
    """(Search Input wishes, unresolved): what Trip Understanding's catalog would hold for the trip's `wishes`: the
    places listing the dish (corpus.serving.dishes), the places whose category is the kind, the reference place of a
    "giống X". A wish the corpus has no place for is returned apart: it would lift nothing."""
    out, unresolved = {"dishes": [], "kinds": [], "like": []}, []
    names = data.region.column("name")
    for w in trip.get("wishes") or []:
        if "dish" in w:
            ids = [h["id"] for h in dishes.search(data.records, w["dish"], limit=len(data.records))]
            (out["dishes"] if ids else unresolved).append({"dish": w["dish"], "quote": w["dish"], "place_ids": ids} if ids else w)
        elif "kind" in w:
            key = squash(w["kind"])
            ids = [r["id"] for r in data.records if key and f" {key} " in f" {squash(r['identity'].get('category') or '')} "]
            (out["kinds"] if ids else unresolved).append({"kind": w["kind"], "quote": w["kind"], "place_ids": ids} if ids else w)
        else:
            ref = next((i for i, n in zip(data.region.ids, names) if squash(n or "") == squash(w["like"])), None)
            (out["like"] if ref else unresolved).append({"place_id": ref, "but": [], "quote": w["like"]} if ref else w)
    return out, unresolved


def violates(rec: dict, fid: str, forbidden: str) -> bool:
    f = feature(rec, fid)
    return bool(f) and f["distribution"].get(forbidden, 0) > 0


def _top_ids(res) -> set[str]:
    """"Hợp nhất": the places the view marks `top`, and the anchors."""
    return {c["id"] for g in res.view["groups"] for c in g["cards"] if c["top"] or c["anchor"]}


def _wish_rows(res) -> list[dict]:
    """One row per said wish of the run that a place passing the screen meets: the best rank of such a place in its
    tab, and whether one is in "Hợp nhất"."""
    top, rows = _top_ids(res), []
    for w in res.wishes:
        if w.kind not in ("dish", "kind", "like") or not w.places:
            continue
        ranks = [min(i for i, p in enumerate(ids) if p in w.places) + 1 for ids in res.ranked.values()
                 if any(p in w.places for p in ids)]
        if ranks:  # the corpus has a place that meets it and passes the hard constraints
            rows.append({"wish": w.key, "label": w.label, "meeting": len(w.places), "rank": min(ranks),
                         "hit": any(p in top for p in w.places)})
    return rows


def _look(res) -> tuple:
    """What a run shows of a ranking: every tab's order and every shown card's reasons."""
    return (tuple((g, tuple(ids)) for g, ids in sorted(res.ranked.items())),
            tuple((c["id"], tuple(x["text"] for x in c["why"])) for g in res.view["groups"] for c in g["cards"]))


def _items(trip: dict, wishes: dict) -> list[tuple[str, str]]:
    """The items of a trip's Search Input a user said: each soft weight and each wish, as (kind, key)."""
    return ([("soft", f) for f in trip["soft"]] + [("dish", w["dish"]) for w in wishes["dishes"]]
            + [("kind", w["kind"]) for w in wishes["kinds"]] + [("like", w["place_id"]) for w in wishes["like"]])


def _without(trip: dict, wishes: dict, item: tuple[str, str]) -> tuple[dict, dict]:
    kind, key = item
    drop = {"dish": ("dishes", "dish"), "kind": ("kinds", "kind"), "like": ("like", "place_id")}
    if kind == "soft":
        return {**trip, "soft": {f: v for f, v in trip["soft"].items() if f != key}}, wishes
    field, name = drop[kind]
    return trip, {**wishes, field: [w for w in wishes[field] if w[name] != key]}


def _penalized(with_: object, without: object) -> list[str]:
    """Places a wish removed from the lists, gave another status, or scored lower (it may only lift)."""
    listed = {p for ids in with_.ranked.values() for p in ids}
    bad = []
    for ids in without.ranked.values():
        bad += [p for p in ids if p not in listed]
    for pid in without.cands:
        if pid in with_.cands and (with_.cands[pid].status != without.cands[pid].status
                                   or with_.cands[pid].score < without.cands[pid].score - 1e-9):
            bad.append(pid)
    return sorted(set(bad))


def _pct(xs: list[float], q: float) -> int:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, max(0, math.ceil(q * len(xs)) - 1))]) if xs else 0


def _unique_names(view: dict) -> list[str]:
    """Names on screen that belong to one place only (a typed "chọn <name>" needs the name to be exact and alone)."""
    cards = {c["id"]: c["name"] for g in view["groups"] for c in g["cards"]}
    return [n for n in cards.values() if sum(squash(m) == squash(n) for m in cards.values()) == 1]


def _timing(data: Data, cfg, version: int, all_trips: list[dict]) -> dict:
    """On a live session of each of the first trips: text_turn_ms = the typed messages the keywords answer (TEXT_TURNS),
    rebase_ms = Tools.rebase with one soft weight more. The first message of the process also pays for parsing the
    records its filter reads once; `max` shows it."""
    rebase, turns, via_model = [], [], 0
    for trip in all_trips[:TIMING_TRIPS]:
        engine = Engine(data, cfg, Store(None))
        sid = engine.create(search_input(trip, version).model_dump(mode="json"))["id"]
        for text in TEXT_TURNS:
            names = _unique_names(engine.load(sid)["view"])  # read now: an earlier message may have changed the screen
            if "{" in text and int(text[text.index("{") + 1]) > len(names):
                continue
            t0 = time.perf_counter()
            engine.turn(sid, text.format("", *names), lambda *_: None)
            turns.append((time.perf_counter() - t0) * 1000)
            via_model += not engine.store.get(sid).log[-1]["action"]["log"][0].startswith("heuristic")
        more = {**trip, "soft": {**trip["soft"], "scenic_view": 1.0}}
        t0 = time.perf_counter()
        Tools(engine).rebase(sid, {"search_input": search_input(more, version).model_dump(mode="json")})
        rebase.append((time.perf_counter() - t0) * 1000)
    return {"rebase_ms": {"p50": _pct(rebase, 0.5), "p95": _pct(rebase, 0.95)},
            "text_turn_ms": {"p50": _pct(turns, 0.5), "p95": _pct(turns, 0.95), "max": _pct(turns, 1.0),
                             "messages": len(turns), "via_model": via_model}}


def evaluate(records: list[dict] | None = None, cfg=None) -> dict:
    data = Data(records) if records is not None else Data.load()
    cfg = cfg or default()
    k, all_trips = trips()
    version = load_ontology().version
    rows = []

    def run_trip(trip: dict, wishes: dict):
        return run_pipeline(Session(id="0" * 12, search_input=search_input(trip, version, wishes), state=State()), data, cfg)

    for trip in all_trips:
        wishes, unresolved = resolve_wishes(trip, data)
        si = search_input(trip, version, wishes)
        t0 = time.perf_counter()
        res = run_trip(trip, wishes)
        ms = round((time.perf_counter() - t0) * 1000)
        items = _items(trip, wishes)
        unchanged = [f"{trip['id']}:{kind}:{key}" for kind, key in items
                     if _look(run_trip(*_without(trip, wishes, (kind, key)))) == _look(res)]
        penalized = _penalized(res, run_trip(trip, {"dishes": [], "kinds": [], "like": []})) if any(wishes.values()) else []
        picked = [c["id"] for g in res.view["groups"] if g["id"] != "anchors" for c in g["cards"]
                  if c["role"] == trip["role"] and c["top"]]
        recs = [data.by_id[i] for i in picked]
        violations = [r["id"] for r in recs for f, v in trip["hard"].items() if violates(r, f, v)]
        results = {r["id"]: [hard_result(r, h) for h in si.hard_filters] for r in recs}
        unknown = [i for i, rs in results.items() if any(res_ != "pass" for res_, _ in rs)]
        uncertain = [i for i, rs in results.items() if any(warn for _, warn in rs)]
        pairs = list(itertools.combinations(recs, 2))
        dup = sum(1 for a, b in pairs if a.get("near_duplicate_group") is not None
                  and a.get("near_duplicate_group") == b.get("near_duplicate_group"))
        rows.append({"trip": trip["id"], "shortlist": picked, "names": [r["identity"]["name"] for r in recs],
                     "unverified": res.view["unverified"]["count"],
                     "excluded": sum(x["count"] for x in res.view["excluded"]["by_rule"]),
                     "violations": violations, "unknown_in_main": unknown, "uncertain_in_main": uncertain,
                     "near_duplicate_rate": round(dup / len(pairs), 3) if pairs else 0.0,
                     "filled": len(picked) >= k, "ms": ms, "wishes": _wish_rows(res), "wishes_unresolved": unresolved,
                     "drop_one_items": len(items), "drop_one_unchanged": unchanged, "wish_penalized": penalized})
    n = len(rows)
    wish_rows = [w for r in rows for w in r["wishes"]]
    items_n = sum(r["drop_one_items"] for r in rows)
    summary = {"trips": n, "shortlist": k,
               "violations": sum(len(r["violations"]) for r in rows),
               "unknown_in_main": sum(len(r["unknown_in_main"]) for r in rows),
               "uncertain_in_main": sum(len(r["uncertain_in_main"]) for r in rows),
               "near_duplicate_rate": round(sum(r["near_duplicate_rate"] for r in rows) / n, 3) if n else 0.0,
               "filled_rate": round(sum(r["filled"] for r in rows) / n, 3) if n else 0.0,
               "unfilled_trips": [r["trip"] for r in rows if not r["filled"]],
               "ms_max": max((r["ms"] for r in rows), default=0),
               "wishes": len(wish_rows),
               "wish_hit_rate": round(sum(w["hit"] for w in wish_rows) / len(wish_rows), 3) if wish_rows else None,
               "wish_hit_warn": bool(wish_rows) and sum(w["hit"] for w in wish_rows) / len(wish_rows) < HIT_WARN,
               "wish_rank_median": statistics.median(w["rank"] for w in wish_rows) if wish_rows else None,
               "wishes_unresolved": [f"{r['trip']}:{next(iter(w.values()))}" for r in rows for w in r["wishes_unresolved"]],
               "drop_one_changes": round(1 - sum(len(r["drop_one_unchanged"]) for r in rows) / items_n, 3) if items_n else None,
               "drop_one_unchanged": [u for r in rows for u in r["drop_one_unchanged"]],
               "wish_penalized": sum(len(r["wish_penalized"]) for r in rows),
               **_timing(data, cfg, version, all_trips)}
    return {"summary": summary, "trips": rows}


def run() -> dict:
    res = evaluate()
    d = Path(os.environ.get("DATA_DIR", "data"))
    out = (d if d.is_absolute() else ROOT / d) / "decision" / "eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"evaluate: {json.dumps(res['summary'], ensure_ascii=False)}")
    return res
