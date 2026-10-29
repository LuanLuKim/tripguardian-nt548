"""Extract phase (docs/CORPUS.md, Tri thức bản địa): Document sections -> chunks -> one Extractor call each; the raw
answers are cached per document, so a second run makes no call."""

import asyncio
import json

from corpus.local import chunks, extract


def doc(did="d1", sections=None):
    return {"doc_id": did, "source_url": f"https://a.vn/{did}", "domain": "a.vn", "title": "Mùa hoa",
            "retrieved_at": "2026-10-28T07:00:00+00:00", "lang": "vi", "kind": "web",
            "sections": sections or [{"heading": "Mùa hoa", "text": "Tháng 1 mai anh đào nở."},
                                     {"heading": "Đi lại", "text": "Thuê xe máy 100.000đ/ngày."}]}


def test_chunks_pack_sections_up_to_the_limit_and_split_a_long_one():
    parts = chunks(doc(), max_chars=1000)
    assert len(parts) == 1 and parts[0]["heading"] == "Mùa hoa"
    assert "Tháng 1 mai anh đào nở." in parts[0]["text"] and "Thuê xe máy" in parts[0]["text"]
    long = doc(sections=[{"heading": "A", "text": "\n\n".join(["x" * 60] * 10)}])
    parts = chunks(long, max_chars=200)
    assert len(parts) > 1 and all(len(p["text"]) <= 200 for p in parts)


def test_extract_calls_once_per_chunk_and_caches_the_raw_answers(tmp_path):
    calls = []

    async def ask(**fields):
        calls.append(fields)
        return {"claims": [{"subject_kind": "phenomenon", "subject_text": "mai anh đào", "kind": "season",
                            "text": "mai anh đào nở", "amount_min_vnd": 0, "amount_max_vnd": 0,
                            "months": [1], "days": [], "hours": "", "weather": "", "who": "",
                            "quote": "Tháng 1 mai anh đào nở."}]}

    out = tmp_path / "extracted"
    stats = asyncio.run(extract([doc()], out, city_name="Đà Lạt", ask=ask, model="fake", chunk_chars=1000))
    assert stats == {"docs": 1, "read": 1, "cached": 0, "failed": 0, "chunks": 1}
    assert calls[0]["city"] == "Đà Lạt" and calls[0]["url"] == "https://a.vn/d1"
    saved = json.loads((out / "d1.json").read_text(encoding="utf-8"))
    assert saved["model"] == "fake" and saved["chunks"][0]["items"][0]["subject_text"] == "mai anh đào"
    stats = asyncio.run(extract([doc()], out, city_name="Đà Lạt", ask=ask, model="fake", chunk_chars=1000))
    assert stats["cached"] == 1 and len(calls) == 1


def test_a_failed_call_writes_nothing_and_logs_the_error(tmp_path):
    async def ask(**fields):
        raise ValueError("bad json")

    out = tmp_path / "extracted"
    stats = asyncio.run(extract([doc()], out, city_name="Đà Lạt", ask=ask, model="fake", chunk_chars=1000))
    assert stats["failed"] == 1 and not (out / "d1.json").exists()
    err = json.loads((tmp_path / "errors.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert err["id"] == "d1" and "bad json" in err["error"]
