"""Monthly rain climate for dates beyond Open-Meteo's forecast horizon.

Three layers, first that has the month wins: `rain_prob_override_by_month` in config/climate.yaml (a hand correction),
the city's ClimateNormal view (data/<city>/views/climate.json, Open-Meteo archive), then `rain_prob_by_month` in the
same file (a rough hand estimate for a city whose view was never built). A month no layer has is None.
"""

from datetime import date
from functools import cache
from pathlib import Path

import yaml

from .. import views

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "config" / "climate.yaml"


@cache
def _table(path: Path, key: str) -> dict[int, float]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {int(k): float(v) for k, v in (doc.get(key) or {}).items()}


def _view_table() -> dict[int, float]:
    doc = views.read("climate") or {}
    return {int(m): v["rain_prob"] for m, v in (doc.get("months") or {}).items() if v.get("rain_prob") is not None}


def climate(dates: list[str], path: Path = PATH) -> dict:
    """{"YYYY-MM-DD": {"rain_prob", "source": "climate", "fetched_at": None}}; a month no layer has is None."""
    table = {**_table(path, "rain_prob_by_month"), **_view_table(), **_table(path, "rain_prob_override_by_month")}
    return {d: {"rain_prob": table.get(date.fromisoformat(d).month), "source": "climate", "fetched_at": None}
            for d in dates}
