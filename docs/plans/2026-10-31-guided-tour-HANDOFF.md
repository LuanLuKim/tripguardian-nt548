# Bàn giao: hướng dẫn có linh vật (Guided Tour)

Ngày 2026-10-31. Người nhận: session làm tiếp. Đọc file này trước, rồi `docs/superpowers/specs/2026-10-31-guided-tour-design.md` (thiết kế, đã được chủ sản phẩm duyệt, nhưng xem "Quyết định đã đổi" bên dưới vì vài chỗ trong spec đã bị chủ sản phẩm đổi sau) và `docs/superpowers/plans/2026-10-31-guided-tour-demo.md` (kế hoạch đợt 1).

## 1. Đã xong (đợt 1, chạy được, chưa triển khai lên trang thật)

Quả sồi (linh vật ở màn đăng nhập) dẫn người dùng đi một vòng: nền tối đi, ô đang nói sáng lên, linh vật đi tới cạnh ô đó, chỉ tay, hiện "…" rồi mới hiện lời, bấm Tiếp để đi tiếp. Cuối tour: nhảy mừng + pháo giấy + âm "ting", rồi đi chỉ nút "Tạo chuyến đi".

- **Tự chạy lần đầu** ở homepage (~1,2 giây sau khi vào), không cần bấm. Nhớ "đã xem" theo tài khoản trong `localStorage` khóa `tg-tour-seen:<account.id>`, ghi ngay lúc bắt đầu (tải lại giữa tour không chạy lại). Mỗi khách là một định danh mới nên khách nào cũng thấy.
- **Xem lại:** nút "Xem lại hướng dẫn" trong Cài đặt (`screens/Account.tsx`, và `GuestProfile` trong `screens/Guest.tsx`) và nút trong trang Hỗ trợ. **Không** có nút ở homepage (chủ sản phẩm bảo bỏ).
- **Chương và điểm dừng** (`web/src/user/tour/steps.ts`): Trang chủ (chào, ô tìm, thẻ lớn, chủ đề, Trending, lịch, hồ sơ) → Thanh bên (mỗi bước **mở đúng trang thật**: `/app/trips`, `/saved`, `/recent`, `/profile`, `/support`, chỉ vào `data-tour="page-head"`) → "Một chuyến đi" (4 câu đứng ở homepage, **chỗ tạm**) → Kết (`end` nhảy mừng + âm; `start` chỉ `new-trip`).
- **Khách:** `Step.guestSay` thay lời cho khách ở chỗ cần tài khoản, kết bằng "Đăng nhập để hưởng đầy đủ quyền lợi nhé!".
- **Thanh điều khiển:** chỉ "Bỏ qua" / "Quay lại" / "Tiếp" (Esc thoát, ← → đi). Không chấm chương, không nút tắt tiếng (chủ sản phẩm bảo gọn).
- **Mượt:** lớp tối dịch bằng `transform` (không làm động `box-shadow` 100vmax), bỏ `drop-shadow` trên ảnh linh vật. Đo bằng `.superpowers/brainstorm/2578419-1793408022/fps.mjs`: trang yên và lúc đứng 60 khung/giây, lúc đi rớt vài khung lẻ (trình duyệt kiểm tra chạy CPU).

### Tệp
Mới: `web/src/user/tour/{steps.ts,place.ts,sound.ts,TourProvider.tsx,Tour.tsx,TourButton.tsx,index.ts}`, `web/src/user/css/tour.css`, `web/scripts/gen_tour_mascot.py`, `web/scripts/test_tour_place.mjs`, `web/vite.preview.config.ts`, `web/public/img/tour/*.webp` (10 dáng + `manifest.json`), hai tài liệu spec / plan và file này.
Sửa: `web/src/user/UserApp.tsx` (bọc `Shell` bằng `TourProvider`, import css), `screens/Discover.tsx`, `home/{Frame,Who,MiniCalendar,Pulse}.tsx` (chỉ thêm `data-tour`), `screens/{Account,Guest,Recent,Support}.tsx` (`data-tour="page-head"` + nút xem lại).
`screens/Auth.tsx`: đã thử rồi gỡ hết (không còn gì của tour); kiểm `git diff` để chắc chắn.

### Kiểm tra
- `cd web && node scripts/test_tour_place.mjs` (6 kiểm tra chỗ đứng của linh vật quanh ô, gồm bong bóng): đang qua.
- `cd web && npx tsc --noEmit -p .`: đang sạch.
- Chạy cả tour bằng trình duyệt thật + quay video: `.superpowers/brainstorm/2578419-1793408022/run-tour.mjs <url> guest` (thư mục `.superpowers/` bị gitignore, là đồ tạm). Cần `PLAYWRIGHT_BROWSERS_PATH=$PWD/.cache/ms-playwright DBUS_SESSION_BUS_ADDRESS=disabled:` và Chromium đầy đủ `chromium-1169` (xem bộ nhớ `playwright-on-gpu156`).

## 2. Cách xem thử (đừng build vào `web/dist`, đừng khởi động lại prod)

Chủ sản phẩm xem qua ssh port-forward nên **liên kết LAN (192.168.20.x) không dùng được**; luôn đưa địa chỉ dạng `http://localhost:<cổng>`.

