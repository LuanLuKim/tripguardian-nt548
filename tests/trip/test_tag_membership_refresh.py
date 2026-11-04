"""A live Browse cache must follow atomic offline tag snapshots and changed supporting pixels."""
import asyncio
import copy
import json
from types import SimpleNamespace

from corpus import tags
from corpus.tags import vocab
from trip.infrastructure.browse import Browse


def test_browse_does_not_keep_a_yes_after_offline_rejudgement(tmp_path, monkeypatch):
    cfg = copy.deepcopy(vocab.raw_config())
    cfg["membership"].update(enabled=True, reader="primary")
    monkeypatch.setattr(vocab, "raw_config", lambda: cfg)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    row = {"place_id": "p", "name": "Cat cafe", "styles": [], "category": "Quán cà phê",
           "record": {"id": "p", "identity": {"name": "Cat cafe", "category_group": "cafe"}},
           "features": {"animals": [{"quote": "Chơi với mèo của quán", "source": "gmaps_review"}]}}
    async def ask(row, cs):
        return {"items": [{"tag": c["tag"], "verdict": "yes", "quote": c["evidence"][0]["quote"]} for c in cs]}
    asyncio.run(tags.judge_places([row], tmp_path, ask=ask))
    k = SimpleNamespace(looks=None, retrieval=SimpleNamespace(get_place=lambda pid: row["record"]))
    browse = Browse(k)
    assert "animals" in browse.place_tags("p").features
    path = tmp_path / "tag_membership/current.json"
    doc = json.loads(path.read_text())
    doc["places"]["p"]["experience:animals"]["verdict"] = "no"
    path.write_text(json.dumps(doc))
    assert "animals" not in browse.place_tags("p").features
