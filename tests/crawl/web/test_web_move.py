import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import SplitResult

import pytest

import agents
import corpus.crawl.web as web
from trip.infrastructure import web as trip_web

SRC = Path(__file__).resolve().parents[3] / "src"


def test_trip_shim_reexports():
    assert trip_web.Web is web.Web
    assert trip_web.WebHit is web.WebHit
    assert trip_web.WebPage is web.WebPage
    assert trip_web.WebError is web.WebError


def test_validate_public_url_single_definition():
    assert agents.validate_public_url is web.validate_public_url
    for url in ("http://127.0.0.1/", "http://localhost/"):
        with pytest.raises(ValueError):
            web.validate_public_url(url)
    assert isinstance(web.validate_public_url("https://example.com/"), SplitResult)


def test_corpus_does_not_import_trip_or_agents():
    code = ("import corpus.crawl.web, sys; "
            "assert not [m for m in sys.modules if m.split('.')[0] in ('trip', 'agents')], 'trip/agents imported'")
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
