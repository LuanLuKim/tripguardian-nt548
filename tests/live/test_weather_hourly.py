from datetime import date

import pytest

import live
from live import settings
from live.weather import hourly


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))


@pytest.fixture
def cfg():
    settings.load.cache_clear()
    yield settings.load(settings.PATH)
    settings.load.cache_clear()


TODAY = lambda: date(2026, 10, 28)


def doc(day, a, b):
    """a, b: per hour 0..23 tuples (prob %, mm, gust, code, visibility m) of best_match and gfs_seamless."""
    out = {"time": [f"{day}T{h:02d}:00" for h in range(24)]}
    for model, rows in (("best_match", a), ("gfs_seamless", b)):
        for i, key in enumerate(("precipitation_probability", "precipitation", "wind_gusts_10m", "weather_code",
                                 "visibility")):
            out[f"{key}_{model}"] = [r[i] if r else None for r in rows]
    return {"hourly": out}


DRY = (0, 0.0, 10.0, 2, 20000.0)


def test_hourly_reads_both_models_and_marks_rain_storm_fog_and_disagreement(cfg, monkeypatch):
    a = [DRY] * 24
    b = [DRY] * 24
    a[14] = (85, 3.0, 20.0, 61, 9000.0)
    b[14] = (80, 2.0, 18.0, 61, 9000.0)
    a[15] = (90, 9.0, 55.0, 95, 9000.0)          # thunderstorm
    b[15] = (20, 0.0, 15.0, 3, 20000.0)          # the second model sees nothing -> disagreement
    a[6] = (0, 0.0, 5.0, 45, 300.0)              # fog
    b[6] = (0, 0.0, 5.0, 3, 800.0)
    seen = []
    monkeypatch.setattr(hourly, "get_json", lambda url, ua, t: seen.append(url) or doc("2026-10-29", a, b))
    r = live.weather_hourly(11.94, 108.44, "2026-10-29", cfg, today_fn=TODAY)
    assert "models=best_match,gfs_seamless" in seen[0] and "hourly=" in seen[0]
    h = r["hours"]
    assert h[14]["rain_prob"] == 0.85 and h[14]["rain_mm"] == 3.0 and not h[14]["disagree"]
    assert h[15]["storm"] is True and h[15]["gust_kmh"] == 55.0 and h[15]["disagree"] is True
    assert h[6]["fog"] is True and h[9]["fog"] is False
    assert r["source"] == "open-meteo" and r["fetched_at"]


def test_a_missing_value_stays_none_and_the_other_model_fills_only_its_own_slot(cfg, monkeypatch):
    a = [None] * 24
    b = [DRY] * 24
    monkeypatch.setattr(hourly, "get_json", lambda url, ua, t: doc("2026-10-29", a, b))
    h = live.weather_hourly(11.94, 108.44, "2026-10-29", cfg, today_fn=TODAY)["hours"]
    assert h[10]["rain_prob"] == 0.0 and h[10]["fog"] is False   # best_match silent -> the second model answers
    a2 = [None] * 24
    monkeypatch.setattr(hourly, "get_json", lambda url, ua, t: doc("2026-10-30", a2, [None] * 24))
    h2 = live.weather_hourly(11.94, 108.44, "2026-10-30", cfg, today_fn=TODAY)["hours"]
    assert h2[10] == {"rain_prob": None, "rain_mm": None, "gust_kmh": None, "storm": None, "fog": None,
                      "disagree": None}


def test_a_day_beyond_the_forecast_horizon_has_no_hourly_forecast(cfg, monkeypatch):
    monkeypatch.setattr(hourly, "get_json", lambda *a: pytest.fail("no network beyond the horizon"))
    assert live.weather_hourly(11.94, 108.44, "2026-12-30", cfg, today_fn=TODAY) is None
