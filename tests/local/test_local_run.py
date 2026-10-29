"""`local extract` + `local group` end to end with a fake Extractor in a temp DATA_DIR: Documents -> extracted answers
-> gated, grouped LocalClaims + sol's claims with a status -> data/<city>/local/."""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from corpus.local import run_extract, run_group

SEC = "Từ tháng 1 đến tháng 2 mai anh đào nở rộ. Ghé Hồ Tuyền Lâm lúc sáng sớm. Ghé Quán Ma Không Có Thật cho vui."


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    docs = tmp_path / "web" / "dalat" / "documents"
    docs.mkdir(parents=True)
    for did, domain in (("d1", "a.vn"), ("d2", "b.vn")):
        (docs / f"{did}.json").write_text(json.dumps({
            "doc_id": did, "source_url": f"https://{domain}/x", "domain": domain, "title": "Mùa hoa",
            "retrieved_at": "2026-10-28T00:00:00+00:00", "lang": "vi", "kind": "web",
            "sections": [{"heading": "Mùa hoa", "text": SEC}]}), encoding="utf-8")
    (tmp_path / "serving").mkdir()
    (tmp_path / "serving" / "places.json").write_text(json.dumps({"records": [
        {"id": "fid:lake", "status": "VERIFIED", "identity": {"name": "Hồ Tuyền Lâm", "lat": 11.9, "lng": 108.4}}]}),
        encoding="utf-8")
    return tmp_path


def claim(subject_kind, subject, kind, text, quote, months=()):
    return {"subject_kind": subject_kind, "subject_text": subject, "kind": kind, "text": text, "amount_min_vnd": 0,
            "amount_max_vnd": 0, "months": list(months), "days": [], "hours": "", "weather": "", "who": "",
            "quote": quote}


async def fake_ask(**fields):
    return {"claims": [
        claim("phenomenon", "mai anh đào", "season", "mai anh đào nở rộ",
              "Từ tháng 1 đến tháng 2 mai anh đào nở rộ", [1, 2]),
        claim("poi", "Hồ Tuyền Lâm", "best_time", "lúc sáng sớm", "Ghé Hồ Tuyền Lâm lúc sáng sớm"),
        claim("poi", "Quán Ma Không Có Thật", "tip", "cho vui", "Ghé Quán Ma Không Có Thật cho vui"),
        claim("city", "Đà Lạt", "tip", "đi chợ", "Đà Lạt có chợ đêm")]}  # quote not in the page: dropped


GENERAL = [{"claim_id": "g1", "subject_kind": "phenomenon", "subject": "Mai anh đào Đà Lạt", "kind": "season",
            "text": "Mai anh đào thường nở khoảng tháng 1 đến tháng 3",
            "when": {"months": [1, 2, 3], "days": [], "hours": "", "weather": ""}, "source": "model"},
           {"claim_id": "g2", "subject_kind": "dish", "subject": "Bánh căn", "kind": "specialty",
            "text": "Bánh căn là món sáng", "when": {"months": [], "days": [], "hours": "", "weather": ""},
            "source": "model"}]


def test_extract_then_group_writes_the_local_claims(data):
    stats = asyncio.run(run_extract("dalat", ask=fake_ask, model="fake"))
    assert stats["read"] == 2
    out = run_group("dalat", general=GENERAL, now=datetime(2026, 10, 28, tzinfo=UTC))
    saved = json.loads((data / "dalat" / "local" / "local_claims.json").read_text(encoding="utf-8"))
    assert saved == out
    st = saved["stats"]
    assert st["items"] == 8 and st["gated"] == 6 and st["dropped"] == {"quote_not_in_source": 2}
    assert st["status"] == {"document": {"kept": 3}, "model": {"confirmed": 1, "unverified": 1}}
    by = {(c["origin"], c["subject"]): c for c in saved["claims"]}
    assert by[("document", "mai anh đào")]["status"] == "kept"
    lake = by[("document", "Hồ Tuyền Lâm")]
    assert (lake["subject_kind"], lake["subject_id"]) == ("poi", "fid:lake")
    ghost = by[("document", "Quán Ma Không Có Thật")]
    assert (ghost["subject_kind"], ghost["subject_id"]) == ("poi_unresolved", None)
    assert by[("model", "Mai anh đào Đà Lạt")]["status"] == "confirmed"
    assert by[("model", "Bánh căn")]["status"] == "unverified"
    assert all(e["quote"] and e["doc_id"] for c in saved["claims"] if c["origin"] == "document" for e in c["evidence"])
    poi = json.loads((data / "dalat" / "local" / "poi_claims.json").read_text(encoding="utf-8"))
    assert [c["subject_id"] for c in poi["claims"]] == ["fid:lake"]
    queue = [json.loads(x) for x in (data / "dalat" / "local" / "poi_unresolved.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [q["name"] for q in queue] == ["Quán Ma Không Có Thật"] and queue[0]["approval"] == "pending"


def test_extract_only_reads_the_named_documents_and_the_limit(data):
    stats = asyncio.run(run_extract("dalat", ask=fake_ask, model="fake", docs=["d2"]))
    assert stats["read"] == 1 and (data / "dalat" / "local" / "extracted" / "d2.json").exists()
    assert not (data / "dalat" / "local" / "extracted" / "d1.json").exists()
    stats = asyncio.run(run_extract("dalat", ask=fake_ask, model="fake", limit=1))
    assert stats["docs"] == 1
