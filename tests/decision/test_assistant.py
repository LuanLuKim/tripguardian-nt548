"""The Lựa chọn chatbot on the shared assistant core (docs/PLACE_DECISION.md §Trợ lý, spec 2026-10-29 assistant-tools §5.9):
heuristics first, then the shared loop with Decision's action tools. The model is scripted; nothing here calls it."""

import json
from dataclasses import replace

from langchain_core.messages import AIMessageChunk
from test_decision_engine import CFG, FakeAgent, data, trip

from agents.assistant import REGISTRY
from decision import tool_schemas
from decision.engine import Engine
from decision.guard import TurnPlan
from decision.session import Store


def call(name, **args):
    return {"id": f"call_{name}", "name": name, "args": json.dumps(args, ensure_ascii=False)}


def reply(*calls, text=""):
    return AIMessageChunk(content=text, tool_call_chunks=[dict(c, index=i) for i, c in enumerate(calls)])


def say(text):
    return AIMessageChunk(content=text)


class Script:
    """A Chat that plays the given replies in order, one per model call; keeps what each call saw."""

    def __init__(self, *replies):
        self.replies, self.seen = list(replies), []

    @property
    def calls(self):
        return len(self.seen)

    async def __call__(self, messages, tools, on_say):
        self.seen.append((list(messages), [t.name for t in tools]))
        if not self.replies:
            from agents import AgentError
            raise AgentError("script ended")
        r = self.replies.pop(0)
        if r.text:
            on_say(r.text)
        return r


def assisted(chat, **kw):
    e = Engine(data(), CFG, Store(None), kw.pop("agent", None), assistant=chat)
    return e


def turn(e, sid, text):
    events = []
    e.turn(sid, text, lambda ev, d: events.append((ev, d)))
    return events


def said(events):
    return next(d for ev, d in events if ev == "say")


def tool_results(chat_seen_messages):
    return [json.loads(m["content"]) for m in chat_seen_messages if m["role"] == "tool"]


def start(chat, **over):
    e = assisted(chat)
    sid = e.create(trip(**over))["id"]
    return e, sid


# ---------- tools are registered for the decision stage only ----------

def test_decision_action_tools_are_registered_with_their_words():
    names = {"select", "drop", "lock", "visited", "like", "more_like", "rerank", "filter", "unfilter", "why_not", "compare",
             "trip", "swap_suggest", "undo"}
    assert names <= set(REGISTRY.names("decision", {"assistant"}))
    assert not names & set(REGISTRY.names("trip", {"assistant", "cards", "web"}))
    for n in names:
        model = REGISTRY.get(n).model
        assert (model.__doc__ or "").strip() and model.model_config.get("extra") == "forbid"
    assert tool_schemas.SelectPlace.tool_name == "select"


# ---------- action tools ----------

def test_a_named_place_is_selected_with_one_version_and_the_effect_goes_back_to_the_model():
    chat = Script(reply(call("select", place="C3", quote="Quán Cà Phê Số 3")), say("Mình đã thêm Quán Cà Phê Số 3."))
    e, sid = start(chat)
    third = {"id": "C3"}
    events = turn(e, sid, "thêm giúp mình Quán Cà Phê Số 3 nhé")
    s = e.store.get(sid)
    assert s.state.selected == [third["id"]] and len(s.history) == 1
    assert said(events) == {"replace": "Mình đã thêm Quán Cà Phê Số 3."}
    result = tool_results(chat.seen[1][0])[0]
    assert result["done"] == "select" and result["place"]["id"] == third["id"] and "effect" in result
    assert [ev for ev, _ in events] == ["say", "view", "done"]


def test_select_needs_the_place_named_or_pointed_at_and_changes_nothing_otherwise():
    chat = Script(reply(call("select", place="P1", quote="chọn đi")), say("Bạn muốn chọn quán nào?"))
    e, sid = start(chat)
    turn(e, sid, "chọn đi")
    assert e.store.get(sid).state.selected == [] and e.store.get(sid).history == []
    assert "error" in tool_results(chat.seen[1][0])[0]


def test_select_by_pointing_word_is_allowed():
    chat = Script(reply(call("select", place="P1", quote="quán đầu tiên")), say("Mình đã chọn quán đầu tiên."))
    e, sid = start(chat)
    turn(e, sid, "lấy quán đầu tiên nhé")
    assert len(e.store.get(sid).state.selected) == 1


