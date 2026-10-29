"""Trip's door to the web: the client lives in corpus.crawl.web (one SearXNG source for corpus and Trip)."""

import socket  # noqa: F401  tests/trip/test_web.py patches web_mod.socket (the same module object as client.socket)

from corpus.crawl.web import Web, WebError, WebHit, WebPage

__all__ = ["Web", "WebError", "WebHit", "WebPage"]
