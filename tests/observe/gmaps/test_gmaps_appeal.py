import asyncio
import io
import json

import numpy as np
from PIL import Image

from corpus.observe.gmaps import appeal
from corpus.serving import scenes


def jpeg(arr) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.asarray(arr, dtype=np.uint8)).save(buf, "JPEG")
    return buf.getvalue()


class Stub:
    def __init__(self, fn):
        self.fn, self.prompt_hash = fn, "h"
        self.role = type("R", (), {"parallel": staticmethod(lambda: 4), "client": staticmethod(lambda: (type("C", (), {"with_options": lambda s, **k: s})(), "m"))})()

    async def ask(self, client, model, images=(), **fields):
        return self.fn(images, fields)


def test_gate_keeps_well_formed_scores_only():
    answer = {"photos": [{"photo": 1, "beauty": 8, "shows_place": 7}, {"photo": 1, "beauty": 2, "shows_place": 2},
                         {"photo": 2, "beauty": 11, "shows_place": 5}, {"photo": 3, "beauty": True, "shows_place": 5},
                         {"photo": 4, "beauty": 3, "shows_place": 4}, {"photo": 9, "beauty": 3, "shows_place": 4}]}
    assert appeal.gate(answer, 4) == {1: (8, 7), 4: (3, 4)}
    assert appeal.gate(None, 2) == {}


def label(pid, scene, blur, owner=False):
    return {"photo_id": pid, "file": f"photos/{pid}.jpg", "sha": f"s{pid}", "scene": scene, "blur": blur, "brightness": 125.0,
            "keep": True, "owner": owner, "person": {"value": False, "confidence": "high"}}


def test_run_scores_the_best_card_candidates_once_and_pick_reads_them(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    d = tmp_path / "gmaps" / "places" / "F1"
    (d / "photos").mkdir(parents=True)
    (d / "place.json").write_text(json.dumps({"fid": "F1", "name": "Quán A", "category": "Restaurant"}), encoding="utf-8")
    rng = np.random.default_rng(2)
    rows = [label("a", "food", 900), label("b", "food", 800), label("c", "interior", 700), label("m", "menu", 2000),
            {**label("p", "food", 2500), "person": {"value": True, "confidence": "high"}}]
    for r in rows:
        (d / r["file"]).write_bytes(jpeg(rng.integers(0, 255, (60, 80))))
    out = tmp_path / "gmaps" / "photo_scenes"
    out.mkdir(parents=True)
    (out / "F1.json").write_text(json.dumps({"place_fid": "F1", "input_hash": "x", "photos": rows}), encoding="utf-8")
    (tmp_path / "serving").mkdir()
    (tmp_path / "serving" / "places.json").write_text(json.dumps({"records": [
        {"id": "F1", "identity": {"category_group": "restaurant"}}]}), encoding="utf-8")
    calls = []

    def rank(images, fields):
        calls.append((len(images), fields["name"]))
        return {"photos": [{"photo": 1, "beauty": 3, "shows_place": 3}, {"photo": 2, "beauty": 6, "shows_place": 6},
                           {"photo": 3, "beauty": 9, "shows_place": 9}]}

    monkeypatch.setattr(appeal, "PHOTO_RANK", Stub(rank))
    monkeypatch.setattr(appeal, "load_config", lambda city: ("Đà Lạt", {}))
    monkeypatch.setitem(appeal.config()["appeal"], "rank_max", 3)
    assert asyncio.run(appeal.run("dalat"))["status"] == {"done": 1}
    assert calls == [(3, "Quán A")]  # the menu and the photo with a stranger are never candidates
    doc = json.loads((tmp_path / "gmaps" / "photo_appeal" / "F1.json").read_text(encoding="utf-8"))
    assert doc["photos"]["c"] == {"beauty": 9, "shows_place": 9, "sha": "sc"} and set(doc["photos"]) == {"a", "b", "c"}
    assert [p["photo_id"] for p in scenes.for_place("F1", "restaurant", tmp_path)] == ["c", "b", "a"]
    assert asyncio.run(appeal.run("dalat"))["status"] == {"cached": 1}
    assert len(calls) == 1
