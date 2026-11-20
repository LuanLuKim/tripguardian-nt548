import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from analytics.auth import MAX_FAILURES, SESSION_SECONDS, WINDOW_SECONDS, AdminAuth
from analytics.server import handler


def test_login_matches_email_and_password_only():
    auth = AdminAuth("Admin@X.vn", "secret")
    assert auth.login("admin@x.vn", "wrong") is None
    assert auth.login("other@x.vn", "secret") is None
    assert auth.login(None, 5) is None
    token = auth.login(" ADMIN@x.vn ", "secret")
    assert token and auth.valid(token)
    auth.logout(token)
    assert not auth.valid(token)


def test_lockout_is_per_client():
    auth = AdminAuth("a@x.vn", "pw")
    for _ in range(MAX_FAILURES):
        auth.login("a@x.vn", "bad", "1.1.1.1")
    with pytest.raises(PermissionError):
        auth.login("a@x.vn", "pw", "1.1.1.1")
    assert auth.login("a@x.vn", "pw", "2.2.2.2")


def test_unconfigured_account_fails_closed():
    auth = AdminAuth("", "")
    assert not auth.configured and not auth.valid("anything")
    with pytest.raises(RuntimeError):
        auth.login("a", "b")


def test_session_expires_and_failures_lock_then_age_out():
    now = [0.0]
    auth = AdminAuth("a@x.vn", "pw", clock=lambda: now[0])
    token = auth.login("a@x.vn", "pw")
    now[0] = SESSION_SECONDS + 1
    assert not auth.valid(token)
    for _ in range(MAX_FAILURES):
        assert auth.login("a@x.vn", "bad") is None
    with pytest.raises(PermissionError):
        auth.login("a@x.vn", "pw")
    now[0] += WINDOW_SECONDS + 1
    assert auth.login("a@x.vn", "pw")


def test_server_gates_routes_behind_the_cookie():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler(None, AdminAuth("a@x.vn", "pw")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api/analytics"

    def post(path, body, cookie=None):
        headers = {"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})}
        return urlopen(Request(f"{base}/{path}", json.dumps(body).encode(), headers))

    try:
        with pytest.raises(HTTPError) as e:
            urlopen(f"{base}/me")
        assert e.value.code == 401
        with pytest.raises(HTTPError) as e:
            urlopen(f"{base}/funnel")
        assert e.value.code == 401
        with pytest.raises(HTTPError) as e:
            post("login", {"email": "a@x.vn", "password": "nope"})
        assert e.value.code == 401
        with post("login", {"email": "a@x.vn", "password": "pw"}) as r:
            set_cookie = r.headers["Set-Cookie"]
            cookie = set_cookie.split(";")[0]
        assert "HttpOnly" in set_cookie and "SameSite=Strict" in set_cookie
        with urlopen(Request(f"{base}/me", headers={"Cookie": cookie})) as r:
            assert json.load(r) == {"email": "a@x.vn"}
        post("logout", {}, cookie).close()
        with pytest.raises(HTTPError) as e:
            urlopen(Request(f"{base}/me", headers={"Cookie": cookie}))
        assert e.value.code == 401
    finally:
        srv.shutdown()
