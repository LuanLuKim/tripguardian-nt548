"""Reads the global views a city's offline build left under data/<city>/views/ (climate.json, calendar.json).

Read-only and optional: a view that was never built is None, and the hand-entered files in config/ answer alone, as
they did before the views existed. The folder is written by the corpus; live only reads it.
"""

import json
from functools import cache
from pathlib import Path

from . import settings
from .cache import data_dir


@cache
def _parsed(path: Path, mtime_ns: int):
    return json.loads(path.read_text(encoding="utf-8"))


def read(name: str) -> dict | None:
    """data/<views_city>/views/<name>.json, parsed (re-read when the file changes), or None when absent / unreadable."""
    p = data_dir() / settings.load().views_city / "views" / f"{name}.json"
    try:
        return _parsed(p, p.stat().st_mtime_ns)
    except (OSError, ValueError):
        return None
