"""Place state, durable transitions, and independent boot/best snapshots."""

from __future__ import annotations

import json
import re
import shutil
import threading
from datetime import datetime, timezone

from paths import DATA
from . import config

_LEDGER_LOCK = threading.Lock()


class Place:
    def __init__(self, slug: str):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", slug):
            raise ValueError(f"Invalid place slug: {slug}")
        self.slug = slug
        self.dir = DATA / "places" / slug
        self.state_file = self.dir / "auto3d.json"
        self.s = dict(slug=slug, fid=None, name=slug, reviews=None, category=None, stage="new",
                      history=[], tokens=0, notes={}, kit_hint=None, kit_forced=None,
                      scores=[], best_round=0, builder=config()["builder"], rounds=0, retries=0, version=2)
        if self.state_file.exists():
            old = json.loads(self.state_file.read_text())
            self.s.update(old)
            if old.get("version", 1) < 2:
                # V1's prep meant prep had completed; write meant writing was next.
                self.s["stage"] = {"prep": "notes", "write": "build"}.get(self.s["stage"], self.s["stage"])
                self.s["rounds"] = sum(h["step"] in ("write", "fix") for h in self.s["history"])
                self.s["version"] = 2

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.s, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(self.state_file)

    def stage(self, name: str) -> None:
        self.s["stage"] = name
        self.save()

    def log(self, step: str, tokens: int = 0, **info) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.s["tokens"] += tokens
        self.s["history"].append({"time": now, "step": step, "tokens": tokens, **info})
        self.save()
        ledger = DATA / "batch/ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER_LOCK, ledger.open("a") as stream:
            stream.write(json.dumps({"time": now, "slug": self.slug, "step": step, "tokens": tokens}) + "\n")

    def snapshot(self, kind: str) -> None:
        source = self.dir / "place.json"
        if source.exists():
            target = self.dir / f"place.{kind}.json"
            tmp = target.with_suffix(".tmp")
            shutil.copy2(source, tmp)
            tmp.replace(target)

    def restore(self, kind: str) -> bool:
        source = self.dir / f"place.{kind}.json"
        if not source.exists():
            return False
        shutil.copy2(source, self.dir / "place.json")
        return True
