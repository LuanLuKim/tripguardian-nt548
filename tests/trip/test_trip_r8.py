"""Production companion evidence, honest acknowledgements and model-free deck skips."""
from datetime import date

import pytest

from trip_fixtures import ScriptedChat, call, reply
from trip.api.engine import Engine, TurnInput
from trip.domain import deck
from trip.domain.guard import names_group, record_fact
from trip.domain.state import TripState
from trip.infrastructure.sessions import SessionStore

PET_TEXT = "Mình đi với bạn trai và bé cún nhà mình, 21-22/11, ô tô từ Sài Gòn. Muốn quán cà phê cho chó vào và chỗ đi dạo thoải mái với cún nha."
FRIENDS_TEXT = "ae oi 6 dua tui minh di dalat 14-15/11, di o to 7 cho tu sg len, muon an nuong an lau voi cafe chill chup hinh, k thich leo doc nhieu, ngan sach tam 600k/nguoi/ngay nha"


@pytest.mark.parametrize("text,quote,who", [(PET_TEXT, "bé cún nhà mình", "pet"),
    (FRIENDS_TEXT, "6 dua tui minh", "friends"), ("đi với chó nhà mình", "chó nhà mình", "pet"),
    ("đi với con boss nhà mình", "con boss nhà mình", "pet"), ("đi với pet", "pet", "pet"),
    ("đi với anh em", "anh em", "friends"), ("bọn mình đi chơi", "bọn mình", "friends"),
    ("tụi mình đi chơi", "tụi mình", "friends"), ("ae đi chơi", "ae", "friends")])
def test_companion_evidence_accepts_everyday_words(catalog, text, quote, who):
    state, note = record_fact(TripState(), "companions", "add", who, quote, "said", text, 1, catalog)
    assert not note
    assert who in state.companions.value


@pytest.mark.parametrize("text,who", [("ăn hot dog", "pet"), ("ghé quán Chó Điên", "pet"),
    ("cà phê Mèo Lười", "pet"), ("Mèo Lười", "pet"), ("Chó Điên", "pet"),
    ("cho mình", "pet"), ("đi với con boss công ty", "pet"), ("mình thích chó", "pet"), ("không mang chó", "pet"),
    ("đi cùng bạn trai", "friends"), ("6 đứa nhỏ", "friends"), ("6 dua nho", "friends")])
def test_companion_evidence_does_not_turn_food_places_or_children_into_companions(text, who):
    assert not names_group(text, who, allow_generic=False)


def test_solo_with_cat_keeps_both_without_calling_them_friends(catalog):
    text = "đi một mình với con mèo"
    state = TripState()
    for who in ("solo", "pet"):
        state, note = record_fact(state, "companions", "add", who, text, "said", text, 1, catalog)
        assert not note
    assert state.companions.value == {"solo", "pet"}
    from trip.domain.derive import derive
    assert derive(state, catalog, 1).people.value == 1


def test_solo_pet_deck_does_not_count_the_pet_as_a_person(catalog, cfg):
    engine, session, chat = make_engine(catalog, cfg)
    session.card = deck.build(session.state, catalog, cfg, ask="companions")
    events = []
    engine.turn(session.id, TurnInput(kind="deck", answers={"companions.who": ["solo", "pet"], "companions.people": ["1"]}),
                lambda *event: events.append(event))
    assert session.state.people.value == 1
    assert session.state.companions.value == {"solo", "pet"}
    assert not any(event == "deck_issues" for event, _ in events)


def test_pet_tool_protects_same_turn_search(turn_tools):
    tools = turn_tools(text=PET_TEXT)
    out = tools.run("record_fact", {"field": "companions", "op": "add", "value": "pet", "quote": "bé cún nhà mình", "how": "said"})
    assert out.get("ok")
    assert any(h.feature == "pets" for h in tools.state.hard)


def test_refused_pet_cannot_be_acknowledged_even_after_partner_is_recorded(turn_tools):
    tools = turn_tools(text="Mình đi với bạn trai, thích quán Mèo Lười")
    tools.run("record_fact", {"field": "companions", "op": "add", "value": "pet", "quote": "quán Mèo Lười", "how": "said"})
    tools.run("record_fact", {"field": "companions", "op": "add", "value": "partner", "quote": "bạn trai", "how": "said"})
    assert tools.rejected_claim("Mình ghi nhận bạn đi cùng bạn trai và bé cún.")
    assert not tools.rejected_claim("Mình đã ghi bạn đi cùng bạn trai.")
    assert not tools.rejected_claim("Mình chưa ghi nhận bạn mang thú cưng.")


