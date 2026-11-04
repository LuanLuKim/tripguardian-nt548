import asyncio
import json
from types import SimpleNamespace

import pytest

from corpus.observe.gmaps import extract, visit_observe as vo


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def place(tmp_path, monkeypatch, targeted=False):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(extract, "load_config", lambda city: (city, {}))
    monkeypatch.setattr(extract, "listed", lambda city: None)
    monkeypatch.setattr(vo, "listed", lambda city: None)
    d = tmp_path / "gmaps" / "places" / "F1"
    write(d / "place.json", {"fid": "F1", "name": "Garden", "category": "Vườn",
                             "fetched_at": "2026-11-04T00:00:00+00:00"})
    reviews = [{"review_id": rid, "author_hash": rid, "rating": "5 sao", "published_text": "1 tháng trước",
                "text": f"{rid} có view đẹp, ngồi hết khoảng 2 tiếng, xe điện 40k/lượt",
                "details": ["Độ ồn\nRất yên tĩnh"]} for rid in ("bad", "keep")]
    write(d / "reviews.json", reviews[1:] if targeted else reviews)
    if targeted:
        write(d / "reviews_keywords.json", {"keywords": {"view": {"reviews": reviews[:1]}}})
    return d


def flag(tmp_path, problem="qc_unscored"):
    write(tmp_path / "gmaps" / "qc" / "F1.json",
          {"llm": {"bad_reviews": [{"review_id": "bad", "problem": problem, "reason": "JSONDecodeError"}]}})


async def providers():
    return [(None, "fake", 4)]


async def forbidden_providers():
    pytest.fail("QC-only pruning must not need the model")


@pytest.mark.parametrize("cached", [False, True, "legacy_offline", "legacy_missing_raw"])
@pytest.mark.parametrize("targeted", [False, True])
def test_unscored_review_has_no_evidence_rating_or_voice(tmp_path, monkeypatch, cached, targeted):
    d = place(tmp_path, monkeypatch, targeted)
    calls = []

    async def ask(client, model, **fields):
        calls.append(fields["reviews"])
        return {"reviews": [{"ref": line.split(":", 1)[0], "observations": [
            {"feature": "scenic_view", "value": "present", "quote": "view đẹp", "time_of_day": "unknown",
             "day_type": "unknown", "weather": "unknown"}], "proposed": [], "details": [
            {"kind": "fee", "text": "xe điện", "amount_vnd": 40000, "audience": "", "unit": "item",
             "min_people": 0, "months": [], "days": [], "hour": "", "who": "", "verdict": "",
             "time_of_day": "unknown", "quote": "xe điện 40k/lượt"}]} for line in fields["reviews"].splitlines()]}

    async def verify(*args, **kwargs):
        return {"verdict": "supports", "reason": ""}

    monkeypatch.setattr(extract, "_providers", providers)
    monkeypatch.setattr(extract, "REVIEW_OBSERVE", SimpleNamespace(ask=ask, prompt_hash="fake"))
    monkeypatch.setattr(extract, "verify_claim", verify)
    target = tmp_path / "gmaps" / "observations" / "F1.json"
    if cached:
        asyncio.run(extract.run("test"))
        old = json.loads(target.read_text())
        assert {o["source_id"] for o in old["details"]} == {"bad", "keep"}
        old["proposed"] = [{"source_id": "bad", "label": "bad proposal"},
                           {"source_id": "keep", "label": "kept proposal"}]
        if cached in ("legacy_offline", "legacy_missing_raw"):
            old["prompt_hash"] = "pre-qc-unscored-version"
        write(target, old)
        monkeypatch.setattr(extract, "_providers", forbidden_providers)
        if cached == "legacy_missing_raw":
            if targeted:
                write(d / "reviews_keywords.json", {"keywords": {}})
            else:
                rows = json.loads((d / "reviews.json").read_text())
                write(d / "reviews.json", [r for r in rows if r["review_id"] != "bad"])
    flag(tmp_path)
    if cached in ("legacy_offline", "legacy_missing_raw"):
        async def unavailable():
            return []

        monkeypatch.setattr(extract, "_providers", unavailable)
        with pytest.raises(SystemExit, match="no LLM endpoint"):
            asyncio.run(extract.run("test"))
        if cached == "legacy_missing_raw":
            assert not target.exists(), "No raw provenance remains to safely subtract the review's rating/voice"
            monkeypatch.setattr(extract, "_providers", providers)
            assert asyncio.run(extract.run("test"))["status"] == {"done": 1}
    else:
        result = asyncio.run(extract.run("test"))
        assert result["status"] == {"pruned" if cached else "done": 1}
    doc = json.loads(target.read_text())
    assert {o["source_id"] for o in doc["observations"]} == {"keep"}
    assert {o["source_id"] for o in doc["details"]} == {"keep"}
    assert all(p["source_id"] == "keep" for p in doc["proposed"])
    assert [r["author"] for r in doc["ratings"]] == ["keep"]
    assert (doc["voices"], doc["voices_targeted"]) == (1, 0)
    assert doc["qc_dropped"] == ["bad"]
    if not cached:
        assert all("bad có" not in text for text in calls)
    if cached == "legacy_offline":
        monkeypatch.setattr(extract, "keep_stale", lambda: True)
    assert asyncio.run(extract.run("test"))["status"] == {"cached": 1}
    assert json.loads(target.read_text())["voices"] == 1


