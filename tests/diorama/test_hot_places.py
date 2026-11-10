import json

from batch import hot_places


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_hot_rows_tolerate_nulls_and_ignore_stale(isolated, monkeypatch, capsys):
    repo = isolated / "repo"
    monkeypatch.setattr(hot_places, "REPO", repo)
    monkeypatch.setattr(hot_places, "DATA", isolated)
    write(repo / "data/serving/places.json", {"records": [
        {"id": "f:id", "identity": {"name": "A", "reviews": None}},
        {"id": "f:two", "identity": {"name": "B", "reviews": 2000}},
    ]})
    write(isolated / "batch/inventory.json", [{"fid": "f_id", "kit": None}, {"fid": "f_two", "kit": None}])
    write(repo / "data/gmaps/photo_scenes/f_two.json", {"photos": [{"scene": "exterior"}] * 6
          + [{"scene": "view"}] * 2 + [{"scene": "exterior", "stale": True}] * 5})
    assert hot_places.rows(0)[0]["tier"] == "B"
    assert hot_places.rows(0)[1]["reviews"] == 0
    assert hot_places.rows(0)[0]["kit"] is None
    hot_places.main(["0", "--json", "queue.json"])
    assert len(json.loads((isolated / "queue.json").read_text())) == 2
    assert capsys.readouterr().out == ""
    hot_places.main(["0"])
    assert "B" in capsys.readouterr().out
