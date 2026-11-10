"""I/O boundaries; each public step takes one Place and returns a bool."""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from dataclasses import asdict
from pathlib import Path

from paths import CODE, DATA, REPO
from . import config, prompts
from .state import Place
from .gate import check_fid, check_place
from .builder import AgentBuilder, FunctionBuilder, ask, ask_validated
from .site import fit_site

PY = str(REPO / ".venv/bin/python")
NODE = "/home/vannk/node/bin/node"


def run(command: list[str], timeout: int | None = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=DATA, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "DIORAMA_DATA": str(DATA),
                               "PATH": f"/home/vannk/node/bin:{os.environ.get('PATH', '')}"})


def pre_gate(place: Place) -> bool:
    result = check_fid(place.s.get("fid"))
    place.s["gate"] = asdict(result)
    place.log("pre_gate", **asdict(result))
    return result.ok


def prep(place: Place) -> bool:
    result = run([PY, str(CODE / "batch/prep_place.py"), place.slug, place.s["fid"]], timeout=900)
    ok = result.returncode == 0 and all((place.dir / f).exists() for f in ("contact.jpg", "photos_index.json", "meta.json"))
    place.log("prep", result=(result.stdout + result.stderr)[-800:])
    return ok


def gate(place: Place) -> bool:
    result = check_place(place.slug, place.s.get("notes", {}).get("drop_photos", []))
    place.s["gate"] = asdict(result)
    place.log("gate", **asdict(result))
    return result.ok


def _validate_notes(value: dict, available: set[str]) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("skip"), bool):
        raise ValueError("NOTES needs skip and a JSON object")
    if value["skip"]:
        if not isinstance(value.get("skip_reason"), str) or not value["skip_reason"]:
            raise ValueError("Skipped NOTES needs a reason")
        return
    required = {"kit", "kit_why", "kit_gap", "evidence", "drop_photos", "signature", "layout", "entrance",
                "interior", "interior_photos", "stops"}
    if not required <= value.keys():
        raise ValueError(f"Missing NOTES fields: {sorted(required - value.keys())}")
    prompts.catalogue(value["kit"])
    extras = value.get("extra_kits", [])
    if (not isinstance(extras, list) or len(extras) > 2 or any(not isinstance(x, str) for x in extras)
            or len(set(extras)) != len(extras) or value["kit"] in extras):
        raise ValueError("NOTES extra_kits must contain 0-2 distinct kits other than the primary kit")
    for kit in extras:
        try:
            prompts.catalogue(kit)
        except (ValueError, OSError) as error:
            raise ValueError(f"Unknown NOTES extra kit: {kit}") from error
    for name in ("evidence", "drop_photos", "signature", "kit_gap", "interior_photos", "stops"):
        if not isinstance(value[name], list):
            raise ValueError(f"NOTES {name} must be a list")
    if not 3 <= len(value["signature"]) <= 8 or not 1 <= len(value["evidence"]) <= 8:
        raise ValueError("NOTES needs 3-8 signature items and 1-8 evidence photos")
    for name in ("kit_why", "layout", "entrance"):
        if not isinstance(value[name], str):
            raise ValueError(f"NOTES {name} must be text")
    if not isinstance(value["interior"], bool) or any(not isinstance(x, str) for x in value["stops"]):
        raise ValueError("Invalid NOTES interior/stops")
    ids = set()
    photo_groups = [value[k] for k in ("evidence", "drop_photos", "interior_photos")]
    for item in value["signature"]:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]
                or item["id"] in ids or item["id"] in ("x1", "x2", "x3") or not isinstance(item.get("what"), str)
                or not isinstance(item.get("must"), bool) or not isinstance(item.get("photos"), list) or not item["photos"]):
            raise ValueError("Invalid or duplicate NOTES signature")
        ids.add(item["id"])
        photo_groups.append(item["photos"])
    for gap in value["kit_gap"]:
        if (not isinstance(gap, dict) or not isinstance(gap.get("what"), str)
                or not isinstance(gap.get("blocks_recognition"), bool)
                or not isinstance(gap.get("signature_ids"), list)
                or any(not isinstance(x, str) or x not in ids for x in gap["signature_ids"])):
            raise ValueError("kit_gap needs {what, signature_ids, blocks_recognition: bool} with known signature ids")
    for group in photo_groups:
        if any(prompts.photo_name(name) not in available for name in group):
            raise ValueError("NOTES references an unavailable evidence photo")
    dropped = {prompts.photo_name(x) for x in value["drop_photos"]}
    used = [value["evidence"], value["interior_photos"]] + [x["photos"] for x in value["signature"]]
    if any(prompts.photo_name(x) in dropped for group in used for x in group):
        raise ValueError("NOTES uses dropped photos as evidence")


