"""Stand-in for `python -m harness serve` until the sample data (T5, R1) lets the real harness start.

Listens where web/server.mjs proxies (127.0.0.1:HARNESS_PORT, default 8769) and answers the routes the web calls:
/api/harness/me and /api/auth/* -> 401 (signed out, as the real harness says it), any other /api/harness/* -> 200 JSON.
Every answer carries X-Color and X-Image-Tag, and GET /api/harness/nt548-version returns them, so blue/green and
canary checks can tell which color served a request. Stdlib only.

NT548 test hooks (never in the product code):
- NT548_FAULT: a fault on every /api/harness/* route but nt548-version, for canary and fault-injection runs (#3, #39).
  `500` (or any 5xx) answers that status; `503@0.3` does it for 30 % of requests; `delay:800` waits 800 ms first.
- POST /api/harness/nt548-chat sends one chat completion through AGENT_BASE_URL (the model gateway), so a fault of the
  fake LLM shows at the load balancer: upstream error -> 502, upstream timeout -> 504.

usage: python ops/nt548/compose/harness_stub.py [--host 127.0.0.1] [--port 8769]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def fault(spec: str | None) -> tuple[int | None, float, float]:
    """NT548_FAULT -> (status or None, share of requests, delay in s). Unknown text is no fault."""
    spec = (spec or "").strip()
    if not spec:
        return None, 0.0, 0.0
    head, _, rate = spec.partition("@")
    share = float(rate) if rate else 1.0
    if head.startswith("delay:"):
        return None, share, float(head.split(":", 1)[1]) / 1000
    if head.isdigit() and 500 <= int(head) <= 599:
        return int(head), share, 0.0
    return None, 0.0, 0.0


def chat(timeout: float = 10.0) -> tuple[int, dict]:
    base = os.environ.get("AGENT_BASE_URL", "").rstrip("/")
    if not base:
        return 503, {"error": "AGENT_BASE_URL not set", "stub": True}
    body = json.dumps({"model": os.environ.get("AGENT_MODEL", "fake"),
                       "messages": [{"role": "user", "content": "nt548 probe"}]}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {os.environ.get('AGENT_API_KEY', 'fake')}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            reply = json.loads(r.read())
        return 200, {"ok": True, "stub": True, "model": reply.get("system_fingerprint", "")}
    except urllib.error.HTTPError as e:
        return 502, {"error": f"model upstream {e.code}", "stub": True}
    except (TimeoutError, OSError) as e:
        timed_out = isinstance(e, TimeoutError) or "timed out" in str(e)
        return (504 if timed_out else 502), {"error": f"model upstream {type(e).__name__}", "stub": True}


class Handler(BaseHTTPRequestHandler):
    server_version = "harness-stub"

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Color", os.environ.get("COLOR", "unknown"))
        self.send_header("X-Image-Tag", os.environ.get("IMAGE_TAG", "unknown"))
        self.end_headers()
        self.wfile.write(data)

    def _route(self) -> None:
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/harness/") and path != "/api/harness/nt548-version":
            status, share, delay = fault(os.environ.get("NT548_FAULT"))
            if share and random.random() < share:
                if delay:
                    time.sleep(delay)
                if status:
                    self._send(status, {"error": "injected fault (NT548_FAULT)", "stub": True})
                    return
        if path == "/api/harness/nt548-version":
            self._send(200, {"color": os.environ.get("COLOR", "unknown"), "image_tag": os.environ.get("IMAGE_TAG", "unknown"), "stub": True})
        elif path == "/api/harness/nt548-chat":
            self._send(*chat())
        elif path == "/api/harness/me" or path.startswith("/api/auth/"):
            self._send(401, {"error": "not signed in", "stub": True})
        elif path.startswith("/api/harness/"):
            self._send(200, {"ok": True, "stub": True})
        else:
            self._send(404, {"error": "not found", "stub": True})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _route

    def log_message(self, fmt: str, *args) -> None:  # one line per request on stdout, for the log pipeline (#37)
        print(f"harness-stub {self.command} {self.path.split('?', 1)[0]} {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("HARNESS_PORT", "8769")))
    args = parser.parse_args()
    print(f"harness-stub color={os.environ.get('COLOR', 'unknown')} tag={os.environ.get('IMAGE_TAG', 'unknown')} on {args.host}:{args.port}", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