def test_a_quote_that_is_not_in_the_message_is_refused():
    chat = Script(reply(call("drop", place="P1", quote="bỏ quán này đi", reason="far")), say("Okay."))
    e, sid = start(chat)
    turn(e, sid, "quán đầu có vẻ xa đó")
    assert e.store.get(sid).state.dropped == []
    assert "quote" in tool_results(chat.seen[1][0])[0]["error"]


def test_two_tools_in_one_message_are_one_version_and_one_undo():
    chat = Script(reply(call("drop", place="P1", quote="quán đầu xa quá", reason="far"),
                        call("filter", feature="opens_by", value="07:00", quote="mở trước 7h")),
                  say("Mình đã bỏ quán đầu và chỉ hiện quán mở trước 7h."))
    e, sid = start(chat)
    turn(e, sid, "quán đầu xa quá, chỉ xem quán mở trước 7h")
    s = e.store.get(sid)
    assert len(s.history) == 1 and s.state.filters == [("opens_by", "07:00")] and len(s.state.dropped) == 1
    assert s.state.profile.travel_mult == CFG.far_step
    e.act(sid, {"type": "undo"})
    s = e.store.get(sid)
    assert s.state.filters == [] and s.state.dropped == []


def test_rerank_applies_wishes_and_feedback_and_refuses_an_unknown_feature():
    chat = Script(reply(call("rerank", wishes=[{"feature": "scenic_view", "value": "present"},
                                               {"feature": "no_such_feature", "value": "x"}],
                           feedback=["crowded"], quote="yên tĩnh, có view")), say("Mình ưu tiên quán yên tĩnh và có view."))
    e, sid = start(chat)
    turn(e, sid, "ưu tiên quán yên tĩnh, có view đẹp")
    st = e.store.get(sid).state
    assert [(x.feature, x.value, x.weight) for x in st.profile.soft] == [("scenic_view", "present", 1)]
    assert st.profile.crowd_tolerance == "avoid"
    r = tool_results(chat.seen[1][0])[0]
    assert r["results"][0]["done"] and "error" in r["results"][1]


def test_why_not_changes_nothing_and_hands_the_model_no_score():
    chat = Script(reply(call("why_not", place="Quán Ăn Bình Dân")), say("Quán đó chưa xác minh."))
    e, sid = start(chat)
    before = e.store.get(sid).state.model_dump()
    turn(e, sid, "sao không thấy Quán Ăn Bình Dân")
    r = tool_results(chat.seen[1][0])[0]
    assert "reasons" in r and "score" not in r and "parts" not in r
    assert e.store.get(sid).state.model_dump() == before and e.store.get(sid).history == []


def test_why_not_dropped_place_returns_a_complete_answer_without_constraint_advice():
    chat = Script(reply(call("why_not", place="C0")), say("Bạn đã bỏ nơi này."))
    e, sid = start(chat)
    e.act(sid, {"type": "drop", "place_id": "C0"})
    turn(e, sid, "sao không thấy Quán Cà Phê Số 0")
    result = tool_results(chat.seen[1][0])[0]
    assert result["answer"] == "Bạn đã bỏ nơi này."
    assert "nới" not in result["answer"] and "giới hạn" not in result["answer"]


def test_why_not_unknown_place_returns_actual_reason_as_a_sentence():
    chat = Script(reply(call("why_not", place="Quán Ăn Bình Dân")), say("Quán đó chưa xác minh."))
    e, sid = start(chat)
    turn(e, sid, "sao không thấy Quán Ăn Bình Dân")
    result = tool_results(chat.seen[1][0])[0]
    assert result["answer"].endswith(".")
    assert all(reason.rstrip(".?!…") in result["answer"] for reason in result["reasons"])
    assert "Bạn đã bỏ" not in result["answer"]


def test_compare_returns_the_table_rows():
    chat = Script(reply(call("compare", places=["C0", "C1"])), say("Hai quán khá giống nhau."))
    e, sid = start(chat)
    turn(e, sid, "so Quán Cà Phê Số 0 với Quán Cà Phê Số 1")
    r = tool_results(chat.seen[1][0])[0]
    assert r["comparisons"][0]["a"]["id"] == "C0" and "rows" in r["comparisons"][0]


def test_trip_wish_goes_to_trip_and_must_be_in_the_message():
    chat = Script(reply(call("trip", texts=["muốn chill hơn", "đổi hết thành đi biển"])), say("Mình chuyển ý chill sang phần hiểu chuyến đi."))
    e, sid = start(chat)
    events = turn(e, sid, "chuyến này muốn chill hơn nhé, quán đầu bạn thấy sao")
    trip_events = [d for ev, d in events if ev == "trip"]
    assert trip_events == [{"texts": ["muốn chill hơn"]}]
    assert tool_results(chat.seen[1][0])[0]["skipped"] == ["đổi hết thành đi biển"]
    assert [ev for ev, _ in events].index("trip") < [ev for ev, _ in events].index("view")


