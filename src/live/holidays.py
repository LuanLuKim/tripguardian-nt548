"""Vietnamese public holidays: the city's CalendarDay view (data/<city>/views/calendar.json: the `holidays` library and
lunar dates), with config/holidays.yaml as the hand-entered layer on top.

A name in the file replaces the view's name for that date; a date in the file the view lacks is added. A date neither
lists is not a holiday; with no view built, the file is the whole truth.
"""

from datetime import date
from functools import cache
from pathlib import Path

import yaml

from . import views

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "config" / "holidays.yaml"


def _as_date(key) -> date:
    return key if isinstance(key, date) else date.fromisoformat(str(key))


@cache
def _table(path: Path) -> dict[date, str]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {_as_date(k): str(v) for k, v in (doc.get("holidays") or {}).items()}


def _view_table() -> dict[date, str]:
    doc = views.read("calendar") or {}
    return {date.fromisoformat(d["date"]): d["holiday"] for d in doc.get("days") or [] if d.get("holiday")}


def holidays(dates: list[date], path: Path = PATH) -> dict[date, str]:
    """Only the holiday dates, mapped to the holiday's name."""
    table = {**_view_table(), **_table(path)}
    return {d: table[d] for d in dates if d in table}
