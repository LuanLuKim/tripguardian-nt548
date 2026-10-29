"""The Lịch trình chatbot on the shared assistant core (docs/PLANNING.md §Trợ lý, spec 2026-10-30 planning-assistant):
the shared loop with Planning's tools; every edit is the button's own Engine.act; the turn is ONE plan version. The model is
scripted; nothing here calls it."""

import json

from langchain_core.messages import AIMessageChunk
from plan_fixtures import CFG, FakeLive, LODGING, fake_matrix, no_geocode, sample_trip

from agents.assistant import REGISTRY
from planning import tool_schemas
from planning.engine import Engine
from planning.session import Store


def fake_route(points, mode, live_cfg):
    return {"points": [list(p) for p in points], "source": "osrm", "fetched_at": "t"}


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

    async def __call__(self, messages, tools, on_say):
        self.seen.append((list(messages), [t.name for t in tools]))
        if not self.replies:
            from agents import AgentError
            raise AgentError("script ended")
        r = self.replies.pop(0)
        if r.text:
            on_say(r.text)
        return r


def started(chat, cfg=CFG):
    d, recs = sample_trip()
    e = Engine(recs + LODGING, cfg=cfg, live_cfg=FakeLive(), store=Store(None), geocode_fn=no_geocode, matrix_fn=fake_matrix,
               sun_fn=lambda *a: (360, 1050), route_fn=fake_route, background=False, assistant=chat)
    sid = e.create(d, None)["id"]
    e.act(sid, {"type": "pick_variant", "id": e.variants(sid)[0]["id"]})
    return e, sid


def turn(e, sid, text):
    events = []
    e.turn(sid, text, lambda ev, d: events.append((ev, d)))
    return events


def said(events):
    return next(d for ev, d in events if ev == "say")["replace"]


def tool_results(messages):
    return [json.loads(m["content"]) for m in messages if m["role"] == "tool"]


def day_of(e, sid, pid):
    return next(i for i, d in enumerate(e.load(sid)["view"]["itinerary"])
                if any(it.get("place_id") == pid for it in d["items"]))


def other_day(e, sid, pid):
    return 1 - day_of(e, sid, pid)


# ---------- tools are registered for the planning stage only ----------

def test_planning_tools_are_registered_with_their_words_and_stay_out_of_other_stages():
    names = {"plan", "stop", "why_here", "diagnostics", "options", "spare_places", "preview_edit", "local_facts",
             "move_place", "reorder_day", "swap_place", "add_place", "remove_place", "lock_place", "unlock_place", "set_pace",
             "set_day_window", "set_visit_minutes", "extend_days", "pick_option", "undo_turn"}
    assert names <= set(REGISTRY.names("planning", {"assistant"}))
    assert not names & set(REGISTRY.names("trip", {"assistant", "cards", "web"}))
    assert not names & set(REGISTRY.names("decision", {"assistant"}))
    for n in names:
        model = REGISTRY.get(n).model
        assert (model.__doc__ or "").strip() and model.model_config.get("extra") == "forbid"
    assert tool_schemas.MovePlace.tool_name == "move_place"
    assert "relax" not in REGISTRY.names("planning", {"assistant"})          # no path relaxes a rule
    assert "confirm" not in REGISTRY.names("planning", {"assistant"})        # the product ends at the user's confirm


# ---------- writes ----------

def test_a_named_stop_moves_with_one_version_and_the_effect_goes_back_to_the_model():
    e, sid = started(None)
    pid = "c1"
    target = other_day(e, sid, pid)
    chat = Script(reply(call("move_place", place=pid, day=target + 1, quote="chuyển c1 sang")),
                  say("Mình đã chuyển c1 sang ngày khác."))
    e.assistant = chat
    before = e._get(sid).position
    events = turn(e, sid, "chuyển c1 sang ngày khác nhé")
    s = e._get(sid)
    assert s.position == before + 1 and day_of(e, sid, pid) == target
    assert [ev for ev, _ in events] == ["say", "view", "done"]
    assert said(events) == "Mình đã chuyển c1 sang ngày khác."
    result = tool_results(chat.seen[1][0])[0]
    assert result["done"] == "move_place" and {d["day"] for d in result["effect"]["days_changed"]} >= {target + 1}
    diff = next(d for ev, d in events if ev == "view")["diff"]
    assert diff["scope"] == "relayout" and {d["day"] for d in diff["days"]} >= {target + 1}


