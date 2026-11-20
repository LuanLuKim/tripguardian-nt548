"""The tariff parsers (journey.tariffs) on small pages written like the brands' own, one case per wording seen on them,
and the build's checks. Numbers marked "checked by hand" were read off the live pages on 17/11/2026."""

import json

import pytest

from journey.tariffs import be, build, grab, lado, xanhsm
from journey.tariffs.common import Fare, fold, km, listed_areas


def test_fold_keeps_decimals_only_when_asked():
    assert fold("0,5 Km đầu") == "0 5 km dau"
    assert fold("0,5 Km đầu", decimals=True) == "0.5 km dau"
    assert fold("Giá mở cửa (1.4km đầu)", decimals=True) == "gia mo cua 1.4km dau"
    assert (km("0.5"), km("1,3"), km("2 ₫"), km("")) == (0.5, 1.3, 2.0, None)


def test_listed_areas():
    assert listed_areas("Khánh Hòa (Khánh Hòa cũ, Ninh Thuận)") == (["khanh_hoa", "ninh_thuan"], [])
    assert listed_areas("Gia Lai") == (["gia_lai"], [])  # one name: that old province only, not Bình Định
    assert listed_areas("Hồ Chí Minh (Hồ Chí Minh cũ, Bình Dương, Bà Rịa - Vũng Tàu)")[0] == [
        "ho_chi_minh", "binh_duong", "ba_ria_vung_tau"]


def _f(open_, open_km, per_km, **kw):
    return Fare(open=open_, open_km=open_km, per_km=per_km, **kw).as_dict()


@pytest.mark.parametrize("pairs, want", [
    # Lâm Đồng beCar 4 chỗ (checked by hand)
    ([("Từ 0-2km (*)", "31.201 ₫"), ("1km tiếp theo với quãng đường 2km-12km", "11.574 ₫"),
      ("1 km tiếp theo sau 12km", "10.568 ₫"), ("Phụ phí đêm khuya", "20.000 ₫")],
     _f(31201, 2.0, [[12.0, 11574], [None, 10568]], night=20000)),
    # TP.HCM beCar 4 chỗ: the "2 - 12km" tier the old reader dropped (checked by hand), and the TSN pickup fee
    ([("Từ 0-2km (*)", "31.501 ₫"), ("1km tiếp theo với quãng đường 2 - 12km", "11.805 ₫"),
      ("1km tiếp theo sau 12km", "10.779 ₫"), ("Phí đặt lịch", "10.000 ₫"), ("Đón tại sân bay TSN", "15.000 ₫")],
     _f(31501, 2.0, [[12.0, 11805], [None, 10779]], pickup={"SGN": 15000})),
    # TP.HCM beTaxi 4 chỗ: a plain rate before "sau 12km" ends at 12 (checked by hand)
    ([("2 km đầy tiên 7 phút đầu tiên(*)", "32.000 ₫"), ("1km tiếp theo", "12.500 ₫"), ("1km tiếp theo sau 12km", "11.500 ₫")],
     _f(32000, 2.0, [[12.0, 12500], [None, 11500]])),
    # "Từ Km 31": the tier before ends at km 30
    ([("0.5km đầu tiên (*)", "8000 ₫"), ("Km tiếp theo đến Km 30", "13300 ₫"), ("Từ Km 31", "9500 ₫")],
     _f(8000, 0.5, [[30.0, 13300], [None, 9500]])),
    # "Giá km thứ 30 trở đi": the 30th km on, so the tier before ends at 29
    ([("Giá mở cửa (1km đầu)", "15.000 ₫"), ("Giá km tiếp theo", "16.000 ₫"), ("Giá km thứ 30 trở đi", "14.500 ₫")],
     _f(15000, 1.0, [[29.0, 16000], [None, 14500]])),
    # "1,3km", "Km12" glued, "Từ Km13"
    ([("1,3km đầu tiên (*)", "20.000 ₫"), ("Km tiếp theo đến Km12", "15.000 ₫"), ("Từ Km13", "13.500 ₫")],
     _f(20000, 1.3, [[12.0, 15000], [None, 13500]])),
    # "1m tiếp theo từ 12km" ("1m" is "1km")
    ([("2km đầu tiên 7 phút đầu tiên(*)", "37.239 ₫"), ("1km tiếp theo", "14.090 ₫"), ("1m tiếp theo từ 12km", "13.084 ₫")],
     _f(37239, 2.0, [[12.0, 14090], [None, 13084]])),
    # English tab
    ([("First 2 km(*)", "33.000 ₫"), ("Next km to Km 12", "10.500 ₫"), ("From Km 13", "10.000 ₫")],
     _f(33000, 2.0, [[12.0, 10500], [None, 10000]])),
    ([("Opening price (first 2km)", "38.000 ₫"), ("Price per additional km", "16.500 ₫"),
      ("Price from 21st km onwards", "14.000 ₫")], _f(38000, 2.0, [[20.0, 16500], [None, 14000]])),
    ([("From 0-2km (*)", "31.704 ₫"), ("Next 1km (Distance from 2-12km)", "10.568 ₫"),
      ("Next 1 km (Distance greater than 12km)", "10.040 ₫")], _f(31704, 2.0, [[12.0, 10568], [None, 10040]])),
    # km column: "Kilomet mở cửa" "0.5" is a distance, not 5 đồng; "2 ₫" (sic) too
    ([("Giá mở cửa (*)", "10.000 ₫"), ("Kilomet mở cửa", "0.5"), ("Km tiếp theo đến Km 30", "14.500 ₫"),
      ("Từ Km 31", "10.300 ₫")], _f(10000, 0.5, [[30.0, 14500], [None, 10300]])),
    ([("Giá mở cửa", "41.000 ₫"), ("Kilomet mở cửa", "2 ₫"), ("Kilomet tiếp theo", "19.000 ₫")],
     _f(41000, 2.0, [[None, 19000]])),
    # beCar Tiết Kiệm thresholds (Lâm Đồng, checked by hand): equal rates merge into one tier
    ([("Giá mở cửa", "31.201 ₫"), ("Ngưỡng km 1", "2"), ("Giá mỗi km 1", "11.245 ₫"), ("Ngưỡng km 2", "12"),
      ("Giá mỗi km 2", "11.245 ₫")], _f(31201, 2.0, [[None, 11245]])),
    # "0.5km đến 30km" / "Km 31 trở đi"
    ([("0.5km đầu tiên", "10.000 ₫"), ("0.5km đến 30km", "14.900 ₫"), ("Km 31 trở đi", "10.500 ₫")],
     _f(10000, 0.5, [[30.0, 14900], [None, 10500]])),
])
def test_be_fare_wordings(pairs, want):
    fare, why, _ = be.fare_of(pairs)
    assert why == "" and fare.as_dict() == want


