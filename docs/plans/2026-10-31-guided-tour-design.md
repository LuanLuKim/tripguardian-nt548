# Hướng dẫn sử dụng có linh vật (Guided Tour) — thiết kế

Ngày 2026-10-31. Chủ sản phẩm yêu cầu; các chỗ đánh dấu **(quyết của người viết)** là lựa chọn của người viết, chưa được chủ sản phẩm xác nhận từng cái.

## 1. Ý định

Người mới vào TripGuardian thấy rất nhiều thứ: trang chủ, thanh bên, bốn giai đoạn của chuyến đi, hàng chục tiện ích nhỏ. Hiện chỉ có bốn thẻ chữ ở trang Hỗ trợ. Cần một bản hướng dẫn **đi cùng** người dùng qua toàn bộ hệ thống: quả sồi (mascot đang có ở màn đăng nhập) là hướng dẫn viên, đi qua đi lại trên màn hình, đứng cạnh đúng ô nó đang nói, đổi biểu cảm theo từng bước. Người dùng bấm "Tiếp" để sang bước mới. Cuối tour có pháo giấy và âm chúc mừng.

Thành công = một người chưa từng dùng app xem hết tour (khoảng 3–4 phút) và biết mỗi tiện ích nằm ở đâu và để làm gì, không phải tự dò.

## 2. Mục tiêu, không mục tiêu, chống mục tiêu

**Mục tiêu**
- Kể **đủ mọi tính năng** người dùng thấy (danh sách ở §5); không bỏ tính năng nào chỉ vì ít dùng.
- Chỉ trên **màn thật** với **dữ liệu thật** (chuyến mẫu), không vẽ lại giao diện giả.
- Người dùng chủ động: không tự chạy; có Quay lại, Bỏ qua chương, nhảy chương, thoát bất cứ lúc nào.
- Linh vật có cảm xúc rõ, di chuyển thật trên màn hình, theo đúng tính cách đang có (quả sồi, hình tạo từ ảnh tham chiếu).

**Không mục tiêu**
- Không bản điện thoại (điện thoại luôn thấy GetApp; thiết kế cho máy tính).
- Không dạy bằng video, không giọng nói, không lời thoại do model sinh: toàn bộ lời là văn bản cố định do ta viết.
- Không đo hiệu quả học (chỉ gửi sự kiện cơ bản, §8).

**Chống mục tiêu (làm xong mà vẫn coi là hỏng)**
- Tour làm hỏng hoặc để lại dữ liệu trong tài khoản người dùng (chuyến mẫu hiện trong "Chuyến của tôi", ghi vào hồ sơ, học sở thích từ chuyến mẫu).
- Tour chặn người dùng thoát; hoặc kẹt khi một ô cần chỉ không có trên màn hình.
- Lời hướng dẫn nói sai về app (nói tính năng không có, hoặc mô tả sai hành vi).
- Gọi model trong lúc tour (chậm, tốn, không ổn định).

## 3. Ràng buộc

- Luật dự án (`RULE.md`): tài liệu tiếng Việt; code, comment, identifier, tên file tiếng Anh. Online chỉ ghi lịch trình và user / session profile; Place Intelligence chỉ đọc. Module chỉ giao tiếp qua public API.
- Màu chỉ lấy từ token (`user/css/tokens.css`); accent thương hiệu `--tg-brand` #b4532a chỉ làm điểm nhấn nhỏ; nền app trắng/đen. Chỉ máy tính. Tôn trọng `prefers-reduced-motion`.
- Không thêm nút lẻ loi nổi trên trang (chủ dự án 2026-10-30): nút bắt đầu tour nằm trong bố cục có sẵn (§4.1).
- Dùng lại thành phần chủ sở hữu đã có; ảnh linh vật tạo từ ảnh tham chiếu `web/public/img/auth/acorn_mascot.png` để giữ đúng nhân vật.
- Không commit, không đẩy lên; thư mục làm việc dùng chung với nhiều phiên khác.

## 4. Quyết định đã chốt (theo lời chủ sản phẩm)

