"""Booking: one contract (Offer) between the UI and every provider; one adapter per provider (docs/BOOKING.md).

Online module: reads live context and corpus-served prices, writes nothing. Today every adapter is a deeplink to the
provider's page; the day a partner API exists it is another adapter with mode = api and the contract does not move.
"""

from . import google_flights, gtravel, tripcom, vexere
from .settings import Settings, load as load_settings
from .types import KINDS, WAYS, CoachQuery, FlightQuery, Offer, Query, StayQuery, query_from_params

ADAPTERS = {"coach": (vexere,), "flight": (google_flights,), "stay": (gtravel, tripcom)}
_TYPES = {"coach": CoachQuery, "flight": FlightQuery, "stay": StayQuery}


def offers(kind: str, query: Query, cfg: Settings | None = None, sources: dict | None = None) -> list[Offer]:
    """All offers of `kind` for the query, every provider of that kind in turn. `sources` maps a provider name to the
    function that reads its data (tests; None: the real one). A provider with nothing to state adds nothing."""
    if kind not in _TYPES:
        raise ValueError(f"unknown kind {kind!r}")
    if not isinstance(query, _TYPES[kind]):
        raise ValueError(f"a {kind} offer needs a {_TYPES[kind].__name__}")
    cfg = cfg or load_settings()
    out: list[Offer] = []
    for adapter in ADAPTERS[kind]:
        out += adapter.offers(query, cfg, (sources or {}).get(adapter.PROVIDER))
    return out


__all__ = ["ADAPTERS", "CoachQuery", "FlightQuery", "KINDS", "Offer", "Query", "Settings", "StayQuery", "WAYS", "load_settings",
           "offers", "query_from_params"]
