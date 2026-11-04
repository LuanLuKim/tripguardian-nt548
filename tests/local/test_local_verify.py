"""Second look (corpus.local.verify, docs/CORPUS.md, Tri thức bản địa): a quote the Extractor says does not state the claim is
dropped from its evidence and the independent sources are counted again; nothing unchecked counts toward `kept`."""

import asyncio
import json
from datetime import UTC, datetime

from corpus.local import group_claims, run_group, run_verify
from corpus.local.group import candidate_rows
from corpus.local.verify import load_cache, passage, todo, verify, vkey

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def row(domain, text, *, quote=None, subject="Thác Datanla", subject_kind="area", kind="access", doc=None, months=()):
    return {"doc_id": doc or f"{domain}-d", "source_url": f"https://{domain}/x", "domain": domain,
            "retrieved_at": "2026-10-28T00:00:00+00:00", "subject_kind": subject_kind, "subject": subject,
            "subject_id": None, "kind": kind, "text": text, "quote": quote or text, "amount_min_vnd": None,
            "amount_max_vnd": None, "when": {"months": list(months), "days": [], "hours": "", "weather": ""}, "who": "",
            "title": "T", "chunk": f"Bối cảnh. {quote or text} Hết."}


ROWS = [row("a.vn", "nằm giữa đèo Prenn cách trung tâm 5 km"), row("b.vn", "nằm giữa đèo Prenn cách trung tâm 5 km hướng nam"),
        row("c.vn", "nằm giữa đèo Prenn cách trung tâm 5 km theo quốc lộ")]


def verdicts_for(ok_domains):
    return {vkey(r): "none" if r["domain"] in ok_domains else "different_thing" for r in ROWS}


def test_a_rejected_row_is_dropped_and_the_sources_are_counted_again():
    assert group_claims(ROWS, now=NOW, city_name="Đà Lạt")[0]["sources"] == 3
    out = group_claims(ROWS, now=NOW, city_name="Đà Lạt", verdicts=verdicts_for({"a.vn", "b.vn"}), vkey=vkey)
    assert out[0]["status"] == "kept" and out[0]["domains"] == ["a.vn", "b.vn"] and len(out[0]["evidence"]) == 2
    out = group_claims(ROWS, now=NOW, city_name="Đà Lạt", verdicts=verdicts_for({"c.vn"}), vkey=vkey)
    assert out[0]["status"] == "unverified" and out[0]["domains"] == ["c.vn"]
    assert group_claims(ROWS, now=NOW, city_name="Đà Lạt", verdicts=verdicts_for(set()), vkey=vkey) == []


def test_a_row_nobody_checked_is_no_evidence_for_kept():
    verdicts = verdicts_for({"a.vn", "b.vn", "c.vn"})
    del verdicts[vkey(ROWS[1])]   # never asked
    out = group_claims(ROWS, now=NOW, city_name="Đà Lạt", verdicts=verdicts, vkey=vkey)
    assert out[0]["status"] == "kept" and out[0]["domains"] == ["a.vn", "c.vn"]
    del verdicts[vkey(ROWS[2])]
    out = group_claims(ROWS, now=NOW, city_name="Đà Lạt", verdicts=verdicts, vkey=vkey)
    assert out[0]["status"] == "unverified"   # one checked source is not two


def test_a_claim_of_one_source_is_a_reference_and_needs_no_verdict():
    out = group_claims(ROWS[:1], now=NOW, city_name="Đà Lạt", verdicts={}, vkey=vkey)
    assert out[0]["status"] == "unverified" and len(out[0]["evidence"]) == 1


def test_the_rows_to_check_are_those_of_clusters_that_would_be_kept():
    lone = row("z.vn", "bánh căn ăn nóng", subject="bánh căn", subject_kind="dish", kind="tip")
    assert [r["domain"] for r in candidate_rows(ROWS + [lone], city_name="Đà Lạt")] == ["a.vn", "b.vn", "c.vn"]


def test_the_passage_shows_the_quote_between_marks_in_its_context():
    p = passage("Mở đầu dài. Đèo Prenn rất đẹp. Kết thúc.", "Đèo Prenn rất đẹp.", 8, 4)
    assert "<<Đèo Prenn rất đẹp.>>" in p and p.startswith("…") and "Kết" in p