1. **Không tự chạy.** Người dùng bấm một nút mới bắt đầu.
2. **Nền tối đi, ô đang nói được chiếu sáng** (cách A trong mockup); không phải sân khấu riêng.
3. **Linh vật di chuyển trên màn hình** khi chuyển bước: đi qua đi lại đến cạnh ô cần chỉ.
4. **Có biểu cảm nhiều** theo từng bước.
5. **Phase khác dẫn sang màn thật** (Tìm hiểu, Lựa chọn, Lịch trình, Đánh giá), không dùng thẻ minh hoạ.
6. **Tour kể đủ toàn bộ tiện ích.**
7. **Âm chúc mừng** khi xong: chủ sản phẩm nhờ đề xuất; đề xuất ở §7.
8. **Ảnh linh vật mới tạo bằng sol hoặc terra** (9router `/v1/images/generations`, đổi `model` giữa `cx/gpt-6.1-sol` và `cx/gpt-6.1-terra`).
10. ~~Tour có hướng dẫn cả màn đăng nhập~~ **Bỏ (chủ sản phẩm, cùng ngày, nói sau): tour bắt đầu từ homepage trở về sau, không có chương đăng nhập, không có "chương 0", không có lối vào từ màn đăng nhập.** Ý cũ: (lời chủ sản phẩm, 2026-10-31): giải thích chính màn đăng nhập (Google, email + mật khẩu, "Dùng thử, không cần tài khoản", điều khoản, và vì sao nên có tài khoản). Cách đặt chương: §5, chương 0 (quyết của người viết).
11. **Tính năng khách bị khoá**: linh vật nói họ **đăng nhập để hưởng đầy đủ quyền lợi** (không im lặng bỏ qua, không giải thích kỹ thuật).
12. **Linh vật là đúng hình quả sồi ở màn đăng nhập** (cùng nhân vật, cùng phong cách ảnh `public/img/auth/`), **tay chỉ vào từng chỗ đang giải thích**, và **đi trên màn hình** bằng hoạt ảnh; ví dụ chủ sản phẩm đưa ra: đang đứng ở nút "Xong", nó đi sang nút "Tạo chuyến đi" rồi chỉ vào đó. **Trên đầu hiện dấu "…" như đang nói chuyện** (giống `tg-auth__dots` của `AuthMascot`) trước khi lời hiện ra.
9. **Chủ sản phẩm giao việc cân đối tối ưu** cho người viết sau khi người viết đã dùng thử app (các mục §4.1, §6 là kết quả).

### 4.1 Quyết định của người viết (đã trình, chủ sản phẩm nói "oke" cho cả khung)

- **Thanh điều khiển tối giản (chủ sản phẩm, sau bản xem thử):** chỉ "Tiếp", "Quay lại", "Bỏ qua" (thoát hẳn); đi lần lượt từng bước. Không chấm / nhãn chương, không nhảy chương, không nút tắt tiếng. Esc cũng thoát. Chương chỉ còn là cách nhóm nội dung trong `steps.ts`.
- **Bong bóng ngắn (chủ sản phẩm):** mỗi lời một ý, tối đa hai dòng; mascot cỡ lớn cho cân với khung hình (~290 px).
- **Chuyến mẫu chỉ xem** cho chương 3–6 (§6).
- **Nơi bắt đầu tour (quyết của người viết):** (a) nút "Hướng dẫn" dạng pill nhỏ có mặt linh vật, ở cuối hàng ô tìm trên trang chủ; (b) nút chính "Xem hướng dẫn cùng linh vật" trong trang Hỗ trợ, thay phần bốn thẻ chữ hiện có (bốn thẻ giữ lại như tóm tắt phía trên nút). Không có nút nổi.
- **Chặn thao tác trong tour (quyết của người viết):** lớp phủ chặn mọi bấm trên trang; chỉ nút của tour (Tiếp, Quay lại, Bỏ qua, tắt tiếng) và phím ← → Enter Esc dùng được. Người dùng không "thử bấm" giữa tour (tránh làm hỏng chuyến mẫu, tránh kẹt).
- **Cuối tour:** quay về trang họ bắt đầu; lời cuối có nút "Tạo chuyến đầu tiên" mở hộp "Kể mình nghe chuyến đi" sẵn có.
- Khách (không tài khoản) và người đã đăng nhập đều dùng được tour.

## 5. Nội dung: sáu chương

Mỗi điểm dừng = một ô thật được chiếu sáng (`data-tour="<id>"` gắn vào phần tử thật), một dáng linh vật, một câu ngắn (≤ 2 câu, giọng "TripGuardian / bạn"). Danh sách dưới là **bộ khung cần phủ hết**; người xây viết lời và có thể gộp hai điểm gần nhau, nhưng **không bỏ tính năng**. Phần tính năng lấy từ `docs/Role_Web_Functional_Design.md` §6; người xây kiểm lại từng dòng với code trước khi viết lời (chống mục tiêu: nói sai).

