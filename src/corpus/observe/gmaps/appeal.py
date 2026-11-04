"""gmaps photo_appeal: how appealing a place's card photos are -> data/gmaps/photo_appeal/<fid_dir>.json (docs/CORPUS.md,
Ảnh Google Maps).

The card candidates of a place (corpus.serving.scenes.candidates: right scene for its kind, no stranger in frame, clean,
no near-duplicate), at most config `appeal.rank_max` of them by sharpness and exposure (topped up with photos of other
scenes when those are fewer), go to the Extractor in one call
(PHOTO_RANK): beauty 1-10 and shows_place 1-10 per photo. scenes.pick orders the card by their sum (owner 2026-10-30:
the photos that make a user want to go and show what the place is like). Display only: nothing here is evidence about
the place. A place is skipped while its scene labels, its category group, the prompt and the config are unchanged; a
photo keeps its scores while its bytes (sha) and the prompt are unchanged.
"""

import asyncio
import collections
import hashlib
import io
import json
from pathlib import Path

from ...crawl.common.files import append_jsonl, data_dir, load_config, now, safe_name, write_json
from ...llm import PHOTO_RANK
from ...serving import scenes

OUT_DIR = scenes.APPEAL_DIR
CHOSEN = "own+off_kind+people"  # which photos `chosen` sends; part of the input hash, change it with that rule


def config() -> dict:
    """config/scenes.yaml (the cached copy corpus.serving.scenes reads; `appeal` and `pick`)."""
    return scenes.full_config()


def gate(answer: dict | None, n: int) -> dict[int, tuple[int, int]]:
    """photo number -> (beauty, shows_place) for every well-formed entry (integers 1-10, first entry of a number wins);
    anything else is left unscored."""
    out: dict[int, tuple[int, int]] = {}
    for e in (answer or {}).get("photos") or []:
        i, b, s = e.get("photo"), e.get("beauty"), e.get("shows_place")
        if all(isinstance(x, int) and not isinstance(x, bool) for x in (i, b, s)) and 1 <= i <= n and i not in out \
                and 1 <= b <= 10 and 1 <= s <= 10:
            out[i] = (b, s)
    return out


def shrink(raw: bytes, px: int) -> bytes:
    """The photo as JPEG with its longest side at most px (what the model needs, a fraction of the upload)."""
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((px, px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def chosen(doc: dict, group: str | None, cfg: dict) -> list[dict]:
    """The photos sent to the model: the sharpest, best exposed `rank_max` card candidates, topped up with the sharpest
    `off_kind` photos when the kind's own scenes are fewer, and a place short of `min_photos` also with its visitor
    photos with people (the model then says whether they show the place)."""
    best = lambda rows: sorted(rows, key=scenes.quality, reverse=True)  # noqa: E731
    n = cfg["appeal"]["rank_max"]
    own = best(scenes.candidates(doc, group, cfg["pick"]))[:n]
    more = scenes.off_kind(doc, group, cfg["pick"])
    if len(own) < cfg["pick"]["min_photos"]:
        more += scenes.with_people(doc, cfg["pick"])
    return own + best(more)[:n - len(own)]


def input_hash(doc: dict, group: str | None, cfg: dict) -> str:
    raw = json.dumps([doc.get("input_hash"), doc.get("label_hash"), group, PHOTO_RANK.prompt_hash, cfg["appeal"], cfg["pick"], CHOSEN],
                     sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def score_place(client, model: str, sem: asyncio.Semaphore, city: str, d: Path, doc: dict, group: str | None,
                      cfg: dict, old: dict | None) -> dict:
    photos = [e for e in chosen(doc, group, cfg) if (d / e["file"]).exists()]  # a re-crawl may have replaced a file
    keep = {pid: v for pid, v in ((old or {}).get("photos") or {}).items()
            if (old or {}).get("prompt_hash") == PHOTO_RANK.prompt_hash}
    fresh = [e for e in photos if (keep.get(e["photo_id"]) or {}).get("sha") != e.get("sha")]
    asked = 0
    if len(photos) > 1 and fresh:  # one photo needs no order; the whole set is scored together so scores compare
        place = json.loads((d / "place.json").read_text(encoding="utf-8"))
        images = [await asyncio.to_thread(lambda e=e: shrink((d / e["file"]).read_bytes(), cfg["appeal"]["px"])) for e in photos]
        async with sem:
            answer = await PHOTO_RANK.ask(client, model, images=images, city=city, count=len(photos),
                                          name=place.get("name"), category=place.get("category") or "unknown")
        for i, (b, s) in gate(answer, len(photos)).items():
            e = photos[i - 1]
            keep[e["photo_id"]] = {"beauty": b, "shows_place": s, "sha": e.get("sha")}
        asked = len(photos)
    current = {e["photo_id"] for e in doc.get("photos") or []}
    return {"place_fid": doc.get("place_fid"), "photos": {k: v for k, v in keep.items() if k in current},
            "stats": {"candidates": len(photos), "asked": asked}}


async def run(city: str, limit: int | None = None, shard: tuple[int, int] | None = None) -> dict:
    """Places of the serving file that have scene labels; shard (i, n): every n-th place from i. A failed place keeps
    its old file and gets a line in data/gmaps/photo_appeal_errors.jsonl."""
    name, _ = load_config(city)
    root = data_dir()
    gm = root / "gmaps"
    out = gm / OUT_DIR
    cfg = config()
    serving = json.loads((root / "serving" / "places.json").read_text(encoding="utf-8"))["records"]
    serving = serving[shard[0]::shard[1]] if shard else serving
    serving = serving[:limit] if limit is not None else serving
    client, model = PHOTO_RANK.role.client()
    client = client.with_options(timeout=300, max_retries=0)
    sem = asyncio.Semaphore(cfg["appeal"]["parallel"] or PHOTO_RANK.role.parallel())
    status: collections.Counter = collections.Counter()

    async def one(rec: dict) -> None:
        doc = scenes.load(rec["id"], root)
        if not doc:
            status["unlabelled"] += 1
            return
        group = (rec.get("identity") or {}).get("category_group")
        target = out / f"{safe_name(rec['id'])}.json"
        h = input_hash(doc, group, cfg)
        try:
            old = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = None
        if old and old.get("input_hash") == h:
            status["cached"] += 1
            return
        try:
            res = await score_place(client, model, sem, name, gm / "places" / safe_name(rec["id"]), doc, group, cfg, old)
        except Exception as e:
            append_jsonl(gm / "photo_appeal_errors.jsonl", {"at": now(), "place": rec["id"], "error": f"{type(e).__name__}: {e}"[:300]})
            status["failed"] += 1
            return
        write_json(target, {**res, "input_hash": h, "prompt_hash": PHOTO_RANK.prompt_hash, "model": model, "built_at": now()})
        status["done"] += 1
        if sum(status.values()) % 100 == 0:
            print(f"gmaps photo_appeal {city}: {dict(status)} of {len(serving)}", flush=True)

    await asyncio.gather(*(one(r) for r in serving))
    summary = {"at": now(), "places": len(serving), "status": dict(status)}
    print(f"gmaps photo_appeal {city}: {json.dumps(summary, ensure_ascii=False)}")
    return summary
