"""The assistant inside the agent turn (plan 2026-10-28-trip-decision-chatbot Task 4, spec §B.1, §B.4)."""

from trip_fixtures import ScriptedChat, call, reply, say

from trip.agent.prompt import build_messages, system_prompt
from trip.api.engine import TurnInput
from trip.domain.required import planning
from trip.domain.state import TripState, with_meta

CAFE = "Cà Phê Đồi Thông Xanh"


def run_turn(engine, text, chat=None):
    sid = engine.create("first", "nothing")["id"]
    engine.turn(sid, TurnInput(kind="text", text=text), lambda e, d: None)
    return engine.store.get(sid)


def last_say(s):
    return next(t["text"] for t in reversed(s.transcript) if t["role"] == "agent" and t.get("kind") == "say")


def system_log(s):
    return next(t["text"] for t in reversed(s.transcript) if t["role"] == "system")


def test_flag_off_prompt_unchanged():
    assert system_prompt() == system_prompt(assistant=False) and "never suggest places" in system_prompt()
    on = system_prompt(assistant=True)
    assert "never suggest places" not in on and "ASSISTANT" in on and "find_places" in on


def test_assistant_prompt_is_the_same_for_every_turn_and_length_style_ride_in_the_context():
    import datetime
    import json
    assert system_prompt(True) == system_prompt(True)  # one static text: the provider's cache is shared by all users
    assert "at most 25 words" not in system_prompt(True) and "reply.language" in system_prompt(True)
    a = build_messages(TripState(), "x", [], None, datetime.date(2026, 10, 28), [], assistant=True, ask_words=30,
                       reply_style="Be brief.")
    b = build_messages(TripState(), "x", [], None, datetime.date(2026, 10, 28), [], assistant=True, ask_words=45,
                       reply_style="Other.")
    assert a[0] == b[0]  # the system message does not move with the words or the style
    reply = json.loads(a[-2]["content"].split("\n", 1)[1])["reply"]
    assert a[-2]["role"] == "user" and reply == {"language": "Vietnamese", "max_words": 30, "style": "Be brief."}
    en = build_messages(TripState(), "We are 2 couples, 3 days in Dalat, we love coffee", [], None, datetime.date(2026, 10, 28), [])
    assert json.loads(en[-2]["content"].split("\n", 1)[1])["reply"] == {"language": "English"}


def test_engine_gives_the_context_its_configured_length_and_style(make_assistant):
    from dataclasses import replace
    chat = ScriptedChat(say("Ok."))
    engine = make_assistant(chat)
    engine.cfg = replace(engine.cfg, assistant=replace(engine.cfg.assistant, ask_words=33, reply_style="STYLE-X"))
    run_turn(engine, "Quán cà phê nào đẹp ở Đà Lạt?")
    context = next(m["content"] for m in chat.seen[0][0] if m["content"].startswith("CURRENT CONTEXT"))
    assert '"max_words": 33' in context and "STYLE-X" in context and "STYLE-X" not in chat.seen[0][0][0]["content"]


def test_data_goes_into_current_context():
    msgs = build_messages(TripState(), "x", [], None, __import__("datetime").date(2026, 10, 28), [],
                          data={"tim_noi": [{"id": "a"}]}, assistant=True)
    assert '"data": {"tim_noi"' in msgs[-2]["content"] and "ASSISTANT" in msgs[0]["content"]
    assert '"data"' not in build_messages(TripState(), "x", [], None, __import__("datetime").date(2026, 10, 28), [])[-2]["content"]


def test_assistant_turn_names_a_found_place(make_assistant):
    chat = ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]})),
                        say(f"Bạn thử {CAFE} nhé, view đồi thông rất đẹp."))
    s = run_turn(make_assistant(chat), "Gợi ý quán cà phê view đồi")
    assert CAFE in last_say(s) and "0xa:0x1" in s.state.meta.shown_ids


def test_prepared_data_reaches_the_model(make_assistant):
    chat = ScriptedChat(say(f"Bạn thử {CAFE} nhé."))
    s = run_turn(make_assistant(chat), "Gợi ý quán cà phê view đồi")
    context = next(m["content"] for m in chat.seen[0][0] if m["content"].startswith("CURRENT CONTEXT"))
    assert '"tim_noi"' in context and CAFE in last_say(s)  # named from the prepared data, no tool call
    assert "find_places" in chat.seen[0][1]


def test_assistant_turn_prunes_unfound_place(make_assistant):
    chat = ScriptedChat(say("Bạn ghé Khách Sạn Đồi Chè nhé. Quán nào ở đây cũng ấm."))
    s = run_turn(make_assistant(chat), "Gợi ý quán cà phê")
    assert "Khách Sạn" not in last_say(s) and "ấm" in last_say(s)


def test_numbers_from_tool_results_may_be_said(make_assistant):
    chat = ScriptedChat(reply(call("get_place", id="0xa:0x1")), say(f"{CAFE} mở từ 7 giờ đến 22 giờ."))
    s = run_turn(make_assistant(chat), f"{CAFE} mở cửa mấy giờ?")
    assert "22 giờ" in last_say(s) and 22 in s.state.meta.told_numbers


