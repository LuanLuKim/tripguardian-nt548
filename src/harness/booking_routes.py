"""Read-only routes for the trip's way in: booking offers and the options from home to the lodging.
Parameters are untrusted: booking.query_from_params validates them and a ValueError becomes a 400."""

from datetime import date
import re
import unicodedata

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


def _city_point(text: str) -> tuple[float, float] | None:
    def fold(value):
        value = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
        return re.sub(r"[^a-z0-9]", "", "".join(c for c in value if unicodedata.category(c) != "Mn"))

    name = fold(text)
    if name in {"tphcm", "hcm", "hochiminh", "thanhphohochiminh", "tphochiminh"}:
        name = fold("Sài Gòn")
    for row in live.load_settings().vexere_regions:
        if fold(row["name"]) == name:
            return float(row["lat"]), float(row["lng"])
    return None


def journey_options(params: dict, options=None) -> dict:
    origin = _point(params, "lat", "lng")
    text = str(params.get("origin") or "").strip()
    if origin is None and not text:
        raise ValueError("need lat and lng or origin")
    if origin is None:
        origin = _city_point(text)
    dest = _point(params, "dest_lat", "dest_lng")
    way = params.get("way", "inbound")
    if way not in booking.WAYS:
        raise ValueError("bad way")
    try:
        day = date.fromisoformat(params["date"]) if params.get("date") else None
    except ValueError as e:
        raise ValueError("bad date") from e
    if origin is None:
        return {"origin": None, "origin_text": text, "dest": list(dest) if dest else None,
                "dest_is_centre": dest is None, "way": way, "day": day.isoformat() if day else None,
                "options": [], "reason": "unknown_origin"}
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
