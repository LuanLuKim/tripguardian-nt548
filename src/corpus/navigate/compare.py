"""Phase `navigate compare` (spec A.9 item 11): what sol proposed blind, against what we already hold.

Reads the ontology, the query config, seasons, dishes, scene names and the places in data/serving/places.json; writes
only `compare_<ts>.json` and `resolve_queue.jsonl` under data/<city>/navigate/. Everything the report calls new is a
proposal with `approval = "pending"`: no code path here adds a feature to the ontology, a line to a config file or a
place to the corpus.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .. import data_root, load_ontology
from ..crawl.web import seed_queries
from ..retrieval import NameRecord, name_score, search_names
from .common import NavigateError, city_info, config, navigate_dir, stamp, write_json, yaml_file
from .plan import load_map
from .schema import MiningMap, fold

FEATURE = "ontology"
REJECTED_FILE = "mining_map_rejected.json"
_SPLIT = re.compile(r"[,;:()/]| - ")


@dataclass(frozen=True)
class Place:
    place_id: str
    name: str


@dataclass
class Known:
    """What the corpus side already holds, as plain text to match against."""
    feature_ids: set[str] = field(default_factory=set)
    concepts: list[tuple[str, str, str]] = field(default_factory=list)  # (source, ref, text)
    queries: list[str] = field(default_factory=list)  # "{city}" stands for the city name
    city_name: str = ""
    ontology_version: int | None = None


def _strings(node, out: list[str]) -> None:
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _strings(v, out)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _strings(v, out)


def load_known(city: str) -> Known:
    """Ontology features (id, hint segments, claims), config/queries.yaml and the web seed phrases, seasons, dish
    groups and the scene names, as they are now."""
    name, _ = city_info(city)
    onto = load_ontology()
    known = Known(feature_ids=set(onto.features), city_name=name, ontology_version=onto.version)
    for f in onto.features.values():
        known.concepts.append((FEATURE, f.id, f.id.replace("_", " ")))
        known.concepts += [(FEATURE, f.id, seg.strip()) for seg in _SPLIT.split(f.hint or "") if seg.strip()]
        known.concepts += [(FEATURE, f.id, c) for c in (getattr(f, "claims", None) or {}).values()]
    for row in yaml_file("seasons.yaml").get("seasons") or []:
        known.concepts.append(("season", row["match"], row["match"]))
    for group in yaml_file("dishes.yaml").get("same") or []:
        known.concepts += [("dish", group[0], d) for d in group]
    for order in ((yaml_file("scenes.yaml").get("pick") or {}).get("scene_order") or {}).values():
        known.concepts += [("scene", s, s) for s in order]
    cfg = yaml_file("queries.yaml")
    texts: list[str] = []
    _strings({k: v for k, v in cfg.items() if k in ("tiktok", "gmaps", "stay")}, texts)
    known.queries = [t for t in texts if " " in t and len(t) <= 80] \
        + [q.text for q in seed_queries(name) if not q.text.startswith(("site:", "tiktok"))]
    return known


def load_places(city: str) -> list[Place]:
    """The places the corpus serves for the city (data/serving/places.json), those inside the city's area."""
    path = data_root() / "serving" / "places.json"
    if not path.exists():
        raise NavigateError(f"{path} is missing: run `python -m corpus serving` first")
    _, area = city_info(city)
    out = []
    for r in json.loads(path.read_text(encoding="utf-8"))["records"]:
        ident = r.get("identity") or {}
        lat, lng = ident.get("lat"), ident.get("lng")
        inside = lat is None or lng is None or (area[0] <= lat <= area[2] and area[1] <= lng <= area[3])
        if inside and ident.get("name"):
            out.append(Place(r["id"], ident["name"]))
    return out