def test_pet_companion_creates_safety_filter_and_survives_handoff(catalog):
    from trip.domain.derive import derive
    from trip.domain.compile import compile_search_input
    state, note = record_fact(TripState(), "companions", "add", "pet", "bé cún nhà mình", "said", PET_TEXT, 1, catalog)
    assert not note
    state = derive(state, catalog, 1)
    si = compile_search_input(state)
    assert "pet" in si.context.companions
    assert any(h.feature == "pets" and h.op == "ne" and h.value == "not_allowed" for h in si.hard_filters)


def make_engine(catalog, cfg):
    chat = ScriptedChat(reply(text="Mình hiểu rồi."))
    engine = Engine(catalog, cfg, SessionStore(None), chat, today=lambda: date(2026, 11, 4))
    sid = engine.create("first", "nothing")["id"]
    return engine, engine.store.get(sid), chat


@pytest.mark.parametrize("kind", ["agent", "drill", "required"])
def test_skip_only_deck_never_calls_model(catalog, cfg, kind):
    from trip.domain.state import Tab, Option
    engine, session, chat = make_engine(catalog, cfg)
    tab = Tab(qid="test" if kind != "required" else "trip", kind=kind, header="Kiểu quán", question="Bạn thích gì?",
              options=(Option(id="v0", label="Yên tĩnh"), *deck.exits()))
    if kind == "required":
        session.card = deck.build(session.state, catalog, cfg, ask="trip")
    elif kind == "drill":
        from trip.domain.state import Drill
        tab = tab.model_copy(update={"qid": "drill.chill"})
        session.state = session.state.model_copy(update={"drills": (Drill(topic="chill", quote="chill", turn=0, tab=tab),)})
        session.card = deck.build(session.state, catalog, cfg)
    else:
        from trip.domain import ask
        tab = ask.check([{"header": "Kiểu quán", "question": "Bạn thích quán kiểu nào?", "options": [
            {"label": label, "writes": [{"field": "soft", "op": "add", "value": key + ":love"}]}
            for label, key in (("Yên tĩnh", "noise=quiet"), ("Nhạc sống", "live_music=present"))]}], session.state, catalog, cfg)[0]
        session.card = deck.build(session.state, catalog, cfg, agent=(tab,))
    qid = session.card.tabs[0].qid
    events = []
    engine.turn(session.id, TurnInput(kind="deck", answers={qid: ["skip"]}), lambda *event: events.append(event))
    assert chat.calls == 0
    assert qid in session.state.meta.declined
    assert session.card.qid == "conversation"
    assert not any(t.get("kind") == "required" for t in engine.load(session.id)["card"].get("tabs", []))
    assert any(event == "say" for event, _ in events)


def test_skip_with_typed_words_still_calls_agent(catalog, cfg):
    engine, session, chat = make_engine(catalog, cfg)
    session.card = deck.build(session.state, catalog, cfg, ask="trip")
    engine.turn(session.id, TurnInput(kind="deck", answers={"trip": ["skip"]}, text="mình muốn cà phê"), lambda *_: None)
    assert chat.calls > 0


def test_cold_drill_defers_without_running_semantic_search(catalog, cfg):
    from dataclasses import replace
    from trip.domain import drill
    from trip.infrastructure.looks import Looks
    from unittest.mock import Mock
    looks = Looks(catalog, warm=False)
    looks._score = Mock(side_effect=AssertionError("semantic encoder in chat turn"))
    cfg = replace(cfg, drills={"chill": {"header": "Chill", "question": "Bạn thích gì?", "variants": [
        {"label": "Yên", "cues": ["yên tĩnh"], "writes": [{"field": "soft", "value": "noise=quiet:love"}]},
        {"label": "Nhạc", "cues": ["nhạc sống"], "writes": [{"field": "soft", "value": "live_music=present:love"}]}]}})
    state = drill.note(TripState(), "chill", 1)
    after = drill.build(state, catalog, looks, cfg, cached_only=True)
    assert after.drills[0].status == "pending" and after.drills[0].tab is None
    looks._score.assert_not_called()


