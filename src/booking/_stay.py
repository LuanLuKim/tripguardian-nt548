"""Stay offers from the prices corpus.serving published (the price crawls' newest row per stay). Shared by the stay
adapters, one provider each; nothing is fetched here and an unpriced stay has no offer."""

from datetime import UTC, datetime, timedelta

from corpus.serving import stay_prices

from .links import tag
from .settings import Settings
from .types import Offer, StayQuery


def _fresh(observed_at: str | None, max_age_h: float) -> bool:
    try:
        seen = datetime.fromisoformat(observed_at)
    except (TypeError, ValueError):
        return False
    return datetime.now(UTC) - seen <= timedelta(hours=max_age_h)


def offers(provider: str, q: StayQuery, cfg: Settings, load=None) -> list[Offer]:
    item = (load or stay_prices.load)(q.city or cfg.stay_city).get((q.fid, q.check_in.isoformat(), q.nights))
    if item is None:
        return []
    if item.get("source") == provider:
        row = item
    else:
        row = (item.get("cross_check") or {}).get(provider)
        row = {**row, "available": None, "source": provider} if row else None
    if not row or not row.get("url"):
        return []
    fresh = _fresh(row.get("observed_at"), cfg.stay_max_age_h) and bool(row.get("price_total_vnd"))
    return [Offer(provider=provider, kind="stay", mode="deeplink", url=tag(row["url"], provider, cfg),
                  source=provider, stay_dates=(q.check_in.isoformat(), (q.check_in + timedelta(days=q.nights)).isoformat()),
                  price_vnd=row["price_total_vnd"] if fresh else None, price_unit="stay_total" if fresh else None,
                  price_night_vnd=row.get("price_night_vnd") if fresh else None,
                  available=row.get("available") if fresh else None, observed_at=row["observed_at"] if fresh else None)]
