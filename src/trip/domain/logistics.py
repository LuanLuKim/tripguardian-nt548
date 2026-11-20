"""Logistics helpers (docs/TRIP_UNDERSTANDING.md §Hậu cần): the road or airport a trip enters the city by, the route of a
coach or flight, and how a chosen coach / flight sets the day's window and the city's entry / exit.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING
from datetime import datetime, timedelta

from ..infrastructure.settings import Settings
from .state import Base, Evidence, Transit, TripState, Update, apply, settle

if TYPE_CHECKING:
    from .frame import Moment

CITY = (11.9404, 108.4583)  # Đà Lạt centre (Chợ Đà Lạt), the same point Place Decision measures from
AIRPORT = Base(text="Sân bay Liên Khương", lat=11.7502, lng=108.3672)
BUS_STATION = Base(text="Bến xe Liên tỉnh Đà Lạt", lat=11.9276, lng=108.4446)
MODE_LABEL = {"self": "Tự đi (xe máy, ô tô)", "bus": "Xe khách", "plane": "Máy bay"}


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Initial bearing from a to b in degrees, 0 = north, clockwise."""
    la1, la2, dl = math.radians(a[0]), math.radians(b[0]), math.radians(b[1] - a[1])
    y = math.sin(dl) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def entry_road(origin: Base, cfg: Settings) -> Base | None:
    """Driving in: the pass the origin's direction comes in by (config/trip.yaml entry_roads); None without a point."""
    if origin.lat is None or origin.lng is None:
        return None
    deg = bearing(CITY, (origin.lat, origin.lng))
    for r in cfg.entry_roads:
        lo, hi = r["from_deg"], r["to_deg"]
        if (lo <= deg < hi) if lo < hi else (deg >= lo or deg < hi):
            return Base(text=r["text"])
    return None


def nearest_airport(origin: Base, cfg: Settings) -> dict | None:
    if origin.lat is None or origin.lng is None or not cfg.airports:
        return None
    return min(cfg.airports, key=lambda a: (a["lat"] - origin.lat) ** 2 + ((a["lng"] - origin.lng) * math.cos(math.radians(origin.lat))) ** 2)


def route(state: TripState, cfg: Settings) -> tuple[str, str] | None:
    """(from, to) of the trip in: IATA codes for a flight, province names for a coach (its card also carries the
    origin's point, which src/live/buses prefers). None when unknown."""
    origin = state.origin.value
    if origin is None:
        return None
    if state.arrival_mode.value == "plane":
        a = nearest_airport(origin, cfg)
        return (a["iata"], "DLI") if a else None
    if state.arrival_mode.value == "bus":
        return (origin.province or origin.text, "Lâm Đồng")
    return None


def travel_moments(state: TripState) -> tuple[Moment | None, Moment | None]:
    """Explicit physical moments take precedence over a selected transit."""
    from .frame import Moment

    arrive, leave = state.frame.arrive.value, state.frame.leave.value
    if arrive is None and state.inbound.value:
        arrive = Moment(at=state.inbound.value.arrive_at, how=state.inbound.value.mode)
    if leave is None and state.outbound.value:
        leave = Moment(at=state.outbound.value.depart_at, how=state.outbound.value.mode)
    return arrive, leave


def with_travel_points(state: TripState) -> TripState:
    """Resolve the local airport for a flight without mutating user facts."""
    arrive, leave = travel_moments(state)
    updates = {}
    for key, moment in (("entry_point", arrive), ("exit_point", leave)):
        field = getattr(state, key)
        if not field.known and moment and moment.how == "plane":
            updates[key] = field.model_copy(update={"value": AIRPORT, "source": "inferred"})
        elif field.value and field.value.text == AIRPORT.text and field.value.lat is None and field.value.lng is None:
            updates[key] = field.model_copy(update={"value": field.value.model_copy(update={
                "lat": AIRPORT.lat, "lng": AIRPORT.lng})})
    return state.model_copy(update=updates) if updates else state


