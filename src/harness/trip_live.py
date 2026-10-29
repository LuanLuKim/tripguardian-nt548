"""The live reads the Trip assistant gets (weather, travel time, route by mode, ways to the city), built from the public
live and journey APIs. One place for the server and the bench."""

from datetime import date

import journey
import live
from trip import LiveTools


def trip_live_tools(cfg, weather=None, matrix=None, route_shape=None, options=None, geosearch=None) -> LiveTools:
    """LiveTools on `cfg` (live.Settings). The keyword arguments replace the live calls (tests)."""
    weather = weather or live.weather
    matrix = matrix or live.travel_matrix
    route_shape = route_shape or live.route_shape
    options = options or journey.options
    geosearch = geosearch or live.geosearch

    def way_in(origin: str, lat: float | None, lng: float | None, day: str | None) -> dict:
        if lat is None or lng is None:
            # the home city, not a place inside the trip's city (live.geocode would append ", Đà Lạt")
            try:
                rows = geosearch(origin, cfg, limit=1)
            except live.Unavailable as e:
                raise ValueError("origin search unavailable") from e
            if not rows:
                raise ValueError("origin not found")
            lat, lng = rows[0]["lat"], rows[0]["lng"]
        raw = options((lat, lng), date.fromisoformat(day) if day else None).as_dict()
        return {**raw, "origin": origin}

    return LiveTools(weather=lambda lat, lng, days: weather(lat, lng, days, cfg),
                     matrix=lambda points: matrix(points, None, cfg),
                     route=lambda points, mode: route_shape(points, mode, cfg), journey=way_in)
