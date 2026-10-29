"""live reads data/<city>/views/ first; the hand-entered YAML is the layer above (holidays) or around (climate) it."""

import importlib
import json
from datetime import date

import pytest

from live import settings


holidays_mod = importlib.import_module("live.holidays")
climate_mod = importlib.import_module("live.weather.climate")


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    settings.load.cache_clear()
    return tmp_path


def write_view(root, name, doc):
    f = root / "dalat" / "views" / f"{name}.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(doc), encoding="utf-8")


def yaml_file(tmp_path, text):
    f = tmp_path / "c.yaml"
    f.write_text(text, encoding="utf-8")
    return f


def months(prob):
    return {"months": {str(m): {"rain_prob": prob(m)} for m in range(1, 13)}}


def test_the_climate_view_beats_the_hand_estimate(data_dir, tmp_path):
    write_view(data_dir, "climate", months(lambda m: 0.9))
    f = yaml_file(tmp_path, "rain_prob_by_month: {6: 0.1}\n")
    assert climate_mod.climate(["2027-06-15"], f)["2027-06-15"] == {"rain_prob": 0.9, "source": "climate", "fetched_at": None}


def test_a_hand_override_beats_the_view_for_its_month_only(data_dir, tmp_path):
    write_view(data_dir, "climate", months(lambda m: 0.9))
    f = yaml_file(tmp_path, "rain_prob_override_by_month: {6: 0.4}\n")
    got = climate_mod.climate(["2027-06-15", "2027-07-15"], f)
    assert got["2027-06-15"]["rain_prob"] == 0.4 and got["2027-07-15"]["rain_prob"] == 0.9


def test_without_a_view_the_hand_estimate_answers_and_a_missing_month_is_none(tmp_path):
    f = yaml_file(tmp_path, "rain_prob_by_month: {6: 0.1}\n")
    got = climate_mod.climate(["2027-06-15", "2027-07-15"], f)
    assert got["2027-06-15"]["rain_prob"] == 0.1 and got["2027-07-15"]["rain_prob"] is None


def test_a_month_the_view_does_not_know_falls_back_not_to_zero(data_dir, tmp_path):
    write_view(data_dir, "climate", {"months": {"6": {"rain_prob": None}}})
    f = yaml_file(tmp_path, "rain_prob_by_month: {6: 0.1}\n")
    assert climate_mod.climate(["2027-06-15"], f)["2027-06-15"]["rain_prob"] == 0.1


def test_a_broken_view_file_is_ignored_like_a_missing_one(data_dir, tmp_path):
    (data_dir / "dalat" / "views").mkdir(parents=True)
    (data_dir / "dalat" / "views" / "climate.json").write_text("{not json", encoding="utf-8")
    f = yaml_file(tmp_path, "rain_prob_by_month: {6: 0.1}\n")
    assert climate_mod.climate(["2027-06-15"], f)["2027-06-15"]["rain_prob"] == 0.1


def test_the_calendar_view_supplies_holidays_the_yaml_lacks(data_dir, tmp_path):
    write_view(data_dir, "calendar", {"days": [{"date": "2029-02-16", "holiday": "Tết Nguyên Đán"},
                                                {"date": "2029-02-17", "holiday": None}]})
    f = yaml_file(tmp_path, "holidays: {}\n")
    assert holidays_mod.holidays([date(2029, 2, 16), date(2029, 2, 17)], f) == {date(2029, 2, 16): "Tết Nguyên Đán"}


def test_a_yaml_name_replaces_the_views_name_for_that_date(data_dir, tmp_path):
    write_view(data_dir, "calendar", {"days": [{"date": "2029-02-16", "holiday": "view name"}]})
    f = yaml_file(tmp_path, 'holidays:\n  "2029-02-16": hand name\n  "2029-03-01": only in file\n')
    got = holidays_mod.holidays([date(2029, 2, 16), date(2029, 3, 1)], f)
    assert got == {date(2029, 2, 16): "hand name", date(2029, 3, 1): "only in file"}


def test_the_view_city_is_a_setting_not_a_constant(data_dir, tmp_path, monkeypatch):
    other = data_dir / "hue" / "views"
    other.mkdir(parents=True)
    (other / "calendar.json").write_text(json.dumps({"days": [{"date": "2029-02-16", "holiday": "H"}]}), encoding="utf-8")
    monkeypatch.setattr(settings, "load", lambda *a, **k: type("S", (), {"views_city": "hue"})())
    f = yaml_file(tmp_path, "holidays: {}\n")
    assert holidays_mod.holidays([date(2029, 2, 16)], f) == {date(2029, 2, 16): "H"}

