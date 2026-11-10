"""Which Maps photos of a place show the same buildings: SIFT + RANSAC homography inliers between every pair of
exterior photos, then connected components of the "strong match" graph. Photos outside the largest component are
suspects (possibly another place), to be confirmed by a vision model or a person; never dropped on this alone.

Usage: python photo_match.py <fid_dir> [more fid_dirs]  -> prints components, writes batch/match/<fid>.json"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA, REPO

import itertools
import json

import cv2
import numpy as np

ROOT = REPO
OUT = DATA / "batch/match"
MIN_INLIERS = 25  # a pair with this many RANSAC inliers shows the same physical thing
SIDE = 900


def features(path, sift):
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    s = SIDE / max(img.shape)
    img = cv2.resize(img, None, fx=s, fy=s) if s < 1 else img
    return sift.detectAndCompute(img, None)


def inliers(a, b, matcher):
    if a[1] is None or b[1] is None or len(a[0]) < 8 or len(b[0]) < 8:
        return 0
    good = [m for m, n in (p for p in matcher.knnMatch(a[1], b[1], k=2) if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return 0
    src = np.float32([a[0][m.queryIdx].pt for m in good])
    dst = np.float32([b[0][m.trainIdx].pt for m in good])
    _, mask = cv2.findFundamentalMat(src, dst, cv2.USAC_MAGSAC, 1.5, 0.999)
    return int(mask.sum()) if mask is not None else 0


def run(fid):
    scenes = json.loads((ROOT / "data/gmaps/photo_scenes" / f"{fid}.json").read_text())["photos"]
    photos = [p for p in scenes if p.get("scene") in ("exterior", "view")]
    sift, matcher = cv2.SIFT_create(nfeatures=3000), cv2.BFMatcher()
    feats = [features(ROOT / "data/gmaps/places" / fid / p["file"], sift) for p in photos]
    n = len(photos)
    edges = np.zeros((n, n), int)
    for i, j in itertools.combinations(range(n), 2):
        if feats[i] and feats[j]:
            edges[i, j] = edges[j, i] = inliers(feats[i], feats[j], matcher)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, j in itertools.combinations(range(n), 2):
        if edges[i, j] >= MIN_INLIERS:
            parent[find(i)] = find(j)
    comps = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    comps = sorted(comps.values(), key=len, reverse=True)
    doc = {"fid": fid, "min_inliers": MIN_INLIERS, "photos": [p["photo_id"] for p in photos],
           "components": [[photos[i]["photo_id"] for i in c] for c in comps],
           "best_inliers": {photos[i]["photo_id"]: int(edges[i].max()) if n > 1 else 0 for i in range(n)}}
    OUT.mkdir(exist_ok=True)
    (OUT / f"{fid}.json").write_text(json.dumps(doc, indent=1))
    return doc


if __name__ == "__main__":
    for fid in sys.argv[1:]:
        d = run(fid)
        print(fid, "sizes", [len(c) for c in d["components"]])
        for c in d["components"]:
            print("  ", [(p[:14], d["best_inliers"][p]) for p in c])
