"""Google web search through the repo's browser, a backend for corpus.crawl.web (docs/CORPUS.md §Nguồn). Public API."""

from . import places
from .crawl import ENGINE, crawl, key, load, run, search_pages, to_search_page
from . import panel
from .serp import Serp, SerpResult, parse as parse_serp

__all__ = ["panel", "places", "ENGINE", "Serp", "SerpResult", "crawl", "key", "load", "parse_serp", "run", "search_pages", "to_search_page"]
