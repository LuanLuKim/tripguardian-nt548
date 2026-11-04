"""Origin text survives the guarded agent boundary and scheduling handoff."""

from datetime import date

import pytest
from trip_fixtures import ScriptedChat, call, reply

from trip import TurnInput


@pytest.mark.parametrize("origin", ["TP.HCM", "Nha Trang", "Hà Nội", "Phường 1"])
def test_agent_origin_is_handed_off_without_invented_coordinates(make_assistant, origin):
    text = f"Mình xuất phát từ {origin}, đi Đà Lạt bằng xe máy"
    chat = ScriptedChat(reply(call("record_fact", facts=[
        {"field": "origin", "op": "set", "value": origin, "quote": origin, "how": "said"}
    ], say="Mình ghi nhận nơi xuất phát.")))
    engine = make_assistant(chat)
    engine.today = lambda: date(2026, 11, 3)
    sid = engine.create("first", "nothing")["id"]
    engine.turn(sid, TurnInput(kind="text", text=text), lambda *a: None)
    state = engine.store.get(sid).state
    assert state.origin.known
    assert state.origin.value.text == origin
    assert state.origin.value.lat is None and state.origin.value.lng is None
    assert not state.entry_point.known
    assert not state.exit_point.known
    assert state.origin.evidence[-1].quote == origin
    handoff = engine._compile(state)
    assert handoff.context.origin.text == origin
    assert handoff.context.origin.lat is None and handoff.context.origin.lng is None


def test_readback_includes_the_recorded_departure_city(make_assistant):
    chat = ScriptedChat(reply(call("record_fact", facts=[
        {"field": "origin", "op": "set", "value": "TP.HCM", "quote": "TP.HCM", "how": "said"}
    ], say="Mình ghi nhận nơi xuất phát.")))
    engine = make_assistant(chat)
    sid = engine.create("first", "nothing")["id"]
    engine.turn(sid, TurnInput(kind="text", text="Mình xuất phát từ TP.HCM"), lambda *a: None)
    state = engine.store.get(sid).state
    assert state.origin.known
    assert any("TP.HCM" in line["text"] and line["kind"] == "said"
               for line in engine._readback(state)["lines"])


@pytest.mark.parametrize("value", ["Hà Nội", '{"text":"TP.HCM","lat":10.8,"lng":106.7}'])
def test_agent_cannot_change_origin_words_or_supply_unverified_coordinates(make_assistant, value):
    chat = ScriptedChat(reply(call("record_fact", facts=[
        {"field": "origin", "op": "set", "value": value, "quote": "TP.HCM", "how": "said"}
    ], say="Ừ.")))
    engine = make_assistant(chat)
    sid = engine.create("first", "nothing")["id"]
    engine.turn(sid, TurnInput(kind="text", text="Mình đi từ TP.HCM"), lambda *a: None)
    assert not engine.store.get(sid).state.origin.known
