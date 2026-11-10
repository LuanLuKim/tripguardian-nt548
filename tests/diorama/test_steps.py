import copy
import json

import pytest

from auto3d import Place, steps, prompts


def test_console_errors_deduplicates_and_limits():
    errors = [f"ERROR geometry {i}" for i in range(12)]
    console = "\n".join(["ready", "error favicon", "ERROR 404", "  ERROR geometry 0  ",
                         *errors, "failed to render", "NOT READY"])
    assert steps._console_errors(console) == errors[:10]
    assert steps._console_errors("ready\nfailed to render\nNOT READY") == ["failed to render", "NOT READY"]


@pytest.mark.parametrize("defect", ["render", "photos", "missing_photo"])
def test_shoot_stop_data_defects_return_feedback(isolated, monkeypatch, defect):
    p = Place("p")
    p.save()
    (p.dir / "place.json").write_text(json.dumps({"hotspots": [
        {"id": "a", "photos": [] if defect == "photos" else ["g00.jpg"]},
        {"id": "b", "photos": []},
    ]}))
    overview = isolated / "00_initial.png"
    stop = isolated / "01_hs_a.png"
    if defect == "render":
        (p.dir / "photos").mkdir()
        (p.dir / "photos/g00.jpg").touch()
    monkeypatch.setattr(steps, "render", lambda place: (overview, [overview] if defect == "render" else [overview, stop]))
    assert not steps.shoot(p)
    assert Place("p").s["shoot_data_error"] is True
    assert "Stop a" in p.s["feedback"] and "Stop b" in p.s["feedback"]
    assert "check every object's numeric fields against the catalogue" in p.s["feedback"]


@pytest.mark.parametrize("failure", ["console", "build", "no_renders", "error_file", "no_overview", "partial_shot"])
def test_shoot_classifies_render_failures(isolated, monkeypatch, failure):
    from types import SimpleNamespace

    p = Place("p")
    p.save()
    (p.dir / "place.json").write_text('{"hotspots": [{"id": "a", "photos": []}]}')

    def run(command, timeout):
        if "build.py" in command[1]:
            return SimpleNamespace(returncode=int(failure == "build"), stdout="", stderr="")
        out = isolated / "bridge/out" / command[2]
        out.mkdir(parents=True)
        if failure != "no_renders":
            (out / ("01_hs_a.png" if failure == "no_overview" else "00_initial.png")).touch()
        (out / "console.txt").write_text("ERROR THREE.BufferGeometry.computeBoundingSphere(): Computed radius is NaN\n" * 20)
        if failure == "error_file":
            (out / "error.txt").write_text("bridge failed")
        return SimpleNamespace(returncode=int(failure in ("no_renders", "partial_shot")), stdout="", stderr="")

    monkeypatch.setattr(steps, "run", run)
    assert not steps.shoot(p)
    if failure in ("console", "partial_shot"):
        assert Place("p").s["shoot_data_error"] is True
        assert p.s["feedback"].count("Computed radius is NaN") == 1
        assert "stop ids: a" in p.s["feedback"]
        assert "NaN geometry usually means" in p.s["feedback"]
    else:
        assert not p.s.get("shoot_data_error")


def test_shoot_reuses_build_bridge_render(isolated, monkeypatch):
    from PIL import Image

    p = Place("p")
    p.save()
    (p.dir / "photos").mkdir()
    Image.new("RGB", (20, 20)).save(p.dir / "photos/g00.jpg")
    (p.dir / "place.json").write_text(json.dumps({"hotspots": [{"id": "a", "photos": ["g00.jpg"]}]}))
    output = isolated / "out_p"
    output.mkdir()
    source = isolated / "bridge/out/tag"
    source.mkdir(parents=True)
    overview, stop = source / "00_initial.png", source / "01_hs_a.png"
    for path in (overview, stop):
        Image.new("RGB", (20, 20)).save(path)
    calls = []
    monkeypatch.setattr(steps, "render", lambda place: calls.append(place) or (overview, [overview, stop]))
    assert steps.shoot(p)
    assert calls == [p]
    assert p.s["overview"] == str(overview)
    assert len(p.s["review_images"]) == 2