def test_more_like_is_a_like_that_names_who_moved_up():
    chat = Script(reply(call("more_like", place="C0", quote="Quán Cà Phê Số 0")), say("Mình ưu tiên thêm quán giống Quán Cà Phê Số 0."))
    e, sid = start(chat)
    turn(e, sid, "kiếm thêm quán giống Quán Cà Phê Số 0")
    assert e.store.get(sid).state.likes == ["C0"]
    assert "effect" in tool_results(chat.seen[1][0])[0]


def test_swap_suggest_changes_no_state():
    chat = Script(reply(call("swap_suggest", place="C0")), say("Bạn có thể thay bằng quán khác trong danh sách."))
    e, sid = start(chat)
    turn(e, sid, "đổi Quán Cà Phê Số 0 lấy chỗ khác tương tự")
    assert e.store.get(sid).history == []
    assert "alternatives" in tool_results(chat.seen[1][0])[0]


def test_undo_works_alone_and_not_beside_another_change():
    chat = Script(reply(call("select", place="C1", quote="Quán Cà Phê Số 1")), say("Đã chọn."))
    e, sid = start(chat)
    turn(e, sid, "chọn Quán Cà Phê Số 1 giúp mình nha")
    chat.replies += [reply(call("undo", quote="hoàn tác")), say("Mình đã hoàn tác.")]
    events = turn(e, sid, "hoàn tác")
    assert e.store.get(sid).state.selected == [] and said(events) == {"replace": "Mình đã hoàn tác."}
    chat.replies += [reply(call("select", place="C2", quote="Quán Cà Phê Số 2"), call("undo", quote="hoàn tác")), say("Ok.")]
    turn(e, sid, "hoàn tác và chọn Quán Cà Phê Số 2")
    assert e.store.get(sid).state.selected == ["C2"]


# ---------- the reply ----------

def test_a_reply_with_an_invented_number_is_sent_back_once():
    chat = Script(say("Quán đó cách 99 phút."), say("Mình chưa có số đo cho quán đó."))
    e, sid = start(chat)
    events = turn(e, sid, "quán đầu cách bao xa")
    assert chat.calls == 2 and said(events) == {"replace": "Mình chưa có số đo cho quán đó."}
    assert chat.seen[1][0][-1]["role"] == "user" and "99" in chat.seen[1][0][-1]["content"]


def test_a_reply_that_stays_bad_is_replaced_never_left_empty():
    chat = Script(say("Cách 99 phút."), say("Cách 98 phút."))
    e, sid = start(chat)
    ev = said(turn(e, sid, "quán đầu cách bao xa"))
    assert ev["replace"].strip()
    assert "99" not in ev["replace"] and "98" not in ev["replace"]


def test_the_turn_log_keeps_the_say_and_the_next_turn_reads_it_as_history():
    chat = Script(say("Quán đầu là quán cà phê."), say("Còn quán thứ hai thì khác."))
    e, sid = start(chat)
    turn(e, sid, "quán đầu là quán gì")
    assert e.store.get(sid).log[-1]["action"]["say"] == "Quán đầu là quán cà phê."
    turn(e, sid, "còn quán thứ hai")
    msgs = chat.seen[1][0]
    assert any(m["role"] == "assistant" and m["content"] == "Quán đầu là quán cà phê." for m in msgs)
    assert msgs[0]["role"] == "system" and msgs[-1] == {"role": "user", "content": "còn quán thứ hai"}
    context = next(m for m in msgs if m["role"] == "user" and m["content"].startswith("CURRENT CONTEXT"))
    assert "P1" in context["content"] and "Quán Cà Phê Số" in context["content"]


# ---------- routing ----------

def test_familiar_sentences_still_go_through_heuristics_without_a_model_call():
    chat = Script()
    e, sid = start(chat)
    turn(e, sid, "yên tĩnh hơn")
    turn(e, sid, "Chọn Quán Cà Phê Số 2")
    assert chat.calls == 0 and e.store.get(sid).state.profile.crowd_tolerance == "avoid"


def test_when_the_model_fails_the_keyword_policy_answers():
    e, sid = start(Script())
    events = turn(e, sid, "Quán Cà Phê Số 2 xa quá")
    assert said(events) == {"replace": "Mình đã ghi nhận, danh sách đã cập nhật."}
    assert e.store.get(sid).state.dropped[0].place_id == "C2"


