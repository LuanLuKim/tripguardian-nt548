import json

from auto3d import gate


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def photos(ext=6, view=2):
    return [{"name": f"g{i:02d}.jpg", "scene": "exterior" if i < ext else "view"} for i in range(ext + view)]


def test_gate_counts_exterior_plus_view(isolated):
    write(gate.REPO / "data/gmaps/photo_scenes/fid.json", {"photos": photos()})
    result = gate.check_fid("fid")
    assert result == gate.Gate(True, 6, 2, "")


def test_gate_drops_neighbour_photos(isolated):
    write(isolated / "places/p/photos_index.json", photos())
    assert gate.check_place("p", []).ok
    for drop in (["g03"], ["g03.jpg"]):
        result = gate.check_place("p", drop)
        assert not result.ok
        assert result.ext + result.view == 7
        assert result.reason == "no_exterior_evidence"


def test_gate_ignores_stale(isolated):
    values = photos()
    values[0]["stale"] = True
    values.append({"scene": "exterior", "keep": False})
    write(gate.REPO / "data/gmaps/photo_scenes/fid.json", {"photos": values})
    write(isolated / "places/p/photos_index.json", values)
    assert gate.check_fid("fid") == gate.Gate(False, 5, 2, "no_exterior_evidence")
    assert not gate.check_place("p", []).ok


def test_gate_missing_scenes(isolated):
    assert gate.check_fid("missing").reason == "no_photo_scenes"
    assert gate.check_place("missing", []).reason == "no_photo_scenes"


def test_gate_reads_config_threshold(isolated, monkeypatch):
    monkeypatch.setattr(gate, "config", lambda: {"evidence_min": 9})
    write(isolated / "places/p/photos_index.json", photos())
    assert not gate.check_place("p", []).ok