def test_a_quote_that_is_not_in_the_message_changes_nothing():
    e, sid = started(None)
    e.assistant = chat = Script(reply(call("remove_place", place="c1", quote="bỏ c1 đi")), say("Okay."))
    before = e._get(sid).position
    turn(e, sid, "c1 có vẻ xa đó")
    assert e._get(sid).position == before and not e._get(sid).state.dropped
    assert "quote" in tool_results(chat.seen[1][0])[0]["error"]


def test_a_stop_the_user_did_not_name_or_point_at_is_not_touched():
    e, sid = started(None)
    e.assistant = chat = Script(reply(call("remove_place", place="c3", quote="bỏ bớt đi")), say("Bạn muốn bỏ chỗ nào?"))
    turn(e, sid, "bỏ bớt đi")
    assert not e._get(sid).state.dropped
    assert "did not name" in tool_results(chat.seen[1][0])[0]["error"]


def test_two_edits_in_one_message_are_one_version_and_one_undo_and_replay_the_same():
    e, sid = started(None)
    pid = "c1"
    target = other_day(e, sid, pid)
    e.assistant = Script(reply(call("move_place", place=pid, day=target + 1, quote="chuyển c1")),
                         reply(call("lock_place", place="c4", quote="khóa c4")),
                         say("Mình đã chuyển c1 và khóa c4."))
    position = e._get(sid).position
    turn(e, sid, "chuyển c1 sang ngày kia và khóa c4 luôn")
    s = e._get(sid)
    assert s.position == position + 1 and s.log[-1]["action"]["type"] == "batch" and len(s.log[-1]["action"]["acts"]) == 2
    assert "c4" in s.state.locked and day_of(e, sid, pid) == target
    shown = e.load(sid)["view"]["itinerary"]
    # a restart: a fresh engine rebuilds the session from states + log, replaying the batch
    again = Engine(e.records, cfg=CFG, live_cfg=FakeLive(), store=e.store, geocode_fn=no_geocode, matrix_fn=fake_matrix,
                   sun_fn=lambda *a: (360, 1050), route_fn=fake_route, background=False)
    assert again.load(sid)["view"]["itinerary"] == shown
    e.act(sid, {"type": "undo"})
    assert e._get(sid).state.locked == [] and e._get(sid).position == position


def test_an_edit_that_leaves_a_soft_flag_is_applied_and_the_flag_is_reported():
    """docs/PLANNING.md: what a move or reorder breaks stays flagged on its row, never blocks (spec 2026-10-15 §8)."""
    e, sid = started(None)
    e.act(sid, {"type": "set_day_window", "day": 0, "start": "08:00", "end": "10:00"})   # a short first day
    position = e._get(sid).position
    day1 = day_of(e, sid, "s1")
    assert day1 != 0
    e.assistant = chat = Script(reply(call("move_place", place="s1", day=1, quote="chuyển s1 sang ngày 1")),
                                say("Mình đã chuyển s1 sang ngày 1, ngày đó sẽ quá giờ."))
    events = turn(e, sid, "chuyển s1 sang ngày 1")
    result = tool_results(chat.seen[1][0])[0]
    assert "error" not in result and result["done"] == "move_place"
    assert result["flagged"][0]["rule"] == "day_window" and result["flagged"][0]["day"] == 1
    assert result["effect"]["confirmable"] is False
    assert e._get(sid).position == position + 1 and day_of(e, sid, "s1") == 0
    assert [ev for ev, _ in events] == ["say", "view", "done"]