def travel_bound(moment: Moment | None, buffer_min: int, entry_min: int, *, departing: bool = False,
                 point: Base | None = None) -> datetime | None:
    """One physical boundary for the frame, legacy hours and gate suggestions."""
    if buffer_min < 0 or entry_min < 0:
        raise ValueError("arrival buffer and entry road minutes must be nonnegative")
    if moment is None:
        return None
    routed = point is not None and point.lat is not None and point.lng is not None
    minutes = 0 if moment.how == "self" else buffer_min + (0 if routed else entry_min)
    return datetime.fromisoformat(moment.at) + timedelta(minutes=-minutes if departing else minutes)


def pick_transit(state: TripState, way: str, t: Transit, cfg: Settings, turn: int) -> TripState:
    """The user chose a coach / flight: it is stored, and the city's entry / exit follow from it. The day's window
    follows too, when the Search Input is compiled (compile.day_window): arrival + buffer, departure − buffer."""
    ev = Evidence(turn=turn, tool=f"transit:{way}")

    def put(field, value):
        return Update(field=field, value=value, source="user", confidence="high", evidence=ev)

    state = apply(state, put(way, t))
    if way == "inbound":
        state = apply(state, put("entry_point", Base(text=t.to_point)))
    else:
        state = apply(state, put("exit_point", Base(text=t.from_point)))
    return settle(state)


# ---------- trade-off sentences (docs/BOOKING.md §Chọn chuyến, nhà, đèo, đánh đổi) ----------

LONG_RIDE_MIN = 240  # a road or coach leg this long is a long sit for a small child


def _night(t: Transit | None) -> bool:
    """A coach or flight leaving late evening / before dawn, or arriving on another day than it left."""
    if t is None:
        return False
    hour = int(t.depart_at[11:13])
    return hour >= 21 or hour < 5 or t.arrive_at[:10] != t.depart_at[:10]


def tradeoffs(state: TripState, cfg: Settings, ride_min: int | None = None) -> list[dict]:
    """Short sentences [{"code", "text"}] about what the chosen way in costs THIS party, each grounded in a fact the
    trip holds (a signal, a companion, the way in, the road's pass); none for a fact that is unknown, nothing guessed.
    ride_min: the road leg's minutes when the caller has them (journey), else the coach's own length."""
    out: list[dict] = []
    mode = state.arrival_mode.value
    t = state.inbound.value
    road = entry_road(state.origin.value, cfg) if state.origin.value else None
    sick = any(s.kind == "motion_sick" for s in state.signals)
    small = any(s.kind == "kids" for s in state.signals) or bool({"kids", "baby"} & set(state.companions.value or ()))
    if t is not None and ride_min is None:
        ride_min = int((datetime.fromisoformat(t.arrive_at) - datetime.fromisoformat(t.depart_at)).total_seconds() // 60)
    if sick and mode in ("self", "bus") and road is not None:
        out.append({"code": "pass_motion_sick", "text": f"Đường vào Đà Lạt qua {road.text} nhiều cua và dốc, bạn hay say xe nên cần "
                                                        f"nghỉ giữa đèo; đi máy bay hoặc xe đi ban ngày sẽ nhẹ hơn."})
    if small and mode in ("self", "bus") and ride_min is not None and ride_min >= LONG_RIDE_MIN:
        out.append({"code": "small_kids_long_ride", "text": f"Chặng đường khoảng {round(ride_min / 60)} giờ, với trẻ nhỏ nên "
                                                          f"dừng nghỉ giữa đường hoặc cân nhắc đi máy bay."})
    if mode == "bus" and _night(t):
        out.append({"code": "overnight_bus", "text": "Xe chạy đêm: bạn ngủ trên xe và đến sáng sớm, ngày đầu có thể mệt, "
                                                      "chưa nhận phòng được ngay."
                                                      + (" Có trẻ nhỏ nên càng khó ngủ." if small else "")})
    return out
