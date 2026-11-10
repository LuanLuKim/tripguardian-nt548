"""Colour pass of one kit's places: the places get the colours of their photos (owner 2026-11-04), shapes stay.
Usage (from scripts/diorama):
  python3 batch/make_colour_brief.py <kit> <tag> <slug,slug,...> [--regress slug,...] [--extra notes.md] [--fix critique.md]
    -> BRIEF_<tag>_colour.md, stages each place's current render as places/<slug>/checks/colour_before_*.png
       (from web/shots/space3d/<slug>-0/1.png, written by `node web/scripts/shots_space3d.mjs <base> check`),
       prints the run_agent.sh command (sol high for the pass, sol medium for --fix).
--regress: places on the same kit outside this run (default: every other place of web/space3d/places.json on this kit).
--fix: coordinator's critique after looking at the last sheets; makes a short fix run (2 rounds max).
kit "template" = Chùa Linh Sơn, whose builders live in index.template.html: run it alone, never next to other runs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CODE, DATA, REPO

import json
import shutil

D = DATA

WEB = json.loads((REPO / "web/space3d/places.json").read_text())


def place_file(slug):
    return next(w["source"] for w in WEB if w["slug"] == slug)


def kit_of(slug):
    return (json.loads((D / place_file(slug)).read_text()).get("kits") or ["template"])[0]


def name_of(slug):
    return json.loads((D / place_file(slug)).read_text())["name"]


def opt(args, flag):
    return args[args.index(flag) + 1] if flag in args else None


def main(kit, tag, slugs, *args):
    slugs = slugs.split(",")
    regress = opt(args, "--regress")
    regress = regress.split(",") if regress else [w["slug"] for w in WEB if w["slug"] not in slugs and kit_of(w["slug"]) == kit]
    lines, images = [], []
    for s in slugs:
        (D / "places" / s / "checks").mkdir(parents=True, exist_ok=True)
        for i, view in enumerate(["overview", "stop1"]):
            shot = REPO / "web/shots/space3d" / f"{s}-{i}.png"
            if shot.exists():
                shutil.copy(shot, D / "places" / s / "checks" / f"colour_before_{view}.png")
        if s == "linhson":
            contact = "photo-contact.png"
            lines.append(f"- `linhson` ({name_of(s)}): place file `linhson.json`, photos `photos/`, contact `photo-contact.png`, "
                         "renders `places/linhson/checks/`, write `places/linhson/COLOURS.md`; its builders are in `index.template.html`.")
        else:
            contact = f"places/{s}/contact.jpg"
            lines.append(f"- `places/{s}/` ({name_of(s)}), build from `{place_file(s)}`.")
        images.append(str(DATA / contact))
    kit_file = str(CODE / ("index.template.html" if kit == "template" else f"kits/{kit}.js"))
    extra = (DATA / opt(args, "--extra")).read_text().strip() if opt(args, "--extra") else ""
    if kit == "template":
        extra += ("\nThis run alone may edit `index.template.html`: only add optional colour fields to the builders this place uses, "
                  "defaults = today's values. Every other place shares the template: shoot `camly` and `cadasa` before and after.")
        regress = regress + ["camly", "cadasa"]
    if regress:
        reg = (f"Places on the same code outside this run must render the same: {', '.join(f'`{r}`' for r in regress)}. Shoot each BEFORE "
               f"any kit edit (`{tag}base<slug>`) and after (`{tag}after<slug>`), compare with `python3 compare_renders.py` (or your eyes on "
               "both sheets): mean pixel change must stay below 1/255.")
    else:
        reg = "Every place on this kit is in this run; still keep each new field's default equal to today's value."
    text = (CODE / "batch/BRIEF_colour.template.md").read_text().format(
        code=CODE, data=DATA, repo=REPO,
        kit=kit, tag=tag, names=", ".join(name_of(s) for s in slugs), places="\n".join(lines), kit_file=kit_file,
        extra=extra, regress=reg, regress_boot=(" and of " + ", ".join(regress)) if regress else "")
    effort = "high"
    if opt(args, "--fix"):
        effort = "medium"
        sheets = ", ".join(f"`out_{s}/` (latest `sheet_{tag}*.jpg`)" for s in slugs)
        text = text.replace("# Colour pass", (
            f"FIX RUN: the colour pass of these places is done; the coordinator reviewed the last sheets ({sheets}). "
            f"Fix exactly these points, keep everything else:\n{(DATA / opt(args, '--fix')).read_text().strip()}\n\n# Colour pass"), 1)
        text = text.replace("At most 3 full-sheet rounds per place", "At most 2 full-sheet rounds per place")
        tag = tag + "fix"
    brief = D / f"BRIEF_{tag}_colour.md"
    brief.write_text(text)
    log = str(DATA / f"run_{tag}_colour.log")
    print(brief.name)
    print(f"bash {CODE / 'run_agent.sh'} sol {brief} {log} {effort} {' '.join(images)}; echo EXIT=$? >> {log}")


if __name__ == "__main__":
    main(*sys.argv[1:])
