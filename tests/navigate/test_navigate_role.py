import asyncio
import json

from corpus.llm import NAVIGATOR, NAVIGATOR_PLAN, tasks


def _agent_env(monkeypatch):
    for k in ("NAVIGATOR_API_KEY", "NAVIGATOR_BASE_URL", "NAVIGATOR_MODEL", "NAVIGATOR_REASONING_EFFORT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AGENT_API_KEY", "agent-key")
    monkeypatch.setenv("AGENT_BASE_URL", "http://127.0.0.1:20128/v1")
    monkeypatch.setenv("AGENT_MODEL", "agent-model")
    monkeypatch.setenv("AGENT_REASONING_EFFORT", "low")


def test_navigator_falls_back_to_agent_route(monkeypatch):
    _agent_env(monkeypatch)
    client, model = NAVIGATOR.client()
    assert model == "agent-model" and str(client.base_url).startswith("http://127.0.0.1:20128")
    assert NAVIGATOR.reasoning() == "low"


def test_navigator_own_keys_win(monkeypatch):
    _agent_env(monkeypatch)
    monkeypatch.setenv("NAVIGATOR_MODEL", "nav-model")
    monkeypatch.setenv("NAVIGATOR_REASONING_EFFORT", "medium")
    assert NAVIGATOR.client()[1] == "nav-model" and NAVIGATOR.reasoning() == "medium"


class _Chunk:
    def __init__(self, text):
        self.choices = [type("C", (), {"delta": type("D", (), {"content": text})()})()]


class _Stream:
    def __init__(self, text):
        self.text = text

    def __aiter__(self):
        async def gen():
            yield _Chunk(self.text)
        return gen()

    async def close(self):
        pass


class _Client:
    def __init__(self, answer):
        self.answer, self.kw = answer, None
        self.chat = type("Ch", (), {"completions": self})()

    async def create(self, **kw):
        self.kw = kw

        return _Stream(json.dumps(self.answer))


def test_ask_sends_reasoning_effort_and_cache_key(monkeypatch):
    _agent_env(monkeypatch)
    client = _Client({"ok": "x"})
    task = tasks.Task(name="t", role=NAVIGATOR, prompt="hi", max_tokens=10,
                      schema={"type": "object", "properties": {"ok": {"type": "string"}}, "required": ["ok"]})
    assert asyncio.run(task.ask(client, "m")) == {"ok": "x"}
    assert client.kw["reasoning_effort"] == "low"
    assert client.kw["extra_body"]["prompt_cache_key"] == "tripguardian-t"


def test_ask_sends_no_reasoning_for_a_role_without_it(monkeypatch):
    client = _Client({"ok": "x"})
    task = tasks.Task(name="t", role=tasks.EXTRACTOR, prompt="hi", max_tokens=10,
                      schema={"type": "object", "properties": {"ok": {"type": "string"}}, "required": ["ok"]})
    asyncio.run(task.ask(client, "m"))
    assert "reasoning_effort" not in client.kw and "extra_body" not in client.kw


def test_plan_task_uses_the_navigator_and_shows_no_corpus():
    assert NAVIGATOR_PLAN.role is NAVIGATOR
    text = NAVIGATOR_PLAN.render(city="Đà Lạt", area="11.78,108.30 to 12.12,108.66")
    assert "Đà Lạt" in text and "ontology" not in text.lower()


def test_plan_schema_accepts_an_answer_that_leaves_out_what_is_empty():
    answer = {"aspects": [{"key": "cloud_hunting", "name_vi": "Săn mây", "why": "x",
                           "target": {"kind": "feature", "ref": "cloud_hunting"}, "queries": ["săn mây Đà Lạt"]}],
              "general_claims": [{"subject_kind": "city", "subject": "Đà Lạt", "kind": "tip", "text": "x"}]}
    tasks.validate(answer, NAVIGATOR_PLAN.schema)
