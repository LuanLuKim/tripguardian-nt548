"""Forgotten password with a one-time code (docs/ACCOUNTS.md §2c): the Accounts rules on Postgres, then the HTTP routes."""

import http.client
import json
import re
import threading
from http.server import ThreadingHTTPServer

import pytest
from cryptography.fernet import Fernet

from accounts import Accounts, AuthError, ResetError

ORIGIN = "http://app.test"
NEW = "mat-khau-moi-1"


class Outbox:
    """Mailer stand-in: keeps what would have been sent."""
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)

    def code(self, n=-1):
        return re.search(r"(\d{3}) (\d{3})", self.sent[n].text).expand(r"\1\2")


@pytest.fixture
def pool(pg_url):
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    p = ConnectionPool(pg_url, min_size=1, max_size=4, kwargs={"row_factory": dict_row}, open=True)
    yield p
    p.close()


@pytest.fixture
def accounts(pool, tmp_path):
    return Accounts(pool, None, tmp_path / "avatars", Fernet.generate_key().decode())


def sql(accounts, query, *args):
    with accounts.pool.connection() as conn:
        cur = conn.execute(query, args)
        return cur.fetchall() if cur.description else []


def age(accounts, seconds, email="lan@example.com"):
    """Pretend the last request was `seconds` ago (the window moves with it)."""
    sql(accounts, "UPDATE password_resets SET sent_at = now() - make_interval(secs => %s), "
        "window_start = LEAST(window_start, now() - make_interval(secs => %s)) WHERE email = %s", seconds, seconds, email)


@pytest.mark.pg
def test_forgot_mails_a_code_only_for_a_real_account_and_stores_only_a_hash(accounts):
    accounts.register("Lan@Example.com", "mat-khau-dai")
    assert accounts.forgot("nobody@example.com") is None
    email, code = accounts.forgot(" LAN@example.com ")
    assert email == "lan@example.com" and re.fullmatch(r"\d{6}", code)
    rows = sql(accounts, "SELECT * FROM password_resets ORDER BY email")
    assert [r["email"] for r in rows] == ["lan@example.com", "nobody@example.com"]  # the unknown email looks the same
    assert rows[1]["user_id"] is None and rows[0]["user_id"] is not None
    assert code not in json.dumps({k: str(v) for k, v in rows[0].items()}) and len(bytes(rows[0]["code_hash"])) == 32
    with pytest.raises(ValueError):
        accounts.forgot("not-an-email")


@pytest.mark.pg
def test_deleted_and_guest_accounts_get_nothing(accounts):
    token = accounts.register("lan@example.com", "mat-khau-dai")
    accounts.delete(accounts.user_for(token)[0]["id"])
    assert accounts.forgot("lan@example.com") is None


@pytest.mark.pg
def test_right_code_sets_the_password_ends_every_session_and_signs_in(accounts):
    old = accounts.register("lan@example.com", "mat-khau-dai")
    other = accounts.login_password("lan@example.com", "mat-khau-dai")
    uid = accounts.user_for(old)[0]["id"]
    _, code = accounts.forgot("lan@example.com")
    token = accounts.reset_password("Lan@example.com", code, NEW)
    assert accounts.user_for(old)[0] is None and accounts.user_for(other)[0] is None  # sessions elsewhere are gone
    assert accounts.user_for(token)[0]["id"] == uid
    assert accounts.user_for(accounts.login_password("lan@example.com", NEW))[0]["id"] == uid
    with pytest.raises(AuthError):
        accounts.login_password("lan@example.com", "mat-khau-dai")
    stored = sql(accounts, "SELECT password_hash FROM users")[0]["password_hash"]
    assert stored.startswith("scrypt$") and NEW not in stored
    with pytest.raises(ResetError) as used:  # a code works once
        accounts.reset_password("lan@example.com", code, "mat-khau-khac-2")
    assert used.value.kind == "expired"


@pytest.mark.pg
def test_a_google_only_account_gets_a_password_too(accounts):
    sql(accounts, "INSERT INTO users (google_sub, email) VALUES ('g-1', 'g1@example.com')")
    _, code = accounts.forgot("g1@example.com")
    assert accounts.user_for(accounts.reset_password("g1@example.com", code, NEW))[0] is not None
    assert accounts.login_password("g1@example.com", NEW)
    assert sql(accounts, "SELECT google_sub FROM users")[0]["google_sub"] == "g-1"


