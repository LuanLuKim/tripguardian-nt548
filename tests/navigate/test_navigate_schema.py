import copy

from corpus.navigate.schema import MiningMap, claim_id, fold, parse_answer

NF_NONE = {"key": "", "type": "none", "values": [], "hint": ""}


def aspect(key="cloud_hunting", **over):
    base = {"key": key, "name_vi": "Săn mây", "why": "Đà Lạt nằm trên cao nguyên.",
            "target": {"kind": "feature", "ref": "cloud_hunting", "new_feature": NF_NONE},
            "queries": ["săn mây Đà Lạt", "đồi săn mây đẹp ở Đà Lạt"], "sources": ["web", "tiktok"],
            "nominees": [{"name": "Đồi Đa Phú", "area_hint": "phường 7"}], "months": [11, 12, 1]}
    base.update(over)
    return base


def claim(**over):
    base = {"subject_kind": "city", "subject": "Đà Lạt", "kind": "best_time",
            "text": "Mùa khô từ tháng 11 đến tháng 3 ít mưa, hợp đi chơi.",
            "when": {"months": [11, 12, 1, 2, 3], "days": [], "hours": "", "weather": ""}}
    base.update(over)
    return base


def parse(aspects=(), claims=()):
    return parse_answer("dalat", {"aspects": list(aspects), "general_claims": list(claims)}, "sol", "2026-10-28T10:00:00+00:00")


def test_valid_answer_becomes_a_map():
    m = parse([aspect()], [claim()])
    assert isinstance(m, MiningMap) and m.city == "dalat" and m.model == "sol" and m.rejected == []
    a = m.aspects[0]
    assert a.key == "cloud_hunting" and a.months == [1, 11, 12] and a.target.new_feature is None
    assert a.nominees[0].name == "Đồi Đa Phú"


def test_general_claim_shape_for_p4():
    c = parse([], [claim()]).general_claims[0].model_dump()
    assert set(c) == {"claim_id", "subject_kind", "subject", "kind", "text", "when", "source"}
    assert c["source"] == "model" and set(c["when"]) == {"months", "days", "hours", "weather"}
    assert c["claim_id"] == claim_id("city", "Đà Lạt", "best_time", claim()["text"]) and len(c["claim_id"]) == 12


def test_bad_aspects_are_dropped_with_a_reason():
    m = parse([aspect(key="Bad Key"), aspect(key="ok_one"), aspect(key="ok_one"), aspect(key="no_why", why=" "),
               aspect(key="no_q", queries=["", "x"])])
    assert [a.key for a in m.aspects] == ["ok_one"]
    reasons = {r.path: r.reason for r in m.rejected}
    assert len(m.rejected) == 4
    assert "snake_case" in reasons["aspects[0]"] and "duplicate" in reasons["aspects[2]"]
    assert "why" in reasons["aspects[3]"] and "query" in reasons["aspects[4]"]


def test_queries_nominees_sources_months_are_clamped():
    a = parse([aspect(queries=[f"truy vấn số {i}" for i in range(12)] + ["truy vấn số 1"],
                      sources=["web", "facebook"], months=[0, 5, 13, 5],
                      nominees=[{"name": f"Quán {i}", "area_hint": ""} for i in range(20)])]).aspects[0]
    assert len(a.queries) == 8 and a.sources == ["web"] and a.months == [5] and len(a.nominees) == 15


def test_new_feature_needs_a_closed_shape():
    def nf(**over):
        return aspect(key="x_" + str(len(over)), target={"kind": "new_feature", "ref": "tide_walk", "new_feature": {
            "key": "tide_walk", "type": "presence", "values": ["present"], "hint": "đi bộ lúc thủy triều rút", **over}})
    ok = parse([nf()]).aspects[0]
    assert ok.target.new_feature.key == "tide_walk" and ok.target.ref == "tide_walk"
    assert parse([nf(key="Tide Walk")]).rejected
    assert parse([nf(values=["yes"])]).rejected                      # presence = ["present"] only
    assert parse([nf(type="rating", values=["good", "mixed", "poor"])]).aspects
    assert parse([nf(type="rating", values=["good"])]).rejected
    assert parse([nf(type="category", values=["a"])]).rejected       # 2-6 values
    assert parse([nf(type="category", values=["calm", "wavy"])]).aspects
    assert parse([nf(hint="")]).rejected and parse([nf(type="none")]).rejected


def test_local_claim_target_ref_must_be_a_claim_kind():
    a = lambda ref: aspect(key="season_ref", target={"kind": "local_claim", "ref": ref, "new_feature": NF_NONE})
    assert parse([a("season")]).aspects and parse([a("weather")]).rejected


def test_claims_are_gated():
    m = parse([aspect(nominees=[{"name": "Quán Gió", "area_hint": ""}])], [
        claim(), claim(),                                          # duplicate -> one kept
        claim(subject="quán gió", subject_kind="dish"),            # a venue, not general knowledge
        claim(text=""), claim(text="x" * 301),
        claim(kind="opening_hours"),                               # not a LocalClaim kind
        claim(subject_kind="poi"),
        claim(subject="Mùa mưa", when={"months": [5, 13], "days": ["weekend"], "hours": "", "weather": "rainy"}),
        claim(subject="Chợ đêm", when={"months": [], "days": [], "hours": "17:00-23:00", "weather": ""}),
        claim(subject="Bình minh", when={"months": [], "days": [], "hours": "sáng sớm", "weather": ""})])
    assert [c.subject for c in m.general_claims] == ["Đà Lạt", "Mùa mưa", "Chợ đêm"]
    assert m.general_claims[1].when.months == [5]
    assert len(m.rejected) == 7


def test_caps_and_missing_lists():
    assert len(parse([aspect(key=f"k_{i:02d}x") for i in range(45)]).aspects) == 40
    m = parse_answer("dalat", {}, "sol", "t")
    assert m.aspects == [] and m.general_claims == []


def test_fold_is_diacritic_blind():
    assert fold("  Đồi  Đa Phú ") == "doi da phu"


def test_parse_does_not_mutate_input():
    raw = {"aspects": [aspect()], "general_claims": [claim()]}
    before = copy.deepcopy(raw)
    parse_answer("dalat", raw, "sol", "t")
    assert raw == before


def test_minimal_answer_without_optional_parts_parses():
    m = parse_answer("dalat", {"aspects": [{"key": "cloud_hunting", "name_vi": "Săn mây", "why": "x",
                                            "target": {"kind": "feature", "ref": "cloud_hunting"},
                                            "queries": ["săn mây Đà Lạt"]}],
                               "general_claims": [{"subject_kind": "city", "subject": "Đà Lạt", "kind": "tip", "text": "x"}]},
                     "sol", "t")
    assert m.rejected == [] and m.aspects[0].sources == [] and m.general_claims[0].when.months == []
