"""Questions the assistant could not answer -> data/trip/gaps.jsonl for the corpus (spec §B.5; plan Task 6)."""

import json

from trip_fixtures import ScriptedChat, say

from trip.api.engine import TurnInput
from trip.infrastructure.gaps import record


def rows(p):
    return [json.loads(line) for line in p.read_text().splitlines()]


def test_gap_kinds_and_city(tmp_path):
    p = tmp_path / "gaps.jsonl"
    record(p, "quán mở 5h sáng", "zero_hits", topic="places")
    record(p, "quán mở 5h sáng", "zero_hits", topic="places")
    got = rows(p)
    assert got == [{"phrase": "quán mở 5h sáng", "kind": "zero_hits", "city": "dalat", "topic": "places",
                    "subject": None, "count": 2, "last_seen": got[0]["last_seen"]}]


def test_same_phrase_other_kind_is_its_own_row_and_old_rows_count_as_dalat(tmp_path):
    p = tmp_path / "gaps.jsonl"
    p.write_text(json.dumps({"phrase": "halal", "kind": "no_data", "count": 3, "last_seen": "x"}) + "\n")
    record(p, "halal", "no_data")
    record(p, "halal", "no_answer", topic="places")
    got = rows(p)
    assert [(r["kind"], r["count"]) for r in got] == [("no_data", 4), ("no_answer", 1)] and got[0]["city"] == "dalat"


def test_find_places_with_no_hit_is_a_gap(turn_tools, tmp_path):
    t = turn_tools()
    out = t.run("find_places", {"criteria": {"groups": ["cafe"], "opens_by": "04:00"}})
    assert out["places"] == []
    got = rows(tmp_path / "gaps.jsonl")
    assert got[0]["kind"] == "zero_hits" and json.loads(got[0]["phrase"]) == {"groups": ["cafe"], "opens_by": "04:00"}


def test_no_answer_and_unsourced_place_are_gaps(make_assistant, tmp_path):
    e = make_assistant(ScriptedChat(say("Bạn ghé Khách Sạn Đồi Chè nhé. Giờ mở cửa thì mình chưa có thông tin.")))
    sid = e.create("first", "nothing")["id"]
    e.turn(sid, TurnInput(kind="text", text="Gợi ý quán cà phê mở sớm"), lambda *a: None)
    got = {r["kind"]: r for r in rows(tmp_path / "gaps.jsonl")}
    assert got["unsourced_place"]["subject"] == "0xe:0x1"
    assert got["no_answer"]["phrase"] == "Gợi ý quán cà phê mở sớm" and got["no_answer"]["topic"] == "places"
    assert all(set(r) == {"phrase", "kind", "city", "topic", "subject", "count", "last_seen"} for r in got.values())
