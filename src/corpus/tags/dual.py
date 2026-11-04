"""Compare independent offline Judges without using evaluation labels."""
from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from . import vocab
from .membership import directory
from .offline import _write, candidates, reviewer_directory, reviewer_task
from .prompt import TAG_MEMBERSHIP


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text()).get("places", {})
    except (OSError, ValueError):
        return {}


def fresh_vote(item: dict, candidate: dict, reviewer: str) -> bool:
    return (item.get("verdict") in {"yes", "no", "unclear"}
            and all(item.get(k) == candidate[k] for k in ("evidence_hash", "record_hash", "definition_hash"))
            and item.get("prompt_hash") == TAG_MEMBERSHIP.prompt_hash
            and (reviewer == "primary" or item.get("reviewer_hash") == reviewer_task(reviewer)[2]))


@vocab.pending_vocabulary()
def compare_judges(rows: list[dict], root: Path, output: Path, *, limit: int = 60) -> dict:
    """Persist every disagreement and a deterministic, bounded owner review. Missing is not no."""
    if not 1 <= limit <= 60:
        raise ValueError("owner review limit must be between 1 and 60")
    primary = _read(reviewer_directory(root, "primary") / "current.json")
    secondary = _read(reviewer_directory(root, "secondary") / "current.json")
    consensus, conflicts, frequencies = {}, [], Counter()
    missing = 0
    for row in sorted(rows, key=lambda r: r["place_id"]):
        pid = row["place_id"]
        consensus[pid] = {}
        for c in candidates(row, root=root):
            tag = c["tag"]
            frequencies[tag] += 1
            a, b = primary.get(pid, {}).get(tag, {}), secondary.get(pid, {}).get(tag, {})
            complete = fresh_vote(a, c, "primary") and fresh_vote(b, c, "secondary")
            agree = complete and a["verdict"] == b["verdict"]
            missing += not complete
            consensus[pid][tag] = {**{k: v for k, v in c.items() if k != "evidence"},
                "evidence": c["evidence"] if tag.startswith("style:") else [],
                "prompt_hash": TAG_MEMBERSHIP.prompt_hash,
                "reviewer_hash": reviewer_task("secondary")[2],
                "verdict": a["verdict"] if agree else "unclear", "quote": a.get("quote", "") if agree else "",
                "reason": "independent_judges_agree" if agree else "awaiting_owner_review",
                "judges": {name: {k: v for k, v in vote.items() if k != "evidence"} if fresh_vote(vote, c, name) else {}
                           for name, vote in (("primary", a), ("secondary", b))}}
            if complete and not agree:
                conflicts.append({"place_id": pid, "name": row["name"], "tag": tag,
                                  "primary": a, "secondary": b, "evidence": c["evidence"]})
    # Spread the bounded review across common interests before taking another case of one tag.
    def changes_membership(item):
        return (item["primary"]["verdict"] == "yes") != (item["secondary"]["verdict"] == "yes")

    def home_interest(item):
        axis, key = item["tag"].split(":", 1)
        return axis == "experience" and vocab.config()["features"].get(key, {}).get("home", True)

    ranked = sorted(conflicts, key=lambda x: (-int(home_interest(x)), -frequencies[x["tag"]], x["tag"], x["place_id"]))
    chosen = []
    for change in (True, False):
        pool = [item for item in ranked if changes_membership(item) == change]
        diverse, seen = [], set()
        for item in pool:
            if item["tag"] not in seen:
                diverse.append(item)
                seen.add(item["tag"])
        chosen.extend(diverse)
        chosen.extend(item for item in pool if item not in diverse)
    chosen = chosen[:limit]
    output.mkdir(parents=True, exist_ok=True)
    _write(directory(root) / "consensus.json", {"schema": 2, "policy": "independent_agreement", "places": consensus})
    for name, items in (("disagreements.jsonl", conflicts), ("review-items.jsonl", chosen)):
        (output / name).write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items))
    from .audit import _photo
    by_id = {r["place_id"]: r for r in rows}
    page = ['<!doctype html><html lang="vi"><meta charset="utf-8"><title>Duyệt bất đồng Judge</title>',
            '<style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:24px}section{border-top:1px solid #bbb;padding:20px 0}'
            'img{max-width:400px;max-height:260px}blockquote{white-space:pre-wrap}small{overflow-wrap:anywhere}</style>',
            '<h1>CHƯA ĐẠT — Chủ dự án duyệt bất đồng hai Judge</h1>',
            f'<p>{len(conflicts)} bất đồng, hiển thị {len(chosen)} mục ưu tiên tag thường dùng; {missing} cặp thiếu Judge còn fresh. '
            'Không tự phân xử và không dùng gold để chọn mục. Ảnh là nguồn gốc, chưa mặc nhiên được duyệt làm ảnh bìa.</p>']
    for item in chosen:
        axis, key = item["tag"].split(":", 1)
        page.append(f'<section><h2>{html.escape(vocab.label(axis, key))} — {html.escape(item["name"])}</h2>'
                    f'<small>{html.escape(item["place_id"])} · {html.escape(item["tag"])}</small>')
        page.append(_photo(by_id[item["place_id"]], root, tag=item["tag"], evidence=item["evidence"]))
        for name in ("primary", "secondary"):
            vote = item[name]
            page.append(f'<h3>{name}: {html.escape(vote["verdict"])}</h3><p>{html.escape(vote.get("reason", ""))}</p>'
                        f'<blockquote>{html.escape(vote.get("quote", ""))}</blockquote>')
        page.extend(f'<blockquote>{html.escape(e["quote"])}</blockquote>' for e in item["evidence"][:3])
        page.append('</section>')
    (output / "review.html").write_text("\n".join(page) + '</html>')
    result = {"places": len(rows), "candidates": sum(frequencies.values()), "disagreements": len(conflicts),
              "membership_disagreements": sum(changes_membership(x) for x in conflicts),
              "missing": missing, "review_items": len(chosen), "by_tag": dict(sorted(Counter(x["tag"] for x in conflicts).items()))}
    _write(output / "comparison.json", result)
    return result
