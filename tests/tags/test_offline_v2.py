"""Offline membership cache must survive releases and fail closed on fabricated quotes."""
import asyncio
import copy
import json

from corpus.tags import of_record
from corpus.tags.offline import candidates, judge_places


def source():
    return {"place_id": "test:place", "name": "Poodle cafe", "group": "cafe", "category": "Quán cà phê",
            "features": {"animals": [{"quote": "Có bé poodle của quán dễ thương", "source": "gmaps", "value": "present"}]},
            "dishes": [], "styles": [], "record": {"id": "test:place", "identity": {"name": "Poodle cafe", "category_group": "cafe"},
                "experience": {"animals": {"value": "present", "status": "VERIFIED", "n": 1, "evidence": ["a"]}}}}


def test_one_call_per_place_incremental_across_releases(tmp_path, monkeypatch):
    calls = []
    async def ask(row, cs):
        calls.append(row["place_id"])
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"], "reason": "resident pet"} for c in cs]}
    row = source()
    first = asyncio.run(judge_places([row], tmp_path, ask=ask, parallel=1))
    second = asyncio.run(judge_places([copy.deepcopy(row)], tmp_path, ask=ask, parallel=1))
    assert first["calls"] == 1 and second["calls"] == 0 and len(calls) == 1
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert "animals" in of_record(row["record"]).features
    row["record"]["experience"]["animals"]["evidence"] = ["changed"]
    assert "animals" not in of_record(row["record"]).features
    third = asyncio.run(judge_places([row], tmp_path, ask=ask, parallel=1))
    assert third["calls"] == 1


def test_judge_cannot_invent_quote_or_omit_a_candidate(tmp_path):
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": "invented", "reason": "wrong"} for c in cs]}
    result = asyncio.run(judge_places([source()], tmp_path, ask=ask, parallel=1))
    assert result["invalid"] >= 1
    data = json.loads((tmp_path / "tag_membership/current.json").read_text())
    assert data["places"]["test:place"]["experience:animals"]["verdict"] == "unclear"


def test_old_prompt_decision_is_not_read_as_current_membership(tmp_path, monkeypatch):
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"], "reason": "fits"} for c in cs]}
    row = source()
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    path = tmp_path / "tag_membership/current.json"
    doc = json.loads(path.read_text())
    doc["places"]["test:place"]["experience:animals"]["prompt_hash"] = "obsolete-prompt"
    path.write_text(json.dumps(doc))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert "animals" not in of_record(row["record"]).features


def test_raw_judge_answer_is_available_for_invalid_evidence_audit(tmp_path):
    async def ask(row, cs):
        return {"items": [{"tag": "experience:animals", "verdict": "yes", "quote": "invented", "reason": "wrong"}]}
    asyncio.run(judge_places([source()], tmp_path, ask=ask))
    answers = list((tmp_path / "tag_membership/answers").glob("*/*.json"))
    assert len(answers) == 1
    assert json.loads(answers[0].read_text())["items"][0]["quote"] == "invented"


def test_existing_cache_is_revalidated_without_calling_model(tmp_path):
    from corpus.tags.offline import cache_key
    from corpus.tags.membership import digest
    row = source()
    row["record"]["menu"] = {"items": []}
    cs = candidates(row)
    c = next(c for c in cs if c["tag"] == "experience:animals")
    folder = tmp_path / "tag_membership/cache" / digest(row["place_id"])[:24]
    folder.mkdir(parents=True)
    cached = {"verdict": "yes", "quote": "invented", "reason": "obsolete validation"}
    (folder / f"{cache_key(c)}.json").write_text(json.dumps(cached))
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "unclear", "quote": "", "reason": "unknown"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    current = json.loads((tmp_path / "tag_membership/current.json").read_text())
    assert current["places"]["test:place"]["experience:animals"]["verdict"] == "unclear"


def test_keyed_judgement_copies_only_the_selected_candidates_original_quote(tmp_path):
    row = source()
    async def ask(row, cs):
        return {"items": {c["tag"]: {"verdict": "yes", "quote_index": 0,
                                  "support": "visitor_experience", "reason": "resident pet"} for c in cs}}
    result = asyncio.run(judge_places([row], tmp_path, ask=ask))
    doc = json.loads((tmp_path / "tag_membership/current.json").read_text())
    item = doc["places"]["test:place"]["experience:animals"]
    assert result["invalid"] == 0
    assert item["verdict"] == "yes"
    assert item["quote"] == "Có bé poodle của quán dễ thương"


def test_keyed_judgement_cannot_select_a_missing_or_boolean_quote_index(tmp_path):
    async def ask(row, cs):
        return {"items": {c["tag"]: {"verdict": "yes", "quote_index": True,
                                  "support": "visitor_experience", "reason": "bad index"} for c in cs}}
    result = asyncio.run(judge_places([source()], tmp_path, ask=ask))
    assert result["invalid"] >= 1
    doc = json.loads((tmp_path / "tag_membership/current.json").read_text())
    assert doc["places"]["test:place"]["experience:animals"]["verdict"] == "unclear"


def test_online_style_membership_rejects_a_changed_supporting_image(tmp_path):
    from corpus.tags import vocab
    from corpus.tags.membership import decisions
    row = source()
    row["styles"] = ["minimal"]
    row["style_evidence"] = {"minimal": [{"file": "photo.jpg", "quote": "Sparse room"}]}
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"reviewed-photo")
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"],
                            "support": "visual_design", "reason": "sparse design"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    assert decisions(row["record"], ["minimal"], tmp_path)["style:minimal"] == "yes"
    photo.write_bytes(b"different-photo")
    assert "minimal" not in vocab.of_record(row["record"], ["minimal"], root=tmp_path).styles


def test_source_evidence_hash_is_order_independent():
    row = source()
    row["features"]["animals"].append({"quote": "Khách chơi cùng bé chó của quán", "source": "gmaps", "value": "present"})
    before = {c["tag"]: c["evidence_hash"] for c in candidates(row)}
    row["features"]["animals"].reverse()
    assert before == {c["tag"]: c["evidence_hash"] for c in candidates(row)}
