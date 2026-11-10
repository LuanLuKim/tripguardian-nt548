"""Input models of the Lịch trình chatbot's tools (docs/PLANNING.md §Trợ lý). Each class docstring is the text the model
reads; fields are its schema. `quote` is words of the user's own message: a tool refuses a quote that is not in it.
`place` is an alias on the screen (P3), a place id, or the place's name. Days are the numbers the user sees (1 = first)."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

QUOTE = "Words of the user's message that ask for this, copied exactly."
PLACE = "A stop of the plan or a place of a tool result: its alias (P3), id or name."
DAY = "Day number as the user sees it: 1 is the first day."


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- reads ----------

class ReadPlan(Strict):
    """Read the plan as it is now: each day's stops with start and end times, travel minutes, the lodging, totals and the
    plan's warnings. Call it before you describe the plan; CURRENT CONTEXT only has the headline."""
    tool_name: ClassVar[str] = "plan"
    day: int | None = Field(None, description="One day only; leave out for every day.")


class ReadStop(Strict):
    """One stop of the plan: its day, times, the trip from the stop before it, how well its hours fit, whether the user
    locked it and what role it has (anchor, locked, chosen)."""
    tool_name: ClassVar[str] = "stop"
    place: str = Field(description=PLACE)


class WhyHere(Strict):
    """Why a place is on this day, or why it is not in the plan: the user's lock, a required role, the layout reason,
    or the reason the plan left it out. Only what the data says."""
    tool_name: ClassVar[str] = "why_here"
    place: str = Field(description=PLACE)


class Diagnostics(Strict):
    """What is wrong or fragile in the plan now: violations (hours, overlap, long legs, budget, day window), how robust it
    is to delays, how well each stop fits its time of day, weather and crowd notes. Use it to answer 'plan có ổn không'."""
    tool_name: ClassVar[str] = "diagnostics"


class Options(Strict):
    """The plan options on offer: the main plan, or when the picks do not fit the days, the fixed trade-offs (drop order)
    with what each keeps and drops. The user chooses; do not choose for them."""
    tool_name: ClassVar[str] = "options"


class SparePlaces(Strict):
    """Places that can still be added to the plan: backups, places the plan left out, suggestions for free slots, with the
    day or slot each fits. Use it when the user asks for more to do or a replacement."""
    tool_name: ClassVar[str] = "spare_places"


class PreviewEdit(Strict):
    """Try one edit WITHOUT saving it: what changes in the minutes and the violations, whether the plan stays confirmable,
    and which places would have to leave. Use it for 'nếu... thì sao', before an edit that may not fit."""
    tool_name: ClassVar[str] = "preview_edit"
    kind: Literal["move", "swap", "add", "remove"]
    place: str = Field(description=PLACE)
    day: int | None = Field(None, description=DAY + " Needed for move and add.")
    with_place: str | None = Field(None, description="For swap: the place that takes its slot. " + PLACE)


class LocalFacts(Strict):
    """Facts a local would check against the plan, from the data only: flower seasons, events, holidays, weather the data
    trusts (doubtful figures are marked) and kept local claims. Use it for 'ngày đó có gì đặc biệt không'."""
    tool_name: ClassVar[str] = "local_facts"


# ---------- writes ----------

class MovePlace(Strict):
    """Move ONE stop to another day ("chuyển Langbiang sang ngày 2"). The engine lays the days out again."""
    tool_name: ClassVar[str] = "move_place"
    place: str = Field(description=PLACE)
    day: int = Field(description=DAY)
    quote: str = Field(description=QUOTE)


class ReorderDay(Strict):
    """Set the order of ONE day's stops ("đi A trước B", "để chợ đêm cuối ngày"). `order` lists every stop of that day, in the
    new order, exactly once."""
    tool_name: ClassVar[str] = "reorder_day"
    day: int = Field(description=DAY)
    order: list[str] = Field(description="Every stop of the day (alias, id or name) in the new order.")
    quote: str = Field(description=QUOTE)


class SwapPlace(Strict):
    """Replace ONE stop by another place ("đổi quán này lấy chỗ khác"). The new place comes from spare_places or the
    user's own words; it takes the day of the stop it replaces."""
    tool_name: ClassVar[str] = "swap_place"
    place: str = Field(description="The stop to take out. " + PLACE)
    with_place: str = Field(description="The place that takes its slot. " + PLACE)
    quote: str = Field(description=QUOTE)


class AddPlace(Strict):
    """Add ONE place to a day ("thêm chỗ đó vào ngày 2"). The place must come from spare_places (backup or suggestion).
    A place the user names that is not there cannot be added on this screen: tell them to pick it in Lựa chọn (the
    plan is rebuilt with it, through the same checks)."""
    tool_name: ClassVar[str] = "add_place"
    place: str = Field(description=PLACE)
    day: int = Field(description=DAY)
    quote: str = Field(description=QUOTE)


