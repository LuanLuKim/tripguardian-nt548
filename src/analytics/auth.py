"""Admin sign-in for the private analytics server: one account from the environment (ADMIN_EMAIL, ADMIN_PASSWORD).

No users row and no Postgres write: the account lives in `.env`, a session is a random token held in memory (a restart
signs everyone out). Without ADMIN_PASSWORD nobody can sign in and every data route answers 401 (fail closed)."""

import hmac
import os
import secrets
import threading
import time

SESSION_SECONDS = 12 * 3600
MAX_FAILURES = 5  # wrong passwords from one client inside WINDOW_SECONDS lock that client until the oldest one ages out
WINDOW_SECONDS = 15 * 60
COOKIE = "tg_admin"


class AdminAuth:
    def __init__(self, email: str | None = None, password: str | None = None, clock=time.monotonic):
        self._email = (os.environ.get("ADMIN_EMAIL", "") if email is None else email).strip().lower()
        self._password = os.environ.get("ADMIN_PASSWORD", "") if password is None else password
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, float] = {}  # token -> expiry
        self._failures: dict[str, list[float]] = {}  # client address -> times of its wrong passwords

    @property
    def configured(self) -> bool:
        return bool(self._email and self._password)

    @property
    def email(self) -> str:
        return self._email

    def login(self, email: object, password: object, client: str = "") -> str | None:
        """A session token when the credentials match; None otherwise. Raises PermissionError while `client` (the
        caller's address) is locked out; one client's failures never lock another out."""
        if not self.configured:
            raise RuntimeError("ADMIN_EMAIL / ADMIN_PASSWORD are not set")
        now = self._clock()
        with self._lock:
            self._failures = {c: kept for c, ts in self._failures.items() if (kept := [t for t in ts if now - t < WINDOW_SECONDS])}
            if len(self._failures.get(client, [])) >= MAX_FAILURES:
                raise PermissionError("too many attempts")
            ok = isinstance(email, str) and isinstance(password, str)
            # Compare both fields every time so the answer does not leak which one was wrong.
            mail_ok = ok and hmac.compare_digest(email.strip().lower().encode(), self._email.encode())
            pass_ok = ok and hmac.compare_digest(password.encode(), self._password.encode())
            if not (mail_ok and pass_ok):
                self._failures.setdefault(client, []).append(now)
                return None
            self._failures.pop(client, None)
            self._sessions = {t: exp for t, exp in self._sessions.items() if exp > now}
            token = secrets.token_urlsafe(32)
            self._sessions[token] = now + SESSION_SECONDS
            return token

    def valid(self, token: str | None) -> bool:
        if not token or not self.configured:
            return False
        with self._lock:
            exp = self._sessions.get(token)
            if exp is None:
                return False
            if exp <= self._clock():
                del self._sessions[token]
                return False
            return True

    def logout(self, token: str | None) -> None:
        with self._lock:
            self._sessions.pop(token or "", None)