def test_be_mislabels_are_read_by_rule_and_reported():
    # Đà Nẵng beCar 4: "1km đầu tiên" under a stated opening price is the price of each further km
    fare, _, reread = be.fare_of([("Từ 0-2km (*)", "29.188 ₫"), ("1km đầu tiên", "14.090 ₫")])
    assert fare.as_dict() == _f(29188, 2.0, [[None, 14090]]) and "each further km" in reread[0]
    # Đà Nẵng beTaxi 7: "1km đầu tiên" = "1" is the opening km
    fare, _, reread = be.fare_of([("Phí mở cửa", "25.000 ₫"), ("1km đầu tiên", "1"), ("1km tiếp theo", "22.600 ₫")])
    assert fare.as_dict() == _f(25000, 1.0, [[None, 22600]]) and not reread
    # Huế beTaxi 4: "Kilomet gói" "1" with no package price is the opening km
    fare, _, reread = be.fare_of([("Giá mở cửa", "20.000 ₫"), ("Kilomet gói", "1"), ("Kilomet tiếp theo", "16.500 ₫")])
    assert fare.open_km == 1.0 and "opening km" in reread[0]
    # Kon Tum: no opening km stated, every km charged
    fare, _, reread = be.fare_of([("Giá mở cửa", "32.000 ₫"), ("Kilomet tiếp theo", "15.000 ₫")])
    assert fare.open_km == 0.0 and "not stated" in reread[0]


@pytest.mark.parametrize("pairs, why", [
    ([("Từ 0-25km (*)", "221.514 ₫"), ("1km tiếp theo", "8.368 ₫")], "package"),
    ([("Gói", "485.000 ₫"), ("Kilomet gói", "30"), ("Kilomet tiếp theo", "12.600 ₫")], "package"),
    ([("Phụ phí đêm khuya", "20.000 ₫"), ("Phí thay đổi điểm đến", "10.000 ₫")], "flexible"),
    ([("Từ 0-2km (*)", "31.000 ₫"), ("Giá đặc biệt cuối tuần", "9.000 ₫")], "no rule reads"),
    ([("Từ 0-2km (*)", "31.000 ₫"), ("Km tiếp theo đến Km 30", "13.000 ₫"), ("Từ Km 26", "12.000 ₫")], "tier ends"),
])
def test_be_drops_a_block_it_cannot_read_whole(pairs, why):
    fare, reason, _ = be.fare_of(pairs)
    assert fare is None and why in reason


