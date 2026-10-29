import pytest

import live
from live import settings
from live.osrm import client

PTS = [(11.94, 108.43), (11.82, 108.47), (11.95, 108.44)]


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))


@pytest.fixture
def cfg():
    settings.load.cache_clear()
    yield settings.load(settings.PATH)
    settings.load.cache_clear()


def step(name, *lnglat):
    return {"name": name, "geometry": {"coordinates": [list(p) for p in lnglat]}}


def test_route_steps_names_the_roads_of_every_leg(cfg, monkeypatch):
    body = {"code": "Ok", "routes": [{"legs": [
        {"steps": [step("Trần Phú", (108.43, 11.94), (108.44, 11.93)), step("Đèo Mimosa", (108.44, 11.93), (108.47, 11.82))]},
        {"steps": [step("", (108.47, 11.82), (108.45, 11.9)), step("Quốc lộ 20", (108.45, 11.9), (108.44, 11.95))]}]}]}
    seen = []
    monkeypatch.setattr(client, "get_json", lambda url, ua, t: seen.append(url) or body)
    r = live.route_steps(PTS, "motorbike", cfg)
    assert "steps=true" in seen[0]
    assert [[s["name"] for s in leg] for leg in r["legs"]] == [["Trần Phú", "Đèo Mimosa"], ["", "Quốc lộ 20"]]
    assert r["legs"][0][1]["coords"] == [[11.93, 108.44], [11.82, 108.47]]   # lat, lng
    assert r["source"] == "osrm"
    live.route_steps(PTS, "motorbike", cfg)
    assert len(seen) == 1                                                     # cached


def test_route_steps_refuses_a_bad_answer(cfg, monkeypatch):
    monkeypatch.setattr(client, "get_json", lambda url, ua, t: {"code": "NoRoute"})
    with pytest.raises(live.Unavailable):
        live.route_steps(PTS, "motorbike", cfg)
