# Bàn giao: giá gọi xe toàn quốc + tổng chi phí cửa tới cửa (17/11/2026)

> **Cập nhật 17/11 chiều: §6 bước 1–5 đã xong và lên prod 12:28 (`./run.sh prod`, kèm lịch trang chủ và mascot mới theo lệnh chủ dự án); `config/rides.yaml` đã xóa. Chưa commit.** Trạng thái và việc còn mở ở §8 cuối file; §4–§6 giữ lại làm lịch sử quyết định.

Đọc file này trước, rồi `docs/BOOKING.md` §Gọi xe. Không cần đọc lại lịch sử phiên trước.

## 1. Mục tiêu (chủ dự án chốt)

- Người dùng chọn điểm xuất phát ở bất kỳ đâu trong Việt Nam. Mỗi thẻ cách đi lên Đà Lạt (máy bay, xe khách) cần hiện **tổng chi phí cửa tới cửa** = gọi xe nhà → sân bay/bến (giá tỉnh xuất phát) + vé × số người + gọi xe sân bay/bến Đà Lạt → chỗ ở (giá Lâm Đồng). Bấm vào thẻ thì xem từng chặng. Chặng nào chưa có giá thì không ra tổng, chỉ nói rõ chặng nào thiếu (giống `total()` trong `web/src/user/rides.ts`).
- Tự lái ô tô / xe máy: **chỉ hiện km và giờ đi**, không ước tiền xăng hay BOT (đúng như hiện tại).
- Giá **chỉ lấy từ bảng hãng công bố**, không mượn giá tỉnh khác, không bịa. Dữ liệu phải làm sạch rất kỹ; chủ dự án nhấn mạnh chất lượng production.
- Ba hãng: Grab, Be, Xanh SM (nay là Green SM). Không mở app (web không mở được app).

## 2. Đang có, đã lên prod (17/11, deploy 09:38)

- `GET /api/harness/rides?legs=km:phút:lat:lng;…` (`src/journey/rides.py`, route ở `src/harness/booking_routes.py`). Giá đọc từ `config/rides.yaml`, chỉ có 3 vùng `lam_dong`, `ho_chi_minh`, `ha_noi`, vùng xác định bằng bán kính quanh tâm.
- Planning gắn `distance_km` vào item `travel` (`src/planning/travel.py` `road_km`, `build.py` `itinerary()`).
- Web: thanh *Gọi xe giữa các điểm* + ghost so 3 hãng mỗi chặng (`web/src/user/screens/plan/Rides.tsx`, `web/src/user/rides.ts`, `css/rides.css`), ô địa chỉ xuất phát ngay trong hàng (`OriginRow`), chip lựa chọn hiện khi rê chuột (`FillRows`), tên *Phương tiện lên Đà Lạt*.
- `config/rides.yaml` sửa lúc 10:30 (prod đọc config trực tiếp nên đã có hiệu lực). Lâm Đồng có:
  - Be: beCar 4/7, beCar Tiết Kiệm, beTaxi 4/7 (không có beBike).
  - Xanh SM: taxi Lado 4/7, tính theo giá Lado (Green SM ở Lâm Đồng chạy bằng xe của đối tác Lado; không có Xanh SM Bike).

## 3. Đã sửa nhưng CHƯA lên prod

- **Web** (`rides.ts` `priceOf` chọn dịch vụ rẻ nhất đủ chỗ trong mỗi hãng, `missingOf` hiện nhãn "không có xe máy", chip ghi tên dịch vụ): build xong ở `web/.deploy-build` nhưng chưa chép sang `web/dist`. Lý do: cùng cây làm việc có `web/src/user/home/MiniCalendar.tsx` + `css/home.css` của phiên `tripguardian-93`, chủ dự án đang duyệt mẫu huy hiệu thời tiết và phiên đó đã nói "wait". Chỉ ship khi chủ dự án duyệt lịch hoặc bảo ship.
- `tests/booking/test_rides.py` đã cập nhật theo config 10:30 (7 test pass).
- **Chưa commit gì** của toàn bộ tính năng gọi xe. Repo này commit tác giả `hohoangluan`, không thêm trailer co-author nếu chủ dự án không yêu cầu; push từ gpu156 không được (chủ dự án tự push).

