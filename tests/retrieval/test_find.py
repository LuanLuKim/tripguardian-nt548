"""find / vocabulary: criteria search over a snapshot Region (hand-built records, no model, no corpus data)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "decision"))  # fixtures.py next to the decision tests
from fixtures import ONT, feat, srec

from corpus.retrieval import Criteria, FindHit, FindResult, RetrievalEngine, SemanticHit
from corpus.retrieval.find import find, vocabulary, warm
from corpus.snapshot import Region

DAY = [["07:00", "22:00"]]


def ids(hits):
    return [h.place_id for h in hits]


def region(*records):
    return Region.from_records(records)


@pytest.fixture
def five():
    a = srec("A", features={"crowd": "low"})
    b = srec("B", features={"crowd": feat("low", status="UNCERTAIN")})
    c = srec("C", group="restaurant", category="Nhà hàng")
    d = srec("D", group="restaurant", category="Nhà hàng", features={"crowd": "high"})
    e = srec("E", group="stay", category="Khách sạn", features={"crowd": "low"})
    return region(a, b, c, d, e)


def test_must_firm_only(five):
    r = find(five, Criteria(must=(("crowd", "low"),)))
    assert ids(r.hits) == ["A"]          # VERIFIED: a hit
    assert ids(r.maybe) == ["B"]         # UNCERTAIN: maybe, never a hit
    assert r.unknown == 1                # C has no evidence at all; D has another value (dropped, not unknown); E is lodging
    assert "D" not in ids(r.hits) + ids(r.maybe)


def test_must_outdated_counts_as_firm():
    r = find(region(srec("A", features={"crowd": feat("low", status="OUTDATED")})), Criteria(must=(("crowd", "low"),)))
    assert ids(r.hits) == ["A"]


def test_stay_only_when_asked(five):
    assert "E" not in ids(find(five, Criteria()).hits)
    r = find(five, Criteria(groups=("stay",)))
    assert ids(r.hits) == ["E"]
    both = find(five, Criteria(groups=("cafe", "stay")), limit=10)
    assert set(ids(both.hits)) == {"A", "B", "E"}


def test_open_at_overnight_and_missing():
    night = srec("N", hours={"fri": [["18:00", "02:00"]]})
    missing_day = srec("M", hours={"mon": DAY})
    uncertain = srec("U", hours={d: DAY for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
                     hours_status="UNCERTAIN")
    nohours = srec("X", hours=None)
    reg = region(night, missing_day, uncertain, nohours)
    assert ids(find(reg, Criteria(open_at=("sat", "01:00"))).hits) == ["N"]      # the fri range runs past midnight
    assert ids(find(reg, Criteria(open_at=("fri", "19:00"))).hits) == ["N"]
    assert ids(find(reg, Criteria(open_at=("sat", "03:00"))).hits) == []
    assert ids(find(reg, Criteria(open_at=("fri", "01:00"))).hits) == []          # nothing runs into fri from thu
    assert ids(find(reg, Criteria(open_at=("mon", "10:00"))).hits) == ["M"]       # M is closed on the days it lacks
    assert ids(find(reg, Criteria(open_at=("tue", "10:00"))).hits) == []          # U is UNCERTAIN: never passes


def test_open_at_end_of_range_is_closed_and_midnight_end():
    p = srec("P", hours={"mon": [["10:00", "00:00"]]})  # Maps writes midnight as 00:00
    reg = region(p)
    assert ids(find(reg, Criteria(open_at=("mon", "23:30"))).hits) == ["P"]
    assert ids(find(reg, Criteria(open_at=("tue", "00:00"))).hits) == []
    assert ids(find(reg, Criteria(open_at=("mon", "09:59"))).hits) == []


def test_opens_by():
    early = srec("E1", hours={"mon": DAY, "sun": [["05:30", "11:00"]]})
    late = srec("L1", hours={"mon": [["08:00", "22:00"]]})
    unc = srec("U1", hours={"sun": [["05:00", "11:00"]]}, hours_status="UNCERTAIN")
    reg = region(early, late, unc)
    assert ids(find(reg, Criteria(opens_by="06:00")).hits) == ["E1"]
    assert set(ids(find(reg, Criteria(opens_by="08:00")).hits)) == {"E1", "L1"}


def test_dish_folds_accents():
    a, b = srec("A"), srec("B")
    a["menu"] = {"dishes": [{"name": "Bánh Căn Nhà Chung"}, {"name": "Bún bò"}]}
    reg = region(a, b)
    r = find(reg, Criteria(dish="banh can"))
    assert ids(r.hits) == ["A"] and "dish:Bánh Căn Nhà Chung" in r.hits[0].matched
    assert ids(find(reg, Criteria(dish="BÚN BÒ")).hits) == ["A"]
    assert ids(find(reg, Criteria(dish="bun bo")).hits) == ["A"]
    assert ids(find(reg, Criteria(dish="pizza")).hits) == []


def test_dish_finds_an_eatery_named_for_it_but_not_a_stay():
    a = srec("A", name="Bánh bèo Bà Hường", group="restaurant")
    b = srec("B", name="Bánh bèo Villa", group="stay")
    r = find(region(a, b), Criteria(dish="banh beo", groups=("restaurant", "stay")))
    assert ids(r.hits) == ["A"] and r.hits[0].matched == ("dish:Bánh bèo Bà Hường",)


def test_dish_is_whole_words_and_keeps_typed_accents():
    a, b, c = srec("A"), srec("B"), srec("C")
    a["menu"] = {"dishes": [{"name": "Bánh Canh"}]}
    b["menu"] = {"dishes": [{"name": "Phở bò"}]}
    c["menu"] = {"dishes": [{"name": "Phô mai"}]}
    reg = region(a, b, c)
    assert ids(find(reg, Criteria(dish="banh can")).hits) == []     # "can" is not the word "canh"
    assert ids(find(reg, Criteria(dish="phở")).hits) == ["B"]       # typed with accents: "phô mai" is not "phở"
    assert set(ids(find(reg, Criteria(dish="pho")).hits)) == {"B", "C"}


def test_near_km():
    here = srec("H", lat=11.94, lng=108.44)
    close = srec("C", lat=11.96, lng=108.44)    # ~2.2 km
    far = srec("F", lat=12.10, lng=108.44)      # ~17.8 km
    r = find(region(here, close, far, srec("Z", lat=None, lng=None)), Criteria(near=(11.94, 108.44, 5.0)))
    assert set(ids(r.hits)) == {"H", "C"}


def test_prefer_and_month_order():
    strong = srec("S", features={"nature": "present"}, voices=5)                       # conf 1.0
    weak = srec("W", features={"nature": feat("present", n=1)}, voices=500)            # conf 1/3
    none = srec("N0", voices=20)
    month = srec("M", voices=1, details={"timing": {"best_months": [12], "avoid_months": []}})
    shunned = srec("V", voices=1, details={"timing": {"best_months": [], "avoid_months": [12]}})
    reg = region(strong, weak, none, month, shunned)
    r = find(reg, Criteria(prefer=(("nature", "present"),)), limit=5)
    assert ids(r.hits)[:2] == ["S", "W"] and "nature=present" in r.hits[0].matched
    assert all(h.score <= r.hits[0].score for h in r.hits)
    r = find(reg, Criteria(month=12), limit=5)
    assert ids(r.hits)[0] == "M" and ids(r.hits)[-1] == "V" and "month" in r.hits[0].matched
    assert "month" not in r.hits[-1].matched


def test_ties_break_by_voices_then_id():
    reg = region(srec("B2", voices=10), srec("A2", voices=10), srec("C2", voices=99))
    assert ids(find(reg, Criteria()).hits) == ["C2", "A2", "B2"]


def test_limit_applies_to_hits_and_maybe(five):
    r = find(five, Criteria(groups=("cafe", "restaurant"), must=(("crowd", "low"),)), limit=1)
    assert len(r.hits) <= 1 and len(r.maybe) <= 1


def test_hits_carry_card_and_release(five):
    r = find(five, Criteria(must=(("crowd", "low"),)))
    assert isinstance(r, FindResult) and isinstance(r.hits[0], FindHit)
    assert r.hits[0].card["id"] == "A" and r.release_id is None


def test_fit_must_works():
    a = srec("A", details={"fit": {"kids": {"value": "good", "distribution": {"good": 2}, "n": 2, "reasons": [],
                                             "status": "VERIFIED", "evidence": []}}})
    assert ids(find(region(a, srec("B")), Criteria(must=(("fit.kids", "good"),))).hits) == ["A"]


def test_parse_accepts_and_converts():
    c = Criteria.parse({"groups": ["cafe"], "must": [["crowd", "low"], ["fit.kids", "good"]],
                        "prefer": [["nature", "present"]], "open_at": ["sat", "06:00"], "opens_by": "06:00",
                        "dish": "banh can", "month": 12, "near": [11.9, 108.4, 3], "text": "view"}, ONT)
    assert c.groups == ("cafe",) and c.must == (("crowd", "low"), ("fit.kids", "good"))
    assert c.open_at == ("sat", "06:00") and c.near == (11.9, 108.4, 3.0) and c.month == 12
    assert Criteria.parse({}, ONT) == Criteria()


@pytest.mark.parametrize("raw", [
    {"must": [["no_such_feature", "x"]]},
    {"must": [["crowd", "enormous"]]},
    {"prefer": [["fit.nobody", "good"]]},
    {"must": [["fit.kids", "great"]]},
    {"groups": ["nonsense"]},
    {"month": 13},
    {"month": 0},
    {"opens_by": "25:00"},
    {"opens_by": "6am"},
    {"open_at": ["someday", "06:00"]},
    {"open_at": ["sat", "25:00"]},
    {"near": [11.9, 108.4, -1]},
    {"bogus_key": 1},
])
def test_parse_rejects_unknown(raw):
    with pytest.raises(ValueError):
        Criteria.parse(raw, ONT)


def test_text_never_embeds_on_empty_scope(five):
    def boom(*a, **k):
        raise AssertionError("semantic must not run on an empty scope")
    r = find(five, Criteria(must=(("crowd", "medium"),), text="view đẹp"), semantic=boom)
    assert r.hits == () and r.maybe == ()


def test_text_runs_on_filtered_scope_and_scores():
    reg = region(srec("A", voices=1), srec("B", voices=1), srec("S", group="stay", category="Khách sạn"))
    seen = {}

    def sem(q, within, **k):
        seen["q"], seen["within"] = q, set(within)
        return [SemanticHit("B", 0.9, "span", None, True, None)]
    r = find(reg, Criteria(text="view đẹp"), semantic=sem)
    assert seen == {"q": "view đẹp", "within": {"A", "B"}}       # lodging is outside the scope
    assert ids(r.hits) == ["B", "A"] and "text" in r.hits[0].matched
    assert find(reg, Criteria(text="x")).hits                       # no `semantic` given: text is ignored, no error


def test_vocabulary_shapes(five):
    v = vocabulary(ONT, five)
    assert v["groups"] == {"cafe": 2, "restaurant": 2, "stay": 1}
    crowd = v["features"]["crowd"]
    assert crowd["values"] == list(ONT.features["crowd"].values) and 0 < len(crowd["label"]) <= 80
    assert v["features"]["scenic_view"]["label"] == ONT.features["scenic_view"].claims["present"]
    assert all(len(f["label"]) <= 80 for f in v["features"].values())
    assert all("." not in f["label"] and ":" not in f["label"]
               for fid, f in v["features"].items() if not ONT.features[fid].claims)
    assert v["companions"]["kids"] == ONT.companions["kids"].vi and set(v["companions"]) == set(ONT.companions)


def test_engine_find_and_vocabulary(five):
    eng = RetrievalEngine(_index=None, _snapshot=MagicMock(), _region=five, _ontology=ONT, release_id="r-1")
    r = eng.find({"must": [["crowd", "low"]]})
    assert ids(r.hits) == ["A"] and r.release_id == "r-1"
    assert ids(eng.find(Criteria(must=(("crowd", "low"),))).hits) == ["A"]
    with pytest.raises(ValueError):
        eng.find({"month": 99})
    eng.warm()
    assert "crowd" in eng.vocabulary()["features"]
    eng.semantic = lambda q, within, **k: [SemanticHit("B", 0.5, "span", None, True, None)]
    assert ids(eng.find({"text": "x"}).hits)[0] == "B"


def test_warm_is_idempotent(five):
    warm(five)
    warm(five)
    assert ids(find(five, Criteria(open_at=("mon", "10:00"))).hits)


def test_prefer_without_confidence_still_moves_ranking():
    fit = {"kids": {"value": "good", "distribution": {"good": 2}, "n": 2, "reasons": [], "status": "VERIFIED",
                    "evidence": []}}
    fitted, plain = srec("F", details={"fit": fit}, voices=1), srec("P", voices=900)
    r = find(region(fitted, plain), Criteria(prefer=(("fit.kids", "good"),)))
    assert ids(r.hits) == ["F", "P"] and "fit.kids=good" in r.hits[0].matched
    assert r.hits[0].score > 0.5      # fit rows carry no conf: a flat 0.5 for a firm match


def test_engine_warm_loads_feature_columns(five):
    calls = []
    five.warm = lambda: calls.append(1) or five
    eng = RetrievalEngine(_index=None, _snapshot=MagicMock(), _region=five, _ontology=ONT, release_id="r-1")
    eng.warm()
    assert calls == [1]
