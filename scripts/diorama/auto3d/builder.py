"""Two data-only builders with a shared per-round result."""

from __future__ import annotations

import copy
import json
import os
import re
import signal
import subprocess
import uuid
import warnings
from dataclasses import dataclass
from typing import Protocol

from paths import CODE, DATA, REPO
from . import config
from .state import Place
from . import prompts


@dataclass
class BuildResult:
    ok: bool
    tokens: int
    log: str


class Builder(Protocol):
    def build(self, place: Place, feedback: str | None) -> BuildResult: ...


def ask(prompt: str, images, effort: str):
    # Import only at the model boundary: status, gates and tests need no keys.
    from batch.ask_model import ask as call

    # Parse after usage is counted, and leave retries to the validation boundary.
    return call(prompt, images, model="sol", effort=effort, want_json=False, retries=0)


def token_count(usage: dict) -> int:
    return int(usage.get("total_tokens") or
               (usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
               + (usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0))


def ask_validated(call, prompt: str, images, effort: str, validate):
    """Retry one rejected answer or model exception, preserving paid token usage."""
    tokens = 0
    errors = []
    for attempt in range(2):
        try:
            output, usage = call(prompt, images, effort)
            tokens += token_count(usage)
            if isinstance(output, str):
                match = re.search(r"\{.*\}|\[.*\]", output, re.S)
                output = json.loads(match.group(0) if match else output)
            return validate(output), tokens, errors
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
            if attempt == 0:
                prompt += f"\nYour previous answer was rejected: {error}. Return valid JSON exactly as specified."
    return None, tokens, errors


def apply_patch(place: dict, patch: dict) -> dict:
    """Return a detached copy; unknown ids are ignored with a warning."""
    if not isinstance(patch, dict):
        raise ValueError("Patch must be an object")
    for field in ("add", "update", "remove", "hotspots", "route", "kits"):
        if field in patch and not isinstance(patch[field], list):
            raise ValueError(f"Patch {field} must be a list")
    if any(not isinstance(ident, str) for ident in patch.get("remove", [])):
        raise ValueError("Removed ids must be strings")
    result = copy.deepcopy(place)
    objects = result.setdefault("objects", [])
    by_id = {obj["id"]: obj for obj in objects}
    for update in patch.get("update", []):
        if not isinstance(update, dict) or not isinstance(update.get("id"), str):
            raise ValueError("Each update needs an id")
        ident = update["id"]
        if ident in by_id:
            by_id[ident].update(copy.deepcopy(update))
        else:
            warnings.warn(f"Unknown update id: {ident}", stacklevel=2)
    removed = set(patch.get("remove", []))
    for ident in removed - by_id.keys():
        warnings.warn(f"Unknown remove id: {ident}", stacklevel=2)
    result["objects"] = [obj for obj in objects if obj["id"] not in removed]
    for obj in patch.get("add", []):
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str):
            raise ValueError("Each added object needs an id")
        result["objects"].append(copy.deepcopy(obj))
    for field in ("hotspots", "route", "kits"):
        if field in patch:
            result[field] = copy.deepcopy(patch[field])
    return result


def build_effort(place: Place) -> str:
    large = (len(prompts.kits_for(place.s["notes"])) > 1 or place.s["notes"].get("interior")
             or len(prompts.example(place.s["notes"]["kit"]).get("objects", [])) >= 40)
    return config()["effort"]["build_large" if large else "build"]


def build_brief(place: Place, feedback: str | None = None) -> str:
    kit = place.s["notes"]["kit"]
    interior = place.s["notes"].get("interior")
    template = (CODE / "batch/BRIEF_place.template.md").read_text()
    text = template.format(
        code=CODE, data=DATA, repo=REPO, slug=place.slug, kit=kit,
        name=place.s["name"], tag=f"a3_{place.slug}_{place.s['rounds']}_{uuid.uuid4().hex[:8]}", stops="5 to 7",
        catalog="Pasted catalogues (do not open kit source):\n" + prompts.catalogues(place.s["notes"]),
        example="Pasted proven example (structure, not evidence):\n" + json.dumps(prompts.example(kit), ensure_ascii=False),
        interior_read=((CODE / "batch/INTERIOR_RULES.md").read_text() if interior else ""),
        interior_scope=("6. One interior stop last, supported by the interior photos; real ceiling and eye-level camera."
                        if interior else "6. No interior stop."),
        photo_notes=json.dumps(place.s["notes"], ensure_ascii=False), tour_title=f"Một vòng {place.s['name']}",
    )
    text += '\nSet "kits" to exactly ' + json.dumps(prompts.kits_for(place.s["notes"])) + " (primary first).\n"
    text += ("\n## " + prompts.coord_note(place).strip() + "\n") if place.s.get("coord_note") else ""
    return text + "\nFor non-recognition-blocking kit gaps, approximate with the closest object types.\n" + (
        "\n## Failing review items / boot feedback\n" + _feedback(place, feedback) if feedback else "") + (
        "\n## Earlier round changes\n" + prompts.history_summary(place)
        + "\nFull-size evidence photos attached in this order: "
        + ", ".join(p.name for p in prompts.evidence_photos(place)) + "\n"
    )


