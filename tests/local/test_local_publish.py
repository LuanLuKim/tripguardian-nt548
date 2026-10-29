"""Publishing LocalClaims (docs/CORPUS.md, Tri thức bản địa): the snapshot carries a `local_claims` table, a region
reads it (an older snapshot without it reads as none known), retrieval.local_knowledge filters it."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "decision"))  # gen.py: generated serving records

from gen import records  # noqa: E402

from corpus.retrieval import local_knowledge  # noqa: E402
from corpus.snapshot import Region, Snapshot, compile_snapshot, tables  # noqa: E402


def lc(cid, status, *, origin="document", subject_kind="phenomenon", subject="mai anh đào", kind="season",
       months=(1, 2), sources=2):
    return {"claim_id": cid, "origin": origin, "status": status, "subject_kind": subject_kind, "subject": subject,
            "subject_id": None, "kind": kind, "text": f"text {cid}",
            "when": {"months": list(months), "days": [], "hours": "", "weather": ""}, "who": "",
            "amount_min_vnd": None, "amount_max_vnd": None, "domains": ["a.vn", "b.vn"][:sources],
            "sources": sources, "official": False, "confidence": 1.0,
            "evidence": [{"doc_id": "d1", "source_url": "https://a.vn/x", "domain": "a.vn",
                          "retrieved_at": "2026-10-28T00:00:00+00:00", "quote": "tháng 1 mai anh đào nở"}],
            "conflicts_with": [], "matched": []}


CLAIMS = [lc("k1", "kept"), lc("u1", "unverified", sources=1), lc("c1", "conflict"),
          lc("p1", "kept", subject_kind="poi_unresolved", subject="Quán Ma"),
          lc("m1", "confirmed", origin="model", sources=0), lc("m2", "contradicted", origin="model", sources=0),
          lc("m3", "unverified", origin="model", subject="Đà Lạt", subject_kind="city", kind="tip", months=(),
             sources=0)]


def test_tables_carry_local_claims_without_unresolved_venues():
    t = tables(records(1), local_claims=CLAIMS)["local_claims"]
    rows = {r["claim_id"]: r for r in t.to_pylist()}
    assert set(rows) == {"k1", "u1", "c1", "m1", "m2", "m3"}
    assert rows["k1"]["fact"] and rows["m1"]["fact"] and not rows["u1"]["fact"] and not rows["m3"]["fact"]
    assert rows["k1"]["months"] == [1, 2] and json.loads(rows["k1"]["evidence_json"])[0]["quote"]
    assert tables(records(1))["local_claims"].num_rows == 0


def test_local_knowledge_filters_and_never_serves_a_contradicted_claim():
    reg = Region("t", tables(records(1), local_claims=CLAIMS))
    got = local_knowledge(reg.local_claims, subject="Mai anh đào", kind="season", month=1)
    assert [c["claim_id"] for c in got] == ["k1", "m1", "c1", "u1"]  # facts first, then by sources
    assert all(c["claim_id"] != "m2" for c in local_knowledge(reg.local_claims))
    assert local_knowledge(reg.local_claims, month=5, kind="season") == []
    assert [c["claim_id"] for c in local_knowledge(reg.local_claims, month=5)] == ["m3"]  # all-year claims
    ref = local_knowledge(reg.local_claims, kind="tip")[0]
    assert ref["label"] == "reference" and not ref["fact"]
    assert [c["claim_id"] for c in local_knowledge(reg.local_claims, facts_only=True)] == ["k1", "m1"]


def test_compile_snapshot_publishes_the_city_local_claims(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    recs = records(2)
    (tmp_path / "serving").mkdir()
    (tmp_path / "serving" / "places.json").write_text(json.dumps({"built_at": "x", "records": recs}), encoding="utf-8")
    (tmp_path / "intel" / "places").mkdir(parents=True)
    (tmp_path / "dalat" / "local").mkdir(parents=True)
    (tmp_path / "dalat" / "local" / "local_claims.json").write_text(json.dumps({"claims": CLAIMS}), encoding="utf-8")
    compile_snapshot("dalat")
    reg = Snapshot.open().region("dalat")
    assert {c["claim_id"] for c in reg.local_claims} == {"k1", "u1", "c1", "m1", "m2", "m3"}


def test_a_snapshot_without_local_claims_reads_as_none_known(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    recs = records(2)
    (tmp_path / "serving").mkdir()
    (tmp_path / "serving" / "places.json").write_text(json.dumps({"built_at": "x", "records": recs}), encoding="utf-8")
    (tmp_path / "intel" / "places").mkdir(parents=True)
    version = compile_snapshot("dalat")["version"]
    import lancedb
    lancedb.connect(str(tmp_path / "snapshot" / version / "dalat")).drop_table("local_claims")  # an older snapshot
    t = {k: v for k, v in tables(recs).items() if k != "local_claims"}
    assert Region("old", t).local_claims == []
    assert Snapshot.open().region("dalat").local_claims == []
