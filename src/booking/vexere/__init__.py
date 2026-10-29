"""Coach adapter: Vexere route page. Trips come from live.buses (one GET, cached); the link is the route page of that day."""

import live

from ..links import tag
from ..settings import Settings
from ..types import CoachQuery, Offer

PROVIDER = "vexere"


def offers(q: CoachQuery, cfg: Settings, source=None) -> list[Offer]:
    """One offer per trip the page lists that day. Nothing to list -> []. A page that cannot be read -> one link with
    no time and no price (the user can still look). An origin no Vexere region matches -> []."""
    lcfg = live.load_settings()
    try:
        link = tag(live.buses_url(q.origin, q.day, q.way, lcfg), PROVIDER, cfg)
    except live.Unavailable:
        return []
    try:
        rows = (source or live.buses)(q.origin, q.day, q.way, lcfg)
    except live.Unavailable:
        return [Offer(provider=PROVIDER, kind="coach", mode="deeplink", url=link)]
    return [Offer(provider=PROVIDER, kind="coach", mode="deeplink", url=link, carrier=r["carrier"],
                  depart_at=r["depart_at"], arrive_at=r["arrive_at"], from_point=r.get("from_point"),
                  to_point=r.get("to_point"), source=r.get("source"),
                  price_vnd=r.get("price_vnd"), price_unit="ticket" if r.get("price_vnd") else None,
                  observed_at=r.get("fetched_at") if r.get("price_vnd") else None, fetched_at=r.get("fetched_at")) for r in rows]
