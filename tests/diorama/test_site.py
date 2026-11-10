import copy
import json
from types import SimpleNamespace

import pytest

from auto3d import Place, fit_site, steps
from paths import DATA


def test_big_site_shrinks_with_margin_without_mutating_input():
    place = {"site": {"width": 200, "depth": 180}, "objects": [
        {"type": "church_gabled", "position": [0, 0, 0], "size": [20, 30]},
        {"type": "parish_ground", "position": [0, 0, 0], "size": [200, 180]},
    ]}
    before = copy.deepcopy(place)
    fitted, report = fit_site(place)
    assert fitted["site"] == {"width": 32, "depth": 42, "centerX": 0, "centerZ": 0}
    assert report["changed"]
    assert report["old"]["width"] == 200
    assert report["new"]["depth"] == 42
    assert place == before
    assert fit_site(fitted)[0] == fitted


@pytest.mark.parametrize("width,depth", [(32, 42), (40, 52.5), (10, 12)])
def test_tight_site_unchanged_and_never_grows(width, depth):
    place = {"site": {"width": width, "depth": depth, "centerX": 3},
             "objects": [{"x": 0, "z": 0, "w": 20, "d": 30}]}
    fitted, report = fit_site(place)
    assert fitted == place
    assert not report["changed"]


def test_recentre_and_only_shrink_oversized_axis():
    place = {"site": {"width": 200, "depth": 10},
             "objects": [{"x": 45, "z": -25, "width": 10, "depth": 8}]}
    fitted, _ = fit_site(place)
    assert fitted["site"] == {"width": 22, "depth": 10, "centerX": 45, "centerZ": -25}


def test_unknown_objects_count_as_xz_points():
    place = {"site": {"width": 200, "depth": 200},
             "objects": [{"type": "unknown", "x": -20, "z": 5},
                         {"type": "unknown", "position": [40, 100, 25]}]}
    fitted, _ = fit_site(place)
    assert fitted["site"] == {"width": 72, "depth": 32, "centerX": 10, "centerZ": 15}


@pytest.mark.parametrize("kind,rotation,size", [
    ("church_gabled", 90, [10, 20]), ("villa", 1.5707963267948966, [10, 50, 20]),
    ("stay_building", 1.5707963267948966, [10, 50, 20]),
])
def test_rotated_footprints(kind, rotation, size):
    fitted, _ = fit_site({"site": {"width": 200, "depth": 200}, "objects": [
        {"type": kind, "position": [30, 0, 40], "rotation": rotation, "size": size}]})
    assert fitted["site"]["width"] == pytest.approx(32)
    assert fitted["site"]["depth"] == pytest.approx(22)


def test_local_outline_radius_hotspots_and_route_points():
    fitted, report = fit_site({"site": {"width": 500, "depth": 500}, "objects": [
        {"type": "church_gabled", "position": [10, 0, 20], "rotation": 90,
         "outline": [[-5, -10], [5, -10], [5, 10], [-5, 10]]},
        {"type": "formal_garden", "position": [-10, 0, 0], "radius": 5}],
        "hotspots": [{"target": [60, 100, 50], "camera": [1000, 100, 1000]}],
        "route": [[[-30, -20], [0, 0]], [[0, 0], [40, 30]]]})
    assert report["bbox"] == [-30, 60, -20, 50]
    assert fitted["site"] == {"width": 102, "depth": 82, "centerX": 15, "centerZ": 15}


@pytest.mark.parametrize("kind,points", [
    ("garden_path", [[0, 0], [0, 30]]),
    ("nature_path", [[0, 99, 0], [0, 99, 30]]),
    ("stay_paving", [[0, 99, 0], [0, 99, 30]]),
])
def test_local_paths_include_width(kind, points):
    fitted, _ = fit_site({"site": {"width": 300, "depth": 300}, "objects": [
        {"type": kind, "position": [20, 0, 10], "points": points, "width": 4}]})
    assert fitted["site"] == {"width": 16, "depth": 46, "centerX": 20, "centerZ": 25}


def test_non_site_ground_is_preserved_even_without_route_association():
    fitted, _ = fit_site({"site": {"width": 300, "depth": 300}, "objects": [
        {"type": "parish_ground", "position": [30, 0, 0], "size": [80, 100]},
        {"x": 0, "z": 0}]})
    assert fitted["site"] == {"width": 92, "depth": 112, "centerX": 30, "centerZ": 0}


def test_site_sized_ground_carrying_paths_is_not_discarded():
    place = {"site": {"width": 200, "depth": 200}, "objects": [
        {"type": "parish_ground", "size": [200, 200], "paths": [[[0, 0], [10, 0]]]},
        {"x": 0, "z": 0}], "route": [[[0, 0], [10, 0]]]}
    assert fit_site(place)[0] == place


def test_empty_and_missing_site_unchanged():
    for place in ({}, {"site": {"width": 200, "depth": 200}, "objects": []}):
        fitted, report = fit_site(place)
        assert fitted == place
        assert not report["changed"]
        assert report["old"] == report["new"]


def test_world_space_villa_drive_does_not_include_origin_or_apply_transform():
    fitted, report = fit_site({"site": {"width": 500, "depth": 500}, "objects": [
        {"type": "villa_drive", "position": [100, 0, 100], "rotation": 1.5,
         "points": [[50, 99, 60], [70, 99, 80]], "width": 4}]}, margin_m=2)
    assert report["bbox"] == [48, 72, 58, 82]
    assert fitted["site"] == {"width": 28, "depth": 28, "centerX": 60, "centerZ": 70}


@pytest.mark.parametrize("margin", [-1, float("inf"), float("nan")])
def test_invalid_margin_rejected(margin):
    with pytest.raises(ValueError):
        fit_site({}, margin)


def test_normalize_fits_site_before_route_fix_and_logs_report(isolated, monkeypatch):
    place = Place("fit")
    place.save()
    file = place.dir / "place.json"
    file.write_text(json.dumps({"site": {"width": 200, "depth": 200},
                                "objects": [{"id": "subject", "x": 20, "z": 30}]}))

    def route_fix(command, timeout):
        assert "route_fix.mjs" in command[1]
        assert json.loads(file.read_text())["site"]["width"] == 12
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(steps, "run", route_fix)
    assert steps.normalize(place)
    assert place.s["history"][-1]["site_fit"]["changed"]


@pytest.mark.parametrize("slug", ["conga", "dinh3", "camly", "linhphuoc", "linhson"])
def test_approved_place_regression_read_only(slug):
    file = DATA / "places" / slug / "place.json"
    if not file.exists():
        pytest.skip(f"Approved place absent: {slug}")
    original = file.read_bytes()
    place = json.loads(original)
    fitted, report = fit_site(place)
    print(f"{slug}: {json.dumps(report, sort_keys=True)}")
    for axis in ("width", "depth"):
        assert abs(fitted["site"][axis] / place["site"][axis] - 1) < .1
    assert file.read_bytes() == original
