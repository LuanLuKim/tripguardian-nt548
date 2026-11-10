import json

import pytest

from auto3d import Place
from auto3d.cli import pipeline
from auto3d import cli


def items(score):
    return [dict(id=f"s{i}", status="ok" if i < round(score * 10) else "missing",
                 blocking=False, cause="data", fix="adjust walls") for i in range(10)]


def fake_steps(calls, scores=(.8,)):
    values = iter(scores)

    def action(name):
        def call(p):
            calls.append(name)
            if name == "notes":
                p.s["notes"] = {"signature": [{"id": "s1", "must": True}], "kit_gap": []}
            elif name == "build":
                (p.dir / "place.json").write_text(json.dumps({"round": p.s["rounds"]}))
            elif name == "review":
                p.s["review"] = {"items": items(next(values))}
            return True
        return call
    return {name: action(name) for name in ("pre_gate", "prep", "gate", "notes", "build", "normalize", "boot", "shoot", "review", "colour")}


def test_resume_skips_done_steps(isolated):
    p = Place("p")
    p.stage("review")
    (p.dir / "place.json").write_text('{"round": 1}')
    calls = []
    pipeline(Place("p"), fake_steps(calls))
    assert calls == ["review", "colour"]
    assert Place("p").s["stage"] == "ready"


def test_kit_gap_stops_at_needs_kit(isolated):
    p = Place("p")
    p.s["notes"] = {"signature": [{"id": "s1", "must": True}],
                    "kit_gap": [{"what": "tower", "signature_ids": ["s1"], "blocks_recognition": True}]}
    p.s["after_notes"] = True
    p.stage("gate")
    calls = []
    pipeline(p, fake_steps(calls))
    assert p.s["stage"] == "needs_kit"
    assert p.s["kit_gap"][0]["what"] == "tower"
    assert calls == ["gate"]


@pytest.mark.parametrize("must, blocks", [(False, True), (False, False), (True, False)])
def test_nonessential_kit_gap_does_not_block(isolated, must, blocks):
    p = Place("p")
    p.s["notes"] = {"signature": [{"id": "s1", "must": must}],
                    "kit_gap": [{"what": "white posts and chains", "signature_ids": ["s1"],
                                 "blocks_recognition": blocks}]}
    p.s["after_notes"] = True
    p.stage("gate")
    calls = []
    pipeline(p, fake_steps(calls))
    assert p.s["stage"] == "ready"


def test_stall_goes_needs_human(isolated):
    p = Place("p")
    calls = []
    pipeline(p, fake_steps(calls, (.6, .6, .6)))
    assert p.s["stage"] == "needs_human"
    assert p.s["scores"] == [.6, .6, .6]
    assert p.s["best_round"] == 1
    assert json.loads((p.dir / "place.json").read_text()) == {"round": 1}
    assert json.loads((p.dir / "place.boot.json").read_text()) == {"round": 3}
    assert calls.count("build") == 3
    assert "colour" not in calls


def test_boot_failure_keeps_last_good(isolated):
    p = Place("p")
    calls, inputs = [], []
    actions = fake_steps(calls, (.6, .5, .8))
    original_build = actions["build"]

    def build(place):
        if place.s["rounds"] == 4:
            inputs.append(json.loads((place.dir / "place.json").read_text()))
            assert "bad geometry" in place.s["feedback"]
        return original_build(place)

    def boot(place):
        if place.s["rounds"] == 3:
            place.s["feedback"] = "bad geometry"
            return False
        return True

    actions.update(build=build, boot=boot)
    pipeline(p, actions)
    assert inputs == [{"round": 2}]
    assert p.s["stage"] == "ready"
    assert p.s["rounds"] == 4
    assert p.s["scores"] == [.6, .5, .8]


def test_boot_failures_exhaust_rounds(isolated):
    p = Place("p")
    actions = fake_steps([])
    actions["boot"] = lambda p: False
    pipeline(p, actions)
    assert p.s["stage"] == "needs_human"
    assert p.s["rounds"] == 5
    assert p.s["scores"] == []


