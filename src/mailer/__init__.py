"""Public mailer API: one small SMTP sender and the account mails (docs/ACCOUNTS.md §2c)."""

from .message import Message, reset_code_message
from .sender import MailError, Mailer, from_env

__all__ = ["MailError", "Mailer", "Message", "from_env", "reset_code_message"]
