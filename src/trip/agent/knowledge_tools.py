"""The assistant's wider read tools and the trip actions save_place / hide_place (spec 2026-10-29 assistant-tools §5.1,
§5.3-5.7). Each tool is one input model (its docstring is what the agent reads) plus a function over
`infrastructure.reads.Reads` (turn.knowledge.more), registered through agents.assistant. Results carry sources and
dates; a field the corpus lacks is "unknown"."""

from __future__ import annotations

from typing import ClassVar, Literal

from agents.assistant import action_tool, read_tool
from pydantic import BaseModel, ConfigDict, Field

from ..domain.state import Anchor, ontology, settle, with_meta

DATE = r"^\d{4}-\d{2}-\d{2}$"


def _one(turn, ref: str) -> str:
    pid = turn.resolve_place(str(ref).strip())
    if pid is None:
        raise ValueError(f"no place {ref!r} in the corpus (or more than one fits): there is no data for it; say so, do not guess")
    return pid


def _many(turn, refs: list[str]) -> list[str]:
    return [_one(turn, r) for r in refs]


def resolve_find_places(turn, criteria: dict) -> dict:
    """find_places criteria with the place names of near_place / exclude mapped to ids (an unknown name is an error)."""
    out = dict(criteria)
    if isinstance(out.get("near_place"), str):
        out["near_place"] = _one(turn, out["near_place"])
    if isinstance(out.get("exclude"), list):
        out["exclude"] = [_one(turn, x) if x not in turn.catalog.by_id else x for x in out["exclude"] if isinstance(x, str)]
    return out


def _match_features(turn):
    """The question's words as feature ids: ontology keywords first, then Clef when it is on."""
    def match(question: str) -> list[str]:
        from .tools import keyword_features
        found = [f["id"] for f in keyword_features(question)]
        if not found and getattr(turn, "judge", None):
            try:
                found = list(turn.judge.features(question, ontology().features.values()))
            except Exception:  # Clef down: the answer says it has no matching evidence
                found = []
        return found
    return match


# ---------- 5.1 places ----------

class PlaceEvidence(BaseModel):
    """What the reviews and other sources say about ONE aspect of ONE place: parking, noise, crowd, toilets, kids,
    wheelchair, car access, price feeling, service... Returns each aspect's value, how many people said it, short
    quotes with their date and source, and what is unknown. Use it for "có chỗ đậu ô tô không", "có ồn không", "hợp trẻ
    nhỏ không", "đông giờ nào". Answer only from the result; unknown means say you have no evidence."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "place_evidence"

    id: str = Field(description="A place id or the place's name.")
    question: str = Field(min_length=1, max_length=200, description="The user's question in their words.")
    features: list[str] | None = Field(None, max_length=4, description=(
        "Feature ids from FEATURES that answer it (parking, noise, crowd, toilet_available, kids, elderly, wheelchair, "
        "car_access, pets...). Leave out and the app matches the question's words."))


@read_tool(PlaceEvidence, group="detail", place_args=("id",))
def place_evidence(turn, inp: PlaceEvidence) -> dict:
    return turn.knowledge.more.evidence(inp.id, inp.question, inp.features, turn.state, match=_match_features(turn))


class ComparePlaces(BaseModel):
    """Put 2-4 places side by side on the same fields: price, rating, hours today, open now, visit time and the aspects
    asked (feature ids). A field a place has no data for is "unknown". Use it for "A hay B", "so mấy chỗ này"."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "compare_places"

    ids: list[str] = Field(min_length=2, max_length=4, description="Place ids or names, 2 to 4.")
    aspects: list[str] | None = Field(None, max_length=6, description=(
        "Feature ids to compare (noise, crowd, parking, value_for_money, kids...). Leave out for crowd, noise, parking, "
        "value_for_money."))


@read_tool(ComparePlaces, group="compare")
def compare_places(turn, inp: ComparePlaces) -> dict:
    ids = _many(turn, inp.ids)
    out = turn.knowledge.more.compare(ids, inp.aspects, turn.state)
    out["_cards"] = ids
    return out


class PlaceStatus(BaseModel):
    """Is this place real and open: the corpus status, whether it is open at this moment (only when its hours are
    verified; otherwise unknown), when its data was last seen, and any permanent-closure report Google Maps gave. Use
    it for "quán này còn mở không", "có thật không", "đóng cửa chưa"."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "place_status"

    id: str = Field(description="A place id or the place's name (a closed place is found by its name).")


@read_tool(PlaceStatus, group="detail")
def place_status(turn, inp: PlaceStatus) -> dict:
    ref = turn.resolve_place(inp.id.strip()) or inp.id.strip()
    return turn.knowledge.more.status(ref, turn.state)


class FindDishes(BaseModel):
    """Places whose menu or reviews name a dish ("bánh căn", "lẩu gà lá é"), with the dish lines as written and the
    sources. The trip's limits are applied. No place = nothing written down about that dish, not that nobody serves it.
    The cards show the places."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "find_dishes"

    dish: str = Field(min_length=1, max_length=100, description="The dish as the user wrote it.")


