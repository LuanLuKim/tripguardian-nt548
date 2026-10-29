"""Flight adapter: the flights the crawl read from Google Flights for that route and day (corpus.serving.flight_offers),
each with the search page link and the airports as Google names them (the trip's entry / exit point once picked). Without a fresh crawled search (none yet, or older than flight_max_age_h) it is the
prefilled search link alone: no price, time or carrier, because a link cannot promise them."""

from datetime import datetime

import live
from corpus.serving import flight_offers

from ..links import tag
from ..settings import Settings
from ..types import FlightQuery, Offer

PROVIDER = "google_flights"


def offers(q: FlightQuery, cfg: Settings, source=None) -> list[Offer]:
    """`source(city, max_age_h)` replaces the reader of the published flights (tests)."""
    link = tag(live.flights_url(q.src, q.dst, q.day), PROVIDER, cfg)
    found = (source or flight_offers.load)(cfg.flight_city, cfg.flight_max_age_h).get((q.src, q.dst, q.day.isoformat()))
    rows = (found or {}).get("offers") or []
    if not rows:
        return [Offer(provider=PROVIDER, kind="flight", mode="deeplink", url=link, from_point=q.src, to_point=q.dst)]
    return [Offer(provider=PROVIDER, kind="flight", mode="deeplink", url=link, price_vnd=r.get("price_vnd"),
                  price_unit="ticket" if r.get("price_vnd") else None, available=True if r.get("price_vnd") else None, observed_at=found["observed_at"],
                  source="gflights", carrier=r["carrier"], flight_no=r.get("flight_no"), stops=r.get("stops"),
                  depart_at=r["depart_at"], arrive_at=r["arrive_at"], from_point=r.get("from_point") or q.src,
                  to_point=r.get("to_point") or q.dst, duration_min=_minutes(r["depart_at"], r["arrive_at"]),
                  fetched_at=found["observed_at"]) for r in rows]


def _minutes(depart_at: str, arrive_at: str) -> int:
    """Air time incl. connections, from the two local clock times (all Vietnamese airports share one time zone)."""
    return round((datetime.fromisoformat(arrive_at) - datetime.fromisoformat(depart_at)).total_seconds() / 60)
