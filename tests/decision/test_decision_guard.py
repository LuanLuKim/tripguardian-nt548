import pytest

from decision.guard import PlanUpdate, TurnPlan, guard, names_in
from decision.policy import policy

ALIASES = {"P1": {"id": "A", "name": "Đồi Chè Cầu Đất"}, "P2": {"id": "B", "name": "Quán Mộc Lan Viên"}}
KEYS = [("doi che cau dat", "A"), ("quan moc lan vien", "B"), ("thac datanla dalat", "Z")]


def plan(*updates, say="Mình đã bỏ nơi đó."):
    return TurnPlan(say=say, updates=tuple(PlanUpdate(op=o, place=p, value=v, quote=q) for o, p, v, q in updates))


def test_names_in_full_or_last_two_words():
    assert names_in("bỏ cầu đất đi", "Đồi Chè Cầu Đất") and names_in("đồi chè cầu đất", "Đồi Chè Cầu Đất")
    assert not names_in("bỏ đồi chè", "Đồi Chè Cầu Đất")


def test_updates_become_actions():
    text = "Cầu Đất xa quá, thêm Lan Viên, muốn chỗ yên tĩnh, tìm chỗ có nhạc nhẹ"
    g = guard(plan(("drop", "P1", "far", "Cầu Đất xa quá"), ("select", "P2", "", "thêm Lan Viên"),
                   ("trip", "", "", "muốn chỗ yên tĩnh"), ("trip", "", "", "tìm chỗ có nhạc nhẹ"),
                   ("crowd", "", "", "chỗ yên tĩnh")), text, ALIASES, "", KEYS)
    assert g.actions == [{"type": "drop", "place_id": "A", "reason": "far"}, {"type": "select", "place_id": "B"},
                         {"type": "trip", "text": "muốn chỗ yên tĩnh"}, {"type": "trip", "text": "tìm chỗ có nhạc nhẹ"},
                         {"type": "feedback", "reason": "crowded"}]
    assert g.say == "Mình đã bỏ nơi đó." and g.log == []


def test_bad_updates_are_dropped_and_logged():
    text = "bỏ nơi thứ hai đi"
    g = guard(plan(("drop", "P9", "", "bỏ nơi thứ hai"), ("drop", "P1", "", "không có câu này"),
                   ("select", "P2", "", "bỏ nơi thứ hai"), ("drop", "", "", "bỏ nơi thứ hai"),
                   ("trip", "", "", "muốn yên tĩnh hơn")), text, ALIASES, "", KEYS)
    assert g.actions == [] and len(g.log) == 5



def test_trip_wish_becomes_a_trip_action_with_the_quoted_words():
    text = "mình không thích quán giống Cà Phê Số 1, muốn yên tĩnh hơn"
    g = guard(plan(("trip", "", "", "không thích quán giống Cà Phê Số 1"), ("trip", "", "", "muốn yên tĩnh hơn")),
              text, ALIASES, "", KEYS)
    assert g.actions == [{"type": "trip", "text": "không thích quán giống Cà Phê Số 1"},
                         {"type": "trip", "text": "muốn yên tĩnh hơn"}]


def test_trip_wish_with_a_quote_not_in_the_message_is_dropped():
    g = guard(plan(("trip", "", "", "thích cà phê sách")), "bỏ nơi thứ hai", ALIASES, "", KEYS)
    assert g.actions == []

def test_say_with_unseen_numbers_or_places_is_replaced():
    assert guard(plan(say="Còn 45 phút trống."), "bỏ đi", ALIASES, "", KEYS).say == ""
    assert guard(plan(say="Còn 45 phút trống."), "bỏ đi", ALIASES, "dư 45 phút", KEYS).say == "Còn 45 phút trống."
    assert guard(plan(say="Thử Thác Datanla Dalat nhé"), "bỏ đi", ALIASES, "", KEYS).say == ""
    assert guard(plan(say="Đồi Chè Cầu Đất đã bỏ"), "bỏ đi", ALIASES, "", KEYS).say == "Đồi Chè Cầu Đất đã bỏ"