@read_tool(FindDishes, group="places")
def find_dishes(turn, inp: FindDishes) -> dict:
    out = turn.knowledge.more.dishes(inp.dish, turn.state)
    out["_cards"] = out["ranked"]
    return out


# ---------- 5.3 travel ----------

class RouteTime(BaseModel):
    """Travel minutes through 2-6 stops in the order given, leg by leg and in total ("đi A rồi B rồi C mất bao lâu").
    Only movement: no visit time, no opening hours, not a schedule."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "route_time"

    ids: list[str] = Field(min_length=1, max_length=6, description="Place ids or names in visiting order.")
    start: str | None = Field(None, description='Where the first leg starts: a place id/name or "center". Leave out to start at the first place.')
    mode: Literal["walk", "motorbike", "car"] | None = Field(None, description="How the user travels, when they said (a walk is an estimate).")


@read_tool(RouteTime, group="distance")
def route_time(turn, inp: RouteTime) -> dict:
    ids = _many(turn, inp.ids)
    start = None if inp.start is None else ("center" if inp.start == "center" else _one(turn, inp.start))
    return turn.knowledge.more.route_time(ids, start, inp.mode, turn.state)


class Journey(BaseModel):
    """How to get to Đà Lạt from where the user starts, on a day: by car, motorbike, coach, plane, each with its time,
    price range and the flights or coach trips found (carrier, times, price, when it was seen). A way is feasible only
    with a real offer; "unknown" means it was not checked. Use it for "từ Hà Nội lên Đà Lạt đi gì", "vé máy bay bao nhiêu"."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "journey"

    origin: str | None = Field(None, description="Where the user sets off from (a city or place name). Leave out to use the trip's origin.")
    date: str | None = Field(None, pattern=DATE, description="The travel day YYYY-MM-DD. Leave out for the trip's start date.")


@read_tool(Journey, group="journey", cache=False)
def journey(turn, inp: Journey) -> dict:
    return turn.knowledge.more.journey(inp.origin, inp.date, turn.state)


# ---------- 5.4 climate, calendar ----------

class Climate(BaseModel):
    """Long-run climate of Đà Lạt by month (temperatures, share of rainy days, share of foggy days; many years of data,
    not a forecast). Omit the month to get all 12 and the rainiest months. Use it for "tháng 12 lạnh không", "mùa mưa
    tháng mấy". For a coming day use weather."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "climate"

    month: int | None = Field(None, ge=1, le=12, description="1..12, or leave out for all months.")


@read_tool(Climate, group="climate")
def climate(turn, inp: Climate) -> dict:
    return turn.knowledge.more.climate(inp.month)


class Calendar(BaseModel):
    """Public holidays, lunar dates, weekends and known events in a date range of at most 45 days. It has NO data on how
    crowded a date is: do not say a date is busy or quiet. Use it for "dịp lễ", "cuối tuần có sự kiện gì"."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "calendar"

    date_from: str = Field(pattern=DATE, description="First day YYYY-MM-DD.")
    date_to: str = Field(pattern=DATE, description="Last day YYYY-MM-DD, at most 45 days after the first.")


@read_tool(Calendar, group="calendar")
def calendar(turn, inp: Calendar) -> dict:
    from datetime import date
    try:
        a, b = date.fromisoformat(inp.date_from), date.fromisoformat(inp.date_to)
    except ValueError:
        raise ValueError("dates must be real YYYY-MM-DD days") from None
    return turn.knowledge.more.calendar(a, b, turn.state)


# ---------- 5.5 stays and cost ----------