**Chương 0 — Đăng nhập (quyết của người viết về chỗ đặt):** một chương ngắn (~4 điểm dừng) trên màn `/app/login`: nút Google; form email + mật khẩu (đăng ký / quên mật khẩu); "Dùng thử, không cần tài khoản" (khách: không lưu lịch sử, chuyến xoá sau 24 giờ không hoạt động); điều khoản; kết bằng lợi ích có tài khoản (lưu chuyến, hồ sơ, bạn bè, thông báo, Google Calendar). Chương này chạy được ở hai nơi: (a) **người chưa đăng nhập** thấy lối "Xem hướng dẫn" ngay trên màn đăng nhập và chỉ cần chương 0 (không cần chuyến mẫu, không cần phiên); sau đó họ tự đăng nhập hoặc dùng thử, rồi có thể mở tour đầy đủ từ trang chủ; (b) **khách** mở tour đầy đủ thì chương 0 là chương đầu (khách vẫn vào được `/app/login`, giữ phiên). **Người đã đăng nhập tài khoản** không thấy chương 0 vì không có màn đăng nhập để chỉ (không đăng xuất họ giữa tour).

| # | Chương (màn) | Điểm dừng (tính năng cần nói) | Dáng gợi ý |
|---|---|---|---|
| 1 | **Trang chủ** (`/app`) | chào; ô tìm ("/" để gõ nhanh, Enter mở "Kể mình nghe chuyến đi"); thẻ lớn + số địa điểm có thật trong dữ liệu; "Gợi ý để bắt đầu" (5 chủ đề, tim để lưu, mở blog); Trending (nơi đang được nhắc nhiều, sự kiện sắp tới); lịch tháng; hồ sơ + chuông thông báo + chat bạn bè | chào (vẫy), tò mò, wow, yêu thích |
| 2 | **Thanh bên** | Chuyến của tôi (gửi cho bạn bè); Đã lưu (nơi + chủ đề); Đã xem gần đây; Cài đặt (hồ sơ, nickname, thông báo, Google Calendar); Hỗ trợ (câu hỏi nhanh, xem lại tour); nút Tạo chuyến đi | chỉ tay, nháy mắt, vẫy |
| 3 | **Tìm hiểu** (`/app/understand`) | chat kể chuyến đi; câu hỏi chọn nhanh và chọn bằng ảnh; thẻ chỗ ở; bảng tiến độ "tám nhóm thông tin"; tóm tắt "Mình đã hiểu như này"; lịch sử chat | nghĩ, tò mò, chỉ tay |
| 4 | **Lựa chọn** (`/app/explore`) | đĩa xoay / lưới; tab nhóm + ô tìm; tim chọn nơi → thanh "Đã chọn" kèm khả thi; "Xem chi tiết" (Tổng quan, Hình ảnh, Xem 360°, Gợi ý lịch trình, Đánh giá); So sánh; trợ lý chat ("/"); tab Chỗ ở; lý do hợp / cảnh báo trên thẻ | wow, chỉ tay, vui |
| 5 | **Lịch trình** (`/app/plan`) | chọn phương án; tổng quan + bản đồ; từng ngày kéo thả; đổi / thêm nơi; Đường tới / về (ô tô, xe máy, xe khách, máy bay); chi phí + chi phí chỗ nghỉ; Độ tin cậy của lịch; Trending cạnh lịch; chat sửa lịch; Chốt kế hoạch + Hoàn tác | chỉ tay, nghĩ, vui |
| 6 | **Sau khi chốt** (`/app/done`, Hôm nay) | phản hồi sau chuyến; Hôm nay / nhắc đêm trước / thông báo / Google Calendar; **kết**: nhảy mừng + pháo giấy + âm + nút "Tạo chuyến đầu tiên" | thư, vui, nhảy mừng |

(Ước ~36 điểm dừng, ~3–4 phút. Con số không phải ràng buộc; độ phủ tính năng mới là ràng buộc.)

## 6. Chuyến mẫu (quyết của người viết)

Vấn đề: người mới chưa có chuyến; Lựa chọn và Lịch trình cần dữ liệu từ model (vài phút) nên không thể "tạo trong lúc tour".

