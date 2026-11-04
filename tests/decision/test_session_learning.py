from copy import deepcopy
from dataclasses import replace

import pytest
from fixtures import feat, hard, love, si, srec

from decision import Data, Engine, Store
from decision.pipeline import run
from decision.session import Drop, Session, State
from decision.settings import default

CFG = replace(default(), wish=deepcopy(default().wish))
CFG.wish["session_learning"]["enabled"] = True


def test_default_learning_is_disabled_without_restoring_pending():
    assert default().wish["session_learning"]["enabled"] is False
    cfg = replace(CFG, wish=deepcopy(CFG.wish))
    cfg.wish["session_learning"]["enabled"] = False
    data = Data(records())
    before = run(Session(id="0" * 12, search_input=si(), state=State()), data, cfg)
    state = State(selected=["pick"], dropped=[Drop(place_id="drop0", reason="dislike")])
    after = run(Session(id="1" * 12, search_input=si(), state=state), data, cfg)
    assert all(after.cands[p].score == before.cands[p].score for p in after.ranked["cafe"])
    assert after.view["pending"] is None



def records():
    return [srec("pick", features={"noise": "quiet"}),
            srec("a-loud", features={"noise": "loud"}),
            srec("z-quiet", features={"noise": "quiet"}),
            srec("unknown"),
            *[srec(f"drop{i}", features={"noise": "loud"}) for i in range(CFG.pattern_min)]]


def result(state=None, search=None, recs=None):
    return run(Session(id="0" * 12, search_input=search or si(), state=state or State()),
               Data(recs or records()), CFG)


def test_consistent_distinctive_attribute_learns_but_universal_attribute_does_not():
    recs = [srec(str(i), features={"noise": "quiet" if i < 3 else "loud", "cleanliness": "clean"}) for i in range(8)]
    before = result(recs=recs)
    after = result(State(selected=["0", "1"]), recs=recs)
    assert after.cands["2"].score > before.cands["2"].score
    assert after.cands["3"].score == before.cands["3"].score


def test_positive_learning_only_uses_configured_taste_values():
    from decision.learning import signals
    recs = [srec(str(i), features={"noise": "loud", "mosquitoes": "present",
                                 "steep_or_stairs": "present", "crowd": "high",
                                 "local_specialty_food": "present"}) for i in range(2)]
    learned = signals(State(selected=["0", "1"]), si(), {r["id"]: r for r in recs}, CFG)
    assert set(learned) == {("local_specialty_food", "present")}


def test_configured_taste_values_belong_to_ontology_and_exclude_effort():
    from pathlib import Path
    import yaml
    ontology = yaml.safe_load((Path(__file__).resolve().parents[2] / "config/ontology.yaml").read_text())
    features = {f["id"]: f for f in ontology["features"]}
    for fid, values in CFG.wish["session_learning"]["taste_values"].items():
        assert features[fid]["group"] in ("experience", "environment")
        assert set(values) <= set(features[fid]["values"])
    assert "mosquitoes" not in CFG.wish["session_learning"]["taste_values"]


def test_common_six_of_six_is_weak_evidence_and_beats_rare_two_of_two():
    from decision.learning import evidence_strength
    common = evidence_strength(6, 6, 70, 100, 3)
    rare = evidence_strength(2, 2, 1, 100, 3)
    assert 0 < rare < common < 1
    assert evidence_strength(6, 6, 100, 100, 3) == 0


def test_only_top_three_meaningful_attributes_receive_learning():
    from decision.learning import adjustments
    from corpus.snapshot import Region
    features = {f: "present" for f in ("scenic_view", "flower_garden", "cozy_decor", "local_specialty_food")}
    recs = [srec(str(i), features=features if i < 6 else {}) for i in range(10)]
    recs += [srec(f"only-{f}", features={f: "present"}) for f in features]
    delta = adjustments(Region.from_records(recs), State(selected=[str(i) for i in range(6)]), si(), CFG)
    assert sum(bool(delta.get(f"only-{f}")) for f in features) == 3


def test_consistency_retracts_unshared_attributes_in_mixed_choices():
    before = result()
    after = result(State(selected=["pick", "a-loud"]))
    assert after.cands["z-quiet"].score == before.cands["z-quiet"].score


