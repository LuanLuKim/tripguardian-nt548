import pytest
from fixtures import si, srec

from decision.curation import ActionError, apply, pending
from decision.session import Chip, Drop, Pending, State
from decision.settings import default

CFG = default()
KNOWN = {"A", "B", "C", "D", "E", "F", "G"}


def act(state, a, alternatives=None, pend=None):
    return apply(state, a, KNOWN.__contains__, alternatives or {}, pend, CFG)


def test_select_lock_unlock_drop_and_reasons_update_profile():
    s = act(State(), {"type": "select", "place_id": "A"})
    s = act(s, {"type": "lock", "place_id": "B"})
    assert s.selected == ["A", "B"] and s.locked == ["B"]
    s = act(s, {"type": "unlock", "place_id": "B"})
    assert s.locked == [] and s.selected == ["A", "B"]
    s = act(s, {"type": "drop", "place_id": "A", "reason": "far"})
    s = act(s, {"type": "drop", "place_id": "C", "reason": "crowded"})
    s = act(s, {"type": "drop", "place_id": "D", "reason": "pricey"})
    s = act(s, {"type": "drop", "place_id": "E", "reason": "visited"})
    assert s.selected == ["B"] and [d.place_id for d in s.dropped] == ["A", "C", "D", "E"]
    assert s.profile.travel_mult == CFG.far_step and s.profile.crowd_tolerance == "avoid"
    assert s.profile.price_sensitivity == CFG.price_step and s.profile.visited == ["E"]
    s = act(s, {"type": "select", "place_id": "A"})
    assert "A" not in [d.place_id for d in s.dropped] and s.last == "select"


def test_original_state_is_not_changed():
    s = State()
    act(s, {"type": "select", "place_id": "A"})
    assert s.selected == []


def test_swap_relax_wishlist_feedback_prefer_note():
    s = act(State(selected=["A"]), {"type": "swap", "place_id": "A", "with_id": "B"}, alternatives={"A": ["B"]})
    assert s.selected == ["B"] and s.dropped == [Drop(place_id="A", reason=None)]
    s = act(s, {"type": "relax", "place_id": "B", "feature": "steep_or_stairs"})
    s = act(s, {"type": "wishlist", "place_id": "B"})
    assert s.relaxed == [("B", "steep_or_stairs")] and s.wishlist == ["B"] and s.selected == []
    s = act(s, {"type": "feedback", "reason": "far"})
    s = act(s, {"type": "prefer", "feature": "noise", "value": "quiet", "weight": 1})
    s = act(s, {"type": "note", "phrase": "nhạc nhẹ"})
    assert s.profile.travel_mult == CFG.far_step and s.profile.soft[0].feature == "noise" and s.unmapped == ["nhạc nhẹ"]


@pytest.mark.parametrize("a", [
    {"type": "select", "place_id": "nope"},
    {"type": "drop", "place_id": "A", "reason": "ugly"},
    {"type": "swap", "place_id": "A", "with_id": "C"},
    {"type": "relax", "place_id": "A"},
    {"type": "feedback", "reason": "dislike"},
    {"type": "prefer", "feature": "noise", "value": "purple", "weight": 1},
    {"type": "answer", "qid": "rethink", "chip": "back"},
    {"type": "explode"},
])
def test_bad_actions_raise(a):
    with pytest.raises(ActionError):
        act(State(selected=["A"]), a, alternatives={"A": ["B"]})


def test_pattern_never_opens_but_legacy_explicit_answer_still_works():
    by_id = {k: srec(k, features={"crowd": "high"}) for k in "ABC"}
    s = State(dropped=[Drop(place_id=k) for k in "ABC"], last="drop")
    assert pending(s, by_id, si(), {"slack": 0}, 20, {}, CFG) is None
    p = Pending(qid="pattern:crowd=high", text="legacy", reason="legacy",
                chips=[Chip(id="yes", label="Yes"), Chip(id="no", label="No")])
    s2 = act(s, {"type": "answer", "qid": p.qid, "chip": "yes"}, pend=p)
    assert (s2.profile.soft[0].feature, s2.profile.soft[0].value, s2.profile.soft[0].weight) == ("crowd", "high", -1)
    assert pending(s2, by_id, si(), {"slack": 0}, 20, {}, CFG) is None
    s3 = act(s, {"type": "answer", "qid": p.qid, "chip": "no"}, pend=p)
    assert s3.profile.soft == [] and pending(s3, by_id, si(), {"slack": 0}, 20, {}, CFG) is None


def test_dropping_never_opens_rethink_or_gap_question():
    by_id = {k: srec(k) for k in KNOWN}
    many = State(dropped=[Drop(place_id=k) for k in "ABCDEF"], last="drop")
    assert pending(many, by_id, si(), {"slack": 0}, 10, {}, CFG) is None
    one = State(dropped=[Drop(place_id="A")], last="drop")
    gap = pending(one, by_id, si(), {"slack": 200}, 10, {"A": "nature"}, CFG)
    assert gap is None
    with pytest.raises(ActionError):
        act(one, {"type": "answer", "qid": "gap:1", "chip": "similar"})
    assert pending(State(dropped=[Drop(place_id="A")], last="select"), by_id, si(), {"slack": 200}, 10, {}, CFG) is None
    assert pending(one, by_id, si(), {"slack": None}, 10, {}, CFG) is None


def test_filter_unfilter_and_like():
    s = act(State(), {"type": "filter", "key": "opens_by", "value": "07:00"})
    s = act(s, {"type": "filter", "key": "kids", "value": "suitable"})
    s = act(s, {"type": "filter", "key": "kids", "value": "suitable"})
    assert s.filters == [("opens_by", "07:00"), ("kids", "suitable")] and s.last == "filter"
    assert act(s, {"type": "unfilter"}).filters == []
    s = act(s, {"type": "like", "place_id": "A"})
    s = act(s, {"type": "like", "place_id": "A"})
    assert s.likes == ["A"]


@pytest.mark.parametrize("a", [
    {"type": "filter", "key": "opens_by", "value": "7h"},
    {"type": "filter", "key": "opens_by", "value": "24:00"},
    {"type": "filter", "key": "noise", "value": "purple"},
    {"type": "filter", "key": "nope", "value": "x"},
    {"type": "like", "place_id": "nope"},
])
def test_bad_filter_or_like_raise(a):
    with pytest.raises(ActionError):
        act(State(), a)
