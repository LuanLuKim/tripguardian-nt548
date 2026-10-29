"""DP1 (owner decision 11): a profile prior weighs less than a signal of this trip, and a trip signal on the same
feature replaces it. Order: trip signal > prior > nothing; a contradicting trip signal wins."""

import pytest

from fixtures import feat, love, si, srec

from decision import preference_fit
from decision.rank import conf, preference, wants
from decision.settings import default
from types import SimpleNamespace

CFG = default()
PRIOR = CFG.prior_weight


def prof():
    return SimpleNamespace(soft=[], visited=[], price_sensitivity=0.0)


def prior(feature, value="present", weight=1):
    return {**love(feature, value, weight), "source": "profile"}


REC = srec("A", features={"scenic_view": feat("present", n=3)})


def fit(*soft):
    s = si(soft_weights=list(soft))
    return preference(REC, wants(s, prof(), CFG))[0]


def test_order_trip_signal_over_prior_over_nothing():
    nothing, only_prior, trip = fit(), fit(prior("scenic_view")), fit(love("scenic_view"))
    assert nothing == 0.0 < only_prior < trip
    assert only_prior == pytest.approx(PRIOR * conf(feat("present", n=3)))
    assert 0 < PRIOR < 1


def test_a_trip_signal_on_the_same_feature_replaces_the_prior():
    assert fit(prior("scenic_view"), love("scenic_view")) == fit(love("scenic_view"))


def test_a_contradicting_trip_signal_wins():
    assert fit(prior("scenic_view"), love("scenic_view", weight=-1)) < 0
    assert fit(prior("scenic_view", weight=-1), love("scenic_view")) > 0


def test_a_prior_on_another_feature_stays_and_counts_less_than_the_trip_wish():
    rec = srec("B", features={"scenic_view": feat("present", n=3), "live_music": feat("present", n=3)})
    s = si(soft_weights=[love("scenic_view"), prior("live_music")])
    got = preference(rec, wants(s, prof(), CFG))[0]
    assert got == pytest.approx((1 + PRIOR) / 2 * conf(feat("present", n=3)))


def test_preference_fit_public_reads_source():
    base = [{"feature": "scenic_view", "value": "present", "weight": 1}]
    only_prior = preference_fit(REC, [{**base[0], "source": "profile"}])[0]
    trip = preference_fit(REC, [{**base[0], "source": "user"}])[0]
    assert 0 < only_prior < trip
    assert preference_fit(REC, [{**base[0], "source": "profile"}, {**base[0], "weight": -1, "source": "user"}])[0] < 0
