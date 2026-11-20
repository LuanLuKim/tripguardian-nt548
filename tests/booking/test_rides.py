from datetime import date

import pytest

import journey
from harness import booking_routes
from journey import areas, rides

DALAT = (11.9404, 108.4583)
DLI = (11.7502, 108.3672)
Q1 = (10.7769, 106.7009)
SGN = (10.8188, 106.6520)
HANOI = (21.0285, 105.8542)
HAN = (21.2212, 105.8072)
BIEN_HOA = (10.9574, 106.8427)
BEFORE_FEE_END = date(2026, 12, 1)


def _row(rows, brand, service):
    return next(r for r in rows if r["brand"] == brand and r["service"] == service)


def test_tiers_are_by_absolute_km():
    t = {"open": 30000, "open_km": 2, "per_km": [[12, 15000], [25, 14000], [None, 13000]]}
    assert rides.fare(30, None, t) == 30000 + 10 * 15000 + 13 * 14000 + 5 * 13000
    assert rides.fare(1, 5, t) == 30000  # inside the opening km: only the opening price


def test_grab_adds_its_platform_fee_until_its_end_date_then_a_share():
    a = rides.place(*DALAT)
    t = rides.load().brands["grab"]["fares"]["lam_dong"]["car4"]
    base = 27000 + 8 * 11880 + 16 * 442  # 2 km open, 8 more, 442/min on 16 of the 20 minutes
    assert rides.fare(10, 20, t) == pytest.approx(base)
    row = _row(rides.quote(10, 20, a, day=BEFORE_FEE_END), "grab", "car4")
    assert (row["vnd_min"], row["vnd_max"]) == (-(-(base + 3000) // 1000) * 1000, -(-(base + 9000) // 1000) * 1000)
    after = _row(rides.quote(10, 20, a, day=date(2027, 3, 1)), "grab", "car4")
    assert after["vnd_min"] == after["vnd_max"] == -(-(base * 1.07) // 1000) * 1000


def test_lam_dong_is_priced_from_each_brands_own_table():
    rows = rides.quote(5, 15, rides.place(*DALAT))
    services = {b: {r["service"] for r in rows if r["brand"] == b} for b in ("grab", "be", "xanhsm")}
    assert services["be"] == {"car4", "car7", "saver", "taxi4", "taxi7"}  # be.com.vn tab Lâm Đồng: no beBike
    assert services["xanhsm"] == {"lado4", "lado7"}  # Lado's taxis on the Xanh SM platform, at Lado's published price
    assert "bike" in services["grab"]
    lado = _row(rows, "xanhsm", "lado4")
    assert lado["vnd_min"] == 15000 + 5 * 11800 and "Lado" in lado["label"]  # no opening km stated: every km charged
    assert _row(rows, "be", "taxi4")["vnd_min"] == 40000 + 3 * 16000


def test_lado_airport_route_is_one_way_and_only_near_its_distance():
    out = rides.quote(30, 40, rides.place(*DALAT), rides.place(*DLI))
    route = [r for r in out if r.get("route")]
    assert {(r["service"].split("@")[0], r["vnd_min"]) for r in route} == {("lado4", 155000), ("lado7", 255000)}
    back = rides.quote(30, 40, rides.place(*DLI), rides.place(*DALAT))
    assert not any(r.get("route") for r in back)  # the page states Đà Lạt -> airport only
    far = rides.quote(41, 50, rides.place(*DALAT), rides.place(*DLI))
    assert not any(r.get("route") for r in far)  # 35 km package, no per-km rate: not past 35 × 1.15


def test_grab_airport_route_runs_both_ways_with_its_per_km():
    there = rides.quote(27, 45, rides.place(*HANOI), rides.place(*HAN), day=BEFORE_FEE_END)
    back = rides.quote(27, 45, rides.place(*HAN), rides.place(*HANOI), day=BEFORE_FEE_END)
    for rows in (there, back):
        r = next(r for r in rows if r["brand"] == "grab" and r.get("route") and r["seats"] == 4)
        assert r["vnd_min"] == -(-(186545 + 7 * 9327 + 3000) // 1000) * 1000 and "Nội Bài" in r["label"]
    assert any(r["label"].startswith("beAirport") for r in there)


def test_airport_pickup_fee_only_when_picked_up_there():
    from_sgn = _row(rides.quote(8, 25, rides.place(*SGN), rides.place(*Q1)), "be", "car4")
    to_sgn = _row(rides.quote(8, 25, rides.place(*Q1), rides.place(*SGN)), "be", "car4")
    assert from_sgn["vnd_min"] - to_sgn["vnd_min"] == 15000  # "Đón tại sân bay TSN" on beCar
    g_from = _row(rides.quote(8, 25, rides.place(*SGN), day=BEFORE_FEE_END), "grab", "car4")
    g_to = _row(rides.quote(8, 25, rides.place(*Q1), day=BEFORE_FEE_END), "grab", "car4")
    assert g_from["vnd_min"] - g_to["vnd_min"] == 10000  # Grab's airport fee, cars picked up at SGN
    bike = [r for r in rides.quote(8, 25, rides.place(*SGN), day=BEFORE_FEE_END) if r["vehicle"] == "motorbike"]
    assert bike and all(r["vnd_min"] < 60000 for r in bike)  # no airport fee on bikes


def test_suburb_to_airport_route_from_another_old_province():
    rows = rides.quote(30, 50, rides.place(*BIEN_HOA), rides.place(*SGN), day=BEFORE_FEE_END)
    r = next(r for r in rows if r["brand"] == "grab" and r.get("route") and r["seats"] == 4)
    assert r["vnd_min"] == -(-(169855 + 13 * 6382 + 3000) // 1000) * 1000 and "Đồng Nai" in r["label"]


def test_an_area_without_a_table_has_no_price():
    rows = rides.quote(5, 15, rides.Place(None, None, None))
    assert {r["brand"] for r in rows} == {"grab", "be", "xanhsm"}
    assert all(r["service"] is None and r["vnd_min"] is None and r["reason"] == "no_table" for r in rows)


def test_a_sub_area_without_its_own_row_uses_its_province():
    hoi_an = rides.place(15.8801, 108.338)
    assert (hoi_an.area, hoi_an.parent) == ("hoi_an", "quang_nam")
    assert {r["service"] for r in rides.quote(5, 15, hoi_an) if r["brand"] == "be"} >= {"car4", "car7"}  # Quảng Nam tab


@pytest.mark.parametrize("point, area", [
    (DALAT, "lam_dong"), (DLI, "lam_dong"), (SGN, "ho_chi_minh"), ((10.9804, 106.6519), "binh_duong"),
    ((10.346, 107.0843), "ba_ria_vung_tau"), (HAN, "ha_noi"), ((11.9982, 109.2193), "khanh_hoa"),
    ((10.2167, 103.9603), "phu_quoc"), ((8.6833, 106.6083), "con_dao"), ((15.8801, 108.338), "hoi_an"),
    ((22.3364, 103.8438), "sa_pa"), ((12.2388, 109.1967), "khanh_hoa"), ((13.75, 100.5), None),
])
def test_area_of_points(point, area):
    assert areas.area_of(*point) == area


def test_route_parses_untrusted_legs():
    out = booking_routes.rides({"legs": f"4.2:12:{DALAT[0]}:{DALAT[1]};8:25:{Q1[0]}:{Q1[1]}:{SGN[0]}:{SGN[1]}"})
    assert [leg["region"] for leg in out["legs"]] == ["lam_dong", "ho_chi_minh"]
    assert set(out["brands"]) == {"grab", "be", "xanhsm"} and all(b["source"] for b in out["brands"].values())
    saigon = {(q["brand"], q["service"]) for q in out["legs"][1]["quotes"] if q["vnd_min"]}
    assert ("be", "car4") in saigon and ("xanhsm", "bike") in saigon
    for bad in ("", "1:2:3", "0:5:11:108", "4:5:91:108", "4:5:11:108:12", "4:5:11:108:nan:108",
                ";".join(["1:1:11:108"] * (rides.MAX_LEGS + 1))):
        with pytest.raises(ValueError):
            booking_routes.rides({"legs": bad})


def test_public_api():
    assert journey.ride_quotes is rides.quotes and journey.parse_ride_legs is rides.parse_legs
