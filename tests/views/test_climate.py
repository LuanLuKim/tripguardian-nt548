import json
from datetime import date, timedelta

import pytest

from corpus.views import climate
from corpus.views.common import ViewError


def synthetic(first=2015, last=2025, rain_every=4):
    """Every day of first..last: tmax 30, tmin 15 (December: tmax 20), rain 5 mm on every `rain_every`-th day, fog on 1st of month."""
    times, tmax, tmin, mm, code = [], [], [], [], []
    d = date(first, 1, 1)
    n = 0
    while d <= date(last, 12, 31):
        times.append(d.isoformat())
        tmax.append(20.0 if d.month == 12 else 30.0)
        tmin.append(15.0)
        mm.append(5.0 if n % rain_every == 0 else 0.0)
        code.append(45 if d.day == 1 else 3)
        d += timedelta(days=1)
        n += 1
    return {"time": times, "temperature_2m_max": tmax, "temperature_2m_min": tmin, "precipitation_sum": mm,
            "weather_code": code}


def test_normals_cover_twelve_months_from_eleven_years():
    out = climate.normals(synthetic(), 1.0, 10)
    assert sorted(out) == list(range(1, 13))
    assert all(v["years"] == 11 for v in out.values())
    assert out[7]["tmax_c"] == 30.0 and out[12]["tmax_c"] == 20.0 and out[1]["tmin_c"] == 15.0
    assert 0.2 < out[3]["rain_prob"] < 0.3
    assert 0.02 < out[3]["fog_prob"] < 0.05


def test_a_threshold_decides_what_a_rainy_day_is():
    assert climate.normals(synthetic(), 6.0, 10)[1]["rain_prob"] == 0.0


def test_missing_weather_codes_leave_fog_unknown_not_zero():
    d = synthetic()
    d.pop("weather_code")
    assert climate.normals(d, 1.0, 10)[5]["fog_prob"] is None


def test_fewer_than_ten_years_is_refused():
    with pytest.raises(ViewError):
        climate.normals(synthetic(2020, 2025), 1.0, 10)


def test_build_writes_the_view_and_reuses_the_raw_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    calls = []
    monkeypatch.setattr(climate, "fetch_json", lambda url, **kw: calls.append(url) or {"daily": synthetic()})
    view = climate.build("dalat")
    assert len(view["months"]) == 12 and view["years"] == [2015, 2025]
    assert "latitude=11.95" in calls[0] and "daily=" in calls[0]
    assert json.loads((tmp_path / "dalat" / "views" / "climate.json").read_text())["months"]["1"]["years"] == 11
    climate.build("dalat")
    assert len(calls) == 1
    assert climate.load("dalat")["city"] == "dalat"


def test_the_city_comes_from_config_not_from_the_code():
    with pytest.raises(ViewError):
        climate.build("atlantis")


def test_a_source_that_never_reports_fog_leaves_fog_unknown_in_every_month():
    d = synthetic()
    d["weather_code"] = [3] * len(d["time"])
    assert all(v["fog_prob"] is None for v in climate.normals(d, 1.0, 10).values())
