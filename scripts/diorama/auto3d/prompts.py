"""Bounded visual inputs and stateless model prompts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from paths import CODE, DATA

PROVEN = {"church": "camly", "villa": "dinh3"}

NOTES = """Prepare an evidence-only studio diorama of {name}.
Image 1 is the numbered contact sheet for orientation, subsequent images are full-size photos: {photos}.
Pick the kit by its supported object types, never invent an object or place feature.
Available kits (names and object types, not their full catalogues):
{kits}
Kit constraint/hint: {hint}. A forced kit must be used and its gaps reported honestly.
Forced extra kits (must all be included): {extra_kits}.{coord_note}
The primary kit carries the main buildings. Add 0-2 distinct extra kits only when a must
signature feature or the site's large landscape (water, hills, forest, rock, landmark garden
objects) is supported by their types and not by the primary kit. A gap covered by an extra
kit is not a kit gap. When the photos show a lake or large pond, a forested valley or hillside,
or a waterfall as part of the site, add nature (nature_lake, nature_hills, nature_grove,
nature_cascade): garden_water and garden_terrain are only for small formal ponds and beds.
Return ONLY JSON:
{{"skip": false, "skip_reason": "", "kit": "kit name", "extra_kits": [], "kit_why": "",
"kit_gap": [{{"what": "needed feature no object type can show", "signature_ids": ["s1"], "blocks_recognition": false}}],
"evidence": ["gNN"], "drop_photos": ["gNN"],
"signature": [{{"id": "s1", "what": "overview-scale recognisable feature", "photos": ["gNN"], "must": true}}],
"layout": "positions and paths supported by numbered photos", "entrance": "photo evidence",
"interior": false, "interior_photos": ["gNN"], "stops": ["Vietnamese title — subject (gNN)"]}}
Use 3-8 signature items, unique ids. evidence: at most 8 strongest exterior/view photos of this place.
Signature items are features a visitor recognises at OVERVIEW scale: massing and proportions,
roof form and colour, towers/domes, wall colour family, entrance position, layout of
buildings/paths/gardens/water, and large landscape features. Judge only what a kit model can
show (simple shapes, no fine ornament). Do not use ornament, textures, window detail,
furniture, statues or plant species as signature items. must means essential to recognition;
a minor feature such as white posts and chains around a palace lawn must never block the palace.
Choose evidence to cover every must signature item; interior features use interior_photos instead.
drop_photos: neighbours, close-up people, food, events, or other irrelevant photos.
skip only when the place itself is not visible. kit_gap is a list of objects, never strings;
each signature_ids list links the unsupported feature to signature items. blocks_recognition
must be a boolean, true ONLY when without this feature the place would not be recognised at all.
Only a gap with blocks_recognition=true linked to a must signature can require a new kit.
For every other gap, the builder must approximate with the closest object types. No gap means [].
Interior only if at least 4 photos show the same room. Stops in real walking order, entrance first.
"""

REVIEW = """Independently review the studio model of {name}. You did NOT build it.
Image 1 is the overview render; subsequent labelled images pair each tour stop's render (LEFT)
with that stop's real evidence photo (RIGHT). Judge only photo-supported features at the kit's
abstraction level: simple shapes, massing and proportions, roof form and colour, towers/domes,
wall colour family, entrance position, layout of buildings/paths/gardens/water, and large
landscape features. Judge only what a kit model can show (simple shapes, no fine ornament).
Explicitly ignore fine ornament, textures, window detail, glass, mouldings, furniture detail,
figure/statue detail, plant species and trunk/branch shapes. These are not defects.
Available kit object types and controls (all fixes must be achievable with these):
{catalogue}
Signature checklist:
{signature}
Return ONLY JSON: {{"items": [{{"id": "s1", "status": "ok|weak|missing|wrong",
"blocking": false, "cause": "data|kit", "fix": "concrete correction or empty when ok"}}]}}
Exactly one item per signature id. At most 3 additional items x1..x3 for framing, floating or blocking defects.
ok = matches at kit abstraction level. weak = recognisable, but a visitor would notice a
difference in shape, proportion, colour family or position. missing/wrong = the feature is
absent or clearly wrong. Never mark weak for ignored fine detail.
blocking=true ONLY for: the overview's main building, or a stop's OWN subject (its title), cut off or hidden;
floating or sunk objects; a wrong colour family of the main building's EXTERIOR walls or roof (interiors
and secondary buildings are never blocking); or a missing main building. Roofs lifted above a
building at the stop before an interior stop are an intended cutaway, not floating.
Every fix must be achievable with the kit's object types: adjust supported shapes, sizes,
positions, colours or cameras; never request fine detail or a new object type. Empty fix when ok.
Kit limitations are cause=kit; inaccurate data/positions/colours/cameras are cause=data.
Do not decide pass or assign a numeric score; code handles both.
"""

BUILD = """Write ONLY the complete place JSON for {name}, kit {kit}.
Set "kits" to exactly {kits} (primary first).
Use only the supplied object types and visible photo evidence; never invent. Match proportions,
layout, materials and real colours (no grey/khaki substitutes); tight cream plinth and evidenced planting.
Hotspots: 5-7 stops in real walking order, entrance first, short Vietnamese titles and captions <100 chars;
photos are gNN.jpg. Set tourTitle, tourCaption, location, subtitle, kits. Frame subjects without obstruction.
route is legs of [x,z] points, one per consecutive outdoor stop, entirely on real paved ground.
{interior}
Notes: {notes}
For non-recognition-blocking kit gaps, approximate with the closest object types.
Metadata/footprints: {context}
Full catalogue:
{catalogue}
Proven example (structure/conventions only, not evidence of this place):
{example}
Attached full-size photos, in order: {photos}
"""

FIX = """Return ONLY a JSON patch of the current place, fixing the failing checklist/boot feedback.
Keep unrelated work. No invented features. Retain the engine conventions and photo colours.
Schema: {{"add": [object], "update": [{{"id": "existing id", "field": "replacement value"}}],
"remove": ["id"], "hotspots": [hotspot], "route": [leg], "kits": ["kit name"]}}.
Updates shallow-merge fields by id; omit hotspots/route when unchanged.
You may also replace the top-level "kits" list. Set "kits" to exactly {kits} (primary first).
Current place: {current}
Failing items / boot feedback: {feedback}
Earlier changes: {history}
Catalogue sections for types in use:
{catalogue}
Attached full-size evidence photos, in order: {photos}
"""


def catalogue(kit: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", kit):
        raise ValueError("Invalid kit name")
    return (CODE / "kits/catalog" / f"{kit}.md").read_text()


def coord_note(place) -> str:
    """Coordinator review of the last render against the photos; empty when none was given."""
    note = place.s.get("coord_note")
    return ("\nCoordinator review of the previous render (highest priority; it overrides the checklist score):\n"
            + note + "\n") if note else ""


def kits_for(notes: dict) -> list[str]:
    return list(dict.fromkeys([notes["kit"], *notes.get("extra_kits", [])]))


def catalogues(notes: dict, types: set[str] | None = None) -> str:
    sections = []
    for kit in kits_for(notes):
        text = catalogue(kit)
        sections.append(f"## Kit: {kit}\n" + (catalogue_sections(text, types) if types is not None else text))
    return "\n\n".join(sections)


def example(kit: str) -> dict:
    source = DATA / "places" / PROVEN.get(kit, "") / "place.json"
    if kit not in PROVEN or not source.exists():
        source = CODE / "kits/examples" / f"{kit}.place.json"
    return json.loads(source.read_text())


def kits_summary() -> str:
    lines = []
    for file in sorted((CODE / "kits/catalog").glob("*.md")):
        text = file.read_text().splitlines()
        selected = [line for i, line in enumerate(text) if i < 32 or line.startswith("#")
                    or line.startswith("| `") or re.match(r"`[a-z][a-z0-9_]*`\s*[—–-]", line)]
        names = sorted({name for name in re.findall(r"`([a-z][a-z0-9_]+)(?:`|\.)", "\n".join(selected))
                        if name == file.stem or name.startswith(file.stem + "_")
                        or (file.stem == "church" and "_" in name)
                        or name in ("buddhist_altar", "quan_am_gallery")})
        glosses = {}
        for i, line in enumerate(text):
            if not line.startswith("#"):
                continue
            for name in re.findall(r"`([a-z][a-z0-9_]+)`", line):
                paragraph = []
                fence = None
                for following in text[i + 1:]:
                    following = following.strip()
                    if following.startswith(("```", "~~~")):
                        marker = following[:3]
                        fence = None if fence == marker else marker
                        continue
                    if fence:
                        continue
                    if following.startswith("#"):
                        break
                    if not following or following.startswith("|"):
                        if paragraph:
                            break
                        continue
                    paragraph.append(following)
                fallback = re.search(rf"`{re.escape(name)}`\s*[—–-]\s*(.+)", line)
                gloss = " ".join(paragraph) or (fallback.group(1) if fallback else "")
                gloss = " ".join(re.sub(r"[`*]", "", gloss).split())
                if len(gloss) > 110:
                    gloss = gloss[:110].rsplit(" ", 1)[0] + "…"
                if gloss:
                    glosses.setdefault(name, gloss)
        entries = [f"{name} ({glosses[name]})" if name in glosses else name for name in names]
        lines.append(f"- {file.stem}: {', '.join(entries)}")
    return "\n".join(lines)


def catalogue_sections(text: str, types: set[str]) -> str:
    blocks = re.split(r"(?=^#{3,4} )", text, flags=re.M)
    # Some catalogues delimit individual types inside a shared heading.
    blocks = [part for block in blocks for part in re.split(r"(?=^`[a-z][a-z0-9_]*`\s*[—–-])", block, flags=re.M)]
    return "\n".join(block for i, block in enumerate(blocks) if i == 0
                     or re.search(r"(?i)shared|common|convention|quy ước", block.splitlines()[0])
                     or any(re.search(rf"`{re.escape(t)}(?:`|\.)", block) for t in types))


def photo_name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"g\d+(?:\.jpg)?", value):
        raise ValueError(f"Invalid evidence photo: {value}")
    return value if value.endswith(".jpg") else value + ".jpg"


def evidence_photos(place) -> list[Path]:
    notes = place.s["notes"]
    names = list(notes.get("evidence", []))[:8]
    if notes.get("interior"):
        names += notes.get("interior_photos", [])
    excluded = {photo_name(x) for x in notes.get("drop_photos", [])}
    return [place.dir / "photos" / name for name in dict.fromkeys(photo_name(x) for x in names) if name not in excluded]


def history_summary(place) -> str:
    return "\n".join(f"Round {h.get('round', '?')}: {str(h.get('changes') or h.get('result', ''))[:600]}"
                     for h in place.s["history"] if h["step"] == "build")
