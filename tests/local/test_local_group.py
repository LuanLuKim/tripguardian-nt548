"""Grouping (docs/CORPUS.md, Tri thức bản địa): dedup, independent domains, conflict, confidence by age; sol's claims
confirmed / contradicted / unverified only against kept Document claims."""

from datetime import UTC, datetime

from corpus.local import check_model, group_claims

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def row(domain, text, *, subject="mai anh đào", subject_kind="phenomenon", kind="season", months=(), lo=None,
        hi=None, at="2026-10-28T00:00:00+00:00", doc=None):
    return {"doc_id": doc or f"{domain}-{text[:5]}", "source_url": f"https://{domain}/x", "domain": domain,
            "retrieved_at": at, "subject_kind": subject_kind, "subject": subject, "subject_id": None, "kind": kind,
            "text": text, "quote": text, "amount_min_vnd": lo, "amount_max_vnd": hi,
            "when": {"months": list(months), "days": [], "hours": "", "weather": ""}, "who": ""}


def by_text(claims):
    return {c["text"]: c for c in claims}


def test_two_independent_domains_keep_a_claim_one_domain_leaves_it_unverified():
    out = group_claims([row("a.vn", "mai anh đào nở rộ", months=[1, 2]),
                        row("b.vn", "hoa mai anh đào nở rộ", months=[1, 2]),
                        row("c.vn", "đi săn mây lúc bình minh", subject="săn mây", kind="tip"),
                        row("c.vn", "săn mây lúc bình minh đẹp", subject="săn mây", kind="tip", doc="c2")],
                       now=NOW, city_name="Đà Lạt")
    assert len(out) == 2
    kept = next(c for c in out if c["subject"] == "mai anh đào")
    assert kept["status"] == "kept" and kept["origin"] == "document" and kept["domains"] == ["a.vn", "b.vn"]
    assert len(kept["evidence"]) == 2 and all(e["quote"] for e in kept["evidence"])
    cloud = next(c for c in out if c["subject"] == "săn mây")
    assert cloud["status"] == "unverified" and cloud["domains"] == ["c.vn"]  # same site twice is one source


def test_an_official_domain_alone_keeps_a_claim():
    out = group_claims([row("dalat.lamdong.gov.vn", "lễ hội hoa tháng 12", kind="event", subject="festival hoa",
                            months=[12])], now=NOW, city_name="Đà Lạt")
    assert out[0]["status"] == "kept" and out[0]["official"] is True


def test_disjoint_months_on_the_same_subject_and_kind_are_a_conflict():
    out = group_claims([row("a.vn", "mai anh đào nở rộ", months=[1, 2]),
                        row("b.vn", "mai anh đào bắt đầu nở", months=[6, 7])], now=NOW, city_name="Đà Lạt")
    assert {c["status"] for c in out} == {"conflict"}
    a, b = out
    assert a["conflicts_with"] == [b["claim_id"]] and b["conflicts_with"] == [a["claim_id"]]


def test_one_source_cannot_overturn_a_claim_two_sources_keep():
    out = group_claims([row("a.vn", "mai anh đào nở rộ", months=[1, 2]),
                        row("b.vn", "hoa mai anh đào nở rộ", months=[1, 2]),
                        row("c.vn", "mai anh đào bắt đầu nở", months=[6, 7])], now=NOW, city_name="Đà Lạt")
    by = {tuple(c["domains"]): c["status"] for c in out}
    assert by == {("a.vn", "b.vn"): "kept", ("c.vn",): "conflict"}


def test_different_price_items_of_the_city_are_no_conflict():
    out = group_claims([row("a.vn", "thuê xe máy", subject="Đà Lạt", subject_kind="city", kind="price_norm",
                            lo=100000, hi=150000),
                        row("b.vn", "bữa sáng bình dân", subject="Đà Lạt", subject_kind="city", kind="price_norm",
                            lo=25000, hi=40000)], now=NOW, city_name="Đà Lạt")
    assert {c["status"] for c in out} == {"unverified"}


def test_confidence_halves_after_the_half_life_and_notices_age_fast():
    old = group_claims([row("a.vn", "mai anh đào nở rộ", at="2025-10-28T00:00:00+00:00")], now=NOW,
                       city_name="Đà Lạt")[0]
    assert abs(old["confidence"] - 0.5) < 0.01
    notice = group_claims([row("a.vn", "đóng cửa bảo trì", kind="notice", subject="Đà Lạt", subject_kind="city",
                               at="2026-09-28T00:00:00+00:00")], now=NOW, city_name="Đà Lạt")[0]
    assert abs(notice["confidence"] - 0.5) < 0.01


def model(text, *, subject="Mai anh đào Đà Lạt", subject_kind="phenomenon", kind="season", months=()):
    return {"claim_id": "m1", "subject_kind": subject_kind, "subject": subject, "kind": kind, "text": text,
            "when": {"months": list(months), "days": [], "hours": "", "weather": ""}, "source": "model"}


KEPT = group_claims([row("a.vn", "mai anh đào nở rộ", months=[1, 2]), row("b.vn", "hoa mai anh đào nở rộ", months=[1, 2]),
                     row("a.vn", "thuê xe máy", subject="Đà Lạt", subject_kind="city", kind="price_norm", lo=100000,
                         hi=150000),
                     row("b.vn", "thuê xe máy giá", subject="Đà Lạt", subject_kind="city", kind="price_norm",
                         lo=120000, hi=150000),
                     row("c.vn", "bánh căn nóng", subject="bánh căn", subject_kind="dish", kind="specialty")],
                    now=NOW, city_name="Đà Lạt")


