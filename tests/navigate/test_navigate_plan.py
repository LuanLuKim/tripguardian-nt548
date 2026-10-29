import asyncio
import json
from datetime import UTC, datetime

import pytest

from corpus.llm import NAVIGATOR_PLAN
from corpus.navigate import NavigateError, general_claims, load_map, plan

NF_NONE = {"key": "", "type": "none", "values": [], "hint": ""}
ANSWER = {
    "aspects": [{"key": "cloud_hunting", "name_vi": "Săn mây", "why": "Cao nguyên.",
                 "target": {"kind": "feature", "ref": "cloud_hunting", "new_feature": NF_NONE},
                 "queries": ["săn mây Đà Lạt"], "sources": ["web", "tiktok"],
                 "nominees": [{"name": "Đồi Đa Phú", "area_hint": "phường 7"}], "months": [11]}],
    "general_claims": [{"subject_kind": "city", "subject": "Đà Lạt", "kind": "best_time",
                        "text": "Mùa khô ít mưa.", "when": {"months": [12], "days": [], "hours": "", "weather": ""}}],
}


class FakeClient:
    """Stands in for the 9router client: records the call, streams ANSWER."""
    def __init__(self, answer=ANSWER):
        self.answer, self.calls = answer, []
        self.chat = type("Ch", (), {"completions": self})()

    async def create(self, **kw):
        self.calls.append(kw)
        text = json.dumps(self.answer)

        class S:
            def __aiter__(s):
                async def g():
                    yield type("C", (), {"choices": [type("X", (), {"delta": type("D", (), {"content": text})()})()]})()
                return g()

            async def close(s):
                pass
        return S()


NOW = datetime(2026, 10, 28, 10, 0, 0, tzinfo=UTC)


def test_plan_writes_stamped_and_latest_map(data):
    client = FakeClient()
    m = asyncio.run(plan("dalat", client=client, model="sol-x", now=NOW))
    out = data / "dalat" / "navigate"
    assert (out / "mining_map_20261028T100000Z.json").exists()
    latest = json.loads((out / "mining_map.json").read_text(encoding="utf-8"))
    assert latest["model"] == "sol-x" and latest["aspects"][0]["key"] == "cloud_hunting"
    assert latest["general_claims"][0]["source"] == "model" and m.city == "dalat"
    assert load_map("dalat").aspects[0].key == "cloud_hunting"
    assert [c.subject for c in general_claims("dalat")] == ["Đà Lạt"]


def test_plan_makes_one_call_and_shows_sol_only_the_city(data):
    client = FakeClient()
    asyncio.run(plan("dalat", client=client, model="m", now=NOW))
    assert len(client.calls) == 1
    prompt = client.calls[0]["messages"][0]["content"]
    assert "Đà Lạt" in prompt and "11.78" in prompt
    for banned in ("ontology", "scenic_view", "queries.yaml", "data/serving"):
        assert banned not in prompt


def test_no_latest_keeps_the_current_map(data):
    asyncio.run(plan("dalat", client=FakeClient(), model="m", now=NOW))
    other = {**ANSWER, "aspects": [{**ANSWER["aspects"][0], "key": "other_aspect"}]}
    asyncio.run(plan("dalat", client=FakeClient(other), model="m", now=datetime(2026, 10, 29, tzinfo=UTC), latest=False))
    out = data / "dalat" / "navigate"
    assert load_map("dalat").aspects[0].key == "cloud_hunting"
    assert (out / "mining_map_20261029T000000Z.json").exists()


def test_empty_gate_result_never_replaces_the_latest_map(data):
    asyncio.run(plan("dalat", client=FakeClient(), model="m", now=NOW))
    with pytest.raises(NavigateError):
        asyncio.run(plan("dalat", client=FakeClient({"aspects": [], "general_claims": []}), model="m",
                         now=datetime(2026, 10, 29, tzinfo=UTC)))
    assert load_map("dalat").aspects[0].key == "cloud_hunting"


def test_unknown_city(data):
    with pytest.raises(NavigateError):
        asyncio.run(plan("atlantis", client=FakeClient(), model="m"))


def test_web_search_reads_the_map(data):
    from corpus.crawl.web.queries import mining_queries
    asyncio.run(plan("dalat", client=FakeClient(), model="m", now=NOW))
    qs = mining_queries(data, "dalat", "Đà Lạt")
    assert qs and {q.group for q in qs} == {"cloud_hunting"} and len(qs) == 2  # plain + site:tiktok.com


def test_task_is_the_navigator_role():
    assert NAVIGATOR_PLAN.role.name == "navigator"
