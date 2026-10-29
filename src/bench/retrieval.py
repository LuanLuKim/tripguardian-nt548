"""python -m bench retrieval: speed and correctness of corpus.retrieval card / find / vocabulary on a real release.

Every case is one suggestion of spec §2.1 turned into criteria. `correct` re-checks each hit on its serving record with
code that does not share find's cache or columns; `recall` compares find (limit = all) with that brute-force pass.
Offline: no model, no network. Writes data/bench/retrieval/<timestamp>.json and prints a table.
"""

import math
import time
from datetime import datetime
from pathlib import Path

import orjson

from corpus.ontology import load as load_ontology
from corpus.retrieval import Criteria, RetrievalEngine
from corpus.serving import dishes, feature

ROOT = Path(__file__).resolve().parents[2]
FIRM = ("VERIFIED", "OUTDATED")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
FIND_P95_MS, CARD_P95_MS, CARD_CHARS_P95, CHARS_PER_TOKEN = 30, 1, 2000, 3
SIGHTS = ["attraction", "nature", "garden_farm", "amusement"]

CASES: list[tuple[str, dict]] = [
    ("cafe_view", {"groups": ["cafe"], "must": [["scenic_view", "present"]]}),
    ("cloud", {"must": [["cloud_hunting", "present"]]}),
    ("early", {"groups": ["cafe"], "opens_by": "06:00"}),
    ("laptop", {"groups": ["cafe"], "must": [["laptop_friendly", "present"]]}),
    ("music", {"must": [["live_music", "present"]]}),
    ("veg", {"must": [["vegetarian_options", "yes"]]}),
    ("kids", {"groups": SIGHTS, "must": [["kids", "suitable"]]}),
    ("elderly", {"groups": SIGHTS[:3], "must": [["steep_or_stairs", "absent"]]}),
    ("pets", {"groups": ["cafe"], "must": [["pets", "allowed"]]}),
    ("sunset", {"must": [["sunset_view", "present"]]}),
    ("pick", {"must": [["pick_your_own", "present"]]}),
    ("lau_ga", {"dish": "lá é"}),
    ("banh_can", {"dish": "bánh căn"}),
    ("xiu_mai", {"dish": "xíu mại"}),
    ("parking", {"groups": ["cafe"], "must": [["parking", "easy"]]}),
    ("cafe_view_sat_7", {"groups": ["cafe"], "must": [["scenic_view", "present"]], "open_at": ["sat", "07:00"]}),
    ("kids_near", {"groups": SIGHTS, "must": [["kids", "suitable"]], "near": [11.9404, 108.4583, 5]}),
    ("veg_quiet", {"must": [["vegetarian_options", "yes"]], "prefer": [["noise", "quiet"]]}),
]


def pct(xs: list[float]) -> dict:
    s = sorted(xs)
    at = lambda q: s[min(len(s) - 1, round(q * (len(s) - 1)))]  # noqa: E731
    return {"p50": round(at(0.5), 3), "p95": round(at(0.95), 3), "max": round(s[-1], 3)}


def _minutes(text: str) -> int:
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def _open_at(hours: dict, day: str, t: int) -> bool:
    """Open at minute t of `day`: a range of that day, or an overnight range of the day before still running."""
    prev = DAYS[DAYS.index(day) - 1]
    for a, b in (hours.get(day) or []):
        a, b = _minutes(a), _minutes(b)
        if (a <= t < b) or (b < a and t >= a):
            return True
    return any(_minutes(b) < _minutes(a) and t < _minutes(b) for a, b in (hours.get(prev) or []))


