"""Judge context preserves usable originals, not opaque observation identifiers."""
from corpus.tags.offline import _validated, candidates, prompt_evidence


def test_context_retains_long_original_instead_of_dropping_it():
    text = "Có khu chơi với mèo của quán. " * 200
    supplied = prompt_evidence([{"quote": text, "source": "gmaps_review", "value": "present",
                                 "observations": ["opaque-id"] * 100}])
    assert supplied and text.startswith(supplied[0]["quote"])
    assert "Có khu chơi với mèo của quán." in supplied[0]["quote"]
    assert "observations" not in supplied[0]
    assert supplied[0]["n"] == 100


def test_quote_from_another_candidate_is_not_support():
    cs = [{"tag": "experience:animals", "evidence": [{"quote": "Chỉ có cây trang trí"}]},
          {"tag": "category:cafe", "evidence": [{"quote": "Cat cafe"}]}]
    out, invalid = _validated({"items": [{"tag": "experience:animals", "verdict": "yes",
                                         "quote": "Cat cafe", "reason": "name"}]}, cs)
    assert invalid == 2
    assert out["experience:animals"]["verdict"] == "unclear"


def test_menu_availability_cannot_be_the_decisive_discovery_evidence():
    cs = [{"tag": "dish:bit_tet", "evidence": [{"quote": "Bò Bít Tết Khoai", "source": "menu"}]}]
    out, invalid = _validated({"items": [{"tag": "dish:bit_tet", "verdict": "yes",
                                         "quote": "Bò Bít Tết Khoai", "reason": "listed on menu"}]}, cs)
    assert out["dish:bit_tet"]["verdict"] == "unclear"
    assert invalid == 1


def test_recommended_dish_remains_a_discovery_motive():
    cs = [{"tag": "dish:bit_tet", "evidence": [{"quote": "Bít tết ở đây rất đáng thử", "source": "review_order", "n": 1}]}]
    out, invalid = _validated({"items": [{"tag": "dish:bit_tet", "verdict": "yes",
                                         "quote": "Bít tết ở đây rất đáng thử", "reason": "recommendation"}]}, cs)
    assert out["dish:bit_tet"]["verdict"] == "yes" and invalid == 0


def test_yes_with_only_availability_or_generic_support_is_rejected():
    for support in ("availability_only", "generic_praise", "contradiction", "incidental", "unsupported"):
        cs = [{"tag": "experience:flower_garden", "evidence": [{"quote": "nơi đẹp", "source": "gmaps_review"}]}]
        out, _ = _validated({"items": [{"tag": "experience:flower_garden", "verdict": "yes", "quote": "nơi đẹp",
                                       "support": support, "reason": "not a concrete visitor experience"}]}, cs)
        assert out["experience:flower_garden"]["verdict"] == "unclear"


def test_prompt_places_binding_definition_next_to_each_candidates_evidence():
    from corpus.tags.offline import judge_input
    row = {"name": "Forest cafe", "category": "Quán cà phê"}
    cs = [{"tag": "experience:nature", "evidence": [{"quote": "cây trang trí", "source": "gmaps_review"}]}]
    got = judge_input(row, cs, [])
    candidate = got["candidates"][0]
    assert "vài cây trang trí" in candidate["definition"]["exclude"]
    assert candidate["evidence"][0]["quote"] == "cây trang trí"
    assert candidate["evidence"][0]["quote_index"] == 0


def test_category_judge_gets_actual_experience_context_not_maps_alone():
    row = {"place_id": "p", "name": "Tiệm Trà", "group": "attraction", "category": "Điểm tham quan",
           "record": {"id": "p", "identity": {"name": "Tiệm Trà", "category_group": "attraction"}},
           "features": {"long_stay_chill": [{"quote": "Tiệm chỉ bán trà, ngồi thư thả cả buổi", "source": "gmaps_review"}]}}
    category = next(c for c in candidates(row) if c["tag"] == "category:attraction")
    assert any("chỉ bán trà" in e["quote"] for e in category["evidence"])