class FindStays(BaseModel):
    """Hotels, homestays and other lodging that fit what the user wants, through the trip's limits. Each stay has its
    night price: kind dated (crawled for those dates, with the day it was seen) or reference (the Google Maps listing
    price, with its date: say it is a reference). criteria are the find_places keys (near_place, price_max per night,
    sort price, must / prefer, text...); groups is always lodging. A stay with no price is left out and counted in
    no_price. The cards show the stays."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "find_stays"

    criteria: dict = Field(default_factory=dict, description=(
        "As find_places criteria: must / prefer [[fid, value]], near_place, near_km, price_max (VND per night), sort "
        "fit | price | reputation | distance, exclude, page, text."))
    dates: dict | None = Field(None, description='{"check_in": "YYYY-MM-DD", "nights": 2} when the user gave dates.')


@read_tool(FindStays, group="stays")
def find_stays(turn, inp: FindStays) -> dict:
    out = turn.knowledge.more.stays(resolve_find_places(turn, inp.criteria), inp.dates, turn.state)
    out["_cards"] = out["ranked"]
    return out


class EstimateCost(BaseModel):
    """What 1-10 places cost for a number of people: entry (official adult price, else the estimated fee), spend per
    person (menu price range) and lodging room-nights. Adds only what is stated; places with no price are listed in
    unknown and left out of the total. Child and senior prices are not applied. Use it for "đi mấy chỗ này hết bao nhiêu"."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "estimate_cost"

    ids: list[str] = Field(min_length=1, max_length=10, description="Place ids or names.")
    people: int = Field(ge=1, le=50, description="How many people pay.")
    nights: int | None = Field(None, ge=1, le=30, description="Nights, for lodging in ids.")
    check_in: str | None = Field(None, pattern=DATE, description="Check-in day YYYY-MM-DD, to use a crawled price for those dates.")


@read_tool(EstimateCost, group="cost")
def estimate_cost(turn, inp: EstimateCost) -> dict:
    return turn.knowledge.more.cost(_many(turn, inp.ids), inp.people, inp.nights, inp.check_in, turn.state)


# ---------- 5.6 local advice and safety ----------

class LocalTips(BaseModel):
    """Local advice for a place and/or a topic: best and worst time, access, what to bring, warnings (touts, cash only,
    night road), and local claims from web documents. Each tip says where it comes from; label reference = say it as
    "tham khảo", not as a fact. Use it for "đi Langbiang cần lưu ý gì", "có bị chặt chém không"."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "local_tips"

    place_id: str | None = Field(None, description="A place id or name.")
    topic: str | None = Field(None, max_length=80, description=(
        "A kind of advice (tip, notice, access, avoid, best_time, price_norm, crowded_at, if_rain) or free words "
        "(\"gửi xe\", \"chặt chém\")."))
    month: int | None = Field(None, ge=1, le=12, description="Only advice for this month.")


@read_tool(LocalTips, group="tips", place_args=("place_id",))
def local_tips(turn, inp: LocalTips) -> dict:
    return turn.knowledge.more.tips(inp.place_id, inp.topic, turn.state, inp.month)


class AreaNotice(BaseModel):
    """Whether a place lies inside a restricted area (military land, no-access land) on the map data. "none_listed" does
    not prove it is open to visit; "unknown" means the map was not built. Use it for "chỗ này có cấm vào không"."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "area_notice"

    id: str = Field(description="A place id or name.")


@read_tool(AreaNotice, group="tips", place_args=("id",))
def area_notice(turn, inp: AreaNotice) -> dict:
    return turn.knowledge.more.area(inp.id)


# ---------- 5.7 actions in the trip ----------

class SavePlace(BaseModel):
    """Save a place the user liked ("lưu quán này lại"): the same as their Thích button, a want in the trip. Only a place
    shown in this chat."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "save_place"

    id: str = Field(description="A place id or name shown in this chat.")


@action_tool("trip", SavePlace, requires="assistant")
def save_place(turn, inp: SavePlace) -> dict:
    pid = _one(turn, inp.id)
    if pid not in turn.told_ids | set(turn.state.meta.shown_ids):
        raise ValueError("save only a place shown in this chat")
    st = turn.state
    if any(a.place_id == pid for a in st.anchors):
        return {"ok": True, "note": "already in the trip"}
    anchor = Anchor(text=turn.catalog.by_id[pid].name, place_id=pid, state="matched", priority="want")
    turn.state = settle(st.model_copy(update={"anchors": (*st.anchors, anchor)}))
    if turn.on_state is not None:
        turn.on_state(turn.state)
    return {"ok": True, "saved": turn.catalog.by_id[pid].name}


class HidePlace(BaseModel):
    """Stop suggesting a place in this trip ("đừng gợi ý quán này nữa"). It only hides the place here: it is not a dislike
    and nothing is learned from it unless the user says why. undo true shows it again."""
    model_config = ConfigDict(extra="forbid")
    tool_name: ClassVar[str] = "hide_place"

    id: str = Field(description="A place id or name.")
    undo: bool = Field(False, description="true = show the place again.")


@action_tool("trip", HidePlace, requires="assistant")
def hide_place(turn, inp: HidePlace) -> dict:
    pid = _one(turn, inp.id)
    hidden = turn.state.meta.hidden_ids
    kept = tuple(x for x in hidden if x != pid)
    new = kept if inp.undo else (*kept, pid)
    turn.state = with_meta(turn.state, hidden_ids=new[-200:])
    return {"ok": True, "hidden": not inp.undo, "n": turn.catalog.by_id[pid].name}
