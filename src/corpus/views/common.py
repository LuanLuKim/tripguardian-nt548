"""Shared by the views: config, the city's area, the output directory and one polite HTTP call."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]


class ViewError(RuntimeError):
    """A source did not answer usably, or the answer is not enough to publish a view."""


@cache
def config() -> dict:
    return yaml.safe_load((ROOT / "config" / "views.yaml").read_text(encoding="utf-8"))


def data_dir() -> Path:
    load_dotenv(ROOT / ".env")
    d = Path(os.environ.get("DATA_DIR", "data"))
    return d if d.is_absolute() else ROOT / d


def views_dir(city: str) -> Path:
    return data_dir() / city / "views"


def city_area(city: str) -> list[float]:
    """[lat_min, lng_min, lat_max, lng_max] of the city in config/cities.yaml."""
    cities = yaml.safe_load((ROOT / "config" / "cities.yaml").read_text(encoding="utf-8"))
    if city not in cities:
        raise ViewError(f"unknown city {city!r}; known: {', '.join(cities)}")
    area = cities[city].get("area")
    if not area or len(area) != 4:
        raise ViewError(f"config/cities.yaml: {city} has no area")
    return [float(x) for x in area]


def center(area: list[float]) -> tuple[float, float]:
    return (area[0] + area[2]) / 2, (area[1] + area[3]) / 2


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def user_agent() -> str:
    load_dotenv(ROOT / ".env")
    return f"TripGuardian/0.1 (contact: {os.environ.get('LIVE_CONTACT', 'unset')})"


def fetch_json(url: str, *, data: dict | None = None, timeout_s: float | None = None):
    """One request (GET, or POST form when `data`); a failure is a ViewError. Callers make requests one at a time."""
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": user_agent(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s or config()["timeout_s"]) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ViewError(f"{url.split('?', 1)[0]}: {e}") from e
