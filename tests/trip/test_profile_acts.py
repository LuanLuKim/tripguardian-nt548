"""DP2 + implicit learning (owner decision 11): acts from Decision / Planning are weak evidence in the profile; a card
pick of a need is a low-confidence prior; a contradiction weakens an entry, never deletes it."""

from datetime import date, timedelta


from trip.domain.patterns import Summary, acts_votes, detect, entries, observe, seed
from trip.domain.state import Evidence, TripState, Update, apply
from trip.infrastructure.profile import ProfileStore
from trip.infrastructure.settings import PatternSettings

TODAY = date(2026, 10, 29)
CFG = PatternSettings(enabled=True, min_sessions=3, window=8, agreement=0.75, stale_days=365, max_places=2)
UID = "user-acts-1"


def put(state, field, value, source="user", quote="x", tool=None, op="set"):
    return apply(state, Update(field=field, op=op, value=value, source=source, confidence="high",
                               evidence=Evidence(turn=1, quote=quote, tool=tool)))


def test_acts_map_to_weak_place_votes_and_dropped_without_reason_is_nothing():
    got = acts_votes([{"kind": "kept_in_plan", "place_id": "p1"}, {"kind": "rated_hop", "place_id": "p2", "value": 1},
                      {"kind": "rated_hop", "place_id": "p3", "value": -1},
                      {"kind": "dropped", "place_id": "p4", "reason": "dislike"},
                      {"kind": "dropped", "place_id": "p5", "reason": None},
                      {"kind": "dropped", "place_id": "p6", "reason": "too_far"},
                      {"kind": "rated_hop", "place_id": "p7", "value": None}])
    assert got == {"place:p1": "kept", "place:p2": "love", "place:p3": "avoid", "place:p4": "avoid"}


def test_kept_in_plan_is_never_love_and_never_replaces_a_rating():
    assert acts_votes([{"kind": "kept_in_plan", "place_id": "p1"}]) == {"place:p1": "kept"}
    assert acts_votes([{"kind": "rated_hop", "place_id": "p1", "value": 1}, {"kind": "kept_in_plan", "place_id": "p1"}]) \
        == {"place:p1": "love"}  # an explicit rating is not undone by the plan being kept again


def test_kept_places_are_a_neutral_candidate_that_reads_as_kept_not_liked(catalog):
    pid = catalog.places[0].id
    h = [Summary(sid=f"a{i}", day=TODAY - timedelta(days=i), votes={f"place:{pid}": "kept"}, how={f"place:{pid}": "acted"})
         for i in range(8)]
    (e,) = entries(h, cfg=CFG, today=TODAY, catalog=catalog)
    assert (e.value, e.status, e.used) == ("kept", "candidate", False)
    assert e.statement == f"Đã giữ {catalog.places[0].name} trong lịch"
    assert detect(h, CFG, TODAY) == [] and seed(TripState(), detect(h, CFG, TODAY), catalog, CFG).meta.prior == ()


def test_kept_never_counts_for_or_against_a_place_the_user_picked():
    h = [Summary(sid=f"s{i}", day=TODAY - timedelta(days=10 - i), votes={"place:p1": "love"}, how={"place:p1": "picked"})
         for i in range(3)]
    h += [Summary(sid=f"k{i}", day=TODAY - timedelta(days=i), votes={"place:p1": "kept"}, how={"place:p1": "acted"})
          for i in range(4)]
    by = {(e.key, e.value): e for e in entries(h, cfg=CFG, today=TODAY)}
    assert by[("place:p1", "love")].status == "active" and by[("place:p1", "love")].against == 0
    assert len(by[("place:p1", "love")].evidence) == 3  # the kept sessions are no proof of liking


def test_a_later_act_on_the_same_place_replaces_the_earlier_one():
    assert acts_votes([{"kind": "kept_in_plan", "place_id": "p1"}, {"kind": "rated_hop", "place_id": "p1", "value": -1}]) \
        == {"place:p1": "avoid"}


def test_acted_only_entries_are_never_used_nor_read_as_liked(catalog):
    pid = catalog.places[0].id
    h = [Summary(sid=f"a{i}", day=TODAY - timedelta(days=i), votes={f"place:{pid}": "love"}, how={f"place:{pid}": "acted"})
         for i in range(8)]
    (e,) = entries(h, cfg=CFG, today=TODAY, catalog=catalog)
    assert e.status == "candidate" and not e.used
    assert "Thích" not in e.statement and catalog.places[0].name in e.statement
    assert detect(h, CFG, TODAY) == []
    h.append(Summary(sid="p", day=TODAY, votes={f"place:{pid}": "love"}, how={f"place:{pid}": "picked"}))
    (e,) = entries(h, cfg=CFG, today=TODAY, catalog=catalog)
    assert e.statement.startswith("Thích")


