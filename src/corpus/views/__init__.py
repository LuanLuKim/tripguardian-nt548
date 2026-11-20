"""Global views (docs/CORPUS.md §View toàn cầu): ClimateNormal, CalendarDay, RestrictedArea per city. Public API.

Offline and city-agnostic: the city's area comes from config/cities.yaml, the settings from config/views.yaml, the
output goes to data/<city>/views/. No model, no browser.
"""

from . import calendar, climate, restricted
from .common import ViewError

VIEWS = {"climate": climate.build, "calendar": calendar.build, "restricted": restricted.build}


def run(view: str, city: str) -> None:
    """Build one view, or `all` of them in order. A view that fails raises ViewError after the earlier ones are written."""
    for name in VIEWS if view == "all" else (view,):
        out = VIEWS[name](city)
        print(f"views {name} {city}: {len(out.get('months') or out.get('days') or out.get('features') or [])} items")


def climate_normals(city: str) -> dict | None:
    """{"1".."12": {tmax_c, tmin_c, rain_prob, fog_prob | None, days, years}} of the built view, else None."""
    view = climate.load(city)
    return None if view is None else view["months"]


def calendar_days(city: str) -> list[dict] | None:
    """[{date, lunar: {year, month, day, leap}, holiday: name | None}] of the built view, else None."""
    view = calendar.load(city)
    return None if view is None else view["days"]


def restricted_areas(city: str) -> list[dict] | None:
    """GeoJSON features of the built view, else None (never built: unknown, not "no restricted area")."""
    return restricted.load(city)


restricted_hits = restricted.hits

__all__ = ["VIEWS", "ViewError", "calendar_days", "climate_normals", "restricted_areas", "restricted_hits", "run"]
