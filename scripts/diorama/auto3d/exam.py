"""Builder exams and review-only calibration against owner-approved places."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import config
from .checklist import verdict
from .state import Place
from . import steps

INPUTS = ("photos", "photos_index.json", "contact.jpg", "meta.json", "osm_footprints.json")


def copy_inputs(source: Path, target: Path) -> None:
    """Create a fresh exam directory containing prepared inputs only."""
    target.mkdir(parents=True, exist_ok=False)
    try:
        for name in INPUTS:
            src = source / name
            if src.is_dir():
                shutil.copytree(src, target / name)
            elif src.is_file():
                shutil.copy2(src, target / name)
    except BaseException:
        shutil.rmtree(target)
        raise


def calibration_result(items: list[dict]) -> dict:
    """Score an approved model and retain actionable non-ok checklist entries."""
    passed, score = verdict(items)
    return {"score": score, "passed": passed,
            "non_ok": [{key: item[key] for key in ("id", "status", "fix")}
                       for item in items if item["status"] != "ok"]}


def run_calibrate(slugs: list[str], keep: bool = False) -> None:
    from . import cli

    # Validate every source and target before any model call or directory creation.
    originals = [Place(slug) for slug in dict.fromkeys(slugs)]
    inputs = []
    for original in originals:
        approved_file = original.dir / "place.json"
        if not approved_file.is_file():
            raise SystemExit(f"{original.slug}: calibration requires an approved place.json")
        approved = json.loads(approved_file.read_text())
        meta_file = original.dir / "meta.json"
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        place = Place(f"x_cal_{original.slug}")
        if place.dir.exists():
            raise SystemExit(f"Calibration target already exists: {place.dir}")
        inputs.append((original, place, approved, meta))

    rows, created = [], []
    try:
        for original, place, approved, meta in inputs:
            row = dict(slug=original.slug, score=None, passed=False, non_ok=[], error=None)
            try:
                copy_inputs(original.dir, place.dir)
                created.append(place.dir)
                shutil.copy2(original.dir / "place.json", place.dir / "place.json")
                kits = approved.get("kits", [])
                place.s.update(fid=meta.get("fid"), name=meta.get("name") or original.s["name"],
                               reviews=meta.get("reviews"), kit_forced=kits[0] if len(kits) == 1 else None)
                # No pipeline, normalization, build, fix or colour pass: the approved JSON is ground truth.
                for name in ("notes", "boot", "shoot", "review"):
                    place.stage(name)
                    if not getattr(steps, name)(place):
                        raise ValueError(f"{name} failed: {place.s.get('feedback') or 'see step history'}")
                    if name == "notes" and place.s["notes"].get("skip"):
                        raise ValueError("NOTES skipped an approved place: " + place.s["notes"].get("skip_reason", ""))
                row.update(calibration_result(place.s["review"]["items"]))
                place.s["review"].update(score=row["score"], passed=row["passed"])
                place.stage("ready" if row["passed"] else "needs_human")
            except Exception as error:
                row["passed"] = False
                row["error"] = f"{type(error).__name__}: {error}"
            row.update(tokens=place.s["tokens"], stage=place.s["stage"])
            rows.append(row)
            score = f"{row['score']:.3f}" if row["score"] is not None else "-"
            print(f"{original.slug}: score={score} pass={row['passed']}")
            for item in row["non_ok"]:
                print(f"  {item['id']} {item['status']}: {item['fix']}")
            if row["error"]:
                print(f"  {row['error']}")

        report = cli.DATA / "batch" / f"calibrate_{datetime.now():%Y%m%d}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
        print(report)
    finally:
        if not keep:
            for directory in created:
                shutil.rmtree(directory)
    if any(not row["passed"] for row in rows):
        raise SystemExit(1)


def exam_metrics(approved: dict, built: dict) -> dict:
    """Compare object populations, largest footprint centroids and tour stops."""
    def largest(value):
        objects = [o for o in value.get("objects", [])
                   if isinstance(o.get("w"), (int, float)) and isinstance(o.get("d"), (int, float))]
        return max(objects, key=lambda o: o["w"] * o["d"], default=None)

    def centroid(obj):
        position = obj.get("position")
        if isinstance(position, list) and len(position) >= 3:
            return position[0], position[2]
        if "x" in obj and "z" in obj:
            return obj["x"], obj["z"]
        return None

    a, b = largest(approved), largest(built)
    ac, bc = centroid(a) if a else None, centroid(b) if b else None
    return {
        "objects_by_type": {
            "approved": dict(Counter(o.get("type", "unknown") for o in approved.get("objects", []))),
            "exam": dict(Counter(o.get("type", "unknown") for o in built.get("objects", []))),
        },
        "centroid_offset_m": math.dist(ac, bc) if ac is not None and bc is not None else None,
        "hotspots": {"approved": len(approved.get("hotspots", [])), "exam": len(built.get("hotspots", []))},
    }


def run_exam(slugs: list[str], builders: list[str], keep: bool = False) -> None:
    from PIL import Image, ImageDraw, ImageOps
    from . import cli

    # Resolve every target before starting anything that spends model quota.
    originals = [Place(slug) for slug in dict.fromkeys(slugs)]
    approved = {}
    for original in originals:
        approved[original.slug] = json.loads((original.dir / "place.json").read_text())
        json.loads((original.dir / "meta.json").read_text())
        for builder in builders:
            target = Place(f"x_{builder}_{original.slug}").dir
            if target.exists():
                raise SystemExit(f"Exam target already exists: {target}")

    rows, created = [], []
    canvas = Image.new("RGB", (2400, 480 * len(originals)), "white")
    for row_index, original in enumerate(originals):
        jobs = []
        meta = json.loads((original.dir / "meta.json").read_text())
        for builder in builders:
            place = Place(f"x_{builder}_{original.slug}")
            copy_inputs(original.dir, place.dir)
            created.append(place.dir)
            place.s.update(fid=meta.get("fid"), name=meta.get("name"), reviews=meta.get("reviews"), builder=builder)
            place.stage("gate")
            jobs.append(place)
        with ThreadPoolExecutor(max_workers=min(len(jobs), config()["parallel"])) as executor:
            list(executor.map(cli.pipeline, jobs))

        # Render final JSONs, including any restored best snapshot; colour may
        # otherwise leave an evidence sheet rather than a single overview.
        images = {}
        for label, place in [("approved", original), *((p.s["builder"], p) for p in jobs)]:
            file = place.dir / "place.json"
            error = None
            try:
                built = json.loads(file.read_text()) if file.exists() else {}
            except (OSError, ValueError) as exc:
                built, error = {}, str(exc)
            rendered = None
            if file.exists() and error is None:
                try:
                    rendered = steps.render(place, log_errors=False)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    error = str(exc)
            images[label] = rendered[0] if rendered else None
            if label == "approved":
                continue
            scores = place.s["scores"]
            score = (max(scores) if place.s["stage"] == "needs_human" else scores[-1]) if scores else None
            rows.append(dict(slug=original.slug, builder=label, **exam_metrics(approved[original.slug], built),
                             checklist_score=score, rounds=place.s["rounds"], tokens=place.s["tokens"],
                             stage=place.s["stage"], render_ok=rendered is not None, error=error))
        for column, label in enumerate(("approved", "agent", "function")):
            x, y = column * 800, row_index * 480
            source = images.get(label)
            if source:
                with Image.open(source) as image:
                    canvas.paste(ImageOps.contain(image.convert("RGB"), (800, 450)), (x, y + 30))
            suffix = "" if source else " | no render" if label in images else " | not selected"
            ImageDraw.Draw(canvas).text((x + 8, y + 8), f"{original.slug} | {label}{suffix}", fill="black")

    date = datetime.now().strftime("%Y%m%d")
    report = cli.DATA / "batch" / f"exam_{date}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    image_file = cli.REPO / "frontend_images" / f"space3d-exam-{date}.jpg"
    image_file.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(image_file, quality=90)
    print(f"{'slug':<18} {'builder':<9} {'objects approved/exam':<28} {'offset m':>9} {'stops A/E':>10} {'score':>6} {'rounds':>6} {'tokens':>9} stage")
    for row in rows:
        counts = row["objects_by_type"]
        types = sorted(counts["approved"].keys() | counts["exam"].keys())
        objects = ", ".join(f"{t}:{counts['approved'].get(t, 0)}/{counts['exam'].get(t, 0)}" for t in types)
        offset = f"{row['centroid_offset_m']:.2f}" if row["centroid_offset_m"] is not None else "-"
        score = f"{row['checklist_score']:.2f}" if row["checklist_score"] is not None else "-"
        stops = f"{row['hotspots']['approved']}/{row['hotspots']['exam']}"
        print(f"{row['slug']:<18} {row['builder']:<9} {objects:<28} {offset:>9} {stops:>10} {score:>6} {row['rounds']:>6} {row['tokens']:>9} {row['stage']}")
    print(report)
    print(image_file)
    if not keep:
        for directory in created:
            shutil.rmtree(directory)