def _km(lat0, lng0, lat, lng) -> float:
    p0, p1 = math.radians(lat0), math.radians(lat)
    h = math.sin((p1 - p0) / 2) ** 2 + math.cos(p0) * math.cos(p1) * math.sin(math.radians(lng - lng0) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def judge(record: dict, c: Criteria) -> str:
    """hit | maybe | unknown | out: this record against the criteria, read straight from the serving record."""
    ident, hours = record["identity"], (record.get("operation") or {}).get("hours") or {}
    group = ident.get("category_group")
    if (group not in c.groups) if c.groups else (group == "stay"):
        return "out"
    if c.near and (ident.get("lat") is None or ident.get("lng") is None
                   or _km(c.near[0], c.near[1], ident["lat"], ident["lng"]) > c.near[2]):
        return "out"
    firm_hours = hours.get("status") in FIRM and hours.get("value")
    if c.open_at and not (firm_hours and _open_at(hours["value"], c.open_at[0], _minutes(c.open_at[1]))):
        return "out"
    if c.opens_by and not (firm_hours and any(_minutes(a) <= _minutes(c.opens_by)
                                              for rs in hours["value"].values() for a, _ in rs)):
        return "out"
    if c.dish:
        wanted, accented = dishes.phrases(c.dish)
        names = [d["name"] for d in (record.get("menu") or {}).get("dishes") or [] if d.get("name")]
        if not any(dishes.has_phrase(dishes.key_for(n, accented), w) for n in names for w in wanted):
            return "out"
    verdict = "hit"
    for fid, value in c.must:
        f = feature(record, fid)
        if f is None:
            verdict = "unknown" if verdict != "out" else verdict
        elif f["value"] != value or f["status"] not in (*FIRM, "UNCERTAIN"):
            return "out"
        elif f["status"] == "UNCERTAIN" and verdict == "hit":
            verdict = "maybe"
    return verdict


def run(engine: RetrievalEngine, repeats: int = 30) -> dict:
    region = engine._region  # bench reads the whole region to brute-force the expected answer
    records = region.records()
    ont = load_ontology()
    cases = {}
    for name, raw in CASES:
        c = Criteria.parse(raw, ont)
        engine.find(raw)  # untimed: first call
        times = []
        for _ in range(repeats):
            t = time.perf_counter()
            found = engine.find(raw)
            times.append((time.perf_counter() - t) * 1000)
        everything = engine.find(raw, limit=len(records) or 1)
        verdicts = {r["id"]: judge(r, c) for r in records}
        expected = {pid for pid, v in verdicts.items() if v == "hit"}
        got = {h.place_id for h in everything.hits}
        cases[name] = {
            "hits": len(everything.hits), "maybe": len(everything.maybe), "unknown": everything.unknown,
            "find_ms": pct(times), "shown": len(found.hits),
            "correct": got <= expected and all(verdicts[h.place_id] == "maybe" for h in everything.maybe),
            "recall": len(got & expected) / len(expected) if expected else 1.0,
            "expected": {"hits": len(expected), "maybe": sum(v == "maybe" for v in verdicts.values()),
                         "unknown": sum(v == "unknown" for v in verdicts.values())}}
    ms, chars = [], []
    for pid in region.ids:
        t = time.perf_counter()
        card = engine.card(pid)
        ms.append((time.perf_counter() - t) * 1000)
        chars.append(len(orjson.dumps(card)))
    card_chars = pct([float(x) for x in chars])
    out = {"release_id": engine.release_id, "places": len(records), "repeats": repeats, "cases": cases,
           "card": {"ms": pct(ms), "chars": card_chars, "tokens_p95": round(card_chars["p95"] / CHARS_PER_TOKEN)},
           "vocabulary": {"chars": len(orjson.dumps(engine.vocabulary()))}}
    out["ok"] = bool(all(c["find_ms"]["p95"] <= FIND_P95_MS and c["correct"] and c["recall"] == 1.0
                         for c in cases.values())
                     and out["card"]["ms"]["p95"] <= CARD_P95_MS and card_chars["p95"] <= CARD_CHARS_P95)
    return out


def main(release: str | None, out: Path | None) -> int:
    t = time.perf_counter()
    engine = RetrievalEngine.open(release)
    opened = time.perf_counter() - t
    engine.warm()
    result = {"at": datetime.now().isoformat(timespec="seconds"),
              "startup": {"open_s": round(opened, 2), "open_warm_s": round(time.perf_counter() - t, 2)},
              **run(engine)}
    out = out or ROOT / "data" / "bench" / "retrieval"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_bytes(orjson.dumps(result, option=orjson.OPT_INDENT_2))
    print(f"release {result['release_id'] or 'legacy'}  places {result['places']}  startup open {opened:.2f}s "
          f"open+warm {result['startup']['open_warm_s']}s")
    print(f"{'case':16} {'hits':>5} {'maybe':>5} {'unk':>5} {'p50ms':>7} {'p95ms':>7} {'max':>7} {'correct':>7} {'recall':>6}")
    for name, c in result["cases"].items():
        f = c["find_ms"]
        print(f"{name:16} {c['hits']:5} {c['maybe']:5} {c['unknown']:5} {f['p50']:7.2f} {f['p95']:7.2f} {f['max']:7.2f} "
              f"{str(c['correct']):>7} {c['recall']:6.2f}")
    card = result["card"]
    print(f"card ms p50 {card['ms']['p50']} p95 {card['ms']['p95']}; chars p50 {card['chars']['p50']:.0f} "
          f"p95 {card['chars']['p95']:.0f} max {card['chars']['max']:.0f}; ~tokens p95 {card['tokens_p95']}; "
          f"vocabulary {result['vocabulary']['chars']} chars")
    print(f"ok: {result['ok']}  -> {path}")
    return 0 if result["ok"] else 1
