"""Booking settings (config/booking.yaml). Partner ids come from .env, never from the repo."""

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "config" / "booking.yaml"


@dataclass(frozen=True)
class Settings:
    version: int
    stay_city: str
    stay_max_age_h: float
    flight_city: str = "dalat"  # which published flight_offers file the flight adapter reads
    flight_max_age_h: float = 36.0  # a crawled search older than this states no flight, price or time (link only)
    affiliate: dict = field(default_factory=dict)  # provider -> {param, env}


@cache
def load(path: Path = PATH) -> Settings:
    return Settings(**yaml.safe_load(path.read_text(encoding="utf-8")))
