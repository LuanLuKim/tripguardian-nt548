"""Upcoming events of a city from the web, with their own days (docs/CORPUS.md §Sự kiện sắp tới). Offline writes
data/<city>/events/; corpus.pulse turns them into the bulletin's event items."""

from .run import load, run

__all__ = ["load", "run"]
