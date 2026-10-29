import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "decision"))  # fixtures.py next to the decision tests
from fixtures import ONT, srec

from bench.retrieval import CASES, run
from corpus.retrieval import RetrievalEngine
from corpus.snapshot import Region

HOURS = {d: [["05:30", "21:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def engine(*records) -> RetrievalEngine:
    return RetrievalEngine(_index=None, _snapshot=MagicMock(), _region=Region.from_records(records), _ontology=ONT,
                           release_id="r-test")


def places():
    cafe = srec("C1", features={"scenic_view": "present", "laptop_friendly": "present"}, hours=HOURS)
    unsure = srec("C2", features={"scenic_view": {**srec("x", features={"scenic_view": "present"})["experience"]["scenic_view"],
                                                  "status": "UNCERTAIN"}}, hours=HOURS)
    eat = srec("R1", group="restaurant", category="Nhà hàng")
    eat["menu"] = {"dishes": [{"name": "Bánh căn nhà chung"}]}
    return cafe, unsure, eat, srec("S1", group="stay", category="Khách sạn", features={"scenic_view": "present"})


def test_bench_on_fixture_region():
    out = run(engine(*places()), repeats=2)
    assert set(out["cases"]) == {name for name, _ in CASES}
    assert len(CASES) == 18
    assert all(c["correct"] is True for c in out["cases"].values())
    cafe_view = out["cases"]["cafe_view"]
    assert (cafe_view["hits"], cafe_view["maybe"], cafe_view["recall"]) == (1, 1, 1.0)
    assert out["cases"]["banh_can"]["hits"] == 1 and out["cases"]["early"]["hits"] == 2
    assert out["cases"]["cafe_view_sat_7"]["hits"] == 1
    assert {"p50", "p95", "max"} <= set(out["cases"]["cafe_view"]["find_ms"])
    assert {"ms", "chars", "tokens_p95"} <= set(out["card"]) and out["vocabulary"]["chars"] > 0
    assert isinstance(out["ok"], bool)


def test_bench_flags_a_hit_that_fails_the_independent_check():
    eng = engine(*places())
    real = eng.find
    eng.find = lambda c, limit=8: replace(real(c, limit), hits=real({"groups": ["stay"]}, limit).hits)  # lodging is wrong
    out = run(eng, repeats=1)
    assert out["cases"]["cafe_view"]["correct"] is False and out["ok"] is False