def test_without_an_assistant_or_when_off_the_structured_agent_answers():
    plan = TurnPlan(say="Mình hiểu rồi.")
    agent = FakeAgent(plan)
    off = replace(CFG, assistant={**CFG.assistant, "enabled": False})
    e = Engine(data(), off, Store(None), agent, assistant=Script(say("không dùng")))
    sid = e.create(trip())["id"]
    turn(e, sid, "bạn nghĩ sao về danh sách")
    assert len(agent.calls) == 1
    plain = FakeAgent(plan)
    e2 = Engine(data(), CFG, Store(None), plain)
    sid = e2.create(trip())["id"]
    turn(e2, sid, "bạn nghĩ sao về danh sách")
    assert len(plain.calls) == 1


# ---------- shared read tools ----------

class Reader:
    """Stands in for a Trip TurnTools (Tools.read_turn): runs shared read tools over the trip state."""

    def __init__(self):
        self.cache_hits, self.log, self.told_ids, self.told_numbers, self.closed = 0, [], set(), set(), False

    def run(self, name, args):
        self.log.append(name)
        self.told_ids.add("C0")
        self.told_numbers.update({7, 22})
        return {"id": "C0", "name": "Quán Cà Phê Số 0", "open": "07:00-22:00"}

    def close(self):
        self.closed = True


def test_shared_read_tools_run_on_the_trip_reader_and_what_they_return_may_be_said():
    chat = Script(reply(call("get_place", id="C0")), say("Quán Cà Phê Số 0 mở từ 7 giờ đến 22 giờ."))
    e, sid = start(chat)
    reader = Reader()
    e.trip_reader = lambda trip_session, text: reader
    e.store.get(sid).trip_session = "0123456789ab"
    events = turn(e, sid, "quán đầu mở mấy giờ")
    assert "get_place" in chat.seen[0][1] and reader.log == ["get_place"] and reader.closed
    assert said(events) == {"replace": "Quán Cà Phê Số 0 mở từ 7 giờ đến 22 giờ."}


def test_no_trip_session_means_no_read_tools_are_offered():
    chat = Script(say("Mình chưa tra được."))
    e, sid = start(chat)
    turn(e, sid, "quán đầu mở mấy giờ")
    offered = chat.seen[0][1]
    assert "get_place" not in offered and "select" in offered and "why_not" in offered
    assert not {"photo_identify", "photo_similar", "link_resolve", "more_like_shown"} & set(offered)


def test_trip_tools_hand_out_a_read_turn_over_the_session_state():
    from contextlib import nullcontext
    from datetime import date
    from types import SimpleNamespace

    from trip.api.tools import Tools as TripTools
    from trip.domain.state import TripState

    session = SimpleNamespace(lock=nullcontext(), state=TripState())
    catalog = SimpleNamespace(by_id={"C0": object()})
    engine = SimpleNamespace(store=SimpleNamespace(root=None, get=lambda sid: session), knowledge=object(), judge=None,
                             catalog=catalog, today=lambda: date(2026, 10, 29),
                             cfg=SimpleNamespace(assistant=SimpleNamespace(enabled=True)))
    tools = TripTools(engine)
    reader = tools.read_turn("0123456789ab", "quán đầu mở mấy giờ")
    assert reader.stage == "trip" and "assistant" in reader.flags and reader.state is session.state
    assert "get_place" in reader.tool_names() and "select" not in reader.tool_names()
    engine.knowledge = None
    assert tools.read_turn("0123456789ab", "x") is None


def test_a_refused_second_reply_keeps_its_good_sentences_and_a_thousand_is_the_k_of_the_result():
    bad = "Quán mở từ 7 giờ, vé 22.000đ. Cách đó 99 phút đi bộ."
    chat = Script(reply(call("get_place", id="C0")), say(bad), say(bad))  # the second is the retry, still bad
    e, sid = start(chat)
    e.trip_reader = lambda trip_session, text: Reader()
    e.store.get(sid).trip_session = "0123456789ab"
    events = turn(e, sid, "quán đầu mở mấy giờ")
    assert said(events) == {"replace": "Quán mở từ 7 giờ, vé 22.000đ."}


def test_chot_with_a_pronoun_goes_to_the_assistant_not_to_trip():
    chat = Script(reply(call("lock", place="C1", quote="Chốt nó")), say("Mình đã chốt Quán Cà Phê Số 1."))
    e, sid = start(chat)
    turn(e, sid, "Thêm Quán Cà Phê Số 1 vào chuyến")
    chat.replies = [reply(call("lock", place="C1", quote="Chốt nó")), say("Mình đã chốt Quán Cà Phê Số 1.")]
    events = turn(e, sid, "Chốt nó luôn nhé")
    assert "trip" not in [ev for ev, _ in events] and e.store.get(sid).state.locked == ["C1"]