def test_pet_unknown_is_explicit_in_search_result(turn_tools):
    tools = turn_tools(text=PET_TEXT)
    tools.run("record_fact", {"field": "companions", "op": "add", "value": "pet", "quote": "bé cún nhà mình", "how": "said"})
    found = tools.run("find_places", {"criteria": {"groups": ["cafe"]}})
    assert found["places"]
    assert all(p["pet_policy"] == "chưa rõ có cho mang thú cưng không" for p in found["places"])


def test_unavailable_photo_index_does_not_cache_a_completed_empty_search(catalog):
    from trip.infrastructure.looks import Looks
    looks = Looks(catalog, warm=False)
    looks.scored_by_cues(["chill"])
    assert looks.cached_scores(["chill"], set(catalog.by_id)) is None


def test_transient_retrieval_failure_does_not_cache_empty_scores(catalog):
    from types import SimpleNamespace
    from trip.infrastructure.looks import Looks
    from unittest.mock import Mock
    semantic = Mock(side_effect=[RuntimeError("temporarily unavailable"), [SimpleNamespace(place_id=catalog.places[0].id, score=0.8)]])
    looks = Looks(catalog, warm=False, retrieval=SimpleNamespace(semantic=semantic))
    assert looks.scored_by_cues(["chill"]) == []
    assert looks.cached_scores(["chill"], set(catalog.by_id)) is None
    assert looks.scored_by_cues(["chill"]) == [(catalog.places[0].id, 0.8)]


def test_empty_drill_scores_are_cached(catalog):
    from trip.infrastructure.looks import Looks
    from unittest.mock import Mock
    looks = Looks(catalog, warm=False)
    looks._score = Mock(return_value=[])
    assert looks.scored_by_cues(["no photo"]) == []
    assert looks.scored_by_cues(["no photo"]) == []
    assert looks._score.call_count == 1


def test_reply_guard_replaces_false_saved_pet_claim(catalog, cfg):
    text = "Mình đi với bạn trai và bé cún nhà mình"
    chat = ScriptedChat(reply(call("record_fact", facts=[
        {"field": "companions", "op": "add", "value": "partner", "quote": "bạn trai", "how": "said"},
        {"field": "companions", "op": "add", "value": "pet", "quote": "mèo", "how": "said"}])),
        reply(call("record_fact", field="unmapped", op="add", value="bé cún nhà mình", quote="bé cún nhà mình", how="said"),
              text="Mình ghi nhận bạn đi cùng bạn trai và bé cún."))
    engine = Engine(catalog, cfg, SessionStore(None), chat, today=lambda: date(2026, 11, 4))
    sid = engine.create("first", "nothing")["id"]
    engine.turn(sid, TurnInput(kind="text", text=text), lambda *_: None)
    session = engine.store.get(sid)
    assert "pet" not in (session.state.companions.value or ())
    assert "ghi nhận bạn đi cùng bạn trai và bé cún" not in session.transcript[-1]["text"]
    assert any("say replaced: acknowledges refused companions=pet" in t["text"] for t in session.transcript if t["role"] == "system")


def test_other_choice_with_words_calls_agent(catalog, cfg):
    engine, session, chat = make_engine(catalog, cfg)
    session.card = deck.build(session.state, catalog, cfg, ask="mobility")
    engine.turn(session.id, TurnInput(kind="deck", answers={"mobility": ["other"]}, text="đi taxi"), lambda *_: None)
    assert chat.calls > 0


