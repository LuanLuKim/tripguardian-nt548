# Bàn giao: web user, 3D, trang Lịch trình (2026-11-11)

Việc phiên này đã code nhưng **chưa kiểm bằng giao diện thật**, và việc chưa làm. Phiên sau ưu tiên kiểm hoạt động trên trình duyệt, sau đó mới làm tiếp. Chưa commit, chưa deploy (hỏi chủ dự án trước khi deploy). Cây làm việc đang có thay đổi chưa commit ở `web/`, `src/`, `tests/`, `docs/`, `scripts/diorama/`.

## 1. Đã chạy test, đạt

- `tests/trip` + `tests/harness`: 1951 đạt, 3 bỏ qua, 4 không chạy. Chạy bằng `PYTHONPATH=src .venv/bin/python -m pytest tests/trip tests/harness -q` (python hệ thống là 3.8, không dùng được).
- `npx tsc -b --noEmit` trong `web/` sạch; `node web/src/user/journey.test.mjs` đạt.
- 3D: `SPACE3D_GL=gpu node web/scripts/test_space3d_scroll.mjs http://127.0.0.1:<cổng> <slug>` đạt với `hoxuanhuong`, `linhson`, `conga` (`conga` từng fail một lần do thời gian, chạy lại đạt). Phục vụ tĩnh bằng `python3 -m http.server <cổng>` trong `web/public`.

## 2. Đã làm, cần người kiểm bằng giao diện thật

### 2.1 Trang Lịch trình (`web/src/user/screens/plan/`, `ui/TimePick.tsx`)

Chưa mở trên trình duyệt với harness thật. Cần kiểm từng mục:

1. **Giờ trong chuyến** (`EveBanner.tsx`, `EveTimes`; chỉ thành viên, kế hoạch đã chốt): bốn ô *Đến / Đi chơi / Về nghỉ / Rời đi* (hai ô giữa chỉ khi chuyến nhiều ngày). Bảng chọn giờ `TimePick` (Radix Popover, lưới 24 giờ + :00 :15 :30 :45): kiểm vị trí popover, đóng bằng *Xong* / Esc, bàn phím, màn hẹp, dark mode nếu có. Bấm *Lưu giờ* phải gọi `POST …/eve` `operation: times` với đúng khóa `arrive` / `leave` / `start` / `end`. `Today.tsx` vẫn chỉ truyền `arrive` / `leave` (hai ô).
2. **Backend `Harness.trip_times`** (`src/harness/dispatch.py`): thêm `start` / `end` (giờ ra ngoài, giờ về nghỉ mỗi ngày; ngày đầu không bắt đầu trước giờ đến, ngày cuối không kết thúc sau giờ rời đi). **Chưa có test riêng** (cần một Planning session đã chốt để dựng; xem `tests/harness/test_dispatch.py` `make()`). Cần: test cho 1 ngày và nhiều ngày, giờ không hợp lệ (`begin >= end` phải báo `ValueError`), và kiểm xem `set_day_window` của Planning chấp nhận đủ các cửa sổ này; sau khi đổi, `days[i].window` của lịch phải đổi đúng.
3. **Đường tới Đà Lạt** (`src/trip/domain/required.py` `arrival_tab`, `deck.py` nhánh `at == "plan"`): hàng *Đường tới Đà Lạt* trong `Overview` (prop `arrivalFill`), nút *Chọn* mở `FillSheet` (`GateAsk`). Chọn *Tự đi, xe máy / ô tô* ghi luôn `mobility`; chọn *Máy bay / Xe khách* thì hàng *Phương tiện* mới hiện. Test backend `tests/trip/test_redesign_gate.py` đạt, nhưng **chưa kiểm giao diện**: thẻ `rental` (gợi ý điểm thuê xe) của câu *Phương tiện* trong `FillSheet`/`GateAsk` có hiển thị đúng không; sau khi trả lời, lịch dựng lại (`advance`) và hàng mới có hiện đúng thứ tự không. Chủ dự án muốn "điểm xuất phát" (từ nhà) nằm sau đường tới Đà Lạt: hiện `WayIn` vẫn nằm dưới hàng chọn, cần nhìn lại thứ tự thực tế.
4. **Chỗ nghỉ dạng ghost** (`parts.tsx` `LodgingGhost`, `Overview` prop `lodgingGhost`): quạt thẻ cùng kiểu `GhostSlot`, "+" chọn bằng `pick_lodging`. Đã bỏ `NoHotel` khỏi `Plan.tsx` (vẫn dùng ở `Choose.tsx`). Cần kiểm: ảnh, nhãn, trạng thái `pending` / rỗng, chọn xong thì thẻ biến mất và hàng hiện chỗ đã chọn + `StayOffer`.

### 2.2 Web user

