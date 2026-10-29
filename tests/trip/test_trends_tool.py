"""The trends tool: the assistant reads the Nhịp Đà Lạt snapshot (docs/CORPUS.md §Nhịp); places pass the trip's hard filters."""

import pytest

from trip.domain.state import TripState

SNAPSHOT = {"as_of": "2026-10-29", "stale": False, "items": [
    {"kind": "hot", "name": "Cà Phê Đồi Thông Xanh", "place_id": "0xa:0x1", "text": "4 video mới trong 30 ngày, 4 tác giả khác nhau · mới nhất 27/10",
     "sources": [{"type": "tiktok_video", "label": "Video TikTok", "url": "https://t/1", "date": "2026-10-27"}]},
    {"kind": "hot", "name": "Quán Nhạc Ồn Ào", "place_id": "0xb:0x1", "text": "3 video mới", "sources": []},
    {"kind": "season", "name": "Dã quỳ", "place_id": None, "text": "Đang vào mùa Dã quỳ (tháng 10–12)", "sources": []}]}


@pytest.fixture
def with_trends(retrieval, served_catalog):
    from trip.infrastructure.knowledge import Knowledge
    calls = []

    def reader(**kw):
        calls.append(kw)
        return SNAPSHOT

    return Knowledge(retrieval, served_catalog, None, ("Chợ Đà Lạt", 11.9429, 108.4372), trends=reader), calls


def test_places_go_through_the_hard_filters_and_carry_their_id(with_trends, kids_hard_state):
    k, calls = with_trends
    out = k.trends(kids_hard_state, kind="hot", month=None)
    assert calls == [{"kind": "hot", "month": None, "limit": 3}]
    assert out["items"][0]["sources"] == [{"label": "Video TikTok", "date": "2026-10-27"}]  # no URL: its digits would flood told_numbers
    assert [i["name"] for i in out["items"]] == ["Cà Phê Đồi Thông Xanh", "Dã quỳ"]  # the unsuitable place is gone
    assert out["items"][0]["id"] == "0xa:0x1" and "id" not in out["items"][1] and "place_id" not in out["items"][0]
    assert out["as_of"] == "2026-10-29"


def test_no_snapshot_is_an_error_result_not_an_empty_trend(retrieval, served_catalog):
    from trip.infrastructure.knowledge import Knowledge
    k = Knowledge(retrieval, served_catalog, None, ("c", 0, 0), trends=lambda **kw: None)
    assert k.trends(TripState()) == {"error": "trends unavailable"}
    assert Knowledge(retrieval, served_catalog, None, ("c", 0, 0)).trends(TripState()) == {"error": "trends unavailable"}


def test_tool_is_offered_and_its_places_may_be_named(turn_tools, with_trends):
    t = turn_tools(assistant=True, know=with_trends[0])
    assert "trends" in t.tool_names()
    out = t.run("trends", {"kind": "hot"})
    assert out["items"][0]["id"] == "0xa:0x1"
    assert "0xa:0x1" in t.told_ids and {27, 29, 30}.issubset(t.told_numbers)
    assert "error" in t.run("trends", {"kind": "gossip"})
    assert "error" in t.run("trends", {"month": 13})


def test_tool_not_offered_without_the_assistant(turn_tools):
    assert "trends" not in turn_tools(assistant=False).tool_names()


def test_trend_words_prepare_the_trends_without_a_model_call(cfg, turn_tools, with_trends):
    from datetime import date
    from trip.agent.prefetch import covers, prepare, route
    r = route("Dạo này Đà Lạt có gì hot không?", [], cfg, ask=lambda *a: {})
    assert "trends" in r.groups
    t = turn_tools(assistant=True, know=with_trends[0])
    data = prepare(r, "Dạo này Đà Lạt có gì hot không?", TripState(), t, date(2026, 10, 29), 1.0)
    assert [i["name"] for i in data["xu_huong"]["items"]][0] == "Cà Phê Đồi Thông Xanh" and covers(r, data)
    assert with_trends[1][-1] == {"kind": None, "month": None, "limit": 3}
    ev = route("Có lễ hội nào sắp tới không", [], cfg, ask=lambda *a: {})
    prepare(ev, "Có lễ hội nào sắp tới không", TripState(), t, date(2026, 10, 29), 1.0)
    assert with_trends[1][-1]["kind"] == "event"
    assert "trends" not in route("Quán cà phê view đồi", [], cfg, ask=lambda *a: {}).groups
    assert not covers(r, {"xu_huong": {"error": "trends unavailable"}})


def test_current_context_is_not_a_second_system_message():
    """Measured 29/10 through 9router: a model given the context as a second system message answers "chưa có dữ liệu"
    with the trends in it; as a user message it reads them. Only the instructions are a system message."""
    import json
    from datetime import date
    from trip.agent.prompt import build_messages
    msgs = build_messages(TripState(), "Dạo này có gì hot?", [], None, date(2026, 10, 29), [], assistant=True,
                          data={"xu_huong": {"as_of": "2026-10-29", "items": []}})
    assert [m["role"] for m in msgs] == ["system", "user", "user"]
    ctx = json.loads(msgs[1]["content"].removeprefix("CURRENT CONTEXT\n"))
    assert ctx["data"]["xu_huong"]["as_of"] == "2026-10-29" and msgs[2]["content"] == "Dạo này có gì hot?"


def test_tiktok_and_standing_out_words_ask_for_trends(cfg):
    from trip.agent.prefetch import route
    assert "trends" in route("Có nơi nào đang nổi trên TikTok mà hợp đi buổi sáng không?", [], cfg, ask=lambda *a: {}).groups
