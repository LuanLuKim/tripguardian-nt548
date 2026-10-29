"""The Lựa chọn chatbot bench's own logic (src/decision/bench.py); no model is called."""

from decision import bench
from decision.session import State


def test_the_case_file_has_at_least_thirty_cases_in_every_family_the_spec_names():
    cases = bench.load_cases()
    assert len(cases) >= 30 and len({c["id"] for c in cases}) == len(cases)
    families = {c["family"] for c in cases}
    assert {"rerank", "filter", "why_not", "compare", "followup", "photos"} <= families
    assert all(c["turns"] and isinstance(c["turns"], list) for c in cases)
    assert [c["id"] for c in bench.load_cases(family="filter")] == [c["id"] for c in cases if c["family"] == "filter"]
    assert len(bench.load_cases(limit=3)) == 3


def test_place_names_fill_the_turn_and_a_missing_one_stays():
    assert bench.fill("Chọn {p1}, bỏ {p2}, thêm {p3}", ["A", "B"]) == "Chọn A, bỏ B, thêm {p3}"


def entry(log, say="Okay."):
    return {"action": {"log": log, "say": say}}


def test_tools_used_reads_the_turn_log():
    assert bench.tools_used(entry(["assistant", "select", "why_not:error [x]", "t_call 1.2"])) == {"select", "why_not"}
    assert bench.tools_used(entry(["heuristic:wish"])) == {"heuristic"}


def test_check_names_what_a_case_got_wrong():
    before, after = State(), State(selected=["A"])
    case = {"tools": ["select"], "expect": {"selected": 1}, "reply_lacks": ["khuyên"]}
    assert bench.check(case, before, after, entry(["select"])) == []
    problems = bench.check(case, before, before, entry(["why_not"], "Mình khuyên bạn"))
    assert len(problems) == 3
    assert bench.check({"expect": {"unchanged": True}}, before, after, entry([])) == ["state changed"]


def test_report_gates_on_speed_unsourced_blocking_and_tool_accuracy():
    rows = [{"id": str(i), "family": "select", "seconds": 3.0, "unsourced": 0, "blocking": 0, "problems": []} for i in range(10)]
    assert bench.report(rows)["gate"] is True
    assert bench.report(rows + [{"id": "x", "family": "select", "seconds": 3.0, "unsourced": 1, "blocking": 0, "problems": []}])["gate"] is False
    slow = [dict(r, seconds=12.0) for r in rows]
    assert bench.report(slow)["gate"] is False
    skipped = bench.report(rows + [{"id": "s", "family": "photos", "skipped": "needs --trip"}])
    assert skipped["skipped"] == ["s"] and skipped["gate"] is True