def test_an_edit_that_breaks_a_physical_rule_is_taken_back_and_reported(monkeypatch):
    e, sid = started(None)
    position, shown = e._get(sid).position, e.load(sid)["view"]["itinerary"]
    day1 = day_of(e, sid, "s1")
    real = e.act

    def act(sid_, action):   # the engine lays the day out as usual, then a physical violation shows up
        out = real(sid_, action)
        if action["type"] == "move_place":
            out["view"]["violations"] = [*out["view"].get("violations", []), {"kind": "departure", "day": 1, "place_id": None,
                                                                              "minutes": 20, "physical": True,
                                                                              "detail": "misses the departure"}]
        return out
    monkeypatch.setattr(e, "act", act)
    e.assistant = chat = Script(reply(call("move_place", place="s1", day=other_day(e, sid, "s1") + 1, quote="chuyển s1 sang ngày khác")),
                                say("Mình chưa chuyển được vì lỡ giờ rời."))
    turn(e, sid, "chuyển s1 sang ngày khác")
    result = tool_results(chat.seen[1][0])[0]
    assert "error" in result and result["would_break"][0]["rule"] == "departure" and result["physical"] is True
    assert e._get(sid).position == position and day_of(e, sid, "s1") == day1
    assert e.load(sid)["view"]["itinerary"] == shown


def test_a_reorder_is_applied_and_reports_what_it_leaves_flagged():
    e, sid = started(None)
    day = day_of(e, sid, "s1")
    order = [st["place_id"] for st in e.load(sid)["view"]["itinerary"][day]["items"] if st["kind"] == "visit" and st.get("place_id")]
    assert len(order) >= 2
    e.assistant = chat = Script(reply(call("reorder_day", day=day + 1, order=order[::-1], quote="đảo thứ tự ngày")), say("Xong."))
    position = e._get(sid).position
    turn(e, sid, "đảo thứ tự ngày")
    result = tool_results(chat.seen[1][0])[0]
    assert "error" not in result, result
    assert e._get(sid).position == position + 1


def test_undo_takes_back_the_whole_last_typed_turn():
    e, sid = started(None)
    target = other_day(e, sid, "c1")
    e.assistant = Script(reply(call("move_place", place="c1", day=target + 1, quote="chuyển c1")), say("Xong."))
    turn(e, sid, "chuyển c1 sang ngày kia")
    moved = day_of(e, sid, "c1")
    e.assistant = Script(reply(call("undo_turn", quote="hoàn tác")), say("Mình đã hoàn tác."))
    events = turn(e, sid, "hoàn tác đi")
    assert day_of(e, sid, "c1") != moved and said(events) == "Mình đã hoàn tác."


def test_undo_is_refused_when_nothing_was_changed_before():
    e, sid = started(None)
    e.act(sid, {"type": "undo"})
    e.assistant = chat = Script(reply(call("undo_turn", quote="hoàn tác")), say("Chưa có gì để hoàn tác."))
    turn(e, sid, "hoàn tác")
    assert "nothing to undo" in tool_results(chat.seen[1][0])[0]["error"] or e._get(sid).position == 0


def test_a_bad_day_is_an_error_not_a_change():
    e, sid = started(None)
    e.assistant = chat = Script(reply(call("move_place", place="c1", day=9, quote="c1 sang ngày 9")), say("Chuyến chỉ có 2 ngày."))
    position = e._get(sid).position
    turn(e, sid, "dời c1 sang ngày 9")
    assert e._get(sid).position == position and "outside the trip" in tool_results(chat.seen[1][0])[0]["error"]


# ---------- reads ----------

