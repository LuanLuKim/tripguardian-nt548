from corpus.aggregate.estimates import amounts_vnd, entry_fee, estimates, group, visit_minutes


def _fee(i, quote, author):
    return {"id": f"x:{i}", "feature": "entry_fee", "value": "paid", "author": author, "span": {"quote": quote}}


def test_amounts_in_review_words():
    assert amounts_vnd("Vé vào cổng 50k/người/lượt") == [50000]
    assert amounts_vnd("thu phí vào cửa là 160.000 đồng/người") == [160000]
    assert amounts_vnd("Vé người lớn: 65k Vé trẻ em: 45k") == [65000, 45000]
    assert amounts_vnd("Mua vé 150.000đ/2 người") == [150000]
    assert amounts_vnd("vé 99k và 150k") == [99000, 150000]
    assert amounts_vnd("Mua vé trước, đi 2 người, 3 tiếng") == []
    assert amounts_vnd("Phí vào cửa là 120.000 dinar/người") == []


def test_entry_fee_from_quotes_one_value_per_author_then_maps_tickets():
    fee = entry_fee([_fee(1, "vé 50k", "a"), _fee(2, "Vé người lớn: 65k Vé trẻ em: 45k", "b"), _fee(3, "vé 100k", "c"),
                     _fee(4, "Mua vé trước", "d")])
    assert fee == {"min_vnd": 50000, "typical_vnd": 65000, "max_vnd": 100000, "n": 3, "source": "reviews"}
    assert entry_fee([_fee(1, "Mua vé trước", "a")], 5.78) is None  # the Maps box failed its precision gate: off by default
    assert entry_fee([], None) is None


def test_entry_fee_maps_tickets_when_the_gate_is_switched_on(monkeypatch):
    from corpus.aggregate import estimates as est
    real = est.defaults()
    monkeypatch.setattr(est, "defaults", lambda: {**real, "maps_tickets_entry_fee": True})
    assert entry_fee([_fee(1, "Mua vé trước", "a")], 5.78)["source"] == "maps_tickets"


def test_category_groups():
    assert group("Quán cà phê")["id"] == "cafe"
    assert group("Điểm thu hút khách du lịch")["id"] == "attraction"
    assert group("Spa sức khỏe")["id"] == "spa"
    assert group("Cửa hàng thời trang")["id"] == "shop"  # not "thờ" of a temple
    assert group(None)["id"] == "other"


def test_visit_minutes_reviews_win_only_with_enough_agreeing_authors():
    assert visit_minutes("Quán cà phê", None)["source"] == "category_default"
    weak = {"n": 2, "status": "signal", "top_value": "half_day"}
    assert visit_minutes("Quán cà phê", weak)["source"] == "category_default"
    got = visit_minutes("Quán cà phê", {**weak, "n": 3})
    assert (got["short"], got["long"], got["source"]) == (180, 300, "reviews")
    assert estimates("Nhà hàng", {}, [])["usable_as_default"] == ["meal", "anchor", "backup"]


def test_ticket_amounts_only_next_to_a_ticket_word():
    from corpus.aggregate.estimates import ticket_amounts
    assert ticket_amounts("giá 700 nghìn đồng/người") == []  # a service price, no ticket word
    assert ticket_amounts("chụp hình 500k/nhóm") == []
    assert ticket_amounts("dâu 400k/kg, vé vào cổng 50k") == [50000]
    assert ticket_amounts("Giá vé là 160.000 đồng, trẻ em 80.000") == [160000]


def test_entry_fee_prefers_recent_quotes():
    from corpus.aggregate.estimates import entry_fee

    def ob(i, quote, day):
        return {"id": f"x{i}", "feature": "entry_fee", "value": "paid", "author": f"a{i}", "observed_at": day,
                "span": {"quote": quote}}
    obs = [ob(1, "vé 20k", "2019-05-01"), ob(2, "vé 50k", "2026-05-01"), ob(3, "giá vé 60k", "2026-08-01")]
    fee = entry_fee(obs)
    assert (fee["min_vnd"], fee["max_vnd"], fee["n"]) == (50000, 60000, 2)