def _tokens(text: str, drop: set[str]) -> frozenset[str]:
    return frozenset(t for t in fold(text.replace("{city}", " ")).split() if len(t) > 1 and t not in drop)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Token Jaccard. One shared word is no match unless both sides are that single word ("hiking" = "hiking"; "rain" is
    not "rain day options"): short token sets reach 0,5 by luck."""
    if not a or not b or (len(a & b) < 2 and a != b):
        return 0.0
    return len(a & b) / len(a | b)


def _aspect_status(aspect, known: Known, drop: set[str], thr: float) -> tuple[str, dict | None]:
    target = aspect.target
    ref = target.ref if target.kind in ("feature", "new_feature") else ""
    if ref in known.feature_ids:
        return "covered_feature", {"source": FEATURE, "ref": ref, "score": 1.0, "text": ref}
    views = [_tokens(t, drop) for t in (aspect.name_vi, aspect.key.replace("_", " "), ref.replace("_", " ")) if t]
    best: dict[str, tuple[float, str, str]] = {}
    for source, cref, text in known.concepts:
        tokens = _tokens(text, drop)
        score = max((_jaccard(v, tokens) for v in views), default=0.0)
        if score > best.get(source, (0.0, "", ""))[0]:
            best[source] = (score, cref, text)
    feature = best.get(FEATURE)
    if feature and feature[0] >= thr:
        return "covered_feature", {"source": FEATURE, "ref": feature[1], "score": round(feature[0], 2), "text": feature[2]}
    others = [(s, v) for s, v in best.items() if s != FEATURE and v[0] >= thr]
    if others:
        s, (score, cref, text) = max(others, key=lambda x: x[1][0])
        return "covered_query", {"source": s, "ref": cref, "score": round(score, 2), "text": text}
    query_tokens = [_tokens(q, drop) for q in known.queries]
    score, text = max(((_jaccard(v, qt), q) for v in views for q, qt in zip(known.queries, query_tokens)), default=(0.0, ""))
    if score >= thr:
        return "covered_query", {"source": "query", "ref": text.replace("{city}", known.city_name).strip(), "score": round(score, 2),
                                        "text": text.replace("{city}", known.city_name).strip()}
    return "new", None


def load_rejected(city: str) -> set[tuple[str, str, str]]:
    """Owner-reviewed wrong matches, (aspect key, match source, match ref), from data/<city>/navigate/mining_map_rejected.json."""
    path = navigate_dir(city) / REJECTED_FILE
    if not path.exists():
        return set()
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("rejected", [])
    except (ValueError, AttributeError):
        return set()
    return {(r["aspect"], r.get("source", ""), r["ref"]) for r in rows if isinstance(r, dict) and "aspect" in r and "ref" in r}


def _queries(aspect, known: Known, drop: set[str], thr: float) -> dict:
    tokens = [_tokens(q, drop) for q in known.queries]
    held, new = [], []
    for q in aspect.queries:
        t = _tokens(q, drop)
        (held if any(_jaccard(t, k) >= thr for k in tokens) else new).append(q)
    return {"total": len(aspect.queries), "held": held, "new": new}


def _covered(nominee: str, name: str, drop: set[str]) -> float:
    """Share of the nominee's own words found in the corpus name. name_score is high when a short corpus name sits
    inside a long nominee ("Nhà thờ Con Gà" ~ "Ga Đà Lạt"); such a match covers a quarter of the nominee and is no proof."""
    words = _tokens(nominee, drop)
    return len(words & _tokens(name, drop)) / len(words) if words else 0.0


def _nominee(nominee, places: list[Place], held: float, maybe: float, drop: set[str], cover: float) -> dict:
    records = [NameRecord(p.place_id, p.name) for p in places]
    hits = search_names(nominee.name, records, within={p.place_id for p in places}, release_id=None, limit=3)
    matches = sorted(({"place_id": h.place_id, "name": h.name, "score": round(name_score(nominee.name, h.name), 2)}
                      for h in hits), key=lambda m: -m["score"])
    best = matches[0]["score"] if matches else 0.0
    covered = _covered(nominee.name, matches[0]["name"], drop) if matches else 0.0
    status = "held" if best >= held and covered >= cover else "maybe" if best >= maybe else "missing"
    return {"name": nominee.name, "area_hint": nominee.area_hint, "status": status, "matches": matches}


def _queue(city: str, rows: list[dict]) -> int:
    path = navigate_dir(city) / "resolve_queue.jsonl"
    seen = set()
    if path.exists():
        seen = {fold(json.loads(line)["name"]) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    fresh = []
    for row in rows:
        if fold(row["name"]) not in seen:
            seen.add(fold(row["name"]))
            fresh.append(row)
    if fresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for row in fresh:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(fresh)


def compare_map(city: str, mining_map: MiningMap | None = None, *, known: Known | None = None,
                places: list[Place] | None = None, now: datetime | None = None) -> dict:
    """Diff the city's mining map against what we hold; write compare_<ts>.json and the resolve queue; return the report."""
    mining_map = mining_map or load_map(city)
    if mining_map is None:
        raise NavigateError(f"no mining map for {city}: run `python -m corpus navigate plan --city {city}` first")
    known = known or load_known(city)
    places = load_places(city) if places is None else places
    cfg, now = config(), now or datetime.now(UTC)
    thr, held_t, maybe_t = cfg["match"]["jaccard"], cfg["nominee"]["held"], cfg["nominee"]["maybe"]
    cover_t = cfg["nominee"]["covered"]
    drop = set(fold(known.city_name).split())
    aspects, new_features, queue = [], [], []
    rejected = load_rejected(city)
    for a in mining_map.aspects:
        status, match = _aspect_status(a, known, drop, thr)
        if match and (a.key, match["source"], match["ref"]) in rejected:
            status, match = "new", None  # the owner judged this match wrong: back to a proposal, never dropped
        entry = {"key": a.key, "name_vi": a.name_vi, "target": a.target.model_dump(mode="json"), "status": status,
                 "match": match, "queries": _queries(a, known, drop, thr),
                 "nominees": [_nominee(n, places, held_t, maybe_t, drop, cover_t) for n in a.nominees]}
        if status == "new":
            entry["approval"] = "pending"
            if a.target.new_feature is not None:
                new_features.append({**a.target.new_feature.model_dump(mode="json"), "aspect": a.key, "approval": "pending"})
        aspects.append(entry)
        queue += [{"name": n["name"], "area_hint": n["area_hint"], "aspect": a.key, "city": city,
                   "proposed_at": now.isoformat(timespec="seconds"), "status": "proposed", "approval": "pending"}
                  for n in entry["nominees"] if n["status"] == "missing"]
    count = lambda key, items, field_: sum(1 for i in items if i[field_] == key)  # noqa: E731
    nominees = [n for a in aspects for n in a["nominees"]]
    report = {
        "city": city, "compared_at": now.isoformat(timespec="seconds"), "map_generated_at": mining_map.generated_at,
        "map_model": mining_map.model, "ontology_version": known.ontology_version, "places_compared": len(places),
        "summary": {
            "aspects": {k: count(k, aspects, "status") for k in ("covered_feature", "covered_query", "new")},
            "new_features": len(new_features),
            "nominees": {k: count(k, nominees, "status") for k in ("held", "maybe", "missing")},
            "queries": {"total": sum(a["queries"]["total"] for a in aspects),
                        "held": sum(len(a["queries"]["held"]) for a in aspects),
                        "new": sum(len(a["queries"]["new"]) for a in aspects)},
            "general_claims": len(mining_map.general_claims),
        },
        "aspects": aspects, "new_features": new_features,
    }
    report["summary"]["resolve_queue_added"] = _queue(city, queue)
    write_json(navigate_dir(city) / f"compare_{stamp(now)}.json", report)
    return report