def test_one_tool_call_per_response_still_does_every_ask_of_a_message():
    chat = Script(reply(call("trip", texts=["thêm một ngày"])), reply(call("select", place="C1", quote="Quán Cà Phê Số 1")),
                  say("Mình đã ghi nhận ý thêm ngày và thêm Quán Cà Phê Số 1."))
    e, sid = start(chat)
    events = turn(e, sid, "thêm một ngày nữa, và chọn Quán Cà Phê Số 1 luôn")
    assert chat.calls == 3 and e.store.get(sid).state.selected == ["C1"]
    assert [d for ev, d in events if ev == "trip"] == [{"texts": ["thêm một ngày"]}]


# ---------- place cards under the reply ----------

class CardReader(Reader):
    """A Reader whose knowledge builds the Trip chat card of a place."""

    def __init__(self):
        super().__init__()
        self.knowledge = type("K", (), {"view": staticmethod(lambda pid, today=None, liked=False, scene=None: {
            "id": pid, "name": pid, "category": None, "area": None, "rating": None, "reviews": None,
            "photos": [], "hours_today": None, "price": None, "liked": liked})})()


def test_the_reply_carries_cards_of_the_places_it_names_that_a_tool_returned():
    chat = Script(reply(call("get_place", id="C0")), say("Quán Cà Phê Số 0 mở từ 7 giờ đến 22 giờ."))
    e, sid = start(chat)
    e.trip_reader = lambda trip_session, text: CardReader()
    e.store.get(sid).trip_session = "0123456789ab"
    events = turn(e, sid, "quán đầu mở mấy giờ")
    names = [ev for ev, _ in events]
    places = next(d for ev, d in events if ev == "places")
    assert places["ids"] == ["C0"] and places["cards"][0]["id"] == "C0"
    assert names.index("say") < names.index("places") < names.index("view")


def test_no_cards_when_the_reply_names_no_returned_place():
    chat = Script(reply(call("get_place", id="C0")), say("Mình chưa rõ giờ mở."))
    e, sid = start(chat)
    e.trip_reader = lambda trip_session, text: CardReader()
    e.store.get(sid).trip_session = "0123456789ab"
    assert "places" not in [ev for ev, _ in turn(e, sid, "quán đầu mở mấy giờ")]


# ---------- group_list: a tab by kind (corpus.tags.split over the tab's places) ----------

def test_group_list_is_registered_and_a_short_tab_gives_no_groups():
    assert "group_list" in REGISTRY.names("decision", {"assistant"})
    chat = Script(reply(call("group_list", tab="Cà phê")), say("Danh sách này chưa chia thành kiểu rõ ràng."))
    e, sid = start(chat)
    before = e.store.get(sid).state.model_dump()
    turn(e, sid, "tab cà phê có những kiểu nào")
    r = tool_results(chat.seen[1][0])[0]
    assert r["tab"] == "Cà phê" and r["total"] == 7 and r["groups"] == [] and "note" in r  # safety unknown stays listed
    assert e.store.get(sid).state.model_dump() == before and e.store.get(sid).history == []  # it changes nothing


def test_group_list_names_a_tab_that_does_not_exist():
    chat = Script(reply(call("group_list", tab="không có tab này")), say("Mình không thấy tab đó."))
    e, sid = start(chat)
    turn(e, sid, "tab nào có những kiểu nào")
    assert "error" in tool_results(chat.seen[1][0])[0]


def test_kinds_of_splits_a_long_list_by_evidence_and_leaves_a_short_one(tmp_path):
    from decision.kinds import kinds_of
    from fixtures import srec
    recs = {}
    for g, cat, n in (("cafe", "Quán cà phê", 6), ("restaurant", "Nhà hàng", 5), ("nature", "Đồi", 4), ("attraction", "Điểm tham quan", 4)):
        for i in range(n):
            recs[f"{g}{i}"] = srec(f"{g}{i}", name=f"{cat} {i}", group=g, category=cat)
    got = kinds_of(list(recs), recs, styles={})
    assert got["axis"] == "category" and got["total"] == 19 and [x["count"] for x in got["groups"]] == [6, 5, 4, 4]
    assert all(set(x["places"][0]) == {"id"} and len(x["places"]) == 3 for x in got["groups"])
    assert kinds_of(list(recs)[:8], recs, styles={}) is None  # under min_places
    assert kinds_of(["nope"] * 20, recs, styles={}) is None  # places without a record are no tags