def _be_page(tabs: list[tuple[str, list[tuple[str, list[tuple[str, str]]]]]]) -> str:
    heads, panes = [], []
    for i, (name, blocks) in enumerate(tabs):
        heads.append(f'<a id="pills-{i}-tab" href="#">{name}</a>')
        body = "".join(f'<div class="box-detail"><div class="sub-detail">{t}</div>'
                       + "".join(f'<p class="note">{n}</p><p class="price">{p}</p>' for n, p in pairs) + "</div>"
                       for t, pairs in blocks)
        panes.append(f'<div id="pills-{i}" role="tabpanel">{body}</div>')
    return "".join(heads) + "".join(panes)


def test_be_page():
    car = [("Từ 0-2km (*)", "31.704 ₫"), ("1km tiếp theo với quãng đường 2 - 12km", "10.568 ₫"),
           ("1km tiếp theo sau 12km", "10.040 ₫")]
    html = _be_page([
        ("Hà Nội", [("beCar 4 chỗ", car), ("beCar Plus", car), ("beCar Tiết Kiệm", [("Phụ phí đêm khuya", "20.000 ₫")]),
                    ("beCar Airport", [("Từ 0-2 km", "26.747 ₫"), ("1km tiếp theo", "8.916 ₫")]),
                    ("beTaxi 7 chỗ", [("Phí mở cửa (2km đầu tiên)", "38.000 ₫"), ("1km tiếp theo", "16.500 ₫"),
                                      ("1km tiếp theo sau 21km", "14.000 ₫")])]),
        ("Hà Nội", [("beCar 4 Seats", [("From 0-2km (*)", "31.704 ₫"), ("Next 1km (Distance from 2-12km)", "10.568 ₫"),
                                       ("Next 1 km (Distance greater than 12km)", "10.040 ₫")]),
                    ("beAirport - beAirport", [("First 0-2 km", "26.747 ₫"), ("Each subsequent km", "8.916 ₫")]),
                    ("beTaxi 7 Seats", [("Opening price (first 2km)", "38.000 ₫"), ("Price per additional km", "16.500 ₫"),
                                        ("Price from 21st km onwards", "14.000 ₫")])]),
        ("Quảng Bình", [("beTaxi 4 chỗ", [])]),
        ("Phú Thọ", [("beTaxi", [("1,3km đầu tiên (*)", "20.000 ₫"), ("Km tiếp theo đến Km12", "15.000 ₫")])]),
        ("Bình Định", [("beTaxi 4 chỗ - Tuyến cố định sân bay", [("Giá", "300.000 ₫")])]),
        ("Nowhere", [("beCar 4 chỗ", car)]),
    ])
    p, meta = be.parse(html)
    assert meta["tabs"] == ["Hà Nội", "Hà Nội", "Quảng Bình", "Phú Thọ", "Bình Định", "Nowhere"]
    assert set(p.fares["ha_noi"]) == {"car4", "taxi7"}  # Plus left out, Tiết Kiệm states no price
    assert p.fares["ha_noi"]["car4"].per_km == [[12.0, 10568], [None, 10040]]  # the English tab agrees: no conflict
    # "sau 21km" (ends at 21) and "from 21st km" (ends at 20) disagree: the first stays, the other is reported
    assert p.fares["ha_noi"]["taxi7"].per_km[0][0] == 21.0 and len(p.conflicts) == 1
    assert len(p.routes) == 1 and p.routes[0]["to"] == {"airport": "HAN"} and p.routes[0]["both_ways"]
    reasons = " | ".join(f"{w}: {y}" for w, y in p.skipped)
    for expected in ("Tiết Kiệm: no opening price", "Quảng Bình | beTaxi 4 chỗ: empty block",
                     "Phú Thọ | beTaxi: the title states no seat count", "Tuyến cố định sân bay: fixed route",
                     "Nowhere: tab names no province"):
        assert expected in reasons


def _next_data(price_data: dict) -> str:
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps({"props": {"pageProps": {"priceData": price_data}}})}</script>'


def _row(city, *items):
    return {"city": city, "items": [{"value1": a, "value2": b, "value3": None} for a, b in items]}


