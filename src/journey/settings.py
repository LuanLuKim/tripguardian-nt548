"""Journey settings: config/journey.yaml thresholds plus the airport table (config/airports.yaml, shared static data)."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "config" / "journey.yaml"
AIRPORTS = ROOT / "config" / "airports.yaml"


@dataclass(frozen=True)
class Settings:
    version: int
    city_centre: dict
    motorbike_max_km: float
    coach_region_max_km: float
    plane: dict
    entry_snap_km: float = 8
    entry_roads: tuple = ()  # ({text, lat, lng}, …) the passes into the city
    airports: tuple = ()  # ({iata, name, lat, lng}, …) flying to the city
    dest_airport: dict | None = None  # {iata, name, lat, lng}


@cache
def load(path: Path = PATH, airports: Path = AIRPORTS) -> Settings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    table = yaml.safe_load(airports.read_text(encoding="utf-8"))
    return Settings(**{**raw, "entry_roads": tuple(raw.get("entry_roads") or ())}, airports=tuple(table["airports"]), dest_airport=table["dest"])