def notes(place: Place) -> bool:
    index = json.loads((place.dir / "photos_index.json").read_text())
    usable = [p for p in index if p.get("keep", True) and not p.get("stale")]
    selected = [p["name"] for p in usable if p["scene"] in ("exterior", "view")][:12]
    prompt = prompts.NOTES.format(name=place.s["name"], kits=prompts.kits_summary(), photos=", ".join(selected),
                                 extra_kits=json.dumps(place.s.get("extra_kits_forced", [])),
                                 hint=place.s.get("kit_forced") or place.s.get("kit_hint") or "none")

    def validate(output):
        _validate_notes(output, {p["name"] for p in usable})
        if not output["skip"]:
            if place.s.get("kit_forced") and output["kit"] != place.s["kit_forced"]:
                raise ValueError("NOTES did not evaluate the forced kit")
            if not set(place.s.get("extra_kits_forced", [])) <= set(output.get("extra_kits", [])):
                raise ValueError("NOTES did not include the forced extra kits")
            scenes = {p["name"]: p["scene"] for p in usable}
            if any(scenes[prompts.photo_name(x)] not in ("exterior", "view") for x in output["evidence"]):
                raise ValueError("NOTES evidence must be exterior/view")
            if output["interior"] and (len(set(output["interior_photos"])) < 4 or any(
                scenes[prompts.photo_name(x)] not in ("interior", "room") for x in output["interior_photos"]
            )):
                raise ValueError("NOTES interior needs at least four interior photos")
        return output

    output, tokens, errors = ask_validated(
        ask, prompt, [place.dir / "contact.jpg", *(place.dir / "photos" / x for x in selected)],
        config()["effort"]["notes"], validate,
    )
    if output is None:
        place.log("notes", tokens=tokens, result="; ".join(errors))
        return False
    place.s["notes"] = output
    (place.dir / "NOTES_coord.md").write_text("# Ghi chú bằng chứng\n\n```json\n" + json.dumps(output, ensure_ascii=False, indent=2) + "\n```\n")
    place.log("notes", tokens=tokens, result="ok", rejected=errors)
    return True


def build(place: Place) -> bool:
    name = place.s.get("builder") or config()["builder"]
    builder = {"agent": AgentBuilder, "function": FunctionBuilder}[name]()
    file = place.dir / "place.json"
    try:
        before = json.loads(file.read_text()) if file.exists() else {}
    except ValueError:
        before = {}
    result = builder.build(place, place.s.get("feedback"))
    changes = []
    if result.ok:
        try:
            after = json.loads(file.read_text())
            old = {o["id"]: o for o in before.get("objects", [])}
            new = {o["id"]: o for o in after.get("objects", [])}
            changes += [f"Added {ident} ({obj.get('type')})" for ident, obj in new.items() if ident not in old]
            changes += [f"Removed {ident}" for ident in old if ident not in new]
            for ident in old.keys() & new.keys():
                fields = {k: v for k, v in new[ident].items() if old[ident].get(k) != v}
                if fields:
                    changes.append(f"Updated {ident}: {json.dumps(fields, ensure_ascii=False)}")
            changes += [f"Changed {k}" for k in after if k != "objects" and before.get(k) != after[k]]
        except (ValueError, TypeError, KeyError) as error:
            result.ok = False
            result.log += f" Invalid place JSON: {error}"
    place.log("build", tokens=result.tokens, round=place.s["rounds"], changes="; ".join(changes)[:1600],
              result=result.log, ok=result.ok)
    if not result.ok:
        place.s["feedback"] = result.log[-1600:]
        place.save()
    return result.ok


