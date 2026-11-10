"""review_sheet.py <slug> [tag]: the coordinator's photo check sheet for one place.

Real photos (places/<slug>/contact.jpg) on top; the latest render's overview plus its two orbit shots below
(bridge/out/<tag>/, newest tag naming the slug unless given). Writes batch/review_<yyyymmdd>/cmp_<slug>.jpg and
prints its path and the tag. Judge recognisable overview features (mass, roofs, colour, layout, water, hills);
the checklist score is only a hint.
"""
import datetime
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import DATA

WIDTH = 2280


def latest_tag(slug: str) -> Path:
    out = DATA / "bridge/out"
    tags = [p for p in out.iterdir() if slug in p.name and (p / "00_initial.png").exists()]
    if not tags:
        raise SystemExit(f"no render with 00_initial.png for {slug} under {out}")
    return max(tags, key=lambda p: (p / "00_initial.png").stat().st_mtime)


def fit(image: Image.Image, width: int) -> Image.Image:
    return image.convert("RGB").resize((width, round(image.height * width / image.width)))


def sheet(slug: str, tag: Path) -> Image.Image:
    top = fit(Image.open(DATA / "places" / slug / "contact.jpg"), WIDTH)
    overview = fit(Image.open(tag / "00_initial.png"), WIDTH // 2)
    orbits = [fit(Image.open(p), WIDTH // 4) for p in sorted(tag.glob("0[12]_orbit*.png"))]
    canvas = Image.new("RGB", (WIDTH, top.height + overview.height), "white")
    canvas.paste(top, (0, 0))
    canvas.paste(overview, (0, top.height))
    for i, image in enumerate(orbits):
        canvas.paste(image, (WIDTH // 2 + i * WIDTH // 4, top.height))
    return canvas


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    slug = sys.argv[1]
    tag = DATA / "bridge/out" / sys.argv[2] if len(sys.argv) == 3 else latest_tag(slug)
    target = DATA / "batch" / f"review_{datetime.date.today():%Y%m%d}" / f"cmp_{slug}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet(slug, tag).save(target, quality=85)
    print(target, tag.name)


if __name__ == "__main__":
    main()