def table(report: dict) -> str:
    """The report as text for the owner: what is already covered, and the new part waiting for approval."""
    s = report["summary"]
    lines = [f"navigate compare {report['city']}: bản đồ của {report['map_model']} lúc {report['map_generated_at']}, "
             f"so với ontology v{report['ontology_version']} và {report['places_compared']} nơi",
             f"- aspect: {s['aspects']['covered_feature']} trùng feature, {s['aspects']['covered_query']} trùng query/mùa/món/cảnh, "
             f"{s['aspects']['new']} mới",
             f"- query của sol: {s['queries']['total']} (đã có {s['queries']['held']}, mới {s['queries']['new']})",
             f"- nominee: {s['nominees']['held']} đã có, {s['nominees']['maybe']} có thể trùng, {s['nominees']['missing']} chưa có "
             f"(vào resolve_queue: {s['resolve_queue_added']} mới)",
             "", "Cần duyệt (chưa có gì được thêm vào ontology, config hay corpus):"]
    new = [a for a in report["aspects"] if a["status"] == "new"]
    if not new:
        lines.append("  (không có aspect mới)")
    for a in new:
        t = a["target"]
        extra = ""
        if t["new_feature"]:
            nf = t["new_feature"]
            extra = f" | feature mới {nf['key']} ({nf['type']}: {', '.join(nf['values'])})"
        lines.append(f"  - {a['key']} — {a['name_vi']} [{t['kind']}:{t['ref']}]{extra}")
    missing = [(a["key"], n) for a in report["aspects"] for n in a["nominees"] if n["status"] == "missing"]
    if missing:
        lines += ["", "Nominee chưa có trong corpus (chờ resolve Maps, sol đề cử không phải bằng chứng nơi có thật):"]
        lines += [f"  - {n['name']} ({n['area_hint']}) — {key}" for key, n in missing]
    maybe = [(a["key"], n) for a in report["aspects"] for n in a["nominees"] if n["status"] == "maybe"]
    if maybe:
        lines += ["", "Nominee có thể trùng nơi đã có:"]
        lines += [f"  - {n['name']} ~ {n['matches'][0]['name']} ({n['matches'][0]['score']})" for _, n in maybe]
    return "\n".join(lines)
