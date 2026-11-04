import json
import smtplib

import pytest

from mailer import MailError, Mailer, from_env, reset_code_message


def test_reset_message_has_the_code_the_expiry_and_the_ignore_line():
    msg = reset_code_message("lan@example.com", "042917", 10)
    for body in (msg.text, msg.html):
        assert "042 917" in body and "10 phút" in body and "bỏ qua email này" in body
    assert "042917" in msg.subject and "TripGuardian" in msg.subject
    assert "<html" in msg.html and "http" not in msg.text  # no links to click


class FakeSMTP:
    log = []

    def __init__(self, host, port, timeout=None, context=None):
        FakeSMTP.log.append(("connect", type(self).__name__, host, port))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        FakeSMTP.log.append(("starttls", context is not None))

    def login(self, user, password):
        FakeSMTP.log.append(("login", user, password))

    def send_message(self, mail):
        FakeSMTP.log.append(("send", mail))


class FakeSSL(FakeSMTP):
    pass


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.log = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSSL)
    return FakeSMTP.log


def test_port_587_uses_starttls_and_sends_text_and_html_from_the_display_name(smtp):
    Mailer("smtp.example.com", 587, "me@example.com", "app-pass", "me@example.com").send(reset_code_message("lan@example.com", "123456", 10))
    assert smtp[0] == ("connect", "FakeSMTP", "smtp.example.com", 587)
    assert smtp[1] == ("starttls", True) and smtp[2] == ("login", "me@example.com", "app-pass")
    mail = smtp[3][1]
    assert mail["From"] == "TripGuardian <me@example.com>" and mail["To"] == "lan@example.com"
    assert mail.get_body(("plain",)).get_content().count("123 456") == 1
    assert "123 456" in mail.get_body(("html",)).get_content()
    assert mail["Date"] and mail["Message-ID"]


def test_port_465_uses_implicit_tls_and_a_named_from_address_keeps_only_the_address(smtp):
    Mailer("smtp.example.com", 465, "u", "p", "Someone <me@example.com>").send(reset_code_message("a@b.vn", "000001", 10))
    assert smtp[0][1] == "FakeSSL" and not any(entry[0] == "starttls" for entry in smtp)
    assert smtp[-1][1]["From"] == "TripGuardian <me@example.com>"


def test_smtp_failures_become_mail_errors_without_the_message_body(monkeypatch):
    class Down(FakeSMTP):
        def starttls(self, context=None):
            raise smtplib.SMTPConnectError(421, "busy")
    monkeypatch.setattr(smtplib, "SMTP", Down)
    with pytest.raises(MailError) as err:
        Mailer("h", 587, "", "", "me@example.com").send(reset_code_message("a@b.vn", "654321", 10))
    assert "654321" not in str(err.value)


def env(monkeypatch, **values):
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM", "MAIL_DEV_OUTBOX", "APP_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_mail_is_off_unless_host_and_sender_are_set(monkeypatch):
    env(monkeypatch)
    assert from_env() is None
    env(monkeypatch, SMTP_HOST="smtp.gmail.com")
    assert from_env() is None
    env(monkeypatch, MAIL_FROM="me@gmail.com")
    assert from_env() is None
    env(monkeypatch, SMTP_HOST="smtp.gmail.com", MAIL_FROM="me@gmail.com", SMTP_PORT="not-a-number")
    assert from_env() is None
    env(monkeypatch, SMTP_HOST="smtp.gmail.com", MAIL_FROM="me@gmail.com", SMTP_USER="me@gmail.com", SMTP_PASSWORD="x")
    mailer = from_env()
    assert (mailer.host, mailer.port, mailer.address, mailer.name, mailer.outbox) == ("smtp.gmail.com", 587, "me@gmail.com", "TripGuardian", None)


def test_dev_outbox_writes_a_file_only_when_asked_and_never_on_https(monkeypatch, tmp_path, capsys):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mail.yaml").write_text("from_name: TripGuardian\ntimeout_s: 5\ndev_outbox: logs/box.jsonl\n")
    env(monkeypatch, APP_BASE_URL="http://127.0.0.1:5999")
    assert from_env(tmp_path) is None  # the flag is off: no outbox, and SMTP is not set
    env(monkeypatch, MAIL_DEV_OUTBOX="1", APP_BASE_URL="http://127.0.0.1:5999")
    mailer = from_env(tmp_path)
    mailer.send(reset_code_message("lan@example.com", "111222", 10))
    line = json.loads((tmp_path / "logs" / "box.jsonl").read_text().splitlines()[0])
    assert line["to"] == "lan@example.com" and "111 222" in line["text"]
    assert oct((tmp_path / "logs" / "box.jsonl").stat().st_mode & 0o777) == "0o600"
    env(monkeypatch, MAIL_DEV_OUTBOX="1", APP_BASE_URL="https://tripguardian.example")
    assert from_env(tmp_path) is None
    assert "ignored" in capsys.readouterr().err
