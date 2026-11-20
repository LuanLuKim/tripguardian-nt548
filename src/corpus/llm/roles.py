"""Model roles (docs/CORPUS.md, Vai trò model): which .env keys point each role at its model.

Which model fills a role is config (docs/LLM_PROVIDER.md); code asks for a role, never for a model.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import AsyncOpenAI

from ..crawl.common.files import ROOT


@dataclass(frozen=True)
class Role:
    name: str
    purpose: str
    key_env: str
    base_url_env: str
    model_env: str
    guided: bool = True  # the server honours response_format json_schema; False: the schema goes in the prompt
    parallel_env: str | None = None  # .env key: concurrent calls the endpoint takes (docs/LLM_PROVIDER.md)
    default_parallel: int = 36  # without parallel_env: the UIT key allows 40 (HTTP 429 above)
    reasoning_env: str | None = None  # .env key: reasoning effort sent to a reasoning model (low, medium, ...)
    fallback: "Role | None" = None  # a .env key of this role that is unset is read from the same key of this role

    def _on_uit(self) -> bool:
        """EXTRACTOR_ON_UIT=1 (process environment): this process runs the Extractor on the UIT Gemma, so a second
        process can work beside one on the LAN host (docs/LLM_PROVIDER.md §UIT API)."""
        return self.name == "extractor" and os.environ.get("EXTRACTOR_ON_UIT", "").strip() not in ("", "0")

    def also_uit(self) -> bool:
        """EXTRACTOR_ALSO_UIT=1 (process environment): an Extractor task that spreads calls over endpoints
        (`gmaps observe`) uses the UIT Gemma beside the LAN host (docs/LLM_PROVIDER.md §UIT API)."""
        return (self.name == "extractor" and not self._on_uit()
                and os.environ.get("EXTRACTOR_ALSO_UIT", "").strip() not in ("", "0"))

    def also_selfhost(self) -> bool:
        """EXTRACTOR_ALSO_SELFHOST=1 (process environment): an Extractor task that spreads calls over endpoints
        (`gmaps observe`) also uses the self-hosted Gemma behind the model gateway (docs/LLM_PROVIDER.md)."""
        return self.name == "extractor" and os.environ.get("EXTRACTOR_ALSO_SELFHOST", "").strip() not in ("", "0")

    @staticmethod
    def selfhost_client() -> tuple[AsyncOpenAI, str, int]:
        """(client, model, parallel) of the self-hosted Gemma: SELFHOST_EXTRACTOR_* in .env, key MODEL_GATEWAY_API_KEY."""
        load_dotenv(ROOT / ".env")
        return (AsyncOpenAI(api_key=os.environ["MODEL_GATEWAY_API_KEY"], base_url=os.environ["SELFHOST_EXTRACTOR_BASE_URL"]),
                os.environ["SELFHOST_EXTRACTOR_MODEL"], int(os.environ.get("SELFHOST_EXTRACTOR_PARALLEL") or 8))

    @staticmethod
    def uit_client() -> tuple[AsyncOpenAI, str]:
        load_dotenv(ROOT / ".env")
        return AsyncOpenAI(api_key=os.environ["UIT_API_KEY"], base_url=os.environ["UIT_API_BASE_URL"]), os.environ["UIT_API_MODEL"]

    def _on_selfhost(self) -> bool:
        """EXTRACTOR_ON_SELFHOST=1 (process environment): this process runs the Extractor on the self-hosted Gemma
        behind the model gateway, so a third process can work beside the LAN and UIT ones."""
        return self.name == "extractor" and os.environ.get("EXTRACTOR_ON_SELFHOST", "").strip() not in ("", "0")

    def client(self) -> tuple[AsyncOpenAI, str]:
        if self._on_selfhost():
            return self.selfhost_client()[:2]
        if self._on_uit():
            return self.uit_client()
        return self.own_client()

    def own_client(self) -> tuple[AsyncOpenAI, str]:
        """The role's own endpoint from .env, even in an EXTRACTOR_ON_UIT process (a UIT run borrowing the LAN host)."""
        load_dotenv(ROOT / ".env")
        return (AsyncOpenAI(api_key=self._env("key_env", required=True), base_url=self._env("base_url_env", required=True)),
                self._env("model_env", required=True))

    def _env(self, attr: str, required: bool = False) -> str | None:
        """The value of this role's .env key `attr` (key_env, base_url_env, ...), else the fallback role's."""
        name = getattr(self, attr)
        value = (os.environ.get(name or "") or "").strip()
        if value:
            return value
        if self.fallback is not None:
            return self.fallback._env(attr, required)
        if required:
            return os.environ[name]  # KeyError names the missing key
        return None

    def reasoning(self) -> str | None:
        """The reasoning effort the role's model is asked for, or None to send none (a model without reasoning)."""
        load_dotenv(ROOT / ".env")
        return self._env("reasoning_env")

    def cache_key(self, task: str) -> dict:
        """Extra body for a call on a reasoning endpoint (OpenAI style, through 9router): one prompt cache key per
        task, so every session's calls share the cached static prompt. Nothing for other endpoints (vLLM)."""
        return {"prompt_cache_key": f"tripguardian-{task}"} if self.reasoning() else {}

    def parallel(self) -> int:
        """Concurrent calls a task of this role runs when it sets none itself."""
        if self._on_selfhost():
            return self.selfhost_client()[2]
        if self._on_uit():
            # the UIT key takes 40; two stay free for the Agent. UIT_EXTRACTOR_PARALLEL in the process environment
            # lowers it when several processes share the key.
            return int(os.environ.get("UIT_EXTRACTOR_PARALLEL") or 38)
        return self.own_parallel()

    def own_parallel(self) -> int:
        load_dotenv(ROOT / ".env")
        return int(os.environ.get(self.parallel_env or "") or self.default_parallel)