@pytest.mark.pg
def test_five_wrong_codes_kill_the_code_even_the_right_one(accounts):
    accounts.register("lan@example.com", "mat-khau-dai")
    _, code = accounts.forgot("lan@example.com")
    wrong = "000000" if code != "000000" else "111111"
    left = []
    for _ in range(4):
        with pytest.raises(ResetError) as err:
            accounts.reset_password("lan@example.com", wrong, NEW)
        assert err.value.kind == "wrong"
        left.append(err.value.tries_left)
    assert left == [4, 3, 2, 1]
    with pytest.raises(ResetError) as err:
        accounts.reset_password("lan@example.com", wrong, NEW)
    assert err.value.kind == "locked"
    with pytest.raises(ResetError) as err:
        accounts.reset_password("lan@example.com", code, NEW)
    assert err.value.kind == "locked"
    with pytest.raises(AuthError):
        accounts.login_password("lan@example.com", NEW)
    age(accounts, 61)  # a new request after the cooldown starts again with all five tries
    _, fresh = accounts.forgot("lan@example.com")
    assert accounts.user_for(accounts.reset_password("lan@example.com", fresh, NEW))[0] is not None


@pytest.mark.pg
def test_an_unknown_email_answers_every_step_like_a_real_one(accounts):
    accounts.register("lan@example.com", "mat-khau-dai")
    accounts.forgot("lan@example.com")
    accounts.forgot("ghost@example.com")
    for email in ("lan@example.com", "ghost@example.com"):
        kinds = []
        for _ in range(5):
            with pytest.raises(ResetError) as err:
                accounts.reset_password(email, "123456" if email.startswith("ghost") else "000000", NEW)
            kinds.append((err.value.kind, err.value.tries_left))
        assert kinds[0] == ("wrong", 4) and kinds[-1] == ("locked", 0)
    with pytest.raises(ResetError) as err:  # never asked at all
        accounts.reset_password("never@example.com", "123456", NEW)
    assert err.value.kind == "expired"


@pytest.mark.pg
def test_a_code_expires_after_ten_minutes(accounts):
    accounts.register("lan@example.com", "mat-khau-dai")
    _, code = accounts.forgot("lan@example.com")
    sql(accounts, "UPDATE password_resets SET expires_at = now() - interval '1 second'")
    with pytest.raises(ResetError) as err:
        accounts.reset_password("lan@example.com", code, NEW)
    assert err.value.kind == "expired"
    assert sql(accounts, "SELECT count(*) AS n FROM password_resets")[0]["n"] == 1  # the row stays for the hourly count
    age(accounts, 61)
    accounts.forgot("lan@example.com")
    assert 595 <= sql(accounts, "SELECT extract(epoch FROM expires_at - now()) AS s FROM password_resets")[0]["s"] <= 600


@pytest.mark.pg
def test_a_new_request_replaces_the_old_code_after_the_cooldown(accounts):
    accounts.register("lan@example.com", "mat-khau-dai")
    _, first = accounts.forgot("lan@example.com")
    with pytest.raises(ResetError) as err:
        accounts.forgot("lan@example.com")
    assert err.value.kind == "wait" and 1 <= err.value.retry_after <= 60
    age(accounts, 61)
    _, second = accounts.forgot("lan@example.com")
    assert sql(accounts, "SELECT count(*) AS n FROM password_resets")[0]["n"] == 1  # one active code per account
    if first != second:
        with pytest.raises(ResetError):
            accounts.reset_password("lan@example.com", first, NEW)
    assert accounts.reset_password("lan@example.com", second, NEW)


@pytest.mark.pg
def test_five_requests_an_hour_per_email_then_wait(accounts):
    accounts.register("lan@example.com", "mat-khau-dai")
    for _ in range(5):
        accounts.forgot("lan@example.com")
        age(accounts, 61)
    with pytest.raises(ResetError) as err:
        accounts.forgot("lan@example.com")
    assert err.value.kind == "wait" and 61 < err.value.retry_after <= 3600
    age(accounts, 3601)  # an hour later the window is new
    assert accounts.forgot("lan@example.com")


