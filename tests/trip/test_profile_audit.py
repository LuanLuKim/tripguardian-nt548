"""The Judge reads a sample of active profile entries with their evidence (docs/TRIP_UNDERSTANDING.md §17)."""

import json
import random
from datetime import date, timedelta

from trip.domain.patterns import Summary, entry_id
from trip.infrastructure.profile import ProfileStore
from trip.infrastructure.profile_audit import audit, render
from trip.infrastructure.settings import PatternSettings

TODAY = date(2026, 10, 28)
CFG = PatternSettings(enabled=True, min_sessions=3, window=8, agreement=0.75, stale_days=365, max_places=2)
UIDS = ("user-aaaa-1111", "user-bbbb-2222")


def fill(store):
    for uid in UIDS:
        for i in range(3):
            store.record(uid, Summary(sid=f"{uid}-{i}", day=TODAY - timedelta(days=5 - i),
                                      votes={"pace": "slow", "novelty": "new"}, how={"pace": "said"},
                                      quotes={"pace": "đi chậm thôi"}))
        store.record(uid, Summary(sid=f"{uid}-x", day=TODAY, votes={"purpose": "photo"}))  # a candidate: not read


def test_render_shows_statement_signal_and_evidence(tmp_path):
    store = ProfileStore(tmp_path, CFG)
    fill(store)
    _, found = store.entries(UIDS[0], TODAY)
    text = render([e for e in found if e.key == "pace"])
    assert "1." in text and "pace=slow" in text and "đi chậm thôi" in text and "said" in text


def test_judge_flags_lower_entries_and_are_logged_for_review(tmp_path):
    store = ProfileStore(tmp_path / "profiles", CFG)
    fill(store)
    seen = []

    def ask(entries):
        seen.append(entries)
        n = entries.count("\n\n") + 1
        return {"verdicts": [{"n": 1, "verdict": "overgeneral", "reason": "một chuyến không đủ"},
                             *({"n": i, "verdict": "ok", "reason": ""} for i in range(2, n + 1)),
                             {"n": 99, "verdict": "unsupported", "reason": "không có mục này"}]}

    log = tmp_path / "audit.jsonl"
    out = audit(store, TODAY, ask, n=10, rng=random.Random(1), log_path=log)
    assert out == {"read": 4, "flagged": 1}
    assert len(seen) == 1 and "purpose=photo" not in seen[0]  # only active entries are read
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert [x["verdict"] for x in lines] == ["overgeneral"]
    flagged = lines[0]
    _, found = store.entries(flagged["user_id"], TODAY)
    assert next(e for e in found if e.id == flagged["entry_id"]).status == "weak"


def test_a_failing_judge_decides_nothing(tmp_path):
    store = ProfileStore(tmp_path / "profiles", CFG)
    fill(store)

    def down(entries):
        raise OSError("judge down")

    assert audit(store, TODAY, down, n=10, rng=random.Random(1), log_path=tmp_path / "a.jsonl") == {"read": 4, "flagged": 0}
    assert all(e.status == "active" for e in store.entries(UIDS[0], TODAY)[1] if e.key != "purpose")


def test_user_edited_entries_are_not_sent(tmp_path):
    store = ProfileStore(tmp_path / "profiles", CFG)
    fill(store)
    for uid in UIDS:
        store.edit(uid, entry_id("pace", "slow"), statement="Đi thong thả")
    seen = []
    audit(store, TODAY, lambda entries: seen.append(entries) or {"verdicts": []}, n=10, rng=random.Random(1),
          log_path=tmp_path / "a.jsonl")
    assert "pace=slow" not in seen[0]
