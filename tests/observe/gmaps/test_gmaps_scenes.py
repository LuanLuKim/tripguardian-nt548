import asyncio
import io
import json

import numpy as np
from PIL import Image

from corpus.observe.gmaps import scenes


def jpeg(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8")).save(buf, "JPEG", quality=95)
    return buf.getvalue()


def test_image_stats_sharp_beats_blur_and_dark_is_dark():
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, (300, 400))
    sharp = scenes.image_stats(jpeg(noise))
    flat = scenes.image_stats(jpeg(np.full((300, 400), 20)))
    assert sharp["blur"] > 1000 > flat["blur"] and flat["brightness"] < 25 < sharp["brightness"]
    assert (sharp["w"], sharp["h"]) == (400, 300)
    assert scenes.image_stats(b"not an image") == {"blur": None, "brightness": None, "w": None, "h": None}


def test_components_join_near_duplicates_by_cosine():
    v = np.array([[1, 0, 0], [0.99, 0.05, 0], [0, 1, 0], [0.98, 0.1, 0.0]], dtype="float16")
    assert scenes.components(v, 0.95) == [0, 0, 2, 0]
    assert scenes.components(v[:1], 0.95) == [0]
    assert scenes.components(v, 1.01) == [0, 1, 2, 3]


def test_clusters_keep_the_sharpest_and_a_photo_without_vector_is_alone():
    es = [{"photo_id": "a", "blur": 50.0}, {"photo_id": "b", "blur": 300.0}, {"photo_id": "c", "blur": 10.0},
          {"photo_id": "d", "blur": None}]
    vecs = {"a": np.array([1, 0]), "b": np.array([0.999, 0.01]), "c": np.array([0, 1])}
    scenes.assign_clusters(es, vecs, 0.95)
    assert [e["cluster"] for e in es] == ["a", "a", "c", "d"]
    assert [e["keep"] for e in es] == [False, True, True, True]


def test_gate_fills_missing_as_unknown_and_distrusts_crowd_without_person():
    out, dropped = scenes.gate({"photos": [
        {"photo": 1, "scene": "interior", "person": "no", "person_confidence": "high"},
        {"photo": 1, "scene": "food", "person": "yes", "person_confidence": "high"},  # repeated number: first wins
        {"photo": 3, "scene": "crowd", "person": "no", "person_confidence": "high"},
        {"photo": 9, "scene": "view", "person": "no", "person_confidence": "high"},  # no photo 9
    ]}, 3)
    assert out[0] == {"scene": "interior", "person": {"value": False, "confidence": "high"}}
    assert out[1] == {"scene": "unknown", "person": {"value": None, "confidence": "low"}}
    assert out[2] == {"scene": "crowd", "person": {"value": None, "confidence": "low"}}
    assert dict(dropped) == {"duplicate": 1, "crowd_without_person": 1, "bad_photo": 1, "missing": 1}


class Stub:
    def __init__(self, fn):
        self.fn, self.prompt_hash = fn, "h"
        self.role = type("R", (), {"parallel": staticmethod(lambda: 4), "client": staticmethod(lambda: (type("C", (), {"with_options": lambda s, **k: s})(), "m"))})()

    async def ask(self, client, model, images=(), **fields):
        return self.fn(images, fields)


def test_run_labels_caches_by_hash_and_relabels_only_new_photos(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    d = tmp_path / "gmaps" / "places" / "F1"
    (d / "photos").mkdir(parents=True)
    (d / "place.json").write_text(json.dumps({"fid": "F1", "name": "Cafe A", "category": "Cafe"}), encoding="utf-8")
    (tmp_path / "serving").mkdir()
    (tmp_path / "serving" / "places.json").write_text(json.dumps({"records": [{"id": "F1"}]}), encoding="utf-8")
    rng = np.random.default_rng(1)

    def add(n: int):
        shots = []
        for i in range(1, n + 1):
            (d / f"photos/p{i}.jpg").write_bytes(jpeg(rng.integers(0, 255, (60, 80)) if i != 2 else np.full((60, 80), 9)))
            shots.append({"photo_id": f"P{i}", "file": f"photos/p{i}.jpg", "kind": "photo", "author_hash": "a", "owner": False,
                          "month": "2026-05"})
        (d / "photos.json").write_text(json.dumps({"fetched_at": "2026-10-02T00:00:00", "photos": shots}), encoding="utf-8")

    calls = []

    def label(images, fields):
        calls.append(len(images))
        return {"photos": [{"photo": i, "scene": "interior", "person": "no", "person_confidence": "high"}
                           for i in range(1, len(images) + 1)]}

    monkeypatch.setattr(scenes, "SCENE_OBSERVE", Stub(label))
    monkeypatch.setattr(scenes, "load_config", lambda city: ("Đà Lạt", {}))
    add(5)
    assert asyncio.run(scenes.run("dalat"))["status"] == {"done": 1}
    doc = json.loads((tmp_path / "gmaps" / "photo_scenes" / "F1.json").read_text(encoding="utf-8"))
    assert calls == [4, 1] and len(doc["photos"]) == 5
    p2 = doc["photos"][1]
    assert p2["scene"] == "interior" and p2["person"] == {"value": False, "confidence": "high"}
    assert p2["brightness"] < 15 and p2["cluster"] == "P2" and p2["keep"] is True and (p2["w"], p2["h"]) == (80, 60)
    assert asyncio.run(scenes.run("dalat"))["status"] == {"cached": 1}
    calls.clear()
    (d / "photos/p6.jpg").write_bytes(jpeg(rng.integers(0, 255, (60, 80))))
    shots = json.loads((d / "photos.json").read_text(encoding="utf-8"))
    shots["photos"].append({"photo_id": "P6", "file": "photos/p6.jpg", "kind": "photo", "author_hash": "b", "owner": False})
    (d / "photos.json").write_text(json.dumps(shots), encoding="utf-8")
    assert asyncio.run(scenes.run("dalat"))["status"] == {"done": 1}
    assert calls == [1]  # five photos were cached by hash; only the new one went to the model
