"""python -m bench assistant, offline: a scripted agent on the served-record fixture of tests/trip (no network)."""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "trip"))
from trip_fixtures import ScriptedChat, call, reply, say, served  # noqa: E402

from bench.assistant import cases, passes, run, seed  # noqa: E402


def engine(chat, tmp_path):
    from corpus import load_ontology
    from corpus.retrieval import RetrievalEngine
    from corpus.snapshot import Region
    from trip import Catalog, Engine, SessionStore, Settings
    from trip.infrastructure.knowledge import Knowledge, LiveTools
    from trip.infrastructure.settings import Assistant
    records = [served("0xa:0x1", "Cà Phê Đồi Thông Xanh", {"scenic_view": "present"}, voices=90),
               served("0xd:0x1", "Đồi Chè Cầu Đất Farm", {}, group="nature", category="Đồi chè", voices=60)]
    retrieval = RetrievalEngine(_index=None, _snapshot=MagicMock(), _region=Region.from_records(records),
                                _ontology=load_ontology(), release_id="r-test")
    catalog = Catalog.from_records([], 1, evidence={r["id"]: r for r in records})
    weather = lambda lat, lng, days: {d: {"rain_prob": 0.3, "source": "open-meteo", "fetched_at": "x"} for d in days}  # noqa: E731
    cfg = Settings(n_min=1, top_k=4, enough_factor=1.0, assistant=Assistant(enabled=True),
                   gaps_path=str(tmp_path / "gaps.jsonl"))
    return Engine(catalog, cfg, SessionStore(None), chat, today=lambda: date(2026, 10, 28),
                  knowledge=Knowledge(retrieval, catalog, LiveTools(weather=weather), ("Chợ Đà Lạt", 11.9429, 108.4372)))


def test_bench_cases_load():
    items = cases()
    assert len(items) == 30 and items[0][1] == {"places"}


def test_seed_is_the_bench_trip():
    st = seed()
    assert st.start_date.value == date(2026, 10, 30) and st.days.value == 3 and st.people.value == 2


def test_bench_assistant_summary_shape(tmp_path):
    chat = ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]})),
                        say("Bạn thử Cà Phê Đồi Thông Xanh nhé."),
                        say("Ngày 31/10 khả năng mưa 30%."))
    rows, s = run(engine(chat, tmp_path), [("Gợi ý quán cà phê có view đồi thông cho mình với", {"places"}),
                                           ("Ngày 31/10 Đà Lạt có mưa không?", {"weather"})])
    assert {"p50_s", "p90_s", "calls_per_turn", "single_call_rate", "clef_full", "ungrounded"} <= set(s)
    assert s["ungrounded"] == 0 and s["clef_full"] == 2 and s["calls_per_turn"] == 1.5 and s["single_call_rate"] == 0.5
    assert rows[0]["shown"] and "30%" in rows[1]["say"]
    assert not passes({**s, "clef_full": 2})


def test_bench_rows_time_each_agent_call(tmp_path):
    chat = ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]})), say("Bạn thử Cà Phê Đồi Thông Xanh nhé."))
    rows, _ = run(engine(chat, tmp_path), [("Gợi ý quán cà phê có view đồi thông cho mình với", {"places"})])
    assert len(rows[0]["call_s"]) == rows[0]["calls"] and all(x >= 0 for x in rows[0]["call_s"])
    assert rows[0]["other_s"] >= 0


def test_nodata_with_cards_counts_a_no_data_reply_under_shown_places(tmp_path):
    from bench.assistant import NO_DATA, summary
    chat = ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]})),
                        say("Mình chưa có dữ liệu về quán nào hợp với bạn."))
    rows, s = run(engine(chat, tmp_path), [("Gợi ý quán cà phê có view đồi thông cho mình với", {"places"})])
    assert rows[0]["shown"] and rows[0]["nodata_with_cards"] and s["nodata_with_cards"] == 1
    assert not passes({**s, "p50_s": 1, "p90_s": 1, "clef_full": 30, "ungrounded": 0})
    assert NO_DATA.search("Mình chưa có thông tin xu hướng") and not NO_DATA.search("Bạn thử Cà Phê Đồi Thông Xanh nhé.")
    assert summary([{**rows[0], "nodata_with_cards": False}])["nodata_with_cards"] == 0


