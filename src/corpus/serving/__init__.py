"""Serving records for Place Decision (docs/PLACE_DECISION.md §2.2): intel -> data/serving/places.json.

python -m corpus serving
"""

from . import clips, dishes, flight_offers, reputation, scenes, stay_prices
from .evidence import conf
from .details import finish
from .groups import areas, mmr, near_duplicate_groups, similarity
from .record import SERVED, build, check, feature
from .run import load, run

__all__ = ["SERVED", "areas", "build", "check", "clips", "conf", "dishes", "feature", "flight_offers", "finish", "load", "mmr", "near_duplicate_groups", "reputation", "run", "scenes", "similarity", "stay_prices"]
