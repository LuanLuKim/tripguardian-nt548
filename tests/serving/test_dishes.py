from corpus.serving import dishes


def rec(rid, name, dishes_=(), order=()):
    return {"id": rid, "identity": {"name": name}, "menu": {"dishes": list(dishes_), "photos": []} if dishes_ else None,
            "review_dishes": [{"dish": t, "n": n, "quote": f"gọi {t}"} for t, n in order],
            "details": {"order": [{"text": "raw unchecked dish", "n": 9}]}}


def test_fold_ignores_case_accents_and_d_bar():
    assert dishes.fold("Bánh Bèo  Chén") == "banh beo chen"
    assert dishes.fold("Sữa đậu nành") == "sua dau nanh"


def test_phrase_is_whole_words():
    assert dishes.has_phrase("banh canh gio heo", "banh canh")
    assert not dishes.has_phrase("banh canhh", "banh canh")
    assert not dishes.has_phrase("canh chua", "banh canh")


def test_search_ranks_popular_menu_over_menu_over_review_order():
    rs = [rec("c", "C", order=[("bánh canh cua", 5)]),
          rec("b", "B", [{"name": "Bánh canh giò heo", "popular": False}]),
          rec("a", "A", [{"name": "Bánh canh cá lóc", "popular": True}]),
          rec("d", "D", [{"name": "Canh chua", "popular": True}])]
    assert [h["id"] for h in dishes.search(rs, "bánh canh")] == ["a", "b", "c"]


def test_alias_and_english_name():
    rs = [rec("a", "A", [{"name": "Sữa nành nóng"}]), rec("b", "B", [{"name": "Soy milk", "name_en": "Sữa đậu nành"}])]
    assert {h["id"] for h in dishes.search(rs, "sữa đậu nành")} == {"a", "b"}


def test_unknown_dish_is_empty_not_none_serving():
    assert dishes.search([rec("a", "A", [{"name": "Phở bò"}])], "bánh bèo") == []
    assert dishes.search([], "") == []


def test_menu_of_dedupes_and_needs_content():
    doc = {"has_menu_tab": True, "highlights": [{"name": "Bánh bèo", "popular": True}],
           "sections": [{"name": "Món chính", "items": [{"name": "Bánh Bèo"}, {"name": "Phở", "price": "50.000 ₫"}]}], "photos": []}
    m = dishes.menu_of(doc)
    assert [d["name"] for d in m["dishes"]] == ["Bánh bèo", "Phở"] and m["dishes"][1]["price"] == "50.000 ₫"
    assert dishes.menu_of({"has_menu_tab": False}) is None
    assert dishes.menu_of({"has_menu_tab": True, "highlights": [], "sections": [], "photos": []}) is None


def test_accented_query_does_not_fold_pho_into_pho_mai():
    rs = [rec("a", "A", [{"name": "Phô mai sợi"}]), rec("b", "B", [{"name": "Phở bò"}])]
    assert [h["id"] for h in dishes.search(rs, "phở")] == ["b"]
    assert {h["id"] for h in dishes.search(rs, "pho")} == {"a", "b"}  # typed without accents: both are possible


def eatery(rid, name, group="restaurant", dishes_=()):
    r = rec(rid, name, dishes_)
    r["identity"]["category_group"] = group
    return r


def test_place_named_after_a_dish_is_evidence_even_without_a_menu():
    rs = [eatery("a", "Bánh bèo Bà Hường"), eatery("b", "Bánh bèo Hotel", group="stay"), eatery("c", "Quán Xưa")]
    hits = dishes.search(rs, "banh beo")
    assert [h["id"] for h in hits] == ["a"]
    assert hits[0]["evidence"] == [{"source": "name", "dish": "Bánh bèo Bà Hường"}]


def test_source_rank_popular_menu_then_name_then_menu_then_review():
    r = dishes.SOURCE_RANK
    assert r["menu_popular"] > r["name"] > r["menu"] > r["review_order"]


