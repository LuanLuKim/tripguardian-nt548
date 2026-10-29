"""LOCAL_CLAIM task (docs/CORPUS.md, Tri thức bản địa): Extractor role, strict schema, quote last."""

from corpus.llm import EXTRACTOR, LOCAL_CLAIM, LOCAL_CLAIM_KINDS, LOCAL_SUBJECT_KINDS
from corpus.llm.tasks import validate


def test_local_claim_is_an_extractor_task_with_a_strict_schema():
    assert LOCAL_CLAIM.role is EXTRACTOR
    item = LOCAL_CLAIM.schema["properties"]["claims"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    assert list(item["properties"])[-1] == "quote"  # quote last: guided decoding loops after it otherwise
    assert item["properties"]["kind"]["enum"] == LOCAL_CLAIM_KINDS
    assert item["properties"]["subject_kind"]["enum"] == LOCAL_SUBJECT_KINDS
    assert "poi" in LOCAL_SUBJECT_KINDS and "poi_unresolved" not in LOCAL_SUBJECT_KINDS  # code sets that, not the model


def test_local_claim_validates_an_answer_and_renders_the_text():
    answer = {"claims": [{"subject_kind": "phenomenon", "subject_text": "mai anh đào", "kind": "season",
                          "text": "mai anh đào nở rộ", "amount_min_vnd": 0, "amount_max_vnd": 0,
                          "months": [1, 2], "days": [], "hours": "", "weather": "", "who": "",
                          "quote": "Tháng 1 đến tháng 2, mai anh đào nở rộ"}]}
    validate(answer, LOCAL_CLAIM.schema)
    text = LOCAL_CLAIM.render(city="Đà Lạt", title="Mùa hoa", url="https://x.vn/a", heading="Mùa hoa",
                              text="Tháng 1 đến tháng 2, mai anh đào nở rộ")
    assert "Đà Lạt" in text and "mai anh đào nở rộ" in text and "https://x.vn/a" in text
