"""The Agent's memo of a chat (domain/memo.py): written when the itinerary is confirmed or the chat goes quiet, only with
consent and only for turns the last memo did not read; read back by the user's next chats as a prior."""

import json
from datetime import date

from trip.agent import AgentError
from trip.api.engine import Engine, TurnInput
from trip.domain import memo
from trip.infrastructure.profile import ProfileStore
from trip.infrastructure.sessions import SessionStore
from trip.infrastructure.settings import PatternSettings
from trip_fixtures import ScriptedChat, say

TODAY = date(2026, 11, 17)
CFG = PatternSettings(enabled=True, min_sessions=3, window=8, agreement=0.75, stale_days=365, max_places=2)
UID = "user-memo-1"
WRITTEN = {"tastes": [{"text": "quán cà phê sân vườn, sáng sớm", "lean": "love", "quote": "nhiều quán cà phê đẹp"}],
           "looks": ["mộc mạc, nhiều cây xanh"], "needs": [{"text": "đau gối, tránh leo dốc", "quote": "mình đau gối"}],
           "notes": ["đi chậm, ít điểm"]}


def engine_with(catalog, cfg, tmp_path, *replies):
    store = ProfileStore(tmp_path, CFG)
    return Engine(catalog, cfg, SessionStore(None), ScriptedChat(*replies), today=lambda: TODAY, profiles=store), store


def test_a_reply_that_is_not_a_memo_is_dropped():
    assert memo.parse("```json\n" + json.dumps(WRITTEN, ensure_ascii=False) + "\n```").looks == ("mộc mạc, nhiều cây xanh",)
    assert memo.parse("Mình đã tóm tắt xong.") is None
    assert memo.parse('{"tastes": [{"text": "x", "lean": "adore"}]}') is None  # outside the schema


def test_earlier_memos_read_as_one_short_prior_newest_first():
    new = memo.Memo.model_validate(WRITTEN)
    old = memo.Memo.model_validate({"tastes": [{"text": "Quán cà phê sân vườn, sáng sớm", "lean": "like"},
                                               {"text": "chợ đêm", "lean": "avoid"}]})
    got = memo.remembered([new, old])
    assert got["tastes"] == ["quán cà phê sân vườn, sáng sớm (love)", "chợ đêm (avoid)"]  # the newer wins a repeat
    assert got["needs"] == ["đau gối, tránh leo dốc"] and memo.remembered([]) is None


def test_a_broken_memo_on_disk_is_dropped_alone(tmp_path):
    store = ProfileStore(tmp_path, CFG)
    store.put_memo(UID, "s1", TODAY, 3, memo.Memo.model_validate(WRITTEN))
    store.note(UID, "trip1", TODAY, {"place:p1": "love"})
    path = tmp_path / f"{UID}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["memos"]["s2"] = {"day": "2026-11-18", "upto": "x", "memo": {}}
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    assert store.memo_upto(UID, "s1") == 3 and store.memo_upto(UID, "s2") == -1
    assert store.history(UID)[0].votes == {"place:p1": "love"}  # the votes beside it are kept
    store.pause(UID, True)
    assert store.memos(UID) == []


def test_remember_needs_consent_and_new_turns_and_the_next_chat_reads_it(catalog, cfg, tmp_path):
    engine, store = engine_with(catalog, cfg, tmp_path, say("Đà Lạt nhiều quán vườn lắm."),
                                say(json.dumps(WRITTEN, ensure_ascii=False)), say("Ok."), say("Chào bạn."))
    sid = engine.create("first", "nothing", UID, True)["id"]
    engine.turn(sid, TurnInput(kind="text", text="Mình muốn sống chậm, nhiều quán cà phê đẹp, mình đau gối"), lambda *_: None)
    s = engine.store.get(sid)
    assert engine.remember(sid, s.state, s.transcript) is True
    sent = engine.chat.seen[-1][0]
    assert sent[0]["content"] == memo.PROMPT and "nhiều quán cà phê đẹp" in sent[1]["content"]
    assert store.memo(UID, sid).needs[0].text == "đau gối, tránh leo dốc"
    calls = engine.chat.calls
    assert engine.remember(sid, s.state, s.transcript) is False and engine.chat.calls == calls  # nothing new: no call
    no = engine.create("first", "nothing", UID, False)["id"]
    n = engine.store.get(no)
    assert engine.remember(no, n.state, n.transcript) is False  # no consent
    other = engine.create("first", "nothing", UID, True)["id"]
    engine.turn(other, TurnInput(kind="text", text="đi Đà Lạt"), lambda *_: None)
    context = "\n".join(m["content"] for m in engine.chat.seen[-1][0] if m["role"] == "user")
    assert '"remembered"' in context and "đau gối, tránh leo dốc" in context


def test_a_failed_memo_call_writes_nothing(catalog, cfg, tmp_path):
    engine, store = engine_with(catalog, cfg, tmp_path, say("Ok."))
    sid = engine.create("first", "nothing", UID, True)["id"]
    engine.turn(sid, TurnInput(kind="text", text="đi Đà Lạt ngắm đồi"), lambda *_: None)
    engine.chat.error = AgentError("down")
    s = engine.store.get(sid)
    assert engine.remember(sid, s.state, s.transcript) is False and store.memo(UID, sid) is None
