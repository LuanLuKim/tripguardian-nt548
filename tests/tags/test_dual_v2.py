"""Independent tag Judges must not share results, credentials or semantic votes."""
import asyncio
import json

import pytest

from corpus.tags import offline
from corpus.tags.prompt import TAG_MEMBERSHIP
from test_offline_v2 import source


def response(cs, verdict):
    return {"items": {c["tag"]: {"verdict": verdict, "quote_index": 0,
                               "support": "visitor_experience", "reason": "Independent reading"} for c in cs}}


def test_secondary_role_is_track_local_sol_high():
    task, model, fingerprint = offline.reviewer_task("secondary")
    assert model == "cx/gpt-6.1-sol"
    assert task.role.reasoning() == "high"
    assert task.role.name == "tags_judge_secondary"
    assert task.role.key_env == "AGENT_API_KEY"
    assert task.role is not TAG_MEMBERSHIP.role
    assert TAG_MEMBERSHIP.role.reasoning() is None
    assert fingerprint


def test_secondary_cache_never_reuses_or_overwrites_primary(tmp_path):
    calls = []
    async def first(row, cs):
        calls.append("primary")
        return response(cs, "yes")
    async def second(row, cs):
        assert "judgements" not in row and "gold" not in row
        calls.append("secondary")
        return response(cs, "no")
    asyncio.run(offline.judge_places([source()], tmp_path, ask=first))
    primary = (tmp_path / "tag_membership/current.json").read_bytes()
    result = asyncio.run(offline.judge_places([source()], tmp_path, ask=second, reviewer="secondary"))
    assert result["calls"] == 1
    assert (tmp_path / "tag_membership/current.json").read_bytes() == primary
    result = asyncio.run(offline.judge_places([source()], tmp_path, ask=second, reviewer="secondary"))
    assert result["calls"] == 0
    assert calls == ["primary", "secondary"]


def test_disagreement_is_unknown_and_review_is_bounded_without_gold(tmp_path):
    async def first(row, cs):
        return response(cs, "yes")
    async def second(row, cs):
        return response(cs, "no")
    row = source()
    asyncio.run(offline.judge_places([row], tmp_path, ask=first))
    asyncio.run(offline.judge_places([row], tmp_path, ask=second, reviewer="secondary"))
    from corpus.tags.dual import compare_judges
    result = compare_judges([row], tmp_path, tmp_path / "review", limit=1)
    assert result["disagreements"] == 2
    assert result["review_items"] == 1
    doc = json.loads((tmp_path / "tag_membership/consensus.json").read_text())
    assert doc["places"][row["place_id"]]["experience:animals"]["verdict"] == "unclear"
    page = (tmp_path / "review/review.html").read_text()
    assert "Có bé poodle" in page and "Independent reading" in page
    assert "CHƯA ĐẠT" in page
    with pytest.raises(ValueError):
        compare_judges([row], tmp_path, tmp_path / "review", limit=61)


def test_secondary_model_change_invalidates_only_secondary_cache(tmp_path, monkeypatch):
    async def ask(row, cs):
        return response(cs, "yes")
    asyncio.run(offline.judge_places([source()], tmp_path, ask=ask, reviewer="secondary"))
    from corpus.tags import vocab
    cfg = vocab.raw_config()
    monkeypatch.setitem(cfg["membership"]["secondary_judge"], "model", "different-model")
    result = asyncio.run(offline.judge_places([source()], tmp_path, ask=ask, reviewer="secondary"))
    assert result["calls"] == 1


def test_audit_can_measure_each_reader_and_consensus_without_changing_online(tmp_path):
    from corpus.tags import run_audit
    async def first(row, cs):
        return response(cs, "yes")
    async def second(row, cs):
        return response(cs, "no")
    row = source()
    asyncio.run(offline.judge_places([row], tmp_path, ask=first))
    asyncio.run(offline.judge_places([row], tmp_path, ask=second, reviewer="secondary"))
    from corpus.tags.dual import compare_judges
    compare_judges([row], tmp_path, tmp_path / "review")
    inputs, gold = tmp_path / "inputs.jsonl", tmp_path / "gold.jsonl"
    inputs.write_text(json.dumps(row) + "\n")
    gold.write_text(json.dumps({"place_id": row["place_id"], "tag": "experience:animals",
                                "gold": "yes", "split": "dev"}) + "\n")
    for reviewer, tp in (("primary", 1), ("secondary", 0), ("consensus", 0)):
        got = run_audit(inputs, gold, tmp_path / reviewer, tmp_path, subset="dev", reviewer=reviewer)
        assert got["total"]["tp"] == tp
        assert got["reviewer"] == reviewer


