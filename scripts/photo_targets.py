"""Gap G3 (docs/plans/2026-10-29-assistant-tools-design.md 5B): which places have < min_photos photos a card can show.

`python scripts/photo_targets.py [--out FILE]` prints coverage (before/after use) by scene kind and category group and, with
--out, writes the places under min_photos, most reviewed first, as {"wanted": N, "places": [{"dir", "reviews", "scenes"}]}.
The photos phase reads that file through GMAPS_PHOTO_TARGETS."""
import argparse, collections, json, pathlib, sys

sys.path.insert(0, "src")
from corpus import category_group  # noqa: E402
from corpus.serving import scenes  # noqa: E402

ROOT = pathlib.Path("data/gmaps/places")
# only places with a photo_scenes file are counted: that is the served set (3,166 on 2026-10-28)


def rows():
    cfg = scenes.config()
    for f in sorted(ROOT.glob("*/place.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        g = category_group(p.get("category"), p.get("name"))["id"]
        doc = scenes.load(f.parent.name)
        if not doc:
            continue
        n = len(scenes.pick(doc, g, cfg, appeal=scenes.load_appeal(f.parent.name))) if doc else 0
        yield {"dir": f.parent.name, "group": g, "kind": scenes.kind_of(g, cfg), "reviews": p.get("reviews") or 0,
               "scenes": n, "photos": len((doc or {}).get("photos") or [])}


def report(rs, need):
    out = {}
    for key in ("kind", "group"):
        agg = collections.defaultdict(lambda: [0, 0])
        for r in rs:
            agg[r[key]][0] += 1
            agg[r[key]][1] += r["scenes"] >= need
        out[key] = {k: f"{b}/{a} = {100 * b / a:.1f}%" for k, (a, b) in sorted(agg.items())}
    out["all"] = f"{sum(r['scenes'] >= need for r in rs)}/{len(rs)} = {100 * sum(r['scenes'] >= need for r in rs) / len(rs):.1f}%"
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--wanted", type=int, default=30)
    a = ap.parse_args()
    need = scenes.config()["min_photos"]
    rs = list(rows())
    print(json.dumps(report(rs, need), ensure_ascii=False, indent=1))
    if a.out:
        todo = sorted((r for r in rs if r["scenes"] < need), key=lambda r: -r["reviews"])
        pathlib.Path(a.out).write_text(json.dumps({"wanted": a.wanted, "places": todo}, ensure_ascii=False), encoding="utf-8")
        print(len(todo), "target places ->", a.out)