def test_skip_keeps_unanswered_agent_even_when_another_drill_is_pending(catalog, cfg):
    from trip.domain import ask
    from trip.domain.state import Drill, Tab
    engine, session, chat = make_engine(catalog, cfg)
    agent = ask.check([{"header": "Kiểu quán", "question": "Bạn thích quán kiểu nào?", "options": [
        {"label": label, "writes": [{"field": "soft", "op": "add", "value": key + ":love"}]}
        for label, key in (("Yên tĩnh", "noise=quiet"), ("Nhạc sống", "live_music=present"))]}], session.state, catalog, cfg)[0]
    drills = tuple(Drill(topic=topic, quote=topic, turn=0, tab=Tab(
        qid="drill." + topic, kind="drill", header=topic, question="Bạn thích gì?", options=deck.exits()))
        for topic in ("chill", "cafe"))
    session.state = session.state.model_copy(update={"drills": drills})
    session.card = deck.build(session.state, catalog, cfg, agent=(agent,))
    assert session.card.tabs[0].qid == "drill.chill"
    engine.turn(session.id, TurnInput(kind="deck", answers={"drill.chill": ["skip"]}), lambda *_: None)
    assert chat.calls == 0
    assert session.card.tabs[0].qid == agent.qid
    assert session.card.tabs[0].question == "Bạn thích quán kiểu nào?"
    assert engine.load(session.id)["card"]["tabs"][0]["qid"] == agent.qid
    engine.turn(session.id, TurnInput(kind="deck", answers={agent.qid: ["skip"]}), lambda *_: None)
    assert agent.qid in session.state.meta.declined and chat.calls == 0
    assert session.card.qid == "conversation"


def test_skip_only_ready_trip_offers_next_ready(catalog, cfg):
    from dataclasses import replace
    engine, session, chat = make_engine(catalog, cfg)
    engine.cfg = replace(cfg, required=("budget",))
    session.card = deck.build(session.state, catalog, engine.cfg, ask="budget")
    engine.turn(session.id, TurnInput(kind="deck", answers={"budget": ["skip"]}), lambda *_: None)
    assert chat.calls == 0 and session.card.qid == "conversation"
    assert "bấm Xem gợi ý khi sẵn sàng" in session.transcript[-1]["text"]


def test_pet_policy_is_added_to_a_read_cached_before_recording_pet(turn_tools):
    tools = turn_tools(text=PET_TEXT)
    found = tools.run("find_places", {"criteria": {"groups": ["cafe"]}})
    pid = found["places"][0]["id"]
    before = tools.run("get_place", {"id": pid})
    assert "error" not in before
    tools.run("record_fact", {"field": "companions", "op": "add", "value": "pet", "quote": "bé cún nhà mình", "how": "said"})
    after = tools.run("get_place", {"id": pid})
    assert after["place"].get("pet_policy") == "chưa rõ có cho mang thú cưng không"


def test_consecutive_skips_are_shorter_and_do_not_open_required_topics(catalog, cfg):
    engine, session, chat = make_engine(catalog, cfg)
    session.card = deck.build(session.state, catalog, cfg, ask="trip")
    engine.turn(session.id, TurnInput(kind="deck", answers={"trip": ["skip"]}), lambda *_: None)
    first = session.transcript[-1]["text"]
    session.card = deck.build(session.state, catalog, cfg, ask="mobility")
    engine.turn(session.id, TurnInput(kind="deck", answers={"mobility": ["skip"]}), lambda *_: None)
    assert len(session.transcript[-1]["text"]) < len(first)
    assert session.card.qid == "conversation" and chat.calls == 0


def test_a_taste_question_always_takes_several_answers(catalog, cfg):
    from trip.domain import ask
    engine, session, chat = make_engine(catalog, cfg)

    def tab(pairs, multi=None):
        q = {"header": "Kiểu quán", "question": "Bạn thích quán kiểu nào?", "options": [
            {"label": label, "writes": [{"field": "soft", "op": "add", "value": value}]} for label, value in pairs]}
        if multi is not None:
            q["multi"] = multi
        return ask.check([q], session.state, catalog, cfg)[0]

    assert tab((("Yên tĩnh", "noise=quiet:love"), ("Nhạc sống", "live_music=present:love")), multi=False).multi
    t = tab((("Yên tĩnh", "noise=quiet:love"), ("Nhạc sống", "live_music=present:love")))
    session.card = deck.build(session.state, catalog, cfg, agent=(t,))
    qid = session.card.tabs[0].qid
    picked = [o.id for o in t.options if o.id not in ("other", "skip")]
    events = []
    engine.turn(session.id, TurnInput(kind="deck", answers={qid: picked}), lambda *e: events.append(e))
    assert not any(ev == "deck_issues" for ev, _ in events)
    assert {"noise=quiet", "live_music=present"} <= set(session.state.soft)