def test_policy_keywords_and_names():
    assert policy("Cầu Đất xa quá", ALIASES)[0] == [{"type": "drop", "place_id": "A", "reason": "far"}]
    assert policy("Lan Viên mình đi rồi", ALIASES)[0] == [{"type": "drop", "place_id": "B", "reason": "visited"}]
    assert policy("muốn chỗ ít người hơn", ALIASES)[0] == [{"type": "feedback", "reason": "crowded"}]
    actions, say = policy("ừm", ALIASES)
    assert actions == [] and "chưa hiểu" in say


def test_select_needs_the_name_in_the_quote_not_just_the_message():
    text = "bỏ Quán Mộc Lan Viên đi, thêm Đồi Chè Cầu Đất"
    g = guard(plan(("select", "P2", "", "thêm")), text, ALIASES, "", KEYS)
    assert g.actions == [] and len(g.log) == 1


def test_select_by_a_two_word_tail_shared_by_several_places_is_refused():
    aliases = {"P1": {"id": "A", "name": "Thung Lũng Tình Yêu Đà Lạt"}}
    keys = [("thung lung tinh yeu da lat", "A"), ("ho tuyen lam da lat", "B")]
    g = guard(plan(("select", "P1", "", "thêm Đà Lạt")), "đi tour, thêm Đà Lạt", aliases, "", keys)
    assert g.actions == []
    ok = guard(plan(("select", "P1", "", "thêm Tình Yêu Đà Lạt")), "thêm Tình Yêu Đà Lạt", aliases, "", [keys[0]])
    assert ok.actions == [{"type": "select", "place_id": "A"}]


def test_guard_prefer_and_filter():
    text = "ưu tiên yên tĩnh, chỉ xem quán mở trước 7h"
    g = guard(plan(("prefer", "", "noise=quiet", "ưu tiên yên tĩnh"), ("filter", "", "opens_by=07:00", "chỉ xem quán mở trước 7h")),
              text, ALIASES, "", KEYS)
    assert {"type": "prefer", "feature": "noise", "value": "quiet", "weight": 1} in g.actions
    assert {"type": "filter", "key": "opens_by", "value": "07:00"} in g.actions and g.log == []


def test_guard_prefer_avoid_unfilter_and_like():
    text = "tránh chỗ ồn, bỏ lọc, kiếm quán giống Lan Viên"
    g = guard(plan(("prefer", "", "noise=loud:avoid", "tránh chỗ ồn"), ("unfilter", "", "", "bỏ lọc"),
                   ("like", "P2", "", "giống Lan Viên"), ("filter", "", "kids=suitable", "bỏ lọc")),
              text, ALIASES, "", KEYS)
    assert g.actions == [{"type": "prefer", "feature": "noise", "value": "loud", "weight": -1},
                         {"type": "unfilter"}, {"type": "like", "place_id": "B"},
                         {"type": "filter", "key": "kids", "value": "suitable"}]


@pytest.mark.parametrize("op,value", [("prefer", "noise=purple"), ("prefer", "nofeature=x"), ("prefer", "noise"),
                                      ("filter", "opens_by=25:99"), ("filter", "opens_by=7h"), ("filter", "noise=purple"),
                                      ("filter", "kids")])
def test_guard_drops_values_outside_the_ontology(op, value):
    g = guard(plan((op, "", value, "xin chào")), "xin chào", ALIASES, "", KEYS)
    assert g.actions == [] and len(g.log) == 1


def test_like_needs_a_known_place_and_say_may_use_numbers_of_the_data():
    g = guard(plan(("like", "", "", "giống Lan Viên")), "giống Lan Viên", ALIASES, "", KEYS)
    assert g.actions == [] and "needs a place" in g.log[0]
    data = '{"h": {"06:30-21:30": "mon"}}'
    assert guard(plan(say="Quán mở lúc 06:30."), "mấy giờ mở", ALIASES, data, KEYS).say == "Quán mở lúc 06:30."
    assert guard(plan(say="Quán mở lúc 05:45."), "mấy giờ mở", ALIASES, data, KEYS).say == ""
