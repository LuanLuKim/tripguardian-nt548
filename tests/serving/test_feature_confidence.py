"""Feature confidence grows with the authors past 3 and shrinks with a low mention rate (corpus.serving.evidence)."""

import pytest

from corpus.serving import conf
from corpus.serving.record import config

CFG = config()["evidence"]


def f(n, agreement=1.0, rate=0.1, status="VERIFIED"):
    return {"n": n, "status": status, "mention_rate": rate, "confidence": {"agreement": agreement}}


def test_3_30_300_authors_with_equal_agreement_order_strictly():
    assert conf(f(3, 0.9)) < conf(f(30, 0.9)) < conf(f(300, 0.9))


def test_diminishing_returns():
    assert conf(f(31)) - conf(f(30)) < conf(f(4)) - conf(f(3))  # each further author adds less


def test_lone_mention_never_outranks_a_well_supported_one():
    assert conf(f(1, 1.0)) < conf(f(30, 0.8))
    assert conf(f(1, 1.0)) < conf(f(10, 0.6))


def test_same_mentions_among_many_reviews_count_less():
    assert conf(f(6, rate=6 / 3000)) < conf(f(6, rate=6 / 10))
    assert conf(f(6, rate=6 / 3000)) > 0.7 * conf(f(6, rate=6 / 10)) - 1e-9  # a mild discount, never a veto


def test_unknown_rate_costs_nothing_and_missing_agreement_is_no_confidence():
    assert conf(f(6, rate=None)) == conf(f(6, rate=0.5)) == conf(f(6, rate=0))
    assert conf({"n": 0, "status": "VERIFIED", "mention_rate": None, "confidence": {"agreement": None}}) == 0.0


def test_stays_within_zero_one():
    assert 0.0 <= conf(f(10**6, 1.0)) <= 1.0
    assert conf(f(3, 1.0, status="UNCERTAIN")) < conf(f(3, 1.0))


def test_config_shape():
    assert CFG["full_n"] < CFG["ref_n"] and 0 < CFG["base"] < 1 and 0 <= CFG["rate_weight"] < 1
    assert pytest.approx(conf(f(CFG["full_n"], rate=1.0))) == CFG["base"]