def test_shoot_console_error_goes_back_to_build(isolated):
    class Interrupted(BaseException):
        pass

    p = Place("p")
    p.s["rounds"] = 2
    p.stage("shoot")
    (p.dir / "place.json").write_text('{"round": 2}')
    (p.dir / "place.boot.json").write_text('{"round": 1}')

    def shoot(place):
        place.s.update(shoot_data_error=True, feedback="NaN geometry at stop a")
        return False

    def build(place):
        saved = Place("p")
        assert saved.s["stage"] == "build"
        assert saved.s["rounds"] == 3  # Only entering build consumes the next round.
        assert saved.s["feedback"] == "NaN geometry at stop a"
        assert not saved.s.get("shoot_data_error")
        assert json.loads((place.dir / "place.json").read_text()) == {"round": 2}
        raise Interrupted()

    transitions = []
    original_stage = p.stage

    def stage(name):
        transitions.append((name, p.s["rounds"]))
        original_stage(name)

    p.stage = stage
    with pytest.raises(Interrupted):
        pipeline(p, {"shoot": shoot, "build": build})
    assert transitions == [("build", 2)]


def test_shoot_infra_failure_is_failed(isolated):
    p = Place("p")
    p.s["rounds"] = 2
    p.stage("shoot")
    pipeline(p, {"shoot": lambda place: False})
    assert Place("p").s["stage"] == "failed:shoot"
    assert p.s["rounds"] == 2


def test_shoot_data_error_exhausts_rounds(isolated):
    p = Place("p")
    p.s["rounds"] = cli.config()["max_rounds"]
    p.stage("shoot")

    def shoot(place):
        place.s.update(shoot_data_error=True, feedback="NaN geometry")
        return False

    pipeline(p, {"shoot": shoot})
    assert Place("p").s["stage"] == "needs_human"
    assert not p.s.get("shoot_data_error")
    assert p.s["feedback"] == "NaN geometry"


def test_failed_build_round_goes_back_to_build(isolated):
    p = Place("p")
    p.stage("build")
    (p.dir / "place.boot.json").write_text('{"round": 0}')
    (p.dir / "place.json").write_text('{"round": 0}')
    calls = []
    actions = fake_steps(calls)
    original = actions["build"]

    def build(place):
        if place.s["rounds"] == 1:
            (place.dir / "place.json").write_text("broken")
            place.s["feedback"] = "builder failed"
            return False
        assert json.loads((place.dir / "place.json").read_text()) == {"round": 0}
        assert place.s["feedback"] == "builder failed"
        return original(place)

    actions["build"] = build
    pipeline(p, actions)
    assert p.s["stage"] == "ready" and p.s["rounds"] == 2
    assert "boot" in calls


def test_failed_build_rounds_stop_at_limit(isolated):
    p = Place("p")
    p.stage("build")
    actions = fake_steps([])
    actions["build"] = lambda place: False
    pipeline(p, actions)
    assert p.s["stage"] == "needs_human"
    assert p.s["rounds"] == cli.config()["max_rounds"]


def test_malformed_data_returns_to_builder(isolated):
    p = Place("p")
    calls = []
    actions = fake_steps(calls)

    def normalize(place):
        if place.s["rounds"] == 1:
            raise ValueError("invalid photo path")
        assert "invalid photo path" in place.s["feedback"]
        return True

    actions["normalize"] = normalize
    pipeline(p, actions)
    assert p.s["stage"] == "ready"
    assert calls.count("build") == 2


def test_last_boot_failure_restores_best_on_stop(isolated, monkeypatch):
    settings = cli.config()
    settings["max_rounds"] = 3
    monkeypatch.setattr(cli, "config", lambda: settings)
    p = Place("p")
    actions = fake_steps([], (.6, .5))
    actions["boot"] = lambda place: place.s["rounds"] != 3
    pipeline(p, actions)
    assert p.s["stage"] == "needs_human"
    assert json.loads((p.dir / "place.json").read_text()) == {"round": 1}
    assert json.loads((p.dir / "place.boot.json").read_text()) == {"round": 2}
    assert p.s["scores"] == [.6, .5]


