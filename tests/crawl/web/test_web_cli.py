"""python -m corpus web <search|documents|all>."""

import importlib

import corpus.__main__ as cli
import corpus.crawl.web as web


def test_web_phases_registered():
    assert set(cli.PHASES["web"]) == {"search", "documents"}
    assert all(needs_browser is False for _, needs_browser in cli.PHASES["web"].values())


def test_web_run_passes_limit(monkeypatch):
    calls = []
    phases = {name: ((lambda city, limit=None, _n=name: calls.append((_n, city, limit))), False)
              for name in ("search", "documents")}
    monkeypatch.setitem(cli.PHASES, "web", phases)
    cli.run("web", "all", "dalat", False, limit=5)
    assert calls == [("search", "dalat", 5), ("documents", "dalat", 5)]


def test_public_api_names():
    module = importlib.import_module("corpus.crawl.web")
    assert set(module.__all__) == {"Web", "WebHit", "WebPage", "WebError", "BudgetExhausted", "SearchPage",
                                   "SearchResult", "WebDocument", "validate_public_url", "Query", "seed_queries",
                                   "slug_queries", "run_search", "run_documents"}
    assert all(hasattr(web, name) for name in module.__all__)