def test_name_is_whole_words_and_a_record_without_group_gets_none():
    rs = [eatery("a", "Bánh bèo"), eatery("b", "Bánh bèo", group=None), eatery("c", "Bánh bèoo")]
    assert [h["id"] for h in dishes.search(rs, "bánh bèo")] == ["a"]


def test_config_synonyms_cross_languages():
    rs = [eatery("a", "A", dishes_=[{"name": "Cà phê trứng"}]), eatery("b", "B", dishes_=[{"name": "Egg Coffee"}]),
          eatery("c", "C", dishes_=[{"name": "Cà phê đen"}])]
    assert {h["id"] for h in dishes.search(rs, "egg coffee")} == {"a", "b"}
    assert {h["id"] for h in dishes.search(rs, "cafe trứng")} == {"a", "b"}


def test_index_is_reused_and_rebuilt_when_the_menu_changes():
    rs = [eatery("a", "A", dishes_=[{"name": "Bánh bèo"}]), eatery("b", "B")]
    first = dishes.index(rs)
    assert dishes.index(rs) is first
    rs[1]["menu"] = {"dishes": [{"name": "Bánh bèo chén"}], "photos": []}
    assert {h["id"] for h in dishes.search(rs, "bánh bèo")} == {"a", "b"}


def test_search_over_a_big_list_is_fast():
    import time
    rs = [eatery(str(i), f"Quán {i}", dishes_=[{"name": f"Món {i}"}] + ([{"name": "Bún bò"}] if i % 20 == 0 else [])) for i in range(4000)]
    dishes.search(rs, "bún bò")  # builds the index
    t = time.perf_counter()
    for _ in range(20):
        dishes.search(rs, "bún bò", limit=5)
    assert (time.perf_counter() - t) / 20 < 0.05


def test_report_counts_hits_and_names_the_reason_for_none():
    rs = [eatery("a", "A", dishes_=[{"name": "Bánh bèo"}]), eatery("b", "B"), eatery("c", "C", group="stay")]
    rows = {r["query"]: r for r in dishes.report(rs, ["bánh bèo", "bê thui"])}
    assert rows["bánh bèo"]["places"] == 1 and rows["bánh bèo"]["sources"] == {"menu": 1}
    assert rows["bê thui"]["places"] == 0
    assert rows["bê thui"]["eateries_unknown"] == 1  # B is an eatery with no dish list: unknown, not "does not serve"


import json
import pytest


@pytest.fixture
def cfg(monkeypatch):
    def set_(**sources):
        monkeypatch.setattr(dishes, "config", lambda: {"sources": {k: {"enabled": v} for k, v in sources.items()},
                                                       "name_groups": []})
    return set_


def photo_place(tmp_path, dishes_, tab=True):
    d = tmp_path / "gmaps" / "places" / "p1"
    d.mkdir(parents=True)
    (d / "menu.json").write_text(json.dumps({"has_menu_tab": tab, "photos": [{"file": "a.jpg"}], "sections": [],
                                             "highlights": []}), encoding="utf-8")
    (d / "menu_photo.json").write_text(json.dumps({"dishes": dishes_}), encoding="utf-8")
    return [{"id": "p1", "identity": {"name": "P"}}]


def test_menu_photo_is_off_until_enabled(tmp_path, cfg):
    cfg(menu_photo=False)
    rs = photo_place(tmp_path, [{"name": "Bánh bèo", "price_vnd": 30000}])
    dishes.attach(rs, tmp_path)
    assert dishes.search(rs, "bánh bèo") == []


def test_menu_photo_dishes_are_a_source_when_enabled(tmp_path, cfg):
    cfg(menu_photo=True)
    rs = photo_place(tmp_path, [{"name": "Bánh bèo", "price_vnd": 30000}])
    assert dishes.attach(rs, tmp_path) == 1
    hit = dishes.search(rs, "banh beo")[0]
    assert [e["source"] for e in hit["evidence"]] == ["menu_photo"]
    assert rs[0]["menu"]["dishes"][0]["price"] == 30000


