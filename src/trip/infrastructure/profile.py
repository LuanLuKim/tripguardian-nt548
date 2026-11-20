"""Stored profile per user (docs/TRIP_UNDERSTANDING.md §17): data/trip/profiles/<user_id>.json.

The file holds each remembered session's votes, the user's edits to entries, the Judge's flags, a pause switch and the
Agent's memo of each chat: {"sessions": [...], "edits": {entry id: Edit}, "flags": {entry id: verdict}, "paused": bool,
"memos": {session id: {"day", "upto", "memo"}}}. Entries are derived from the votes on every read (domain/patterns.py).
The user id is opaque (an account id through the harness). The votes hold the user's own body needs only as patterns.observe
allows; a memo holds the health, body or diet needs the user said about themself (owner 2026-11-17: kept without asking
again, under the same remember consent).
"""

import json
import re
import threading
from datetime import date
from pathlib import Path

from ..domain.memo import Memo
from ..domain.patterns import Edit, Entry, Pattern, Summary, entries, entry_id, patterns_of
from .settings import PatternSettings

USER_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")
MAX_SESSIONS = 200  # oldest summaries beyond this are dropped
MAX_MEMOS = 30  # memos of the latest chats kept
STATEMENT_MAX = 200


class ProfileStore:
    def __init__(self, root: Path, cfg: PatternSettings):
        self.root, self.cfg = root, cfg
        self._lock = threading.Lock()

    def _path(self, user_id: str) -> Path:
        if not USER_ID.fullmatch(user_id):
            raise ValueError("user_id must be 8-64 letters, digits, '-' or '_'")
        return self.root / f"{user_id}.json"

    @staticmethod
    def _read(path: Path) -> dict:
        empty = {"sessions": [], "edits": {}, "flags": {}, "paused": False, "memos": {}}
        if not path.exists():
            return empty
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {"sessions": [Summary.model_validate(x) for x in raw["sessions"]],
                    "edits": {k: Edit.model_validate(v) for k, v in (raw.get("edits") or {}).items()},
                    "flags": {k: str(v) for k, v in (raw.get("flags") or {}).items()},
                    "paused": raw.get("paused") is True,
                    "memos": ProfileStore._memos(raw.get("memos"))}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):  # unreadable: an empty profile, never a failed trip
            return empty

    @staticmethod
    def _memos(raw) -> dict:
        """The stored memos; one that does not read is dropped alone, never the votes beside it."""
        out = {}
        for k, v in (raw or {}).items() if isinstance(raw, dict) else ():
            try:
                out[str(k)] = {"day": str(v["day"]), "upto": int(v["upto"]), "memo": Memo.model_validate(v["memo"])}
            except (ValueError, KeyError, TypeError):
                continue
        return out

    def _write(self, path: Path, data: dict) -> None:
        sessions = [s for s in data["sessions"] if s.votes][-MAX_SESSIONS:]
        ids = {entry_id(k, v) for s in sessions for k, v in s.votes.items()}
        body = {"sessions": [s.model_dump(mode="json") for s in sessions],
                "edits": {k: v.model_dump(mode="json") for k, v in data["edits"].items() if k in ids},
                "flags": {k: v for k, v in data["flags"].items() if k in ids},
                "paused": data["paused"],
                "memos": {k: {**v, "memo": v["memo"].model_dump(mode="json")} for k, v in
                          sorted(data["memos"].items(), key=lambda kv: kv[1]["day"])[-MAX_MEMOS:]}}
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def history(self, user_id: str) -> list[Summary]:
        path = self._path(user_id)
        with self._lock:
            return self._read(path)["sessions"]

    def entries(self, user_id: str, today: date, catalog=None) -> tuple[bool, list[Entry]]:
        """(whole profile paused, every entry), for the user to see."""
        path = self._path(user_id)
        with self._lock:
            d = self._read(path)
        return d["paused"], entries(d["sessions"], cfg=self.cfg, today=today, edits=d["edits"], flags=d["flags"],
                                    catalog=catalog)

    def patterns(self, user_id: str, today: date) -> list[Pattern]:
        paused, found = self.entries(user_id, today)
        return [] if paused else patterns_of(found, self.cfg)

    def record(self, user_id: str, summary: Summary) -> None:
        """One summary per session id: recording the same session again replaces it."""
        path = self._path(user_id)
        with self._lock:
            d = self._read(path)
            d["sessions"] = [s for s in d["sessions"] if s.sid != summary.sid] + [summary]
            self._write(path, d)

    def note(self, user_id: str, sid: str, day: date, votes: dict[str, str]) -> None:
        """Weak votes from what the user did in Decision / Planning (patterns.acts_votes), merged into one "acts:<sid>"
        session per trip: a later vote on the same key replaces the earlier one. They are how "acted"."""
        if not votes:
            return
        path, key = self._path(user_id), f"acts:{sid}"
        with self._lock:
            d = self._read(path)
            old = next((s for s in d["sessions"] if s.sid == key), None)
            before = old.votes if old else {}
            merged = {**before, **{k: v for k, v in votes.items() if not (v == "kept" and before.get(k) not in (None, "kept"))}}
            done = Summary(sid=key, day=day, votes=merged, how={k: "acted" for k in merged})
            d["sessions"] = [s for s in d["sessions"] if s.sid != key] + [done]
            self._write(path, d)

    def memo_upto(self, user_id: str, sid: str) -> int:
        """The last turn of chat `sid` its memo read; -1 when it has none."""
        path = self._path(user_id)
        with self._lock:
            got = self._read(path)["memos"].get(sid)
        return got["upto"] if got else -1

    def memo(self, user_id: str, sid: str) -> Memo | None:
        path = self._path(user_id)
        with self._lock:
            got = self._read(path)["memos"].get(sid)
        return got["memo"] if got else None

    def put_memo(self, user_id: str, sid: str, day: date, upto: int, memo: Memo) -> None:
        """One memo per chat: writing it again replaces it."""
        path = self._path(user_id)
        with self._lock:
            d = self._read(path)
            d["memos"][sid] = {"day": day.isoformat(), "upto": upto, "memo": memo}
            self._write(path, d)

    def memos(self, user_id: str, but: str = "") -> list[Memo]:
        """The memos of the user's other chats, newest first; none while the profile is paused."""
        path = self._path(user_id)
        with self._lock:
            d = self._read(path)
        if d["paused"]:
            return []
        rows = sorted(((v["day"], k, v["memo"]) for k, v in d["memos"].items() if k != but), reverse=True)
        return [m for _, _, m in rows]

    @staticmethod
    def _signal(d: dict, eid: str) -> tuple[str, str] | None:
        return next(((k, v) for s in d["sessions"] for k, v in s.votes.items() if entry_id(k, v) == eid), None)

    def edit(self, user_id: str, eid: str, statement: str | None = None, paused: bool | None = None) -> bool:
        """The user's own wording and / or a pause of one entry. False when there is no such entry."""
        if statement is not None and (not isinstance(statement, str) or not statement.strip()
                                      or len(statement.strip()) > STATEMENT_MAX):
            raise ValueError(f"statement must be 1-{STATEMENT_MAX} characters")
        if paused is not None and not isinstance(paused, bool):
            raise ValueError("paused must be true or false")
        path = self._path(user_id)
        with self._lock:
            d = self._read(path)
            if self._signal(d, eid) is None:
                return False
            old = d["edits"].get(eid) or Edit()
            d["edits"][eid] = Edit(statement=statement.strip() if statement is not None else old.statement,
                                   paused=old.paused if paused is None else paused)
            self._write(path, d)
            return True

    def delete(self, user_id: str, eid: str) -> bool:
        """Deleted for real: the entry's votes and quotes leave every session, its edit and flag go too."""
        path = self._path(user_id)
        with self._lock:
            d = self._read(path)
            signal = self._signal(d, eid)
            if signal is None:
                return False
            key, value = signal
            d["sessions"] = [s if s.votes.get(key) != value else s.model_copy(update={
                "votes": {k: v for k, v in s.votes.items() if k != key},
                "how": {k: v for k, v in s.how.items() if k != key},
                "quotes": {k: v for k, v in s.quotes.items() if k != key}}) for s in d["sessions"]]
            d["edits"].pop(eid, None)
            d["flags"].pop(eid, None)
            self._write(path, d)
            return True

    def pause(self, user_id: str, paused: bool) -> None:
        """Pause the whole profile: nothing seeds a trip; entries stay for the user to see."""
        if not isinstance(paused, bool):
            raise ValueError("paused must be true or false")
        path = self._path(user_id)
        with self._lock:
            d = self._read(path)
            d["paused"] = paused
            self._write(path, d)

    def flag(self, user_id: str, eid: str, verdict: str) -> bool:
        """The Judge found the entry unfounded: it drops to weak until the user edits it."""
        path = self._path(user_id)
        with self._lock:
            d = self._read(path)
            if self._signal(d, eid) is None:
                return False
            d["flags"][eid] = verdict
            self._write(path, d)
            return True

    def users(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json")) if self.root.exists() else []

    def forget(self, user_id: str) -> bool:
        path = self._path(user_id)
        with self._lock:
            if not path.exists():
                return False
            path.unlink()
            return True
