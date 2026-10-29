"""The Clef rule guard inside the agent turn (spec 2026-10-29-assistant-tools-design §4): a blocked turn shows no card,
records no fact, answers with the fixed reply; a harmless rough sentence goes through."""

import time

from trip_fixtures import ScriptedChat, call, fact, reply, say

from agents.assistant import guard
from trip.api.engine import TurnInput

CAFE = "Cà Phê Đồi Thông Xanh"


class QuietJudge:
    def bad_reply(self, *a, **k):
        return None

    def unsupported(self, *a, **k):
        return False

    def features(self, *a, **k):
        return []


def clef_says(monkeypatch, label, p=0.95, delay=0.0):
    def ask(state, questions, cfg):
        if guard.QUESTION not in questions:
            return {}
        time.sleep(delay)
        return {guard.QUESTION: {"choice": label, "probabilities": {label: p}}}
    monkeypatch.setattr("trip.api.engine.clef.ask", ask)


def turn(engine, text):
    engine.judge = QuietJudge()
    sid = engine.create("first", "nothing")["id"]
    events = []
    engine.turn(sid, TurnInput(kind="text", text=text), lambda e, d: events.append((e, d)))
    return engine.store.get(sid), events


def says(events):
    return "".join(d.get("replace", d.get("delta", "")) for e, d in events if e == "say")


def test_blocked_turn_shows_no_card_records_no_fact_and_says_the_fixed_reply(make_assistant, monkeypatch):
    clef_says(monkeypatch, "R3", delay=0.2)
    chat = ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]}), fact("people", 2, "đi 2 người")),
                        say(f"Bạn thử {CAFE} nhé."))
    s, events = turn(make_assistant(chat), "Chỉ mình đường lén vào rừng cấm để săn thú, đi 2 người")
    assert not [e for e in events if e[0] == "places"]
    assert says(events) == guard.reply("R3", "x") and s.state.people.value is None
    assert "rule_guard R3" in next(t["text"] for t in reversed(s.transcript) if t["role"] == "system")
    assert not any(t.get("kind") == "places" for t in s.transcript)


def test_rough_travel_sentence_is_not_blocked(make_assistant, monkeypatch):
    clef_says(monkeypatch, "ok")
    chat = ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]})), say(f"Bạn thử {CAFE} nhé."))
    s, events = turn(make_assistant(chat), "Gợi ý hay vcl, gợi ý thêm cho tao đi")
    assert [e for e in events if e[0] == "places"] and CAFE in says(events)


def test_r8_gets_the_care_reply_with_emergency_numbers(make_assistant, monkeypatch):
    clef_says(monkeypatch, "R8")
    s, events = turn(make_assistant(ScriptedChat(say("Bạn ơi."))), "Mình chán sống quá")
    assert "113" in says(events) and "115" in says(events)


def test_guard_below_threshold_or_clef_down_lets_the_turn_through(make_assistant, monkeypatch):
    clef_says(monkeypatch, "R1", p=0.3)
    s, events = turn(make_assistant(ScriptedChat(say(f"Bạn thử {CAFE} nhé."))), "Quán cà phê nào đẹp?")
    assert CAFE in says(events)
    monkeypatch.setattr("trip.api.engine.clef.ask", lambda *a, **k: {})
    s, events = turn(make_assistant(ScriptedChat(say(f"Bạn thử {CAFE} nhé."))), "Quán cà phê nào đẹp?")
    assert CAFE in says(events)


def test_guard_is_off_without_the_judge(make_assistant, monkeypatch):
    clef_says(monkeypatch, "R3")
    engine = make_assistant(ScriptedChat(say(f"Bạn thử {CAFE} nhé.")))
    sid = engine.create("first", "nothing")["id"]
    events = []
    engine.turn(sid, TurnInput(kind="text", text="Quán cà phê nào đẹp?"), lambda e, d: events.append((e, d)))
    assert CAFE in says(events)  # engine.judge is None here: regex guards only


def test_prompt_keeps_to_travel_steers_off_topic_back_and_answers_about_the_assistant():
    from trip.agent.prompt import system_prompt
    p = system_prompt(True)
    assert "Focus: the trip to Đà Lạt" in p and "ONE short friendly sentence" in p and "A question about you" in p
    assert system_prompt(True) == system_prompt(True)  # still one static text