def test_a_model_claim_matching_a_kept_claim_is_confirmed():
    out = check_model([model("Mai anh đào thường nở khoảng tháng 1 đến tháng 3", months=[1, 2, 3])], KEPT,
                      city_name="Đà Lạt")
    assert out[0]["status"] == "confirmed" and out[0]["origin"] == "model" and out[0]["evidence"] == []
    assert out[0]["matched"] == [next(c["claim_id"] for c in KEPT if c["subject"] == "mai anh đào")]


def test_a_model_claim_against_kept_evidence_is_contradicted():
    out = check_model([model("Mai anh đào nở tháng 10", months=[10])], KEPT, city_name="Đà Lạt")
    assert out[0]["status"] == "contradicted" and out[0]["matched"]
    price = model("Thuê xe máy phổ thông thường khoảng 300.000–400.000 đồng/ngày", subject="Đà Lạt",
                  subject_kind="city", kind="price_norm")
    assert check_model([price], KEPT, city_name="Đà Lạt")[0]["status"] == "contradicted"
    price["text"] = "Thuê xe máy phổ thông thường khoảng 100.000–200.000 đồng/ngày"
    assert check_model([price], KEPT, city_name="Đà Lạt")[0]["status"] == "confirmed"


def test_no_kept_evidence_leaves_a_model_claim_unverified():
    dish = model("Bánh căn là món sáng quen thuộc", subject="Bánh căn Đà Lạt", subject_kind="dish", kind="specialty")
    assert check_model([dish], KEPT, city_name="Đà Lạt")[0]["status"] == "unverified"  # only one source said it
    other = model("Dã quỳ nở tháng 10", subject="Dã quỳ", months=[10])
    out = check_model([other], KEPT, city_name="Đà Lạt")[0]
    assert out["status"] == "unverified" and out["matched"] == []


def test_a_one_word_subject_is_not_the_same_as_a_longer_name_containing_it():
    # "hồng" (persimmon) is not "đồi cỏ hồng" (pink grass hills): a lone shared word is no subject match
    out = group_claims([row("a.vn", "đồi cỏ hồng nở rộ", subject="đồi cỏ hồng", months=[11, 12]),
                        row("b.vn", "mùa hồng chín đỏ", subject="hồng", months=[11])], now=NOW, city_name="Đà Lạt")
    assert {c["status"] for c in out} == {"unverified"} and len(out) == 2


def test_neighbouring_bloom_months_from_two_sites_are_one_claim_not_a_conflict():
    out = group_claims([row("a.vn", "mai anh đào bắt đầu nở sớm", months=[12]),
                        row("b.vn", "hoa mai anh đào chớm nở", subject="hoa mai anh đào", months=[1]),
                        row("c.vn", "chiêm ngưỡng hoa mai anh đào", subject="hoa Mai Anh Đào", months=[3])],
                       now=NOW, city_name="Đà Lạt")
    by = {tuple(c["when"]["months"]): c["status"] for c in out}
    assert by == {(1, 12): "kept", (3,): "unverified"}  # 3 is two months off: neither the same claim nor a conflict


def test_one_page_never_conflicts_with_itself_and_item_prices_are_no_conflict():
    out = group_claims([row("a.vn", "homestay theo đêm", subject="Đà Lạt", subject_kind="city", kind="price_norm",
                            lo=150000, hi=400000),
                        row("a.vn", "homestay theo đêm cao cấp loại", subject="Đà Lạt", subject_kind="city", kind="price_norm",
                            lo=1000000, hi=1500000, doc="a2"),
                        row("b.vn", "hộp nhạc gỗ size nhỏ", subject="hộp nhạc gỗ size nhỏ", subject_kind="dish",
                            kind="specialty", lo=355000, hi=355000),
                        row("c.vn", "hộp nhạc gỗ loại lớn bán chạy", subject="hộp nhạc gỗ size lớn", subject_kind="dish",
                            kind="specialty", lo=755000, hi=755000)], now=NOW, city_name="Đà Lạt")
    assert "conflict" not in {c["status"] for c in out}


def test_a_shared_generic_word_is_not_the_same_flower():
    out = group_claims([row("a.vn", "nở rộ cuối năm", subject="hoa hướng dương", months=[10, 11, 12]),
                        row("b.vn", "nở rộ giữa năm", subject="hoa oải hương", months=[6, 7])], now=NOW,
                       city_name="Đà Lạt")
    assert {c["status"] for c in out} == {"unverified"}


def test_the_city_name_is_dropped_as_a_phrase_not_word_by_word():
    # "Đà Lạt" folds to "da lat"; dropping "da" alone would turn "Dã quỳ" into "quỳ"
    kept = group_claims([row("a.vn", "hoa dã quỳ nở", subject="hoa dã quỳ", months=[10, 11]),
                         row("b.vn", "dã quỳ nở vàng", subject="dã quỳ", months=[10, 11])], now=NOW, city_name="Đà Lạt")
    out = check_model([model("Dã quỳ nở tháng 10 đến tháng 11", subject="Dã quỳ Đà Lạt", months=[10, 11])], kept,
                      city_name="Đà Lạt")
    assert out[0]["status"] == "confirmed"
