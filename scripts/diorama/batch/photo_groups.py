"""Mis-attributed Maps photos, second try: one vision call sees ALL exterior/view photos of a place (numbered, small)
and groups them by physical place, then says which group is the named place. Photos outside that group are suspects.
Usage: python photo_groups.py [--terra] <fid_dir> [...]  -> batch/groups/<fid>.json"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA, REPO

import asyncio, base64, io, json, sys
ROOT = REPO
sys.path.insert(0, str(ROOT / "src"))
from PIL import Image  # noqa: E402
D = DATA / "batch"
TERRA = "--terra" in sys.argv
PROMPT = """These {n} photos (numbered 1-{n} in order) were posted on the Google Maps page of "{name}" ({category}) in
Da Lat, Vietnam. Some photos on such pages actually show a DIFFERENT place nearby or with a similar name.
1. Group the photos by the physical place they show (same buildings, gates, statues, decoration, grounds; different
   parts or angles of one site belong to one group). Places of the same kind (two pagodas) are different groups.
2. Say which group is "{name}": use signs with its name, and otherwise the group most photos belong to.
Answer with exactly one JSON object: {{"groups": [{{"photos": [numbers], "what": "short description"}}],
"place_group": index into groups (0-based), "why": "short reason"}}"""

def small(p, side=384):
    im = Image.open(p).convert("RGB"); im.thumbnail((side, side)); b = io.BytesIO(); im.save(b, "JPEG", quality=80)
    return b.getvalue()

async def run(fid):
    place = json.loads((ROOT / "data/gmaps/places" / fid / "place.json").read_text())
    photos = [p for p in json.loads((ROOT / "data/gmaps/photo_scenes" / f"{fid}.json").read_text())["photos"]
              if p.get("scene") in ("exterior", "view")]
    text = PROMPT.format(n=len(photos), name=place["name"], category=place.get("category") or "")
    content = [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," +
               base64.b64encode(small(ROOT / "data/gmaps/places" / fid / p["file"])).decode()}} for p in photos]
    if TERRA:
        from dotenv import dotenv_values
        from openai import AsyncOpenAI
        env = dotenv_values(ROOT / ".env")
        client = AsyncOpenAI(base_url=env["9ROUTER_API_URL"], api_key=env["9ROUTER_API_KEY"],
                             default_headers={"User-Agent": "curl/8.5.0"}, timeout=300)
        model = "cx/gpt-6.1-terra"
    else:
        from corpus.llm.roles import EXTRACTOR
        client, model = EXTRACTOR.client()
    r = await client.chat.completions.create(model=model, messages=[{"role": "user", "content": content}], max_tokens=1500)
    t = r.choices[0].message.content
    ans = json.loads(t[t.find("{"):t.rfind("}") + 1])
    keep = set(ans["groups"][ans["place_group"]]["photos"])
    doc = {"fid": fid, "model": model, "answer": ans, "ids": [p["photo_id"] for p in photos],
           "suspects": [p["photo_id"] for i, p in enumerate(photos, 1) if i not in keep]}
    (D / "groups").mkdir(exist_ok=True)
    (D / "groups" / f"{fid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    return doc

if __name__ == "__main__":
    for fid in [a for a in sys.argv[1:] if not a.startswith("--")]:
        d = asyncio.run(run(fid))
        for i, g in enumerate(d["answer"]["groups"]):
            print(i, g["what"][:90], [d["ids"][k - 1][:12] for k in g["photos"]])
        print("place_group", d["answer"]["place_group"], d["answer"]["why"][:150]); print("suspects", [s[:12] for s in d["suspects"]])
