from copy import deepcopy

import pytest

from fixtures import feat, fit_entry, hard, love, si, srec
from corpus.serving import check, feature
from corpus.snapshot import Region
from corpus.snapshot.tables import tables
from decision import Data, Engine, Store, load_settings, run_pipeline
from decision.fit import details_fit
from decision.frame import _generic, fit_table, roles, score_table, screen_table
from decision.model import Cand
from decision.rank import preference
from decision.session import Session, State
from decision.trip_days import trip_days
from requirements import allowed, hard_result


def silence(value="absent"):
    return {**feat(value, n=0), "reason": "silence", "distribution": {}, "evidence": [],
            "by_context": {"day_type=weekend": {value: 10}}}


@pytest.mark.parametrize("fid,value", [("steep_or_stairs", "absent"), ("kids", "suitable"), ("fit.kids", "good")])
def test_silence_all_readers_match_an_empty_record_without_rebuilding(fid, value):
    rec = srec("silent", features={} if fid.startswith("fit.") else {fid: silence(value)},
               details={"fit": {"kids": silence(value)}} if fid.startswith("fit.") else None)
    # Simulate an immutable snapshot compiled by the old reader, including stale confidence/context/verdicts.
    raw = deepcopy(rec)
    f = raw["details"]["fit"]["kids"] if fid.startswith("fit.") else raw["effort" if fid == "steep_or_stairs" else "suitability"][fid]
    f["reason"], f["n"], f["evidence"] = None, 10, ["old"]
    t = tables([raw])
    import orjson
    import pyarrow as pa
    t["records"] = pa.Table.from_pylist([{"id": rec["id"], "json": orjson.dumps(rec).decode()}], schema=t["records"].schema)
    region = Region("test", t)
    assert feature(rec, fid) is None
    assert check(rec, fid, value) == "unknown"
    assert hard_result(rec, hard(fid, value, op="eq"))[0] == "unknown"
    col = region.feature(fid)
    assert col.value == [None] and not col.exists[0] and not col.firm[0] and col.conf[0] == 0
    assert region.ctx_top(fid, "day_type=weekend") == [None]
    if fid.startswith("fit."):
        assert region.verdict("kids") == ([None], [None])
        assert details_fit(rec, ["kids"], load_settings(), []) == 0
    req = si(hard_filters=[hard(fid, value, op="eq")]).hard_filters[0]
    assert _generic(region, req).tolist() == ["unknown"]


def test_silent_preference_and_fit_are_identical_to_missing():
    cfg = load_settings()
    rec = srec("same", features={"steep_or_stairs": silence()})
    missing = srec("same")
    search = si(soft_weights=[love("steep_or_stairs", "absent", context={"day_type": "weekend"})])
    ws = [("steep_or_stairs", "absent", {"day_type": "weekend"}, 1)]
    assert preference(rec, ws) == preference(missing, ws)
    a = run_pipeline(Session(id="0" * 12, search_input=search, state=State()), Data([rec]), cfg)
    b = run_pipeline(Session(id="0" * 12, search_input=search, state=State()), Data([missing]), cfg)
    assert a.cands["same"].parts == b.cands["same"].parts
    assert a.cands["same"].matches == []


@pytest.mark.parametrize("fid,good,bad", [("steep_or_stairs", "absent", "present"),
                                         ("kids", "suitable", "unsuitable"), ("fit.kids", "good", "bad")])
def test_safety_unknown_is_clean_eligible_and_after_all_passes_across_tabs_and_search(fid, good, bad):
    def record(pid, value=None, **kwargs):
        return srec(pid, name="Safety " + pid,
                    features={fid: feat(value)} if value and not fid.startswith("fit.") else {},
                    details={"fit": {"kids": fit_entry(value)}} if value and fid.startswith("fit.") else None,
                    **kwargs)
    recs = [record("unknown", voices=1000), record("pass-a", good, voices=1),
            record("pass-b", good, voices=2), record("fail", bad, voices=500)]
    search = si(hard_filters=[hard(fid, bad)], context={"experience": "first"})
    engine = Engine(Data(recs), load_settings(), Store(None))
    created = engine.create(search.model_dump(mode="json"))
    sid = created["id"]
    res = engine._result(engine.store.get(sid))
    assert res.ranked["cafe"][-1] == "unknown"
    assert set(res.ranked["cafe"][:-1]) == {"pass-a", "pass-b"}
    assert allowed(recs[0], search.hard_filters[0])
    cards = {c["id"]: c for g in created["view"]["groups"] for c in g["cards"]}
    unknown = cards["unknown"]
    assert unknown["status"] == "main" and unknown["unverified"] == []
    assert len(unknown["tradeoffs"]) == 1 and unknown["tradeoffs"][0]["text"].startswith("Chưa rõ")
    if fid.startswith("fit."):
        assert "fit.kids" not in unknown["tradeoffs"][0]["text"]
        assert "trẻ nhỏ" in unknown["tradeoffs"][0]["text"]
    assert unknown["depends_on_unknown"] is None
    assert all(not c["tradeoffs"] for pid, c in cards.items() if pid.startswith("pass"))
    assert created["view"]["unverified"]["count"] == 0
    found = engine.search(sid, "Safety")["cards"]
    assert [c["id"] for c in found][-1] == "unknown" and "fail" not in [c["id"] for c in found]
    engine.act(sid, {"type": "select", "place_id": "unknown"})
    selected = engine.load(sid)["view"]
    assert not any(x["check"].startswith("relax:") for x in selected["feasibility"]["conflicts"])