## 4. Việc dở: dữ liệu toàn quốc (bắt đầu từ đây)

Kiến trúc đã chọn:

| Phần | Vị trí | Trạng thái |
|---|---|---|
| 63 tỉnh cũ + Côn Đảo → 34 tỉnh mới, tên gọi, khu vực con (Phú Quốc, Sa Pa, Hội An), 12 sân bay | `config/provinces.yaml` | **Xong**, đã kiểm khớp tên |
| Dùng chung: dựng lưới bảng (rowspan), `fold`, `vnd`, `area_key`, `listed_areas`, `airport_code`, `Fare`, `Parsed`, `problems()` (biên hợp lý) | `src/journey/tariffs/common.py` | **Xong**, chạy đúng |
| Bộ đọc Grab | `src/journey/tariffs/grab.py` | **Xong**: 60 vùng, 20 tuyến cố định, phí nền tảng (1–3k xe máy, 3–9k ô tô tới 25/02/2027, sau đó 7%), phí sân bay 10k cho ô tô đón tại SGN/DAD/CXR/PQC. Bỏ có chủ đích: "Bãi Dài ⇒ Nha Trang", "Đi Ghép" |
| Bộ đọc Be | `src/journey/tariffs/be.py` | **Phải viết lại `fare_of`** (xem §5) |
| Bộ đọc Xanh SM | `src/journey/tariffs/xanhsm.py` | Chưa viết |
| Bộ đọc Lado (đối tác Xanh SM ở Lâm Đồng) | `src/journey/tariffs/lado.py` | Chưa viết |
| Ranh giới tỉnh cũ đã làm sạch | `config/provinces.geojson` | Chưa làm |
| Build: tải trang → đọc → kiểm → gộp → báo cáo → ghi bảng sạch | `src/journey/tariffs/build.py` + `__main__.py` (`python -m journey.tariffs refresh`) | Chưa viết |
| Runtime: điểm → tỉnh cũ/khu vực con | `src/journey/areas.py` | Chưa viết |
| Runtime: giá đọc từ bảng sạch, tuyến cố định, phí sân bay, phí nền tảng theo ngày | `src/journey/rides.py` | Phải viết lại |
| Gắn giá xe vào chặng `transfer` của journey + tổng ở thẻ cách đi | `src/journey/options.py`, `web/src/user/screens/plan/WayIn.tsx` | Chưa làm |

Quy ước dữ liệu:
- Trang tải về lưu ở `data/rides/<grab|be|xanhsm|lado>/page.html` (gitignored, mỗi nguồn một thư mục theo RULE §2).
- Bảng sạch ghi vào `config/rides_tariffs.json` (đưa vào git để xem diff mỗi lần cập nhật giá).
- Báo cáo build (dòng bỏ qua, xung đột, thay đổi > 30% so với lần trước) ghi vào `data/rides/report.json` và in ra màn hình. Build lỗi thì không ghi đè bảng cũ.
- Vùng giá luôn là **tỉnh cũ** (khóa trong `provinces.yaml`), vì cả 3 hãng vẫn định giá theo tỉnh cũ.
  - Nhãn chỉ ghi một tên ("Gia Lai") thì chỉ áp cho tỉnh cũ cùng tên.
  - Nhãn liệt kê rõ ("Khánh Hòa (Khánh Hòa cũ, Ninh Thuận)") thì áp cho đúng các tỉnh trong danh sách (`listed_areas`).
  - Khu vực con không có dòng riêng thì lùi về dòng của tỉnh cha.
- Ghế: 4 chỗ = 4 khách; 6/7 chỗ = 6 khách. Chỉ giữ dịch vụ cơ bản (bỏ Plus, Premium, tiếng Anh, thú cưng, xe điện, thuê theo giờ, gói đường dài), vì chúng không bao giờ rẻ nhất.
- Không đổi khóa của `config/rides.yaml` trước khi deploy code mới: prod đang chạy code cũ đọc file này với loader strict. Bảng mới dùng file mới (`config/rides_tariffs.json`); hằng số như `round_vnd` đặt trong code. Xóa `config/rides.yaml` sau khi đã deploy code mới.

