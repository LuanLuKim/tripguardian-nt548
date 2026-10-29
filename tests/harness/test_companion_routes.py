import pytest

from harness import Conflict, RouteError
from test_dispatch import decision, make, run


class FakeCompanion:
    def __init__(self):
        self.synced, self.calls = [], []

    def sync(self, jid, user_id, plan):
        self.synced.append((jid, plan["value"]))

    def today(self, jid, plan, day=None):
        return {"plan_value": plan["value"], "day": day}

    def checkin(self, jid, stop_id, place_id):
        self.calls.append(("checkin", stop_id, place_id))
        return {"ok": True}

    def option(self, jid, plan, option_id):
        if option_id != "drop:b":
            raise ValueError("that option is not offered")
        return {"type": "drop_place", "place": "b"}

    def suggestions(self, jid, si, plan, place_id, disliked, similar):
        return {"place_id": place_id, "disliked": sorted(disliked)}


def confirmed():
    h, tools = make()
    h.companion = FakeCompanion()
    v = run(h, decision(h), "advance", "to-planning")
    v = run(h, v, "confirm", "confirm-1")
    return h, v


def test_confirm_makes_the_trip_and_today_reads_it():
    h, v = confirmed()
    assert h.companion.synced == [(v["id"], v["outputs"]["planning"]["value"])]
    assert h.today(v["id"], day=2) == {"plan_value": v["outputs"]["planning"]["value"], "day": 2}


def test_companion_needs_a_confirmed_plan_and_known_operations():
    h, _ = make()
    h.companion = FakeCompanion()
    v = decision(h)
    with pytest.raises(RouteError):
        h.companion_act(v["id"], "checkin", {"stop_id": "x"})
    h2, v2 = confirmed()
    with pytest.raises(RouteError):
        h2.companion_act(v2["id"], "teleport", {})
    assert h2.companion_act(v2["id"], "checkin", {"place_id": "p"}) == {"ok": True}


def test_add_and_adjust_change_the_plan_only_when_confirmed_and_valid():
    h, v = confirmed()
    with pytest.raises(ValueError):
        h.companion_act(v["id"], "add", {"place_id": "x", "day": 1})  # no confirmed: true
    before = h.load(v["id"])
    with pytest.raises(ValueError):
        h.companion_act(v["id"], "add", {"place_id": "not-in-backups", "day": 1, "confirmed": True})
    after = h.load(v["id"])
    assert "planning" in after["outputs"] and after["revision"] == before["revision"]  # refused by Planning: no change
    with pytest.raises(ValueError):
        h.companion_act(v["id"], "adjust", {"option_id": "drop:zzz", "confirmed": True})
    out = h.companion_act(v["id"], "adjust", {"option_id": "drop:b", "confirmed": True})
    assert out["changed"] and h.load(v["id"])["revision"] == before["revision"] + 2  # act + confirm
    assert len(h.companion.synced) == 2


def test_another_owner_cannot_reach_the_companion():
    h, v = confirmed()
    with pytest.raises(KeyError):
        h.today(v["id"], owner="b" * 32)


def test_companion_off_is_a_conflict():
    h, v = confirmed()
    h.companion = None
    with pytest.raises(Conflict):
        h.today(v["id"])


# --- D.3 evening check (accept / decline / undo) ---

from conftest_eve import pending_item  # noqa: E402


def with_eve(tmp_path):
    from companion import plan_hash, stops_of
    from planning import EveStore
    h, v = confirmed()
    h.eve_store = EveStore(tmp_path)
    digest = plan_hash(stops_of(h.load(v["id"])["outputs"]["planning"]))
    return h, v, digest


def test_the_evening_check_read_is_an_empty_answer_without_a_store():
    h, v = confirmed()
    assert h.eve(v["id"]) == {"enabled": False, "pending": [], "notes": [], "undo": False}
    with pytest.raises(Conflict):  # an act is still refused
        h.eve_act(v["id"], "undo", {})
    with pytest.raises(KeyError):
        h.eve("000000000000")


