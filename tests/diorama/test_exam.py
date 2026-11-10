import json
from datetime import datetime

import pytest
from PIL import Image

from auto3d import Place, cli, steps
from auto3d.exam import INPUTS, copy_inputs, exam_metrics, run_exam


def test_exam_metrics():
    approved = {"objects": [
        {"type": "house", "w": 10, "d": 20, "position": [1, 8, 2]},
        {"type": "house", "w": 1, "d": 2, "position": [99, 0, 99]},
        {"type": "tree"},
    ], "hotspots": [{"id": "a"}, {"id": "b"}]}
    built = {"objects": [
        {"type": "house", "w": 20, "d": 20, "position": [4, 100, 6]},
        {"type": "bench"}, {"type": "bench"},
    ], "hotspots": [{"id": "a"}]}
    metrics = exam_metrics(approved, built)
    assert metrics["objects_by_type"] == {
        "approved": {"house": 2, "tree": 1}, "exam": {"house": 1, "bench": 2}}
    assert metrics["centroid_offset_m"] == pytest.approx(5)
    assert metrics["hotspots"] == {"approved": 2, "exam": 1}


def test_exam_centroid_xz_and_unknown():
    a = {"objects": [{"type": "villa", "w": 8, "d": 9, "x": 0, "z": 0}]}
    b = {"objects": [{"type": "villa", "w": 8, "d": 9, "x": 3, "z": 4}]}
    assert exam_metrics(a, b)["centroid_offset_m"] == 5
    assert exam_metrics(a, {})["centroid_offset_m"] is None
    del b["objects"][0]["x"]
    assert exam_metrics(a, b)["centroid_offset_m"] is None


def test_copy_inputs_only_allowlisted_files(tmp_path):
    source, target = tmp_path / "approved", tmp_path / "exam"
    source.mkdir()
    (source / "photos").mkdir()
    (source / "photos/g00.jpg").write_bytes(b"photo")
    for name in (*INPUTS[1:], "place.json", "COLOURS.md", "NOTES_coord.md", "summary.json", "auto3d.json"):
        (source / name).write_text(name)
    copy_inputs(source, target)
    assert {p.name for p in target.iterdir()} == set(INPUTS)
    assert (target / "photos/g00.jpg").read_bytes() == b"photo"
    (target / "photos/g00.jpg").write_bytes(b"changed")
    assert (source / "photos/g00.jpg").read_bytes() == b"photo"
    with pytest.raises(FileExistsError):
        copy_inputs(source, target)


def test_copy_inputs_missing_optional_files(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    (source / "meta.json").write_text("{}")
    copy_inputs(source, target)
    assert [p.name for p in target.iterdir()] == ["meta.json"]


def test_copy_inputs_cleans_partial_copy_without_touching_source(tmp_path, monkeypatch):
    from auto3d import exam

    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    (source / "photos").mkdir()
    (source / "photos/g00.jpg").write_bytes(b"photo")
    (source / "meta.json").write_text("{}")

    def fail(*args):
        raise OSError("copy failed")

    monkeypatch.setattr(exam.shutil, "copy2", fail)
    with pytest.raises(OSError, match="copy failed"):
        copy_inputs(source, target)
    assert not target.exists()
    assert (source / "photos/g00.jpg").read_bytes() == b"photo"
    assert (source / "meta.json").read_text() == "{}"


@pytest.mark.parametrize("keep", [False, True])
def test_exam_pipeline_isolated_inputs_report_and_gallery(isolated, monkeypatch, keep):
    monkeypatch.setattr(cli, "REPO", isolated / "repo")
    original = Place("p")
    original.dir.mkdir(parents=True)
    answer = {"objects": [{"type": "house", "w": 4, "d": 5, "x": 0, "z": 0}], "hotspots": []}
    (original.dir / "place.json").write_text(json.dumps(answer))
    (original.dir / "meta.json").write_text(json.dumps(dict(fid="0x1_0x2", name="A place", reviews=42)))
    (original.dir / "COLOURS.md").write_text("answer")
    seen = []

    def pipeline(place):
        seen.append(place.s.copy())
        assert not (place.dir / "place.json").exists()
        assert not (place.dir / "COLOURS.md").exists()
        (place.dir / "place.json").write_text(json.dumps(answer))
        place.s.update(scores=[.5, .8], rounds=2, tokens=25)
        place.stage("ready")

    def render(place, **kwargs):
        image = isolated / f"{place.slug}.png"
        Image.new("RGB", (20, 20), "red").save(image)
        return image, [image]

    monkeypatch.setattr(cli, "pipeline", pipeline)
    monkeypatch.setattr(steps, "render", render)
    run_exam(["p"], ["agent", "function"], keep)
    assert {s["builder"] for s in seen} == {"agent", "function"}
    assert all(s["stage"] == "gate" and s["fid"] == "0x1_0x2" and s["name"] == "A place"
               and s["reviews"] == 42 for s in seen)
    date = datetime.now().strftime("%Y%m%d")
    rows = json.loads((isolated / f"batch/exam_{date}.json").read_text())
    assert len(rows) == 2
    assert all(r["checklist_score"] == .8 and r["rounds"] == 2 and r["tokens"] == 25
               and r["stage"] == "ready" for r in rows)
    with Image.open(isolated / f"repo/frontend_images/space3d-exam-{date}.jpg") as image:
        assert image.size == (2400, 480)
    assert (isolated / "places/x_agent_p").exists() == keep
    assert (isolated / "places/x_function_p").exists() == keep
    assert json.loads((original.dir / "place.json").read_text()) == answer


def test_exam_refuses_existing_targets_before_pipeline(isolated, monkeypatch):
    original = Place("p")
    original.dir.mkdir(parents=True)
    (original.dir / "place.json").write_text("{}")
    (original.dir / "meta.json").write_text("{}")
    target = Place("x_agent_p")
    target.save()
    before = target.state_file.read_bytes()
    with pytest.raises(SystemExit, match="already exists"):
        run_exam(["p"], ["agent", "function"])
    assert target.state_file.read_bytes() == before
