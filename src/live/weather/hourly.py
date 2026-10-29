"""Open-Meteo hourly forecast for one day, two models side by side (best_match and gfs_seamless), so a check can
tell a firm forecast from one the models disagree on. Within the 16-day horizon only; beyond it there is none."""

from datetime import date

from ..cache import get as cache_get
from ..cache import put as cache_put
from ..http import get_json
from ..settings import Settings
from .open_meteo import THUNDERSTORM, in_range

MODELS = ("best_match", "gfs_seamless")
HOURLY = ("precipitation_probability", "precipitation", "wind_gusts_10m", "weather_code", "visibility")
FOG = (45, 48)                 # WMO fog codes
FOG_VISIBILITY_M = 1000        # under this the view is gone, whatever the code says
DISAGREE_PROB = 0.5            # the two models' rain chances this far apart -> not a firm forecast


def _hour(v: dict) -> dict:
    code, vis, prob = v.get("weather_code"), v.get("visibility"), v.get("precipitation_probability")
    fog = None if code is None and vis is None else bool((code in FOG) or (vis is not None and vis < FOG_VISIBILITY_M))
    return {"rain_prob": prob / 100 if prob is not None else None, "rain_mm": v.get("precipitation"),
            "gust_kmh": v.get("wind_gusts_10m"), "storm": code in THUNDERSTORM if code is not None else None, "fog": fog}


def weather_hourly(lat: float, lng: float, day: str, cfg: Settings, today_fn=date.today) -> dict | None:
    """{"hours": {0..23: {"rain_prob", "rain_mm", "gust_kmh", "storm", "fog", "disagree"}}, "source", "fetched_at"}
    or None beyond the forecast horizon. A slot best_match left empty is read from the second model; a figure neither
    gave stays None. disagree: the models' rain chances are DISAGREE_PROB apart, or one sees a storm the other does
    not (None when either is silent). May raise live.Unavailable."""
    if not in_range([day], today_fn()):
        return None
    payload = {"kind": "hourly2", "lat": round(lat, 4), "lng": round(lng, 4), "day": day}
    hit = cache_get("weather", payload, cfg.ttl_s["weather"])
    if hit is None:
        url = (f"{cfg.open_meteo_url}?latitude={lat:.4f}&longitude={lng:.4f}&hourly={','.join(HOURLY)}"
               f"&models={','.join(MODELS)}&timezone=Asia%2FBangkok&start_date={day}&end_date={day}")
        h = get_json(url, cfg.user_agent, cfg.timeout_s).get("hourly") or {}
        rows = {}
        for i, t in enumerate(h.get("time") or []):
            if t[:10] == day:
                rows[int(t[11:13])] = {m: {k: (h.get(f"{k}_{m}") or [None] * (i + 1))[i] for k in HOURLY}
                                       for m in MODELS}
        hit = cache_put("weather", payload, rows, "open-meteo")
    hours = {}
    for hour in range(24):
        per = (hit["value"] or {}).get(hour) or (hit["value"] or {}).get(str(hour)) or {}
        a, b = _hour(per.get(MODELS[0]) or {}), _hour(per.get(MODELS[1]) or {})
        out = {k: a[k] if a[k] is not None else b[k] for k in a}
        if None in (a["rain_prob"], b["rain_prob"]):
            out["disagree"] = None
        else:
            out["disagree"] = abs(a["rain_prob"] - b["rain_prob"]) >= DISAGREE_PROB or (
                a["storm"] is not None and b["storm"] is not None and a["storm"] != b["storm"])
        hours[hour] = out
    return {"hours": hours, "source": hit["source"], "fetched_at": hit["fetched_at"]}
