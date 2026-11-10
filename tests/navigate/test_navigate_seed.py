import json
import sys

import pytest
import yaml

from corpus import navigate


@pytest.fixture
def seed_path(tmp_path):
    path = tmp_path / "navigate.yaml"
    path.write_text(yaml.safe_dump({"seed": {"dalat": [
        {"name": "Biệt thự Hằng Nga", "area_hint": "", "why": "famous architecture"},
        {"name": "Đường hầm đất sét", "area_hint": "Tà Nung", "why": "famous sight"},
    ]}}, allow_unicode=True), encoding="utf-8")
    return path


def test_enqueue_dedups_by_folded_name(data):
    rows = [{"name": "Biệt thự Hằng Nga"}, {"name": "biet thu hang nga"}]
    assert navigate.enqueue_nominees("dalat", rows) == 1
    queue = data / "dalat" / "navigate" / "resolve_queue.jsonl"
    assert len(queue.read_text(encoding="utf-8").splitlines()) == 1
    assert navigate.enqueue_nominees("dalat", rows) == 0


def test_seed_reads_config_and_is_idempotent(data, seed_path):
    assert navigate.seed("dalat", seed_path) == 2
    assert navigate.seed("dalat", seed_path) == 0
    queue = data / "dalat" / "navigate" / "resolve_queue.jsonl"
    rows = [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {"name": "Biệt thự Hằng Nga", "area_hint": "", "aspect": "seed", "why": "famous architecture"},
        {"name": "Đường hầm đất sét", "area_hint": "Tà Nung", "aspect": "seed", "why": "famous sight"},
    ]


def test_pending_includes_seed(data, seed_path):
    navigate.seed("dalat", seed_path)
    pending = navigate.pending_nominees("dalat")
    assert {row["name"] for row in pending} == {"Biệt thự Hằng Nga", "Đường hầm đất sét"}
    assert all(row["aspect"] == "seed" for row in pending)
    navigate.record_resolution("dalat", {"name": "Biệt thự Hằng Nga", "status": "resolved"})
    assert [row["name"] for row in navigate.pending_nominees("dalat")] == ["Đường hầm đất sét"]


def test_seed_missing_city_is_zero(data, seed_path):
    assert navigate.seed("hanoi", seed_path) == 0
    seed_path.write_text("match: {}\n", encoding="utf-8")
    assert navigate.seed("dalat", seed_path) == 0
    seed_path.write_text("", encoding="utf-8")
    assert navigate.seed("dalat", seed_path) == 0
    assert not (data / "dalat" / "navigate").exists()


def test_seed_cli(data, monkeypatch, capsys):
    from corpus.__main__ import main

    monkeypatch.setattr(navigate, "seed", lambda city: 15 if city == "dalat" else 0)
    monkeypatch.setattr(sys, "argv", ["corpus", "navigate", "seed", "--city", "dalat"])
    main()
    assert capsys.readouterr().out == (
        "navigate seed dalat: 15 added to resolve_queue\n"
        "next: python -m corpus gmaps resolve --city dalat\n"
    )