def test_render_calls_build_then_bridge(isolated, monkeypatch):
    from types import SimpleNamespace
    from PIL import Image

    p = Place("p")
    p.save()
    commands = []

    def run(command, timeout):
        commands.append(command)
        if "shot.py" in command[1]:
            out = isolated / "bridge/out" / command[2]
            out.mkdir(parents=True)
            Image.new("RGB", (20, 20)).save(out / "00_initial.png")
            (out / "console.txt").write_text("ready")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(steps, "run", run)
    overview, pngs = steps.render(p)
    assert overview == pngs[0]
    assert commands[0][1].endswith("build.py")
    assert commands[1][1].endswith("bridge/shot.py")
    assert commands[1][-2:] == ["--out", "out_p"]


def notes_value():
    return dict(skip=False, skip_reason="", kit="villa", kit_why="photo match", kit_gap=[], evidence=["g00", "g01"],
                drop_photos=[], signature=[dict(id=f"s{i}", what="yellow plaster wall", photos=["g00"], must=i == 1) for i in range(3)],
                layout="front garden", entrance="g00", interior=False, interior_photos=[], stops=["Cổng (g00)"])


@pytest.mark.parametrize("extras", [None, [], ["nature"]])
def test_notes_extra_kits_optional(extras):
    value = notes_value()
    if extras is not None:
        value["extra_kits"] = extras
    steps._validate_notes(value, {"g00.jpg", "g01.jpg"})


@pytest.mark.parametrize("extras", [["nonexistent_kit"], ["villa"], ["nature", "nature"],
                                     ["nature", "garden", "church"], "nature", [None]])
def test_notes_extra_kits_invalid(extras):
    value = notes_value()
    value["extra_kits"] = extras
    with pytest.raises(ValueError):
        steps._validate_notes(value, {"g00.jpg", "g01.jpg"})


@pytest.mark.parametrize("included", [False, True])
def test_notes_forced_extra_kits(isolated, monkeypatch, included):
    p = Place("p")
    p.s["extra_kits_forced"] = ["nature"]
    p.save()
    (p.dir / "photos_index.json").write_text(json.dumps([
        {"name": "g00.jpg", "scene": "exterior"}, {"name": "g01.jpg", "scene": "view"}]))
    value = notes_value()
    if included:
        value["extra_kits"] = ["nature"]
    seen = []

    def ask(prompt, *args):
        seen.append(prompt)
        return value, {}

    monkeypatch.setattr(steps, "ask", ask)
    assert steps.notes(p) == included
    assert 'Forced extra kits (must all be included): ["nature"]' in seen[0]
    if not included:
        assert "forced extra kits" in p.s["history"][-1]["result"]


@pytest.mark.parametrize("kits", [["storefront"], ["nature"], [], "storefront+nature"])
def test_boot_rejects_missing_required_kits(isolated, kits):
    p = Place("p")
    p.s["notes"] = {"kit": "storefront", "extra_kits": ["nature"]}
    p.save()
    (p.dir / "place.json").write_text(json.dumps({"kits": kits}))
    assert not steps.boot(p)
    assert "Boot error; place.json kits is missing required kits:" in p.s["feedback"]
    assert p.s["history"][-1]["step"] == "boot"


@pytest.mark.parametrize("extras", [None, ["nature"]])
def test_boot_accepts_required_kits(isolated, monkeypatch, extras):
    from types import SimpleNamespace

    p = Place("p")
    p.s["notes"] = {"kit": "storefront"}
    if extras is not None:
        p.s["notes"]["extra_kits"] = extras
    p.save()
    (p.dir / "place.json").write_text(json.dumps({"kits": ["storefront", *(extras or [])]}))
    monkeypatch.setattr(steps, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="boot ok", stderr=""))
    assert steps.boot(p)


