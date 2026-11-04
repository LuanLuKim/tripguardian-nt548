"""SearXNG as a corpus source (docs/CORPUS.md §Nguồn): one shared client, data under data/web/. Public API."""

from .client import (BudgetExhausted, SearchPage, SearchResult, Web, WebDocument, WebError, WebHit, WebPage,
                     validate_public_url)
from .discover import run as run_search
from . import places
from .documents import run as run_documents
from .queries import Query, seed_queries, slug_queries

__all__ = ["BudgetExhausted", "Query", "SearchPage", "SearchResult", "Web", "WebDocument", "WebError", "WebHit",
           "WebPage", "places", "run_documents", "run_search", "seed_queries", "slug_queries", "validate_public_url"]
