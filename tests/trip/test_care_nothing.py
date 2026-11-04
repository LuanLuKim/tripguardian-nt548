"""T4 (prod e2e 2026-11-03): "không có gì" to the open Lưu ý question is the answer, whatever the agent does next."""

import pytest
from trip_fixtures import ScriptedChat, say

from trip.api.engine import TurnInput
from trip.domain.readiness import missing
from trip.domain.text import says_nothing

ASK = "Có điều gì về sức khỏe, đi lại hay ăn uống cần lưu ý không?"


@pytest.mark.parametrize("text,clause", [("không có gì. cho tui quán bánh căn Nhà Chung", "không có gì"), ("Không", "Không"),
                                         ("bình thường, đi thôi", "bình thường"), ("không có gì đặc biệt", "không có gì đặc biệt")])
def test_a_nothing_clause_is_found(text, clause):
    assert says_nothing(text) == clause


@pytest.mark.parametrize("text", ["không có xe máy", "không thích đông", "có, bà tôi đau gối", "", "chưa chốt"])
def test_other_words_are_not_nothing(text):
    assert says_nothing(text) == ""


def _talk(engine, text, asked=True):
    sid = engine.create("first", "nothing")["id"]
    s = engine.store.get(sid)
    if asked:
        s.transcript.append({"role": "agent", "text": ASK, "turn": 0, "kind": "say"})
        engine.store.save(s)
    engine.turn(sid, TurnInput(kind="text", text=text), lambda e, d: None)
    return engine.store.get(sid)


def test_nothing_after_the_care_question_answers_it(make_assistant):
    s = _talk(make_assistant(ScriptedChat(say("Ok."))), "không có gì. cho tui quán bánh căn")
    assert s.state.care.value == "none" and s.state.care.source == "user"
    assert "care" not in dict(missing(s.state))


@pytest.mark.parametrize("asked", [
    "Lưu ý quán này chỉ mở ban ngày. Bạn muốn ăn món gì?",
    "Lưu ý quán này chỉ mở ban ngày! Bạn muốn ăn món gì?",
])
def test_nothing_after_an_unrelated_question_keeps_care_unknown(make_assistant, asked):
    engine = make_assistant(ScriptedChat(say("Ok.")))
    sid = engine.create("first", "nothing")["id"]
    session = engine.store.get(sid)
    session.transcript.append({"role": "agent", "text": asked, "turn": 0, "kind": "say"})
    engine.store.save(session)
    engine.turn(sid, TurnInput(kind="text", text="không có gì"), lambda *_: None)
    assert not engine.store.get(sid).state.care.known


def test_nothing_without_the_question_is_not_a_care_answer(make_assistant):
    s = _talk(make_assistant(ScriptedChat(say("Ok."))), "không có gì", asked=False)
    assert not s.state.care.known
