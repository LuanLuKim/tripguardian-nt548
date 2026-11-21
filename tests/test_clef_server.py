"""Batch grouping of scripts/clef_server.py: rows x longest row under the token cap, media records alone."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("torch")  # scripts/clef_server.py is a GPU model server; plain CI installs skip it

SPEC = importlib.util.spec_from_file_location("clef_server", Path(__file__).resolve().parent.parent / "scripts" / "clef_server.py")
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


def record(length, media=None):
    return SimpleNamespace(input_ids=(0,) * length, media=media)


def test_text_records_share_a_forward_under_the_token_cap():
    encoded = [record(500), record(600), record(550), record(520)]
    groups = server.batches(encoded, max_tokens=1800)
    assert sorted(i for g in groups for i in g) == [0, 1, 2, 3]
    for group in groups:
        assert len(group) * max(len(encoded[i].input_ids) for i in group) <= 1800
    assert len(groups) == 2


def test_media_records_go_alone_and_a_long_record_still_runs():
    encoded = [record(500, media={"pixel_values": 1}), record(9000), record(400)]
    groups = server.batches(encoded, max_tokens=4096)
    assert [0] in groups and [1] in groups and [2] in groups