## 5. Bẫy dữ liệu đã gặp (đọc kỹ trước khi viết tiếp)

**Be** (`https://be.com.vn/consumer/be-transport/`, bản tiếng Việt; 34 tab `pills-N`, tab "Hà Nội" xuất hiện 2 lần với bản tiếng Anh):
- Mỗi tab gồm các khối `class="box-detail"`, tên dịch vụ ở `.sub-detail`, giá là các cặp `<p class="note">` + `<p class="price">` (`_tabs`, `_blocks` trong `be.py` đã đúng).
- `fare_of` hiện tại **bỏ sót bậc km mà không báo**. Ví dụ TP.HCM beCar 4 chỉ còn bậc "sau 12km" vì không khớp được "1km tiếp theo với quãng đường 2 - 12km". Viết lại theo nguyên tắc: **mỗi dòng có giá phải được phân loại** (giá mở cửa, km mở cửa, bậc km, phụ phí đêm, phí bỏ qua); có dòng không hiểu được thì loại cả khối và ghi báo cáo.
- Chuẩn hóa nhãn mà vẫn giữ số thập phân ("0.5km", "1.4km"; `fold()` hiện xóa dấu chấm nên "0.5" thành "0 5"). Cột km ("Kilomet mở cửa", "1km đầu tiên" có giá trị "1") phải đọc thành số km, không đọc bằng `vnd()`.
- Các kiểu ghi đã thấy:
  - Mở cửa: "Từ 0-2km", "From 0-2km", "0 - 2km (*) First 7 minutes", "2km đầu tiên", "2kn đầu tiên", "2 km đầy tiên 7 phút đầu tiên", "0.5km đầu tiên", "1km đầu tiên (*)", "Giá mở cửa (1.4km đầu)", "Giá mở cửa (1km đầu)", "Phí mở cửa (2km đầu tiên)", "Opening price (first 2km)", "First 2 km", "First 0-2 km", "Giá cước tối thiểu 2km đầu tiên", "0.5 Km đầu", "0.5Km đầu".
  - Bậc có mốc trên: "1km tiếp theo với quãng đường 2km-12km" / "2 - 12 km:", "Next 1km (Distance from 2-12km)", "Km tiếp theo đến Km 30", "Next km to Km 12", "1km tiếp cho quãng đường 12km", "0.5km đến 30km", "1km tiếp theo từ 2km-12km".
  - Bậc từ mốc trở đi: "1 km tiếp theo sau 12km", "1km tiếp theo sau 21km", "1m tiếp theo từ 12km" ("1m" là gõ nhầm "1km"), "Next 1 km (Distance greater than 12km)", "Từ Km 31", "Km 31 trở đi", "From Km 13", "Giá km thứ 30 trở đi", "Price from 21st km onwards". Với "Từ Km 31" thì bậc trước kết thúc ở km 30; với "sau 12km" thì kết thúc ở 12.
  - Bậc không mốc: "1km tiếp theo", "1 km tiếp theo", "Next 1km", "Kilomet tiếp theo", "Giá km tiếp theo", "Price per additional km", "Each subsequent km".
  - Ngưỡng: "Ngưỡng km 1 / Giá mỗi km 1 / Ngưỡng km 2 / Giá mỗi km 2" (beCar Tiết Kiệm).