def _feedback(place: Place, feedback: str | None) -> str:
    failing = [x for x in place.s.get("review", {}).get("items", []) if x.get("status") != "ok"]
    return (feedback or "") + ("\nStill failing checklist items: " + json.dumps(failing, ensure_ascii=False) if failing else "")


class AgentBuilder:
    def build(self, place: Place, feedback: str | None) -> BuildResult:
        brief = place.dir / f"build_{place.s['rounds']}.md"
        log = place.dir / f"build_{place.s['rounds']}.log"
        brief.write_text(build_brief(place, feedback))
        # run() kills its direct child on timeout; record the session id for descendants.
        pid_file = place.dir / f"build_{place.s['rounds']}_{uuid.uuid4().hex}.pid"
        timed_out = False
        try:
            result = subprocess.run(
                ["bash", "-c", 'echo $$ > "$1"; shift; exec "$@"', "auto3d", str(pid_file),
                 str(CODE / "run_agent.sh"), "sol", str(brief), str(log), build_effort(place),
                 *(str(p) for p in prompts.evidence_photos(place))],
                cwd=DATA, env={**os.environ, "DIORAMA_DATA": str(DATA)},
                capture_output=True, text=True, timeout=config()["agent_timeout_s"], start_new_session=True,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            if pid_file.exists():
                try:
                    os.killpg(int(pid_file.read_text().strip()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        finally:
            pid_file.unlink(missing_ok=True)
        output = log.read_text() if log.exists() else ("" if timed_out else result.stderr)
        if timed_out:
            output += "\nagent timeout"
        counts = re.findall(r"tokens used\s*[:=]?\s*([\d,]+)", output, re.I)
        tokens = sum(int(value.replace(",", "")) for value in counts)
        return BuildResult(not timed_out and result.returncode == 0 and (place.dir / "place.json").exists(), tokens, output[-1600:])


class FunctionBuilder:
    def build(self, place: Place, feedback: str | None) -> BuildResult:
        kit = place.s["notes"]["kit"]
        file = place.dir / "place.json"
        photos = prompts.evidence_photos(place)
        fixing = bool(feedback) and file.exists()
        current = None
        if fixing:
            try:
                current = json.loads(file.read_text())
            except ValueError:
                fixing = False
        if fixing:
            prompt = prompts.FIX.format(
                kits=json.dumps(prompts.kits_for(place.s["notes"])),
                current=json.dumps(current, ensure_ascii=False), feedback=_feedback(place, feedback),
                history=prompts.history_summary(place),
                catalogue=prompts.catalogues(place.s["notes"], {o["type"] for o in current["objects"]}),
                photos=", ".join(p.name for p in photos),
            )
            effort = config()["effort"]["fix_function"]
        else:
            context = {}
            for name in ("meta.json", "osm_footprints.json"):
                if (place.dir / name).exists():
                    context[name] = json.loads((place.dir / name).read_text())
            prompt = prompts.BUILD.format(
                kits=json.dumps(prompts.kits_for(place.s["notes"])),
                name=place.s["name"], kit=kit, notes=json.dumps(place.s["notes"], ensure_ascii=False),
                context=json.dumps(context, ensure_ascii=False), catalogue=prompts.catalogues(place.s["notes"]),
                example=json.dumps(prompts.example(kit), ensure_ascii=False),
                interior=((CODE / "batch/INTERIOR_RULES.md").read_text() if place.s["notes"].get("interior") else "No interior stop."),
                photos=", ".join(p.name for p in photos),
            )
            effort = build_effort(place)
            if feedback:
                prompt += "\nEarlier attempt failed: " + feedback

        def validate(out):
            with warnings.catch_warnings(record=True) as reported:
                warnings.simplefilter("always")
                value = apply_patch(current, out) if fixing else out
            if not isinstance(value, dict) or not isinstance(value.get("objects"), list) or not value["objects"]:
                raise ValueError("Builder returned no place objects")
            if any(not isinstance(o, dict) or not isinstance(o.get("id"), str) or not isinstance(o.get("type"), str)
                   for o in value["objects"]):
                raise ValueError("Every object needs a string id and type")
            report = "; ".join(str(w.message) for w in reported)
            return value, (json.dumps(out, ensure_ascii=False)[:1200] if fixing else "Initial place written") + report

        validated, tokens, errors = ask_validated(ask, prompt, photos, effort, validate)
        if validated is None:
            return BuildResult(False, tokens, "; ".join(errors))
        value, report = validated
        file.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        return BuildResult(True, tokens, "; ".join([*errors, report]))