def test_exploring_user_is_not_asked_required(make_assistant):
    chat = ScriptedChat(reply(call("ask_required", topic="trip", question="Bạn định đi ngày nào?")),
                        say("Tháng 11 Đà Lạt có mùa hoa dã quỳ."))
    s = run_turn(make_assistant(chat), "Đà Lạt tháng 11 có gì vui?")
    assert "ask_required:error" in system_log(s)


def test_planning_user_is_asked_required(make_assistant):
    assert planning(with_meta(TripState(), intent="plan")) and not planning(TripState())


def test_intent_is_recorded_from_the_users_words(make_assistant):
    chat = ScriptedChat(reply(call("record_fact", facts=[{"field": "intent", "op": "set", "value": "plan",
                                                          "quote": "muốn đi", "how": "said"}],
                                   say="Tuyệt, mình lên lịch nhé.")))
    s = run_turn(make_assistant(chat), "Mình muốn đi Đà Lạt")
    assert s.state.meta.intent == "plan"


def test_invite_to_plan_only_once(make_assistant):
    invite = "Bạn có muốn mình lên lịch cho chuyến này không?"
    e = make_assistant(ScriptedChat(say(f"Tháng 11 có hoa dã quỳ. {invite}"), say(f"Có cà phê ngon. {invite}")))
    sid = e.create("first", "nothing")["id"]
    e.turn(sid, TurnInput(kind="text", text="Đà Lạt tháng 11 có gì?"), lambda *a: None)
    assert e.store.get(sid).state.meta.invited and invite in last_say(e.store.get(sid))
    e.turn(sid, TurnInput(kind="text", text="Còn cà phê thì sao?"), lambda *a: None)
    assert invite not in last_say(e.store.get(sid))


def test_flag_off_offers_no_read_tools(make_assistant):
    chat = ScriptedChat(say("Ừ."))
    run_turn(make_assistant(chat, assistant=False), "Gợi ý quán cà phê")
    assert "find_places" not in chat.seen[0][1]
    assert not any(m["content"].startswith("CURRENT CONTEXT") and '"data"' in m["content"] for m in chat.seen[0][0])



# ---------- speed levers (flag-gated): hidden tools, cache-only responses end the turn, two calls at most ----------

def test_assistant_hides_name_lookup_and_answered_date_tools(make_assistant):
    chat = ScriptedChat(say("Tham khảo: mai có thể mưa nhẹ."))
    run_turn(make_assistant(chat), "Mai Đà Lạt có mưa không?")
    offered = chat.seen[0][1]
    assert "search_places" not in offered and "add_days" not in offered and "find_places" in offered
    off = ScriptedChat(say("Ừ."))
    run_turn(make_assistant(off, assistant=False), "Mai Đà Lạt có mưa không?")
    assert "search_places" in off.seen[0][1] and "add_days" in off.seen[0][1]


def test_find_places_is_hidden_only_when_prepared_data_holds_places(make_assistant):
    from dataclasses import replace
    q = "Gợi ý quán cà phê view đồi"

    def offered(hide, text):
        chat = ScriptedChat(say("Ok."))
        engine = make_assistant(chat)
        engine.cfg = replace(engine.cfg, assistant=replace(engine.cfg.assistant, hide_prepared_lookup=hide))
        run_turn(engine, text)
        return chat.seen[0][1]
    assert "find_places" not in offered(True, q) and "find_places" in offered(False, q)
    assert "find_places" in offered(True, "Mai Đà Lạt có mưa không?")  # nothing placed in data: the model may search


def test_a_response_served_only_from_the_cache_ends_the_turn(make_assistant):
    # prefetch already ran find_places({"text": …}); the model asks the same again and writes its reply with it
    q = "Gợi ý quán cà phê view đồi"
    chat = ScriptedChat(reply(call("find_places", criteria={"text": q}), text=f"Bạn thử {CAFE} nhé."))
    s = run_turn(make_assistant(chat), q)
    assert chat.calls == 1 and CAFE in last_say(s) and "find_places cached" in system_log(s)


def test_a_cache_only_response_without_text_gets_one_call_without_read_tools(make_assistant):
    q = "Gợi ý quán cà phê view đồi"
    chat = ScriptedChat(reply(call("find_places", criteria={"text": q})), say(f"Bạn thử {CAFE} nhé."))
    s = run_turn(make_assistant(chat), q)
    assert chat.calls == 2 and CAFE in last_say(s)
    assert "record_fact" in chat.seen[1][1]
    assert not {"find_places", "get_place", "weather", "web_search"} & set(chat.seen[1][1])


def test_the_assistant_calls_the_model_twice_at_most(make_assistant):
    chat = ScriptedChat(reply(call("get_place", id="0xa:0x1")), reply(call("get_place", id="0xc:0x1")),
                        say("không bao giờ tới đây"))
    s = run_turn(make_assistant(chat), f"{CAFE} có gì?")
    assert chat.calls == 2 and "record_fact" in chat.seen[1][1]
    assert "get_place" not in chat.seen[1][1]


