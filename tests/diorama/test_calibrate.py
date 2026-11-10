import json
from datetime import datetime

import pytest

from auto3d import Place, cli, steps
from auto3d.exam import calibration_result, run_calibrate


def approved_place(slug):
    place = Place(slug)
    place.dir.mkdir(parents=True)
    (place.dir / "place.json").write_text('{"kits": ["villa"], "objects": [{"id": "approved"}]}\n')
    (place.dir / "meta.json").write_text('{"fid": "0x1_0x2", "name": "Approved palace", "reviews": 42}')
    (place.dir / "photos").mkdir()
    (place.dir / "photos/g00.jpg").write_bytes(b"photo")
    (place.dir / "photos_index.json").write_text("[]")
    (place.dir / "contact.jpg").write_bytes(b"contact")
    (place.dir / "NOTES_coord.md").write_text("Do not copy stale signatures")
    return place


def report(data):
    return json.loads((data / f"batch/calibrate_{datetime.now():%Y%m%d}.json").read_text())


def test_calibration_result_is_pure_and_uses_weighted_score():
    items = [dict(id=f"s{i}", status="ok" if i < 4 else "weak", blocking=False, fix="resize roof")
             for i in range(6)]
    before = json.dumps(items)
    result = calibration_result(items)
    assert result == {"score": 5 / 6, "passed": True,
                      "non_ok": [dict(id=f"s{i}", status="weak", fix="resize roof") for i in (4, 5)]}
    assert json.dumps(items) == before
    items.append(dict(id="x1", status="wrong", blocking=True, fix="frame tower top"))
    result = calibration_result(items)
    assert result["score"] == 5 / 6 and not result["passed"]
    assert result["non_ok"][-1] == dict(id="x1", status="wrong", fix="frame tower top")


@pytest.mark.parametrize("keep", [False, True])
def test_calibrate_only_reviews_copied_ground_truth(isolated, monkeypatch, capsys, keep):
    original = approved_place("p")
    before = {str(p.relative_to(original.dir)): p.read_bytes() for p in original.dir.rglob("*") if p.is_file()}
    calls = []

    def action(name):
        def call(place):
            calls.append((place.slug, name))
            assert place.slug == "x_cal_p"
            assert (place.dir / "place.json").read_bytes() == before["place.json"]
            assert place.s["kit_forced"] == "villa"
            assert place.s["fid"] == "0x1_0x2" and place.s["name"] == "Approved palace"
            assert place.s["reviews"] == 42
            assert (place.dir / "photos/g00.jpg").read_bytes() == b"photo"
            assert (place.dir / "contact.jpg").read_bytes() == b"contact"
            assert not (place.dir / "NOTES_coord.md").exists()
            if name == "notes":
                assert place.s["notes"] == {}
                # Approved ground truth still gets reviewed if NOTES claims a kit gap.
                place.s["notes"] = dict(signature=[dict(id="s1", must=True)], kit="villa",
                                        kit_gap=[dict(what="tower", signature_ids=["s1"], blocks_recognition=True)])
            if name == "review":
                place.s["review"] = {"items": [dict(id="s1", status="ok", blocking=False, fix="")]}
            place.log(name, tokens=2)
            return True
        return call

    for name in ("notes", "boot", "shoot", "review"):
        monkeypatch.setattr(steps, name, action(name))
    for name in ("build", "normalize", "colour", "prep", "gate", "pre_gate"):
        monkeypatch.setattr(steps, name, lambda *args: pytest.fail("Only calibration steps are allowed"))
    monkeypatch.setattr(cli, "pipeline", lambda *args: pytest.fail("Must not run the builder pipeline"))
    run_calibrate(["p", "p"], keep)
    assert calls == [("x_cal_p", name) for name in ("notes", "boot", "shoot", "review")]
    rows = report(isolated)
    assert len(rows) == 1 and rows[0] == dict(slug="p", score=1.0, passed=True, non_ok=[],
                                             error=None, tokens=8, stage="ready")
    assert "p: score=1.000 pass=True" in capsys.readouterr().out
    assert (isolated / "places/x_cal_p").exists() == keep
    assert {str(p.relative_to(original.dir)): p.read_bytes() for p in original.dir.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("failure", ["blocking", "score", "notes", "skip", "boot", "shoot", "review", "exception"])
def test_calibration_failures_report_exit_one_and_continue(isolated, monkeypatch, capsys, failure):
    for slug in ("p", "q"):
        approved_place(slug)
    calls = []

    def action(name):
        def call(place):
            calls.append((place.slug, name))
            if place.slug == "x_cal_p":
                if failure == name:
                    return False
                if failure == "exception" and name == "boot":
                    raise RuntimeError("broken boot")
                if failure == "skip" and name == "notes":
                    place.s["notes"] = dict(skip=True, skip_reason="no exterior")
                    return True
            if name == "notes":
                place.s["notes"] = dict(skip=False, kit="villa", signature=[dict(id="s1")])
            if name == "review":
                place.s["review"] = {"items": [dict(id="s1", status="ok", blocking=False, fix="")]}
                if place.slug == "x_cal_p" and failure == "blocking":
                    place.s["review"]["items"].append(dict(id="x1", status="wrong", blocking=True, fix="frame tower top"))
                if place.slug == "x_cal_p" and failure == "score":
                    place.s["review"]["items"][0].update(status="weak", fix="resize main roof")
            return True
        return call

    for name in ("notes", "boot", "shoot", "review"):
        monkeypatch.setattr(steps, name, action(name))
    with pytest.raises(SystemExit) as exc:
        run_calibrate(["p", "q"])
    assert exc.value.code == 1
    rows = report(isolated)
    assert len(rows) == 2 and not rows[0]["passed"] and rows[1]["passed"]
    assert ("x_cal_q", "review") in calls
    assert not (isolated / "places/x_cal_p").exists()
    assert not (isolated / "places/x_cal_q").exists()
    output = capsys.readouterr().out
    if failure == "blocking":
        assert rows[0]["score"] == 1.0 and "x1 wrong: frame tower top" in output
    elif failure == "score":
        assert rows[0]["score"] == 0.5 and "s1 weak: resize main roof" in output
    else:
        assert rows[0]["score"] is None and rows[0]["error"]


@pytest.mark.parametrize("invalid", ["missing_approved", "existing_target", "malformed_approved"])
def test_calibration_preflights_all_places_before_spending_quota(isolated, monkeypatch, invalid):
    approved_place("p")
    q = approved_place("q")
    if invalid == "missing_approved":
        (q.dir / "place.json").unlink()
    elif invalid == "existing_target":
        Place("x_cal_q").save()
    else:
        (q.dir / "place.json").write_text("invalid")
    monkeypatch.setattr(steps, "notes", lambda *args: pytest.fail("Must preflight all slugs first"))
    with pytest.raises((SystemExit, ValueError)):
        run_calibrate(["p", "q"])
    assert not (isolated / "places/x_cal_p").exists()
    if invalid == "existing_target":
        assert Place("x_cal_q").state_file.is_file()
