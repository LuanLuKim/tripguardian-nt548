"""python -m planning bench: the case file loads, every case is well formed, and the helpers agree (no model call)."""

from planning import bench


def test_the_case_file_has_at_least_twenty_cases_with_unique_ids_and_known_tools():
    from agents.assistant import REGISTRY
    import planning.assistant  # noqa: F401  (registers the planning tools)
    cases = bench.load_cases()
    assert len(cases) >= 20 and len({c["id"] for c in cases}) == len(cases)
    names = set(REGISTRY.names("planning", {"assistant"}))
    for c in cases:
        assert c["turns"] and c["family"]
        assert set(c.get("tools") or ()) <= names | {"get_place", "distance"}, c["id"]


def test_fill_and_report_and_gate():
    assert bench.fill("Chuyển {p1} sang {p2}", ["A b", "C d"]) == "Chuyển A b sang C d"
    rows = [{"id": "a", "family": "f", "seconds": 3.0, "unsourced": 0, "physical": 0, "blocking": 0, "problems": []},
            {"id": "b", "family": "f", "seconds": 5.0, "unsourced": 0, "physical": 0, "blocking": 0, "problems": []}]
    assert bench.report(rows)["gate"] is True
    rows[1]["physical"] = 1
    assert bench.report(rows)["gate"] is False


def test_tools_used_reads_the_turn_log():
    log = ["assistant", "plan", "move_place:error [x]", "say pruned: numbers [3]", "t_call 1.2"]
    assert bench.tools_used(log) == {"plan", "move_place"}


def test_a_move_and_a_reorder_on_the_full_bench_plan_are_applied_not_refused():
    """Root cause of move 0.0 / reorder 0.0 (2026-10-30): the bench plan is full, so every move leaves the day past its end or
    a sunrise place off its time; the assistant took each act back. Now only physical / impossible violations are refused;
    the rest is flagged (docs/PLANNING.md). Real snapshot, no model: a scripted tool call per case."""
    import json
    from langchain_core.messages import AIMessageChunk

    class Script:
        def __init__(self, *calls):
            self.calls = list(calls)

        async def __call__(self, messages, tools, on_say):
            if not self.calls:
                return AIMessageChunk(content="Xong.")
            name, args = self.calls.pop(0)
            return AIMessageChunk(content="", tool_call_chunks=[{"id": "c1", "name": name, "args": json.dumps(args, ensure_ascii=False), "index": 0}])

    engine, _, decision = bench.build(False)
    sid = bench.start(engine, decision)
    view = engine.load(sid)["view"]
    p1, p2, p3, p4 = bench.stop_names(view)
    day1 = [it["name"] for it in view["itinerary"][0]["items"] if it["kind"] == "visit" and it.get("place_id")]
    turns = [("move_place", dict(place=p1, day=2, quote=f"Chuyển {p1} sang ngày 2"), f"Chuyển {p1} sang ngày 2"),
             ("move_place", dict(place=p3, day=1, quote=f"{p3} ở ngày 1"), f"Mình muốn {p3} ở ngày 1"),
             ("reorder_day", dict(day=1, order=[p2, *[x for x in day1 if x != p2]], quote=f"{p2} trước {p1}"), f"Cho mình đi {p2} trước {p1}"),
             ("reorder_day", dict(day=1, order=[*[x for x in day1 if x != p1], p1], quote=f"{p1} đi cuối"), f"Để {p1} đi cuối ngày 1")]
    for tool, args, text in turns:
        position = engine._get(sid).position
        engine.assistant = Script((tool, args))
        engine.turn(sid, text, lambda *a: None)
        assert engine._get(sid).position == position + 1, (text, engine.turn_log[sid])
        engine.act(sid, {"type": "undo"})