# ---------- round 5: the first call offers no lookup when the prepared data answers (assistant.covered_tools) ----------

def _with(engine, **kw):
    from dataclasses import replace
    engine.cfg = replace(engine.cfg, assistant=replace(engine.cfg.assistant, **kw))
    return engine


def test_covered_question_first_call_offers_no_tool(make_assistant):
    q = "Gợi ý quán cà phê view đồi"
    chat = ScriptedChat(say(f"Bạn thử {CAFE} nhé."))
    s = run_turn(_with(make_assistant(chat), covered_tools="none"), q)
    assert chat.calls == 1 and chat.seen[0][1] == [] and CAFE in last_say(s) and "covered" in system_log(s)


def test_covered_question_write_mode_keeps_record_fact_only(make_assistant):
    chat = ScriptedChat(say("Ok."))
    run_turn(_with(make_assistant(chat), covered_tools="write"), "Gợi ý quán cà phê view đồi")
    offered = chat.seen[0][1]
    assert {"record_fact", "hide_place"} <= set(offered)  # "đóng cửa rồi mà" after a covered list still hides the place
    assert "record_fact" in offered and not {"find_places", "get_place", "distance", "weather", "web_search"} & set(offered)


def test_several_questions_keep_the_read_tools_even_when_the_prepared_data_covers_a_group(make_assistant):
    chat = ScriptedChat(say("Ok."))
    run_turn(_with(make_assistant(chat), covered_tools="write"), "Gợi ý quán cà phê view đồi? Từ chợ lên đó đi lại bằng gì?")
    assert {"record_fact", "get_place"} <= set(chat.seen[0][1])  # N3: only one of three questions was answered


def test_compound_request_keeps_reads_without_multiple_question_marks(make_assistant):
    from trip.agent.prefetch import Route

    for mode in ("write", "none"):
        for text in (
            "Gợi ý quán cà phê view đồi, từ chợ lên đó đi lại bằng gì?",
            "Gợi ý quán cà phê view đồi từ chợ lên đó đi lại bằng gì",
            "Gợi ý quán cà phê view đồi và cách đi từ chợ lên đó",
        ):
            chat = ScriptedChat(say("Ok."))
            engine = _with(make_assistant(chat), covered_tools=mode)

            def prepared(text, state, tools):
                tools.route = Route({"places"}, [])
                return {"tim_noi": [{"id": "0xa:0x1", "n": CAFE}]}, "prepared places only"

            engine._prefetch = prepared
            run_turn(engine, text)
            assert {"get_place", "find_services"} <= set(chat.seen[0][1]), (mode, text)


def test_uncovered_question_keeps_the_tools(make_assistant):
    chat = ScriptedChat(say("Ừ."))
    run_turn(_with(make_assistant(chat), covered_tools="none"), "Đặc sản Đà Lạt là gì?")  # no group: nothing prepared
    assert "find_places" in chat.seen[0][1]
    default = ScriptedChat(say("Ok."))
    run_turn(make_assistant(default), "Gợi ý quán cà phê view đồi")  # default "all": today's behaviour
    assert "record_fact" in default.seen[0][1] and "get_place" in default.seen[0][1]


def test_a_fact_said_at_turn_one_is_still_in_the_state_at_turn_thirty():
    import datetime
    from trip.domain.state import with_meta
    state = TripState().model_copy(update={"days": TripState().days.model_copy(update={"value": 3, "source": "user", "status": "confirmed"})})
    transcript = []
    for t in range(1, 31):
        transcript += [{"role": "user", "text": "đi 3 ngày" if t == 1 else f"câu {t}", "turn": t},
                       {"role": "agent", "text": f"trả lời {t}", "turn": t, "kind": "say"}]
    msgs = build_messages(state, "câu 31", transcript, None, datetime.date(2026, 10, 28), [], assistant=True)
    joined = " ".join(m["content"] for m in msgs[1:-2])
    assert "đi 3 ngày" not in joined and "câu 2 " not in joined and "câu 12 " not in joined  # the first 12 turns went at once
    assert "câu 13 " in joined and "câu 30 " in joined
    assert '"days": {"value": 3' in msgs[-2]["content"]  # what turn 1 said lives in the state


def test_covered_question_write_mode_keeps_the_tools_prefetch_never_prepares(make_assistant):
    # a cost or stay ask Clef routed to "places" must still reach estimate_cost / find_stays
    chat = ScriptedChat(say("Ok."))
    run_turn(_with(make_assistant(chat), covered_tools="write"), "Gợi ý quán cà phê view đồi")
    offered = set(chat.seen[0][1])
    assert "find_places" not in offered and {"estimate_cost", "find_stays"} <= offered


def test_an_english_question_answered_in_vietnamese_is_written_again_in_english(make_assistant):
    chat = ScriptedChat(say("Bạn có thể thử ăn lẩu gà lá é nhé."), say("You could try a hot pot place at night."))
    s = run_turn(make_assistant(chat), "What should I eat in Da Lat at night?")
    assert chat.calls == 2 and "wrong_language" in system_log(s)
    assert last_say(s) == "You could try a hot pot place at night."
