"""ops/nt548/compose/harness_stub.py answers the routes web/server.mjs proxies, and names its color."""

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("harness_stub", Path(__file__).resolve().parents[2] / "ops/nt548/compose/harness_stub.py")
stub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stub)


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("COLOR", "green")
    monkeypatch.setenv("IMAGE_TAG", "abc123")
    server = ThreadingHTTPServer(("127.0.0.1", 0), stub.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def call(url, method="GET"):
    req = urllib.request.Request(url, method=method, data=b"{}" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read())


def test_signed_out_routes_are_401_like_the_real_harness(base):
    assert call(base + "/api/harness/me")[0] == 401
    assert call(base + "/api/auth/google/start?next=/app")[0] == 401


def test_other_harness_routes_are_200_and_carry_the_color(base):
    status, headers, body = call(base + "/api/harness/journeys", "POST")
    assert status == 200 and body["stub"] is True
    assert headers["X-Color"] == "green" and headers["X-Image-Tag"] == "abc123"


def test_version_route_names_color_and_tag(base):
    status, _, body = call(base + "/api/harness/nt548-version")
    assert status == 200 and body == {"color": "green", "image_tag": "abc123", "stub": True}


def test_unknown_path_is_404(base):
    assert call(base + "/elsewhere")[0] == 404
