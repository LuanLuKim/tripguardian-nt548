"""Planning thresholds (config/planning.yaml)."""

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "config" / "planning.yaml"


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass(frozen=True)
class Settings:
    version: int
    road_factor: float
    rough_speed_kmh: dict
    walk_km: float
    walk_kmh: float
    default_days: int
    day_start: int          # minutes after midnight
    day_end: int
    leave_at: int
    visit_key: dict
    per_day: dict
    buffer_min: dict
    long_leg_min: int
    buffer_extra_long: int
    buffer_extra_uncertain: int
    rest_min: dict
    max_consecutive_min: dict
    meals_per_day: int
    meal_min: int
    meal_windows: dict      # name -> (earliest start, latest start) in minutes
    pins: dict
    exact_n: int
    improve_passes: int
    weights: dict
    rain_high: float
    buffer_extra_rain: int
    robustness: dict
    objective_weights: dict
    near_close_min: int
    far_leg_min: int
    backup_radius_min: int
    backups_per_place: int
    radius_km: dict
    lodging_k: int
    lodging_list_k: int
    lodging_share: float
    min_reviews: int
    split_min: int
    lodging_pool: int
    lodging_weights: dict
    loc_ref_min: int
    history_max: int
    repair_diff_weight: float
    decision_url: str
    first_token_s: float
    total_s: float
    rethink_drops: int
    crowd_busy_pct: int
    conditions: dict
    time_suitability: dict = field(default_factory=dict)
    meal_durations: dict = field(default_factory=dict)
    duration_profiles: dict = field(default_factory=dict)
    repair_local_additions: int = 1
    repair_search_limit: int = 720
    cache_entries: int = 128
    route_cache_entries: int = 4096   # one trip's day layouts / orders (build.Trip.routes), reused across the overload search
    suggestion_workers: int = 2
    direction_workers: int = 3        # overload directions searched in forked processes at once (1 = in this process)
    chunk_days: int = 7
    long_trip_exact_n: int = 5
    spread_extra_min: int = 45        # road a fitting selection may add to give an otherwise empty day one stop (layout.assign)
    composer: dict = field(default_factory=lambda: {"rho": 0.9, "alpha": 0.7, "tight_ratio": 0.8,
                                                   "per_day_max": {"slow": 4, "normal": 5, "packed": 7},
                                                   "search_limit": 120, "transport_vnd_per_min": {}})
    realistic: dict = field(default_factory=dict)
    stay_price_max_age_h: float = 36.0   # a dated lodging price older than this is not used (corpus.serving.stay_prices)
    eve_replan: dict = field(default_factory=dict)   # D.3 evening check (docs/PLANNING.md §Đổi lịch tối trước ngày đi)
    assistant: dict = field(default_factory=lambda: {"enabled": False, "max_steps": 4, "max_tokens": 900})   # the Lịch trình chatbot (docs/PLANNING.md §Trợ lý)
    expert: dict = field(default_factory=lambda: {"enabled": False})   # D.2 Local Expert (docs/PLANNING.md §Local Expert)


@cache
def load(path: Path = PATH) -> Settings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    for k in ("day_start", "day_end", "leave_at"):
        raw[k] = to_min(raw[k])
    raw["meal_windows"] = {name: (to_min(a), to_min(b)) for name, (a, b) in raw["meal_windows"].items()}
    raw["pins"] = {f: {**p, **({"from": to_min(p["from"]), "to": to_min(p["to"])} if p["anchor"] == "clock" else {})}
                   for f, p in raw["pins"].items()}
    return Settings(**raw)