- App: `cd web && npx vite --config vite.preview.config.ts --port 5428 --strictPort --host 0.0.0.0` (đang chạy; nhật ký `logs/vite_tour_5428.log`; tắt: lấy pid từ `ss -ltnp | grep :5428`). Cấu hình này giữ nguyên `Host` của trình duyệt khi proxy tới harness; vite thường đổi Host nên harness trả 403 `cross-origin request refused` cho mọi POST. Phải mở bằng `localhost` (cookie phiên có `Secure`, trình duyệt chỉ nhận qua https hoặc localhost). Vào `http://localhost:5428/app/login` → "Dùng thử, không cần tài khoản" → tour tự chạy.
- Vite trên thư mục NFS **không thấy sửa file**: sau mỗi lần sửa hãy tắt và chạy lại vite của mình.
- Trang xem ảnh/video của superpowers (cổng 49671) chỉ phục vụ file **nằm phẳng** trong thư mục nội dung, không có mime cho `.webm` / `.webp`; video phải nhúng base64 (xem `content/tour-demo-2.html`).

## 3. Quyết định đã đổi sau spec (chủ sản phẩm nói; spec đã ghi chú một phần)

1. Không có chương đăng nhập; tour bắt đầu từ homepage.
2. Tự chạy lần đầu cho mọi người (spec cũ nói "không tự chạy"); nút xem lại ở Cài đặt, không ở homepage.
3. Thanh điều khiển tối giản; bỏ nút tắt tiếng; bỏ nhảy chương.
4. Bong bóng cực ngắn (một ý, tối đa hai dòng); linh vật to (~290 px thiết kế, nhân 0,825 vì app vẽ ở 82,5%).
5. **Phải dẫn sang màn thật cho cả các bước của chuyến đi**, vì nếu chỉ đứng ở homepage thì người dùng không hình dung được luồng hệ thống.

## 4. Việc còn lại: đợt 2 — chuyến mẫu và các màn Tìm hiểu / Lựa chọn / Lịch trình / Đánh giá

Thay chương "Một chuyến đi" (bốn câu tạm) bằng các bước có `route` + `target` trên màn thật. Điều kiện (spec §6, §6.1, đã được duyệt):

- **Chuyến mẫu:** nhân bản một chuyến Đà Lạt **thật, hoàn chỉnh** thành một journey tạm cho người xem. Journey là một dòng `envelope` JSON trong bảng `journeys` (`src/harness/pgstore.py`, `contracts.Journey`; API `/api/harness/sessions` ở `src/harness/server.py`, `dispatch.py`). Hướng gợi ý: xuất envelope của một chuyến đã chốt thành fixture trong repo, thêm một thao tác máy chủ tạo bản sao cho `owner` hiện tại.
- **Không gây hại:** không hiện trong "Chuyến của tôi", Đã xem gần đây, thông báo; không dùng để học hồ sơ / sở thích; chỉ đọc (chặn ghi **phía máy chủ**, không chỉ lớp phủ); tự hết hạn (TTL) và bị xóa khi tour kết thúc; không đụng chuyến đang dở của người dùng (không thay chuyến đang mở trong `TripProvider`); không gọi model.
- **Trạng thái mỗi chương:** Tìm hiểu có đoạn chat đã hỏi–đáp; Lựa chọn có sẵn vài nơi đã chọn (đủ cổng sang Lịch trình); Lịch trình đã chọn phương án, chưa chốt (thấy Chốt và Hoàn tác); Đánh giá/Done có lịch đã chốt. Chat / trợ lý chỉ chỉ vào, không có trả lời mẫu.
- **Khách:** vẫn xem được; tính năng cần tài khoản thì mời đăng nhập (không dẫn sang màn bị khóa).
- **Dữ liệu cũ:** corpus pin vào một phiên bản; đã có `409 stale_data_version`; cần lệnh dựng lại fixture.
- **Ngoài ra:** `data-tour` cho các ô của các màn đó, test đối chiếu `steps.ts` với `data-tour` thật trên chuyến mẫu (hai chế độ: có tài khoản và khách); thêm tên sự kiện `tour_start|tour_step|tour_skip|tour_done` vào allowlist ở `src/analytics` rồi mới gửi qua `user/events.ts`.
- Khi triển khai: cần khởi động lại harness; đọc bộ nhớ `prod-deploy-runbook` và `prod-runs-from-shared-tree` trước, **chỉ triển khai khi chủ sản phẩm yêu cầu**.

## 5. Điểm cần biết / chưa kiểm

- Lỗi chủ sản phẩm báo "click không qua bước tiếp theo": **chưa tái hiện được** (click chuột thật qua cả các trang đều chạy). Nếu còn, hỏi họ đang ở bước nào và bấm nút nào.
- Âm "ting" chưa nghe thật (trình duyệt kiểm tra không phát tiếng); logic Web Audio chạy không lỗi.
- Bước "Trending": nếu bản tin xu hướng chưa có thì khối "Top xu hướng" không có `data-tour="trending"` → linh vật đứng giữa màn và nói không chỉ tay (hành vi mặc định khi không thấy ô sau ~1,5 s).
- Có `data-tour="nav-…"` trên các mục thanh bên nhưng hiện không bước nào dùng (đã chuyển sang mở trang thật); giữ cũng được, xóa cũng được.
- Không commit gì; thư mục làm việc dùng chung nhiều session. Ảnh sinh bằng 9router (`cx/gpt-6.1-terra` cho `wave`, `cx/gpt-6.1-sol` cho các dáng còn lại); 9router phải đang chạy ở :20128 nếu cần tạo thêm.
- Ghi nhớ của tôi về chủ đề này: `~/.claude/projects/-workingspace-aiclub-WorkingSpace-Personal-vannk-tripguardian/memory/guided-tour-mascot.md`.
