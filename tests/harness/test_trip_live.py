"""The Trip assistant's live tools built from live / journey public APIs."""

from datetime import date

from harness import trip_live_tools


class Cfg:
    pass


def test_route_goes_through_route_shape_with_the_mode():
    seen = []
    tools = trip_live_tools(Cfg(), route_shape=lambda pts, mode, cfg: seen.append((pts, mode)) or {"coords": [], "minutes": 5},
                            weather=None, matrix=None)
    out = tools.route([(1.0, 2.0), (1.1, 2.1)], "motorbike")
    assert out["minutes"] == 5 and seen == [([(1.0, 2.0), (1.1, 2.1)], "motorbike")]


def test_journey_uses_the_given_point_else_geocodes_and_names_the_origin():
    calls = {}

    class J:
        def as_dict(self):
            return {"origin": [10.0, 106.0], "options": [{"mode": "car"}], "day": "2026-11-12"}

    def options(origin, day, dest=None, way="inbound", cfg=None):
        calls["o"], calls["d"] = origin, day
        return J()

    tools = trip_live_tools(Cfg(), options=options, geosearch=lambda text, cfg, limit=1: [{"lat": 10.0, "lng": 106.0, "text": "x"}],
                            weather=None, matrix=None, route_shape=None)
    out = tools.journey("Sài Gòn", None, None, "2026-11-12")
    assert out["origin"] == "Sài Gòn" and out["options"] == [{"mode": "car"}]
    assert calls == {"o": (10.0, 106.0), "d": date(2026, 11, 12)}
    tools.journey("Sài Gòn", 11.0, 107.0, None)
    assert calls == {"o": (11.0, 107.0), "d": None}


def test_journey_origin_is_searched_without_the_city_suffix():
    seen = []
    tools = trip_live_tools(Cfg(), options=lambda *a, **k: type('J', (), {'as_dict': lambda self: {'options': []}})(),
                            geosearch=lambda t, c, limit=1: seen.append(t) or [{'lat': 1.0, 'lng': 2.0}], weather=None, matrix=None, route_shape=None)
    tools.journey('Hà Nội', None, None, None)
    assert seen == ['Hà Nội']


def test_journey_without_a_geocode_hit_is_unavailable():
    import pytest
    tools = trip_live_tools(Cfg(), options=lambda *a, **k: None, geosearch=lambda t, c, limit=1: [], weather=None, matrix=None, route_shape=None)
    with pytest.raises(ValueError):
        tools.journey("Nowhere", None, None, None)
