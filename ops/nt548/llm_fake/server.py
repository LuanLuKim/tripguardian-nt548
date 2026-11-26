"""Fake OpenAI-compatible LLM for the NT548 stack (no GPU, no key): stands in behind scripts/model_gateway.py.

    GET  /v1/models
    POST /v1/chat/completions   (stream or not)
    GET  /healthz

The reply is deterministic: the same model + messages give the same text. Environment, read at start:

    FAKE_VERSION      label in every reply, header X-Fake-Version and system_fingerprint (default v1)
    FAKE_MODELS       comma-separated ids for /v1/models; any model is answered anyway (default gemma26b-a4b)
    FAKE_DELAY_MS     added before every completion (default 0)
    FAKE_ERROR_RATE   share of completions answered with FAKE_ERROR_STATUS, 0..1 (default 0)
    FAKE_ERROR_STATUS status of an injected error (default 500)
    FAKE_SEED         seed of the error draw, so a run can be repeated (default: random)
    FAKE_BAD_JSON_RATE share of JSON-mode replies (response_format json_object) that are broken JSON, 0..1 (default 0):
                      a model version that answers but breaks the format, for the eval gate (#16)

With response_format {"type": "json_object"} the reply is a JSON object {"answer", "version"}.

usage: python ops/nt548/llm_fake/server.py [--host 0.0.0.0] [--port 8000]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

log = logging.getLogger("llm_fake")

WORDS = ("Đà Lạt", "hồ Xuân Hương", "đồi chè", "cà phê", "chợ đêm", "thông", "sương sớm", "bánh căn", "đèo", "thác")


@dataclass
class Settings:
    version: str = "v1"
    models: tuple[str, ...] = ("gemma26b-a4b",)
    delay_ms: int = 0
    error_rate: float = 0.0
    error_status: int = 500
    bad_json_rate: float = 0.0
    seed: int | None = None
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.error_rate <= 1.0:
            raise ValueError(f"FAKE_ERROR_RATE must be within 0..1, got {self.error_rate}")
        if not 0.0 <= self.bad_json_rate <= 1.0:
            raise ValueError(f"FAKE_BAD_JSON_RATE must be within 0..1, got {self.bad_json_rate}")
        if self.delay_ms < 0:
            raise ValueError(f"FAKE_DELAY_MS must be >= 0, got {self.delay_ms}")
        self.rng = random.Random(self.seed)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        seed = env.get("FAKE_SEED", "").strip()
        return cls(
            version=env.get("FAKE_VERSION", "v1"),
            models=tuple(m.strip() for m in env.get("FAKE_MODELS", "gemma26b-a4b").split(",") if m.strip()),
            delay_ms=int(env.get("FAKE_DELAY_MS", "0")),
            error_rate=float(env.get("FAKE_ERROR_RATE", "0")),
            error_status=int(env.get("FAKE_ERROR_STATUS", "500")),
            bad_json_rate=float(env.get("FAKE_BAD_JSON_RATE", "0")),
            seed=int(seed) if seed else None,
        )


def reply_text(version: str, model: str, messages: list) -> str:
    """Same version + model + messages -> same text; a short Vietnamese sentence the UI can show."""
    digest = hashlib.sha256(json.dumps([model, messages], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    picks = [WORDS[int(digest[i:i + 2], 16) % len(WORDS)] for i in range(0, 8, 2)]
    return f"[fake {version}] Gợi ý: {picks[0]}, {picks[1]}, {picks[2]} và {picks[3]}. (ref {digest[:12]})"


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="llm-fake")
    headers = {"X-Fake-Version": settings.version}

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        return JSONResponse({"ok": True, "version": settings.version}, headers=headers)

    @app.get("/v1/models")
    def models() -> JSONResponse:
        data = [{"id": m, "object": "model", "created": 0, "owned_by": f"llm-fake-{settings.version}"} for m in settings.models]
        return JSONResponse({"object": "list", "data": data}, headers=headers)

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({"error": {"message": "body is not JSON", "type": "invalid_request_error"}}, 400, headers)
        messages = body.get("messages") if isinstance(body, dict) else None
        if not isinstance(messages, list) or not messages:
            return JSONResponse({"error": {"message": "messages must be a non-empty list", "type": "invalid_request_error"}}, 400, headers)
        model = str(body.get("model") or settings.models[0])
        if settings.delay_ms:
            await asyncio.sleep(settings.delay_ms / 1000)
        if settings.error_rate and settings.rng.random() < settings.error_rate:
            log.error("injected error status=%d model=%s version=%s", settings.error_status, model, settings.version)
            return JSONResponse({"error": {"message": "injected failure (FAKE_ERROR_RATE)", "type": "server_error"}},
                                settings.error_status, headers)
        text = reply_text(settings.version, model, messages)
        fmt = body.get("response_format") if isinstance(body.get("response_format"), dict) else {}
        if fmt.get("type") == "json_object":
            text = json.dumps({"answer": text, "version": settings.version}, ensure_ascii=False)
            if settings.bad_json_rate and settings.rng.random() < settings.bad_json_rate:
                text = text[: len(text) // 2]  # cut off mid-object, as a model hitting max_tokens does
        cid = "chatcmpl-fake-" + hashlib.sha256(text.encode()).hexdigest()[:16]
        created = int(time.time())
        log.info("completion model=%s version=%s stream=%s", model, settings.version, bool(body.get("stream")))
        if body.get("stream"):
            return StreamingResponse(stream(cid, created, model, text, settings.version), media_type="text/event-stream", headers=headers)
        n_in = sum(len(str(m.get("content", "")).split()) for m in messages if isinstance(m, dict))
        n_out = len(text.split())
        return JSONResponse({
            "id": cid, "object": "chat.completion", "created": created, "model": model,
            "system_fingerprint": f"llm-fake-{settings.version}",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": n_in, "completion_tokens": n_out, "total_tokens": n_in + n_out},
        }, headers=headers)

    return app


async def stream(cid: str, created: int, model: str, text: str, version: str):
    """OpenAI chat.completion.chunk events: the role, the text word by word, the stop, then [DONE]."""
    def chunk(delta: dict, finish: str | None = None) -> str:
        return "data: " + json.dumps({
            "id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
            "system_fingerprint": f"llm-fake-{version}",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }, ensure_ascii=False) + "\n\n"

    yield chunk({"role": "assistant", "content": ""})
    words = text.split(" ")
    for i, word in enumerate(words):
        yield chunk({"content": word if i == 0 else " " + word})
    yield chunk({}, "stop")
    yield "data: [DONE]\n\n"


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    log.info("llm-fake %s on :%d delay_ms=%d error_rate=%.2f", settings.version, args.port, settings.delay_ms, settings.error_rate)
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
