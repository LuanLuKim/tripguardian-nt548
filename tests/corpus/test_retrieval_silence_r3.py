"""Serving, snapshot and compact retrieval must agree on observed evidence."""

from copy import deepcopy

import orjson
import pyarrow as pa
import pytest

from corpus.ontology import load as load_ontology
from corpus.retrieval import card
from corpus.serving import feature
from corpus.snapshot import Region, tables


def record_with_feature(fid, value, status, **overrides):
    record = {
        "id": "silence-parity", "status": "VERIFIED", "operation": {},
        "identity": {"name": "Parity", "category_group": "cafe"},
        "usable_as": ["experience"],
    }
    group = load_ontology().features[fid].group
    record[group] = {fid: {
        "value": value, "status": status, "n": 3, "distribution": {value: 3},
        "evidence": ["review:1"], "by_context": {}, "mention_rate": 0.1,
        "confidence": {"agreement": 1.0}, **overrides,
    }}
    return record


@pytest.mark.parametrize("status", ["VERIFIED", "OUTDATED", "UNCERTAIN"])
@pytest.mark.parametrize("fid,value", [
    ("nature", "present"), ("crowd", "low"), ("entry_fee", "free"),
    ("steep_or_stairs", "absent"), ("kids", "suitable"),
])
@pytest.mark.parametrize("silence", [
    {"reason": "silence"},
    {"reason": "silence", "n": 0, "distribution": {}, "evidence": []},
    {"reason": "stale", "n": 0, "distribution": {}, "evidence": []},
])
def test_silence_is_unknown_in_serving_snapshot_and_compact_card(fid, value, status, silence):
    record = record_with_feature(fid, value, status, **silence)
    # Old snapshots may contain a value even when their JSON record only carries silence.
    observed = record_with_feature(fid, value, status)
    compiled = tables([observed])
    compiled["records"] = pa.Table.from_pylist(
        [{"id": record["id"], "json": orjson.dumps(record).decode()}],
        schema=compiled["records"].schema,
    )
    region = Region("legacy", compiled)
    before = deepcopy(record)

    assert feature(record, fid) is None
    column = region.feature(fid)
    assert column.value == [None] and not column.exists[0] and not column.firm[0]
    compact = card(record)
    assert f"{fid}={value}" not in compact.get("f", []) + compact.get("f?", [])
    assert card(region.record(record["id"])) == compact
    assert record == before


@pytest.mark.parametrize("status,key", [("VERIFIED", "f"), ("OUTDATED", "f"), ("UNCERTAIN", "f?")])
def test_observed_features_keep_the_same_value_and_status_across_readers(status, key):
    record = record_with_feature("steep_or_stairs", "absent", status)
    before = deepcopy(record)
    region = Region.from_records([record])

    assert feature(record, "steep_or_stairs")["value"] == "absent"
    assert region.feature("steep_or_stairs").value == ["absent"]
    assert region.feature("steep_or_stairs").status == [status]
    assert card(record)[key] == ["steep_or_stairs=absent"]
    assert ("f?" if key == "f" else "f") not in card(record)
    assert record == before


def test_silent_entry_fee_feature_cannot_establish_a_fee_conflict():
    record = record_with_feature(
        "entry_fee", "free", "UNCERTAIN", reason="conflicts_entry_fee_estimate",
        n=0, distribution={}, evidence=[],
    )
    record["operation"]["entry_fee"] = {"typical_vnd": 50000, "source": "official", "kind": "fact"}

    assert feature(record, "entry_fee") is None
    assert Region.from_records([record]).feature("entry_fee").value == [None]
    assert "conflict" not in card(record)["fee"]
    assert "f?" not in card(record)
