"""The Clef rule guard of the assistant (agents.assistant.guard)."""

import time

import yaml

from agents.assistant import Guarded, TurnCore
from agents.assistant import guard
from agents.assistant.guard import LABELS, check, reply


def answering(label, p=0.97, seen=None):
    def ask(state, questions):
        if seen is not None:
            seen.append((state, questions))
        return {guard.QUESTION: {"choice": label, "probabilities": {label: p, "ok": 1 - p}}}
    return ask


def test_one_choice_question_with_every_label():
    seen = []
    check(answering("ok", seen=seen), "Mai mưa không?", prev_user="Tìm cà phê", prev_reply="x" * 500, shown=["Quán A"], threshold=0.8)
    state, questions = seen[0]
    q = questions[guard.QUESTION]
    assert q["type"] == "choice" and set(q["criteria"]) == set(LABELS)
    assert state["user_message"] == "Mai mưa không?" and state["previous_user_message"] == "Tìm cà phê"
    assert len(state["previous_reply"]) <= 200 and state["places_shown"] == ["Quán A"]


def test_a_sure_rule_label_blocks():
    v = check(answering("R3", 0.95), "x", threshold=0.8)
    assert v.label == "R3" and v.hit and v.blocked
    assert reply(v.label, "x")  # a fixed reply exists


def test_below_threshold_is_ok():
    v = check(answering("R3", 0.6), "x", threshold=0.8)
    assert v.label == "ok" and not v.hit


def test_r7_and_r8_answer_with_a_fixed_reply_but_are_not_blocks():
    for label in ("R7", "R8"):
        v = check(answering(label), "x", threshold=0.8)
        assert v.hit and not v.blocked
    assert "113" in reply("R8", "tôi muốn chết") and "115" in reply("R8", "tôi muốn chết")
    assert "113" in reply("R8", "i want to die") and reply("R7", "x") != reply("R8", "x")


def test_a_failing_or_silent_clef_is_ok():
    assert not check(lambda s, q: {}, "x", threshold=0.5).hit

    def boom(s, q):
        raise OSError("down")
    assert not check(boom, "x", threshold=0.5).hit


def test_guarded_runs_in_a_thread_and_waits_at_most_the_wait():
    def slow(s, q):
        time.sleep(0.5)
        return {guard.QUESTION: {"choice": "R1", "probabilities": {"R1": 0.99}}}
    g = Guarded(slow, "x", threshold=0.8)
    assert g.peek() is None and not g.blocked_now()
    assert not g.verdict(wait=0.05).hit  # too slow: it decides nothing
    assert g.verdict(wait=2).hit


def test_blocked_turn_sends_no_cards():
    t = TurnCore("trip", {"assistant"})
    t.verdict = lambda: True
    assert t.emit_cards(["a"]) == [] and t.cards_sent == []


def test_labelled_set_is_big_enough_and_complete():
    cases = yaml.safe_load(open("config/bench_assistant_guard.yaml", encoding="utf-8"))["cases"]
    assert len(cases) >= 80 and {c["label"] for c in cases} == set(LABELS)
    texts = [c["text"] for c in cases]
    assert "Gợi ý hay vcl, gợi ý thêm cho tao đi" in texts and "Hay vậy má thề, kiếm thêm mấy chỗ như này đi" in texts
