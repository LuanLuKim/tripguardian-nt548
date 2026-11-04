"""Read-only release evidence export; independent of gold sampling and membership decisions."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ..releases import resolve
from . import vocab


def export_inputs(root: Path, output: Path) -> dict:
    """Export all served places and original evidence, deterministically, without a model or source writes."""
    import lancedb

    release = resolve(root)
    records = json.loads((release / "serving/places.json").read_text())["records"]
    index = release / "index" / (release / "index/current").read_text().strip()
    styles = json.loads((index / "places.json").read_text())
    evidence = defaultdict(lambda: defaultdict(list))
    spans = lancedb.connect(str(index)).open_table("spans").search().select(
        ["place_id", "quote", "features", "observations", "source"]).limit(1000000).to_list()
    for span in spans:
        for feature in json.loads(span["features"]):
            key, _, value = feature.partition("=")
            item = {"quote": span["quote"], "source": span["source"], "value": value,
                    "observations": json.loads(span["observations"])}
            if item not in evidence[span["place_id"]][key]:
                evidence[span["place_id"]][key].append(item)
    rows = []
    for record in sorted(records, key=lambda r: r["id"]):
        pid, identity = record["id"], record.get("identity") or {}
        style_ids = sorted(styles.get(pid, {}).get("styles", ()))
        visual = defaultdict(list)
        fid = pid.replace(":", "_")
        try:
            observations = json.loads((root / "gmaps/style_observations" / f"{fid}.json").read_text())["observations"]
        except (OSError, ValueError, KeyError):
            observations = []
        for item in observations:
            key, span = item.get("feature"), item.get("span") or {}
            relative = Path(span.get("field") or "")
            photo = Path("gmaps/places") / fid / relative
            if (key not in style_ids or item.get("value") != "present" or relative.is_absolute()
                    or ".." in relative.parts or not (root / photo).is_file()):
                continue
            value = {"file": str(photo), "quote": span.get("quote") or str(photo), "observation_id": item.get("id")}
            targets = [key] + [parent for parent, children in vocab.children("style").items()
                               if key in children and parent in style_ids]
            for target in targets:
                if value not in visual[target]:
                    visual[target].append(value)
        # Bound images per style exactly as the initial independently reviewed input did.
        visual = {key: values[:2] for key, values in sorted(visual.items())}
        features = {key: sorted(values, key=lambda e: json.dumps(e, sort_keys=True, ensure_ascii=False))
                    for key, values in sorted(evidence[pid].items())}
        rows.append({"place_id": pid, "name": identity.get("name", ""), "group": identity.get("category_group"),
                     "category": identity.get("category"), "features": features, "styles": style_ids,
                     "style_evidence": visual, "record": record})
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))
    temp.replace(output)
    return {"places": len(rows), "release": release.name, "index": index.name, "output": str(output)}
