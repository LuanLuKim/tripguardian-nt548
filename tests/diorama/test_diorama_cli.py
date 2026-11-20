import json
from types import ModuleType

import pytest

from auto3d import Place, cli


def test_run_resumes_failed_stage_keeps_notes(isolated, monkeypatch):
    p = Place("p")
    notes = {"kit": "villa", "signature": [{"id": "s1"}]}
    p.s.update(notes=notes, scores=[.6], rounds=2)
    p.stage("failed:shoot")
    (p.dir / "place.boot.json").write_text('{"saved": true}')
    seen = []

    def pipeline(place, **kwargs):
        seen.append(place.s["stage"])
        assert place.s["notes"] == notes
        assert place.s["scores"] == [.6] and place.s["rounds"] == 2

    monkeypatch.setattr(cli, "pipeline", pipeline)
    cli.main(["run", "p"])
    assert seen == ["shoot"]
    saved = Place("p")
    assert saved.s["notes"] == notes
    assert saved.s["history"][-1]["step"] == "resume"
    assert saved.s["history"][-1]["from"] == "failed:shoot"
    assert (p.dir / "place.boot.json").read_text() == '{"saved": true}'


@pytest.mark.parametrize("retries", [0, 1, 2])
def test_queue_retry_limit(isolated, monkeypatch, retries):
    import batch.hot_places

    p = Place("p")
    p.s.update(fid="0x1_0x2", retries=retries)
    p.stage("failed:review")
    monkeypatch.setattr(batch.hot_places, "rows", lambda *args: [
        {"fid": "0x1_0x2", "tier": "A"}])
    seen = []
    monkeypatch.setattr(cli, "pipeline", lambda place, **kwargs: seen.append(place.s.copy()))
    cli.main(["queue"])
    if retries == 2:
        assert seen == []
        assert Place("p").s["stage"] == "failed:review"
    else:
        assert len(seen) == 1 and seen[0]["stage"] == "review"
        assert Place("p").s["retries"] == retries + 1


def test_run_terminal_does_not_write_or_invoke_pipeline(isolated, monkeypatch, capsys):
    p = Place("p")
    p.s["fid"] = "0x1_0x2"
    p.stage("ready")
    before = p.state_file.read_bytes()
    monkeypatch.setattr(cli, "pipeline", lambda *a, **kw: pytest.fail("terminal place was run"))
    cli.main(["run", "0x1_0x2", "--builder", "function"])
    assert p.state_file.read_bytes() == before
    assert "p: ready" in capsys.readouterr().out


def test_run_redo_passes_builder_and_kit(isolated, monkeypatch):
    p = Place("p")
    p.stage("needs_human")
    seen = []
    monkeypatch.setattr(cli, "pipeline", lambda place, **kw: seen.append((place.s, kw)))
    cli.main(["run", "p", "--redo", "--builder", "function", "--kit", "villa"])
    assert seen[0][0]["builder"] == "function"
    assert seen[0][0]["kit_forced"] == "villa"
    assert seen[0][1] == {"redo": True}


@pytest.mark.parametrize("stage", ["gate", "build", "ready", "failed:boot"])
def test_extra_kit_after_notes_requires_redo(isolated, stage):
    p = Place("p")
    p.s["notes"] = {"kit": "storefront"}
    p.stage(stage)
    before = p.state_file.read_bytes()
    with pytest.raises(SystemExit):
        cli.main(["run", "p", "--extra-kit", "nature"])
    assert p.state_file.read_bytes() == before


def test_run_forces_extra_kits_with_redo(isolated, monkeypatch):
    p = Place("p")
    p.stage("ready")
    seen = []
    monkeypatch.setattr(cli, "pipeline", lambda place, **kw: seen.append((place.s.copy(), kw)))
    cli.main(["run", "p", "--redo", "--kit", "storefront", "--extra-kit", "nature", "--extra-kit", "garden"])
    assert seen[0][0]["extra_kits_forced"] == ["nature", "garden"]
    assert seen[0][1] == {"redo": True}
    assert Place("p").s["extra_kits_forced"] == ["nature", "garden"]


