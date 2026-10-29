"""Google web search through the repo's browser, a backend for corpus.crawl.web (docs/CORPUS.md §Nguồn). Public API."""

from .crawl import ENGINE, crawl, load, run, search_pages, to_search_page
from .serp import Serp, SerpResult, parse as parse_serp

__all__ = ["ENGINE", "Serp", "SerpResult", "crawl", "load", "parse_serp", "run", "search_pages", "to_search_page"]
