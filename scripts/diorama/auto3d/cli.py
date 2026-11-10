"""Resumable orchestration and the batch command line."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Mapping

from paths import DATA, REPO
from . import config, prompts
from .checklist import verdict, next_action
from .state import Place
from . import steps as real_steps

Step = Callable[[Place], bool]
TERMINAL = {"ready", "skip", "needs_kit", "needs_human", "published"}


def terminal(stage: str) -> bool:
    return stage in TERMINAL or stage.startswith("failed:")


def _stop(place: Place) -> None:
    restored = place.s["best_round"] > 0 and place.restore("best")
    if not restored:
        place.restore("boot")
    place.s["reason"] = "round_limit_or_stall"
    place.stage("needs_human")


def _kit_gap(place: Place) -> bool:
    notes = place.s["notes"]
    must = {x["id"] for x in notes.get("signature", []) if isinstance(x, dict) and x.get("must")}
    return any(x.get("blocks_recognition") is True and must.intersection(x["signature_ids"])
               for x in notes.get("kit_gap", []))


def pipeline(place: Place, steps: Mapping[str, Step] | None = None, *, redo: bool = False) -> None:
    """stage always names the NEXT step. Injected steps perform no real I/O."""
    cfg = config()
    actions = steps if steps is not None else {name: getattr(real_steps, name) for name in
               ("pre_gate", "prep", "gate", "notes", "build", "normalize", "boot", "shoot", "review", "colour")}
    if redo:
        place.s.update(notes={}, scores=[], best_round=0, rounds=0, feedback=None, after_notes=False,
                       review={}, review_images=[], reason="", kit_gap=[], overview=None, best_overview=None)
        place.stage("new")
    while not terminal(place.s["stage"]):
        stage = place.s["stage"]
        try:
            if stage == "new":
                if not actions["pre_gate"](place):
                    place.s["reason"] = place.s.get("gate", {}).get("reason", "no_exterior_evidence")
                    place.stage("skip")
                else:
                    place.stage("prep")
            elif stage == "prep":
                place.stage("gate" if actions["prep"](place) else "failed:prep")
            elif stage == "gate":
                if not actions["gate"](place):
                    place.s["reason"] = place.s.get("gate", {}).get("reason", "no_exterior_evidence")
                    place.stage("skip")
                elif place.s.get("after_notes") or place.s["notes"]:
                    if place.s["notes"].get("skip"):
                        place.s["reason"] = place.s["notes"].get("skip_reason", "")
                        place.stage("skip")
                    elif _kit_gap(place):
                        place.s["kit_gap"] = place.s["notes"]["kit_gap"]
                        place.stage("needs_kit")
                    else:
                        place.stage("build")
                else:
                    place.stage("notes")
            elif stage == "notes":
                if not actions["notes"](place):
                    place.stage("failed:notes")
                elif place.s["notes"].get("skip"):
                    place.s["reason"] = place.s["notes"].get("skip_reason", "")
                    place.stage("skip")
                else:
                    place.s["after_notes"] = True
                    place.stage("gate")
            elif stage == "build":
                if place.s["rounds"] >= cfg["max_rounds"]:
                    _stop(place)
                    continue
                place.s["rounds"] += 1
                place.save()
                if actions["build"](place):
                    place.stage("boot")
                else:
                    place.restore("boot")
                    if place.s["rounds"] >= cfg["max_rounds"]:
                        _stop(place)
                    else:
                        place.stage("build")
            elif stage == "boot":
                try:
                    booted = actions["normalize"](place) and actions["boot"](place)
                except (ValueError, KeyError, TypeError) as error:
                    booted = False
                    place.s["feedback"] = f"Invalid place data: {error}"
                    place.log("boot", result=place.s["feedback"])
                if booted:
                    place.snapshot("boot")
                    place.s["feedback"] = None
                    place.stage("shoot")
                else:
                    place.restore("boot")
                    place.s["feedback"] = place.s.get("feedback") or "Viewer failed to boot; repair the data file."
                    if place.s["rounds"] >= cfg["max_rounds"]:
                        _stop(place)
                    else:
                        place.stage("build")
            elif stage == "shoot":
                if actions["shoot"](place):
                    place.stage("review")
                elif place.s.pop("shoot_data_error", False):
                    # The current data already booted; keep it for the builder to repair.
                    if place.s["rounds"] >= cfg["max_rounds"]:
                        _stop(place)
                    else:
                        place.stage("build")
                else:
                    place.stage("failed:shoot")
            elif stage == "review":
                if not actions["review"](place):
                    place.stage("failed:review")
                    continue
                items = place.s["review"]["items"]
                passed, score = verdict(items)
                previous = place.s["scores"]
                if not previous or score > max(previous):
                    place.snapshot("best")
                    place.s["best_round"] = place.s["rounds"] or 1
                    place.s["best_overview"] = place.s.get("overview")
                previous.append(score)
                place.s["review"].update(score=score, passed=passed)
                place.s["review_final"] = place.s["review"]
                if passed:
                    place.stage("colour")
                elif place.s["rounds"] >= cfg["max_rounds"] or next_action(previous, cfg["max_rounds"], cfg["stall_rounds"]) == "stop":
                    _stop(place)
                else:
                    place.s["feedback"] = json.dumps([x for x in items if x["status"] != "ok"], ensure_ascii=False)
                    place.stage("build")
            elif stage == "colour":
                place.stage("ready" if actions["colour"](place) else "failed:colour")
            else:
                raise ValueError(f"Unknown stage: {stage}")
        except Exception as error:
            if stage == "boot":
                place.restore("boot")
            place.log("error", stage=stage, result=f"{type(error).__name__}: {error}")
            place.stage("failed:" + stage)


def slugify(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", folded.lower())[:14]


def _places() -> list[Place]:
    return [Place(file.parent.name) for file in sorted(DATA.glob("places/*/auto3d.json"))]


def _score(place: Place) -> str:
    scores = place.s["scores"]
    if not scores:
        return "-"
    score = max(scores) if place.s["stage"] == "needs_human" else scores[-1]
    return f"{score:.2f}"


def status() -> None:
    places = _places()
    for place in places:
        s = place.s
        stage = s["stage"]
        if s["notes"].get("extra_kits"):
            stage += "  [" + "+".join(prompts.kits_for(s["notes"])) + "]"
        print(f"{place.slug:<16} {stage:<16} tokens {s['tokens']:>8} checklist {_score(place):>4}  {s.get('name') or ''}")
    print("Stages:", dict(Counter(p.s["stage"] for p in places)))
    print("Tokens:", sum(p.s["tokens"] for p in places))


def gallery(out: str | None = None) -> None:
    from PIL import Image, ImageDraw, ImageOps

    tiles = []
    for place in _places():
        if place.s["stage"] != "ready" and not place.s["stage"].startswith("needs_"):
            continue
        source = place.s.get("best_overview") if place.s["stage"] == "needs_human" else place.s.get("overview")
        is_sheet = bool(source and "review_" in str(source))
        if not source:
            for entry in reversed(place.s["history"]):
                if entry.get("sheet"):
                    source = DATA / entry["sheet"]
                    is_sheet = True
                    break
        tile = Image.new("RGB", (960, 570), "white")
        if source and (DATA / source).exists():
            with Image.open(DATA / source) as image:
                if is_sheet:
                    # V1 review sheets begin with a 640x360 overview tile.
                    image = image.crop((0, 0, min(640, image.width), min(360, image.height)))
                tile.paste(ImageOps.contain(image.convert("RGB"), (960, 540)), (0, 30))
        ImageDraw.Draw(tile).text((8, 8), f"{place.slug} | {place.s['stage']} | checklist {_score(place)}", fill="black")
        tiles.append(tile)
    canvas = Image.new("RGB", (960, 570 * max(1, len(tiles))), "white")
    for i, tile in enumerate(tiles):
        canvas.paste(tile, (0, 570 * i))
    target = DATA / out if out else DATA / "batch/auto3d_gallery.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, quality=88)
    print(target, len(tiles))


def publish(slugs: list[str]) -> None:
    places = [Place(slug) for slug in dict.fromkeys(slugs)]
    for place in places:
        if place.s["stage"] != "ready":
            raise SystemExit(f"{place.slug}: publish requires ready, found {place.s['stage']}")
        if not place.s.get("fid"):
            raise SystemExit(f"{place.slug}: missing fid")
    file = REPO / "web/space3d/places.json"
    entries = json.loads(file.read_text())
    existing = {entry["slug"] for entry in entries}
    for place in places:
        if place.slug not in existing:
            entries.append({"slug": place.slug, "id": place.s["fid"].replace("_", ":"), "source": f"places/{place.slug}/place.json"})
    file.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n")
    env = {**os.environ, "DIORAMA_DATA": str(DATA), "PATH": f"/home/vannk/node/bin:{os.environ.get('PATH', '')}"}
    commands = [
        [real_steps.NODE, "web/scripts/build_space3d.mjs"],
        [real_steps.NODE, "web/scripts/shots_space3d.mjs", "http://127.0.0.1:8472", "check", "web/shots/space3d_after", *slugs],
        [real_steps.NODE, "web/scripts/shots_space3d.mjs", "http://127.0.0.1:8472", "poster", "x", *slugs],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        print((result.stdout + result.stderr)[-800:])
        if result.returncode:
            raise SystemExit(f"Publish check failed ({result.returncode}); places remain ready")
    for place in places:
        place.stage("published")


def add(name: str) -> None:
    try:
        from corpus.navigate import enqueue_nominees
    except ImportError as error:
        raise SystemExit("add requires the public corpus.navigate.enqueue_nominees API; it is unavailable in this checkout") from error
    count = enqueue_nominees("dalat", [{"name": name, "area_hint": "", "aspect": "seed"}])
    print(f"Enqueued: {count}")
    for step in ("resolve", "filter", "counts", "list", "crawl", "qc", "photos", "photo_scenes"):
        print(f"python -m corpus gmaps {step} --city dalat")
    print("python -m corpus build --city dalat")


def _job(ident: str, inventory: dict, saved: dict) -> Place:
    if not ident.startswith("0x"):
        return Place(ident)
    fid = ident.replace(":", "_")
    if fid in saved:
        return saved[fid]
    info = inventory.get(fid, {})
    if not info.get("name"):
        raw = REPO / "data/gmaps/places" / fid / "place.json"
        info = json.loads(raw.read_text()) if raw.exists() else {}
    slug = slugify(info["name"]) if info.get("name") else "fid_" + fid.split("_")[-1]
    place = Place(slug)
    if place.s.get("fid") not in (None, fid):
        place = Place(slug + "_" + fid.split("_")[-1])
    place.s.update(fid=fid, name=info.get("name") or fid, reviews=info.get("reviews"),
                   category=info.get("group") or info.get("category"), kit_hint=info.get("kit"))
    return place


def main(argv: list[str] | None = None) -> None:
    cfg = config()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    queue = sub.add_parser("queue")
    queue.add_argument("--tier", default="A,B")
    queue.add_argument("--n", type=int, default=3)
    queue.add_argument("--min-reviews", type=int, default=1000)
    queue.add_argument("--parallel", type=int, default=cfg["parallel"])
    run = sub.add_parser("run")
    run.add_argument("places", nargs="+")
    run.add_argument("--kit")
    run.add_argument("--extra-kit", action="append")
    run.add_argument("--builder", choices=("agent", "function"))
    run.add_argument("--redo", action="store_true")
    run.add_argument("--parallel", type=int, default=cfg["parallel"])
    sub.add_parser("status")
    sub.add_parser("gallery").add_argument("out", nargs="?")
    sub.add_parser("publish").add_argument("slugs", nargs="+")
    sub.add_parser("add").add_argument("name")
    exam = sub.add_parser("exam")
    exam.add_argument("slugs", nargs="+")
    exam.add_argument("--builders", default="agent,function")
    exam.add_argument("--keep", action="store_true")
    calibrate = sub.add_parser("calibrate")
    calibrate.add_argument("slugs", nargs="+")
    calibrate.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)
    command = args.command or "status"
    if command == "status":
        return status()
    if command == "gallery":
        return gallery(args.out)
    if command == "publish":
        return publish(args.slugs)
    if command == "add":
        return add(args.name)
    if command == "calibrate":
        from .exam import run_calibrate

        return run_calibrate(args.slugs, args.keep)
    if command == "exam":
        from .exam import run_exam

        builders = list(dict.fromkeys(args.builders.split(",")))
        if not builders or any(b not in ("agent", "function") for b in builders):
            parser.error("--builders must be a comma-separated list of agent,function")
        return run_exam(args.slugs, builders, args.keep)
    if args.parallel < 1:
        parser.error("--parallel must be positive")
    if command == "run":
        extras = list(dict.fromkeys(args.extra_kit or []))
        if len(extras) > 2 or args.kit in extras:
            parser.error("--extra-kit requires at most two kits distinct from --kit")
        for kit in ([args.kit] if args.kit else []) + extras:
            try:
                prompts.catalogue(kit)
            except (ValueError, OSError) as error:
                parser.error(f"Invalid kit {kit}: {error}")
    saved = {p.s["fid"]: p for p in _places() if p.s.get("fid")}
    if command == "queue":
        from batch.hot_places import rows

        if args.n < 0:
            parser.error("--n must not be negative")
        selected = [r for r in rows(args.min_reviews) if r["tier"] in args.tier.split(",")
                    and (r["fid"] not in saved or not terminal(saved[r["fid"]].s["stage"])
                         or (saved[r["fid"]].s["stage"].startswith("failed:")
                             and saved[r["fid"]].s["retries"] < cfg["retry_failed"]))][:args.n]
        jobs = []
        for row in selected:
            place = _job(row["fid"], {row["fid"]: row}, saved)
            if not terminal(place.s["stage"]) or place.s["stage"].startswith("failed:"):
                jobs.append(place)
    else:
        file = DATA / "batch/inventory.json"
        inventory = {x["fid"]: x for x in json.loads(file.read_text())} if file.exists() else {}
        jobs = [_job(ident, inventory, saved) for ident in args.places]
    jobs = list({p.slug: p for p in jobs}.values())
    active = []
    for place in jobs:
        if getattr(args, "extra_kit", None):
            if (place.s["notes"] or place.s["stage"] not in ("new", "prep", "gate", "notes")) and not args.redo:
                parser.error("Changing extra kits after NOTES requires --redo")
            primary = args.kit or place.s.get("kit_forced")
            if primary in extras:
                parser.error("--extra-kit must differ from the primary kit")
            place.s["extra_kits_forced"] = extras
        if place.s["stage"].startswith("failed:") and not getattr(args, "redo", False):
            failed = place.s["stage"]
            if command == "queue":
                place.s["retries"] += 1
            place.s["stage"] = failed.split(":", 1)[1]
            place.log("resume", **{"from": failed})
        if terminal(place.s["stage"]) and not getattr(args, "redo", False):
            continue
        if getattr(args, "kit", None):
            if place.s["stage"] not in ("new", "prep", "gate", "notes") and not args.redo:
                parser.error("Changing a kit after NOTES requires --redo")
            place.s["kit_forced"] = args.kit
        place.s["builder"] = getattr(args, "builder", None) or place.s["builder"] or cfg["builder"]
        place.save()
        active.append(place)
    with ThreadPoolExecutor(args.parallel) as executor:
        list(executor.map(lambda p: pipeline(p, redo=getattr(args, "redo", False)), active))
    for place in jobs:
        print(f"{place.slug}: {place.s['stage']}, tokens {place.s['tokens']}")
