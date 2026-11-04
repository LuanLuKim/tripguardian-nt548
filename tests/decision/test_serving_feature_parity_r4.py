from copy import deepcopy

import pytest

from fixtures import feat, si, srec
from corpus.serving import feature
from decision import load_settings
from decision.feasibility import _top_experience, need_buckets
from decision.learning import attributes, signals
from decision.model import Cand
from decision.session import Drop, State
from decision.trip_days import trip_days


SILENCE_CASES = [("silence", 0), ("silence", 30), (None, 0), ("stale", 0)]
GROUP_FEATURES = [("scenic_view", "present"), ("noise", "quiet"), ("pets", "allowed"),
                  ("steep_or_stairs", "absent"), ("kids", "suitable")]


def silent_feature(value, reason, n, status="VERIFIED"):
    return {**feat(value, n=n, status=status), "reason": reason,
            "distribution": {value: n} if n else {}, "evidence": ["old:1"] if n else [],
            "by_context": {"time_of_day=early_morning": {value: 30}}}


@pytest.mark.parametrize("status", ["VERIFIED", "OUTDATED", "UNCERTAIN"])
@pytest.mark.parametrize("reason,n", SILENCE_CASES)
def test_top_experience_treats_serving_silence_as_missing(reason, n, status):
    rec = srec("same", features={"cloud_hunting": silent_feature("present", reason, n, status)})
    before = deepcopy(rec)
    assert feature(rec, "cloud_hunting") is None
    assert _top_experience(rec) == _top_experience(srec("same")) is None
    assert rec == before


def test_silence_cannot_displace_a_backed_timed_anchor():
    cfg = load_settings()
    cloud = feat("present", n=6, by_context={"time_of_day=early_morning": {"present": 6}})
    rec = srec("same", features={"cloud_hunting": cloud,
                                "scenic_view": silent_feature("present", "silence", 30)})
    missing = srec("same", features={"cloud_hunting": cloud})
    days = trip_days(si().context, cfg)
    assert feature(rec, "scenic_view") is None
    assert need_buckets(Cand(rec, "experience"), set(), True, days, cfg) == need_buckets(
        Cand(missing, "experience"), set(), True, days, cfg) == frozenset({"early_morning"})


@pytest.mark.parametrize("fid,value", GROUP_FEATURES)
@pytest.mark.parametrize("status", ["VERIFIED", "OUTDATED", "UNCERTAIN"])
@pytest.mark.parametrize("reason,n", SILENCE_CASES)
def test_learning_attributes_treat_serving_silence_as_missing(fid, value, reason, n, status):
    rec = srec("same", features={fid: silent_feature(value, reason, n, status)})
    before = deepcopy(rec)
    assert feature(rec, fid) is None
    assert attributes(rec) == attributes(srec("same")) == {}
    assert rec == before


@pytest.mark.parametrize("action", ["select", "dislike", "unexplained"])
def test_silent_curation_never_teaches_a_session_signal(action):
    cfg = load_settings()
    recs = [srec(str(i), features={"noise": silent_feature("quiet", "silence", 30)})
            for i in range(max(2, cfg.pattern_min))]
    assert all(feature(rec, "noise") is None for rec in recs)
    ids = [rec["id"] for rec in recs]
    state = State(selected=ids) if action == "select" else State(
        dropped=[Drop(place_id=pid, reason="dislike" if action == "dislike" else None) for pid in ids])
    assert signals(state, si(), {rec["id"]: rec for rec in recs}, cfg) == {}
    assert cfg.wish["session_learning"]["enabled"] is False


@pytest.mark.parametrize("status,n,evidence,eligible", [
    ("VERIFIED", 3, ["x:1"], True), ("OUTDATED", 3, ["x:1"], False),
    ("UNCERTAIN", 3, ["x:1"], False), ("VERIFIED", 0, ["x:1"], False),
    ("VERIFIED", 3, [], False)])
def test_backed_learning_keeps_existing_status_count_and_evidence_guards(status, n, evidence, eligible):
    f = {**feat("quiet", n=n, status=status), "evidence": evidence}
    rec = srec("backed", features={"noise": f})
    assert feature(rec, "noise") == f
    assert attributes(rec) == ({"noise": f} if eligible else {})


def test_backed_top_experience_keeps_count_and_feature_id_tiebreak():
    rec = srec("backed", features={"cloud_hunting": feat("present", n=3),
                                  "scenic_view": feat("present", n=3, status="OUTDATED")})
    assert _top_experience(rec) == "scenic_view"
    rec["experience"]["cloud_hunting"]["n"] = 4
    assert _top_experience(rec) == "cloud_hunting"
