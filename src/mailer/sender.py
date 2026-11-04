"""SMTP sender configured from .env (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM) and config/mail.yaml.
Port 465 uses implicit TLS, any other port STARTTLS. The dev outbox (MAIL_DEV_OUTBOX=1) writes messages to a file instead
of sending and is refused on an https APP_BASE_URL, so a real deployment can never leave codes in a file."""

import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr
from pathlib import Path

import yaml

from .message import Message

ROOT = Path(__file__).resolve().parents[2]


class MailError(Exception):
    """A message that could not be handed to the mail server. The text never contains the message body."""


class Mailer:
    def __init__(self, host: str = "", port: int = 587, user: str = "", password: str = "", sender: str = "",
                 name: str = "TripGuardian", timeout: float = 15, outbox: Path | None = None):
        self.host, self.port, self.user, self.password = host, port, user, password
        self.address = parseaddr(sender)[1]  # MAIL_FROM may be "Name <a@b.c>"; the display name comes from the config
        self.name, self.timeout, self.outbox = name, timeout, outbox

    def send(self, message: Message) -> None:
        if self.outbox is not None:
            self.outbox.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.outbox, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as out:
                out.write(json.dumps({"to": message.to, "subject": message.subject, "text": message.text}, ensure_ascii=False) + "\n")
            return
        mail = EmailMessage()
        mail["From"], mail["To"], mail["Subject"] = formataddr((self.name, self.address)), message.to, message.subject
        mail["Date"], mail["Message-ID"] = formatdate(localtime=False), make_msgid(domain=self.address.rpartition("@")[2] or None)
        mail.set_content(message.text)
        mail.add_alternative(message.html, subtype="html")
        context = ssl.create_default_context()
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context) as smtp:
                    self._deliver(smtp, mail)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                    smtp.starttls(context=context)
                    self._deliver(smtp, mail)
        except (smtplib.SMTPException, OSError) as exc:
            raise MailError(f"{type(exc).__name__}: {exc}") from exc

    def _deliver(self, smtp, mail: EmailMessage) -> None:
        if self.user:
            smtp.login(self.user, self.password)
        smtp.send_message(mail)


def from_env(root: Path = ROOT) -> Mailer | None:
    """None when mail is not configured; callers then answer 503 instead of pretending to send."""
    cfg = yaml.safe_load((root / "config" / "mail.yaml").read_text(encoding="utf-8"))
    name, timeout = cfg["from_name"], float(cfg["timeout_s"])
    if os.environ.get("MAIL_DEV_OUTBOX") == "1":
        if os.environ.get("APP_BASE_URL", "").startswith("https://"):
            print("MAIL_DEV_OUTBOX is ignored on an https APP_BASE_URL", file=sys.stderr)
        else:
            outbox = root / cfg["dev_outbox"]
            print(f"MAIL_DEV_OUTBOX=1: mails are written to {outbox}, not sent", file=sys.stderr)
            return Mailer(sender="dev@localhost", name=name, outbox=outbox)
    host, sender = os.environ.get("SMTP_HOST", "").strip(), os.environ.get("MAIL_FROM", "").strip()
    if not host or not parseaddr(sender)[1]:
        return None
    try:
        port = int(os.environ.get("SMTP_PORT") or 587)
    except ValueError:
        return None
    return Mailer(host, port, os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASSWORD", ""), sender, name, timeout)
