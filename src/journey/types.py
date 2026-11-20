"""What journey.options returns. Every number a source did not give stays None."""

from dataclasses import asdict, dataclass

from booking import Offer

Point = tuple[float, float]  # (lat, lng)


@dataclass(frozen=True)
class Leg:
    kind: str  # drive | transfer | flight
    from_label: str  # origin | lodging | centre | an IATA code
    to_label: str
    minutes: int | None = None
    distance_km: float | None = None
    coords: list | None = None  # [[lat, lng], …] the line to draw
    source: str | None = None
    fetched_at: str | None = None
    via: str | None = None  # the pass a drive leg comes in by (config/journey.yaml entry_roads); None when unknown
    rides: dict | None = None  # a transfer leg's ride-hailing quotes (journey.rides.leg_quote), when asked for


@dataclass(frozen=True)
class Option:
    mode: str  # car | motorbike | bus | plane
    feasible: bool | None  # None: the code could not tell (unchecked, no date, a source down)
    reason: str  # short code, worded by the UI
    legs: tuple[Leg, ...] = ()
    minutes: int | None = None  # door to door; None unless every leg is known
    price_min_vnd: int | None = None
    price_max_vnd: int | None = None
    offers: tuple[Offer, ...] = ()

    def as_dict(self) -> dict:
        d = asdict(self)
        d["legs"] = [asdict(leg) for leg in self.legs]
        d["offers"] = [o.as_dict() for o in self.offers]
        return d


@dataclass(frozen=True)
class Journey:
    origin: Point
    dest: Point
    dest_is_centre: bool
    way: str
    day: str | None
    options: tuple[Option, ...]
    ride_brands: dict | None = None  # where the transfer legs' ride quotes come from (journey.rides.brands)

    def as_dict(self) -> dict:
        d = {"origin": list(self.origin), "dest": list(self.dest), "dest_is_centre": self.dest_is_centre,
             "way": self.way, "day": self.day, "options": [o.as_dict() for o in self.options]}
        if self.ride_brands is not None:
            d["ride_brands"] = self.ride_brands
        return d
