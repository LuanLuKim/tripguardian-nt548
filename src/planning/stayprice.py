"""Dated lodging prices for the trip's own stay (corpus.serving.stay_prices) laid over a candidate's reference price.

The key is exact: (stay id, check-in = trip start date, nights). Another date or another length is a different price, so
it is never borrowed; a row older than `stay_price_max_age_h` is dropped by the loader. Nothing known -> the reference
night price from Maps' hotel list (`price_kind: reference`, dated by `price_at`), and nothing at all -> unknown (None).
"""

from datetime import UTC, datetime

import live
from corpus.serving import stay_prices
from trip import nights

from .settings import Settings


def load_prices(city: str, max_age_h: float | None = None) -> dict:
    return stay_prices.load(city, max_age_h)


def age_h(observed_at: str | None, now: datetime | None = None) -> float | None:
    """Hours since the price was seen, one decimal; None when there is no readable `observed_at`."""
    try:
        seen = datetime.fromisoformat(observed_at)
    except (TypeError, ValueError):
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    return round(((now or datetime.now(UTC)) - seen).total_seconds() / 3600, 1)


def overlay(cands: list[dict], tc: dict, cfg: Settings) -> list[dict]:
    """Each candidate with `price_kind` ("dated" | "reference" | None) and, for a dated price, `price_vnd` = the observed
    night price and `price_at` = its `observed_at`."""
    start, n = tc.get("start_date"), nights(tc)
    table = load_prices(live.load_settings().views_city, cfg.stay_price_max_age_h) if start and n > 0 else {}
    out = []
    for c in cands:
        got = table.get((c["id"], start, n))
        if got and got.get("price_night_vnd"):
            out.append({**c, "price_vnd": got["price_night_vnd"], "price_at": got["observed_at"], "price_kind": "dated"})
        else:
            out.append({**c, "price_kind": "reference" if c.get("price_vnd") is not None else None})
    return out
