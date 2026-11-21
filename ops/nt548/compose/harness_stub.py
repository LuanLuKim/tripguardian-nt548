"""Stand-in for `python -m harness serve` until the sample data (T5, R1) lets the real harness start.

Listens where web/server.mjs proxies (127.0.0.1:HARNESS_PORT, default 8769) and answers the routes the web calls:
/api/harness/me and /api/auth/* -> 401 (signed out, as the real harness says it), any other /api/harness/* -> 200 JSON.
Every answer carries X-Color and X-Image-Tag, and GET /api/harness/nt548-version returns them, so blue/green and
canary checks can tell which color served a request. Stdlib only.

usage: python ops/nt548/compose/harness_stub.py [--host 127.0.0.1] [--port 8769]
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
        if path == "/api/harness/nt548-version":
            self._send(200, {"color": os.environ.get("COLOR", "unknown"), "image_tag": os.environ.get("IMAGE_TAG", "unknown"), "stub": True})
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
