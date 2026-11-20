"""Private analytics HTTP server: 127.0.0.1 only, read-only database role, admin sign-in required (auth.py).
Never proxied by web/server.mjs.

POST /api/analytics/login   {email, password} -> {email} and a `tg_admin` HttpOnly cookie
POST /api/analytics/logout  -> {}
GET  /api/analytics/me      -> {email}; every other GET needs the cookie (401 without it)

Public admin (web/server.mjs, docs/OPERATIONS.md): the tunnel server proxies these routes and asks /me before it lets
the review API or the admin snapshot through. It passes `x-tg-client-ip` (lockout is per address) and `x-tg-secure`
(the request came over https: the cookie gets Secure)."""

import json
import re
import sys
import threading
import traceback
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from uuid import UUID

from . import queries, tabs, users
from .auth import COOKIE, SESSION_SECONDS, AdminAuth
from .trends import trends  # the package re-exports this name, which hides the submodule

SESSION = re.compile(r"/api/analytics/sessions/([0-9a-f]{12})")
PLACE = re.compile(r"/api/analytics/places/([^/]{1,120})")
PERSON = re.compile(r"/api/analytics/users/([0-9a-f]{32})")


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return value.hex
    raise TypeError(type(value).__name__)


def handler(pool, auth: AdminAuth):
    class Handler(BaseHTTPRequestHandler):
        def _token(self):
            for part in self.headers.get("Cookie", "").split(";"):
                name, _, value = part.strip().partition("=")
                if name == COOKIE:
                    return value
            return None

        def _json(self, code, value, cookie=None):
            body = json.dumps(value, ensure_ascii=False, default=_plain).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if cookie is not None:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if not auth.valid(self._token()):
                return self._json(401, {"error": "unauthorized"})
            params = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/api/analytics/me":
                return self._json(200, {"email": auth.email})
            routes = {"/api/analytics/funnel": lambda: queries.funnel(pool, params),
                      "/api/analytics/decision": lambda: queries.decision(pool, params),
                      "/api/analytics/sessions": lambda: queries.sessions(pool, params),
                      "/api/analytics/today": lambda: queries.today(pool),
                      "/api/analytics/versions": lambda: queries.versions(pool),
                      "/api/analytics/trip": lambda: tabs.trip(pool, params),
                      "/api/analytics/planning": lambda: tabs.planning(pool, params),
                      "/api/analytics/reality": lambda: tabs.reality(pool, params),
                      "/api/analytics/notifications": lambda: tabs.notifications(pool, params),
                      "/api/analytics/agent": lambda: tabs.agent(pool, params),
                      "/api/analytics/quality": lambda: tabs.quality(pool, params),
                      "/api/analytics/insights": lambda: tabs.insights(pool, params),
                      "/api/analytics/clusters": lambda: tabs.clusters(pool),
                      "/api/analytics/users": lambda: users.overview(pool, params),
                      "/api/analytics/users/list": lambda: users.people(pool, params),
                      "/api/analytics/trends": lambda: trends(pool, params)}
            fn = routes.get(url.path)
            if fn is None and (m := SESSION.fullmatch(url.path)):
                fn = lambda: queries.session(pool, m[1])  # noqa: E731
            elif fn is None and (m := PLACE.fullmatch(url.path)):
                fn = lambda: tabs.place(pool, unquote(m[1]), params)  # noqa: E731
            elif fn is None and (m := PERSON.fullmatch(url.path)):
                fn = lambda: users.person(pool, m[1])  # noqa: E731
            if fn is None:
                return self._json(404, {"error": "not found"})
            try:
                return self._json(200, fn())
            except KeyError:
                return self._json(404, {"error": "not found"})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            except Exception:
                traceback.print_exc(file=sys.stderr)
                return self._json(500, {"error": "server error"})

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/api/analytics/logout":
                auth.logout(self._token())
                return self._json(200, {}, f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")
            if path != "/api/analytics/login":
                return self._json(404, {"error": "not found"})
            if not auth.configured:
                return self._json(503, {"error": "Chưa đặt ADMIN_EMAIL / ADMIN_PASSWORD trong .env"})
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 4096)) or b"{}")
                body = body if isinstance(body, dict) else {}
                token = auth.login(body.get("email"), body.get("password"), self.headers.get("x-tg-client-ip", ""))
            except (ValueError, TypeError):
                return self._json(400, {"error": "bad request"})
            except PermissionError:
                return self._json(429, {"error": "Sai quá nhiều lần, thử lại sau 15 phút"})
            if token is None:
                return self._json(401, {"error": "Sai email hoặc mật khẩu"})
            secure = "; Secure" if self.headers.get("x-tg-secure") == "1" else ""
            return self._json(200, {"email": auth.email},
                              f"{COOKIE}={token}; Path=/; Max-Age={SESSION_SECONDS}; HttpOnly; SameSite=Strict{secure}")

        def log_message(self, *args):
            pass
    return Handler


def run(pool, port=8770):
    # Read every journey's Trip request once in the background so the first Xu hướng page is not the slow one.
    threading.Thread(target=lambda: trends(pool, {"from": "2026-01-01"}), daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", port), handler(pool, AdminAuth())).serve_forever()
