"""Count what Trip could not answer from the data, without writing Place Intelligence (docs/TRIP_UNDERSTANDING.md).

One row per (phrase, kind, city): {phrase, kind, city, topic, subject, count, last_seen}. kind: no_data (a wish with no
data), zero_hits (find_places found nothing; phrase = its criteria as JSON), no_answer (the reply said "chưa có thông
tin"; phrase = the user's message, topic = the tool group), unsourced_place (a place cut from the reply because no tool
returned it; subject = its id). Never a user id, a session id or anything else personal.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..domain.text import squash

LOCK = threading.Lock()


def record(path: Path, phrase: str, kind: str, city: str = "dalat", topic: str | None = None,
           subject: str | None = None) -> None:
    with LOCK:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
        key = (squash(phrase), kind, city)
        row = next((r for r in rows if (squash(r["phrase"]), r.get("kind"), r.get("city", "dalat")) == key), None)
        if row is None:
            row = {"phrase": phrase, "kind": kind, "city": city, "topic": topic, "subject": subject, "count": 0}
            rows.append(row)
        row.setdefault("city", city)
        row["topic"], row["subject"] = topic or row.get("topic"), subject or row.get("subject")
        row.update(count=row["count"] + 1, last_seen=datetime.now(timezone.utc).isoformat())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