- Lỗi nhãn của chính trang Be: Đà Nẵng beCar 4/7 ghi "Từ 0-2km 29.188" rồi "1km đầu tiên 14.090", nghĩa thực là giá km tiếp theo. Được phép sửa theo luật này nhưng phải ghi vào báo cáo là "đã hiểu lại". Đà Nẵng beTaxi 7 ghi "1km đầu tiên" có giá trị "1", tức là km mở cửa.
- Loại cả khối khi là gói ("Gói", "Kilomet gói", "Package", "Từ 0-25km", "đường dài", "Phí qua đêm"), khi khối rỗng (Quảng Bình beTaxi), và khi beCar Tiết Kiệm ở TP.HCM/Hà Nội không ghi giá (giá linh hoạt).
- beAirport (Hà Nội: "First 0-2 km" 26.747, "Each subsequent km" 8.916) là giá theo km chỉ cho chuyến đi/về Nội Bài: ghi thành tuyến `{"to": {"airport": "HAN"}, "both_ways": true, "fare": {...}}`. Bình Định "Tuyến cố định sân bay" 300k/390k dùng sân bay Phù Cát (UIH), không có trong bảng sân bay, nên bỏ và ghi báo cáo.
- Số đã kiểm tay (dùng làm test):
  - Lâm Đồng: beCar 4: 31.201đ/2km, 11.574đ (2–12km), 10.568đ; beCar 7: 37.239đ, 14.090đ, 13.084đ; Tiết Kiệm: 31.201đ, 11.245đ; beTaxi 4: 40.000đ/2km, 16.000đ; beTaxi 7: 50.000đ, 22.500đ.
  - TP.HCM: beBike 13.817đ, 4.633đ; beCar 4: 31.501đ, 11.805đ, 10.779đ; beCar 7: 37.239đ, 14.372đ, 13.346đ; beTaxi 4: 32.000đ, 12.500đ, 11.500đ; beTaxi 7: 38.000đ, 15.500đ, 14.500đ.
  - Hà Nội: beBike 14.472đ, 4.918đ; beCar 4: 31.704đ, 10.568đ, 10.040đ; beCar 7: 37.319đ, 13.194đ, 12.048đ.

**Xanh SM** (`https://www.xanhsm.com/vn-vi/xanhsm-car` và `/vn-vi/greensm-bike`):
- Giá nằm trong JSON `__NEXT_DATA__` → `props.pageProps.priceData`. Trang car có các khóa `taxi`, `two_ways`, `premium`, `luxury`; trang bike có `gia_niem_yet`, `phu_phi`, `notes`. Mỗi dòng có dạng `{city, items:[{value1, value2, value3}]}`.
- Chỉ dùng `taxi` (dịch vụ chính, ghi là "Xanh SM Taxi") và bike thường (`value2`; `value3` là Bike Plus).
- `city` dạng "Khánh Hòa (Khánh Hòa cũ, Ninh Thuận)" thì dùng `listed_areas`. "Hồ Chí Minh (địa phận TP HCM cũ)" / "(địa phận Bình Dương cũ)" là dòng Bike Plus.
- Có xung đột: "Bình Phước" đứng riêng, đồng thời nằm trong "Đồng Nai (Đồng Nai cũ, Bình Phước)". Giữ dòng riêng (cụ thể hơn) và ghi báo cáo.
- `value2` của taxi có dạng "30.500 VNĐ (Giảm tới 20.500 VNĐ hoặc tăng đến 54.900 VNĐ)": lấy số đầu (giá niêm yết).
- Bậc: "Giá mở cửa (2 km đầu)", "từ km tiếp theo đến km 12", "đến km 25", "từ km 26 trở đi". Bike: "Giá khởi hành (02 km đầu)", "Giá tiếp theo", "Phí thời gian di chuyển (VNĐ/phút)".
- Không có Lâm Đồng ở cả hai bảng.

**Lado** (`https://ladotaxi.com`, khối `boardprice-item`):
- Taxi 4 chỗ: mở cửa 15.000đ, 11.800đ/km, từ km 26 là 10.500đ. Taxi 7 chỗ: 15.000đ, 18.700đ/km, từ km 26 là 13.500đ. Trang không ghi giá mở cửa đi được bao xa, nên `open_km: 0` (mọi km đều tính, ghi rõ trong ghi chú).
- Có tuyến cố định "Đà Lạt -> Sân Bay (35km)": 4 chỗ 155.000đ, 7 chỗ 255.000đ. Đây là tuyến **một chiều** Đà Lạt → Liên Khương; chiều ngược lại chưa thấy. Quan trọng vì tính theo km sẽ ra khoảng 400k.
- Gắn vào hãng `xanhsm`, vùng `lam_dong`, nhãn "Xanh SM · taxi Lado". Nguồn chứng minh quan hệ đối tác: greensm.com/vn-vi/news/trien-khai-chuoi-chuong-trinh-thuong-cho-bac-tai-xanh-tai-lam-dong (08/10/2026).

