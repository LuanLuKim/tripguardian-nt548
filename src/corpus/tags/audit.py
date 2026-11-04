"""Reproducible membership quality audit, tree and self-contained owner review."""
from __future__ import annotations

import base64
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import vocab
from .group import Fixed, split
from .membership import decisions, decision_path, using_reviewer


def metrics(gold: list[dict], predicted: dict[tuple[str, str], bool]) -> dict:
    """Precision/recall of yes membership; no/unclear remain separate labels in gold."""
    by_tag = defaultdict(Counter)
    for row in gold:
        actual = row["gold"] == "yes"
        yes = predicted.get((row["place_id"], row["tag"]), False)
        c = by_tag[row["tag"]]
        c["pairs"] += 1
        c["true"] += actual
        c["predicted_yes"] += yes
        c["tp"] += actual and yes
        c["fp"] += not actual and yes
        c["fn"] += actual and not yes
    def output(c):
        return {**{k: c[k] for k in ("pairs", "true", "predicted_yes", "tp", "fp", "fn")}, "precision": c["tp"] / c["predicted_yes"] if c["predicted_yes"] else None,
                "recall": c["tp"] / c["true"] if c["true"] else None}
    total = sum(by_tag.values(), Counter())
    return {"tags": {k: output(v) for k, v in sorted(by_tag.items())}, "total": output(total)}


def quality_gates(score: dict, active_tags=()) -> dict:
    """Report the owner's fixed targets; absent measurements are never a successful certification."""
    refs = sorted(set(score["tags"]) | set(active_tags))
    unmeasured = [ref for ref in refs if score["tags"].get(ref, {}).get("precision") is None]
    low_precision = [ref for ref in refs if (score["tags"].get(ref, {}).get("precision") is not None
                                           and score["tags"][ref]["precision"] < .9)]
    low_recall = [ref for ref in refs if (score["tags"].get(ref, {}).get("recall") is not None
                                        and score["tags"][ref]["recall"] < .6)]
    overall = score["total"]["precision"]
    return {"targets": {"precision_per_tag": .9, "precision_total": .93, "recall_per_tag": .6},
            "passed": overall is not None and overall >= .93 and not (unmeasured or low_precision or low_recall),
            "unmeasured_precision": unmeasured, "low_precision": low_precision, "low_recall": low_recall}


@vocab.pending_vocabulary()
def run_audit(inputs: Path, gold: Path, output: Path, root: Path, *, subset="holdout", reviewer="primary") -> dict:
    with using_reviewer(reviewer):
        return _run_audit(inputs, gold, output, root, subset=subset, reviewer=reviewer)


