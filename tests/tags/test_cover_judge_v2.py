"""Offline cover selection must bind actual pixels, indices and independent role configuration."""
import asyncio

from PIL import Image

from corpus import tags


def inputs(root):
    Image.new("RGB", (32, 32), "blue").save(root / "one.jpg")
    row = {"place_id": "p", "name": "Cloud cafe", "record": {"id": "p", "identity": {"name": "Cloud cafe"}}}
    request = {"place_id": "p", "tags": ["experience:cloud_hunting"], "files": ["one.jpg"]}
    return row, request


def test_cover_selection_reuses_unchanged_pixels_but_not_a_changed_image(tmp_path):
    row, request = inputs(tmp_path)
    calls = []
    async def ask(payload, images):
        calls.append(payload)
        assert len(images) == 1 and payload["candidates"][0]["definition"]["exclude"]
        return {"items": {"experience:cloud_hunting": {"image_index": 0, "verdict": "yes", "reason": "Cloud sea visible"}}}
    first = asyncio.run(tags.judge_cover_candidates([row], [request], tmp_path, tmp_path / "review", ask=ask))
    assert first["calls"] == 1 and first["reviews"][0]["file"] == "one.jpg"
    again = asyncio.run(tags.judge_cover_candidates([row], [request], tmp_path, tmp_path / "review", ask=ask))
    assert again["calls"] == 0 and again["reviews"] == first["reviews"]
    Image.new("RGB", (32, 32), "red").save(tmp_path / "one.jpg")
    changed = asyncio.run(tags.judge_cover_candidates([row], [request], tmp_path, tmp_path / "review", ask=ask))
    assert changed["calls"] == 1 and len(calls) == 2


def test_an_invented_photo_index_can_never_become_an_approval(tmp_path):
    row, request = inputs(tmp_path)
    async def ask(payload, images):
        return {"items": {"experience:cloud_hunting": {"image_index": 7, "verdict": "yes", "reason": "Invented"}}}
    result = asyncio.run(tags.judge_cover_candidates([row], [request], tmp_path, tmp_path / "review", ask=ask))
    assert result["reviews"] == []
    assert result["unresolved"] == [{"place_id": "p", "tag": "experience:cloud_hunting", "reason": "invalid_or_missing_selection"}]


def test_cover_inputs_reject_paths_outside_data_before_any_model_call(tmp_path):
    import pytest
    row, request = inputs(tmp_path)
    request["files"] = ["../outside.jpg"]
    async def ask(*args):
        raise AssertionError("Unsafe inputs reached the model")
    with pytest.raises(ValueError, match="data-relative"):
        asyncio.run(tags.judge_cover_candidates([row], [request], tmp_path, tmp_path / "review", ask=ask))