def test_select_weakly_reranks_same_pool_without_changing_counts_or_profile():
    before = result()
    state = State(selected=["pick"])
    after = result(state)
    assert set(before.ranked["cafe"]) == set(after.ranked["cafe"])
    assert after.cands["z-quiet"].score > before.cands["z-quiet"].score
    assert after.ranked["cafe"].index("z-quiet") < after.ranked["cafe"].index("a-loud")
    assert after.cands["unknown"].score == before.cands["unknown"].score
    assert state.profile.soft == [] and state.likes == []


@pytest.mark.parametrize("reason", [None, "far", "pricey", "visited"])
def test_single_non_taste_drop_never_teaches_feature(reason):
    before = result()
    after = result(State(dropped=[Drop(place_id="drop0", reason=reason)]))
    # far/pricey have their own explicit feedback path; this state isolates taste learning.
    assert after.cands["a-loud"].score == before.cands["a-loud"].score


def test_unexplained_drop_pattern_requires_min_and_unknown_is_not_penalized():
    before = result()
    after = result(State(dropped=[Drop(place_id=f"drop{i}") for i in range(CFG.pattern_min)]))
    assert after.cands["a-loud"].score < before.cands["a-loud"].score
    assert after.cands["unknown"].score == before.cands["unknown"].score


def test_explicit_dislike_teaches_immediately_but_never_overrides_current_trip():
    state = State(dropped=[Drop(place_id="drop0", reason="dislike")])
    assert result(state).cands["a-loud"].score < result().cands["a-loud"].score
    search = si(soft_weights=[love("noise", "loud")])
    assert result(state, search).cands["a-loud"].score == result(search=search).cands["a-loud"].score


@pytest.mark.parametrize("f", [feat("quiet", status="UNCERTAIN"), feat("quiet", status="OUTDATED"),
                               feat("quiet", n=0), {**feat("quiet"), "evidence": []}])
def test_unbacked_selection_never_teaches(f):
    recs = records()
    recs[0] = srec("pick", features={"noise": f})
    assert result(State(selected=["pick"]), recs=recs).cands["z-quiet"].score == result(recs=recs).cands["z-quiet"].score


def test_undo_and_change_of_mind_restore_original_order_and_like_is_separate():
    engine = Engine(Data(records()), CFG, Store(None))
    sid = engine.create(si().model_dump(mode="json"))["id"]
    before = engine._result(engine.store.get(sid)).ranked
    engine.act(sid, {"type": "select", "place_id": "pick"})
    engine.act(sid, {"type": "undo"})
    assert engine._result(engine.store.get(sid)).ranked == before
    engine.act(sid, {"type": "select", "place_id": "pick"})
    engine.act(sid, {"type": "drop", "place_id": "pick"})
    after = engine._result(engine.store.get(sid))
    assert after.ranked["cafe"] == [p for p in before["cafe"] if p != "pick"]
    assert engine.store.get(sid).state.likes == []


@pytest.mark.parametrize("seed", range(3))
def test_enabled_learning_matches_scalar_reference_with_shared_cache(seed):
    from gen import records as generated_records, sessions
    from reference import run_reference
    recs = generated_records(seed)
    data, memo = Data(recs), {}
    for session in sessions(seed, recs, 5):
        assert run(session, data, CFG, memo).view == run_reference(session, recs, CFG).view


def test_learning_is_bounded_and_cached_previous_results_are_immutable():
    engine = Engine(Data(records()), CFG, Store(None))
    sid = engine.create(si().model_dump(mode="json"))["id"]
    before = engine._result(engine.store.get(sid))
    old_score = before.cands["z-quiet"].score
    old_view = before.view.copy()
    for pid in ("pick", "z-quiet"):
        engine.act(sid, {"type": "select", "place_id": pid})
    after = engine._result(engine.store.get(sid))
    assert before.cands["z-quiet"].score == old_score and before.view == old_view
    assert all(abs(after.cands[pid].parts.get("session", 0)) <= CFG.wish["session_learning"]["max_lift"]
               for ids in after.ranked.values() for pid in ids)
    assert engine.load(sid)["view"] == after.view


def test_learning_never_admits_hard_fail_or_unknown_and_never_opens_pending():
    state = State(selected=["pick"], dropped=[Drop(place_id=f"drop{i}") for i in range(CFG.pattern_min)])
    after = result(state, si(hard_filters=[hard("noise", "quiet", op="eq")]))
    assert set(after.ranked["cafe"]) == {"pick", "z-quiet"}
    assert after.view["pending"] is None
    assert result(State(dropped=[Drop(place_id=f"drop{i % CFG.pattern_min}") for i in range(10)])).view["pending"] is None