@pytest.mark.pg
def test_bad_input_costs_no_try_and_changes_nothing(accounts):
    accounts.register("lan@example.com", "mat-khau-dai")
    _, code = accounts.forgot("lan@example.com")
    for args in (("lan@example.com", code, "short"), ("lan@example.com", code, "x" * 129), ("lan@example.com", "12345", NEW),
                 ("lan@example.com", "abcdef", NEW), ("bad", code, NEW)):
        with pytest.raises(ValueError):
            accounts.reset_password(*args)
    assert sql(accounts, "SELECT tries FROM password_resets")[0]["tries"] == 0
    assert accounts.login_password("lan@example.com", "mat-khau-dai")


def test_reset_is_off_without_the_server_key(tmp_path):
    off = Accounts(None, None, tmp_path)
    assert not off.reset_ready
    with pytest.raises(RuntimeError):
        off.forgot("lan@example.com")
    with pytest.raises(RuntimeError):
        off.reset_password("lan@example.com", "123456", NEW)


# --- HTTP ---------------------------------------------------------------------------------------------------

class StubHarness:
    events = []

    def _event(self, name, user, journey, **kw):
        self.events.append(name)

    def adopt(self, *a):
        return 0


def serve(accounts, mailer, monkeypatch):
    from harness import server
    monkeypatch.setattr(server, "_spawn", lambda job: job())  # send inline so the test can read the outbox
    http_server = ThreadingHTTPServer(("127.0.0.1", 0), server.handler(StubHarness(), accounts, ORIGIN, mailer=mailer))
    threading.Thread(target=http_server.serve_forever, daemon=True).start()
    return http_server


def post(port, path, data, origin=ORIGIN, ip=None, cookie=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    if ip:
        headers["X-Tg-Client-Ip"] = ip
    if cookie:
        headers["Cookie"] = f"tg_session={cookie}"
    conn.request("POST", path, json.dumps(data), headers)
    res = conn.getresponse()
    out = json.loads(res.read())
    conn.close()
    return res.status, out, res.getheader("Set-Cookie")


def get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path)
    res = conn.getresponse()
    out = json.loads(res.read())
    conn.close()
    return res.status, out


@pytest.fixture
def web(accounts, monkeypatch):
    box = Outbox()
    srv = serve(accounts, box, monkeypatch)
    yield srv.server_address[1], box, accounts
    srv.shutdown()
    srv.server_close()


FORGOT, RESET = "/api/auth/password/forgot", "/api/auth/password/reset"


@pytest.mark.pg
def test_forgot_answers_the_same_for_every_email_and_mails_only_real_accounts(web):
    port, box, accounts = web
    accounts.register("lan@example.com", "mat-khau-dai")
    a = post(port, FORGOT, {"email": "lan@example.com"}, ip="10.0.0.1")
    b = post(port, FORGOT, {"email": "ghost@example.com"}, ip="10.0.0.1")
    assert a[:2] == b[:2] == (200, {"sent": True, "resend_after": 60, "expires_in": 600}) and a[2] is None
    assert [m.to for m in box.sent] == ["lan@example.com"]
    assert "bỏ qua email này" in box.sent[0].text and "10 phút" in box.sent[0].html
    assert get(port, "/api/auth/options") == (200, {"password_reset": True})


@pytest.mark.pg
def test_forgot_refuses_other_origins_bad_input_and_the_cooldown(web):
    port, box, accounts = web
    accounts.register("lan@example.com", "mat-khau-dai")
    assert post(port, FORGOT, {"email": "lan@example.com"}, origin=None)[0] == 403
    assert post(port, FORGOT, {"email": "lan@example.com"}, origin="http://evil.test")[0] == 403
    assert post(port, FORGOT, {"email": 5})[0] == 400 and post(port, FORGOT, {"email": "nope"})[0] == 400
    assert not box.sent
    assert post(port, FORGOT, {"email": "lan@example.com"}, ip="10.0.0.2")[0] == 200
    again = post(port, FORGOT, {"email": "lan@example.com"}, ip="10.0.0.3")
    ghost = [post(port, FORGOT, {"email": "ghost@example.com"}, ip=f"10.0.1.{i}")[0] for i in (1, 2)]
    assert again[0] == 429 and 1 <= again[1]["retry_after"] <= 60 and ghost == [200, 429]  # same for unknown emails
    assert len(box.sent) == 1


