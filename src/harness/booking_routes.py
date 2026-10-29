"""Read-only routes for the trip's way in: booking offers and the options from home to the lodging.
Parameters are untrusted: booking.query_from_params validates them and a ValueError becomes a 400."""

from datetime import date

import booking
import journey
import live


def offers(params: dict) -> dict:
    kind = params.get("kind", "")
    if kind == "stay" and str(params.get("fid", "")).startswith("@"):
        # a lodging the user typed in (fid "@home") is not a listed place: it has no offers, which is a normal answer
        return {"offers": [], "reason": "self_entered_lodging"}
    query = booking.query_from_params(kind, params)
    return {"offers": [o.as_dict() for o in booking.offers(kind, query)]}


def _point(params: dict, lat: str, lng: str):
    if params.get(lat) is None and params.get(lng) is None:
        return None
    try:
        p = (float(params[lat]), float(params[lng]))
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"need numeric {lat} and {lng}") from e
    if not (-90 <= p[0] <= 90 and -180 <= p[1] <= 180):
        raise ValueError(f"{lat}/{lng} out of range")
    return p


def journey_options(params: dict, options=None) -> dict:
    origin = _point(params, "lat", "lng")
    if origin is None:
        raise ValueError("need lat and lng")
    dest = _point(params, "dest_lat", "dest_lng")
    way = params.get("way", "inbound")
    if way not in booking.WAYS:
        raise ValueError("bad way")
    try:
        day = date.fromisoformat(params["date"]) if params.get("date") else None
    except ValueError as e:
        raise ValueError("bad date") from e
    run = options or (lambda o, d, t, w: journey.options(o, d, t, way=w))
    return run(origin, day, dest, way).as_dict()


def home_point(city: str | None, search=None) -> dict | None:
    """The profile's home_city as a point {"text", "lat", "lng", "province"} for the trip's origin prior; None when
    unset or no geocoder answers (the prior is then simply absent: nothing is guessed)."""
    if not city or not city.strip():
        return None
    try:
        rows = (search or (lambda q: live.geosearch(q, live.load_settings(), limit=1)))(city.strip())
    except live.Unavailable:
        return None
    return {"text": city.strip(), "lat": rows[0]["lat"], "lng": rows[0]["lng"], "province": rows[0].get("province")} if rows else None
