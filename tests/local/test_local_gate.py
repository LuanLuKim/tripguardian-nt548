"""Gate of a LocalClaim (docs/CORPUS.md, Tri thức bản địa): every part of a claim must be in its quote, the quote in
the section. A claim that fails is dropped with a reason, never kept with a guess."""

import pytest

from corpus.local import gate_claim, months_in

SECTION = ("Mùa hoa\n\nTừ **tháng 12 đến tháng 2**, mai anh đào nở rộ khắp các con dốc. Thuê xe máy khoảng "
           "100.000 – 150.000đ/ngày. Cuối tuần chợ đêm đông từ 18h đến 22h, trời mưa thì nên vào quán.")


def item(**kw):
    base = {"subject_kind": "phenomenon", "subject_text": "mai anh đào", "kind": "season", "text": "mai anh đào nở rộ",
            "amount_min_vnd": 0, "amount_max_vnd": 0, "months": [12, 1, 2], "days": [], "hours": "", "weather": "",
            "who": "",
            "quote": "tháng 12 đến tháng 2, mai anh đào nở rộ khắp các con dốc"}
    base.update(kw)
    return base


def test_a_claim_whose_parts_are_all_in_the_quote_stands():
    claim, why = gate_claim(item(), SECTION)
    assert why is None
    assert claim["subject"] == "mai anh đào" and claim["subject_id"] is None
    assert claim["when"]["months"] == [1, 2, 12]
    assert claim["amount_min_vnd"] is None and claim["amount_max_vnd"] is None


@pytest.mark.parametrize("kw, reason", [
    ({"quote": "tháng 3 mai anh đào nở"}, "quote_not_in_source"),
    ({"quote": ""}, "quote_not_in_source"),
    ({"text": "hoa nở quanh năm"}, "text_not_in_quote"),
    ({"subject_text": " "}, "no_subject"),
    ({"kind": "rumour"}, "bad_kind"),
    ({"subject_kind": "poi_unresolved"}, "bad_kind"),
    ({"months": [12, 1, 2, 3], "days": [], "hours": "", "weather": ""}, "month_not_in_quote"),
    ({"months": [13], "days": [], "hours": "", "weather": ""}, "month_not_in_quote"),
    ({"months": [12], "days": ["weekend"], "hours": "", "weather": ""}, "day_not_in_quote"),
    ({"months": [12], "days": [], "hours": "05:00-07:00", "weather": ""}, "hour_not_in_quote"),
    ({"months": [12], "days": [], "hours": "sáng sớm", "weather": ""}, "bad_hours"),
    ({"months": [12], "days": [], "hours": "", "weather": "foggy"}, "weather_not_in_quote"),
    ({"amount_min_vnd": 50000, "amount_max_vnd": 50000}, "amount_not_in_quote"),
])
def test_a_claim_is_dropped_with_the_reason(kw, reason):
    assert gate_claim(item(**kw), SECTION) == (None, reason)


def test_price_range_days_hours_and_weather_must_be_in_the_quote():
    price = item(subject_kind="city", subject_text="Đà Lạt", kind="price_norm", text="Thuê xe máy",
                 amount_min_vnd=100000, amount_max_vnd=150000,
                 **{"months": [], "days": [], "hours": "", "weather": ""},
                 quote="Thuê xe máy khoảng 100.000 – 150.000đ/ngày")
    claim, why = gate_claim(price, SECTION)
    assert why is None and (claim["amount_min_vnd"], claim["amount_max_vnd"]) == (100000, 150000)
    night = item(subject_kind="area", subject_text="chợ đêm", kind="crowded_at", text="chợ đêm đông",
                 **{"months": [], "days": ["weekend"], "hours": "18:00-22:00", "weather": ""},
                 quote="Cuối tuần chợ đêm đông từ 18h đến 22h")
    claim, why = gate_claim(night, SECTION)
    assert why is None and claim["when"]["hours"] == "18:00-22:00"
    rain = item(subject_kind="city", subject_text="Đà Lạt", kind="if_rain", text="nên vào quán",
                **{"months": [], "days": [], "hours": "", "weather": "rainy"}, quote="trời mưa thì nên vào quán")
    assert gate_claim(rain, SECTION)[1] is None


def test_one_amount_fills_both_ends_and_a_swapped_range_is_ordered():
    one = item(kind="price_norm", text="Thuê xe máy", amount_min_vnd=0, amount_max_vnd=100000,
               **{"months": [], "days": [], "hours": "", "weather": ""}, quote="Thuê xe máy khoảng 100.000")
    claim, _ = gate_claim(one, SECTION)
    assert (claim["amount_min_vnd"], claim["amount_max_vnd"]) == (100000, 100000)
    swapped = {**one, "amount_min_vnd": 150000, "amount_max_vnd": 100000,
               "quote": "Thuê xe máy khoảng 100.000 – 150.000đ/ngày"}
    claim, _ = gate_claim(swapped, SECTION)
    assert (claim["amount_min_vnd"], claim["amount_max_vnd"]) == (100000, 150000)


def test_a_poi_resolves_by_name_or_stays_unresolved():
    poi = item(subject_kind="poi", subject_text="Hồ Tuyền Lâm", kind="tip", text="mai anh đào nở rộ",
               **{"months": [], "days": [], "hours": "", "weather": ""})
    claim, _ = gate_claim(poi, SECTION, resolve=lambda name: "fid:1" if "Tuyền Lâm" in name else None)
    assert (claim["subject_kind"], claim["subject_id"]) == ("poi", "fid:1")
    claim, _ = gate_claim(poi, SECTION, resolve=lambda name: None)
    assert (claim["subject_kind"], claim["subject_id"]) == ("poi_unresolved", None)
    claim, _ = gate_claim(poi, SECTION)  # no resolver: unknown, never a guessed id
    assert (claim["subject_kind"], claim["subject_id"]) == ("poi_unresolved", None)


def test_months_in_reads_singles_ranges_lists_and_wraps_the_year():
    assert months_in("tháng 12 đến tháng 2") == {12, 1, 2}
    assert months_in("từ tháng 5 - 10") == {5, 6, 7, 8, 9, 10}
    assert months_in("tháng 1, 2 và 3") == {1, 2, 3}
    assert months_in("Tháng 11") == {11}
    assert months_in("năm 2026 có 30 ngày") == set()


def test_a_venue_opening_hours_line_is_not_local_knowledge():
    section = "Gâu Garden\nĐịa chỉ: 12 Hùng Vương. Giờ mở cửa: 8h – 22h. Quán có nuôi cún."
    hours = item(subject_kind="poi", subject_text="Gâu Garden", kind="tip", text="Giờ mở cửa: 8h – 22h", months=[],
                 quote="Giờ mở cửa: 8h – 22h")
    assert gate_claim(hours, section) == (None, "venue_hours")