**Ranh giới tỉnh:**
- geoBoundaries gbOpen VNM ADM1 (public domain, 64 vùng, năm 2008): `https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/VNM/ADM1/geoBoundaries-VNM-ADM1.geojson`. Tải vào thư mục riêng, coi là dữ liệu chưa tin cậy.
- Cần làm sạch: "Hà Nội\t" dính tab, "Ho Chi Minh" viết tiếng Anh. Ánh xạ bằng `area_key`, kiểm đủ 64 khóa, mỗi khóa đúng một vùng. Làm tròn tọa độ 4 chữ số.
- Bờ biển đã giản lược nên một điểm sát biển có thể nằm ngoài vùng: lấy vùng gần nhất trong `snap_km` (15 km). Khu vực con kiểm bằng `box` trước.
- Điểm phải test: Đà Lạt, Liên Khương → `lam_dong`; Tân Sơn Nhất → `ho_chi_minh`; Thủ Dầu Một → `binh_duong`; Vũng Tàu; Nội Bài → `ha_noi`; Cam Ranh → `khanh_hoa`; Dương Đông → `phu_quoc`; Côn Đảo; Hội An; Sa Pa.

## 6. Thứ tự làm tiếp (gợi ý)

1. Viết lại `be.fare_of` theo §5. Test bằng HTML mẫu nhỏ, mỗi kiểu nhãn một case, kèm các số đã kiểm tay.
2. Viết `xanhsm.py`, `lado.py`, `provinces.geojson`, rồi `build.py` + CLI. Chạy build, đọc báo cáo, đối chiếu tay vài tỉnh.
3. Viết `areas.py`, sửa `rides.py` sang bảng mới:
   - Tuyến cố định: áp khi điểm đón thuộc `from` và điểm trả khớp `to` (sân bay trong `airport_km`, hoặc vùng); chiều ngược lại nếu `both_ways`. Gói `price` cho `min_km` đầu rồi cộng `per_km`; nếu không có `per_km` thì chỉ áp khi km ≤ `min_km` × 1,15.
   - Phí sân bay: chỉ ô tô, chỉ khi đón tại sân bay đó.
   - Phí nền tảng Grab: khoảng tiền trước ngày `until`, sau đó `after_pct`%.
   - API nhận thêm điểm trả: `km:phút:lat:lng[:lat2:lng2]`.
4. Gắn giá vào chặng `transfer` trong `journey.options._road` (điểm đón = tọa độ đầu, điểm trả = tọa độ cuối). Thêm dòng tổng vào thẻ trong `WayIn.tsx`; dùng hãng và loại xe người dùng đã chọn (`tg.ride.v1`), hãng đó thiếu giá thì lấy hãng rẻ nhất và ghi rõ tên hãng.
5. Cập nhật `docs/BOOKING.md` §Gọi xe, `docs/Role_Web_Functional_Design.md`, `DEV_LOG` (mục `rides-inline-fill-2026-11-17`). Chụp ảnh vào `frontend_images/` (RULE §0.2). Báo chủ dự án duyệt, rồi xin deploy.

## 7. Quy tắc vận hành không được quên

- Không build vào `web/dist` (đó là prod). Kiểm bằng `npx tsc --noEmit -p .` trong `web/`, hoặc build ra thư mục tạm bằng `--outDir`.
- Deploy chỉ khi chủ dự án bảo:
  - Code `src/`: `HARNESS_GPU=0 SKIP_CLEF=1 setsid nohup ./run.sh prod > logs/run/deploy.log 2>&1 &`.
  - Chỉ web: build vào `web/.deploy-build` theo `build_web` trong `run.sh`, rồi `cp -a` sang `web/dist`.
  - Trước khi deploy, `diff -rq src .prod_src` và tìm file web mới hơn `web/dist`. File nào không phải của mình thì hỏi các phiên khác (`ListAgents`, `SendMessage`).
