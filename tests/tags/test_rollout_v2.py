"""Unapproved membership stays disabled; legacy refs remain readable in either mode."""
import copy

import pytest

from corpus.tags import Fixed, PlaceTags, of_record, resolve_ref, split

from corpus.tags import vocab


def test_disabled_rollout_preserves_deployed_membership_and_vocabulary(monkeypatch):
    cfg = copy.deepcopy(vocab.config())
    cfg["membership"]["enabled"] = False
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg, raising=False)
    record = {"id": "p", "identity": {"name": "Karaoke X", "category_group": "bar"},
              "experience": {"animals": {"value": "present", "status": "VERIFIED", "n": 1, "mention_rate": .001},
                             "heritage_architecture": {"value": "present", "status": "VERIFIED", "n": 1}}}
    tags = of_record(record, ["minimal"])
    assert tags.group == "bar" and tags.features == frozenset({"animals", "heritage_architecture"})
    assert tags.styles == frozenset({"minimal"})
    assert vocab.label("experience", "sunset_view") == "Ngắm hoàng hôn, bình minh"
    assert resolve_ref("experience:heritage_architecture") == ("experience", "heritage_architecture")
    assert resolve_ref("experience:retired") is None


def test_offline_judge_builds_pending_vocabulary_without_enabling_online(tmp_path, monkeypatch):
    import asyncio
    import json
    from corpus.tags import judge_places
    cfg = copy.deepcopy(vocab.raw_config())
    cfg["membership"]["enabled"] = False
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg)
    row = {"place_id": "p", "name": "Đồi bình minh", "category": "Đồi", "styles": [],
           "record": {"id": "p", "identity": {"name": "Đồi bình minh", "category_group": "nature"}},
           "features": {"sunset_view": [{"quote": "Ngắm bình minh từ đồi", "source": "gmaps_review"}]}}
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"], "reason": "fits"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    got = json.loads((tmp_path / "tag_membership/current.json").read_text())
    assert "experience:sunrise_view" in got["places"]["p"]
    assert vocab.enabled() is False
    assert "sunrise_view" not in vocab.config()["features"]


def test_offline_audit_reads_pending_membership_without_enabling_online(tmp_path, monkeypatch):
    import asyncio
    import json
    from corpus.tags import judge_places, run_audit
    cfg = copy.deepcopy(vocab.raw_config())
    cfg["membership"]["enabled"] = False
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg)
    row = {"place_id": "p", "name": "Đồi bình minh", "category": "Đồi", "styles": [],
           "record": {"id": "p", "identity": {"name": "Đồi bình minh", "category_group": "nature"}},
           "features": {"sunset_view": [{"quote": "Ngắm bình minh từ đồi", "source": "gmaps_review"}]}}
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"], "reason": "fits"} for c in cs]}
    asyncio.run(judge_places([row], tmp_path, ask=ask))
    inputs, gold = tmp_path / "input.jsonl", tmp_path / "gold.jsonl"
    inputs.write_text(json.dumps(row) + "\n")
    gold.write_text(json.dumps({"place_id": "p", "tag": "experience:sunrise_view", "gold": "yes", "split": "dev"}) + "\n")
    result = run_audit(inputs, gold, tmp_path / "audit", tmp_path, subset="dev")
    assert result["total"]["tp"] == 1
    assert vocab.enabled() is False
    assert "sunrise_view" not in vocab.config()["features"]


@pytest.mark.parametrize("enabled", [False, True])
def test_subtag_pair_guard_changes_only_the_enabled_reader(monkeypatch, enabled):
    cfg = copy.deepcopy(vocab.raw_config())
    cfg["membership"]["enabled"] = enabled
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg)
    places = [PlaceTags(f"{feature}:{i}", "bar", frozenset({feature}))
              for feature in ("animals", "hiking", "long_stay_chill") for i in range(6)]
    got = split(places, Fixed(groups=frozenset({"bar"})))
    if enabled:
        assert got is None
    else:
        assert got.axis == "experience" and got.covered == 18


def test_enabled_rollout_uses_strong_membership_and_new_alias(monkeypatch):
    cfg = copy.deepcopy(vocab.config())
    cfg["membership"]["enabled"] = True
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg, raising=False)
    record = {"id": "p", "identity": {"name": "Karaoke X", "category_group": "bar"},
              "experience": {"animals": {"value": "present", "status": "VERIFIED", "n": 1, "mention_rate": .001}}}
    tags = of_record(record, ["minimal"])
    assert tags.group == "karaoke" and not tags.features and not tags.styles
    assert resolve_ref("experience:heritage_architecture") == ("experience", "historical_site")