def test_unknown_safety_tradeoff_precedes_crowd_and_has_no_duplicate_alert():
    rec = srec("unknown", crowd_by_time={"weekday": {"morning": 95}})
    search = si(hard_filters=[hard("steep_or_stairs", "present"), hard("long_walk", "present")],
                pace={"crowd_tolerance": "avoid"})
    engine = Engine(Data([rec]), load_settings(), Store(None))
    view = engine.create(search.model_dump(mode="json"))["view"]
    card = view["groups"][0]["cards"][0]
    assert len(card["tradeoffs"]) == 1
    assert card["tradeoffs"][0]["text"] == "Chưa rõ có dốc, nhiều bậc; phải đi bộ xa"
    assert card["unverified"] == []


def test_non_safety_and_physical_fail_stay_closed():
    rec = srec("closed", hours={"sun": [["07:00", "10:00"]]})
    search = si(hard_filters=[hard("steep_or_stairs", "present")], context={"days": 1})
    engine = Engine(Data([rec, srec("noise")]), load_settings(), Store(None))
    assert all(c["id"] != "closed" for g in engine.create(search.model_dump(mode="json"))["view"]["groups"] for c in g["cards"])
    assert not allowed(srec("noise"), hard("noise", "loud"))


def test_chat_cards_use_safety_evidence_order_and_hide_proven_failures():
    from datetime import date
    from types import SimpleNamespace
    from decision.assistant import DecisionTurn

    recs = [srec("unknown", name="Unknown Cafe"),
            srec("pass", name="Pass Cafe", features={"steep_or_stairs": "absent"}),
            srec("fail", name="Fail Cafe", features={"steep_or_stairs": "present"})]
    engine = Engine(Data(recs), load_settings(), Store(None))
    created = engine.create(si(hard_filters=[hard("steep_or_stairs", "present")]).model_dump(mode="json"))
    session = engine.store.get(created["id"])
    reader = SimpleNamespace(knowledge=SimpleNamespace(view=lambda pid, *args: {"id": pid}))
    turn = DecisionTurn(engine, session, engine._result(session), {}, "quán nào", date(2026, 11, 4), reader)
    turn.seen_ids = ["unknown", "fail", "pass"]
    assert turn.cards("Unknown Cafe, Fail Cafe, Pass Cafe")["ids"] == ["pass", "unknown"]


def test_evaluation_distinguishes_unknown_from_a_proven_violation():
    from decision.evaluate import violates
    disputed = srec("disputed", features={"steep_or_stairs": feat("absent", dist={"absent": 3, "present": 1})})
    assert not violates(disputed, "steep_or_stairs", "present")
    assert violates(srec("fail", features={"steep_or_stairs": "present"}), "steep_or_stairs", "present")


def test_unknown_safety_owns_the_single_tradeoff_even_with_a_dietary_note():
    engine = Engine(Data([srec("restaurant", group="restaurant", usable=("meal",))]), load_settings(), Store(None))
    inp = si(hard_filters=[hard("steep_or_stairs", "present")], soft_weights=[love("vegetarian_options", "yes")])
    created = engine.create(inp.model_dump(mode="json"))
    for view in (created["view"], engine.load(created["id"])["view"]):
        card = view["groups"][0]["cards"][0]
        assert card["tradeoffs"] == [{"text": "Chưa rõ có dốc, nhiều bậc", "sid": "steep_or_stairs"}]


@pytest.mark.parametrize("other_wish", [False, True])
def test_unknown_safety_does_not_repeat_in_confidence_when_also_a_soft_wish(other_wish):
    engine = Engine(Data([srec("unknown", voices=1000)]), load_settings(), Store(None))
    wishes = [love("steep_or_stairs", "absent")]
    if other_wish:
        wishes.append(love("noise", "quiet"))
    inp = si(hard_filters=[hard("steep_or_stairs", "present")], soft_weights=wishes)
    view = engine.create(inp.model_dump(mode="json"))["view"]
    card = view["groups"][0]["cards"][0]
    assert card["tradeoffs"] == [{"text": "Chưa rõ có dốc, nhiều bậc", "sid": "steep_or_stairs"}]
    assert "dốc" not in card["confidence"]["reason"]
    assert card["confidence"]["level"] == ("low" if other_wish else "high")
    assert ("chưa có bằng chứng" in card["confidence"]["reason"]) == other_wish
