"""Place names in Place Intelligence: tidy for the user, raw kept (corpus.aggregate.naming). Same table as web/src/data/placeName.test.mjs."""
import pytest

from corpus.aggregate.naming import MAX, display_name, distinct_names

CASES = [
    ("dồi Cù", "Dồi Cù"),
    ("ĐÀ LẠT THIÊN VƯƠNG", "Đà Lạt Thiên Vương"),
    ("ENJOY_VILLA", "Enjoy Villa"),
    ("homy hostel", "Homy Hostel"),
    ("Cá tầm Đà Lạt QUÁN ÁNH DƯƠNG CS2 .lẩu nướng cá tầm.Gà đồi cơm lam", "Cá tầm Đà Lạt Quán Ánh Dương CS2"),
    ("Mộc Hương spa - Dưỡng sinh & chăm sóc sức khỏe", "Mộc Hương spa"),
    ("CÁ TẦM CÂY ĐÀO QUÁN : Lẩu_Nướng. Gà Đồi_ Cơm Lam - quán cá tầm", "Cá Tầm Cây Đào Quán"),
    ("Windy Valley 1- Homestay Đà Lạt", "Windy Valley 1"),
    ("Massage Đà Lạt & Gội Đầu Dưỡng Sinh - MEM SPA (샴푸와 컨디셔너, 마사지)", "Mem Spa"),
    ("실내 스크린 골프 & 연습장 / 달랏(Đà Lạt) sân tập golf trong nhà / LUIS GOLF CLUB", "Luis Golf Club"),
    ("MASSAGE TRỊ LIỆU ĐÀ LẠT - LALITA SPA", "Lalita Spa"),
    ("Món Thái - Khap Bun Kha", "Khap Bun Kha"),
    ("Quán Xưa - Lẩu Bò Atiso", "Quán Xưa"),
    ("Lẩu gà lá é Hạnh - Chi nhánh 2", "Lẩu gà lá é Hạnh Chi nhánh 2"),
    ("Bánh căn Lệ - CS2", "Bánh căn Lệ CS2"),
    ("NVN ĐÀ LẠT", "NVN Đà Lạt"),
    ("LẨU BBQ HÀN QUỐC", "Lẩu BBQ Hàn Quốc"),
    ('NHÀ CỦA GẤU "BEAR\'S HOUSE"', 'Nhà của Gấu "Bear\'s House"'),
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


def test_branches_keep_apart():
    got = distinct_names({"a": "Nature Hotel - Phan Bội Châu", "b": "Nature Hotel - Lê Đại Hành", "c": "Cafe ZooDoo",
                          "d": "Quán cơm Linh Đà Lạt", "e": "Quán cơm Linh Đà Lạt - Trần Hưng Đạo"})
    assert got == {"a": "Nature Hotel Phan Bội Châu", "b": "Nature Hotel Lê Đại Hành", "c": "Cafe ZooDoo",
                   "d": "Quán cơm Linh Đà Lạt", "e": "Quán cơm Linh Đà Lạt Trần Hưng Đạo"}
    assert all(display_name(v) == v for v in got.values())  # the web applies display_name again


def test_same_google_name_is_left_alone():
    assert distinct_names({"a": "Hum Homestay Da Lat", "b": "Hum Homestay Da Lat"}) == {"a": "Hum Homestay Da Lat",
                                                                                        "b": "Hum Homestay Da Lat"}


def test_search_finds_the_google_name_too():
    from corpus.retrieval import NameRecord, search_names
    recs = [NameRecord("a", "Lalita Spa", "spa", "MASSAGE TRỊ LIỆU ĐÀ LẠT - LALITA SPA"), NameRecord("b", "Cafe ZooDoo", "cafe")]
    assert [h.place_id for h in search_names("massage trị liệu lalita", recs, within={"a", "b"}, release_id=None)] == ["a"]
    assert search_names("lalita spa", recs, within={"a", "b"}, release_id=None)[0].name == "Lalita Spa"