def test_comparison_is_stable_and_changed_evidence_cannot_keep_a_consensus_yes(tmp_path):
    from corpus.tags.dual import compare_judges
    async def ask(row, cs):
        return response(cs, "yes")
    row = source()
    for reviewer in ("primary", "secondary"):
        asyncio.run(offline.judge_places([row], tmp_path, ask=ask, reviewer=reviewer))
    compare_judges([row], tmp_path, tmp_path / "first")
    path = tmp_path / "tag_membership/consensus.json"
    first = path.read_bytes()
    compare_judges(list(reversed([row])), tmp_path, tmp_path / "second")
    assert path.read_bytes() == first
    row["features"]["animals"][0]["quote"] = "Khách tự mang chó tới quán"
    result = compare_judges([row], tmp_path, tmp_path / "changed")
    assert result["missing"] >= 1
    assert json.loads(path.read_text())["places"][row["place_id"]]["experience:animals"]["verdict"] == "unclear"


def test_metering_records_provider_usage_without_inventing_price():
    from types import SimpleNamespace
    seen, usage = [], []
    class Stream:
        async def __aiter__(self):
            yield SimpleNamespace(usage=SimpleNamespace(model_dump=lambda: {"prompt_tokens": 80, "completion_tokens": 20}))
        async def close(self):
            pass
    async def create(**kwargs):
        seen.append(kwargs)
        return Stream()
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    async def run():
        metered = offline.metered_client(client, usage)
        stream = await metered.chat.completions.create(model="model", stream=True)
        async for _ in stream:
            pass
        await stream.close()
    asyncio.run(run())
    assert seen[0]["stream_options"] == {"include_usage": True}
    assert usage == [{"prompt_tokens": 80, "completion_tokens": 20}]


def test_snapshot_is_batched_but_all_per_tag_results_are_durable(tmp_path, monkeypatch):
    import copy
    writes = []
    write = offline._write
    def tracked(path, value):
        if path.name == "current.json":
            writes.append(path)
        write(path, value)
    monkeypatch.setattr(offline, "_write", tracked)
    rows = []
    for i in range(26):
        row = copy.deepcopy(source())
        row["place_id"] = row["record"]["id"] = f"test:{i}"
        rows.append(row)
    async def ask(row, cs):
        return response(cs, "yes")
    asyncio.run(offline.judge_places(rows, tmp_path, ask=ask))
    assert len(writes) <= 3
    assert len(json.loads((tmp_path / "tag_membership/current.json").read_text())["places"]) == 26
    assert len(list((tmp_path / "tag_membership/cache").glob("*/*.json"))) == 52


def test_owner_review_prioritizes_membership_changes_over_no_unclear_differences(tmp_path):
    from corpus.tags.dual import compare_judges
    async def primary(row, cs):
        answer = response(cs, "no")
        answer["items"]["experience:animals"]["verdict"] = "yes"
        return answer
    async def secondary(row, cs):
        answer = response(cs, "unclear")
        answer["items"]["experience:animals"]["verdict"] = "no"
        return answer
    asyncio.run(offline.judge_places([source()], tmp_path, ask=primary))
    asyncio.run(offline.judge_places([source()], tmp_path, ask=secondary, reviewer="secondary"))
    compare_judges([source()], tmp_path, tmp_path / "review", limit=1)
    chosen = json.loads((tmp_path / "review/review-items.jsonl").read_text())
    assert chosen["tag"] == "experience:animals"


def test_unchanged_image_hash_does_not_reread_the_same_photo(tmp_path, monkeypatch):
    from pathlib import Path
    row = source()
    row["styles"] = ["minimal", "rustic"]
    row["style_evidence"] = {key: [{"file": "photo.jpg", "quote": "Original image"}] for key in row["styles"]}
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"original")
    original, reads = Path.read_bytes, []
    def tracked(path):
        if path == photo:
            reads.append(path)
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", tracked)
    first = offline.candidates(row, root=tmp_path)
    assert offline.candidates(row, root=tmp_path) == first
    assert len(reads) == 1
    photo.write_bytes(b"changed")
    assert offline.candidates(row, root=tmp_path) != first


def test_pending_rollout_defaults_to_consensus_not_a_single_reader():
    import yaml
    from corpus.tags.vocab import PATH
    cfg = yaml.safe_load(PATH.read_text())
    assert cfg["membership"]["enabled"] is False
    assert cfg["membership"]["reader"] == "consensus"


def test_online_consensus_does_not_duplicate_all_offline_source_evidence(tmp_path):
    from corpus.tags.dual import compare_judges
    async def ask(row, cs):
        return response(cs, "yes")
    for reviewer in ("primary", "secondary"):
        asyncio.run(offline.judge_places([source()], tmp_path, ask=ask, reviewer=reviewer))
    compare_judges([source()], tmp_path, tmp_path / "review")
    entry = json.loads((tmp_path / "tag_membership/consensus.json").read_text())["places"]["test:place"]["experience:animals"]
    assert entry["quote"] == "Có bé poodle của quán dễ thương"
    assert not entry.get("evidence")
    assert all("evidence" not in vote for vote in entry["judges"].values())
    raw = json.loads((tmp_path / "tag_membership/current.json").read_text())
    assert raw["places"]["test:place"]["experience:animals"]["evidence"]