Quyết định: một **chuyến mẫu cố định** (Đà Lạt, 3 ngày, 2 người, đầy đủ cả ba giai đoạn), dựng **một lần ngoại tuyến** từ dữ liệu corpus thật và lưu thành fixture trong repo. Khi bắt đầu chương 3, hệ thống tạo cho người dùng một journey tạm từ fixture đó (không gọi model) để các màn thật đọc như mọi journey khác.

Yêu cầu hành vi (cách làm cụ thể do người xây quyết):
- Journey tạm **không hiện** trong "Chuyến của tôi", Đã xem gần đây, thông báo; **không** được dùng để học hồ sơ / sở thích (User Profile là prior, chuyến mẫu không phải ý người dùng); **bị xoá** khi tour kết thúc hoặc bị thoát. Cách giữ (quyết của người viết): **trong bộ nhớ máy chủ, theo phiên, có hạn dùng (TTL)**, không ghi xuống kho journey thật; nên không cần job dọn nền riêng, hết hạn là mất. Đây là một lớp **đọc-chỉ tách biệt**, không phải cờ `tour` rải qua nhiều route thật: mục tiêu là chạm ít nhất vào harness, tài khoản, thư viện, học hồ sơ và bộ gửi thông báo (`RULE.md` §4 thay đổi tối thiểu).
- Chỉ đọc: mọi thao tác ghi (chọn nơi, kéo thả, chốt) bị khoá ở phía máy chủ cho journey này, không chỉ ở lớp phủ giao diện (Hard constraint fail-closed).
- Không bịa địa điểm: fixture chỉ chứa nơi có thật trong corpus; dữ liệu cũ phải phát hiện được (đã có cơ chế `stale_data_version` 409) và có lệnh dựng lại fixture.
- Nếu người dùng **đang có chuyến dở**, tour không đụng tới chuyến đó (không thay thế, không đổi chuyến đang mở trong `TripProvider`); sau tour quay về đúng trạng thái trước.
- Nếu không dựng được journey mẫu (lỗi mạng, harness lỗi): các chương 1–2 vẫn chạy; chương 3–6 hiện một lời xin lỗi ngắn của linh vật (dáng buồn) và nút "Bỏ qua tới phần kết".

### 6.1 Làm rõ sau khi người xây đọc thử (đều là quyết của người viết)

- **Hình dạng chuyến mẫu: mỗi chương một trạng thái cố định**, vì lớp phủ chặn thao tác nên người dùng không thể tự đi tới các trạng thái đó. Chương 3: có sẵn đoạn chat đã hỏi–đáp và bảng tiến độ đầy. Chương 4: đã chọn sẵn một số nơi (đủ để thanh "Đã chọn" và nút sang Lịch trình hiện). Chương 5: lịch đã chọn phương án, **chưa chốt** (để thấy Chốt kế hoạch và Hoàn tác). Chương 6: lịch **đã chốt** (để `/app/done` và Hôm nay có nội dung). Chat / trợ lý ở Lựa chọn và Lịch trình: linh vật chỉ vào khung chat và nói nó làm gì, **không** có câu trả lời mẫu.
- **Cổng "đủ nơi mới sang Lịch trình"**: chuyến mẫu thoả cổng bằng các nơi đã chọn sẵn; cổng không bị nới cho ai khác.
- **Chuyến đang dở của người dùng**: tour chạy trên một trạng thái chuyến **riêng** (provider lồng hoặc `journey` theo route, người xây chọn), không bao giờ ghi vào `TripProvider` của chuyến thật; thoát tour là còn nguyên chuyến cũ.
- **Khách**: Hôm nay, thông báo, Google Calendar, hồ sơ (nickname) bị khoá với khách. Với khách, các điểm dừng đó **không dẫn sang màn bị khoá**: linh vật chỉ vào chỗ vào (nếu hiện) và nói điều có được khi có tài khoản, kết bằng lời mời **đăng nhập để hưởng đầy đủ quyền lợi** (dáng yêu thích / vẫy, không phải dáng buồn; giọng mời, không giọng cấm). Lời mời này dùng đúng một câu mẫu chung để mọi chỗ nhất quán. Test `data-tour` chạy hai chế độ: đã đăng nhập và khách.
- **Tải lại trang giữa tour**: tour nhớ chương và bước ở `sessionStorage` (bọc try/catch); tải lại thì dựng lại chuyến mẫu (rẻ, không gọi model) và tiếp tục ở **đầu chương đang dở**. Nếu không đọc được thì bắt đầu lại từ chương 1.
- **Âm và pháo giấy chỉ chạy khi bấm "Xong" ở bước kết.** Thoát bằng Esc / Bỏ qua thì im và không pháo.