@pytest.mark.parametrize("problem", ["qc_unscored", "spam"])
@pytest.mark.parametrize("mode", ["fresh", "cached", "rules", "keep_stale", "new_review",
                                 "missing_raw", "already_marked"])
def test_visit_qc_drops_verified_evidence_even_from_cache(tmp_path, monkeypatch, problem, mode):
    d = place(tmp_path, monkeypatch)
    calls = []

    async def ask(client, model, **fields):
        calls.append(fields["snippets"])
        return {"items": [{"ref": int(line[1:line.index("]")]), "quote": "hết khoảng 2 tiếng",
                           "kind": "own_stay"} for line in fields["snippets"].splitlines()]}

    async def verify(*args, **kwargs):
        return {"verdict": "supports", "reason": ""}

    monkeypatch.setattr(vo, "_providers", providers)
    monkeypatch.setattr(vo, "VISIT_OBSERVE", SimpleNamespace(ask=ask, prompt_hash="fake"))
    monkeypatch.setattr(vo, "VISIT_VERIFY", SimpleNamespace(ask=verify, prompt_hash="fake"))
    target = tmp_path / "gmaps" / vo.FOLDER / "F1.json"
    if mode != "fresh":
        asyncio.run(vo.run("test"))
        assert {o["source_id"] for o in json.loads(target.read_text())["verified"]} == {"bad", "keep"}
        if mode == "rules":
            monkeypatch.setattr(vo, "RULES_VERSION", "next")
        if mode == "keep_stale":
            monkeypatch.setattr(vo, "keep_stale", lambda: True)
        if mode == "missing_raw":
            rows = json.loads((d / "reviews.json").read_text())
            write(d / "reviews.json", [r for r in rows if r["review_id"] != "bad"])
        if mode == "already_marked":
            old = json.loads(target.read_text())
            old["qc_dropped"] = ["bad"]
            write(target, old)
        if mode == "new_review":
            rows = json.loads((d / "reviews.json").read_text())
            write(d / "reviews.json", rows + [{**rows[1], "review_id": "new", "author_hash": "new",
                                               "text": "New visitor ngồi hết khoảng 2 tiếng"}])
        else:
            monkeypatch.setattr(vo, "_providers", forbidden_providers)
    flag(tmp_path, problem)
    asyncio.run(vo.run("test"))
    doc = json.loads(target.read_text())
    expected = {"keep", "new"} if mode == "new_review" else {"keep"}
    assert {o["source_id"] for o in doc["observations"]} == expected
    assert {o["source_id"] for o in doc["verified"]} == expected
    assert doc["qc_dropped"] == ["bad"]
    monkeypatch.setattr(vo, "RULES_VERSION", "another-rule-version")
    monkeypatch.setattr(vo, "_providers", forbidden_providers)
    asyncio.run(vo.run("test"))
    assert {o["source_id"] for o in json.loads(target.read_text())["observations"]} == expected
    if mode == "fresh":
        assert all("bad có" not in text for text in calls)


def test_a_new_qc_drop_reason_does_not_invalidate_every_cached_observation(monkeypatch):
    # 2026-11-04: adding "qc_unscored" to QC_DROP changed cache_key, so a build re-observed all 3261 places of the
    # city for a few dropped reviews. New reasons are applied per place (bad_review_ids -> input_hash, prune).
    ont = extract.load_ontology()
    before = extract.cache_key(ont)
    monkeypatch.setattr(extract, "QC_DROP", extract.QC_DROP | {"some_future_reason"})
    assert extract.cache_key(ont) == before
    assert "qc_unscored" in extract.QC_DROP and "qc_unscored" not in extract.QC_DROP_KEY
