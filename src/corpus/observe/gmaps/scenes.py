"""gmaps photo_scenes: a label per Maps photo -> data/gmaps/photo_scenes/<fid_dir>.json (docs/CORPUS.md, Ảnh Google Maps).

Per photo: scene (Extractor vision, `unknown` when unsure), has_person (yes / no / unknown + confidence), blur and
brightness (plain image statistics, no model) and a near-duplicate cluster (cosine on the existing SigLIP2 photo vectors,
the sharpest photo of a cluster is the keeper). Display only: nothing here is evidence about the place, and the raw
photos.json is never edited. Labels are cached by the photo's sha256 + prompt hash, so a second run only labels new
photos; a place is skipped while photos.json, the prompt, the vectors and the config are unchanged.
"""

import asyncio
import collections
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import yaml

from ...crawl.common.files import ROOT, append_jsonl, data_dir, load_config, now, safe_name, write_json
from ...llm import SCENE_OBSERVE, SCENES
from .photos import PHOTOS_FILE

OUT_DIR = "photo_scenes"
CONFIG_FILE = ROOT / "config" / "scenes.yaml"
VECTORS_DIR = ("gmaps", "photo_vectors")


def config() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))


def image_stats(raw: bytes, width: int = 384) -> dict:
    """{"blur": Laplacian variance, "brightness": mean luminance 0-255, "w", "h": the photo's own size} measured on the
    photo scaled to `width` px wide. All None when the bytes are not an image."""
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(raw))
        size = im.size
        im.draft("L", (width * 2, width * 2))
        im = im.convert("L")
        im = im.resize((width, max(1, round(im.height * width / im.width))))
    except (OSError, ValueError, ZeroDivisionError):
        return {"blur": None, "brightness": None, "w": None, "h": None}
    a = np.asarray(im, dtype=np.float32)
    if min(a.shape) < 3:
        return {"blur": None, "brightness": None, "w": None, "h": None}
    lap = a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4 * a[1:-1, 1:-1]
    return {"blur": round(float(lap.var()), 1), "brightness": round(float(a.mean()), 1), "w": size[0], "h": size[1]}


def components(vecs: np.ndarray, limit: float) -> list[int]:
    """For every row the smallest row index of its cluster: rows are joined while cosine >= limit (single linkage)."""
    n = len(vecs)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    if n > 1:
        v = vecs.astype(np.float32)
        v = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
        sim = v @ v.T
        for i, j in zip(*np.where(np.triu(sim >= limit, k=1))):
            a, b = find(int(i)), find(int(j))
            if a != b:
                parent[max(a, b)] = min(a, b)
    return [find(i) for i in range(n)]


def vectors_of(d: Path, root: Path) -> dict[str, np.ndarray]:
    """photo_id -> SigLIP2 vector of this place's photos (empty when the place has no vector file)."""
    stem = root.joinpath(*VECTORS_DIR) / d.name
    try:
        meta = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
        vecs = np.load(stem.with_suffix(".npy"))
    except (OSError, ValueError):
        return {}
    items = meta.get("items") or []
    if len(items) != len(vecs):
        return {}
    return {it["photo_id"]: vecs[i] for i, it in enumerate(items) if it.get("photo_id")}


def assign_clusters(entries: list[dict], vecs: dict[str, np.ndarray], limit: float) -> None:
    """Sets `cluster` (id of the first photo of the cluster) and `keep` (the sharpest photo of each cluster, ties to the
    earlier photo). A photo without a vector is its own cluster."""
    with_vec = [e for e in entries if e["photo_id"] in vecs]
    label = dict(zip((e["photo_id"] for e in with_vec),
                     components(np.stack([vecs[e["photo_id"]] for e in with_vec]), limit) if with_vec else []))
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for e in entries:
        first = label.get(e["photo_id"])
        e["cluster"] = with_vec[first]["photo_id"] if first is not None else e["photo_id"]
        groups[e["cluster"]].append(e)
    for members in groups.values():
        best = max(members, key=lambda m: (m.get("blur") if m.get("blur") is not None else -1.0))
        for m in members:
            m["keep"] = m is best


def gate(answer: dict, n: int) -> tuple[list[dict], collections.Counter]:
    """One label per photo number 1..n. A missing photo is unknown; a repeated number keeps the first; a crowd scene
    that says "no person" contradicts itself, so the person answer becomes unknown."""
    dropped: collections.Counter = collections.Counter()
    got: dict[int, dict] = {}
    for o in (answer or {}).get("photos") or []:
        i = o.get("photo")
        if not isinstance(i, int) or not 1 <= i <= n:
            dropped["bad_photo"] += 1
        elif i in got:
            dropped["duplicate"] += 1
        else:
            got[i] = o
    out = []
    for i in range(1, n + 1):
        o = got.get(i)
        if o is None:
            dropped["missing"] += 1
            out.append({"scene": "unknown", "person": {"value": None, "confidence": "low"}})
            continue
        scene = o["scene"] if o.get("scene") in SCENES else "unknown"
        person = {"yes": True, "no": False}.get(o.get("person"))
        conf = o.get("person_confidence") if o.get("person_confidence") in ("high", "medium", "low") else "low"
        if scene == "crowd" and person is False:
            dropped["crowd_without_person"] += 1
            person, conf = None, "low"
        out.append({"scene": scene, "person": {"value": person, "confidence": conf if person is not None else "low"}})
    return out, dropped


def label_hash(cfg: dict) -> str:
    return hashlib.sha256((SCENE_OBSERVE.prompt_hash + str(cfg["label"]["batch"])).encode()).hexdigest()[:12]


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


