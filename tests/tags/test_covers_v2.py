"""A tag cover must be reviewed for that motive and bound to the exact image."""
import asyncio

from corpus import tags


def test_only_reviewed_fresh_images_of_current_members_are_returned(tmp_path):
    record = {"id": "p:1", "identity": {"name": "Cloud cafe", "category_group": "cafe"}}
    row = {"place_id": "p:1", "name": "Cloud cafe", "record": record, "styles": [],
           "features": {"cloud_hunting": [{"quote": "Săn mây từ ban công quán", "source": "gmaps_review"}]}}
    photo = tmp_path / "gmaps/places/p_1/photos/cloud.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"original-reviewed-image")
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "support": "visitor_experience",
                            "quote": c["evidence"][0]["quote"], "reason": "cloud panorama"} for c in cs]}
    asyncio.run(tags.judge_places([row], tmp_path, ask=ask))
    review = {"place_id": "p:1", "tag": "experience:cloud_hunting", "file": "gmaps/places/p_1/photos/cloud.jpg",
              "verdict": "yes", "reason": "Sea of clouds is visible", "reviewed_by": "manual"}
    assert tags.approved_covers(record, [], "experience:cloud_hunting", root=tmp_path) == []
    tags.save_cover_reviews([row], [review], tmp_path)
    assert tags.approved_covers(record, [], "experience:cloud_hunting", root=tmp_path) == [review["file"]]
    assert tags.approved_covers(record, [], "experience:animals", root=tmp_path) == []
    photo.write_bytes(b"changed-image")
    assert tags.approved_covers(record, [], "experience:cloud_hunting", root=tmp_path) == []


def test_rejected_cover_and_path_escape_never_become_approved(tmp_path):
    import pytest
    record = {"id": "p:1", "identity": {"name": "Cafe", "category_group": "cafe"}}
    row = {"place_id": "p:1", "name": "Cafe", "record": record, "styles": []}
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo")
    review = {"place_id": "p:1", "tag": "category:cafe", "file": "photo.jpg", "verdict": "unclear",
              "reason": "Not enough context", "reviewed_by": "manual"}
    tags.save_cover_reviews([row], [review], tmp_path)
    assert tags.approved_covers(record, [], "category:cafe", root=tmp_path) == []
    with pytest.raises(ValueError):
        tags.save_cover_reviews([row], [{**review, "file": "../outside.jpg", "verdict": "yes"}], tmp_path)


def test_style_cover_cannot_bypass_allowed_place_groups(tmp_path):
    record = {"id": "p:1", "identity": {"name": "Temple", "category_group": "religious"}}
    row = {"place_id": "p:1", "name": "Temple", "record": record, "styles": ["minimal"],
           "style_evidence": {"minimal": [{"file": "photo.jpg", "quote": "Sparse design"}]}}
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo")
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "support": "visual_design",
                            "quote": c["evidence"][0]["quote"], "reason": "simple design"} for c in cs]}
    asyncio.run(tags.judge_places([row], tmp_path, ask=ask))
    tags.save_cover_reviews([row], [{"place_id": "p:1", "tag": "style:minimal", "file": "photo.jpg",
        "verdict": "yes", "reason": "Sparse design", "reviewed_by": "manual"}], tmp_path)
    assert tags.approved_covers(record, ["minimal"], "style:minimal", root=tmp_path) == []


def test_cover_approval_is_disabled_with_legacy_rollout(tmp_path, monkeypatch):
    from corpus.tags import vocab
    cfg = vocab.raw_config()
    monkeypatch.setattr(vocab, "raw_config", lambda: {**cfg, "membership": {**cfg["membership"], "enabled": False}})
    assert tags.approved_covers({"id": "p"}, [], "category:cafe", root=tmp_path) == []


def test_merging_reviews_never_renews_the_hash_of_an_old_changed_photo(tmp_path):
    import json
    row = {"place_id": "p", "record": {"id": "p", "identity": {"name": "Cafe"}}, "styles": []}
    (tmp_path / "one.jpg").write_bytes(b"old reviewed pixels")
    (tmp_path / "two.jpg").write_bytes(b"new reviewed pixels")
    review = {"place_id": "p", "tag": "category:cafe", "file": "one.jpg", "verdict": "yes",
              "reason": "Cafe visible", "reviewed_by": "manual"}
    tags.save_cover_reviews([row], [review], tmp_path)
    path = tmp_path / "tag_membership/covers.json"
    before = json.loads(path.read_text())["reviews"][0]
    (tmp_path / "one.jpg").write_bytes(b"changed pixels not reviewed")
    tags.save_cover_reviews([row], [{**review, "file": "two.jpg"}], tmp_path, merge=True)
    after = json.loads(path.read_text())["reviews"]
    assert len(after) == 2 and next(r for r in after if r["file"] == "one.jpg") == before