class RemovePlace(Strict):
    """Take ONE stop out of the plan ("bỏ chỗ này"). reason only when the user gave it: far, crowded, pricey, dislike, visited."""
    tool_name: ClassVar[str] = "remove_place"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)
    reason: Literal["far", "crowded", "pricey", "dislike", "visited"] | None = Field(None, description="Why, when the user said.")


class LockPlace(Strict):
    """Pin ONE stop to its day so no later edit moves or drops it ("giữ chỗ này ở ngày 1", "chốt quán này")."""
    tool_name: ClassVar[str] = "lock_place"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)


class UnlockPlace(Strict):
    """Release the pin of ONE stop ("mở khóa chỗ này")."""
    tool_name: ClassVar[str] = "unlock_place"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)


class SetPace(Strict):
    """Change the pace of the whole trip: slow (đi chậm, ít nơi mỗi ngày), normal, packed (dày hơn). The days are laid out again."""
    tool_name: ClassVar[str] = "set_pace"
    level: Literal["slow", "normal", "packed"]
    quote: str = Field(description=QUOTE)


class SetDayWindow(Strict):
    """Change when ONE day starts and ends ("ngày 2 bắt đầu 9h, về lúc 17h"). start and end are HH:MM."""
    tool_name: ClassVar[str] = "set_day_window"
    day: int = Field(description=DAY)
    start: str = Field(description="HH:MM")
    end: str = Field(description="HH:MM")
    quote: str = Field(description=QUOTE)


class SetStopTime(Strict):
    """Set the exact start time of ONE stop ("đổi Horizon sang 15:00"). start is HH:MM; this does NOT change
    the day's window or departure. The time is kept even when it breaks a rule: the result says what is now flagged
    (and the stop's real start if the layout could not put it exactly there); say it plainly and offer undo."""
    tool_name: ClassVar[str] = "set_stop_time"
    place: str = Field(description=PLACE)
    start: str = Field(description="Exact start in HH:MM, 00:00 through 23:59.")
    quote: str = Field(description=QUOTE)


class SetVisitMinutes(Strict):
    """Change how long the user stays at ONE stop ("ở Langbiang 2 tiếng"). minutes within the range CURRENT CONTEXT gives."""
    tool_name: ClassVar[str] = "set_visit_minutes"
    place: str = Field(description=PLACE)
    minutes: int
    quote: str = Field(description=QUOTE)


class ExtendDays(Strict):
    """Make every day start earlier (side=start) or end later (side=end) by the same minutes, so every pick fits again — the
    overload card's 'giữ đủ' choice. Only when the user asked for longer days."""
    tool_name: ClassVar[str] = "extend_days"
    side: Literal["start", "end"]
    minutes: int
    quote: str = Field(description=QUOTE)


class PickOption(Strict):
    """Choose one of the plan options from `options` ("lấy hướng ít đi lại"). Only the id `options` returned."""
    tool_name: ClassVar[str] = "pick_option"
    id: str
    quote: str = Field(description=QUOTE)


class Undo(Strict):
    """Take back the last change ("hoàn tác", "quay lại như trước"). Alone in a turn; it takes back everything the last
    typed message did."""
    tool_name: ClassVar[str] = "undo_turn"
    quote: str = Field(description=QUOTE)


# ---------- lodging and priority ----------

class LodgingOptions(Strict):
    """The stay of the plan and the stays on offer for it: each with its id, name, night price (dated for the trip's
    nights or a Maps reference price, with its date), travel minutes to the trip's places and what reviewers confirmed.
    Use it for "chỗ ở nào gần hơn / rẻ hơn", "đổi khách sạn". A stay the user booked themselves is kept unless they ask."""
    tool_name: ClassVar[str] = "lodging_options"
    max_per_night: int | None = Field(None, ge=0, description="Only stays at or under this price a night (VND).")


class PickLodging(Strict):
    """Make ONE stay from lodging_options the plan's lodging ("lấy khách sạn đó", "đổi sang homestay thứ hai"); the
    days are laid out again from it. Only an id lodging_options returned."""
    tool_name: ClassVar[str] = "pick_lodging"
    id: str = Field(description="The stay's id from lodging_options.")
    quote: str = Field(description=QUOTE)


class SetLodgingBudget(Strict):
    """Set the most the user pays a night for the stay ("chỗ ở dưới 800k một đêm"); the stays on offer are filtered
    by it. Leave max_per_night out to remove the limit."""
    tool_name: ClassVar[str] = "set_lodging_budget"
    max_per_night: int | None = Field(None, ge=0, description="VND a night, as the user said it.")
    quote: str = Field(description=QUOTE)


class SetPriority(Strict):
    """What the plan should favour when it lays the days out ("xếp sao cho ít đi lại", "ưu tiên rẻ", "trời mưa vẫn đi
    được"): least_travel, low_cost, weather_robust, diverse, preference_fit. It changes the order and split of the days,
    never which rules are checked."""
    tool_name: ClassVar[str] = "set_priority"
    priority: Literal["least_travel", "low_cost", "weather_robust", "diverse", "preference_fit"]
    quote: str = Field(description=QUOTE)