def test_xanhsm_pages():
    car_items = [("Giá mở cửa (2 km đầu)", "30.500 VNĐ (Giảm tới 20.500 VNĐ hoặc tăng đến 54.900 VNĐ)"),
                 ("Giá cước từ km tiếp theo đến km 12", "15.200 VNĐ (Giảm tới 9.200 VNĐ)"),
                 ("Giá cước từ km tiếp theo đến km 25", "14.700 VNĐ"), ("Giá cước từ km 26 trở đi", "13.300 VNĐ")]
    other = [("Giá mở cửa (0,5 km đầu)", "12.500 VNĐ"), ("Giá cước từ km tiếp theo đến km 25", "12.400 VNĐ"),
             ("Giá cước từ km 26 trở đi", "11.100 VNĐ")]
    car = _next_data({"taxi": {"rows": [
        _row("Hồ Chí Minh (Hồ Chí Minh cũ, Bình Dương, Bà Rịa - Vũng Tàu)", *car_items),
        _row("Đồng Nai (Đồng Nai cũ, Bình Phước)\t", *car_items), _row("Bình Phước", *other),
        _row("Gia Lai", *other)]}, "premium": {"rows": [_row("Lâm Đồng", *car_items)]}})
    bike = _next_data({"gia_niem_yet": {"columns": "Giá niêm yết|Green SM Bike (VNĐ)|Green SM Bike Plus (VNĐ)", "rows": [
        _row("TP. Hồ Chí Minh", ("Giá khởi hành (02 km đầu)", "10.200"), ("Giá tiếp theo (từ km tiếp theo)", "4.150"),
             ("Phí thời gian di chuyển (VNĐ/phút)", "275")),
        _row("Hồ Chí Minh  (địa phận TP HCM cũ)", ("Giá khởi hành (02 km đầu)", "-"), ("Giá tiếp theo (từ km tiếp theo)", "-"))]}})
    p, _ = xanhsm.parse({"car": car, "bike": bike})
    hcm = Fare(open=30500, open_km=2.0, per_km=[[12.0, 15200], [25.0, 14700], [None, 13300]]).as_dict()  # by hand
    assert all(p.fares[k]["car4"].as_dict() == hcm for k in ("ho_chi_minh", "binh_duong", "ba_ria_vung_tau", "dong_nai"))
    assert p.fares["binh_phuoc"]["car4"].open == 12500  # its own row wins over the list in the Đồng Nai row
    assert "gia_lai" in p.fares and "binh_dinh" not in p.fares  # "Gia Lai" alone: the old Gia Lai only
    assert "lam_dong" not in p.fares  # Premium is not read
    assert p.fares["ho_chi_minh"]["bike"].as_dict() == _f(10200, 2.0, [[None, 4150]], per_min=275)
    assert any("Bike Plus only" in y for _, y in p.skipped)


def test_lado_page():
    html = """<div class="boardprice-item col-4"><p class="name"> Taxi 4 chỗ </p>
      <div class="price">11.800</div> <div class="unit">VNĐ/km</div>
      <div class="pricemore-tt"> Giá mở cửa </div> <div class="pricemore-price"> 15.000 VNĐ </div>
      <div class="pricemore-tt"> Vượt ngưỡng 26 km </div> <div class="pricemore-price"> 10.500 VNĐ </div></div>
      <div class="boardprice-item col-4"><p class="name"> Xe hợp đồng </p><div class="price">20.000</div>
      <div class="unit">VNĐ/km</div></div>
      <div class="swiper-slide"><div class="route-name">Đà Lạt(Dalat) -> Sân Bay(Airport) (35km)</div>
      <div class="route-set-item"> 4 chỗ(Seats): 155.000 VNĐ </div><div class="route-set-item"> 7 chỗ(seats): 255.000 VNĐ
      </div></div>
      <div class="swiper-slide"><div class="route-name">Đà Lạt (Dalat)<>Nha Trang (135km)</div></div>"""
    p, _ = lado.parse(html)
    assert p.fares["lam_dong"]["lado4"].as_dict() == _f(15000, 0.0, [[26.0, 11800], [None, 10500]])  # checked by hand
    assert [(r["service"], r["price"], r["both_ways"], r["to"]) for r in p.routes] == [
        ("lado4", 155000, False, {"airport": "DLI"}), ("lado7", 255000, False, {"airport": "DLI"})]
    assert any("contract" in y for _, y in p.skipped)


