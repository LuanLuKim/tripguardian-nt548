from corpus.observe.gmaps import menu_read as m


def items(*pairs):
    return {"is_menu": True, "items": [{"name": n, "price_vnd": p} for n, p in pairs]}


def test_agree_keeps_only_names_both_reads_have():
    a = items(("Bánh Bèo", 30000), ("Phở bò", 50000))
    b = items(("banh beo", 30000), ("Cà phê", 20000))
    assert [x["name"] for x in m.agree(a, b)] == ["Bánh Bèo"]


def test_agree_price_needs_both_reads_equal():
    a = items(("Bánh bèo", 30000), ("Phở bò", 50000))
    b = items(("Bánh bèo", 30000), ("Phở bò", 55000))
    got = {x["name"]: x["price_vnd"] for x in m.agree(a, b)}
    assert got == {"Bánh bèo": 30000, "Phở bò": 0}  # dish agreed, price did not: price unknown


def test_agree_ignores_not_a_menu_and_absurd_prices():
    assert m.agree({"is_menu": False, "items": [{"name": "Phở", "price_vnd": 0}]}, items(("Phở", 0))) == []
    a = items(("Phở", 5))
    assert m.agree(a, a)[0]["price_vnd"] == 0  # 5 dong is a misread


def test_agree_drops_too_short_names():
    a = items(("A", 0), ("Phở", 0))
    assert [x["name"] for x in m.agree(a, a)] == ["Phở"]


def test_merge_photos_dedups_by_fold_and_keeps_price():
    merged = m.merge([[{"name": "Phở", "price_vnd": 0}], [{"name": "pho", "price_vnd": 45000}]])
    assert merged == [{"name": "Phở", "price_vnd": 45000}]
