"""The contract between the UI and every provider: Offer, and one typed query per kind."""

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date

KINDS = ("coach", "flight", "stay")
WAYS = ("inbound", "outbound")
IATA = re.compile(r"[A-Z]{3}")
FID = re.compile(r"[A-Za-z0-9_:.-]{3,80}")


@dataclass(frozen=True)
class Offer:
    """What a provider link can legitimately state. Every field a link does not state stays None (unknown), never a guess."""

    provider: str
    kind: str  # coach | flight | stay
    mode: str  # deeplink | api (api adapters do not exist yet)
    url: str | None = None
    price_vnd: int | None = None
    price_unit: str | None = None  # ticket (one seat) | stay_total (the whole stay, all rooms asked for)
    price_night_vnd: int | None = None
    available: bool | None = None
    observed_at: str | None = None  # when the price was seen; None when the offer states no price
    source: str | None = None
    carrier: str | None = None
    flight_no: str | None = None  # a flight's number(s), "VJ 360" or "VN 123 + VN 456" for a connection
    depart_at: str | None = None
    arrive_at: str | None = None
    from_point: str | None = None
    to_point: str | None = None
    stay_dates: tuple[str, str] | None = None  # (check_in, check_out)
    stops: int | None = None  # a flight's stopovers (0 = direct); None for anything else or unknown
    duration_min: int | None = None  # a flight's length as the source states it
    fetched_at: str | None = None  # when the trip (times, carrier) was read from its source

    @property
    def offer_id(self) -> str:
        raw = "|".join(str(v) for v in (self.provider, self.kind, self.carrier, self.depart_at, self.from_point,
                                          self.stay_dates, self.url))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["stay_dates"] = list(self.stay_dates) if self.stay_dates else None
        return {"offer_id": self.offer_id, **d, "transit": self.transit()}

    def transit(self) -> dict | None:
        """The trip's Transit (trip.domain.state.Transit, the payload of the inbound / outbound pick) for a coach or flight
        that states both times and a source; None otherwise, so a link-only offer cannot be picked as a trip."""
        if self.kind not in ("coach", "flight") or not (self.depart_at and self.arrive_at and self.carrier and self.source and self.fetched_at):
            return None
        return {"mode": "bus" if self.kind == "coach" else "plane", "carrier": self.carrier, "depart_at": self.depart_at[:16],
                "arrive_at": self.arrive_at[:16], "from_point": self.from_point or "", "to_point": self.to_point or "",
                "price_vnd": self.price_vnd, "stops": self.stops, "source": self.source,
                "fetched_at": self.fetched_at}


@dataclass(frozen=True)
class CoachQuery:
    origin: tuple[float, float] | str  # a point (lat, lng) or a province name
    day: date
    way: str = "inbound"


@dataclass(frozen=True)
class FlightQuery:
    src: str  # IATA
    dst: str
    day: date


@dataclass(frozen=True)
class StayQuery:
    fid: str  # Maps fid, the corpus key of the lodging
    check_in: date
    nights: int
    city: str | None = None  # None: the city in config/booking.yaml


Query = CoachQuery | FlightQuery | StayQuery
QUERY_TYPE = {"coach": CoachQuery, "flight": FlightQuery, "stay": StayQuery}


def _day(raw) -> date:
    try:
        return date.fromisoformat(str(raw))
    except ValueError as e:
        raise ValueError(f"bad date {raw!r}") from e


def _num(raw, lo: float, hi: float, name: str) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"bad {name}") from e
    if not lo <= v <= hi:
        raise ValueError(f"{name} out of range")
    return v


def query_from_params(kind: str, p: dict) -> Query:
    """Build a typed query from untrusted request parameters; ValueError on anything out of shape."""
    if kind == "coach":
        way = p.get("way", "inbound")
        if way not in WAYS:
            raise ValueError("bad way")
        if p.get("lat") is not None or p.get("lng") is not None:
            origin = (_num(p.get("lat"), -90, 90, "lat"), _num(p.get("lng"), -180, 180, "lng"))
        elif isinstance(p.get("origin"), str) and 2 <= len(p["origin"].strip()) <= 80:
            origin = p["origin"].strip()
        else:
            raise ValueError("coach needs lat+lng or origin")
        return CoachQuery(origin=origin, day=_day(p.get("date")), way=way)
    if kind == "flight":
        src, dst = str(p.get("src", "")).upper(), str(p.get("dst", "")).upper()
        if not (IATA.fullmatch(src) and IATA.fullmatch(dst)):
            raise ValueError("bad IATA code")
        return FlightQuery(src=src, dst=dst, day=_day(p.get("date")))
    if kind == "stay":
        fid = str(p.get("fid", ""))
        if not FID.fullmatch(fid):
            raise ValueError("bad fid")
        nights = int(_num(p.get("nights"), 1, 30, "nights"))
        return StayQuery(fid=fid, check_in=_day(p.get("check_in")), nights=nights)
    raise ValueError(f"unknown kind {kind!r}")
