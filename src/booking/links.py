"""Affiliate tagging of a deeplink: only when the config names a query param and .env holds the partner id."""

import os
from urllib.parse import urlencode

from dotenv import load_dotenv

from .settings import ROOT, Settings


def tag(url: str, provider: str, cfg: Settings) -> str:
    rule = cfg.affiliate.get(provider) or {}
    if not rule.get("param") or not rule.get("env"):
        return url
    load_dotenv(ROOT / ".env")
    value = os.environ.get(rule["env"], "").strip()
    if not value:
        return url
    return f"{url}{'&' if '?' in url else '?'}{urlencode({rule['param']: value})}"
