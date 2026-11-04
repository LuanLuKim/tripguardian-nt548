from corpus.crawl.gsearch import places


def test_query_texts_by_kind_and_city_name_not_repeated():
    assert places.query_for("panel", "Thác Datanla", "Đà Lạt") == "Thác Datanla Đà Lạt"
    assert places.query_for("panel", "Chùa Linh Phước Đà Lạt", "Đà Lạt") == "Chùa Linh Phước Đà Lạt"
    assert places.query_for("fee", "Thác Datanla", "Đà Lạt") == "giá vé Thác Datanla Đà Lạt 2026"
    assert places.query_for("hours", "Thác Datanla", "Đà Lạt") == "Thác Datanla Đà Lạt giờ mở cửa"


def test_who_is_asked_what():
    sight = {"fid": "a", "name": "A", "group": "attraction", "website": None, "hours": True}
    bare_sight = {**sight, "hours": False}
    cafe_no_hours = {**sight, "group": "cafe", "hours": False}
    cafe = {**sight, "group": "cafe", "hours": True}
    stay = {**sight, "group": "stay", "hours": False}
    assert places.wanted("panel", sight) and places.wanted("fee", sight) and not places.wanted("hours", sight)
    assert places.wanted("hours", bare_sight)
    assert places.wanted("panel", cafe_no_hours) and places.wanted("hours", cafe_no_hours)
    assert not places.wanted("fee", cafe_no_hours)  # a cafe sells no entry
    assert not places.wanted("panel", cafe)  # hours known, no entry ticket: nothing left to ask
    assert not places.wanted("panel", stay) and not places.wanted("hours", stay)