GRAB = """<table><tr><th>Thành phố/ Tỉnh</th><th>Khu vực</th><th>For cheaper fare, using</th><th>Giá cước (VNĐ)</th>
<th>Giá cước (VNĐ)</th><th>Giá cước (VNĐ)</th></tr><tr><th>Thành phố/ Tỉnh</th><th>Khu vực</th><th>Dịch vụ</th>
<th>Giá cước tối thiểu 2km đầu tiên</th><th>Giá cước mỗi km tiếp theo</th><th>Giá cước tính theo thời gian di chuyển</th></tr>
<tr><td rowspan="2">Lâm Đồng</td><td rowspan="2"></td><td>GrabCar 4 chỗ</td><td>27.000</td><td>11.880</td><td>442</td></tr>
<tr><td>GrabCar Plus</td><td>30.000</td><td>13.000</td><td>500</td></tr></table>
<p>đến 25/02/2027: Đối với các dịch vụ GrabBike, mức phí nền tảng sẽ từ 1.000đ đến 3.000đ. Đối với các dịch vụ Grab 4 bánh,
mức phí nền tảng sẽ từ 3.000đ đến 9.000đ.</p><p>Từ 26/02/2027 đến khi có thông báo mới: phí nền tảng là 7% trên giá cước.</p>
<p>Phí vận hành Sân bay: 10.000đ cho ô tô. Các Sân bay đang được áp dụng bao gồm: Tân Sơn Nhất, Cam Ranh.</p>
<p>Cập nhật lần cuối: 08/07/2026</p>"""


def test_grab_page():
    p, meta = grab.parse(GRAB)
    assert p.fares["lam_dong"]["car4"].as_dict() == _f(27000, 2, [[None, 11880]], per_min=442)  # checked by hand
    assert set(p.fares["lam_dong"]) == {"car4"}
    assert meta["fee"] == {"until": "2027-02-25", "motorbike": [1000, 3000], "car": [3000, 9000], "after_pct": 7}
    assert p.airport_pickup == {"SGN": 10000, "CXR": 10000} and meta["page_updated"] == "2026-07-08"


def _pages(root, be_html=None):
    car = [("Từ 0-2km (*)", "31.201 ₫"), ("1km tiếp theo", "11.574 ₫")]
    files = {
        "grab/page.html": GRAB,
        "be/page.html": be_html or _be_page([("Lâm Đồng", [("beCar 4 chỗ", car)])]),
        "xanhsm/car.html": _next_data({"taxi": {"rows": [_row("Gia Lai", ("Giá mở cửa (2 km đầu)", "20.000 VNĐ"),
                                                              ("Giá cước từ km 26 trở đi", "11.000 VNĐ"))]}}),
        "xanhsm/bike.html": _next_data({"gia_niem_yet": {"columns": "Giá niêm yết|Green SM Bike (VNĐ)", "rows": []}}),
        "lado/page.html": """<div class="boardprice-item"><p class="name">Taxi 4 chỗ</p><div class="price">11.800</div>
            <div class="unit">VNĐ/km</div><div class="pricemore-tt">Giá mở cửa</div><div class="pricemore-price">15.000
            </div></div>""",
    }
    for rel, html in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(html, encoding="utf-8")


def test_build_writes_reports_and_refuses_a_big_move(tmp_path):
    _pages(tmp_path)
    table, report = tmp_path / "rides_tariffs.json", tmp_path / "report.json"
    rep = build.build(src=tmp_path, table=table, report=report, today="2026-11-17")
    t = json.loads(table.read_text())
    assert rep["written"] and set(t["brands"]) == {"grab", "be", "xanhsm"}
    assert t["brands"]["xanhsm"]["fares"]["lam_dong"]["lado4"]["open"] == 15000  # Lado under Xanh SM
    assert "phí nền tảng" in t["brands"]["grab"]["note"] and t["brands"]["grab"]["platform_fee"]["after_pct"] == 7
    # Gia Lai states a tier "từ km 26 trở đi" with nothing before it: the row is dropped and reported, not guessed
    assert any("Gia Lai" in s["where"] and "no tier before it" in s["why"] for s in rep["brands"]["xanhsm"]["skipped"])
    # Be's Lâm Đồng car doubles: the build stops and keeps the old table
    car = [("Từ 0-2km (*)", "62.402 ₫"), ("1km tiếp theo", "23.148 ₫")]
    _pages(tmp_path, _be_page([("Lâm Đồng", [("beCar 4 chỗ", car)])]))
    before = table.read_text()
    rep = build.build(src=tmp_path, table=table, report=report, today="2026-11-17")
    assert not rep["written"] and table.read_text() == before
    assert rep["changes"]["moved"][0]["fare"] == "be/lam_dong/car4" and json.loads(report.read_text())["errors"]
    assert build.build(src=tmp_path, table=table, report=report, accept=True)["written"]


def test_build_refuses_a_page_it_cannot_read(tmp_path):
    _pages(tmp_path, "<html>new layout</html>")
    rep = build.build(src=tmp_path, table=tmp_path / "t.json", report=tmp_path / "r.json", today="2026-11-17")
    assert not rep["written"] and not (tmp_path / "t.json").exists()
    assert any(e.startswith("be: no fare read") for e in rep["errors"])