## 7. Linh vật: ảnh, chuyển động, âm thanh

**Hình dạng (đã chốt).** Linh vật tour là **chính quả sồi ở màn đăng nhập**: cùng nhân vật, cùng nét, tạo từ cùng ảnh tham chiếu; không vẽ nhân vật mới. Cần dùng lại cách trình bày của `AuthMascot.tsx` / `auth.css` (khung `tg-auth__pet`, bóng đất, cross-fade các dáng, bong bóng `tg-auth__say`, chấm `tg-auth__dots`) càng nhiều càng tốt; không viết lại.

**Tay chỉ.** Dáng `point` (một tay giơ chỉ sang bên; lật ngang để chỉ sang trái) và `point_up` (chỉ lên trên) cho ô nằm cao hơn nó; linh vật luôn đứng sao cho tay chỉ hướng về ô, không che ô. Ô nằm ngay phía dưới thì nó đứng bên cạnh và chỉ chéo xuống bằng `point` (không cần thêm dáng).

**Đang nói.** Mỗi lần tới một điểm dừng: dáng của bước hiện, **trên đầu hiện bong bóng "…" (ba chấm nhảy) ~600–800 ms**, rồi bong bóng đổi sang lời (lời hiện cả cụm, không gõ từng chữ). Bước Tiếp: bong bóng thu lại, linh vật đi, tới nơi lại "…" rồi lời. Dấu "…" cũng hiện lúc đang chờ trang mới dựng.

**Ảnh (mới).** Script mới `web/scripts/gen_tour_mascot.py` theo mẫu `gen_mascot_moods.py` (cùng ảnh tham chiếu, nền trong suốt, 720 px, `webp`, ghi `manifest.json`, bỏ qua file đã có trừ `--force`). Dáng mới tối thiểu: `walk_a`, `walk_b` (hai khung bước, quay mặt phải; hướng trái = lật ngang bằng CSS), `point` và `point_up` (chỉ tay), `wave` (vẫy), `wow`, `wink`, `love`, `cheer` (nhảy mừng giơ hai tay, pháo giấy nhỏ), `bow` (cúi chào cảm ơn). Dùng lại sẵn: `curious`, `wait` (nghĩ), `happy`, `shy`, `mail`, `sad` (lỗi chuyến mẫu). Model mặc định sol (đã kiểm chứng giữ nhân vật); **thử terra trên một dáng trước** và dùng terra nếu giữ nhân vật tốt như sol. Kiểm tra bằng mắt từng ảnh trước khi dùng; dáng nào lệch nhân vật thì tạo lại.

**Chuyển động.** Linh vật là một phần tử cố định, `transform` dịch tới vị trí cạnh ô được chiếu sáng (chọn phía còn chỗ; không che ô đang chỉ; bong bóng nói nằm trên phía đối diện). Khi đang đi: luân phiên `walk_a` / `walk_b` mỗi ~180 ms, quay mặt theo hướng đi, bóng đất co giãn; tới nơi thì chuyển sang dáng của bước (cross-fade như `AuthMascot`). Thời gian đi ~600–800 ms. Mục tiêu hiệu năng: chỉ `transform` / `opacity`. `prefers-reduced-motion`: không đi, chỉ mờ chuyển vị trí; không pháo giấy.

**Ô không có / chưa tải.** Nếu `data-tour` của bước không tìm thấy trong ~1,5 s (dữ liệu chưa tải, ô bị ẩn vì thiếu dữ liệu), linh vật đứng giữa màn, nói bằng lời không chỉ tay, bước vẫn tính là đã đi. Không bao giờ kẹt, không bao giờ báo lỗi cho người dùng.

**Âm chúc mừng (đề xuất, quyết của người viết).** Sinh bằng Web Audio, không dùng file âm thanh: bốn nốt đi lên C5–E5–G5–C6 (~90 ms mỗi nốt, sóng sin + chút tam giác), kèm một tiếng lấp lánh cao ở cuối, tổng ~1,2 giây, âm lượng nhỏ (gain ≤ 0,15). Phát khi người dùng bấm "Xong" ở bước kết (có thao tác của người dùng nên trình duyệt cho phát). Nút tắt tiếng trong thanh điều khiển của tour, lưu lựa chọn ở `localStorage` (bọc try/catch; thiếu thì mặc định bật). *Khác với lời nói trước đó trong cuộc trao đổi:* âm **không** tự tắt khi bật giảm chuyển động (giảm chuyển động nói về hình, không phải tiếng); chỉ pháo giấy tắt.

