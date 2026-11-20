"""ClimateNormal: per-month climate of a city from Open-Meteo's archive (docs/CORPUS.md §View toàn cầu).

Daily values over start_year..end_year at the centre of the city's area -> per calendar month: median daily max / min
temperature, share of rainy days, share of fog days (None when the source never reports fog at all). A figure the source does
not give is None, never a default.
"""

import urllib.parse
from collections import defaultdict
from statistics import median

from .common import ViewError, center, city_area, config, fetch_json, now, read_json, views_dir, write_json

FOG_CODES = (45, 48)  # WMO weather codes: fog, depositing rime fog
DAILY = "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"


def path(city: str):
    return views_dir(city) / "climate.json"


def normals(daily: dict, rain_mm: float, min_years: int) -> dict:
    """Open-Meteo `daily` columns -> {month(1..12): {tmax_c, tmin_c, rain_prob, fog_prob, days, years}}.

    A year counts toward a month when it has at least 20 days with a precipitation figure. Fewer than `min_years`
    such years for any month raises ViewError: a thin normal is worse than none.
    """
    by_month = defaultdict(lambda: defaultdict(list))   # month -> year -> [(tmax, tmin, mm, code)]
    cols = [daily.get(k) or [] for k in ("temperature_2m_max", "temperature_2m_min", "precipitation_sum", "weather_code")]
    for i, day in enumerate(daily.get("time") or []):
        row = tuple(c[i] if i < len(c) else None for c in cols)
        by_month[int(day[5:7])][int(day[:4])].append(row)
    out = {}
    for m in range(1, 13):
        years = {y: rows for y, rows in by_month[m].items() if sum(r[2] is not None for r in rows) >= 20}
        if len(years) < min_years:
            raise ViewError(f"month {m}: {len(years)} usable years, need {min_years}")
        rows = [r for rs in years.values() for r in rs]
        med = lambda i: round(median(v), 1) if (v := [r[i] for r in rows if r[i] is not None]) else None
        wet = [r[2] for r in rows if r[2] is not None]
        fog = [r[3] in FOG_CODES for r in rows if r[3] is not None]
        out[m] = {"tmax_c": med(0), "tmin_c": med(1), "rain_prob": round(sum(x >= rain_mm for x in wet) / len(wet), 3),
                  "fog_prob": round(sum(fog) / len(fog), 3) if fog else None,
                  "days": len(rows), "years": len(years)}
    if not any(v["fog_prob"] for v in out.values()):   # a reanalysis that never reports fog cannot say a month has none
        for v in out.values():
            v["fog_prob"] = None
    return out


def build(city: str) -> dict:
    """Fetch (or reuse the raw answer under views/raw/), compute, write data/<city>/views/climate.json."""
    cfg = config()["climate"]
    lat, lng = center(city_area(city))
    start, end = f"{cfg['start_year']}-01-01", f"{cfg['end_year']}-12-31"
    raw_path = views_dir(city) / "raw" / f"climate_{start[:4]}_{end[:4]}_{lat:.3f}_{lng:.3f}.json"
    doc = read_json(raw_path)
    fresh = doc is None
    if fresh:
        url = (f"{cfg['url']}?latitude={lat:.4f}&longitude={lng:.4f}&start_date={start}&end_date={end}"
               f"&daily={DAILY}&timezone={urllib.parse.quote('Asia/Bangkok')}")
        doc = fetch_json(url, timeout_s=180)
    months = normals(doc.get("daily") or {}, cfg["rain_mm"], cfg["min_years"])
    if fresh:   # only an answer that made a valid view is kept
        write_json(raw_path, doc)
    view = {"city": city, "source": "open-meteo-archive", "center": {"lat": lat, "lng": lng},
            "years": [cfg["start_year"], cfg["end_year"]], "rain_mm": cfg["rain_mm"], "built_at": now(),
            "months": {str(m): v for m, v in months.items()}}
    write_json(path(city), view)
    return view


def load(city: str) -> dict | None:
    """The built view, or None when it was never built."""
    return read_json(path(city))
