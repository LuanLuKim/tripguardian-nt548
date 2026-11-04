"""Actual image evidence is required for style membership, including cache invalidation."""
import asyncio
import json

from PIL import Image

from corpus.tags.offline import candidates, judge_places


def row_with_photo(tmp_path):
    photo = tmp_path / "gmaps/places/p/photos/front.jpg"
    photo.parent.mkdir(parents=True)
    Image.new("RGB", (30, 20), "white").save(photo)
    return {"place_id": "p", "name": "Minimal cafe", "category": "Quán cà phê", "group": "cafe",
            "record": {"id": "p", "identity": {"name": "Minimal cafe", "category_group": "cafe"}},
            "styles": ["minimal"], "features": {},
            "style_evidence": {"minimal": [{"file": "gmaps/places/p/photos/front.jpg",
                                            "quote": "plain walls and sparse simple furniture"}]}}, photo


def test_style_candidate_binds_actual_photo_content(tmp_path):
    row, photo = row_with_photo(tmp_path)
    before = next(c for c in candidates(row, root=tmp_path) if c["tag"] == "style:minimal")
    Image.new("RGB", (30, 20), "red").save(photo)
    after = next(c for c in candidates(row, root=tmp_path) if c["tag"] == "style:minimal")
    assert before["evidence_hash"] != after["evidence_hash"]
    photo.unlink()
    missing = next(c for c in candidates(row, root=tmp_path) if c["tag"] == "style:minimal")
    assert missing["evidence"] == []


def test_judge_images_are_real_decodable_pixels_in_evidence_order(tmp_path):
    from corpus.tags.offline import image_payload
    from io import BytesIO
    row, photo = row_with_photo(tmp_path)
    payload, files = image_payload(candidates(row, root=tmp_path), tmp_path)
    assert files == ["gmaps/places/p/photos/front.jpg"]
    assert len(payload) == 1
    assert Image.open(BytesIO(payload[0])).size == (30, 20)


def test_spa_design_is_a_real_style_need_when_pixels_are_judged_yes(tmp_path):
    from corpus.tags import of_record
    row, _ = row_with_photo(tmp_path)
    row["record"]["identity"].update(name="Minimal Spa", category_group="spa")
    row.update(name="Minimal Spa", category="Spa")
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "support": "visual_design",
                           "quote": c["evidence"][0]["quote"], "reason": "visible design"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    assert of_record(row["record"], row["styles"], root=tmp_path).styles == frozenset({"minimal"})


def test_missing_photo_never_becomes_style_yes_even_if_model_agrees(tmp_path):
    row, photo = row_with_photo(tmp_path)
    photo.unlink()
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": "Minimal cafe", "reason": "name"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    doc = json.loads((tmp_path / "tag_membership/current.json").read_text())
    assert doc["places"]["p"]["style:minimal"]["verdict"] == "unclear"