- **Đã lưu** (`Account.tsx` `Saved`, `css/home.css`): thẻ `tg-rc` như Đã xem gần đây, không nhóm theo ngày; hai nút tròn rê vào mới hiện (thêm vào chuyến, xóa khỏi yêu thích). Cần xem bằng mắt (nhãn loại góc trái, sao góc phải, nút trên thiết bị cảm ứng, tab nhóm vẫn lọc đúng) và bấm thẻ phải mở tờ chi tiết, không nhảy sang trang `/explore/place/…`. CSS `.tg-sv*` cũ trong `screens.css` giờ không dùng, có thể dọn.
- **Nút Lập lịch** (`journey.ts` `stageReady`): journey còn ở bước `trip` mà người dùng đang ở Chọn nơi thì tự `advance` rồi đi tiếp, không còn lỗi *Advance this journey explicitly first*. Chưa tái hiện bằng trình duyệt thật. Kịch bản: Sửa trong Tìm hiểu → dùng thanh bên sang Chọn nơi → Lập lịch. Kiểm cả trường hợp thiếu ngày đi (phải ra hộp thoại bổ sung, không văng toast lỗi).
- **Hộp tóm tắt chuyến** (`ReadbackSheet.tsx` `TripSummary`, `css/gate.css`): khi không thiếu gì thì hiện các dòng `Readback.lines` (Bạn nói / Mình đoán / Mặc định / Cần xem lại). Dựng lại từ bản cũ trong git, chưa xem màn hình thật; cần kiểm khi `lines` rỗng, nhiều dòng (cuộn), màn hẹp.
- **Xóa chuyến cũ** (`session.py` / `pgstore.py` `release`, `dispatch.py` `discard`): không còn nạp lại journey khi xóa. Test `tests/harness` đạt (cả bản file và Postgres). Chưa thử trên dữ liệu prod thật; sau khi deploy, thử xóa lại các chuyến cũ báo "Chưa xóa được".

### 2.3 Mô hình 3D (`scripts/diorama/index.template.html`, `web/space3d/scroll.js`, `web/scripts/build_space3d.mjs`)

- **Đường dẫn tự dựng** (`buildGuide`): nơi chưa có `place.route` tự có mũi tên và đi bộ góc nhìn người. Nơi có route tay nhưng thiếu `walk` (`camtucau`, `linhan`, `yersin`) lấy `walk` từ đầu mỗi chặng. Chỉ xem ảnh `hoxuanhuong`; `mazebar` và `camtucau` chỉ chạy không lỗi trang, **chưa xem ảnh**. Cần chạy qua cả 107 nơi (`/tmp/.../walk.mjs` là mẫu: nạp, bấm *Bắt đầu tham quan*, cuộn, chụp) và xem: đường có xuyên nước / nhà / cây không, mũi tên có bị chôn dưới mặt đất không (hiện mũi tên trên Hồ Xuân Hương còn nhỏ, đoạn kè đá chưa đẹp), nơi địa hình dốc, nơi có `interior` (`mazebar`, `tiemnuongtrong`).
  - Điều chỉnh nếu cần: `S` (kích thước ô), `clipY` (cao hơn neo 2,4 m), trọng số `cost` (nước +14, vật cao +8, bậc +8), độ nâng mũi tên, bề rộng (`carrierWidth` dùng ngưỡng 0,15 khi `place.guided`).
  - Giới hạn đã biết: chỉ dựng cho nơi không có `walk`, không `interior`; hai nơi có `interior` hiện bay như cũ nếu không nối được.
- **Nhìn quanh khi đi** (`scroll.js`, patch `freeLook` trong `build_space3d.mjs`): trong lúc đi bộ, OrbitControls tắt và kéo chuột xoay đầu (yaw không giới hạn, pitch ±1,2 rad), đi xong thì ánh nhìn về lại khung của điểm dừng. Thử bằng kéo chuột giữa chặng thấy camera không nhảy tới đích. Cần kiểm: cảm giác mượt, trên màn cảm ứng, kéo khi cuộn chuột đang scrub, kéo rồi nhả giữa chặng, `prefers-reduced-motion`.
- `web/public/space3d` đã build lại (`viewer-<hash>.js` mới). Build lại bằng `node web/scripts/build_space3d.mjs` sau mỗi lần sửa template; mỗi bản build đổi tên file viewer nên commit kèm việc xóa file cũ.

## 3. Chưa làm

- **Ô search** ("Bạn muốn đi đâu, làm gì?"): chủ dự án muốn hướng blog theo địa điểm. Mỗi nơi là một trang blog có bình luận và bài đăng của người dùng; gom bài theo chủ đề ("săn mây", "quán cà phê view đồi") thành trang như blog; ô search tìm trong nơi + bài viết, không nhồi nhiều loại kết quả; cần tính cả bạn bè chia sẻ bài. Chưa có thiết kế hay code: cần brainstorm + spec trước (dữ liệu bài đăng, kiểm duyệt, quyền riêng tư, ảnh).
- **Điểm xuất phát / đường tới Đà Lạt**: thứ tự `WayIn` vs hàng chọn (xem 2.1 mục 3). Điểm xuất phát chỉ là nhà để ước giờ; trong chuyến mỗi ngày bắt đầu ở chỗ ở.
- **3D**: chưa có chuyển động nối khi bấm điểm không kề nhau (vẫn bay). Chưa kiểm hiệu năng của `buildGuide` trên máy yếu (hai lượt chụp ô lưới ~350×240 lúc nạp).

## 4. Tài liệu đã cập nhật phiên này

`docs/Role_Web_Functional_Design.md` (§6: Đã lưu, đường dẫn 3D tự dựng), `docs/UI_SPEC_USER_WEB.md` (hộp tóm tắt chuyến, Đến Đà Lạt, Chỗ nghỉ, Giờ trong chuyến). Phiên sau nhớ sửa lại nếu giao diện thật khác mô tả; `docs/log/DEV_LOG.md` chưa ghi gì cho phiên này.