@pytest.mark.pg
def test_one_address_may_ask_only_so_often(web, monkeypatch):
    from harness import server
    monkeypatch.setattr(server, "RESET_ASKS_PER_IP_HOUR", 3)
    port, box, _ = web
    codes = [post(port, FORGOT, {"email": f"u{i}@example.com"}, ip="10.9.9.9")[0] for i in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert post(port, FORGOT, {"email": "u9@example.com"}, ip="10.9.9.8")[0] == 200


@pytest.mark.pg
def test_reset_signs_in_clears_the_password_wait_and_ends_old_sessions(web):
    port, box, accounts = web
    old = accounts.register("lan@example.com", "mat-khau-dai")
    for _ in range(8):  # eight wrong passwords put this email on hold
        post(port, "/api/auth/login", {"email": "lan@example.com", "password": "sai-roi"}, ip="10.0.0.4")
    assert post(port, "/api/auth/login", {"email": "lan@example.com", "password": "mat-khau-dai"})[0] == 429
    post(port, FORGOT, {"email": "lan@example.com"})
    code = box.code()
    wrong = post(port, RESET, {"email": "lan@example.com", "code": "000000" if code != "000000" else "111111", "password": NEW})
    assert wrong[0] == 400 and wrong[1] == {"error": "wrong code", "tries_left": 4} and wrong[2] is None
    assert post(port, RESET, {"email": "lan@example.com", "code": code, "password": "short"})[0] == 400
    status, body, cookie = post(port, RESET, {"email": "Lan@Example.com", "code": code, "password": NEW})
    assert (status, body) == (200, {"signed_in": True})
    assert cookie.startswith("tg_session=") and "HttpOnly" in cookie and "Max-Age=2592000" in cookie
    assert accounts.user_for(cookie.split("=", 1)[1].split(";")[0])[0] is not None and accounts.user_for(old)[0] is None
    assert post(port, "/api/auth/login", {"email": "lan@example.com", "password": NEW})[0] == 200  # the hold is gone
    assert post(port, RESET, {"email": "lan@example.com", "code": code, "password": NEW})[:2] == (410, {"error": "code expired"})


@pytest.mark.pg
def test_the_fifth_wrong_code_answers_locked_and_the_route_checks_origin(web):
    port, box, accounts = web
    accounts.register("lan@example.com", "mat-khau-dai")
    post(port, FORGOT, {"email": "lan@example.com"})
    code = box.code()
    wrong = "000000" if code != "000000" else "111111"
    answers = [post(port, RESET, {"email": "lan@example.com", "code": wrong, "password": NEW})[:2] for _ in range(5)]
    assert [a[0] for a in answers] == [400, 400, 400, 400, 410] and answers[-1][1] == {"error": "code locked"}
    assert post(port, RESET, {"email": "lan@example.com", "code": code, "password": NEW})[0] == 410
    assert post(port, RESET, {"email": "lan@example.com", "code": code, "password": NEW}, origin=None)[0] == 403
    assert post(port, RESET, {"email": "lan@example.com", "code": 123456, "password": NEW})[0] == 400


@pytest.mark.pg
def test_a_mail_server_failure_changes_neither_the_answer_nor_the_log(accounts, monkeypatch, capsys):
    class Broken:
        def send(self, message):
            raise OSError("connection refused")
    accounts.register("lan@example.com", "mat-khau-dai")
    srv = serve(accounts, Broken(), monkeypatch)
    try:
        assert post(srv.server_address[1], FORGOT, {"email": "lan@example.com"})[:2] == (200, {"sent": True, "resend_after": 60, "expires_in": 600})
    finally:
        srv.shutdown()
        srv.server_close()
    err = capsys.readouterr().err
    assert "password reset mail failed: OSError" in err and not re.search(r"\d{6}", err)


def test_without_mail_the_routes_answer_503_and_the_page_is_told(monkeypatch, tmp_path):
    keyed = Accounts(None, None, tmp_path, Fernet.generate_key().decode())
    for accounts, mailer in ((keyed, None), (Accounts(None, None, tmp_path), Outbox())):
        srv = serve(accounts, mailer, monkeypatch)
        try:
            port = srv.server_address[1]
            assert post(port, FORGOT, {"email": "lan@example.com"})[:2] == (503, {"error": "password reset unavailable"})
            assert post(port, RESET, {"email": "lan@example.com", "code": "123456", "password": NEW})[0] == 503
            assert get(port, "/api/auth/options") == (200, {"password_reset": False})
        finally:
            srv.shutdown()
            srv.server_close()
