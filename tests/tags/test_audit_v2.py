"""Audit uses its explicit data root and includes independent positive denominators."""
import asyncio
import json

from corpus.tags import judge_places, run_audit
from corpus.tags.audit import metrics


def test_metrics_keep_false_negatives_and_unknown_gold_separate():
    gold = [{"place_id": "a", "tag": "experience:animals", "gold": "yes"},
            {"place_id": "b", "tag": "experience:animals", "gold": "yes"},
            {"place_id": "c", "tag": "experience:animals", "gold": "unclear"}]
    got = metrics(gold, {("a", "experience:animals"): True, ("c", "experience:animals"): True})
    assert got["total"]["precision"] == .5 and got["total"]["recall"] == .5
    assert got["total"]["fn"] == 1


def test_audit_gate_never_calls_unmeasured_precision_a_pass():
    from corpus.tags.audit import quality_gates
    score = metrics([{"place_id": "a", "tag": "experience:animals", "gold": "yes"}], {})
    gate = quality_gates(score, ["experience:animals", "experience:cloud_hunting"])
    assert not gate["passed"]
    assert gate["unmeasured_precision"] == ["experience:animals", "experience:cloud_hunting"]
    assert gate["low_recall"] == ["experience:animals"]
    assert gate["targets"] == {"precision_per_tag": .9, "precision_total": .93, "recall_per_tag": .6}


def test_audit_gate_checks_each_tag_even_when_total_precision_is_high():
    from corpus.tags.audit import quality_gates
    gold = [{"place_id": str(i), "tag": "category:cafe", "gold": "yes"} for i in range(30)]
    gold += [{"place_id": "rat", "tag": "experience:animals", "gold": "no"}]
    score = metrics(gold, {(r["place_id"], r["tag"]): True for r in gold})
    assert score["total"]["precision"] > .93
    gate = quality_gates(score, ["category:cafe", "experience:animals"])
    assert not gate["passed"] and gate["low_precision"] == ["experience:animals"]


def test_audit_tree_keeps_machine_readable_subtag_membership_for_cover_checks(tmp_path):
    rows = []
    for group in ("cafe", "camping", "attraction"):
        for i in range(4):
            pid = f"{group}{i}"
            rows.append({"place_id": pid, "name": pid, "category": group, "styles": [],
                "record": {"id": pid, "identity": {"name": pid, "category_group": group}},
                "features": {"cloud_hunting": [{"quote": "Săn mây từ đồi vào buổi sáng", "source": "gmaps_review"}]}})
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"], "reason": "fits"} for c in cs]}
    asyncio.run(judge_places(rows, tmp_path, ask=ask))
    inputs, gold = tmp_path / "inputs.jsonl", tmp_path / "gold.jsonl"
    inputs.write_text("".join(json.dumps(r) + "\n" for r in rows))
    gold.write_text(json.dumps({"place_id": "cafe0", "tag": "experience:cloud_hunting", "gold": "yes", "split": "dev"}) + "\n")
    result = run_audit(inputs, gold, tmp_path / "audit", tmp_path, subset="dev")
    branch = result["tree"]["experience:cloud_hunting"]
    assert len(branch["place_ids"]) == 12
    assert {s["ref"] for s in branch["subtags"]} == {"category:cafe", "category:camping", "category:attraction"}
    assert all(s["count"] == 4 and len(s["place_ids"]) == 4 for s in branch["subtags"])


def test_audit_reads_requested_offline_root_not_process_data_dir(tmp_path, monkeypatch):
    row = {"place_id": "p", "name": "Cat cafe", "category": "Quán cà phê", "styles": [],
           "record": {"id": "p", "identity": {"name": "Cat cafe", "category_group": "cafe"}},
           "features": {"animals": [{"quote": "Khách chơi với mèo của quán", "source": "gmaps_review"}]}}
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"], "reason": "fits"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path / "offline", ask=ask))
    inputs, gold = tmp_path / "input.jsonl", tmp_path / "gold.jsonl"
    inputs.write_text(json.dumps(row) + "\n")
    gold.write_text(json.dumps({"place_id": "p", "tag": "experience:animals", "gold": "yes", "split": "holdout"}) + "\n")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "unrelated"))
    got = run_audit(inputs, gold, tmp_path / "output", tmp_path / "offline")
    assert got["total"]["tp"] == 1 and got["total"]["fn"] == 0
    assert "Cat cafe" in (tmp_path / "output/tree-after.txt").read_text()


def test_review_shows_exact_category_judge_quote(tmp_path):
    row = {"place_id": "p", "name": "Quán cà phê X", "category": "Quán cà phê", "styles": [],
           "record": {"id": "p", "identity": {"name": "Quán cà phê X", "category_group": "cafe"}}, "features": {}}
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": "Quán cà phê X", "reason": "identity"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    inputs, gold = tmp_path / "input.jsonl", tmp_path / "gold.jsonl"
    inputs.write_text(json.dumps(row) + "\n")
    gold.write_text(json.dumps({"place_id": "p", "tag": "category:cafe", "gold": "yes", "split": "dev"}) + "\n")
    run_audit(inputs, gold, tmp_path / "output", tmp_path, subset="dev")
    page = (tmp_path / "output/review.html").read_text()
    assert "<blockquote>Quán cà phê X</blockquote>" in page
    assert "Chưa đọc được câu gốc." not in page


def test_style_review_embeds_the_judged_image_not_an_arbitrary_place_photo(tmp_path):
    import base64
    from io import BytesIO
    from PIL import Image

    photo = tmp_path / "support.jpg"
    Image.new("RGB", (30, 30), "red").save(photo)
    row = {"place_id": "p", "name": "Minimal cafe", "category": "Quán cà phê", "styles": ["minimal"],
           "record": {"id": "p", "identity": {"name": "Minimal cafe", "category_group": "cafe"}},
           "features": {}, "style_evidence": {"minimal": [{"file": "support.jpg", "quote": "Clean open room"}]}}
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"],
                           "support": "visual_design"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    inputs, gold = tmp_path / "input.jsonl", tmp_path / "gold.jsonl"
    inputs.write_text(json.dumps(row) + "\n")
    gold.write_text(json.dumps({"place_id": "p", "tag": "style:minimal", "gold": "yes", "split": "dev"}) + "\n")
    run_audit(inputs, gold, tmp_path / "output", tmp_path, subset="dev")
    page = (tmp_path / "output/review.html").read_text()
    style = page.split("Minimal cafe", 1)[1]
    assert 'alt="Ảnh bằng chứng style:minimal"' in style
    image = style.split('src="data:image/jpeg;base64,', 1)[1].split('"', 1)[0]
    pixel = Image.open(BytesIO(base64.b64decode(image))).getpixel((10, 10))
    assert pixel[0] > 200 and pixel[1] < 30 and pixel[2] < 30
