"""Raw data crawl: one module per source, plain files under DATA_DIR, nothing is ever deleted.

Public API for other packages (RULE.md §2): a caller outside src/corpus/crawl may use only these three names, plus
corpus.crawl.web, which has its own public API (the SearXNG client shared with Trip).
"""

from .common.browser import LoginRequired, open_sessions
from .gmaps.search import search as maps_search

__all__ = ["LoginRequired", "maps_search", "open_sessions"]
