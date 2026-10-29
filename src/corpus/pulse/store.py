"""data/<city>/pulse/{generated_at}.json + latest.json (docs/CORPUS.md §Nhịp). Offline writes; online only reads."""

import json
import os
from functools import lru_cache
from pathlib import Path

from .. import data_root


def pulse_dir(city: str, root: Path | None = None) -> Path:
    return (root or data_root()) / city / "pulse"


def write(city: str, snapshot: dict, keep: int, root: Path | None = None) -> Path:
    """Atomic write of the dated file and latest.json; dated files beyond the newest `keep` (this folder only) go."""
    d = pulse_dir(city, root)
    d.mkdir(parents=True, exist_ok=True)
    name = snapshot["generated_at"].replace("-", "").replace(":", "")[:15] + "Z.json"
    body = json.dumps(snapshot, ensure_ascii=False, indent=1).encode("utf-8")
    for target in (d / name, d / "latest.json"):
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, target)
    for old in sorted(p for p in d.glob("2*.json"))[:-keep]:
        old.unlink()
    return d / name


def load(city: str, root: Path | None = None) -> dict | None:
    """The newest snapshot, or None when the job never ran (unknown, not "nothing is trending")."""
    p = pulse_dir(city, root) / "latest.json"
    try:
        return _parsed(p, p.stat().st_mtime_ns)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=8)
def _parsed(path: Path, mtime_ns: int) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
