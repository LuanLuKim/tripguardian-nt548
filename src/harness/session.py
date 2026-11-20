"""One atomic snapshot per journey, including module state and request receipts."""

import json
import os
from copy import deepcopy
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .contracts import Journey

SID = re.compile(r"[0-9a-f]{12}")


class Store:
    def __init__(self, root: Path | None):
        self.root = root
        self._mem: dict[str, Journey] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._guard = threading.Lock()
        self.feedback: list[dict] = []

    def new(self) -> Journey:
        return Journey(id=uuid.uuid4().hex[:12])

    def lock(self, jid: str):
        if not SID.fullmatch(jid):
            raise KeyError(jid)
        with self._guard:
            return self._locks.setdefault(jid, threading.RLock())

    def get(self, jid: str) -> Journey:
        return self.read(jid)

    def read(self, jid: str) -> Journey:
        """Detached public snapshot, including request history."""
        with self.lock(jid):
            return deepcopy(self._read(jid))

    def _read(self, jid: str) -> Journey:
        """Borrowed cache entry; only internal callers holding the journey lock may use it."""
        with self.lock(jid):
            if jid not in self._mem:
                path = self.root / f"{jid}.json" if self.root else None
                if not path or not path.exists():
                    raise KeyError(jid)
                session = Journey.model_validate_json(path.read_text(encoding="utf-8"))
                if session.id != jid:
                    raise ValueError("journey file ID mismatch")
                self._mem[jid] = session
            return self._mem[jid]

    def state(self, jid: str) -> Journey:
        """Detached current state for readers that do not need request history."""
        with self.lock(jid):
            session = self._read(jid)
            return deepcopy(session, {id(session.receipts): {}})

    def peek(self, jid: str) -> Journey:
        """Cheap read-only state without request history, for metadata reads and rendering. Top-level maps are
        copied; their values are shared with the cache (a save replaces the cached journey, never edits it), so a
        caller must not mutate nested values. A multi-MB journey's deepcopy costs seconds; this costs microseconds."""
        with self.lock(jid):
            s = self._read(jid)
            return Journey.model_construct(id=s.id, user_id=s.user_id, corpus_binding=s.corpus_binding, stage=s.stage,
                                           revision=s.revision, sessions=dict(s.sessions), outputs=dict(s.outputs),
                                           snapshots=dict(s.snapshots), receipts={})

    def summary_parts(self, ids: list[str]) -> dict[str, dict]:
        """What one line of the trips list reads, per known journey id (unknown ids are left out)."""
        out = {}
        for jid in ids:
            try:
                with self.lock(jid):
                    s = self.peek(jid)
            except KeyError:
                continue
            out[jid] = _parts(s.id, s.stage, s.revision, s.outputs, s.sessions, s.snapshots, self.updated_at(jid))
        return out

    def _working(self, jid: str) -> Journey:
        """Private write view, used only under the journey lock; historical receipts are append-only."""
        session = self._read(jid)
        return deepcopy(session, {id(session.receipts): dict(session.receipts)})

    def _saved_copy(self, session: Journey) -> Journey:
        previous = self._mem.get(session.id)
        receipts = {}
        for key, value in session.receipts.items():
            old = previous.receipts.get(key) if previous else None
            receipts[key] = old if value is old else deepcopy(value)
        return deepcopy(session, {id(session.receipts): receipts})

    def append_feedback(self, record: dict) -> None:
        """Feedback lines live beside the session files (data/harness/feedback.jsonl); memory-only stores keep them."""
        with self._guard:
            if self.root:
                path = self.root.parent / "feedback.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            else:
                self.feedback.append(record)

    def list_for(self, owner: str, limit: int = 50) -> list[str]:
        """Journey IDs of one account, newest first."""
        with self._guard:
            known = dict(self._mem)
        if self.root and self.root.exists():
            files = sorted(self.root.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
            for f in files:
                if f.stem not in known and SID.fullmatch(f.stem):
                    try:
                        known[f.stem] = Journey.model_validate_json(f.read_text(encoding="utf-8"))
                    except ValueError:
                        continue
            order = {f.stem: i for i, f in enumerate(files)}
        else:
            order = {jid: -i for i, jid in enumerate(known)}
        mine = [jid for jid, j in known.items() if j.user_id == owner]
        return sorted(mine, key=lambda jid: order.get(jid, -1))[:limit]

    def release(self, jid: str, owner: str) -> bool:
        """Takes the journey off `owner` without reading it as a Journey: an envelope written by an older build may no
        longer validate, and an account must still be able to remove it. False when the journey is missing or is not
        owner's."""
        with self.lock(jid):
            path = self.root / f"{jid}.json" if self.root else None
            if path and path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("user_id") != owner:
                    return False
                data["user_id"] = None
                tmp = path.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                tmp.replace(path)
                self._mem.pop(jid, None)
                return True
            held = self._mem.get(jid)
            if held is None or held.user_id != owner:
                return False
            held.user_id = None
            return True

    def updated_at(self, jid: str) -> str | None:
        """UTC ISO time of the journey's last save (its file's modified time); None when nothing is saved to disk."""
        if not self.root or not SID.fullmatch(jid):
            return None
        try:
            return datetime.fromtimestamp((self.root / f"{jid}.json").stat().st_mtime, timezone.utc).isoformat()
        except OSError:
            return None

    def save(self, session: Journey) -> None:
        with self.lock(session.id):
            saved = self._saved_copy(session)
            if self.root:
                self.root.mkdir(parents=True, exist_ok=True)
                path = self.root / f"{session.id}.json"
                tmp = path.with_suffix(".json.tmp")
                with tmp.open("w", encoding="utf-8") as f:
                    f.write(json.dumps(session.model_dump(mode="json"), ensure_ascii=False))
                    f.flush()
                    os.fsync(f.fileno())
                tmp.replace(path)
                try:
                    fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                except OSError:
                    # Rename landed, but durability is unknown. Reload the visible file
                    # rather than retaining the pre-rename cache after an error.
                    self._mem.pop(session.id, None)
                    raise
            self._mem[session.id] = saved


def _parts(jid, stage, revision, outputs: dict, sessions: dict, snapshots: dict, updated_at) -> dict:
    return {"id": jid, "stage": stage, "revision": revision, "updated_at": updated_at,
            "context": (outputs.get("trip") or {}).get("context") or {},
            "itinerary": (outputs.get("planning") or {}).get("itinerary") if "planning" in outputs else None,
            "confirmed": "planning" in outputs,
            "decision_confirmed": [c["id"] for c in (outputs.get("decision") or {}).get("confirmed", [])]
            if "decision" in outputs else None,
            "selected": list(((snapshots.get("decision") or {}).get("state") or {}).get("selected") or [])
            if "decision" in sessions else [],
            "transcript": (snapshots.get("trip") or {}).get("transcript") or []}
