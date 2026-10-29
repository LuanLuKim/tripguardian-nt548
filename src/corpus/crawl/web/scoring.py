"""How much new each web query brought (query_yield.jsonl), summed by group; groups at >= 2x the median are hot and
go first next run (the round budget that doubles for them is P8's)."""

import json
from pathlib import Path
from statistics import median

from ..common.files import now
from .queries import Query


def yield_row(q: Query, h: str, *, results: int, videos_total: int, videos_new: int, docs_new: int, slugs_new: int,
              blocked: list[str], cached: bool) -> dict:
    return {"at": now(), "query": q.text, "hash": h, "group": q.group, "source": q.source, "results": results,
            "videos_total": videos_total, "videos_new": videos_new, "docs_new": docs_new, "slugs_new": slugs_new,
            "new": videos_new + docs_new + slugs_new, "blocked_engines": blocked, "cached": cached}


def group_scores(path: Path) -> dict[str, dict]:
    scores: dict[str, dict] = {}
    if not path.exists():
        return scores
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            group, new = str(row["group"]), int(row["new"])
        except (ValueError, KeyError, TypeError):
            continue
        s = scores.setdefault(group, {"queries": 0, "new": 0})
        s["queries"] += 1
        s["new"] += new
    for s in scores.values():
        s["mean_new"] = s["new"] / s["queries"]
    return scores


def hot_groups(path: Path) -> set[str]:
    scores = group_scores(path)
    if not scores:
        return set()
    cut = 2 * median(s["new"] for s in scores.values())
    return {g for g, s in scores.items() if s["new"] > 0 and s["new"] >= cut}
