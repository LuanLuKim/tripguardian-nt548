"""The Judge checks a random sample of active profile entries (docs/TRIP_UNDERSTANDING.md §17).

For each entry it reads the statement, the signal and the evidence: do the user's words / acts say it, does it
generalise too far, is it a fact of only one trip. Any verdict but "ok" flags the entry (it drops to weak) and is
written to a JSONL log for a person to review. A failing Judge decides nothing.
"""

import json
import random
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from ..domain.patterns import Entry
from .profile import ProfileStore

VERDICTS = ("ok", "unsupported", "overgeneral", "trip_only")
REASON_MAX = 200


def render(found: list[Entry]) -> str:
    """Numbered entries with their evidence, as the Judge reads them."""
    blocks = []
    for i, e in enumerate(found, 1):
        proof = "\n".join(f"   - {p.date.isoformat()} {p.how}" + (f": “{p.quote}”" if p.quote else " (chosen on a card)")
                          for p in e.evidence)
        blocks.append(f"{i}. [{e.kind}] {e.statement}\n   signal: {e.key}={e.value}\n   evidence:\n{proof}")
    return "\n\n".join(blocks)


def _ask_judge() -> Callable[..., dict]:
    import asyncio
    from corpus.llm import PROFILE_AUDIT
    client, model = PROFILE_AUDIT.role.client()
    return lambda **fields: asyncio.run(PROFILE_AUDIT.ask(client, model, **fields))


def audit(store: ProfileStore, today: date, ask: Callable[..., dict] | None = None, *, n: int, rng: random.Random,
          log_path: Path) -> dict:
    """Read up to n active entries the user has not edited, drawn at random over every stored profile, in one Judge
    call; flag the ones it does not find founded. Returns {"read", "flagged"}."""
    pool = [(uid, e) for uid in store.users() for e in store.entries(uid, today)[1]
            if e.status == "active" and not e.user_edited]
    picked = rng.sample(pool, min(n, len(pool)))
    if not picked:
        return {"read": 0, "flagged": 0}
    ask = ask or _ask_judge()
    try:
        answer = ask(entries=render([e for _, e in picked]))
        verdicts = answer.get("verdicts") or []
    except Exception:  # noqa: BLE001 - a Judge that fails, times out or answers badly decides nothing
        verdicts = []
    flagged = 0
    lines = []
    for v in verdicts:
        if not isinstance(v, dict) or not isinstance(v.get("n"), int) or not 1 <= v["n"] <= len(picked):
            continue
        if v.get("verdict") not in VERDICTS or v["verdict"] == "ok":
            continue
        uid, e = picked[v["n"] - 1]
        if store.flag(uid, e.id, v["verdict"]):
            flagged += 1
            lines.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "user_id": uid,
                          "entry_id": e.id, "key": e.key, "value": e.value, "statement": e.statement,
                          "verdict": v["verdict"], "reason": str(v.get("reason") or "")[:REASON_MAX]})
    if lines:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in lines)
    return {"read": len(picked), "flagged": flagged}
