"""Place cards and quick replies in the chat, the Thích tap (plan 2026-10-28-trip-decision-chatbot Task 5, §B.4)."""

import pytest
from trip_fixtures import ScriptedChat, call, reply, say

from trip.api.engine import TurnInput

CAFE = "Cà Phê Đồi Thông Xanh"


def run_turn(engine, text):
    sid = engine.create("first", "nothing")["id"]
    events = []
    engine.turn(sid, TurnInput(kind="text", text=text), lambda e, d: events.append((e, d)))
    return engine.store.get(sid), events


def show_first_hit():
    # with the assistant on a turn has two calls: the tools in the first, the reply in the second (offered no tool)
    return ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]}),
                              call("show_places", ids=["0xa:0x1"], why="view đồi thông"),
                              call("quick_replies", options=["Thêm quán nữa", "Quán yên tĩnh"])),
                        say(f"Bạn thử {CAFE} nhé."))


def test_show_places_refuses_unseen_id(turn_tools):
    t = turn_tools(assistant=True)
    assert "error" in t.run("show_places", {"ids": ["nope"], "why": "x"})
    t.run("find_places", {"criteria": {"groups": ["cafe"]}})
    assert "error" not in t.run("show_places", {"ids": ["0xa:0x1"], "why": "view"})


def test_quick_replies_bounds(turn_tools):
    t = turn_tools(assistant=True)
    assert "error" in t.run("quick_replies", {"options": ["chỉ một"]})
    assert "error" in t.run("quick_replies", {"options": ["a", "x" * 41]})
    assert "error" not in t.run("quick_replies", {"options": ["Có", "Không"]})


def test_display_tools_only_with_the_assistant(turn_tools):
    assert "show_places" not in turn_tools(assistant=False).tool_names()


def test_places_message_persists_and_reloads(make_assistant):
    e = make_assistant(show_first_hit())
    s, events = run_turn(e, "Gợi ý quán cà phê view đồi")
    msg = next(t for t in s.transcript if t.get("kind") == "places")
    # cards go out when find_places returns (card first): the whole ranked list; the curated words ride with it
    assert msg["ids"][0] == "0xa:0x1" and msg["why"] == "view đồi thông" and msg["tool"] == "find_places"
    assert len([d for ev, d in events if ev == "places"]) == 1
    places = next(d for ev, d in events if ev == "places")
    assert places["cards"][0]["name"] == CAFE and places["cards"][0]["liked"] is False
    assert next(d for ev, d in events if ev == "replies")["options"] == ["Thêm quán nữa", "Quán yên tĩnh"]
    loaded = e.load(s.id)
    assert any(m.get("kind") == "places" and m["cards"][0]["id"] == msg["ids"][0] for m in loaded["transcript"])
    assert any(m.get("kind") == "replies" and m["options"] == ["Thêm quán nữa", "Quán yên tĩnh"]
               for m in loaded["transcript"])


def test_place_view_fields_come_from_the_record(knowledge):
    v = knowledge.view("0xa:0x1")
    assert v["name"] == CAFE and v["category"] == "Quán cà phê" and v["rating"] is None and v["photos"] == []
    assert v["hours_today"] is not None and v["price"] is None and v["liked"] is False


@pytest.fixture
def shown_session(make_assistant):
    e = make_assistant(show_first_hit())
    s, _ = run_turn(e, "Gợi ý quán cà phê view đồi")
    return e, s


def test_like_writes_want_anchor_without_model(shown_session):
    e, s = shown_session
    pid = s.state.meta.shown_ids[0]
    calls = e.chat.calls
    e.turn(s.id, TurnInput(kind="like", target=pid, value="on"), lambda *a: None)
    after = e.store.get(s.id).state
    assert any(a.priority == "want" and a.place_id == pid for a in after.anchors) and e.chat.calls == calls
    card = next(m for m in e.load(s.id)["transcript"] if m.get("kind") == "places")["cards"][0]
    assert card["liked"] is True
    e.turn(s.id, TurnInput(kind="like", target=pid, value="off"), lambda *a: None)
    assert not any(a.place_id == pid for a in e.store.get(s.id).state.anchors)


def test_like_refuses_an_unshown_place(shown_session):
    e, s = shown_session
    with pytest.raises(ValueError):
        e.turn(s.id, TurnInput(kind="like", target="0xe:0x1", value="on"), lambda *a: None)


def test_old_transcript_without_places_loads(make_assistant):
    e = make_assistant(ScriptedChat(say("Chào bạn.")))
    s, _ = run_turn(e, "Chào")
    assert all(m.get("kind") != "places" for m in e.load(s.id)["transcript"])