def test_plan_and_diagnostics_read_the_plan_the_screen_shows():
    e, sid = started(None)
    e.assistant = chat = Script(reply(call("plan")), reply(call("diagnostics")), say("Lịch của bạn ổn."))
    position = e._get(sid).position
    turn(e, sid, "lịch hiện giờ ổn không")
    plan, diag = tool_results(chat.seen[2][0])
    assert {st["id"] for d in plan["days"] for st in d["stops"]} == {"c1", "c2", "c3", "c4", "s1", "s2", "s3", "r1"} - set(
        p["place_id"] for p in e.load(sid)["view"]["unplaced"])
    assert all(set(st) >= {"alias", "id", "name", "start", "end"} for d in plan["days"] for st in d["stops"])
    assert "violations" in diag and e._get(sid).position == position


def test_why_here_says_where_a_dropped_place_went():
    e, sid = started(None)
    e.act(sid, {"type": "drop_place", "place": "c4", "reason": "far"})
    e.assistant = chat = Script(reply(call("why_here", place="c4")), say("Bạn đã bỏ nơi đó vì xa."))
    turn(e, sid, "sao c4 không còn trong lịch")
    r = tool_results(chat.seen[1][0])[0]
    assert r["in_plan"] is False and r["left_out"] == {"by": "the user", "reason": "far"}


def test_preview_edit_saves_nothing():
    e, sid = started(None)
    target = other_day(e, sid, "c1")
    e.assistant = chat = Script(reply(call("preview_edit", kind="move", place="c1", day=target + 1)), say("Nếu chuyển thì vẫn ổn."))
    position = e._get(sid).position
    turn(e, sid, "nếu chuyển c1 sang ngày kia thì sao")
    r = tool_results(chat.seen[1][0])[0]
    assert r["would_do"] == "move_place" and "confirmable" in r and e._get(sid).position == position


# ---------- the reply ----------

def test_a_number_nobody_gave_is_cut_from_the_reply():
    e, sid = started(None)
    e.assistant = Script(reply(call("plan")), say("Lịch có 37 điểm dừng. Mọi thứ vẫn ổn."), say("Lịch có 37 điểm dừng. Mọi thứ vẫn ổn."))
    events = turn(e, sid, "tóm tắt lịch giúp mình")
    assert "37" not in said(events) and "ổn" in said(events)


def test_times_from_the_plan_may_be_said():
    e, sid = started(None)
    first = e.load(sid)["view"]["itinerary"][0]["items"]
    start = next(it["start"] for it in first if it["kind"] == "visit")
    e.assistant = Script(reply(call("plan")), say(f"Điểm đầu tiên bắt đầu lúc {start}."))
    assert start in said(turn(e, sid, "mấy giờ bắt đầu"))


def test_the_session_keeps_the_typed_turns_for_the_next_prompt():
    e, sid = started(None)
    e.assistant = Script(say("Chào bạn, mình đang xem lịch."), say("Mình vẫn ở đây."))
    turn(e, sid, "chào")
    chat = e.assistant
    e.assistant = second = Script(say("Mình vẫn ở đây."))
    turn(e, sid, "còn đó không")
    msgs = second.seen[0][0]
    assert {"role": "user", "content": "chào"} in msgs and {"role": "assistant", "content": "Chào bạn, mình đang xem lịch."} in msgs
    assert e._get(sid).chat[-1] == {"text": "còn đó không", "say": "Mình vẫn ở đây."}


def test_the_model_failing_falls_back_to_the_keyword_policy():
    from agents import AgentError

    class Broken:
        async def __call__(self, messages, tools, on_say):
            raise AgentError("down")
    e, sid = started(Broken())
    events = turn(e, sid, "nhanh lên đi, đi dày hơn")
    assert e.load(sid)["view"]["state"]["pace_override"] == "packed"
    assert [ev for ev, _ in events] == ["say", "view", "done"]


def test_assistant_off_keeps_the_older_agent_path():
    e, sid = started(None)
    events = turn(e, sid, "xin chào")
    assert [ev for ev, _ in events][-2:] == ["view", "done"]
