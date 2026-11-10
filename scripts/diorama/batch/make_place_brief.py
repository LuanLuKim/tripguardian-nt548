"""Fill batch/BRIEF_place.template.md, the data-only run of one place. Usage:
python batch/make_place_brief.py <slug> <kit> <tag> <notes.md> [--interior] -> BRIEF_<tag>_place.md"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA, REPO

import json

D = DATA
PROVEN = {"church": "places/camly/place.json", "villa": "places/dinh3/place.json", "pagoda": "kits/examples/pagoda.place.json"}


def main(slug, kit, tag, notes, *flags):
    meta = json.loads((D / "places" / slug / "meta.json").read_text())
    catalog = CODE / "kits" / "catalog" / f"{kit}.md"
    example = PROVEN.get(kit, f"kits/examples/{kit}.place.json")
    example = (DATA if example.startswith("places/") else CODE) / example
    interior = "--interior" in flags
    text = (CODE / "batch" / "BRIEF_place.template.md").read_text().format(
        code=CODE, data=DATA, repo=REPO,
        name=meta["name"], slug=slug, kit=kit, tag=tag, stops="5 to 7",
        catalog=catalog.read_text() if catalog.exists() else "No catalogue: use the pasted example's object types and options.",
        example=example.read_text(),
        interior_read=(CODE / 'batch/INTERIOR_RULES.md').read_text() if interior else "",
        interior_scope=("6. One interior stop last, built from the interior photos with the kit's interior: real ceiling, altar or counter, eye-level camera; the outdoor stop before it lifts the roof (cutaway)."
                        if interior else "6. No interior this run."),
        photo_notes=(DATA / notes).read_text().strip(), tour_title=f"Một vòng {meta['name']}")
    out = D / f"BRIEF_{tag}_place.md"
    out.write_text(text)
    print(out.name, len(text))


if __name__ == "__main__":
    main(*sys.argv[1:])
