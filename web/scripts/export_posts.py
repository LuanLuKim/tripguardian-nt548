"""Write web/public/data/posts.json: the editorial posts about the places with a 3D model (`python -m corpus intro
posts`, docs/CORPUS.md §Giới thiệu địa điểm), as the Bài viết screen reads them. Signed by TripGuardian; only blocks
that passed the code checks and the Judge are in the corpus file.

Usage (repo root): .venv/bin/python web/scripts/export_posts.py   (rerun after `python -m corpus intro posts`)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "web" / "public" / "data" / "posts.json"
KEEP = ("id", "placeId", "title", "tags", "blocks", "sources", "review_count", "author", "at")


def main(city: str = "dalat") -> None:
    from corpus import data_root
    src = data_root() / city / "intro" / "posts.json"
    posts = json.loads(src.read_text(encoding="utf-8"))["posts"] if src.exists() else []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"posts": [{k: p[k] for k in KEEP if k in p} for p in posts]}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    print(f"{len(posts)} editorial posts -> {OUT}")


if __name__ == "__main__":
    main(*sys.argv[1:])