- Prod đọc `config/` trực tiếp: sửa config là đổi prod ngay, phải hỏi chủ dự án trước.
- Ảnh chụp UI: Vite dev ở :5211 trỏ vào harness :8769 (bản prod, code cũ). Route mới chưa có ở đó, nên dựng payload bằng code mới qua một server tạm rồi `page.route`. Cách đăng nhập và đường dẫn Chromium nằm trong bộ nhớ `dev-login-account-in-env`.
- Test liên quan: `pytest tests/booking/test_rides.py tests/planning/test_planning_travel_output.py tests/planning/test_planning_golden.py tests/planning/test_planning_lodging_golden.py tests/trip/test_redesign_gate.py`.

## 8. Trạng thái sau phiên 17/11 chiều

Đã xong (tài liệu chính: `docs/BOOKING.md` §Gọi xe; nhật ký: `DEV_LOG` mục `rides-inline-fill-2026-11-17`):
- Bộ đọc `be.py` viết lại (mỗi dòng có giá phải được một luật đọc), `xanhsm.py`, `lado.py`, `boundaries.py`, `build.py` + `__main__.py`. `grab.URL` sửa sang bản `/vn/en/` (bộ đọc dựa vào cột "For cheaper fare" chỉ có ở bản này).
- `config/rides_tariffs.json` đã dựng: Grab 60 vùng, Be 31, Xanh SM 45 (gồm Lado ở Lâm Đồng). `config/provinces.geojson` đã dựng (64 vùng). `provinces.yaml` thêm `area` cho mỗi sân bay (Nội Bài rơi vào Vĩnh Phúc theo đường biên giản lược).
- `journey/areas.py`, `journey/rides.py` (đọc bảng mới, tuyến cố định, phí nền tảng theo ngày, phí đón sân bay, API nhận điểm trả), `journey.options(with_rides=True)` gắn `Leg.rides` vào chặng `transfer`; route web bật, Trip assistant không bật.
- Web: dòng *Cửa tới cửa* ở thẻ Máy bay / Xe khách (`WayIn.tsx` `DoorToDoor`, `rides.ts` `pickFor` / `useRideChoice`), chặng cuối tới chỗ ở đã chọn (`Plan.tsx` truyền `destLat/destLng`, `people`). Ảnh: `frontend_images/web-door-to-door-2026-11-17/`.
- Test: `tests/booking/test_rides.py` (viết lại), `tests/booking/test_tariffs.py` (mới), thêm 1 test ở `test_journey_options.py`. `tests/booking tests/harness tests/planning`: 1765 pass.

Còn mở, cần chủ dự án:
- Duyệt rồi deploy **toàn bộ** (code `src/` + web): prod hiện chạy code cũ đọc `config/rides.yaml` (đừng xóa file này trước khi deploy; xóa sau). Web build của phiên sáng ở `web/.deploy-build` đã cũ, phải build lại. Cùng cây có thay đổi của phiên khác (`MiniCalendar.tsx`, `home.css`, …): hỏi trước khi deploy.
- Quyết định: (a) Green SM Mini rẻ hơn Car nhưng trang không ghi số chỗ nên đang bỏ; (b) tuyến Lado Đà Lạt → Liên Khương là giá Lado công bố, chưa chắc đặt qua app Green SM có áp giá này; (c) trang Grab tự ghi "Quảng Trị | Quảng Bình | Tuyến đi Hà Nội 100 km" (đang giữ nguyên như trang).
- Lỗi có sẵn, không thuộc phần này: ở màn hình 390px, trang Lịch trình tràn ngang (thẻ ngày rộng 481px) và khối *Phương tiện lên Đà Lạt* chỉ rộng ~166px.
- Chưa commit gì. Repo commit tác giả `hohoangluan`, không thêm trailer co-author; chủ dự án tự push.

Sau deploy 12:28: chủ dự án chốt (2) bỏ Green SM Mini, (3) tuyến Lado giữ làm giá tham khảo. Khối CSS điện thoại cho Lịch trình đã gỡ: điện thoại chưa có thiết kế, để nguyên như cũ.