@pytest.mark.parametrize("extras", [None, ["nature"]])
def test_pipeline_retries_missing_extra_kit_and_preserves_old_notes(isolated, monkeypatch, extras):
    from types import SimpleNamespace
    from auto3d.cli import pipeline

    p = Place("p")
    original_notes = {"kit": "storefront", "signature": []}
    if extras is not None:
        original_notes["extra_kits"] = extras
    p.s["notes"] = copy.deepcopy(original_notes)
    p.stage("build")
    feedback = []

    def build(place):
        feedback.append(place.s.get("feedback"))
        kits = ["storefront"]
        if place.s["rounds"] > 1:
            kits += extras or []
        (place.dir / "place.json").write_text(json.dumps({"kits": kits}))
        return True

    def review(place):
        place.s["review"] = {"items": [dict(id="s1", status="ok", blocking=False, cause="data", fix="")]}
        return True

    monkeypatch.setattr(steps, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="boot ok", stderr=""))
    actions = {name: lambda place: True for name in ("normalize", "shoot", "colour")}
    actions.update(build=build, boot=steps.boot, review=review)
    pipeline(p, actions)
    assert p.s["stage"] == "ready"
    assert p.s["notes"] == original_notes
    assert p.s["rounds"] == (2 if extras else 1)
    if extras:
        assert "missing required kits: nature" in feedback[1]


def test_notes_uses_orientation_plus_twelve_original_photos(isolated, monkeypatch):
    p = Place("p")
    p.save()
    index = [dict(name=f"g{i:02d}.jpg", scene="exterior" if i < 13 else "interior") for i in range(15)]
    (p.dir / "photos_index.json").write_text(json.dumps(index))
    captured = []

    def ask(prompt, images, effort):
        captured.append((prompt, images, effort))
        return notes_value(), {"total_tokens": 11}

    monkeypatch.setattr(steps, "ask", ask)
    assert steps.notes(p)
    assert captured[0][1] == [p.dir / "contact.jpg", *(p.dir / "photos" / f"g{i:02d}.jpg" for i in range(12))]
    assert p.s["tokens"] == 11
    assert '"signature_ids"' in captured[0][0]
    assert '"blocks_recognition"' in captured[0][0]
    assert "OVERVIEW scale" in captured[0][0]
    assert "white posts and chains" in captured[0][0]


@pytest.mark.parametrize("change", [
    {"kit_gap": ["plain strings are invalid"]},
    {"kit_gap": [{"what": "tower", "signature_ids": ["unknown"], "blocks_recognition": True}]},
    {"kit_gap": [{"what": "tower", "signature_ids": ["s1"]}]},
    {"kit_gap": [{"what": "tower", "signature_ids": ["s1"], "blocks_recognition": "false"}]},
    {"evidence": ["g99"]}, {"drop_photos": ["g00"]}, {"signature": []},
])
def test_invalid_notes_rejected_and_tokens_recorded(isolated, monkeypatch, change):
    p = Place("p")
    p.save()
    (p.dir / "photos_index.json").write_text(json.dumps([{"name": "g00.jpg", "scene": "exterior"}]))
    value = notes_value()
    value.update(change)
    monkeypatch.setattr(steps, "ask", lambda *args: (value, {"total_tokens": 7}))
    assert not steps.notes(p)
    assert p.s["tokens"] == 14


def test_review_enforces_ids_and_statuses(isolated, monkeypatch):
    p = Place("p")
    p.save()
    (p.dir / "place.json").write_text('{"kits": ["villa"]}')
    p.s.update(notes={"signature": [{"id": "s1", "what": "yellow plaster", "photos": ["g00"], "must": True}]}, review_images=["overview", "stop-pair"])
    valid = {"items": [{"id": "s1", "status": "weak", "blocking": False, "cause": "data", "fix": "yellow"}]}
    captured = []

    def ask(prompt, images, effort):
        captured.append(images)
        return copy.deepcopy(valid), {"total_tokens": 12}

    monkeypatch.setattr(steps, "ask", ask)
    assert steps.review(p)
    assert p.s["review"] == valid
    assert captured == [["overview", "stop-pair"]]
    valid["items"].append(valid["items"][0])
    assert not steps.review(p)
    assert p.s["tokens"] == 36


@pytest.mark.parametrize("blocks", [False, True])
def test_notes_accepts_boolean_recognition_gap(blocks):
    value = notes_value()
    value["kit_gap"] = [{"what": "tower", "signature_ids": ["s1"], "blocks_recognition": blocks}]
    steps._validate_notes(value, {"g00.jpg", "g01.jpg"})


