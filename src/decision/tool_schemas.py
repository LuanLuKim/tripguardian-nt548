"""Input models of the Lựa chọn chatbot's action tools (docs/PLACE_DECISION.md §Trợ lý). Each class docstring is the
text the model reads; fields are its schema. `quote` is words of the user's own message: the tool refuses a quote that is
not in it. `place` is an alias on the screen (P1), a place id, or the place's name."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

QUOTE = "Words of the user's message that ask for this, copied exactly."
PLACE = "A place of the screen or of a tool result: its alias (P3), id or name."


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SelectPlace(Strict):
    """Put ONE place into the user's trip. Only when the user named it or pointed at it ("lấy quán này", "chọn quán đầu",
    "thêm Cà Phê Muối"). Never pick for the user."""
    tool_name: ClassVar[str] = "select"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)


class DropPlace(Strict):
    """Take ONE place out of the list ("bỏ quán này", "quán này xa quá, bỏ đi"). reason only when the user gave it:
    far, crowded, pricey, dislike."""
    tool_name: ClassVar[str] = "drop"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)
    reason: Literal["far", "crowded", "pricey", "dislike"] | None = Field(None, description="Why, when the user said.")


class LockPlace(Strict):
    """Lock ONE place so the plan keeps it ("chốt quán này", "khóa nơi này"). Only when the user named or pointed at it."""
    tool_name: ClassVar[str] = "lock"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)


class VisitedPlace(Strict):
    """The user has already been to ONE place ("quán này đi rồi", "tới đây rồi"). It leaves the list; it is not a dislike."""
    tool_name: ClassVar[str] = "visited"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)


class LikePlace(Strict):
    """The user likes ONE place and wants its kind ranked higher ("thích quán này", "mình mê chỗ đó"). Lifts places
    that look like it; removes nothing."""
    tool_name: ClassVar[str] = "like"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)


class MoreLikePlace(Strict):
    """The user asks for MORE places of the kind of one place ("kiếm thêm kiểu quán thứ hai", "thêm chỗ giống đó").
    Lifts look-alikes; the result names the places that moved up. Do not call `like` for the same place too."""
    tool_name: ClassVar[str] = "more_like"
    place: str = Field(description=PLACE)
    quote: str = Field(description=QUOTE)


class Wish(Strict):
    feature: str = Field(description="An ontology feature id from FEATURES.")
    value: str = Field(description="One of that feature's values.")
    avoid: bool = Field(False, description="True when the user wants places WITHOUT it.")


class Rerank(Strict):
    """Change how the lists are ranked from a taste the user just said ("ưu tiên quán yên tĩnh, có chỗ đỗ ô tô", "gần
    hơn", "đỡ đắt hơn"). wishes = ontology features (FEATURES) wanted or avoided; feedback = far (closer), crowded
    (quieter), pricey (cheaper). The result names the places that entered or left the top of each tab. A taste with no
    feature in FEATURES: say it cannot be ranked, do not invent one."""
    tool_name: ClassVar[str] = "rerank"
    quote: str = Field(description=QUOTE)
    wishes: list[Wish] = Field(default_factory=list, max_length=6)
    feedback: list[Literal["far", "crowded", "pricey"]] = Field(default_factory=list, max_length=3)


class FilterList(Strict):
    """Narrow the lists to places that match ("chỉ xem quán mở trước 7h", "chỉ quán có chỗ đỗ ô tô"). feature is
    `opens_by` with value HH:MM, or an ontology feature id from FEATURES with one of its values. Hidden places can come
    back with `unfilter`."""
    tool_name: ClassVar[str] = "filter"
    feature: str = Field(description="`opens_by` or an ontology feature id.")
    value: str
    quote: str = Field(description=QUOTE)


class Unfilter(Strict):
    """Remove every filter ("bỏ lọc", "cho xem lại hết")."""
    tool_name: ClassVar[str] = "unfilter"
    quote: str = Field(description=QUOTE)


class WhyNot(Strict):
    """Why ONE place is not in the lists, or where it is ("sao không thấy Cà Phê Muối"). Changes nothing."""
    tool_name: ClassVar[str] = "why_not"
    place: str = Field(description=PLACE)


class ComparePlaces(Strict):
    """Compare 2 or 3 places of the same kind with their table of differences and what choosing one costs the trip ("so
    hai quán này"). Aspects without evidence on both sides are not in the table: say they are unknown. Changes nothing."""
    tool_name: ClassVar[str] = "compare"
    places: list[str] = Field(min_length=2, max_length=3, description="2-3 places: alias, id or name.")


class GroupList(Strict):
    """Group ONE tab's list by kind ("trong tab ăn uống có những kiểu nào?", "chia nhóm giúp mình cho dễ chọn"). Returns
    the kinds with how many places each holds and a few example places; say them in one or two sentences with the labels
    and let the user choose, do not pick. Only for a long tab; no groups in the result = the list does not split into
    clear kinds, say so. Changes nothing."""
    tool_name: ClassVar[str] = "group_list"
    tab: str = Field(description="A tab of the screen: its label (as in CURRENT CONTEXT places) or its id.")


class TripWish(Strict):
    """The user changes WHAT the trip is, not the list: mood, pace, who goes, days, budget ("chuyến này muốn chill hơn",
    "đi thêm một ngày"). Trip Understanding reads the words and rebuilds the lists; do not say the list has changed."""
    tool_name: ClassVar[str] = "trip"
    texts: list[str] = Field(min_length=1, max_length=4, description="Each is words of the user's message, copied exactly.")


class SwapSuggest(Strict):
    """Alternatives for ONE chosen or listed place ("đổi quán này lấy chỗ khác tương tự"): places of the same role that
    passed the hard rules. Changes nothing; the user picks."""
    tool_name: ClassVar[str] = "swap_suggest"
    place: str = Field(description=PLACE)


class Undo(Strict):
    """Undo the last change ("hoàn tác", "quay lại như trước"). Use it alone in a turn."""
    tool_name: ClassVar[str] = "undo"
    quote: str = Field(description=QUOTE)
