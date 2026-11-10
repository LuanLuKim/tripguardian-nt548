"""Rank served places by reviews and usable photo tier; export independently of printing."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA, REPO


def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def rows(min_reviews: int = 1000) -> list[dict]:
    from auto3d import config

    threshold = config()["evidence_min"]
    done = {p["id"].replace(":", "_") for p in _load(REPO / "web/space3d/places.json", [])}
    skip = _load(DATA / "batch/skip.json", [])
    kits = {x["fid"]: x.get("kit") for x in _load(DATA / "batch/inventory.json", [])}
    result = []
    for record in _load(REPO / "data/serving/places.json", {"records": []})["records"]:
        identity = record["identity"]
        reviews = identity.get("reviews") or 0
        if reviews < min_reviews:
            continue
        fid = record["id"].replace(":", "_")
        photos = _load(REPO / "data/gmaps/photo_scenes" / f"{fid}.json", {"photos": []})["photos"]
        scenes = Counter(p.get("scene") for p in photos if p.get("keep", True) and not p.get("stale"))
        ext, view, inside = scenes["exterior"], scenes["view"], scenes["interior"] + scenes["room"]
        tier = ("done" if fid in done else "skip" if fid in skip else "A" if ext >= threshold
                else "B" if ext + view >= threshold else "C")
        result.append({"fid": fid, "name": identity["name"], "group": identity.get("category_group"), "reviews": reviews,
                       "ext": ext, "view": view, "int": inside, "tier": tier, "kit": kits.get(fid)})
    return sorted(result, key=lambda x: -x["reviews"])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("min_reviews", type=int, nargs="?", default=1000)
    parser.add_argument("--json", dest="output")
    args = parser.parse_args(argv)
    values = rows(args.min_reviews)
    if args.output:
        target = DATA / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n")
        return
    print(f">= {args.min_reviews} reviews: {len(values)} places;", dict(Counter(x["tier"] for x in values)))
    for x in values:
        if x["tier"] in ("A", "B", "C"):
            print(f"{x['tier']} {x['reviews']:>6} {x['kit'] or '?':<10} {x['group'] or '':<12} "
                  f"ext {x['ext']:>2} view {x['view']:>2} int {x['int']:>2}  {x['name'][:48]}  {x['fid']}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
