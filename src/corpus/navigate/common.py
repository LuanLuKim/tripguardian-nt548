"""Paths, config and the plain-file helpers of the navigator."""

import json
import os
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import yaml

from .. import data_root

ROOT = Path(__file__).resolve().parents[3]


class NavigateError(RuntimeError):
    """The navigator cannot continue (unknown city, sol returned nothing usable, no map to compare)."""


@cache
def config() -> dict:
    return yaml.safe_load((ROOT / "config" / "navigate.yaml").read_text(encoding="utf-8"))


def yaml_file(name: str) -> dict:
    path = ROOT / "config" / name
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}


def city_info(city: str) -> tuple[str, list[float]]:
    """(display name, [lat_min, lng_min, lat_max, lng_max]) from config/cities.yaml."""
    cities = yaml_file("cities.yaml")
    if city not in cities:
        raise NavigateError(f"unknown city {city!r}; known: {', '.join(cities)}")
    return cities[city]["name"], cities[city]["area"]


def navigate_dir(city: str) -> Path:
    return data_root() / city / "navigate"


def stamp(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
