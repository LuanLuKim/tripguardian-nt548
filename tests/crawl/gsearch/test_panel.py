from pathlib import Path

from corpus.crawl.gsearch import panel

FIX = Path(__file__).parent / "fixtures"


def read(name):
    return panel.parse((FIX / name).read_text(encoding="utf-8"))


def test_no_panel_is_not_present():
    p = panel.parse("<html><body><div id='rso'></div></body></html>")
    assert not p.present and p.hours is None and p.admissions == ()


def test_weekly_hours_in_maps_structure_and_official_line_is_the_only_official_price():
    p = read("panel_valley.html")
    assert p.present and p.title == "Thung lũng Tình Yêu"
    assert p.hours == {d: [["07:30", "17:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    assert "Thứ Sáu 07:30–17:00" in p.hours_text
    official = [a for a in p.admissions if a.official]
    assert [(a.price_vnd, a.url) for a in official] == [(212000, "https://ticketssee.com/thunglungtinhyeu/")]
    assert {a.seller for a in p.admissions if not a.official} >= {"Klook", "Agoda"}  # resellers are kept apart


def test_zoo_official_price_and_resellers():
    p = read("panel_zoo.html")
    assert [a.price_vnd for a in p.admissions if a.official] == [150000]
    assert p.hours is None  # this panel shows no hours block: absent, never closed


def test_free_line_without_a_seller_is_free_but_not_official():
    p = read("panel_free.html")
    assert len(p.admissions) == 1 and p.admissions[0].free and not p.admissions[0].official
    assert p.admissions[0].price_vnd is None


def test_open_all_day_closed_day_and_split_ranges():
    rows = "".join(f"<tr><td>{d}</td><td>{v}</td></tr>" for d, v in [
        ("Thứ Hai", "Mở cửa cả ngày"), ("Thứ Ba", "Đóng cửa"), ("Thứ Tư", "08:00–11:30, 13:30–17:00"),
        ("Thứ Năm", "Giờ khác"), ("Chủ Nhật", "7:00–18:00")])
    html = (f"<html><body><div data-attrid='title'>X</div>"
            f"<div data-attrid='kc:/location/location:hours'><table>{rows}</table></div></body></html>")
    p = panel.parse(html)
    assert p.hours == {"mon": [["00:00", "24:00"]], "tue": [], "wed": [["08:00", "11:30"], ["13:30", "17:00"]],
                       "sun": [["07:00", "18:00"]]}  # "Giờ khác" is unknown: the day is absent
