import pytest

from fixtures import feat, hard, si, srec

from decision import Data, Engine, Store, load_settings
from requirements import allowed, hard_result


@pytest.mark.parametrize("policy, admitted", [("exclude", False), ("flag", True)])
def test_uncertain_alternative_is_unknown_and_leaves_admission_to_policy(policy, admitted):
    rec = srec("quiet", features={"noise": feat("quiet", n=1, status="UNCERTAIN")})
    req = hard("noise", "loud", policy=policy)
    assert hard_result(rec, req) == ("unknown", None)
    assert allowed(rec, req) is admitted


@pytest.mark.parametrize("value, status, expected", [
    ("quiet", "VERIFIED", "pass"),
    ("quiet", "OUTDATED", "pass"),
    ("loud", "VERIFIED", "fail"),
    ("loud", "UNCERTAIN", "unknown"),
    ("quiet", "UNCERTAIN", "unknown"),
])
def test_negative_hard_requires_firm_evidence(value, status, expected):
    rec = srec("noise", features={"noise": feat(value, n=1, status=status)})
    assert hard_result(rec, hard("noise", "loud")) == (expected, None)


def test_missing_noise_remains_unknown():
    assert hard_result(srec("missing"), hard("noise", "loud")) == ("unknown", None)


def test_soft_preference_cannot_admit_uncertain_negative_hard():
    rec = srec("quiet", features={"noise": feat("quiet", n=1, status="UNCERTAIN")})
    search = si(hard_filters=[hard("noise", "loud")], soft_weights=[
        {"feature": "noise", "value": "quiet", "context": None, "weight": 1, "source": "user"},
    ])
    engine = Engine(Data([rec]), load_settings(), Store(None))
    result = engine.create(search.model_dump(mode="json"))
    assert all(card["id"] != "quiet" for group in result["view"]["groups"] for card in group["cards"])