def test_notes_skip_is_terminal_without_another_step(isolated):
    p = Place("p")
    p.stage("notes")

    def notes(place):
        place.s["notes"] = {"skip": True, "skip_reason": "neighbour photos"}
        return True

    pipeline(p, {"notes": notes})
    assert p.s["stage"] == "skip"
    assert p.s["reason"] == "neighbour photos"


def test_gate_fail_skips(isolated):
    p = Place("p")
    calls = []
    actions = fake_steps(calls)
    actions["pre_gate"] = lambda p: False
    pipeline(p, actions)
    assert p.s["stage"] == "skip"
    assert p.s["reason"] == "no_exterior_evidence"
    assert p.s["tokens"] == 0
    assert not calls


def test_gate_after_notes_stops_before_build(isolated):
    p = Place("p")
    actions = fake_steps([])

    def gate(place):
        return not place.s.get("after_notes")

    actions["gate"] = gate
    pipeline(p, actions)
    assert p.s["stage"] == "skip"
    assert p.s["rounds"] == 0


def test_review_kit_cause_cannot_require_new_kit_without_recognition_gap(isolated):
    p = Place("p")
    actions = fake_steps([])

    def review(place):
        place.s["review"] = {"items": [dict(id="s1", status="missing", cause="kit", blocking=True, fix="new type")]}
        return True

    actions["review"] = review
    pipeline(p, actions)
    assert p.s["stage"] == "needs_human"
    assert p.s["rounds"] == 3


@pytest.mark.parametrize("blocking", [False, True])
def test_weighted_review_with_framing_extra(isolated, blocking):
    p = Place("p")
    calls = []
    actions = fake_steps(calls)

    def review(place):
        place.s["review"] = {"items": [
            dict(id=f"s{i}", status="ok" if i < 4 else "weak", blocking=False, fix="adjust size")
            for i in range(6)] + [dict(id="x1", status="wrong", blocking=blocking, fix="frame tower top")]}
        return True

    actions["review"] = review
    pipeline(p, actions)
    assert p.s["scores"][0] == pytest.approx(5 / 6)
    assert p.s["stage"] == ("needs_human" if blocking else "ready")
    assert ("colour" in calls) is not blocking


def test_v1_state_loads(isolated):
    directory = isolated / "places/p"
    directory.mkdir(parents=True)
    original = {"slug": "p", "stage": "ready", "tokens": 42, "notes": {"signature": ["yellow wall"]},
                "history": [{"step": "write", "tokens": 42}]}
    file = directory / "auto3d.json"
    file.write_text(json.dumps(original))
    before = file.read_bytes()
    p = Place("p")
    assert p.s["tokens"] == 42
    assert p.s["scores"] == [] and p.s["best_round"] == 0
    assert p.s["notes"] == original["notes"]
    pipeline(p, {})
    assert file.read_bytes() == before


@pytest.mark.parametrize("stage", ["ready", "skip", "needs_kit", "needs_human", "published", "failed:boot"])
def test_terminal_untouched_unless_redo(isolated, stage):
    p = Place("p")
    p.stage(stage)
    before = p.state_file.read_bytes()
    pipeline(p, {})
    assert p.state_file.read_bytes() == before
    pipeline(p, fake_steps([]), redo=True)
    assert p.s["stage"] == "ready"


def test_transition_saved_before_next_step(isolated):
    class Interrupted(BaseException):
        pass

    p = Place("p")
    actions = fake_steps([])

    def interrupt(place):
        assert Place("p").s["stage"] == "shoot"
        raise Interrupted()

    actions["shoot"] = interrupt
    with pytest.raises(Interrupted):
        pipeline(p, actions)
    calls = []
    pipeline(Place("p"), fake_steps(calls))
    assert calls == ["shoot", "review", "colour"]


def test_log_records_tokens_and_ledger(isolated):
    p = Place("p")
    p.log("notes", tokens=123, result="ok")
    assert Place("p").s["tokens"] == 123
    entry = json.loads((isolated / "batch/ledger.jsonl").read_text())
    assert set(entry) == {"time", "slug", "step", "tokens"}
    assert entry["slug"] == "p" and entry["tokens"] == 123
