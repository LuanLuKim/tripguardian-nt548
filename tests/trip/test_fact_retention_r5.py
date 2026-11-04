"""Regressions from the production matrix, using scripted model boundaries only."""

from datetime import date

import pytest
from trip_fixtures import ScriptedChat, call, reply, say

from trip import TripState, TurnInput, prepass
from trip.domain.guard import record_fact


TODAY = date(2026, 11, 3)


@pytest.mark.parametrize("comment", ["Mà tụi mình hơi ngại chỗ đông quá, cuối tuần chắc đông lắm hen",
                                     "Cuối tuần chắc đông lắm, tụi mình muốn đi chợ đêm"])
def test_weekend_comment_does_not_replace_explicit_dates(make_assistant, comment):
    engine = make_assistant(ScriptedChat(say("Ừ."), say("Ừ.")))
    engine.today = lambda: TODAY
    sid = engine.create("first", "nothing")["id"]
    for text in ("Tụi mình 2 người đi 21-22/11 qua đêm, chạy xe máy từ Sài Gòn",
                 comment):
        engine.turn(sid, TurnInput(kind="text", text=text), lambda *a: None)
    state = engine.store.get(sid).state
    assert state.start_date.value == date(2026, 11, 21)
    assert state.days.value == 2


@pytest.mark.parametrize("new_text,want", [
    ("Đổi sang cuối tuần này nhé", date(2026, 11, 7)),
    ("Mình đi cuối tuần sau nhé", date(2026, 11, 14)),
    ("Đổi sang 28/11 nhé", date(2026, 11, 28)),
])
def test_real_date_correction_still_wins(make_assistant, new_text, want):
    engine = make_assistant(ScriptedChat(say("Ừ."), say("Ừ.")))
    engine.today = lambda: TODAY
    sid = engine.create("first", "nothing")["id"]
    for text in ("Đi 21-22/11", new_text):
        engine.turn(sid, TurnInput(kind="text", text=text), lambda *a: None)
    assert engine.store.get(sid).state.start_date.value == want


def test_dated_meal_does_not_reset_trip_start(make_assistant):
    engine = make_assistant(ScriptedChat(say("Ừ."), say("Ừ.")))
    engine.today = lambda: TODAY
    sid = engine.create("first", "nothing")["id"]
    for text in ("Đi Đà Lạt 20-22/11", "Ngày 22/11 mẹ ăn chay cả ngày hôm đó"):
        engine.turn(sid, TurnInput(kind="text", text=text), lambda *a: None)
    assert engine.store.get(sid).state.start_date.value == date(2026, 11, 20)


@pytest.mark.parametrize("quote", ["22/11", "Ngày 22/11 mẹ ăn chay cả ngày hôm đó"])
def test_agent_cannot_use_a_meal_date_as_trip_start(make_assistant, served_catalog, quote):
    engine = make_assistant(ScriptedChat(say("Ừ.")))
    engine.today = lambda: TODAY
    original = "Đi Đà Lạt 20-22/11"
    state = engine._deterministic(TripState(), original, prepass(original, TODAY), 1)
    text = "Ngày 22/11 mẹ ăn chay cả ngày hôm đó"
    state, note = record_fact(state, "start_date", "set", "2026-11-22", quote, "said", text, 2, served_catalog)
    assert state.start_date.value == date(2026, 11, 20)
    assert note.startswith("refused:")


def test_available_halfday_on_one_date_is_one_trip_day():
    facts = prepass("Đi công tác Đà Lạt, 18/11 chỉ rảnh từ 2h chiều đến 7h tối, đi Grab", TODAY).proposals
    assert any(p.field == "days" and p.value == 1 for p in facts)


def test_agent_can_record_a_real_relative_date_correction_with_the_whole_quote(make_assistant, served_catalog):
    engine = make_assistant(ScriptedChat(say("Ừ.")))
    engine.today = lambda: TODAY
    original = "Đi 21-22/11"
    state = engine._deterministic(TripState(), original, prepass(original, TODAY), 1)
    text = "Đổi sang cuối tuần này nhé"
    state, note = record_fact(state, "start_date", "set", "2026-11-07", text, "said", text, 2, served_catalog)
    assert not note
    assert state.start_date.value == date(2026, 11, 7)


def test_agent_cannot_turn_weekend_comment_into_a_new_start(make_assistant, served_catalog):
    engine = make_assistant(ScriptedChat(say("Ừ.")))
    engine.today = lambda: TODAY
    text = "Đi 21-22/11"
    state = engine._deterministic(TripState(), text, prepass(text, TODAY), 1)
    state, note = record_fact(state, "start_date", "set", "2026-11-07", "cuối tuần", "said",
                              "cuối tuần chắc đông lắm", 2, served_catalog)
    assert state.start_date.value == date(2026, 11, 21)
    assert note.startswith("refused:")


