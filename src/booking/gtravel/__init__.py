"""Stay adapter: gtravel link and price, from the published stay_prices."""

from .. import _stay
from ..settings import Settings
from ..types import Offer, StayQuery

PROVIDER = "gtravel"


def offers(q: StayQuery, cfg: Settings, source=None) -> list[Offer]:
    return _stay.offers(PROVIDER, q, cfg, source)