def test_maps_time_spent_wins_over_reviews_and_defaults():
    from corpus.aggregate.estimates import visit_minutes
    signal = {"n": 5, "status": "signal", "top_value": "half_day"}
    v = visit_minutes("Thác", signal, {"min_minutes": 60, "max_minutes": 150})
    assert v == {"short": 60, "typical": 105, "long": 150, "source": "maps_time_spent", "n": 0}
    assert visit_minutes("Thác", signal)["source"] == "reviews"


def test_category_groups_match_whole_words_longest_phrase_first():
    assert group("Quán bia sân vườn")["id"] == "bar"  # "quán bia", not the garden's "vườn"
    assert group("Câu lạc bộ chèo thuyền")["id"] != "dessert"  # "chèo" holds no "chè"
    assert group("Hồ bơi ngoài trời")["id"] == "amusement"  # "hồ bơi", not the lake's "hồ"
    assert group("Cửa hàng kem")["id"] == "dessert" and group("Quán ăn nhẹ")["id"] == "dessert"


def test_a_category_no_phrase_matches_is_read_from_the_name():
    assert group("Dịch vụ ô tô riêng", "Vườn Hồng Treo Dốc Tình")["id"] == "garden_farm"
    assert group("Quán cà phê", "Spa Hoa")["id"] == "cafe"  # a matched category wins over the name
    assert group("Studio nhiếp ảnh", "Đường Ray")["id"] == "other"


def _stay(i, author, minutes, quote="đi hết 2 tiếng"):
    return {"id": f"v:{i}", "feature": "visit_duration", "value": "1_to_2h", "author": author, "source_type": "gmaps_review",
            "span": {"quote": quote}, "detail": {"minutes": list(minutes)}}


def test_visit_minutes_from_durations_one_stay_per_author():
    obs = [_stay(1, "a", (120, 120)), _stay(2, "a", (60, 60)), _stay(3, "b", (90, 90)), _stay(4, "c", (120, 120))]
    got = visit_minutes("Điểm tham quan", None, None, None, obs)
    assert (got["source"], got["basis"], got["n"]) == ("reviews", "durations", 3)  # author a counted once
    assert got["short"] <= got["typical"] <= got["long"] and got["typical"] == 90
    assert 1 <= len(got["quotes"]) <= 3
    assert visit_minutes("Điểm tham quan", None, {"min_minutes": 30, "max_minutes": 60}, None, obs)["source"] == "maps_time_spent"


def test_visit_minutes_ignores_observations_without_minutes_or_from_other_sources():
    bucket_only = {"id": "x", "feature": "visit_duration", "value": "half_day", "author": "a", "source_type": "gmaps_review",
                   "span": {"quote": "nửa ngày"}}
    video = {**_stay(1, "b", (90, 90)), "source_type": "tiktok_segment"}
    wild = _stay(2, "c", (5, 5))
    assert visit_minutes("Điểm tham quan", None, None, None, [bucket_only, video, wild])["source"] == "category_default"


def test_words_alone_need_as_many_authors_as_the_bucket_signal():
    day = [_stay(i, f"a{i}", (360, 600), "đi cả ngày") for i in range(1, 3)]
    assert visit_minutes("Điểm tham quan", None, None, None, day)["source"] == "category_default"
    got = visit_minutes("Điểm tham quan", None, None, None, day + [_stay(3, "a3", (360, 600), "đi cả ngày")])
    assert (got["source"], got["n"]) == ("reviews", 3)
    mixed = visit_minutes("Điểm tham quan", None, None, None, [_stay(1, "x", (120, 120)), *day[:1]])
    assert mixed["n"] == 1 and mixed["typical"] == 120  # one written number is enough; the lone word is left out
