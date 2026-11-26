"""ops/nt548/lb_check.py against a fake load balancer that picks a color from the tg_session cookie."""

import hashlib
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("lb_check", Path(__file__).resolve().parents[2] / "ops/nt548/lb_check.py")
lb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lb)


class FakeLB(BaseHTTPRequestHandler):
    green_pct = 10
    fail_path = None

    def _answer(self):
        cookie = (self.headers.get("Cookie") or "").removeprefix("tg_session=")
        bucket = int(hashlib.md5(cookie.encode()).hexdigest(), 16) % 100
        color = "green" if bucket < FakeLB.green_pct else "blue"
        if self.headers.get("Content-Length"):
            self.rfile.read(int(self.headers["Content-Length"]))
        status = 500 if self.path == FakeLB.fail_path else 200
        self.send_response(status)
        self.send_header("X-LB-Color", color)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    do_GET = do_POST = _answer

    def log_message(self, *args):
        pass


@pytest.fixture
def url():
    FakeLB.green_pct, FakeLB.fail_path = 10, None
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeLB)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_split_within_tolerance(url):
    assert lb.main(["--url", url, "split", "--color", "green", "--expect", "10", "--tol", "4", "--n", "500"]) == 0
    assert lb.main(["--url", url, "split", "--color", "green", "--expect", "50", "--tol", "4", "--n", "300"]) == 1


def test_sticky_by_cookie(url):
    assert lb.main(["--url", url, "sticky", "--users", "5", "--n", "10"]) == 0


def test_load_then_verify(url, tmp_path):
    out = tmp_path / "load.json"
    assert lb.main(["--url", url, "load", "--seconds", "1", "--workers", "2", "--out", str(out)]) == 0
    s = json.loads(out.read_text())
    assert s["requests"] > 10 and s["conn_errors"] == 0 and set(s["colors"]) <= {"blue", "green"}
    assert lb.main(["verify", str(out)]) == 0
    FakeLB.fail_path = "/api/harness/me"
    assert lb.main(["--url", url, "load", "--seconds", "1", "--workers", "2", "--out", str(out)]) == 0
    assert lb.main(["verify", str(out), "--max-5xx", "0"]) == 1


def test_no_answer_is_a_connection_error():
    status, color = lb.request("http://127.0.0.1:9", "/", "x", timeout=1)
    assert (status, color) == (0, "")


def test_wait_color(url):
    FakeLB.green_pct = 0
    assert lb.main(["--url", url, "wait-color", "--color", "blue", "--timeout", "5", "--n", "20"]) == 0
    FakeLB.green_pct = 50
    assert lb.main(["--url", url, "wait-color", "--color", "blue", "--timeout", "1", "--n", "20"]) == 1
