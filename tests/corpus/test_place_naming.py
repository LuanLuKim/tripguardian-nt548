"""Place names in Place Intelligence: tidy for the user, raw kept (corpus.aggregate.naming). Same table as web/src/data/placeName.test.mjs."""
import pytest

from corpus.aggregate.naming import MAX, display_name

CASES = [
    ("dồi Cù", "Dồi Cù"),
    ("ĐÀ LẠT THIÊN VƯƠNG", "Đà Lạt Thiên Vương"),
    ("ENJOY_VILLA", "Enjoy Villa"),
    ("homy hostel", "Homy Hostel"),
    ("Cá tầm Đà Lạt QUÁN ÁNH DƯƠNG CS2 .lẩu nướng cá tầm.Gà đồi cơm lam", "Cá tầm Đà Lạt Quán Ánh Dương CS2"),
    ("Mộc Hương spa - Dưỡng sinh & chăm sóc sức khỏe", "Mộc Hương spa"),
    ("CÁ TẦM CÂY ĐÀO QUÁN : Lẩu_Nướng. Gà Đồi_ Cơm Lam - quán cá tầm", "Cá Tầm Cây Đào Quán"),
    ("Windy Valley 1- Homestay Đà Lạt", "Windy Valley 1"),
    ("Massage Đà Lạt & Gội Đầu Dưỡng Sinh - MEM SPA (샴푸와 컨디셔너, 마사지)", "Massage Đà Lạt & Gội Đầu Dưỡng Sinh"),
    ("실내 스크린 골프 & 연습장 / 달랏(Đà Lạt) sân tập golf trong nhà / LUIS GOLF CLUB", "Sân Tập Golf Trong Nhà"),
    ("T.U.K Villa & Hotel", "T.U.K Villa & Hotel"),
    ("KDL Rừng Thông Núi Voi - Elephant Mountain Pine Forest", "KDL Rừng Thông Núi Voi"),
    ("Cafe ZooDoo", "Cafe ZooDoo"),
]


@pytest.mark.parametrize("raw,tidy", CASES)
def test_display_name(raw, tidy):
    assert display_name(raw) == tidy
    assert display_name(tidy) == tidy  # tidy is stable


def test_long_name_stops_at_a_word():
    out = display_name("Một cái tên rất dài của một nơi nào đó ở Đà Lạt không có dấu phân cách nào cả")
    assert len(out) <= MAX + 1 and out.endswith("…")

