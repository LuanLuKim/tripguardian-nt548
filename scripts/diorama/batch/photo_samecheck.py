"""Mis-attributed Maps photos: the Extractor (vision) compares each exterior/view photo with 4 anchor photos of the
same place and says whether it shows the same place. Anchors = owner photos first, then the photos with the most
SIFT matches (batch/match/<fid>.json from photo_match.py). Experiment for the 3D batch (DIORAMA_BATCH_HANDOFF §6).

Usage: python photo_samecheck.py [--terra] <fid_dir> [...]   -> batch/samecheck/<fid>.json
--terra: ask cx/gpt-6.1-terra through 9router instead of the Extractor (when the Gemma hosts are down)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA, REPO

import asyncio
import base64
import io
import os
import json

ROOT = REPO
sys.path.insert(0, str(ROOT / "src"))
from PIL import Image  # noqa: E402

from corpus.llm.roles import EXTRACTOR  # noqa: E402
from corpus.llm.tasks import Task  # noqa: E402

D = DATA / "batch"
PARALLEL = 38  # owner 2026-11-04: no other Gemma consumer, use the full LAN budget
TERRA = "--terra" in sys.argv

SAME_PLACE = Task(
    name="same_place_check", role=EXTRACTOR, max_tokens=300,
    schema={"type": "object", "properties": {
        "same": {"type": "string", "enum": ["yes", "no", "unsure"]},
        "reason": {"type": "string"}}, "required": ["same", "reason"], "additionalProperties": False},
    prompt="""Photos 1-4 are reference photos of one place in Da Lat, Vietnam: "{name}" ({category}).
Photo 5 was posted on the same Google Maps page, but some photos on such pages show a different place.
Does photo 5 show the SAME place as photos 1-4 (the same buildings, gate, statues, decoration or grounds, possibly
from another angle or another part of the site)? Answer "no" when photo 5 shows a different building or site, even of
the same kind (another pagoda, another church, another cafe). Answer "unsure" when photo 5 shows nothing that can be
compared (a close-up, the sky, food). Give a short reason naming what matches or differs.""")


def jpeg(path: Path, side: int = 640) -> bytes:
    im = Image.open(path).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue()


async def check(fid: str) -> dict:
    place = json.loads((ROOT / "data/gmaps/places" / fid / "place.json").read_text())
    scenes = json.loads((ROOT / "data/gmaps/photo_scenes" / f"{fid}.json").read_text())["photos"]
    photos = [p for p in scenes if p.get("scene") in ("exterior", "view")]
    match = json.loads((D / "match" / f"{fid}.json").read_text())
    best = match["best_inliers"]
    ranked = sorted(photos, key=lambda p: (not p.get("owner"), -best.get(p["photo_id"], 0)))
    anchors = ranked[:4]
    files = {p["photo_id"]: ROOT / "data/gmaps/places" / fid / p["file"] for p in photos}
    anchor_bytes = [jpeg(files[p["photo_id"]]) for p in anchors]
    if TERRA:
        from dotenv import dotenv_values
        from openai import AsyncOpenAI
        env = dotenv_values(ROOT / ".env")
        client = AsyncOpenAI(base_url=env["9ROUTER_API_URL"], api_key=env["9ROUTER_API_KEY"],
                             default_headers={"User-Agent": "curl/8.5.0"}, timeout=240, max_retries=1)
        model = "cx/gpt-6.1-terra"
    else:
        client, model = EXTRACTOR.client()
        client = client.with_options(timeout=240, max_retries=0)
    sem = asyncio.Semaphore(8 if TERRA else PARALLEL)

    async def ask(images, **fields):
        if not TERRA:
            return await SAME_PLACE.ask(client, model, images=images, **fields)
        text = SAME_PLACE.render(**fields) + ('\n\nAnswer with exactly one JSON object and nothing else, matching: '
                                              + json.dumps(SAME_PLACE.schema))
        content = [{"type": "text", "text": text}] + [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b).decode()}}
            for b in images]
        r = await client.chat.completions.create(model=model, messages=[{"role": "user", "content": content}],
                                                 max_tokens=300)
        t = r.choices[0].message.content
        return json.loads(t[t.find("{"):t.rfind("}") + 1])
    out = {}

    async def one(p):
        if p in anchors:
            out[p["photo_id"]] = {"same": "anchor"}
            return
        async with sem:
            try:
                a = await ask(anchor_bytes + [jpeg(files[p["photo_id"]])],
                              name=place["name"], category=place.get("category") or "")
            except Exception as e:  # noqa: BLE001
                a = {"same": "error", "reason": f"{type(e).__name__}: {e}"[:200]}
        out[p["photo_id"]] = a
    await asyncio.gather(*(one(p) for p in photos))
    doc = {"fid": fid, "model": model, "anchors": [p["photo_id"] for p in anchors], "photos": out}
    (D / "samecheck").mkdir(exist_ok=True)
    (D / "samecheck" / f"{fid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    return doc


if __name__ == "__main__":
    for fid in [a for a in sys.argv[1:] if not a.startswith("--")]:
        d = asyncio.run(check(fid))
        for pid, a in d["photos"].items():
            print(pid[:14], a["same"], a.get("reason", "")[:110])
