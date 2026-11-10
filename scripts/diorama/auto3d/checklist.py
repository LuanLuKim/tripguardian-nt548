"""Deterministic decisions on independent checklist reviews."""

from __future__ import annotations

from . import config


def verdict(items: list[dict]) -> tuple[bool, float]:
    scored = [x for x in items if x.get("id") not in ("x1", "x2", "x3")]
    weights = {"ok": 1.0, "weak": 0.5}
    score = sum(weights.get(x.get("status"), 0.0) for x in scored) / len(scored) if scored else 0.0
    blocked = any(x.get("blocking") for x in items)
    return score >= config()["pass_ok_ratio"] and not blocked, score


def next_action(scores: list[float], max_rounds: int, stall_rounds: int) -> str:
    if len(scores) >= max_rounds:
        return "stop"
    if len(scores) > stall_rounds and all(
        scores[i] <= max(scores[:i]) for i in range(len(scores) - stall_rounds, len(scores))
    ):
        return "stop"
    return "continue"


def kit_blocked(items: list[dict]) -> bool:
    return any(x.get("blocking") and x.get("cause") == "kit"
               and x.get("status") in ("missing", "wrong") for x in items)
