"""Short, clean place names for cards (planning.placename): foreign-script, brand-tail and city parts go."""

import pytest

from planning.placename import short_name


@pytest.mark.parametrize("raw,want", [
    ("ĐÔI DÉP Camellia Tea Spa, Massage | Đà Lạt (달랏 마사지 스파)", "ĐÔI DÉP Camellia Tea Spa"),
    ("Ngọc Kim An Spa & Health - Massage Da Lat - 달랏 마사지", "Ngọc Kim An Spa & Health"),
    ("Moon Spa Dalat (문스파 달랏)", "Moon Spa Dalat"),
    ("GÀ RÁN HÀN QUỐC CHAN'S CHICKEN 찬스 치킨", "GÀ RÁN HÀN QUỐC CHAN'S CHICKEN"),
    ("Mộc Hương spa - Dưỡng sinh & chăm sóc sức khỏe", "Mộc Hương spa"),
    ("Mứt Số 10 – Hồng Treo Gió Đà Lạt | Đặc Sản Đà Lạt", "Mứt Số 10"),
    ("La Tulipe Rouge | Travel Hiphop Bar", "La Tulipe Rouge"),
    ("Cuk จุก - Thailand Food Tour In Da Lat", "Cuk – Thailand Food Tour In Da Lat"),
    ("MASSAGE -TRỊ LIỆU- NHẤN HUYỆT -GIÁC HƠI-Giá rẻ Tại nhà 마사지 받고 싶을 때 전화해", "MASSAGE – TRỊ LIỆU – NHẤN HUYỆT"),
    ("Bánh tráng nướng Cô Chi - Đà Lạt", "Bánh tráng nướng Cô Chi"),
])
def test_noisy_maps_names_become_short_names(raw, want):
    assert short_name(raw) == want


@pytest.mark.parametrize("raw", ["Hồ Xuân Hương", "Đà Lạt Milk Farm", "Cà phê A-B", "Quán Gỗ", "Đà Lạt"])
def test_a_clean_name_is_left_alone(raw):
    assert short_name(raw) == raw


def test_nothing_usable_falls_back_to_the_original_or_empty():
    assert short_name("달랏 마사지") == "달랏 마사지"      # all foreign script: nothing to keep, show what the corpus has
    assert short_name("") == "" and short_name(None) == ""


def test_a_long_name_with_no_separator_is_cut_at_a_word():
    out = short_name("Nhà hàng Buffet Hải Sản Nướng Lẩu Đặc Biệt Phố Núi Cao Nguyên Xanh")
    assert len(out) <= 40 and out.startswith("Nhà hàng Buffet") and not out.endswith(" ")