@pytest.mark.parametrize("text,days", [
    ("Đi Đà Lạt 20-22/11. Ngày 22/11 mẹ ăn chay, hai ngày kia ăn bình thường", 3),
    ("Đi 20-22/11, mỗi ngày 2 chỗ", 3),
])
def test_partial_days_are_not_trip_duration(text, days):
    got = [p.value for p in prepass(text, TODAY).proposals if p.field == "days"]
    assert got == [days]


@pytest.mark.parametrize("text,count", [
    ("Mình và bạn đi Đà Lạt 21-22/11", 2),
    ("hai mẹ con đi Đà Lạt 14-15/11 bằng ô tô", 2),
    ("Hai anh em đi Đà Lạt 25-26/11 bằng xe máy", 2),
    ("Mình và bạn đi cùng gia đình, tổng 4 người", 4),
])
def test_explicit_pair_count_is_not_lost(text, count):
    assert any(p.field == "people" and p.value == count and not p.inferred
               for p in prepass(text, TODAY).proposals)


@pytest.mark.parametrize("text", ["Mình và bạn bè đi Đà Lạt", "Mình và bạn cùng với mẹ đi Đà Lạt",
                                  "hai mẹ con và bà ngoại đi Đà Lạt", "Không đi với hai anh em"])
def test_pair_phrases_do_not_under_count_a_larger_or_negated_party(text):
    assert not any(p.field == "people" for p in prepass(text, TODAY).proposals)


@pytest.mark.parametrize("field,value,quote", [("companions", "partner", "vợ chồng"),
                                                ("companions", "solo", "một mình"),
                                                ("companions", "coworkers", "team building"),
                                                ("mobility", "motorbike", "xe máy"),
                                                ("pace", "slow", "nhịp chậm")])
def test_supported_frame_fact_records_and_removes_its_gate_input(served_catalog, tmp_path, field, value, quote):
    from trip.agent.tools import TurnTools
    from trip.domain.required import tabs
    from trip.infrastructure.settings import Settings

    tools = TurnTools(TripState(), quote, 1, served_catalog, TODAY, gaps=tmp_path / "gaps.jsonl")
    result = tools.run("record_fact", {"field": field, "op": "add" if field == "companions" else "set",
                                       "value": value, "quote": quote, "how": "said"})
    assert "error" not in result
    state = tools.state
    assert getattr(state, field).known
    missing = {t.qid: t.inputs for t in tabs(state, Settings())}
    if field == "companions":
        assert "who" not in missing.get("companions", ())
    else:
        assert field not in missing


@pytest.mark.parametrize("relation", ["Tụi mình 2 người", "Nhóm mình 8 người", "Tui đi Đà Lạt"])
def test_unknown_relationship_is_not_guessed(served_catalog, relation):
    for who in ("partner", "friends", "solo"):
        state, note = record_fact(TripState(), "companions", "add", who, relation, "said", relation, 1, served_catalog)
        assert not state.companions.known
        assert note.startswith("refused:")


def test_full_vnd_amount_and_scope_are_read():
    facts = prepass("500.000 đồng cho cả chuyến cháu nhé", TODAY).proposals
    assert any(p.field == "budget_vnd" and p.value == 500_000 for p in facts)
    assert any(p.field == "budget_scope" and p.value == "trip_total" for p in facts)


def test_arrival_and_departure_dates_give_trip_duration(make_assistant):
    import json
    facts = [{"field": field, "op": "set", "value": json.dumps({"at": at}), "quote": quote, "how": "said"}
             for field, at, quote in (("frame.arrive", "2026-11-20T21:30", "tới Đà Lạt 20/11"),
                                       ("frame.leave", "2026-11-21T09:00", "21/11 9h phải về"))]
    engine = make_assistant(ScriptedChat(reply(call("record_fact", facts=facts, say="Ừ."))))
    engine.today = lambda: TODAY
    sid = engine.create("first", "nothing")["id"]
    engine.turn(sid, TurnInput(kind="text", text="tới Đà Lạt 20/11, 21/11 9h phải về"), lambda *a: None)
    state = engine.store.get(sid).state
    assert state.start_date.value == date(2026, 11, 20)
    assert state.days.value == 2


def test_read_tool_does_not_end_turn_with_unrecorded_trip_hints(make_assistant):
    text = "Hai vợ chồng đi Đà Lạt 28-29/11 xe máy, muốn ghé cà phê"
    facts = [{"field": field, "op": op, "value": value, "quote": quote, "how": "said"}
             for field, op, value, quote in (("companions", "add", "partner", "vợ chồng"),
                                              ("mobility", "set", "motorbike", "xe máy"))]
    chat = ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]}), text="Bạn thử cà phê nhé."),
                        reply(call("record_fact", facts=facts, say="Mình ghi nhận.")))
    engine = make_assistant(chat)
    engine.today = lambda: TODAY
    sid = engine.create("first", "nothing")["id"]
    engine.turn(sid, TurnInput(kind="text", text=text), lambda *a: None)
    state = engine.store.get(sid).state
    assert state.companions.value == frozenset({"partner"}), [t for t in engine.store.get(sid).transcript if t['role'] == 'system']
    assert state.people.value == 2
    assert state.mobility.value == "motorbike"
    assert chat.calls == 2