def _run_audit(inputs: Path, gold: Path, output: Path, root: Path, *, subset: str, reviewer: str) -> dict:
    rows = [json.loads(line) for line in inputs.read_text().splitlines() if line.strip()]
    labels = [json.loads(line) for line in gold.read_text().splitlines() if line.strip()]
    labels = [r for r in labels if r.get("split") == subset]
    placed = {r["place_id"]: vocab.of_record(r["record"], r.get("styles", ()), root=root) for r in rows}
    predicted = {}
    for label in labels:
        p = placed.get(label["place_id"])
        resolved = vocab.resolve_ref(label["tag"])
        predicted[(label["place_id"], label["tag"])] = bool(p and resolved and p.carries(*resolved))
    result = metrics(labels, predicted)
    result["scope"] = "old-membership stratified candidates; not city-wide recall; style not measured without image gold"
    result["subset"] = subset
    result["reviewer"] = reviewer
    result["failures"] = [r for r in labels if predicted.get((r["place_id"], r["tag"])) and r["gold"] != "yes"]
    groups = defaultdict(list)
    for r in rows:
        p = placed[r["place_id"]]
        for axis in vocab.AXES:
            for key in sorted(p.keys(axis)):
                groups[vocab.ref(axis, key)].append(r)
    result["counts"] = {tag: len(rs) for tag, rs in sorted(groups.items())}
    result["quality_gate"] = quality_gates(result, groups)
    result["over_20_percent"] = {tag: len(rs) for tag, rs in groups.items() if len(rs) > .2 * len(rows)}
    result["tag_count"] = len(groups)
    result["subtag_count"] = 0
    result["tree"] = {}
    tree, page = [], ['<!doctype html><html lang="vi"><meta charset="utf-8"><title>Duyệt gu Đà Lạt</title>',
        '<style>body{font:16px system-ui;max-width:1200px;margin:auto;padding:24px}section{border-top:1px solid #bbb;padding:20px 0}'
        '.cards{display:flex;gap:16px;flex-wrap:wrap}article{width:340px;background:#f5f5f5;padding:12px}img{width:100%;height:210px;object-fit:cover}'
        'blockquote{margin:8px 0;white-space:pre-wrap}small{overflow-wrap:anywhere}</style><h1>Gu của chuyến — duyệt bằng chứng</h1>',
        '<p>Ảnh và câu gốc được nhúng vào file, không cần server. Thiếu ảnh/bằng chứng được ghi rõ; không coi là đã kiểm.</p>']
    by_id = {r["place_id"]: r for r in rows}
    try:
        saved = json.loads(decision_path(root).read_text()).get("places", {})
    except (OSError, ValueError):
        saved = {}
    for tag, rs in sorted(groups.items()):
        axis, key = tag.split(":", 1)
        name = vocab.label(axis, key)
        tree.append(f'{tag} | {name} | {len(rs)} nơi')
        fixed = Fixed(groups=frozenset([key])) if axis == "category" else Fixed(features=frozenset([key])) if axis == "experience" else Fixed(styles=frozenset([key])) if axis == "style" else Fixed(dish=vocab.dish_kinds()[key]["phrases"][0])
        divided = split([placed[r["place_id"]] for r in rs], fixed)
        result["tree"][tag] = {"label": name, "place_ids": [r["place_id"] for r in rs],
            "subtags": [{"ref": s.id, "label": s.label, "count": s.count, "place_ids": list(s.place_ids)}
                        for s in divided.subtags] if divided else []}
        blocks = [(s.label, [by_id[pid] for pid in s.place_ids]) for s in divided.subtags] if divided else [(name, rs)]
        result["subtag_count"] += len(divided.subtags) if divided else 0
        page.append(f'<section><h2>{html.escape(name)} — {len(rs)} nơi</h2>')
        for subname, subs in blocks:
            tree.append(f'  {subname}: ' + ' | '.join(r['name'] for r in subs[:6]))
            page.append(f'<h3>{html.escape(subname)}</h3><div class="cards">')
            for r in subs[:3]:
                ev = decisions(r["record"], r.get("styles", ()), root)
                # Use saved verbatim evidence, never synthesize a supporting quotation.
                feature = vocab.config()["features"].get(key, {}).get("source", key).partition("=")[0]
                quotes = [e["quote"] for e in r.get("features", {}).get(feature, ())] if axis == "experience" else []
                if axis == "dish":
                    from ..serving import dishes
                    phrases = vocab.dish_kinds()[key]["phrases"]
                    quotes = [e.get("quote") or e.get("dish", "") for e, texts in dishes.rows_of(r["record"])
                              if any(dishes.has_phrase(dishes.keep(t), dishes.keep(p)) for t in texts for p in phrases)]
                judged_quote = saved.get(r["place_id"], {}).get(tag, {}).get("quote") if tag in ev else None
                if judged_quote:
                    quotes = [judged_quote, *[q for q in quotes if q != judged_quote]]
                elif axis == "category":
                    quotes = [r.get("name", ""), r.get("category", "")]
                image_evidence = saved.get(r["place_id"], {}).get(tag, {}).get("evidence", ()) if axis == "style" and tag in ev else ()
                img = _photo(r, root, tag=tag, evidence=image_evidence, quote=judged_quote)
                page.append(f'<article><h4>{html.escape(r["name"])}</h4>{img}<small>{html.escape(r["place_id"])}</small>'
                            f'<p>Judge: {html.escape(ev.get(tag, "chưa chấm — fallback"))}</p>'
                            + ''.join(f'<blockquote>{html.escape(q)}</blockquote>' for q in quotes[:3])
                            + ('<p>Chưa đọc được câu gốc.</p>' if not quotes else '') + '</article>')
            page.append('</div>')
        page.append('</section>')
    output.mkdir(parents=True, exist_ok=True)
    (output / f"metrics-{subset}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    (output / "tree-after.txt").write_text('\n'.join(tree))
    (output / "review.html").write_text('\n'.join(page) + '</html>')
    print(json.dumps({"total": result["total"], "tags": result["tags"], "quality_gate": result["quality_gate"], "tag_count": result["tag_count"],
                      "subtag_count": result["subtag_count"], "over_20_percent": result["over_20_percent"]}, ensure_ascii=False))
    return result


def _photo(row, root, *, tag="", evidence=(), quote=None):
    ident = row["place_id"].replace(":", "_")
    folder = root / "gmaps" / "places" / ident
    try:
        if tag.startswith("style:"):
            items = sorted(evidence, key=lambda e: e.get("quote") != quote)
            paths = [root / e["file"] for e in items if e.get("file")
                     and not Path(e["file"]).is_absolute() and ".." not in Path(e["file"]).parts]
            alt = f"Ảnh bằng chứng {tag}"
        else:
            doc = json.loads((folder / "photos.json").read_text())
            items = doc if isinstance(doc, list) else doc.get("photos", [])
            paths = [folder / item.get("file", "") for item in items]
            alt = "Ảnh gốc địa điểm — chưa xác nhận đúng tag"
        for path in paths:
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                from PIL import Image
                from io import BytesIO
                image = Image.open(path).convert("RGB")
                image.thumbnail((500, 340))
                out = BytesIO()
                image.save(out, format="JPEG", quality=72)
                return f'<img alt="{html.escape(alt)}" src="data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode() + '">'
    except (OSError, ValueError, TypeError):
        pass
    return '<p>Chưa có ảnh đọc được.</p>'
