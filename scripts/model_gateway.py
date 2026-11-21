"""OpenAI-compatible gateway in front of the self-hosted models (9router style).

One public port, routed by the `model` field or by path prefix:

    POST /v1/chat/completions                     body.model = clef-flash | gemma26b-a4b
    POST /v1/clef-flash[/chat/completions]        forced to clef-flash
    POST /v1/gemma26b-a4b[/chat/completions]      forced to gemma26b-a4b
    GET  /v1/models

gemma26b-a4b is an OpenAI-compatible server (vLLM; llama-server as rollback), proxied as is. With several
--gemma-url the requests go to the upstream with the fewest outstanding requests; an upstream that refuses
the connection or answers 502/503/504 is skipped for --cooldown seconds and the request goes to the next one.
Several --clef-url (clef_server.py replicas) are balanced the same way.
A URL may end in @<weight> (http://llm-v1:8000@90 --gemma-url http://llm-v2:8000@10): once any upstream of a model
has a weight, its requests are split at random in proportion to the weights of the upstreams that are not cooling down
(no suffix counts as 1). An upstream at weight 0 gets traffic only when every weighted one is down: a canary at 0 is
off, yet still a fallback.
clef-flash is a decision model, not a text generator: the chat request is turned
into a SystemOne request and the answers come back as JSON in the message content.
Clef needs `questions` (top-level, or inside a JSON user message); the `state` is
the top-level `state`, the JSON user message's `state`, or the chat text itself.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

CLEF = "clef-flash"
GEMMA = "gemma26b-a4b"


def message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if part.get("type") == "text")
    return ""


def message_images(messages: list[dict[str, Any]]) -> list[str]:
    images = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") == "image_url":
                url = part["image_url"]["url"] if isinstance(part["image_url"], dict) else part["image_url"]
                if not url.startswith("data:"):
                    raise ValueError("clef-flash accepts images only as data: URIs")
                images.append(url)
    return images


def systemone_request(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages") or []
    request: dict[str, Any] = {"model": CLEF}
    texts = [message_text(message) for message in messages if message.get("role") in ("system", "user")]
    last = texts[-1].strip() if texts else ""
    if last.startswith("{"):
        try:
            parsed = json.loads(last)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and "questions" in parsed:
            request.update({key: parsed[key] for key in ("state", "questions", "media_kwargs") if key in parsed})
    if "questions" not in request:
        request["questions"] = body.get("questions")
    if "state" not in request:
        request["state"] = body["state"] if "state" in body else "\n\n".join(texts)
    if not isinstance(request["questions"], dict) or not request["questions"]:
        raise ValueError("clef-flash needs `questions` (top-level or in a JSON user message)")
    images = message_images(messages)
    if images:
        request["images"] = images
    return request


def completion(model: str, answer: dict[str, Any]) -> dict[str, Any]:
    usage = answer.get("usage", {})
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps(answer["answers"], ensure_ascii=False)},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": 0,
            "total_tokens": usage.get("input_tokens", 0),
        },
        "systemone": answer,
    }


def sse(completion_body: dict[str, Any]):
    base = {key: completion_body[key] for key in ("id", "created", "model")}
    base["object"] = "chat.completion.chunk"
    message = completion_body["choices"][0]["message"]
    yield "data: " + json.dumps({**base, "choices": [{"index": 0, "delta": message, "finish_reason": None}]}) + "\n\n"
    yield "data: " + json.dumps({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}) + "\n\n"
    yield "data: [DONE]\n\n"


DOWN_STATUS = (502, 503, 504)


def parse_upstream(spec: str) -> tuple[str, float | None]:
    """"http://host:port@90" -> ("http://host:port", 90.0); no numeric @suffix -> (spec, None)."""
    url, sep, tail = spec.rpartition("@")
    if not sep or "/" in tail:
        return spec, None
    try:
        weight = float(tail)
    except ValueError:
        return spec, None
    if weight < 0:
        raise ValueError(f"negative weight in {spec!r}")
    return url, weight


class Upstream:
    def __init__(self, url: str, weight: float | None = None) -> None:
        self.url = url.rstrip("/")
        self.weight = weight
        self.outstanding = 0
        self.down_until = 0.0


class Upstreams:
    """Choice over several servers of the same model, with a cooldown for failed ones.

    Least outstanding requests by default; a random split by weight once any URL carries @<weight>.
    """

    def __init__(
        self,
        urls: list[str],
        cooldown_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.items = [Upstream(*parse_upstream(url)) for url in urls]
        self.weighted = any(item.weight is not None for item in self.items)
        self.cooldown_s = cooldown_s
        self.clock = clock
        self.rng = rng or random.Random()

    def weight(self, item: Upstream) -> float:
        return 1.0 if item.weight is None else item.weight

    def acquire(self, exclude: tuple[Upstream, ...] = ()) -> Upstream | None:
        now = self.clock()
        pool = [item for item in self.items if item not in exclude]
        # all cooling: probe anyway instead of refusing for the whole cooldown
        usable = [item for item in pool if item.down_until <= now] or pool
        if not usable:
            return None
        if self.weighted:
            # weight 0 is a fallback only: used when no upstream with traffic is left
            live = [item for item in usable if self.weight(item) > 0]
            chosen = self.rng.choices(live, weights=[self.weight(i) for i in live])[0] if live else min(usable, key=lambda item: item.outstanding)
        else:
            chosen = min(usable, key=lambda item: item.outstanding)
        chosen.outstanding += 1
        return chosen

    def release(self, item: Upstream) -> None:
        item.outstanding -= 1

    def mark_down(self, item: Upstream) -> None:
        item.down_until = self.clock() + self.cooldown_s


def build_app(
    clef_urls: list[str] | str,
    gemma_urls: list[str] | str,
    api_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
    cooldown_s: float = 30.0,
    clock: Callable[[], float] = time.monotonic,
    rng: random.Random | None = None,
) -> FastAPI:
    app = FastAPI(title="model-gateway")
    client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0), transport=transport, limits=httpx.Limits(max_connections=None, max_keepalive_connections=64))
    upstreams = Upstreams([gemma_urls] if isinstance(gemma_urls, str) else list(gemma_urls), cooldown_s, clock, rng)
    clefs = Upstreams([clef_urls] if isinstance(clef_urls, str) else list(clef_urls), cooldown_s, clock, rng)

    def authorize(request: Request) -> None:
        if api_key and request.headers.get("authorization") != f"Bearer {api_key}":
            raise HTTPException(status_code=401, detail="invalid api key")

    async def chat(request: Request, forced: str | None):
        authorize(request)
        body = await request.json()
        model = forced or body.get("model")
        if model not in (CLEF, GEMMA):
            raise HTTPException(status_code=404, detail=f"unknown model {model!r}; use {CLEF} or {GEMMA}")
        if model == CLEF:
            try:
                request_body = systemone_request(body)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            tried_clef: list[Upstream] = []
            while True:
                chosen = clefs.acquire(tuple(tried_clef))
                if chosen is None:
                    raise HTTPException(status_code=502, detail="no clef upstream available")
                tried_clef.append(chosen)
                try:
                    upstream = await client.post(f"{chosen.url}/v1/systemone", json=request_body)
                except httpx.TransportError:
                    clefs.mark_down(chosen)
                    continue
                finally:
                    clefs.release(chosen)
                if upstream.status_code in DOWN_STATUS:
                    clefs.mark_down(chosen)
                    continue
                break
            if upstream.status_code != 200:
                return JSONResponse(upstream.json(), status_code=upstream.status_code)
            result = completion(CLEF, upstream.json())
            if body.get("stream"):
                return StreamingResponse(sse(result), media_type="text/event-stream")
            return JSONResponse(result)
        tried: list[Upstream] = []
        while True:
            chosen = upstreams.acquire(tuple(tried))
            if chosen is None:
                raise HTTPException(status_code=502, detail="no gemma upstream available")
            tried.append(chosen)
            body["model"] = GEMMA
            try:
                upstream = await client.send(client.build_request("POST", f"{chosen.url}/v1/chat/completions", json=body), stream=True)
            except httpx.TransportError:
                upstreams.release(chosen)
                upstreams.mark_down(chosen)
                continue
            if upstream.status_code in DOWN_STATUS:
                await upstream.aclose()
                upstreams.release(chosen)
                upstreams.mark_down(chosen)
                continue
            break
        headers = {"content-type": upstream.headers.get("content-type", "application/json")}

        async def relay():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()
                upstreams.release(chosen)

        return StreamingResponse(relay(), status_code=upstream.status_code, headers=headers)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models(request: Request) -> dict[str, Any]:
        authorize(request)
        return {"object": "list", "data": [{"id": name, "object": "model", "owned_by": "local"} for name in (CLEF, GEMMA)]}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        return await chat(request, None)

    @app.post("/v1/{name}/chat/completions")
    async def named_chat_completions(name: str, request: Request):
        return await chat(request, name)

    @app.post("/v1/{name}")
    async def named(name: str, request: Request):
        return await chat(request, name)

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=30000)
    parser.add_argument("--clef-url", action="append", help="repeat for several clef_server.py replicas (default http://127.0.0.1:30001); URL@weight splits by weight")
    parser.add_argument("--gemma-url", action="append", help="repeat for several upstreams (default http://127.0.0.1:30002, llama.cpp); URL@weight splits by weight")
    parser.add_argument("--cooldown", type=float, default=30.0, help="seconds a failed upstream is skipped")
    args = parser.parse_args()
    app = build_app(
        args.clef_url or ["http://127.0.0.1:30001"], args.gemma_url or ["http://127.0.0.1:30002"], os.environ.get("MODEL_GATEWAY_API_KEY", ""), cooldown_s=args.cooldown
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
