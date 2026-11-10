"""Brief for one fix run on a place that already has place.json. Usage:
python batch/make_fix_brief.py <slug> <kit> <tag> <critique.md> <sheet.jpg> [--interior] -> BRIEF_<tag>_place.md
critique.md = the coordinator's 3-4 bullets from the last render (what to fix, with photo numbers)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA

import subprocess

D = DATA


def main(slug, kit, tag, critique, sheet, *flags):
    subprocess.run([sys.executable, str(CODE / "batch/make_place_brief.py"), slug, kit, tag, f"places/{slug}/NOTES_coord.md", *flags],
                   check=True, capture_output=True, cwd=D)
    brief = D / f"BRIEF_{tag}_place.md"
    text = brief.read_text().replace("# Studio model of", (
        f"FIX RUN: `places/{slug}/place.json` exists. The coordinator looked at its render (`{sheet}`, view it first). "
        f"Fix exactly these points, keep the rest:\n{(DATA / critique).read_text().strip()}\n\n# Studio model of"), 1)
    brief.write_text(text.replace("- At most 3 shot rounds.", "- At most 2 shot rounds."))
    print(brief.name)


if __name__ == "__main__":
    main(*sys.argv[1:])