def normalize(place: Place) -> bool:
    file = place.dir / "place.json"
    value = json.loads(file.read_text())
    seen = set()
    objects = []
    for obj in value.get("objects", []):
        if obj.get("id") not in seen:
            seen.add(obj.get("id"))
            objects.append(obj)
    value["objects"] = objects
    dropped = {prompts.photo_name(x) for x in place.s["notes"].get("drop_photos", [])}
    for hotspot in value.get("hotspots", []):
        hotspot["photos"] = list(dict.fromkeys(prompts.photo_name(x) for x in hotspot.get("photos", [])))
        if any(x in dropped or not (place.dir / "photos" / x).exists() for x in hotspot["photos"]):
            place.s["feedback"] = f"Stop {hotspot.get('id')} uses dropped or missing photos"
            place.log("normalize", result=place.s["feedback"])
            return False
    value, site_report = fit_site(value)
    file.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    try:
        result = run([NODE, str(CODE / "batch/route_fix.mjs"), place.slug], timeout=300)
    except subprocess.TimeoutExpired:
        # large sites make the 0.25 m raster + A* slow; the route stays as written and boot checks it
        place.log("normalize", result="route_fix timed out after 300 s; route left as written", site_fit=site_report)
        return True
    place.log("normalize", result=(result.stdout + result.stderr)[-1500:], site_fit=site_report)
    if result.returncode:
        place.s["feedback"] = "Route normalization failed: " + (result.stdout + result.stderr)[-1500:]
    return result.returncode == 0


def boot(place: Place) -> bool:
    value = json.loads((place.dir / "place.json").read_text())
    kits = value.get("kits", [])
    missing = [kit for kit in prompts.kits_for(place.s["notes"]) if not isinstance(kits, list) or kit not in kits]
    if missing:
        place.s["feedback"] = "Boot error; place.json kits is missing required kits: " + ", ".join(missing)
        place.log("boot", result=place.s["feedback"])
        return False
    result = run([NODE, str(CODE / "check_place.mjs"), place.slug], timeout=300)
    ok = result.returncode == 0 and "boot ok" in result.stdout
    if not ok:
        place.s["feedback"] = "Boot error; fix the place JSON: " + (result.stdout + result.stderr)[-1500:]
    place.log("boot", result=(result.stdout + result.stderr)[-1500:])
    return ok


def _console_errors(console: str) -> list[str]:
    return list(dict.fromkeys(
        line.strip() for line in console.splitlines()
        if any(x in line.lower() for x in ("error", "failed", "not ready"))
        and "favicon" not in line.lower() and "404" not in line
    ))[:10]


def _shoot_data_error(place: Place, description: str) -> None:
    place.s["feedback"] = (
        "Render data defects: " + description + "\n"
        "NaN geometry usually means a missing/zero/negative size or a non-numeric coordinate in an "
        "object; check every object's numeric fields against the catalogue"
    )
    place.s["shoot_data_error"] = True
    place.log("shoot", result=place.s["feedback"])


def render(place: Place, *, log_errors: bool = True) -> tuple[Path, list[Path]] | None:
    """Build and bridge-shot a place; return the overview and all raw PNGs."""
    result = run([PY, str(CODE / "build.py"), str(place.dir / "place.json"), str(DATA / f"out_{place.slug}")], timeout=300)
    if result.returncode:
        if log_errors:
            place.log("shoot", result=(result.stdout + result.stderr)[-800:])
        return None
    # Fresh tags avoid stale DONE files without deleting previous render evidence.
    tag = f"a3_{place.slug}_{uuid.uuid4().hex[:10]}"
    result = run([PY, str(CODE / "bridge/shot.py"), tag, "--out", f"out_{place.slug}"], timeout=None)
    source = DATA / "bridge/out" / tag
    pngs = sorted(source.glob("*.png"))
    overview = next((p for p in pngs if "initial" in p.name), None)
    console = (source / "console.txt").read_text() if (source / "console.txt").exists() else ""
    errors = _console_errors(console)
    if (result.returncode and not pngs) or overview is None or (source / "error.txt").exists():
        if log_errors:
            place.log("shoot", result=(result.stdout + result.stderr)[-800:])
        return None
    if errors:
        if log_errors:
            value = json.loads((place.dir / "place.json").read_text())
            ids = [h["id"] for h in value.get("hotspots", [])]
            _shoot_data_error(place, f"Console errors (tour stop ids: {', '.join(ids) or 'none'}):\n" + "\n".join(errors))
        return None
    return overview, pngs


