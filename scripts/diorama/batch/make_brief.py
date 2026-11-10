"""Fill batch/BRIEF_r1.template.md for one place. Usage:
python batch/make_brief.py <slug> <kit> <tag> <notes.md> [kit_file] [kit_note]
-> BRIEF_<tag>_r1.md next to the other briefs. notes.md = the coordinator's photo notes (Markdown bullets)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA, REPO

import json

D = DATA


def main(slug, kit, tag, notes, kit_file=None, kit_note=None):
    meta = json.loads((D / "places" / slug / "meta.json").read_text())
    kit_file = kit_file or f"{kit}.js"
    exists = (CODE / "kits" / kit_file).exists()
    kit_note = kit_note or ("existing kit: extend it with options, keep every place that already uses it unchanged"
                            if exists else "new kit: register its object types via the run-17 registry")
    text = (CODE / "batch" / "BRIEF_r1.template.md").read_text().format(
        code=CODE, data=DATA, repo=REPO,
        name=meta["name"], slug=slug, kit=kit, kit_file=kit_file, kit_note=kit_note, tag=tag,
        photo_notes=(DATA / notes).read_text().strip(), tour_title=f"Một vòng {meta['name']}")
    out = D / f"BRIEF_{tag}_r1.md"
    out.write_text(text)
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:])