def test_menu_photo_does_not_duplicate_a_dish_the_owner_listed(tmp_path, cfg):
    cfg(menu_photo=True)
    rs = photo_place(tmp_path, [{"name": "Bánh Bèo", "price_vnd": 0}])
    f = tmp_path / "gmaps" / "places" / "p1" / "menu.json"
    f.write_text(json.dumps({"has_menu_tab": True, "photos": [], "highlights": [],
                             "sections": [{"name": "Món", "items": [{"name": "Bánh bèo", "price": 25000}]}]}), encoding="utf-8")
    dishes.attach(rs, tmp_path)
    assert [d["name"] for d in rs[0]["menu"]["dishes"]] == ["Bánh bèo"]
    assert [e["source"] for e in dishes.search(rs, "bánh bèo")[0]["evidence"]] == ["menu"]


def test_menu_price_evidence_needs_enough_agreed_prices(tmp_path, cfg):
    cfg(menu_photo=True)
    rs = photo_place(tmp_path, [{"name": f"Món {i}", "price_vnd": p} for i, p in enumerate([20000, 30000, 40000, 50000])])
    dishes.attach(rs, tmp_path)
    ev = rs[0]["menu"]["price_evidence"]
    assert ev["source"] == "menu_photo" and ev["n"] == 4 and ev["min_vnd"] == 30000 and ev["max_vnd"] == 40000
    few = photo_place(tmp_path / "x", [{"name": "A đây", "price_vnd": 20000}])
    dishes.attach(few, tmp_path / "x")
    assert "price_evidence" not in (few[0]["menu"] or {})


def test_review_order_needs_a_verified_quote(tmp_path, cfg):
    cfg(review_order=True)
    d = tmp_path / "gmaps" / "places" / "p1"
    d.mkdir(parents=True)
    (d / "dish_review.json").write_text(json.dumps({"dishes": [
        {"dish": "bò né", "quote": "mình gọi bò né ăn rất ngon", "judge": "serves"},
        {"dish": "pizza", "quote": "bạn mình thích pizza", "judge": "unsure"}]}), encoding="utf-8")
    rs = [{"id": "p1", "identity": {"name": "P"}}]
    dishes.attach(rs, tmp_path)
    assert [x["dish"] for x in rs[0]["review_dishes"]] == ["bò né"]
    assert dishes.search(rs, "bò né")[0]["evidence"][0]["quote"].startswith("mình gọi")
    cfg(review_order=False)
    rs2 = [{"id": "p1", "identity": {"name": "P"}}]
    dishes.attach(rs2, tmp_path)
    assert not rs2[0].get("review_dishes")


def test_raw_details_order_is_never_dish_evidence():
    r = {"id": "a", "identity": {"name": "A"}, "details": {"order": [{"text": "phở bò", "n": 5}]}}
    assert dishes.search([r], "phở bò") == []


def test_review_order_drops_generic_words_and_wishes(tmp_path, monkeypatch):
    monkeypatch.setattr(dishes, "config", lambda: {"sources": {"review_order": {"enabled": True}}, "name_groups": [],
                                                   "generic": ["đồ uống", "bữa sáng"], "wish_prefix": ["muốn ăn"]})
    d = tmp_path / "gmaps" / "places" / "p1"
    d.mkdir(parents=True)
    (d / "dish_review.json").write_text(json.dumps({"dishes": [
        {"dish": "Đồ uống", "quote": "đồ uống ngon", "judge": "serves"},
        {"dish": "Muốn ăn gà nướng", "quote": "Muốn ăn gà nướng", "judge": "serves"},
        {"dish": "gà nướng", "quote": "gà nướng ngon", "judge": "serves"}]}), encoding="utf-8")
    rs = [{"id": "p1", "identity": {"name": "P"}}]
    dishes.attach(rs, tmp_path)
    assert [x["dish"] for x in rs[0]["review_dishes"]] == ["gà nướng"]
