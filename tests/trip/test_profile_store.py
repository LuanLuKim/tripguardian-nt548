"""Profile entries stored, listed, edited, paused and deleted (docs/TRIP_UNDERSTANDING.md §17)."""

import json
from datetime import date, timedelta

import pytest
from trip_fixtures import ScriptedChat

from trip.agent import AgentError
from trip.api.engine import Engine, TurnInput
from trip.domain.patterns import Summary, entry_id
from trip.infrastructure.profile import ProfileStore
from trip.infrastructure.sessions import SessionStore
from trip.infrastructure.settings import PatternSettings

TODAY = date(2026, 10, 28)
CFG = PatternSettings(enabled=True, min_sessions=3, window=8, agreement=0.75, stale_days=365, max_places=2)
UID = "user-abc-123"


def fill(store, n=3, votes=None):
    for i in range(n):
        store.record(UID, Summary(sid=f"s{i}", day=TODAY - timedelta(days=10 - i),
                                  votes=votes or {"pace": "slow", "soft:crowd=low": "love"},
                                  how={"pace": "said"}, quotes={"pace": f"đi chậm {i}"}))


@pytest.fixture
def store(tmp_path):
    return ProfileStore(tmp_path, CFG)


def test_every_stored_vote_is_listed_as_an_entry(store):
    fill(store)
    store.record(UID, Summary(sid="s9", day=TODAY, votes={"novelty": "new"}))
    paused, found = store.entries(UID, TODAY)
    assert not paused
    assert {(e.key, e.value) for e in found} == {("pace", "slow"), ("soft:crowd=low", "love"), ("novelty", "new")}
    pace = next(e for e in found if e.key == "pace")
    assert pace.status == "active" and pace.evidence[-1].quote == "đi chậm 2"


def test_delete_removes_the_entry_its_evidence_and_its_effect(store, tmp_path):
    fill(store)
    eid = entry_id("pace", "slow")
    assert store.delete(UID, eid) and not store.delete(UID, eid)
    raw = (tmp_path / f"{UID}.json").read_text(encoding="utf-8")
    assert "pace" not in raw and "đi chậm" not in raw  # deleted for real: no vote, no quote left
    assert [p.key for p in store.patterns(UID, TODAY)] == ["soft:crowd=low"]


def test_a_session_left_with_no_vote_is_dropped(store):
    store.record(UID, Summary(sid="a", day=TODAY, votes={"pace": "slow"}))
    store.delete(UID, entry_id("pace", "slow"))
    assert store.history(UID) == []


def test_edit_wins_and_pause_stops_use(store):
    fill(store, n=1)
    eid = entry_id("pace", "slow")
    assert store.edit(UID, eid, statement="Mình thích đi thong thả")
    assert [p.key for p in store.patterns(UID, TODAY)] == ["pace"]  # an edit is the user's own confirmation
    assert store.edit(UID, eid, paused=True)
    assert store.patterns(UID, TODAY) == []
    e = next(e for e in store.entries(UID, TODAY)[1] if e.id == eid)
    assert e.paused and e.statement == "Mình thích đi thong thả"
    assert not store.edit(UID, "000000000000", paused=True)


def test_edit_rejects_bad_text(store):
    fill(store, n=1)
    for bad in ("", "  ", "x" * 201, 3):
        with pytest.raises(ValueError):
            store.edit(UID, entry_id("pace", "slow"), statement=bad)


def test_pausing_the_whole_profile_stops_every_prior_and_keeps_entries(store):
    fill(store)
    store.pause(UID, True)
    assert store.patterns(UID, TODAY) == [] and store.entries(UID, TODAY)[0] is True
    store.pause(UID, False)
    assert len(store.patterns(UID, TODAY)) == 2


def test_a_judge_flag_makes_the_entry_weak(store):
    fill(store)
    eid = entry_id("pace", "slow")
    assert store.flag(UID, eid, "overgeneral")
    assert [p.key for p in store.patterns(UID, TODAY)] == ["soft:crowd=low"]


def test_record_keeps_edits_flags_and_pause(store, tmp_path):
    fill(store)
    store.edit(UID, entry_id("pace", "slow"), statement="Thong thả")
    store.pause(UID, True)
    store.record(UID, Summary(sid="new", day=TODAY, votes={"novelty": "new"}))
    body = json.loads((tmp_path / f"{UID}.json").read_text(encoding="utf-8"))
    assert body["paused"] is True and entry_id("pace", "slow") in body["edits"]


def test_old_file_shape_still_reads(store, tmp_path):
    (tmp_path / f"{UID}.json").write_text(json.dumps({"sessions": [
        {"sid": f"s{i}", "day": "2026-10-20", "votes": {"pace": "slow"}} for i in range(3)]}))
    assert [p.key for p in store.patterns(UID, TODAY)] == ["pace"]


# ---------- engine ----------

@pytest.fixture
def engine(catalog, cfg, store):
    return Engine(catalog, cfg, SessionStore(None), ScriptedChat(error=AgentError("down")), today=lambda: TODAY,
                  profiles=store)


def test_engine_lists_edits_and_deletes_entries(engine, store):
    fill(store)
    view = engine.profile(UID)
    assert view["enabled"] and not view["paused"]
    pace = next(e for e in view["entries"] if e["key"] == "pace")
    assert pace["status"] == "active" and pace["used"] and pace["statement"] and pace["evidence"][0]["how"] == "said"
    assert engine.edit_entry(UID, pace["id"], {"paused": True})["paused"] is True
    with pytest.raises(ValueError):
        engine.edit_entry(UID, pace["id"], {"color": "red"})
    with pytest.raises(KeyError):
        engine.edit_entry(UID, "000000000000", {"paused": True})
    assert engine.delete_entry(UID, pace["id"]) and all(e["key"] != "pace" for e in engine.profile(UID)["entries"])
    assert engine.pause_profile(UID, True)["paused"] is True


def test_a_deleted_entry_no_longer_seeds_a_session(engine, store):
    fill(store)
    assert engine.store.get(engine.create("returning", "nothing", UID, True)["id"]).state.pace.source == "profile"
    engine.delete_entry(UID, entry_id("pace", "slow"))
    s = engine.store.get(engine.create("returning", "nothing", UID, True)["id"]).state
    assert not s.pace.known and "pace" not in s.meta.prior


def test_engine_without_learning_shows_an_empty_profile(catalog, cfg):
    e = Engine(catalog, cfg, SessionStore(None), ScriptedChat(error=AgentError("down")), today=lambda: TODAY)
    assert e.profile(UID) == {"enabled": False, "paused": False, "entries": []}
    assert e.delete_entry(UID, "000000000000") is False


def test_a_said_choice_is_remembered_with_its_quote(engine, store):
    sid = engine.create("first", "nothing", UID, True)["id"]
    events = []
    engine.turn(sid, TurnInput(kind="edit", target="pace", value="slow"), lambda e, d: events.append(e))
    engine.turn(sid, TurnInput(kind="show"), lambda e, d: events.append(e))
    (s,) = store.history(UID)
    assert s.votes == {"pace": "slow"} and s.how["pace"] in ("said", "picked")