@pytest.mark.parametrize("args", [["--extra-kit", "nonexistent_kit"],
                                  ["--kit", "nature", "--extra-kit", "nature"],
                                  ["--extra-kit", "nature", "--extra-kit", "garden", "--extra-kit", "villa"]])
def test_invalid_cli_extra_kits(isolated, args):
    with pytest.raises(SystemExit):
        cli.main(["run", "p", *args])


def test_status_shows_extra_kits_only_when_present(isolated, capsys):
    p = Place("p")
    p.s["notes"] = {"kit": "storefront", "extra_kits": ["nature"]}
    p.stage("ready")
    q = Place("q")
    q.s["notes"] = {"kit": "villa"}
    q.stage("ready")
    cli.main(["status"])
    lines = capsys.readouterr().out.splitlines()
    assert "ready  [storefront+nature]" in lines[0]
    assert "[villa]" not in lines[1]


def test_exam_dispatch(isolated, monkeypatch):
    from auto3d import exam

    seen = []
    monkeypatch.setattr(exam, "run_exam", lambda *args: seen.append(args))
    cli.main(["exam", "p", "q", "--builders", "function", "--keep"])
    assert seen == [(["p", "q"], ["function"], True)]


def test_exam_invalid_builder(isolated):
    with pytest.raises(SystemExit):
        cli.main(["exam", "p", "--builders", "other"])


@pytest.mark.parametrize("keep", [False, True])
def test_calibrate_dispatch(isolated, monkeypatch, keep):
    from auto3d import exam

    seen = []
    monkeypatch.setattr(exam, "run_calibrate", lambda *args: seen.append(args))
    cli.main(["calibrate", "p", "q", *(["--keep"] if keep else [])])
    assert seen == [(["p", "q"], keep)]


def test_add_uses_public_api_and_prints_corpus_commands(isolated, monkeypatch, capsys):
    import sys

    fake = ModuleType("corpus.navigate")
    seen = []
    fake.enqueue_nominees = lambda city, rows: seen.append((city, rows)) or 1
    monkeypatch.setitem(sys.modules, "corpus.navigate", fake)
    cli.main(["add", "A real place"])
    assert seen == [("dalat", [{"name": "A real place", "area_hint": "", "aspect": "seed"}])]
    output = capsys.readouterr().out
    assert "python -m corpus gmaps resolve --city dalat" in output
    for step in ("filter", "counts", "list", "crawl", "qc", "photos", "photo_scenes"):
        assert f"python -m corpus gmaps {step} --city dalat" in output
    assert "python -m corpus build --city dalat" in output


def test_add_missing_api_message(isolated, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "corpus.navigate", ModuleType("corpus.navigate"))
    with pytest.raises(SystemExit, match="public corpus.navigate.enqueue_nominees API"):
        cli.main(["add", "A real place"])


def test_gallery_uses_v1_overview_tile(isolated):
    from PIL import Image

    p = Place("p")
    p.s["history"] = [{"step": "shoot", "sheet": "out_p/review_old.jpg"}]
    p.stage("ready")
    out = isolated / "out_p"
    out.mkdir()
    Image.new("RGB", (1280, 720), "red").save(out / "review_old.jpg")
    cli.gallery("gallery.jpg")
    with Image.open(isolated / "gallery.jpg") as image:
        r, g, b = image.getpixel((480, 300))
    assert r > 200 and g < 30 and b < 30


def test_run_note_persists_through_redo_and_clears(isolated, monkeypatch):
    p = Place("p")
    p.stage("ready")
    seen = []
    monkeypatch.setattr(cli, "pipeline", lambda place, **kw: seen.append(place.s.copy()))
    cli.main(["run", "p", "--redo", "--note", "  steep valley down to the lake "])
    assert seen[0]["coord_note"] == "steep valley down to the lake"
    assert Place("p").s["coord_note"] == "steep valley down to the lake"
    cli.main(["run", "p", "--redo"])
    assert Place("p").s["coord_note"] == "steep valley down to the lake"
    cli.main(["run", "p", "--redo", "--note", ""])
    assert Place("p").s["coord_note"] is None