EXTRACTOR = Role(
    name="extractor",
    purpose="high-volume, cheap calls: one small judgement or extraction per item",
    key_env="LLM_API_KEY", base_url_env="EXTRACTOR_BASE_URL", model_env="EXTRACTOR_MODEL",
    parallel_env="EXTRACTOR_PARALLEL",
)

# The Judge roles run on the UIT Gemma (docs/LLM_PROVIDER.md §UIT API): the key takes 40
# concurrent calls, 38 of them here. The live Agent has its own endpoint and credentials.
UIT = dict(key_env="UIT_API_KEY", base_url_env="UIT_API_BASE_URL", model_env="UIT_API_MODEL", default_parallel=38)

JUDGE = Role(
    name="judge",
    purpose="low-volume checks that gate what gets published",
    **UIT,
)

JUDGE_FIRST = Role(
    name="judge_first",
    purpose="optional cheaper first reader for the audit: its 'correct' stands, anything else goes to the Judge",
    **{**UIT, "model_env": "JUDGE_FIRST_MODEL"},  # unset = no first reader (judge.audit.first_reader)
)

JUDGE_STRONG = Role(
    name="judge_strong",
    purpose="the Judge's hardest calls: values that widen choices (suitable for elderly, kids, wheelchair)",
    **UIT,
)

AGENT = Role(
    name="agent",
    purpose="live conversation turns: one streamed structured call per user message (src/trip)",
    key_env="AGENT_API_KEY", base_url_env="AGENT_BASE_URL", model_env="AGENT_MODEL",
    reasoning_env="AGENT_REASONING_EFFORT",
)

NAVIGATOR = Role(
    name="navigator",
    purpose="decides what to mine for a city, from the city name alone (corpus.navigate); the Agent route unless NAVIGATOR_* says otherwise",
    key_env="NAVIGATOR_API_KEY", base_url_env="NAVIGATOR_BASE_URL", model_env="NAVIGATOR_MODEL",
    reasoning_env="NAVIGATOR_REASONING_EFFORT", fallback=AGENT, default_parallel=1,
)

WRITER = Role(
    name="writer",
    purpose="offline Vietnamese copy from given evidence only (corpus.intro: a place's introduction); the Agent route unless WRITER_* says otherwise",
    key_env="WRITER_API_KEY", base_url_env="WRITER_BASE_URL", model_env="WRITER_MODEL",
    reasoning_env="WRITER_REASONING_EFFORT", fallback=AGENT, default_parallel=4,
    guided=False,  # 9router does not enforce strict schemas: the schema goes in the prompt
)

TRENDS = Role(
    name="trends",
    purpose="the nightly Trending bulletin's reading (corpus.events: a page's events, the season names grouped); the Gemma "
            "Judge marked most of a festival's own pages 'not in the city' (2026-11-18), so it takes the Agent route "
            "(terra on 9router) unless TRENDS_* says otherwise",
    key_env="TRENDS_API_KEY", base_url_env="TRENDS_BASE_URL", model_env="TRENDS_MODEL",
    reasoning_env="TRENDS_REASONING_EFFORT", fallback=AGENT, default_parallel=4,
    guided=False,  # 9router does not enforce strict schemas: the schema goes in the prompt
)

USER_SIM = Role(
    name="user_sim",
    purpose="benchmark only: plays a traveller from a hidden trip (python -m bench, --live / --briefs)",
    key_env="USER_SIM_API_KEY", base_url_env="USER_SIM_BASE_URL", model_env="USER_SIM_MODEL",
)
