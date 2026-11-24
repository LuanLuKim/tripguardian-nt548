"""Synthetic sample data releases for NT548 (T5.2, #9): no crawled review, photo or account goes in.

Writes made-up Maps inputs (place name, category, coordinates, opening hours, one attribute) for Da Lat, then lets
TripGuardian's own offline pipeline build each release (corpus.releases.rebuild: normalize -> aggregate -> serving ->
snapshot -> index -> manifest with sha256 of every artifact). No network, no model call, no GPU.

Output, one DATA_DIR per release (ops/nt548/compose/app.yml mounts <out>/<DATA_RELEASE> at /data):
    <out>/r-a/releases/<release id>/   manifest.json, serving/, snapshot/, index/, ...
    <out>/r-a/releases/current         names that release
    <out>/r-b/...                      the same places as r-a, minus DROPPED, plus ADDED, one renamed
    <out>/r-b-drop, <out>/r-b-nocoords only with --broken: releases data_check (ops/nt548/data_check.py) must refuse
    <out>/releases.json                alias -> release id, place count

The inputs are deterministic (same seed -> same bytes, see inputs_digest). The release id and build timestamps are
not: rebuild stamps a fresh id, as it does for real releases.

usage: python ops/nt548/sample-data/make.py [--out ops/nt548/sample-data] [--seed 548] [--places 40]
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("LANCEDB_LOG", "error")  # LanceDB warns once per new table; nothing to act on
CITY = "dalat"
# (Maps category, name prefix): categories map to corpus groups via config/category_defaults.yaml
KINDS = [("Quán cà phê", "Cà phê"), ("Nhà hàng", "Quán"), ("Điểm tham quan", "Điểm"), ("Thác nước", "Thác"),
         ("Chợ", "Chợ"), ("Tiệm bánh", "Tiệm bánh")]
WORDS = ["Sương Mai", "Đồi Thông", "Mimosa", "Hoa Dã Quỳ", "Gió Núi", "Mây Trắng", "Phố Cổ", "Bên Hồ", "Lá Phong",
         "Ban Mai", "Thung Lũng", "Hoàng Hôn", "Trăng Non", "Sao Đêm", "Cỏ Hồng", "Đá Xanh"]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
# where r-b differs from r-a (indexes into the generated list; kept small so data_check's 10 % rule passes)
DROPPED = (3, 17)
ADDED = 3
RENAMED = 5


def _place(rng: random.Random, n: int) -> dict:
    category, prefix = KINDS[n % len(KINDS)]
    opens = rng.choice(["06:00", "07:00", "08:00", "09:00"])
    closes = rng.choice(["17:00", "20:00", "21:30", "22:00"])
    return {"fid": f"nt548-{n:04d}", "name": f"{prefix} {rng.choice(WORDS)} {n:02d} (mẫu)", "category": category,
            # inside the dalat area of config/cities.yaml, around the centre
            "lat": round(11.90 + rng.random() * 0.08, 6), "lng": round(108.40 + rng.random() * 0.08, 6),
            "hours": {d: [[opens, closes]] for d in DAYS if not (d == "mon" and n % 7 == 0)}}


def places(seed: int, count: int, broken: bool = False) -> dict[str, list[dict]]:
    """The place lists of r-a and r-b; r-b drops DROPPED, adds ADDED new places and renames RENAMED.
    broken=True adds two releases data_check must refuse: r-b-drop (r-b minus 20 % of r-a's places) and
    r-b-nocoords (r-b with one place that has no coordinates)."""
    rng = random.Random(seed)
    base = [_place(rng, n) for n in range(1, count + 1)]
    b = [dict(p) for i, p in enumerate(base) if i not in DROPPED]
    b += [_place(rng, n) for n in range(count + 1, count + 1 + ADDED)]
    b[RENAMED] = {**b[RENAMED], "name": b[RENAMED]["name"].replace("(mẫu)", "(mẫu, đổi tên)")}
    out = {"r-a": base, "r-b": b}
    if broken:
        out["r-b-drop"] = b[:int(count * 0.8)]
        out["r-b-nocoords"] = [{**p, "lat": None, "lng": None} if i == 0 else p for i, p in enumerate(b)]
    return out


def _observation_doc(p: dict, ontology_version: str) -> dict:
    """Same shape as corpus.observe output for one Maps attribute (tests/normalization/test_normalize.py doc())."""
    obs = {"id": "gmaps:attr:0", "place_fid": p["fid"], "feature": "outdoor_seating", "value": "present",
           "context": {}, "source_type": "gmaps_attribute", "source_id": p["fid"], "author": "gmaps:attributes",
           "observed_at": "2026-11-01", "span": {"quote": "Outdoor seating", "field": "attributes"},
           "extractor": "rules@v1", "ontology_version": ontology_version}
    return {"place_fid": p["fid"], "place_name": p["name"], "as_of": "2026-11-01", "ontology_version": ontology_version,
            "place": {"name": p["name"], "category": p["category"], "lat": p["lat"], "lng": p["lng"]},
            "place_facts": {"hours": p["hours"]}, "observations": [obs], "details": None, "ratings": []}


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def write_inputs(root: Path, rows: list[dict], ontology_version: str) -> None:
    """Replace the Maps inputs under root with rows (list, per-place observation and place file)."""
    for sub in ("gmaps/list", "gmaps/observations", "gmaps/places"):
        shutil.rmtree(root / sub, ignore_errors=True)
    _write(root / "gmaps" / "list" / f"{CITY}.json", {"items": [{"fid": p["fid"]} for p in rows]})
    for p in rows:
        _write(root / "gmaps" / "observations" / f"{p['fid']}.json", _observation_doc(p, ontology_version))
        _write(root / "gmaps" / "places" / p["fid"] / "place.json", {"fid": p["fid"], "attributes": ["Outdoor seating"]})


def inputs_digest(root: Path) -> str:
    """sha256 over every input file (path + bytes): equal for equal seeds."""
    digest = hashlib.sha256()
    for path in sorted((root / "gmaps").rglob("*.json")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def build(out: Path, seed: int = 548, count: int = 40, broken: bool = False) -> dict:
    """Build r-a then r-b in one work root (so r-b's quality.json compares against r-a), copy each to <out>/<alias>."""
    sys.path.insert(0, str(ROOT / "src"))
    from corpus import load_ontology
    from corpus.releases import rebuild, publish

    lists = places(seed, count, broken)
    summary = {"seed": seed, "city": CITY, "releases": {}}
    out.mkdir(parents=True, exist_ok=True)
    # the pipeline prints one summary per stage; keep them in build.log instead of the console
    with tempfile.TemporaryDirectory(prefix="nt548-sample-") as tmp, \
            (out / "build.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        work = Path(tmp)
        previous = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = str(work)  # anything that falls back to data_dir() stays inside the work root
        try:
            version = load_ontology().version
            for alias, rows in lists.items():
                write_inputs(work, rows, version)
                manifest = rebuild(CITY, work)
                publish(manifest["release_id"], work)
                target = out / alias
                shutil.rmtree(target, ignore_errors=True)
                (target / "releases").mkdir(parents=True)
                shutil.copytree(work / "releases" / manifest["release_id"], target / "releases" / manifest["release_id"])
                (target / "releases" / "current").write_text(manifest["release_id"], encoding="utf-8")
                summary["releases"][alias] = {"release_id": manifest["release_id"], "places": len(manifest["eligible_ids"]),
                                              "inputs_sha256": inputs_digest(work)}
        finally:
            if previous is None:
                os.environ.pop("DATA_DIR", None)
            else:
                os.environ["DATA_DIR"] = previous
    _write(out / "releases.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--seed", type=int, default=548)
    parser.add_argument("--places", type=int, default=40)
    parser.add_argument("--broken", action="store_true", help="also build r-b-drop and r-b-nocoords (data_check must refuse them)")
    args = parser.parse_args()
    summary = build(args.out.resolve(), args.seed, args.places, args.broken)
    for alias, item in summary["releases"].items():
        print(f"{alias}: {item['release_id']} ({item['places']} places) -> {args.out / alias}")


if __name__ == "__main__":
    main()
