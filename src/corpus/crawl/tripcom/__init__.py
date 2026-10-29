"""Trip.com lodging price for trip dates, a cross-check on Google Travel (docs/CORPUS.md §Nguồn, tripcom). Public API."""

from .crawl import SOURCE, list_url, observation, run
from .parser import Hotel, parse_list

__all__ = ["Hotel", "SOURCE", "list_url", "observation", "parse_list", "run"]