def test_verify_asks_each_row_once_and_remembers_the_answer(tmp_path):
    out = tmp_path / "verified.jsonl"
    asked = []

    async def ask(**fields):
        asked.append(fields)
        return {"problem": "none" if "km" in fields["text"] else "not_stated"}
    items = todo(ROWS, load_cache(out))
    assert len(items) == 3
    stats = asyncio.run(verify(items, city_name="Đà Lạt", ask=ask, model="fake", out=out, parallel=2))
    assert stats["asked"] == 3 and stats["ok"] == 3 and "<<" in asked[0]["passage"]
    assert todo(ROWS, load_cache(out)) == []   # nothing left to ask
    assert len(load_cache(out)) == 3


def test_a_failed_call_writes_nothing_and_is_asked_again(tmp_path):
    out = tmp_path / "verified.jsonl"

    async def broken(**fields):
        raise RuntimeError("server down")
    stats = asyncio.run(verify(todo(ROWS, {}), city_name="Đà Lạt", ask=broken, model="m", out=out))
    assert stats["failed"] == 3 and not out.exists()
    assert len(todo(ROWS, load_cache(out))) == 3


def test_run_verify_then_group_keeps_only_what_was_checked(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    docs = tmp_path / "web" / "dalat" / "documents"
    docs.mkdir(parents=True)
    ext = tmp_path / "dalat" / "local" / "extracted"
    ext.mkdir(parents=True)
    (tmp_path / "serving").mkdir()
    (tmp_path / "serving" / "places.json").write_text(json.dumps({"records": []}), encoding="utf-8")
    for did, domain, tail in (("d1", "a.vn", "một"), ("d2", "b.vn", "hai")):
        text = f"Thác Datanla nằm giữa đèo Prenn cách trung tâm 5 km {tail}."
        (docs / f"{did}.json").write_text(json.dumps({
            "doc_id": did, "source_url": f"https://{domain}/x", "domain": domain, "title": "Thác Datanla Đà Lạt",
            "retrieved_at": "2026-10-28T00:00:00+00:00", "lang": "vi", "kind": "web",
            "sections": [{"heading": "", "text": text}]}), encoding="utf-8")
        item = {"subject_kind": "area", "subject_text": "Thác Datanla", "kind": "access", "text": f"cách trung tâm 5 km {tail}",
                "amount_min_vnd": 0, "amount_max_vnd": 0, "months": [], "days": [], "hours": "", "weather": "", "who": "",
                "quote": text}
        (ext / f"{did}.json").write_text(json.dumps({"doc_id": did, "chunks": [{"heading": "", "text": text,
                                                                               "items": [item]}]}), encoding="utf-8")

    async def ask(**fields):
        return {"problem": "none" if "một" in fields["passage"] else "different_thing"}
    stats = asyncio.run(run_verify("dalat", ask=ask, model="fake"))
    assert stats["asked"] == 2 and stats["rounds"] == 1
    out = run_group("dalat", general=[], now=NOW)
    doc = [c for c in out["claims"] if c["origin"] == "document"]
    assert out["stats"]["verified"] == 2 and [c["status"] for c in doc] == ["unverified"] and doc[0]["domains"] == ["a.vn"]


def test_a_kept_claim_needs_a_passing_claim_level_check_against_all_its_quotes():
    from corpus.local.verify import ckey
    claims = group_claims(ROWS, now=NOW, city_name="Đà Lạt")
    assert claims[0]["status"] == "kept"
    kw = dict(now=NOW, city_name="Đà Lạt")
    assert group_claims(ROWS, **kw, claim_verdicts={}, ckey=ckey)[0]["status"] == "unverified"   # never compared
    assert group_claims(ROWS, **kw, claim_verdicts={ckey(claims[0]): "different_things"}, ckey=ckey)[0]["status"] == "unverified"
    assert group_claims(ROWS, **kw, claim_verdicts={ckey(claims[0]): "none"}, ckey=ckey)[0]["status"] == "kept"


def test_claim_checks_are_asked_once_per_kept_claim_with_all_quotes(tmp_path):
    from corpus.local.verify import claim_todo, verify_claims
    claims = group_claims(ROWS, now=NOW, city_name="Đà Lạt")
    out = tmp_path / "verified_claims.jsonl"
    asked = []

    async def ask(**fields):
        asked.append(fields)
        return {"problem": "months_differ"}
    items = claim_todo(claims, load_cache(out))
    assert len(items) == 1
    stats = asyncio.run(verify_claims(items, city_name="Đà Lạt", chunks={}, ask=ask, model="m", out=out))
    assert stats == {"asked": 1, "failed": 0, "ok": 0, "rejected": 1}
    assert asked[0]["quotes"].count("<<") == 3 and "(a.vn)" in asked[0]["quotes"]
    assert claim_todo(claims, load_cache(out)) == []
