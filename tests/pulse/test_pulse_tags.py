"""Pulse tag trends: the daily snapshot carries tags ranked by recent TikTok clips (docs/CORPUS.md §Nhịp, home page topics)."""

from datetime import UTC, datetime

from corpus import pulse
from corpus.pulse import store

TAG = {"ref": "experience:cloud_hunting", "axis": "experience", "key": "cloud_hunting", "label": "Săn mây", "places": 163,
       "clips": 43, "authors": 41, "newest": "2026-10-26", "top": ["p1", "p2"]}


def snap(day="2026-10-29", tags=(TAG,)):
    return {"city": "dalat", "generated_at": f"{day}T06:00:00+00:00", "day": day, "counts": {}, "inputs": {}, "items": [],
            "tags": list(tags)}


def at(day):
    return datetime.fromisoformat(f"{day}T08:00:00+00:00").astimezone(UTC)


def test_tag_trends_reads_the_snapshot_and_flags_stale(tmp_path):
    store.write("dalat", snap(), keep=5, root=tmp_path)
    t = pulse.tag_trends("dalat", now=at("2026-10-30"), root=tmp_path)
    assert t["as_of"] == "2026-10-29" and t["window_days"] == 30 and t["stale"] is False
    assert t["tags"][0]["label"] == "Săn mây" and t["tags"][0]["clips"] == 43
    assert pulse.tag_trends("dalat", now=at("2026-11-04"), root=tmp_path)["stale"] is True


def test_no_tags_when_the_job_never_wrote_them_or_they_are_old(tmp_path):
    assert pulse.tag_trends("nowhere", root=tmp_path) is None
    store.write("dalat", {**snap(), "tags": []}, keep=5, root=tmp_path)
    assert pulse.tag_trends("dalat", now=at("2026-10-30"), root=tmp_path) is None  # empty = the page shows its own topics
    store.write("dalat", snap("2026-10-01"), keep=5, root=tmp_path)
    assert pulse.tag_trends("dalat", now=at("2026-10-30"), root=tmp_path) is None  # older than hide_after_days
    old = {k: v for k, v in snap("2026-10-29").items() if k != "tags"}
    store.write("dalat", old, keep=5, root=tmp_path)
    assert pulse.tag_trends("dalat", now=at("2026-10-30"), root=tmp_path) is None  # a snapshot from before tags existed