def test_the_evening_check_read_before_a_plan_is_confirmed_is_empty(tmp_path):
    from planning import EveStore
    h, _ = confirmed()
    fresh = h.create()
    h.eve_store = EveStore(tmp_path)
    assert h.eve(fresh["id"]) == {"enabled": True, "pending": [], "notes": [], "undo": False}


def test_accept_applies_the_option_as_acts_then_confirm_and_can_be_undone(tmp_path):
    h, v, digest = with_eve(tmp_path)
    h.eve_store.save(v["id"], digest, {"pending": [pending_item(level=2)]})
    assert h.eve(v["id"])["pending"][0]["place_id"] == "b"
    h.eve_store.save(v["id"], digest, {"notes": [{"date": "2026-12-13", "place_id": "c", "name": "c", "level": 1,
                                                 "factor": "holiday", "text": "Dịp Quốc khánh: giờ mở cửa có thể khác"}]})
    assert h.eve(v["id"])["notes"][0]["place_id"] == "c" and h.eve(v["id"])["pending"]    # notes ride along, nothing to pick
    args = {"date": "2026-12-12", "place_id": "b", "option_id": "backup:b"}
    with pytest.raises(ValueError):
        h.eve_act(v["id"], "accept", args)                                   # not confirmed: true
    with pytest.raises(ValueError):
        h.eve_act(v["id"], "accept", {**args, "option_id": "invented"})
    before = h.load(v["id"])["revision"]
    h.eve_act(v["id"], "accept", {**args, "confirmed": True})
    assert h.load(v["id"])["revision"] == before + 2 and len(h.companion.synced) == 2   # one act + confirm
    assert h.eve(v["id"])["undo"] is True                                   # the fake plan keeps its hash
    h.eve_act(v["id"], "undo", {})
    assert h.load(v["id"])["revision"] == before + 4 and h.eve(v["id"])["undo"] is False


def test_decline_remembers_the_cause_and_a_level_3_cannot_be_declined(tmp_path):
    h, v, digest = with_eve(tmp_path)
    h.eve_store.save(v["id"], digest, {"pending": [pending_item(level=3)]})
    with pytest.raises(ValueError):
        h.eve_act(v["id"], "decline", {"date": "2026-12-12", "place_id": "b"})
    h.eve_store.save(v["id"], digest, {"pending": [pending_item(level=2)]})
    out = h.eve_act(v["id"], "accept", {"date": "2026-12-12", "place_id": "b", "option_id": "keep:b"})
    assert out["pending"] == []
    assert h.eve_store.get(v["id"], digest)["declined"] == ["rain:b:2026-12-12"]


# --- DP6: a change of arrival / departure reaches the Planning session, the confirmed plan stays ---

def test_new_arrival_and_departure_reach_the_planning_session_without_unconfirming(tmp_path):
    h, v, _ = with_eve(tmp_path)
    j = h.store.get(v["id"])
    j.outputs["planning"] = {**j.outputs["planning"], "time_budget": {"per_day": [
        {"from": "08:00", "to": "20:00"}, {"from": "08:00", "to": "20:00"}, {"from": "08:00", "to": "17:00"}]}}
    h.store.save(j)
    calls = []
    real = h.tools["planning"].apply
    h.tools["planning"].apply = lambda sid, op, payload, emit: (calls.append((op, payload)), real(sid, op, payload, emit))[1]
    out = h.eve_act(v["id"], "times", {"arrive": "14:30", "leave": "15:00"})
    assert calls == [("act", {"type": "set_day_window", "day": 0, "start": "14:30", "end": "20:00"}),
                     ("act", {"type": "set_day_window", "day": 2, "start": "08:00", "end": "15:00"})]
    assert "planning" in h.store.get(v["id"]).outputs and out["pending"] == []     # still confirmed, nothing chosen for the user
    calls.clear()
    h.eve_act(v["id"], "times", {"arrive": "14:30", "leave": "15:00"})
    assert len(calls) == 2                                                          # the override is the new truth; same times: idempotent
    for bad in ({}, {"arrive": "25:00"}, {"leave": "x"}):
        with pytest.raises(ValueError):
            h.eve_act(v["id"], "times", bad)
