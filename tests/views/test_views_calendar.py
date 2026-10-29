from datetime import date

import pytest

from corpus.views import calendar
from corpus.views.common import ViewError


def by_date(ds):
    return {d["date"]: d for d in ds}


@pytest.mark.parametrize("year,solar", [(2026, "2026-02-17"), (2027, "2027-02-06"), (2028, "2028-01-26")])
def test_tet_falls_on_lunar_new_year_and_is_a_holiday(year, solar):
    table = by_date(calendar.days(2026, 2028))
    day = table[solar]
    assert day["lunar"] == {"year": year, "month": 1, "day": 1, "leap": False}
    assert day["holiday"] and "Tết" in day["holiday"]


def test_the_days_before_and_after_tet_are_holidays_and_a_normal_day_is_not():
    table = by_date(calendar.days(2026, 2026))
    assert table["2026-02-16"]["holiday"] and table["2026-02-18"]["holiday"]
    assert table["2026-03-11"]["holiday"] is None
    assert table["2026-09-02"]["holiday"] and table["2026-01-01"]["holiday"]


def test_every_day_of_the_range_is_present_once():
    out = calendar.days(2026, 2027)
    assert len(out) == 365 * 2 and len({d["date"] for d in out}) == len(out)


def test_sources_are_injectable_and_a_bad_range_is_refused():
    out = calendar.days(2026, 2026, holiday_fn=lambda c, ys: {date(2026, 1, 1): "X"}, lunar_fn=lambda d: {"m": 1})
    assert out[0] == {"date": "2026-01-01", "lunar": {"m": 1}, "holiday": "X"} and out[1]["holiday"] is None
    with pytest.raises(ViewError):
        calendar.days(2027, 2026)


def test_build_writes_the_view_for_the_configured_years(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    view = calendar.build("dalat")
    assert view["country"] == "VN" and view["years"] == [2025, 2030]
    assert calendar.load("dalat")["days"][0]["date"] == "2025-01-01"
    assert (tmp_path / "dalat" / "views" / "calendar.json").exists()