## 8. Kiến trúc giao diện (gợi ý, người xây có thể đổi nếu giữ được hành vi)

- Module mới `web/src/user/tour/` (public API qua `index.ts`): `TourProvider` đặt **trên** `Shell` để sống qua các lần đổi trang; `Tour.tsx` (lớp phủ + linh vật + bong bóng + thanh điều khiển); `steps.ts` (dữ liệu: id, chương, route, target, dáng, lời); `sound.ts`; `mascot` (chọn khung, hướng, đường đi); CSS `user/css/tour.css`.
- Chuyển trang giữa các chương dùng `navigate` của `router.ts` (có View Transitions); tour chờ trang mới dựng xong (target xuất hiện hoặc hết 1,5 s) rồi mới cho linh vật đi.
- Gắn `data-tour="…"` vào phần tử thật ở các màn (Discover, Frame, Understand, Explore, PlaceSheet, Plan, Done, Support, Who…). Một test đối chiếu danh sách `steps.ts` với các `data-tour` thật trên chuyến mẫu, để đổi giao diện mà làm hụt một điểm dừng thì test báo.
- Sự kiện (qua `user/events.ts`): `tour_start`, `tour_step` (id), `tour_skip` (chương hoặc cả tour, bước nào), `tour_done`.
- Truy cập: lớp phủ là hộp thoại có tiêu điểm bị giữ, bong bóng dùng `aria-live=polite`, phím ← → Enter Esc, nút có nhãn, ô chiếu sáng không phụ thuộc màu.

## 9. Chấp nhận

1. Bấm "Hướng dẫn" ở trang chủ → linh vật đi tới ô tìm, nói, nền tối đi chỉ chừa ô tìm sáng; Tiếp → nó đi sang ô kế tiếp, đổi biểu cảm.
1b. Ở điểm dừng nút "Xong" (hoặc điểm tương đương trong bước bấm "Tiếp"), linh vật đi sang nút "Tạo chuyến đi", tay chỉ vào đó, trên đầu hiện "…" rồi mới hiện lời.
1c. Người chưa đăng nhập mở màn đăng nhập, bấm "Xem hướng dẫn": linh vật giải thích Google / email / dùng thử / điều khoản / lợi ích có tài khoản; không có yêu cầu nào tới chuyến mẫu.
1d. Khách đi tới tính năng bị khoá: nghe lời mời "đăng nhập để hưởng đầy đủ quyền lợi", không bị đẩy sang màn bị khoá.
2. Đi hết các chương (0–6 tuỳ loại người dùng) trên máy tính 1440×900 và 1280×720 mà không có chỗ nào linh vật che ô đang chỉ, không cuộn ngang, không lỗi console.
3. Ở chương 3–6 mọi màn là màn thật của chuyến mẫu; không một yêu cầu nào tới model; không ghi gì vào hồ sơ hay "Chuyến của tôi"; thoát giữa chừng thì không còn journey mẫu nào của người dùng đó.
4. Người đang có chuyến dở: sau tour vẫn đúng chuyến đó, đúng bước đó.
5. Bước kết: nhảy mừng, pháo giấy, âm phát một lần; tắt tiếng thì im; giảm chuyển động thì không pháo, không đi.
6. Mỗi điểm dừng của §5 có trong `steps.ts`; test đối chiếu `data-tour` qua.
7. Cập nhật tài liệu cùng lúc: `docs/Role_Web_Functional_Design.md` §6 (màn nào ở file nào), `docs/UI_SPEC_USER_WEB.md`, trang Hỗ trợ, `docs/log/DEV_LOG.md`.

## 10. Để người xây quyết

- Cách dựng journey tạm từ fixture (endpoint harness mới, hay cơ chế nạp journey có sẵn), cách khoá ghi cho nó, cách dọn nền; miễn đạt §6.
- Cách vẽ lớp chiếu sáng (cắt lỗ bằng `box-shadow` / SVG mask / clip-path), cách đo vị trí khi trang cuộn; miễn đạt §9.
- Văn phong từng câu (giữ giọng "TripGuardian / bạn", ngắn, không giọng AI hay giọng biểu mẫu), số điểm dừng thật sự.
- Chọn dáng cụ thể cho từng điểm dừng trong phạm vi bộ ảnh §7.