def test_v2_cases_load_and_follow_the_documented_format():
    from bench.assistant import load_cases, runnable
    items = load_cases()
    fams = {}
    for c in items:
        fams.setdefault(c.family, []).append(c)
    assert {"followup", "photo", "link", "multi", "who", "offtopic", "rule"} <= set(fams) and all(len(fams[f]) >= 5 for f in fams)
    link = next(c for c in items if c.id == "link-maps")
    assert link.turns[-1][0].endswith("17z") and "https://www.google.com/maps" in link.turns[-1][0]
    ok, skipped = runnable(items)
    assert not skipped and all(c.photos for c in items if c.family == "photo")  # the fixtures are in tests/fixtures/perceive/app/
    assert next(c for c in items if c.id == "photo-what").photo_sure is False
    assert next(c for c in items if c.id == "rule-r3").blocked == "R3"


def test_v2_case_without_its_photo_is_skipped_not_failed(tmp_path):
    from bench.assistant import Case, runnable
    gone = Case("x", "photo", (("hi", "tests/fixtures/perceive/app/does-not-exist.png"),))
    ok, skipped = runnable([gone, Case("y", "followup", (("hi", None),))])
    assert skipped == ["x"] and [c.id for c in ok] == ["y"]


def test_v2_run_measures_tools_cards_and_guard(tmp_path):
    from bench.assistant import Case, passes_v2, run_v2, summary_v2
    chat = ScriptedChat(reply(call("find_places", criteria={"groups": ["cafe"]})), say("Bạn thử Cà Phê Đồi Thông Xanh nhé."),
                        say("Mình chỉ hỗ trợ chuyến Đà Lạt thôi, bạn cần gợi ý chỗ nào?"))
    eng = engine(chat, tmp_path)
    row = run_v2(eng, Case("a", "places", (("Gợi ý quán cà phê view đồi thông cho mình với", None),), frozenset({"places"}), True))
    # Independent read tools may finish in either order; early weather prefetch must not hide the place lookup.
    assert row["tool_group_ok"] and row["shown"] and not row["problems"]
    assert "find_places" in row["tools"]
    off = run_v2(eng, Case("b", "offtopic", (("Hôm nay bóng đá thế nào?", None),), cards=False, reply_has=("Đà Lạt",)))
    assert not off["problems"] and not off["wrong_block"]
    s = summary_v2([row, off])
    assert s["tool_group_by_family"] == {"places": 1.0} and s["wrong_blocks"] == 0 and s["photo_guesses"] == 0
    assert "cached_ratio" in s and not passes_v2({**s, "p50_s": 99})


def test_cached_pair_sums_the_turns_calls():
    from bench.assistant import cached_pair
    assert cached_pair(["t_call 1.0", "cached_tokens 100/400", "cached_tokens 300/500"]) == (400, 900)


def test_guard_set_runner_counts_wrong_blocks_and_recall(tmp_path):
    from agents.assistant import guard
    from bench.assistant import GUARD_CASES, run_guard_set

    def perfect(state, questions):
        label = next(c["label"] for c in __import__("yaml").safe_load(GUARD_CASES.read_text(encoding="utf-8"))["cases"]
                     if c["text"] == state["user_message"])
        return {guard.QUESTION: {"choice": label, "probabilities": {label: 0.99}}}
    r = run_guard_set(perfect, 0.55)
    assert r["passes"] and r["wrong_blocks"] == 0 and r["rule_recall"] == 1.0 and r["sentences"] >= 80
    r = run_guard_set(lambda s, q: {guard.QUESTION: {"choice": "R3", "probabilities": {"R3": 0.99}}}, 0.55)
    assert not r["passes"] and r["wrong_blocks"] > 40


def test_bench_photo_is_a_data_uri_trip_accepts():
    from bench.assistant import photo_b64
    from trip.infrastructure.images import sanitize_photo
    assert sanitize_photo(photo_b64("tests/fixtures/perceive/app/plan-gate.png"))


def test_assistant_overrides_are_typed_and_checked():
    from bench.assistant import assistant_overrides
    from trip.infrastructure.settings import Assistant
    got = assistant_overrides("covered_tools=all, hide_prepared_lookup=false,prefetch_wait_s=2", Assistant())
    assert got == {"covered_tools": "all", "hide_prepared_lookup": False, "prefetch_wait_s": 2.0}
    assert assistant_overrides("", Assistant()) == {}
    import pytest
    with pytest.raises(ValueError):
        assistant_overrides("nope=1", Assistant())