def shoot(place: Place) -> bool:
    from PIL import Image, ImageDraw, ImageOps

    place.s.pop("shoot_data_error", None)
    rendered = render(place)
    if rendered is None:
        return False
    overview, pngs = rendered
    tag = overview.parent.name
    value = json.loads((place.dir / "place.json").read_text())
    defects = []
    for hotspot in value.get("hotspots", []):
        if not any(p.stem.endswith("_hs_" + hotspot["id"]) for p in pngs):
            defects.append(f"Stop {hotspot['id']} has no render")
        evidence = hotspot.get("photos", [])
        if not evidence or any(not (place.dir / "photos" / prompts.photo_name(x)).exists() for x in evidence):
            defects.append(f"Stop {hotspot['id']} has missing evidence photos")
    if not value.get("hotspots"):
        defects.append("No tour stops to review")
    if defects:
        _shoot_data_error(place, "; ".join(defects))
        return False
    pairs = []
    for i, hotspot in enumerate(value.get("hotspots", [])):
        stop_render = next((p for p in pngs if p.stem.endswith("_hs_" + hotspot["id"])), None)
        evidence = hotspot.get("photos", [])
        photo = place.dir / "photos" / prompts.photo_name(evidence[0])
        canvas = Image.new("RGB", (1400, 424), "white")
        with Image.open(stop_render) as image:
            canvas.paste(ImageOps.contain(image.convert("RGB"), (700, 394)), (0, 30))
        with Image.open(photo) as image:
            canvas.paste(ImageOps.contain(image.convert("RGB"), (700, 394)), (700, 30))
        ImageDraw.Draw(canvas).text((8, 8), f"{hotspot['id']} | render LEFT | evidence RIGHT: {photo.name}", fill="black")
        pair = DATA / f"out_{place.slug}" / f"review_{tag}_{i}.jpg"
        canvas.save(pair, quality=92)
        pairs.append(str(pair))
    place.s["review_images"] = [str(overview), *pairs]
    place.s["overview"] = str(overview)
    place.log("shoot", result="ok", overview=str(overview), images=place.s["review_images"])
    return True


def _validate_review(output: dict, signature: list[dict]) -> list[dict]:
    if not isinstance(output, dict) or not isinstance(output.get("items"), list):
        raise ValueError("Review needs an items list")
    items = output["items"]
    required = {x["id"] for x in signature}
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in seen
                or item.get("status") not in ("ok", "weak", "missing", "wrong")
                or not isinstance(item.get("blocking"), bool) or item.get("cause") not in ("data", "kit")
                or not isinstance(item.get("fix"), str)):
            raise ValueError("Invalid checklist item")
        seen.add(item["id"])
    if not required <= seen or not seen <= required | {"x1", "x2", "x3"}:
        raise ValueError("Review must cover exactly every signature plus at most x1..x3")
    return items


def review(place: Place) -> bool:
    signature = place.s["notes"]["signature"]
    # In-flight V1 notes used strings; retain them as evidenced checklist entries.
    if signature and isinstance(signature[0], str):
        signature = [{"id": f"s{i+1}", "what": text, "photos": re.findall(r"g\d+", text), "must": True}
                     for i, text in enumerate(signature)]
        place.s["notes"]["signature"] = signature
    value = json.loads((place.dir / "place.json").read_text())
    kits = value.get("kits") or prompts.kits_for(place.s["notes"])
    prompt = prompts.REVIEW.format(name=place.s["name"], signature=json.dumps(signature, ensure_ascii=False),
                                   catalogue="\n".join(prompts.catalogue(kit) for kit in dict.fromkeys(kits)))
    items, tokens, errors = ask_validated(
        ask, prompt, place.s["review_images"], config()["effort"]["review"],
        lambda output: _validate_review(output, signature),
    )
    if items is None:
        place.log("review", tokens=tokens, result="; ".join(errors))
        return False
    place.s["review"] = {"items": items}
    place.log("review", tokens=tokens, result="ok", rejected=errors)
    return True


def colour(place: Place) -> bool:
    result = run([PY, str(CODE / "batch/colour_by_model.py"), place.slug, "--rounds", "2"], timeout=3600)
    tokens = sum(int(x) for x in re.findall(r"^round .*?(\d+) tokens", result.stdout, re.M))
    place.log("colour", tokens=tokens, result=(result.stdout + result.stderr)[-1200:])
    if result.returncode:
        return False
    final = re.search(r"^final sheet:\s*(.+)$", result.stdout, re.M)
    if final:
        place.s["overview"] = final.group(1).strip()
    result = run([PY, str(CODE / "batch/write_colour_notes.py"), "auto3d", place.slug], timeout=900)
    place.log("colour_notes", result=(result.stdout + result.stderr)[-800:])
    return result.returncode == 0