async def label_place(client, model: str, sem: asyncio.Semaphore, city: str, d: Path, root: Path, cfg: dict,
                      old: dict | None) -> dict:
    place = json.loads((d / "place.json").read_text(encoding="utf-8"))
    doc = json.loads((d / PHOTOS_FILE).read_text(encoding="utf-8"))
    photos = [p for p in doc["photos"] if not p.get("stale") and (d / p["file"]).exists()]  # stale = cover only
    lh = label_hash(cfg)
    cached = {e["sha"]: e for e in (old or {}).get("photos", []) if e.get("sha")}
    entries, todo = [], []
    for p in photos:
        raw = await asyncio.to_thread((d / p["file"]).read_bytes)
        sha = hashlib.sha256(raw).hexdigest()[:24]
        prev = cached.get(sha)
        e = {"photo_id": p["photo_id"], "file": p["file"], "sha": sha, "kind": p.get("kind"), "owner": bool(p.get("owner")),
             "author_hash": p.get("author_hash"), "month": p.get("month")}
        if prev and prev.get("label_hash") == lh:
            e.update({k: prev[k] for k in ("blur", "brightness", "w", "h", "scene", "person", "label_hash") if k in prev})
            if "w" not in prev:  # labelled before sizes were stored: measure again, the labels stay
                e.update({k: v for k, v in (await asyncio.to_thread(image_stats, raw, cfg["label"]["stats_width"])).items()})
        else:
            e.update(await asyncio.to_thread(image_stats, raw, cfg["label"]["stats_width"]))
            todo.append((e, raw))
        entries.append(e)
    dropped: collections.Counter = collections.Counter()
    size = cfg["label"]["batch"]

    async def one(batch: list[tuple[dict, bytes]]) -> None:
        listing = "; ".join(f"{i} = {'owner' if e['owner'] else 'visitor'} {e.get('kind') or 'photo'}"
                            for i, (e, _) in enumerate(batch, 1))
        async with sem:
            answer = await SCENE_OBSERVE.ask(client, model, images=[r for _, r in batch], city=city, count=len(batch),
                                             name=place.get("name"), category=place.get("category") or "unknown",
                                             photo_list=listing)
        labels, drop = gate(answer, len(batch))
        dropped.update(drop)
        for (e, _), lab in zip(batch, labels):
            e.update(lab)
            e["label_hash"] = lh

    await asyncio.gather(*(one(todo[s:s + size]) for s in range(0, len(todo), size)))
    assign_clusters(entries, vectors_of(d, root), cfg["cluster_cos"])
    return {"place_fid": place["fid"], "place_name": place.get("name"), "as_of": doc["fetched_at"][:10], "photos": entries,
            "stats": {"photos": len(entries), "labelled_now": len(todo), "dropped": dict(dropped)}}


def input_hash(d: Path, root: Path, cfg: dict) -> str:
    vec = root.joinpath(*VECTORS_DIR) / f"{d.name}.json"
    raw = (d / PHOTOS_FILE).read_bytes() + (vec.read_bytes() if vec.exists() else b"") + label_hash(cfg).encode() \
        + str(cfg["cluster_cos"]).encode() + str(cfg["label"]["stats_width"]).encode() + b"stats:w,h"
    return hashlib.sha256(raw).hexdigest()[:16]


async def run(city: str, limit: int | None = None, shard: tuple[int, int] | None = None) -> dict:
    """shard (i, n): only every n-th place from i. Places of the serving file only; a failed place has no new file and a
    line in data/gmaps/photo_scene_errors.jsonl."""
    name, _ = load_config(city)
    root = data_dir()
    gm = root / "gmaps"
    out = gm / OUT_DIR
    cfg = config()
    serving = json.loads((root / "serving" / "places.json").read_text(encoding="utf-8"))["records"]
    dirs = [gm / "places" / safe_name(r["id"]) for r in serving]
    dirs = [d for d in dirs if (d / PHOTOS_FILE).exists()]
    dirs = dirs[shard[0]::shard[1]] if shard else dirs
    dirs = dirs[:limit] if limit is not None else dirs
    client, model = SCENE_OBSERVE.role.client()
    client = client.with_options(timeout=240, max_retries=0)
    sem = asyncio.Semaphore(cfg["label"]["parallel"] or SCENE_OBSERVE.role.parallel())
    places = asyncio.Semaphore(8)  # places read and measured at once (disk and CPU), not model calls
    status: collections.Counter = collections.Counter()

    async def one(d: Path) -> None:
        target = out / f"{d.name}.json"
        h = input_hash(d, root, cfg)
        old = _json(target)
        if old and old.get("input_hash") == h:
            status["cached"] += 1
            return
        async with places:
            try:
                res = await label_place(client, model, sem, name, d, root, cfg, old)
            except Exception as e:
                append_jsonl(gm / "photo_scene_errors.jsonl", {"at": now(), "place": d.name,
                                                              "error": f"{type(e).__name__}: {e}"[:300]})
                status["failed"] += 1
                return
        write_json(target, {**res, "input_hash": h, "label_hash": label_hash(cfg), "model": model, "built_at": now()})
        status["done"] += 1
        if sum(status.values()) % 100 == 0:
            print(f"gmaps photo_scenes {city}: {dict(status)} of {len(dirs)}", flush=True)

    await asyncio.gather(*(one(d) for d in dirs))
    summary = {"at": now(), "places": len(dirs), "status": dict(status)}
    print(f"gmaps photo_scenes {city}: {json.dumps(summary, ensure_ascii=False)}")
    return summary