def test_acted_votes_are_half_a_session_for_a_mixed_entry():
    h = [Summary(sid="s0", day=TODAY - timedelta(days=9), votes={"place:p1": "love"}, how={"place:p1": "picked"})]
    h += [Summary(sid=f"a{i}", day=TODAY - timedelta(days=i), votes={"place:p1": "love"}, how={"place:p1": "acted"})
          for i in range(3)]  # 1 + 1.5 = 2.5 < 3
    assert entries(h, cfg=CFG, today=TODAY)[0].status == "candidate"
    h.append(Summary(sid="a9", day=TODAY, votes={"place:p1": "love"}, how={"place:p1": "acted"}))
    assert entries(h, cfg=CFG, today=TODAY)[0].status == "active"  # 3.0


def test_a_rating_against_a_stored_place_weakens_it_without_deleting_it():
    h = [Summary(sid=f"s{i}", day=TODAY - timedelta(days=10 - i), votes={"place:p1": "love"}, how={"place:p1": "picked"})
         for i in range(3)]
    assert [e.status for e in entries(h, cfg=CFG, today=TODAY)] == ["active"]
    h.append(Summary(sid="acts:x", day=TODAY, votes={"place:p1": "avoid"}, how={"place:p1": "acted"}))
    by = {(e.key, e.value): e for e in entries(h, cfg=CFG, today=TODAY)}
    assert by[("place:p1", "love")].status == "weak" and not by[("place:p1", "love")].used
    assert by[("place:p1", "love")].against == 1  # still listed, evidence kept


def test_store_note_merges_into_one_acts_session_and_respects_delete(tmp_path):
    store = ProfileStore(tmp_path, CFG)
    store.note(UID, "trip1", TODAY, {"place:p1": "love"})
    store.note(UID, "trip1", TODAY, {"place:p2": "avoid", "place:p1": "avoid"})
    (s,) = store.history(UID)
    assert s.sid == "acts:trip1" and s.votes == {"place:p1": "avoid", "place:p2": "avoid"}
    assert set(s.how.values()) == {"acted"}
    (e,) = [e for e in store.entries(UID, TODAY)[1] if e.key == "place:p2"]
    assert store.delete(UID, e.id)
    assert "place:p2" not in store.history(UID)[0].votes


def test_a_card_picked_need_is_stored_as_a_low_confidence_prior_never_a_constraint(catalog):
    s = put(TripState(), "signal", "vegetarian", quote="deck:care", tool="deck:care", op="add")
    assert observe(s) == {"need:vegetarian": ("yes", "picked", None)}
    h = [Summary(sid="a", day=TODAY, votes={"need:vegetarian": "yes"}, how={"need:vegetarian": "picked"})]
    (p,) = detect(h, CFG, TODAY)
    assert p.confidence == "low"
    seeded = seed(TripState(), [p], catalog, CFG)
    assert seeded.signals == () and seeded.hard == ()
    assert all(f.source == "profile" and f.confidence == "low" for f in seeded.soft.values())


def test_the_app_own_strictest_answer_is_not_a_need_vote():
    s = put(TripState(), "signal", "vegetarian", quote="next:strictest", tool="next:strictest", op="add")
    assert observe(s) == {}


# ---------- Engine.note_acts: written only with the trip's own consent ----------

def _engine(catalog, cfg, tmp_path):
    from trip_fixtures import ScriptedChat
    from trip.agent import AgentError
    from trip.api.engine import Engine
    from trip.infrastructure.sessions import SessionStore
    store = ProfileStore(tmp_path, CFG)
    return Engine(catalog, cfg, SessionStore(None), ScriptedChat(error=AgentError("down")), today=lambda: TODAY,
                  profiles=store), store


def test_note_acts_needs_remember_and_the_same_user(catalog, cfg, tmp_path):
    engine, store = _engine(catalog, cfg, tmp_path)
    acts = [{"kind": "kept_in_plan", "place_id": "p1"}]
    yes = engine.create("first", "nothing", UID, True)["id"]
    no = engine.create("first", "nothing", UID, False)["id"]
    assert engine.note_acts(UID, no, acts) is False and store.history(UID) == []
    assert engine.note_acts("someone-else-9", yes, acts) is False
    assert engine.note_acts(UID, "nosuchsession", acts) is False
    assert engine.note_acts(UID, yes, [{"kind": "dropped", "place_id": "p1", "reason": "too_far"}]) is False
    assert engine.note_acts(UID, yes, acts) is True
    assert store.history(UID)[0].votes == {"place:p1": "kept"}


def test_store_note_keeps_an_earlier_rating_when_the_plan_is_kept_again(tmp_path):
    store = ProfileStore(tmp_path, CFG)
    store.note(UID, "trip2", TODAY, {"place:p1": "love"})  # rated
    store.note(UID, "trip2", TODAY, {"place:p1": "kept", "place:p2": "kept"})  # a later confirm of the same trip
    assert store.history(UID)[0].votes == {"place:p1": "love", "place:p2": "kept"}