def test_review_uses_actual_model_kits_and_kit_scale_rules(isolated, monkeypatch):
    p = Place("p")
    p.save()
    (p.dir / "place.json").write_text('{"kits": ["church", "garden"]}')
    p.s.update(notes={"kit": "villa", "signature": [{"id": "s1"}]}, review_images=["overview"])
    captured = []
    monkeypatch.setattr(prompts, "catalogue", lambda kit: f"SUPPORTED OBJECTS: {kit}")

    def ask(prompt, images, effort):
        captured.append(prompt)
        return {"items": [dict(id="s1", status="ok", blocking=False, cause="data", fix="")]}, {}

    monkeypatch.setattr(steps, "ask", ask)
    assert steps.review(p)
    prompt = captured[0]
    assert "SUPPORTED OBJECTS: church" in prompt and "SUPPORTED OBJECTS: garden" in prompt
    assert "SUPPORTED OBJECTS: villa" not in prompt
    for rule in ("simple shapes, no fine ornament", "glass, mouldings", "trunk/branch shapes",
                 "Every fix must be achievable", "blocking=true ONLY", "a missing main building"):
        assert rule in prompt


def test_notes_retries_once_then_succeeds(isolated, monkeypatch):
    p = Place("p")
    p.save()
    (p.dir / "photos_index.json").write_text(json.dumps([
        {"name": "g00.jpg", "scene": "exterior"}, {"name": "g01.jpg", "scene": "view"}]))
    answers = iter(['{"skip": invalid JSON}', json.dumps(notes_value())])
    calls = []

    def ask(prompt, images, effort):
        calls.append((prompt, images, effort))
        return next(answers), {"total_tokens": 7}

    monkeypatch.setattr(steps, "ask", ask)
    assert steps.notes(p)
    assert p.s["tokens"] == 14
    assert len(calls) == 2 and "rejected" in calls[1][0]
    assert calls[0][1:] == calls[1][1:]
    assert calls[1][0].startswith(calls[0][0])


def test_review_fails_after_two_bad_answers(isolated, monkeypatch):
    p = Place("p")
    p.save()
    (p.dir / "place.json").write_text('{"kits": ["villa"]}')
    p.s.update(notes={"signature": [{"id": "s1"}]}, review_images=["overview"])
    calls = []

    def ask(prompt, images, effort):
        calls.append(prompt)
        return {}, {"total_tokens": 5}

    monkeypatch.setattr(steps, "ask", ask)
    assert not steps.review(p)
    assert len(calls) == 2 and p.s["tokens"] == 10


@pytest.mark.parametrize("step", ["notes", "review"])
def test_model_exceptions_are_retried_and_logged(isolated, monkeypatch, step):
    p = Place("p")
    p.s.update(notes={"signature": []}, review_images=[])
    p.save()
    (p.dir / "photos_index.json").write_text("[]")
    (p.dir / "place.json").write_text('{"kits": ["villa"]}')
    calls = []

    def ask(prompt, images, effort):
        calls.append(prompt)
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(steps, "ask", ask)
    assert not getattr(steps, step)(p)
    assert len(calls) == 2 and "network unavailable" in calls[1]
    assert "network unavailable" in p.s["history"][-1]["result"]


def test_failed_build_records_log_tail_as_feedback(isolated, monkeypatch):
    from auto3d.builder import BuildResult

    p = Place("p")
    p.s["builder"] = "function"
    p.save()
    log = "earlier output " * 200 + "network error"
    monkeypatch.setattr(steps.FunctionBuilder, "build", lambda *args: BuildResult(False, 17, log))
    assert not steps.build(p)
    assert Place("p").s["feedback"] == log[-1600:]
    assert p.s["tokens"] == 17


@pytest.mark.parametrize("items", [[], [{"id": "s2"}], [dict(id="s1", status="excellent", blocking=False, cause="data", fix="")]])
def test_review_missing_or_invalid_items(items):
    with pytest.raises(ValueError):
        steps._validate_review({"items": items}, [{"id": "s1"}])
