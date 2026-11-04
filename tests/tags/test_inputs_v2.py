"""Release input export is reproducible and never overwrites the frozen gold."""
import json

from corpus import tags


def test_export_reads_original_feature_spans_and_existing_style_photos(tmp_path):
    import lancedb

    source = tmp_path / "data"
    index = source / "index/i1"
    index.mkdir(parents=True)
    (source / "index/current").write_text("i1")
    (source / "serving").mkdir()
    record = {"id": "p:1", "identity": {"name": "Quiet cafe", "category_group": "cafe", "category": "Quán cà phê"}}
    (source / "serving/places.json").write_text(json.dumps({"records": [record]}))
    (index / "places.json").write_text(json.dumps({"p:1": {"styles": ["minimal"]}}))
    lancedb.connect(str(index)).create_table("spans", [{"place_id": "p:1", "quote": "Có bé mèo của quán",
        "features": '["animals=present"]', "observations": '["review:1"]', "source": "gmaps_review"}])
    folder = source / "gmaps/places/p_1/photos"
    folder.mkdir(parents=True)
    (folder / "a.jpg").write_bytes(b"photo-input")
    styles = source / "gmaps/style_observations"
    styles.mkdir()
    (styles / "p_1.json").write_text(json.dumps({"observations": [{"id": "style:1", "feature": "minimal",
        "value": "present", "span": {"quote": "Sparse room", "field": "photos/a.jpg"}}]}))
    out = tmp_path / "inputs.jsonl"
    tags.export_inputs(source, out)
    first = out.read_bytes()
    row = json.loads(first)
    assert row["features"]["animals"][0]["quote"] == "Có bé mèo của quán"
    assert row["styles"] == ["minimal"]
    assert row["style_evidence"]["minimal"][0]["file"] == "gmaps/places/p_1/photos/a.jpg"
    tags.export_inputs(source, out)
    assert out.read_bytes() == first
    assert not (tmp_path / "gold.jsonl").exists()


def test_export_retains_child_photos_as_evidence_for_candidate_parent_style(tmp_path):
    import lancedb

    source = tmp_path / "data"
    index = source / "index/i1"
    index.mkdir(parents=True)
    (source / "index/current").write_text("i1")
    (source / "serving").mkdir()
    record = {"id": "p:1", "identity": {"name": "Old cafe", "category_group": "cafe"}}
    (source / "serving/places.json").write_text(json.dumps({"records": [record]}))
    (index / "places.json").write_text(json.dumps({"p:1": {"styles": ["retro", "french_colonial"]}}))
    lancedb.connect(str(index)).create_table("spans", [{"place_id": "p:1", "quote": "Old house",
        "features": "[]", "observations": "[]", "source": "gmaps_review"}])
    folder = source / "gmaps/places/p_1/photos"
    folder.mkdir(parents=True)
    (folder / "a.jpg").write_bytes(b"photo-input")
    styles = source / "gmaps/style_observations"
    styles.mkdir()
    (styles / "p_1.json").write_text(json.dumps({"observations": [{"id": "style:1", "feature": "french_colonial",
        "value": "present", "span": {"quote": "Old French villa", "field": "photos/a.jpg"}}]}))
    out = tmp_path / "inputs.jsonl"
    tags.export_inputs(source, out)
    row = json.loads(out.read_text())
    assert row["style_evidence"]["retro"][0]["quote"] == "Old French villa"