def test_places_the_reply_names_become_cards_without_a_call(make_assistant):
    e = make_assistant(ScriptedChat(say(f"Bạn thử {CAFE} nhé.")))
    s, events = run_turn(e, "Gợi ý quán cà phê view đồi")
    msg = next(t for t in s.transcript if t.get("kind") == "places")
    assert msg["ids"][0] == "0xa:0x1" and e.chat.calls == 1  # the named place leads its search's ranked list


def test_more_than_three_good_places_become_more_than_three_cards(make_assistant):
    e = make_assistant(ScriptedChat(say(f"Bạn thử {CAFE} nhé.")))
    s, _ = run_turn(e, "Gợi ý quán cà phê view đồi")
    msg = next(t for t in s.transcript if t.get("kind") == "places")
    assert len(msg["ids"]) > 3 and msg["ids"][0] == "0xa:0x1"  # the ranked list of the prepared search, best first
    best_first = [p["id"] for p in e.knowledge.find({"text": "Gợi ý quán cà phê view đồi"}, s.state)["places"]]
    assert msg["ids"] == best_first[:len(msg["ids"])]  # score order
    assert "0xf:0x1" in best_first and "0xf:0x1" not in msg["ids"]  # 10 voices: under 0.6 x the best score


def test_dish_block_carries_menu_evidence_and_persists(make_assistant):
    e = make_assistant(ScriptedChat(reply(call("find_dishes", dish="bánh căn")), say("Có quán nhé.")))
    e.catalog.dishes = lambda q: [{"id": "0xa:0x1", "name": CAFE, "score": 9, "evidence": [
        {"source": "review_order", "dish": "Bánh căn", "n": 3, "quote": "bánh căn giòn"},
        {"source": "menu", "dish": "Bánh căn", "section": "Món chính"}]}]
    e.catalog._dish_records()  # noqa: SLF001
    s, events = run_turn(e, "ăn bánh căn ở đâu")
    block = next(d for ev, d in events if ev == "block")
    assert block["kind"] == "dish" and block["dish"] == "bánh căn"
    ev = block["places"][0]["evidence"]
    assert ev[0]["source"] == "menu" and ev[1]["quote"] == "bánh căn giòn" and block["cards"][0]["id"] == "0xa:0x1"
    assert any(m.get("kind") == "block" and m["block"]["kind"] == "dish" for m in e.load(s.id)["transcript"])


def _dish_hit():
    return [{"id": "0xa:0x1", "name": CAFE, "score": 9, "evidence": [
        {"source": "menu", "dish": "Bánh căn", "section": "Món chính"},
        {"source": "review_order", "dish": "Bánh căn", "n": 3, "quote": "bánh căn giòn"}]}]


def test_dish_block_comes_from_the_prepared_lookup_when_the_model_never_calls_find_dishes(make_assistant):
    """QA B2: the model answers a dish question from the prepared data (find_places), so no find_dishes call and no
    block. The dish the corpus lookups found in the message is shown with its evidence anyway."""
    e = make_assistant(ScriptedChat(reply(call("find_places", criteria={"text": "bánh căn"})), say(f"Bạn thử {CAFE} nhé.")))
    e.catalog.dishes = lambda q: _dish_hit() if q.strip().lower() == "bánh căn" else []
    s, events = run_turn(e, "ăn bánh căn ở đâu")
    block = next(d for ev, d in events if ev == "block")
    assert block["kind"] == "dish" and block["dish"] == "bánh căn" and block["places"][0]["id"] == "0xa:0x1"
    assert sum(1 for ev, _ in events if ev == "block") == 1
    assert any(m.get("kind") == "block" for m in e.load(s.id)["transcript"])


def test_dish_block_is_not_sent_twice_when_the_model_called_find_dishes(make_assistant):
    e = make_assistant(ScriptedChat(reply(call("find_dishes", dish="bánh căn")), say("Có quán nhé.")))
    e.catalog.dishes = lambda q: _dish_hit() if q.strip().lower() == "bánh căn" else []
    _, events = run_turn(e, "ăn bánh căn ở đâu")
    assert sum(1 for ev, _ in events if ev == "block") == 1


def test_services_block_hides_unknown_fields():
    from trip.api.blocks import services_block
    out = services_block({"anchor": "unknown (no lodging)", "found": 1, "sources": ["Google Maps"], "crawled": "2026-10-01",
                          "rows": [{"name": "ATM A", "kind": "ATM", "distance_km": 0.4, "address": "unknown", "phone": "0900", "website": "unknown"}]})
    assert out["rows"] == [{"name": "ATM A", "kind": "ATM", "distance_km": 0.4, "phone": "0900"}] and "anchor" not in out
    assert services_block({"rows": []}) is None
