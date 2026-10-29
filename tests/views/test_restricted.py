import json

import pytest

from corpus.views import restricted
from corpus.views.common import ViewError


def geom(*pts):
    return [{"lat": lat, "lon": lng} for lat, lng in pts]


SQUARE = geom((11.90, 108.40), (11.90, 108.42), (11.92, 108.42), (11.92, 108.40), (11.90, 108.40))


def way(id, tags, g=SQUARE):
    return {"type": "way", "id": id, "tags": tags, "geometry": g}


def test_a_closed_military_way_becomes_a_polygon_with_its_name():
    f = restricted.feature(way(1, {"landuse": "military", "name": "Doanh trại"}))
    assert f["geometry"]["type"] == "Polygon"
    assert f["properties"] == {"osm": "way/1", "kind": "military", "name": "Doanh trại", "landuse": "military"}


def test_a_no_access_area_is_kept_but_a_looping_road_or_building_is_not():
    assert restricted.feature(way(2, {"access": "no", "leisure": "park"}))["properties"]["kind"] == "no_access"
    assert restricted.feature(way(3, {"access": "no", "highway": "service"})) is None
    assert restricted.feature(way(4, {"access": "no", "barrier": "fence"})) is None


def test_an_open_way_is_not_an_area():
    assert restricted.feature(way(5, {"landuse": "military"}, geom((11.9, 108.4), (11.9, 108.5), (12.0, 108.5)))) is None


def test_a_relation_joins_its_outer_ways_and_cuts_its_hole():
    a = geom((11.90, 108.40), (11.90, 108.42), (11.92, 108.42))
    b = geom((11.92, 108.42), (11.92, 108.40), (11.90, 108.40))
    hole = geom((11.905, 108.405), (11.905, 108.410), (11.910, 108.410), (11.910, 108.405), (11.905, 108.405))
    rel = {"type": "relation", "id": 9, "tags": {"military": "airfield"},
           "members": [{"type": "way", "role": "outer", "geometry": a}, {"type": "way", "role": "outer", "geometry": b},
                       {"type": "way", "role": "inner", "geometry": hole}]}
    f = restricted.feature(rel)
    assert f["geometry"]["type"] == "Polygon" and len(f["geometry"]["coordinates"]) == 2
    assert restricted.hits(11.915, 108.41, [f]) and not restricted.hits(11.907, 108.407, [f])


def test_a_feature_carries_its_bbox_and_a_point_outside_it_is_never_tested_against_the_polygon():
    f = restricted.feature(way(1, {"landuse": "military"}))
    assert f["bbox"] == [108.40, 11.90, 108.42, 11.92]
    f["geometry"] = None   # would raise if hits() looked at the polygon of a point outside the bbox
    assert restricted.hits(12.5, 109.0, [f]) == []


def test_hits_returns_properties_of_every_area_holding_the_point():
    f = restricted.feature(way(1, {"landuse": "military", "name": "A"}))
    assert [h["name"] for h in restricted.hits(11.91, 108.41, [f])] == ["A"]
    assert restricted.hits(11.95, 108.41, [f]) == []


def test_the_overpass_query_covers_the_cities_bbox_and_every_tag():
    q = restricted.query([11.78, 108.30, 12.12, 108.66], 60)
    assert q.count("(11.78,108.3,12.12,108.66)") == 6
    assert '"landuse"="military"' in q and '["military"]' in q and '"access"="no"' in q and "out geom" in q


def test_build_writes_geojson_and_reuses_the_raw_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    calls = []
    monkeypatch.setattr(restricted, "fetch_json", lambda url, **kw: calls.append(kw) or {"elements": [way(1, {"landuse": "military"})]})
    out = restricted.build("dalat")
    assert out["type"] == "FeatureCollection" and len(out["features"]) == 1 and out["bbox"][0] == 11.78
    restricted.build("dalat")
    assert len(calls) == 1
    assert json.loads((tmp_path / "dalat" / "views" / "restricted.geojson").read_text())["features"][0]["properties"]["osm"] == "way/1"
    assert len(restricted.load("dalat")) == 1


def test_an_answer_without_elements_is_an_error_not_an_empty_view(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(restricted, "fetch_json", lambda url, **kw: {"remark": "runtime error: timeout"})
    with pytest.raises(ViewError):
        restricted.build("dalat")
    assert restricted.load("dalat") is None
