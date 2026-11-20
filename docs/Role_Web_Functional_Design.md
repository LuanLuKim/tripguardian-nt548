# TripGuardian — Thiết kế chức năng Web

Tài liệu này nói **mỗi vai trò được làm gì và mỗi màn hình phải cho làm gì, hiển thị gì**. Không bàn vì sao (xem `docs/Project_Context.md`), luồng hệ thống phía sau (xem `docs/ARCHITECTURE.md`), cách thiết kế giao diện (xem `docs/UX_Design_Brief.md`), hay đặc tả trang cho designer (xem `docs/UI_SPEC_USER_WEB.md`).

Màn nào nằm ở file nào và gọi backend nào: §6.

---

## 1. Bề mặt và vai trò

```text
LANDING      giải thích vấn đề, một CTA → User Web          /          (public)
USER WEB     lên kế hoạch, quyết định, đi cùng trong chuyến    /app       (tài khoản Google hoặc khách)
ADMIN WEB    nội bộ: duyệt dữ liệu bị đánh dấu, theo dõi       /admin
             phiên, chất lượng, hệ thống
```

Chỉ có hai vai trò: **User** (người lên kế hoạch chuyến đi) và **Admin** (đội vận hành). MVP không cần Super Admin, Moderator, Data Manager, hay Analyst.

### Quyền của User

| Nhóm | Được phép |
|---|---|
| Chuyến đi | Tạo, xem, sửa chuyến đi của mình |
| Sở thích, constraint, anchor | Thêm, sửa; khóa hoặc bỏ nơi bắt buộc đến |
| User Profile | Cấp hoặc thu hồi nguồn dữ liệu; xem, sửa, đặt lại profile của mình |
| Địa điểm | Nhập địa điểm đã lưu; xem gợi ý và bằng chứng; so sánh; thêm, bỏ, khóa, thay |
| Kế hoạch | Xem cảnh báo, xung đột, phương án dự phòng; tạo và sửa lịch trình |
| Phản hồi | Gửi phản hồi; báo thông tin địa điểm sai |
| Trong chuyến | Check-in tự nguyện, bỏ qua, đánh giá Hợp / Không hợp; xuất lịch ra Google Calendar (luôn xem trước rồi xác nhận); bật / tắt thông báo |
| Tài khoản | Sửa hồ sơ, đổi avatar, xóa tài khoản (`docs/ACCOUNTS.md`) |

User **không** được: sửa dữ liệu nguồn của địa điểm, sửa bằng chứng hay confidence, xem dữ liệu của người khác, vào Admin Web.

### Quyền của Admin

| Nhóm | Được phép |
|---|---|
| Review | Xử lý hàng đợi review: Accept, Disable, hoặc Report error trên một giá trị, liên kết, loại, hoặc bản trùng |
| Địa điểm | Xem danh sách địa điểm và bằng chứng; yêu cầu làm mới nguồn |
| Xung đột | Accept để giữ chưa chắc chắn, hoặc Report error trên observation của nguồn sai (build lại, rule chọn giá trị; xung đột vẫn giữ trong lịch sử) |
| Quan sát | Xem toàn bộ dữ liệu người dùng (transcript, phiên, event, check-in, thông báo), analytics, Insights, pilot, trạng thái hệ thống, lỗi, phản hồi |

Admin **không** gõ giá trị mới cho fact của địa điểm: dữ liệu do agent xây, giá trị sai được báo lỗi và hệ thống build lại từ bằng chứng (`docs/CORPUS.md` §7 Publish và review). Admin không sửa lịch trình của User và không quyết định thay User.

---

## 2. User Web — các màn hình

Luồng bắt đầu khác nhau theo trạng thái bắt đầu (`docs/Project_Context.md` §3.2). Cách hiển thị giá trị chưa chắc chắn, fact, signal, estimate: `docs/UX_Design_Brief.md` §4.

### 2.1 Vào ứng dụng

- Chưa đăng nhập: các nút bắt đầu ở Landing mở `/app/login` (đã có phiên, kể cả khách, thì vào thẳng `/app`; logo luôn về `/app`). Màn đăng nhập có Google, email + mật khẩu (hai chế độ Đăng nhập / Tạo tài khoản, và "Quên mật khẩu?" ở §2.1 bên dưới) và "Dùng thử, không cần tài khoản"; lần đầu thêm màn đồng ý điều khoản và chính sách dữ liệu (`docs/ACCOUNTS.md` §2). Google trả về đúng trang đang mở.
- Mỗi trạng thái của màn đăng nhập có giao diện riêng, gắn với một phản hồi thật của harness (`POST /api/auth/login`, `/register`, `/guest`; `GET /api/auth/google/callback`). Linh vật (chú thỏ tai cụp đeo ba lô của chủ dự án) đổi dáng theo trạng thái:

| Trạng thái | Nguồn | Hiển thị | Linh vật |
|---|---|---|---|
| Thiếu / sai ô (email trống hoặc sai dạng, mật khẩu trống, dưới 8 ký tự, hai mật khẩu không khớp) | kiểm ở client theo đúng luật của server; 400 `email is not valid` / `password must have 8-128 characters` / `name is too long` cũng gắn vào đúng ô | thông báo ngay dưới từng ô, nút luôn bấm được; bấm gửi khi còn lỗi thì đưa con trỏ về ô lỗi đầu tiên; ô trống chỉ bị nhắc khi gửi, ô đã gõ thì nhắc khi rời ô | nghiêng đầu, dấu "?", bong bóng nêu ô nào chưa ổn |
| Đang gõ mật khẩu | focus ô mật khẩu / nhập lại | gợi ý "Thêm N ký tự nữa", "Đủ dài rồi", "Khớp rồi" | che mắt; bật hiện mật khẩu thì hé mắt nhìn |
| Email đã có tài khoản | 409 `email is taken` (kể cả email từng vào bằng Google) | thông báo dưới ô email kèm "Đăng nhập bằng email này" (giữ nguyên email đã gõ) | nghiêng đầu, "Email này mình nhận ra rồi nè!" |
| Sai email hoặc mật khẩu | 401 `wrong email or password` (một thông điệp cho mọi nguyên nhân) | khung báo lỗi trên nút, xóa ô mật khẩu và focus lại | buồn, giọt mồ hôi |
| Thử quá nhiều lần | 429 (8 lần sai / 15 phút cho một email) | khung báo "chờ vài phút", gợi ý Google | buồn |
| Mất mạng / máy chủ lỗi | `fetch` lỗi / 5xx | khung báo kèm "Thử lại" | buồn |
| Lỗi khác | 403 `cross-origin request refused`, 400 không gắn được vào ô | khung báo "kiểm tra lại các ô hoặc tải lại trang" | buồn |
| Đang gửi | chờ phản hồi | nút đổi thành "Đang đăng nhập…" / "Đang tạo tài khoản…" có vòng quay, các ô khóa | nghĩ, bong bóng ba chấm |
| Thành công | 200 `signed_in` | nút thành "Vào rồi, đang mở…" / "Tài khoản đã sẵn sàng"; khoảng 1,4 giây (0,5 giây nếu giảm chuyển động) rồi mới tải phiên và mở app (hoặc màn đồng ý điều khoản) | nhảy mừng |
| Google từ chối / hết hạn | `/app/login?error=denied|state|failed` | khung báo đầu form | buồn |
| Khách không mở được | `POST /api/auth/guest` 429 (quá nhiều phiên một giờ) / lỗi khác | khung báo dưới nút khách | buồn |

  Linh vật là ảnh thật của cùng nhân vật cho từng dáng (`web/public/img/bunny/`). Bản hiện tại là chú thỏ tai cụp thắt hai nơ vàng, ba lô nâu (tấm 12 dáng của chủ dự án, `docs/design/mascot-sheet.png`): mười hai dáng `idle`, `happy`, `wait`, `wow`, `sad`, `sleepy`, `love`, `point`, `curious`, `map`, `cry`, `angry` được tách nền từ tấm đó bằng `web/scripts/cut_mascot_sheet.py` (cùng script cắt khuôn mặt `idle` làm `img/gen/bot-avatar.webp` cho trợ lý và `reference.png`); các dáng tấm không vẽ (`shy`, `peek`, `mail`; `wink`, `cheer`, `bow`, `point_up`, `walk_a`, `walk_b` của tour; và mười trạng thái dành cho các khoảnh khắc của sản phẩm: `umbrella` mưa, `cold` trời lạnh, `coffee` quán cà phê, `camera` chụp ảnh, `idea` gợi ý, `warn` cảnh báo Đánh đổi, `calendar` lịch đã chốt, `thumbs_up` đồng ý, `suitcase` chuẩn bị đi, `eat` món ăn — chưa gắn vào màn nào) tạo bằng `web/scripts/gen_mascot_moods.py` và `gen_tour_mascot.py` qua endpoint ảnh của 9router, lấy `reference.png` làm ảnh tham chiếu để giữ nguyên nhân vật (`manifest.json` ghi model, prompt, giờ). Muốn đổi linh vật: thay tấm dáng, chạy `cut_mascot_sheet.py`, rồi `gen_*` với `--force`. Nền phong cảnh Đà Lạt và cành lá góc trang (`web/public/img/auth/scene.webp`, `leaves.webp`) tạo bằng `web/scripts/gen_auth_scene.py`. Giao diện thẻ đăng nhập theo mockup xanh lá của chủ dự án: cột trái là cảnh có logo chữ TripGuardian (vẽ bằng SVG, `Brand` trong `AuthMascot.tsx`), cột phải là form; ô nhập bo tròn có biểu tượng đầu ô, khung "Tài khoản dùng thử" cuối form. Đổi dáng bằng chuyển mờ, thêm chút chuyển động (lắc, nhảy, đung đưa) và bong bóng lời. `prefers-reduced-motion`: giữ dáng và bong bóng, bỏ chuyển động.
- **Quên mật khẩu** (`docs/ACCOUNTS.md` §2c): liên kết "Quên mật khẩu?" cạnh nhãn Mật khẩu ở form đăng nhập, chỉ hiện khi `GET /api/auth/options` trả `password_reset: true` (server có SMTP). Bấm thì thẻ đăng nhập đổi thành bảng hai bước (email đã gõ được mang theo, "Quay lại đăng nhập" trả lại):

| Trạng thái | Nguồn | Hiển thị | Linh vật |
|---|---|---|---|
| Bước 1, nhập email | liên kết "Quên mật khẩu?" | ô email, nút "Gửi mã"; email trống / sai dạng nhắc ngay dưới ô | nghiêng đầu, dấu "?" |
| Đang gửi mã | chờ `forgot` | nút "Đang gửi mã…" có vòng quay, ô khóa | nghĩ, ba chấm |
| Đã gửi | 200 (giống nhau cho mọi email) | bước 2: "Nếu email này có tài khoản, mình đã gửi mã tới …", hạn 10 phút, nhắc xem Spam, "Đổi email"; 6 ô mã (gõ tự nhảy ô, Backspace lùi, dán cả mã vào ô nào cũng trải đủ 6 ô, bàn phím số, `one-time-code`); ô mật khẩu mới + nhập lại (luật như đăng ký); đủ 6 số thì con trỏ nhảy sang mật khẩu | cầm phong thư |
| Gõ mật khẩu mới | focus ô mật khẩu | như đăng ký ("Thêm N ký tự nữa", "Khớp rồi") | che mắt / hé mắt |
| Gửi lại | đếm ngược theo `resend_after` | "Gửi lại sau 0:59", hết giờ thành nút "Gửi lại mã" (mã mới thay mã cũ, ô mã xóa trống) | giữ nguyên |
| Thiếu ô | kiểm ở client khi gửi | thông báo dưới từng ô, con trỏ về ô lỗi đầu | nghiêng đầu, bong bóng nêu ô nào chưa ổn |
| Mã sai | 400 `wrong code` + `tries_left` | "Mã chưa đúng. Bạn còn N lần thử.", 6 ô viền đỏ và xóa trống | buồn |
| Mã bị hủy / hết hạn | 410 `code locked` / `code expired` | khung báo "Mã này không dùng được nữa" / "Mã đã hết hạn" kèm "Gửi mã mới" (khóa tới hết thời gian chờ) | buồn |
| Chờ gửi lại | 429 `wait` + `retry_after` | khung "Mình vừa gửi mã rồi", chờ N giây (hoặc "thử lại sau khoảng N phút" nếu dài hơn 2 phút), ở bước 1 có "Nhập mã mình đã nhận" | nghiêng đầu |
| Quá nhiều lần | 429 `too many requests` (theo địa chỉ) | khung "Bạn thử hơi nhiều lần rồi" | buồn |
| Tính năng tắt | 503 `password reset unavailable` | khung "Tính năng này đang tạm tắt", gợi ý Google | buồn |
| Mất mạng / máy chủ lỗi | `fetch` lỗi / 5xx | khung báo kèm "Thử lại" | buồn |
| Thành công | 200 `signed_in` | nút "Đã đổi, đang mở…", rồi vào app như đăng nhập (mọi phiên cũ của tài khoản đã bị kết thúc) | nhảy mừng |
- Một ô nhập tự do: người dùng gõ hoặc dán link đã lưu, danh sách, lịch có sẵn, hoặc chỉ một câu. Hệ thống tự phân loại trạng thái bắt đầu, không hỏi.
- Lối tắt khi chưa biết gõ gì: "Chưa có gì" / "Địa điểm đã lưu" / "Nơi bắt buộc đến" / "Một lịch trình".
- Người dùng quay lại có hồ sơ: đề xuất "Theo gu quen thuộc" hoặc "Lần này khác".

### 2.2 Thiết lập chuyến đi

- Bắt buộc: ngày đi, số người và là ai (người yêu, bạn, trẻ em, bố mẹ), phương tiện. Hỏi sau phần trò chuyện, bỏ qua được: cách tới Đà Lạt (tự đi / xe khách / máy bay; không chọn chuyến), điểm xuất phát (nhà), đã có chỗ ở chưa (có thì gõ tìm; chưa thì chọn ở tab "Chỗ ở" của Chọn nơi, gợi ý theo gu). Chỗ ở là điểm bắt đầu / kết thúc mọi ngày của lộ trình.
- Tùy chọn: nơi bắt buộc đến, booking cố định, giờ check-in/check-out và giờ phải rời Đà Lạt, giới hạn cứng (ngân sách, thời gian di chuyển tối đa mỗi chặng, tránh đường dốc, phải xong trước một giờ, loại hoạt động không muốn).
- Giới hạn cứng và sở thích mềm là hai loại khác nhau (`docs/ARCHITECTURE.md` §2).
- Cổng trước lịch đếm các câu chưa được xác nhận, không tính giá trị tự điền là thao tác của bạn; câu chuyến đi chỉ xong khi đủ các phần đang hỏi, gồm giờ bắt đầu/kết thúc. Tiêu đề, thanh tiến độ và dấu ✓ dùng chung trạng thái.
- Khối món ăn ưu tiên nhãn có dấu trong evidence khi khớp chuẩn hóa với món đang hỏi; không khớp thì giữ nhãn backend, không đoán dấu.

### 2.3 Khám phá sở thích

- Mỗi lần một câu hỏi, kèm chip gợi ý, ô nhập tự do, "Chưa chắc", "Bỏ qua / gợi ý trước đi". Quy tắc chọn câu hỏi và ngân hàng câu hỏi: `docs/TRIP_UNDERSTANDING.md` §5, §12.
- Có profile: chỉ hỏi điều khác lần này — "Theo gu quen thuộc / Muốn thử cái mới / Đi với người khác / Có yêu cầu riêng".
- Kết thúc bằng **Tóm tắt chuyến đi**: thông tin cơ bản, anchor, giới hạn cứng, sở thích (đánh dấu nếu lấy từ hồ sơ), điều còn chưa biết. Sửa được trước khi bắt đầu tìm.

### 2.4 Nhập địa điểm đã lưu / lịch trình có sẵn

- Mỗi mục: đã khớp ✓ / cần chọn (2–3 ứng viên với tên, khu vực, ảnh hoặc ghim bản đồ) / không tìm thấy (giữ ở dạng "chưa xác minh" hoặc xóa).
- Gộp trùng ("Túi Mơ To" và "Tiệm Túi Mơ To" là một nơi). Gắn nhãn bắt buộc đến / đã lưu / đã đi / tránh / chưa rõ.
- Không bao giờ đoán match. Nơi chưa xác minh vẫn ở lại trong chuyến đi, có đánh dấu (`docs/PLACE_DECISION.md` §4).

### 2.5 Shortlist

- Gom theo nhóm: điểm tham quan, thiên nhiên & view, ăn uống & cà phê, mua sắm / đặc sản. Chỗ ở không nằm trong shortlist (§2.2).
- Thẻ địa điểm:

```text
Tên · loại · khu vực
Vì sao phù hợp   ✓ view rừng thông  ✓ hợp cặp đôi  ✓ gần khu Ngày 2 của bạn
Đánh đổi         ! thêm ~25 phút di chuyển
Thời gian        60–90 phút
Độ tin cậy       Cao / Trung bình / Thấp
```

- Thao tác: thêm vào danh sách chọn · bỏ · khóa · so sánh · xem chi tiết.
- So sánh nơi giống nhau mở từ nút nổi "So sánh N nơi" (lưới không chen dòng "khá giống nhau").
- Trạng thái: quá ít kết quả ("nới một giới hạn?"); mọi nơi bị một giới hạn cứng loại (nói rõ giới hạn nào).

### 2.6 Chi tiết địa điểm (bằng chứng)

- **Thông tin thực tế** (giờ, giá, đặt chỗ): giá trị + nguồn (chính thức / Google) + ngày kiểm tra. Xung đột hiển thị cả hai giá trị, đánh dấu chưa xác nhận.
- **Trải nghiệm**: mỗi feature mở ra clip TikTok phát tại đúng đoạn và xu hướng comment kèm cỡ mẫu ("62% trong 123 comment về độ đông, từ 30 creator"), cùng 2–3 comment gốc có link về video.
- **Mức vận động** (đi bộ, dốc, đường vào) và **đối tượng phù hợp** (cặp đôi, trẻ em, người lớn tuổi).
- Nút **Báo thông tin sai**: chỉ đưa địa điểm vào hàng đợi review và kích hoạt làm mới nguồn; không đổi dữ liệu và không được coi là bằng chứng.

### 2.7 So sánh

- 2 (tối đa 3) nơi giống nhau; chỉ hiển thị các thuộc tính khác nhau (trải nghiệm, di chuyển, độ đông, chi phí, thời điểm đẹp nhất).
- Một câu hỏi tiếp theo, ví dụ "Ưu tiên ít di chuyển hay chỗ yên tĩnh hơn?". Lựa chọn cập nhật chuyến đi ngay; hệ thống không chọn thay.

### 2.8 Tuyển chọn — danh sách đã chọn kèm khả thi trực tiếp

- Luôn hiển thị: số nơi đã chọn, tổng thời gian tham quan, thời gian di chuyển ước tính, chi phí ước tính. Thanh chỉ tóm tắt; **không** cảnh báo "chọn hơi nhiều", không gợi ý bỏ nơi, không lộ mã nơi (03/11: Lựa chọn không chặn, không nhắc; quá tải xử lý ở Lịch trình).
- Mỗi thay đổi hiện một dòng chênh lệch số: "+1 nơi · +70 phút · +35 phút di chuyển".
- Hai nút khác nhau trên thẻ: tim = **Yêu thích** (danh sách Đã lưu, không vào chuyến; thẻ không có nút Thích, danh sách không đổi khi lưu); **Thêm vào chuyến** = vào danh sách đã chọn.
- Bỏ thực hiện ngay, không hỏi lý do; giữ thao tác hoàn tác. Hai bộ đếm số nơi dùng cùng danh sách lựa chọn optimistic.
- Thẻ thiếu ảnh giữ placeholder kèm “Chưa có ảnh của {tên}”; ảnh tải lỗi thử ảnh gốc khi thiếu thumbnail, nếu vẫn lỗi hiện “Chưa tải được ảnh”, không hiện credit ảnh hỏng. Đổi nguồn ảnh thì thử tải lại.

### 2.9 Kết quả khả thi

| Kết quả | Hiển thị |
|---|---|
| **Khả thi** | Chuyển sang xếp lịch |
| **Khả thi một phần** | Nơi nào xung đột, vi phạm quy tắc nào, mỗi cách sửa được gì ("Bỏ C: tiết kiệm 90 phút, Ngày 2 ổn"); người dùng chọn cách sửa |
| **Không khả thi** | Lý do tổng thể (cần 14 giờ, có 9 giờ · vượt ngân sách 400k · hai booking trùng giờ) và lối quay lại tuyển chọn |

Xung đột với giới hạn của người dùng → đưa ra "nới giới hạn này" kèm cái giá cụ thể. Xung đột vật lý → chỉ đưa ra cách dời có thật (`docs/PLACE_DECISION.md` §13.3).

### 2.10 Lịch trình

- (03/11) Chưa có lịch: chữ hướng dẫn bấm **Lập lịch** (đúng tên nút) và có nút về Lựa chọn. Thiếu điểm xuất phát: hàng *Bạn khởi hành từ đâu?* có sẵn ô gõ địa chỉ như bản đồ (chọn gợi ý là lưu, lịch được xếp lại), không câu "chưa biết bạn xuất phát từ đâu". Không có thẻ dự phòng (18/11/2026). Cổng thiếu thông tin (409 `trip_incomplete`, chỉ khi người dùng tự nhắc vấn đề sức khỏe chưa rõ) mở hộp câu hỏi ngay. Thông báo luôn có nhãn tiếng Việt (kind chưa biết dùng nhãn chung, không hiện khóa thô). Eve chỉ gọi cho tài khoản, không gọi cho khách.

- Màn chỉ nhận act, không chat. Planning Agent đề xuất nội bộ từ phương án đã kiểm; “+ Thêm nơi” quay về tuyển chọn trong cùng hành trình.
- Theo từng ngày: dòng thời gian (giờ đến, khoảng thời gian ở lại, di chuyển giữa các điểm), bản đồ lộ trình, chi phí ước tính, cảnh báo tại đúng điểm dừng.
- Chi phí, độ vững và dự phòng đọc từ lịch hiện tại sau sửa; xung đột validation hiện trước khi chốt. Gợi ý thêm hoạt động có trạng thái đang tìm / chưa tải được, không cản thao tác sửa lịch. Read/SSE cũ không thay view mới (`docs/AGENT_HARNESS.md`).
- Quá tải mở ba thẻ để user chọn, không tự chọn qua Agent. Giữ tất cả có phần đối chiếu timeline riêng; nút chọn bị khóa khi lịch gốc chưa hợp lệ. Mọi đường chọn profile unavailable và nút chốt draft vi phạm đều bị vô hiệu. Preview/apply và delta theo lịch hiện tại: `docs/PLANNING.md` §Vòng người dùng sửa và góp ý.
- Nhãn độ vững mỗi ngày: Vững / Khả thi / Mong manh, kèm lý do một câu (`docs/PLANNING.md` ⓕ).
- Thẻ độ phù hợp giờ ghé giải thích ước lượng theo hoạt động và phút rút; gợi ý khoảng trống/quá tải có nút thêm tùy chọn từ backup, xếp lại ngày và hoàn tác được (`docs/PLANNING.md` §Độ phù hợp giờ ghé).
- Không hiện phương án dự phòng (18/11/2026).
- (04/11) Thẻ gợi ý khoảng trống, dự phòng và màn thêm / đổi nơi hiện nguyên văn `alternative.warnings[].text`; gợi ý từng ngày (ghost) hiện `ghost.items[].note` (ví dụ "chưa rõ có cho mang thú cưng không"), chữ nhỏ, không chặn nút. Thẻ nơi ở Lựa chọn hiện thú cưng như thuộc tính thường (cho / không cho kèm số nguồn, hoặc "Chưa rõ…"), không nhãn cảnh báo.
- Thông tin chưa xác nhận vẫn được đánh dấu ("Giờ mở cửa chưa xác nhận — kiểm tra trước khi đi").

### 2.11 Hồ sơ và dữ liệu

- Avatar, tên hiển thị, thành phố hay xuất phát, phương tiện hay dùng, hay đi với ai: đều tùy chọn, chỉ là gợi ý ban đầu "từ hồ sơ" cho chuyến mới.
- Sở thích của chuyến hiện tại (từ lời người dùng hoặc từ hồ sơ), Google Calendar đã kết nối và nút ngắt, cài đặt thông báo theo loại + tạm im, hướng dẫn thêm vào màn hình chính (iPhone).
- Xóa tài khoản: hỏi hai bước.

### 2.12 Phản hồi

- Sau kế hoạch hoặc sau chuyến đi: gợi ý có đúng, lý do có dễ hiểu, lịch có thực tế, có còn phải tìm chỗ khác, có tự tin hơn. Ngắn, không bắt buộc.
- Dùng cho analytics và pilot; nếu người dùng cho phép, nơi đã đến và phản hồi cập nhật User Profile (`docs/Project_Context.md` §8.5).

### 2.13 Hôm nay (Đang đi)

- Sau khi chốt lịch: từng ngày, mỗi điểm dừng một thẻ (giờ, ảnh, giờ mở, cảnh báo của lịch). Nút **Đã đến** tự nguyện; không có trạng thái "lỡ". Bỏ qua kèm lý do tùy chọn; sau khi đến có Hợp / Không hợp.
- Đã đến mở "Ở đây": chơi gì ở đây (kèm trích dẫn, clip), lưu ý thực tế, giờ hoàng hôn / mức đông theo giờ khi có dữ liệu, gần đây (vừa thời gian trước điểm sau), nơi tương tự khi đông hoặc không như kỳ vọng. "Tôi đang ở nơi khác" tìm nơi rồi check-in.
- Tới muộn: một dòng trung tính "Phần còn lại hơi chật · Xem cách điều chỉnh"; đổi lịch chỉ khi người dùng chọn và xác nhận.
- Thẻ Google Calendar (xem trước → xác nhận; lệch kế hoạch thì một dòng "Lịch Google khác kế hoạch hiện tại"), thẻ xin bật thông báo, Hộp thông báo. Chi tiết: `docs/COMPANION.md`.

### 2.14 Hướng dẫn có linh vật

- Linh vật (quả sồi) dẫn một vòng: nền tối đi, ô đang nói sáng lên, linh vật đứng cạnh ô và chỉ tay, lời ngắn cố định (không do model viết). Chương: Trang chủ (ô tìm, thẻ lớn, chủ đề, Trending, lịch, hồ sơ) → Thanh bên (mỗi bước mở đúng trang thật) → "Một chuyến đi" (bốn câu đứng ở trang chủ) → Kết (nhảy mừng, pháo giấy, âm, rồi chỉ nút Tạo chuyến đi).
- Tự chạy lần đầu ở trang chủ; "đã xem" nhớ theo tài khoản trong `localStorage` (`tg-tour-seen:<account.id>`), ghi lúc bắt đầu. Khách nào cũng thấy (mỗi khách một định danh mới); bước cần tài khoản đổi lời mời đăng nhập.
- Điều khiển: Bỏ qua / Quay lại / Tiếp, Esc thoát, phím ← →. Xem lại từ Cài đặt và trang Hỗ trợ. Ô không có trên màn (ví dụ Trending chưa có bản tin) thì linh vật đứng giữa màn, không chỉ tay.

---

## 3. Admin Web — các màn hình

```text
ADMIN
├── Dashboard                     /admin
├── Review Queue                  /admin/review
├── Labels (gán nhãn đo chất lượng) /admin/labels
├── Places (danh sách + chi tiết)  /admin/places
├── Evidence (theo dõi + xung đột) /admin/evidence
├── Người dùng (danh sách + chi tiết) /admin/users
├── Xu hướng tiêu dùng            /admin/trends
├── Trip Sessions                 /admin/sessions
├── Analytics                     /admin/analytics
└── System Monitor                /admin/system
```

### 3.1 Hàng đợi review

Việc chính hằng ngày của Admin. Nội dung và thứ tự hàng đợi: `docs/CORPUS.md` §7 Publish và review.

- **Danh sách:** loại mục (giá trị Judge đánh dấu · kiểm tra giá trị cho phép về an toàn / tiếp cận / đối tượng phù hợp · tên chưa resolve · feature đề xuất), địa điểm, khía cạnh, vì sao nằm ở đây, mức rủi ro.
- **Một mục:** giá trị, thành phần độ tin cậy (số nguồn, đồng thuận, độ mới, loại nguồn), bằng chứng (clip tại timestamp, comment, trích đoạn chính thức), finding của Judge.
- **Thao tác:** Accept · Disable · Report error (giá trị / liên kết / loại POI/ZONE / trùng / category). Accept hàng loạt cho mục rủi ro thấp cùng loại.
- Mẫu ngẫu nhiên các mục đã publish được trộn vào **không đánh dấu** và phải trông y hệt các mục khác.

### 3.2 Gán nhãn (đo chất lượng)

Nơi duy nhất sinh ra thước đo precision của corpus (`docs/CORPUS.md` §Đo chất lượng). Khác hàng đợi review: ở đây người duyệt không quyết định số phận một giá trị, chỉ nói "bằng chứng này có đỡ được giá trị này không".

- **Một mục:** feature + giá trị cần chấm, bối cảnh, và đoạn review gốc có **tô đậm đúng quote** mà Extractor dựa vào; ảnh Maps và video TikTok hiện cùng cách.
- **Thao tác:** nhãn đúng / sai / không rõ, kèm ghi chú tùy chọn. Lấy theo lô (`BATCH` = 4) để chấm nhanh.
- **Thống kê:** số nhãn và precision (kèm cận dưới Wilson) theo từng feature, so với `gate` — giá trị chưa đủ nhãn thì chưa được phục vụ một mình (`docs/CORPUS.md` §5 Aggregate, `servable`).

### 3.3 Danh sách địa điểm và chi tiết

- **Danh sách:** địa điểm · trạng thái · bằng chứng · độ tin cậy · cập nhật. Lọc theo trạng thái (bộ trạng thái chung: `docs/CORPUS.md` §Trạng thái), category, thành phố (theo config), coverage. Hiển thị khía cạnh có trạng thái tệ nhất.
- **Chi tiết:** Identity, Operation, Experience, Environment, Effort, Suitability — mỗi khía cạnh có trạng thái, coverage, bằng chứng, độ mới, độ tin cậy; finding của Judge và lịch sử review.
- **Thao tác:** Accept · Disable · Report error · Request refresh. Provenance cũ không bao giờ bị xóa.

### 3.4 Theo dõi bằng chứng và xung đột

- **Mỗi bản ghi:** nhận định · nguồn · thời điểm thu thập · độ tin cậy · trạng thái. Lọc: Fresh / Outdated / Missing / Conflicting / Single source.
- **Xung đột** (cùng nhận định, khác giá trị): Accept (giữ chưa chắc chắn) · Report error trên observation của nguồn sai (build lại, rule chọn giá trị) · Refresh sources. Khi chưa xử lý, User Web nhận trạng thái chưa chắc chắn.

### 3.5 Dashboard

```text
Places 842 · Verified 691 · Needs Review 23 · Outdated 53
Last build: auto-published 88% · sampled precision 96% · cost per place $0.04
Hôm nay: người dùng mới 5 · hành trình 18 · lịch đã chốt 13 · phản hồi 2 · lỗi và fallback 1
```

Vài con số để phát hiện vấn đề nhanh; hàng "Hôm nay" lấy số thật từ server analytics (`docs/ANALYTICS.md`). Màn này không đợi snapshot admin (40 MB): nó đọc `/data/admin-overview.json` (~85 KB nén; `admin_overview` trong `web/scripts/export_snapshot.py`, `admin/overview.ts`), vẽ khung chờ ngay, và snapshot chỉ bắt đầu tải sau khi màn này đã vẽ; `index.html` bắt đầu ba lần đọc của `/admin` (`/me`, tổng quan, Hôm nay) ngay khi phân tích HTML, trước khi script tải xong (`admin/prefetch.ts`). Dưới hàng đó là thẻ "Hàng đợi duyệt" (`QueueCard` trong `Dashboard.tsx`): 8 mục chưa xử lý có rủi ro cao nhất; mục rủi ro thấp chấp nhận ngay tại thẻ, mục còn lại mở hàng đợi `/admin/review`.

### 3.6 Phiên chuyến đi

Để debug, đánh giá pilot, tìm chỗ người dùng bỏ dở. Danh sách hành trình trên server, lọc theo bước đã tới, bỏ dở (24 giờ không động, chưa chốt), phản hồi thấp (điểm ≤ 2), có lỗi / fallback. Chi tiết là dòng thời gian phát lại: event, log Decision / Planning, phản hồi, hội thoại Hiểu chuyến, các yêu cầu đã ghi.

### 3.7 Analytics

Tab Phễu, Trip, Quyết định, Lịch trình, Thực tế, Thông báo, Agent, Chất lượng; lọc theo ngày, cách bắt đầu, phiên bản; Phễu so sánh hai phiên bản. Màn Insights liệt kê việc nên làm (từ khóa cần crawl, mong muốn ontology chưa hiểu, nơi hay bị bỏ, câu hỏi hay bị bỏ qua, phiên lỗi) và các nhóm ý người dùng viết trong tuần. Chi tiết chỉ số: `docs/ANALYTICS.md` §3–4.

Chỉ số chất lượng quan trọng hơn lượt xem hay click CTA. Ngưỡng chỉ đặt sau khi có baseline thật.

### 3.8 Theo dõi hệ thống và lỗi

- **Thành phần:** Corpus build (lần chạy gần nhất, ngân sách đã dùng) · Discovery · Resolution · Evidence pipeline · Recommendation · Feasibility · Routing · LLM. Trạng thái: Healthy / Warning / Unavailable.
- **Lỗi gần đây:** thời gian · sự kiện · địa điểm hoặc chuyến đi liên quan ("20:14 thiếu giờ mở cửa — Place #128").

### 3.9 Người dùng

Để vận hành và định hướng sản phẩm theo **người**: ai dùng, đi tới đâu, dừng ở đâu, quay lại không, tính năng nào chưa ai chạm tới. Chỉ đọc; không khóa, sửa hay xóa tài khoản (§5). Định nghĩa số: `docs/ANALYTICS.md` §5.

- **Tổng quan:** chọn 7 / 30 / 90 ngày / từ đầu, tùy chọn gồm tài khoản thử. Sáu KPI so với kỳ trước; biểu đồ theo ngày (hành trình tạo, lượt chốt, tài khoản hoạt động, phiên khách; rê chuột hoặc phím ← → đọc từng ngày; xem dạng bảng); mỗi người đi tới đâu (bước rơi nhiều nhất tô vàng); giữ chân theo tuần đăng ký (ô in số); tính năng được dùng theo luồng sản phẩm; cách đăng nhập và hồ sơ đã điền.
- **Tín hiệu cần chú ý:** danh sách sự thật đếm được, không ngưỡng; bấm một mục lọc bảng dưới đúng nhóm người đó.
- **Danh sách:** tìm theo tên / email / nickname / id; lọc loại (tài khoản, khách) và nhóm (mới, hoạt động, chưa tạo hành trình, chưa chốt, chỉ 1 ngày, có lỗi, chấm ≤ 2); sắp theo mọi cột; tiến độ là 7 ô của các bước.
- **Một người** (`/admin/users/<id>`): hồ sơ, đồng ý, lịch hoạt động 26 tuần, các bước đã tới, tính năng đã dùng, hành trình (bấm để phát lại ở §3.6), phản hồi, sự kiện gần nhất.

### 3.10 Xu hướng tiêu dùng

Nửa thứ hai của bảng điều khiển người dùng (công tắc *Người dùng · Xu hướng tiêu dùng* ở đầu cả hai màn): khách thích nơi nào, lập lịch ra sao, muốn gì, để định hướng sản phẩm, nội dung và Trending. Cùng bộ chọn kỳ. Định nghĩa số: `docs/ANALYTICS.md` §6.

- **Đang lên 7 ngày qua:** 5 nơi được quan tâm tăng nhiều nhất so với tuần trước.
- **Nơi được quan tâm:** xếp theo được chọn / vào lịch đã chốt / xem chi tiết / thích và lưu / đang lên / bị bỏ, lọc theo nhóm; tỉ trọng lượt chọn theo nhóm; mỗi hàng đủ các cột và tỉ lệ chọn; bấm để mở trang Địa điểm (§3.3).
- **Lịch nhiều người lập:** độ dài chuyến, nơi mỗi ngày, chốt trước bao lâu, giờ tới nơi, cặp nơi hay xếp cùng chuyến và hay đi liền nhau.
- **Khi nào khách đi**, **khách muốn gì** (đi cùng ai, số người, số ngày, phương tiện, ngân sách, mục đích, sở thích, loại nơi, món, cảm hứng), **chủ đề và từ khóa**, **vì sao khách bỏ một nơi**.

---

## 4. Ưu tiên MVP

| User Web | Admin Web |
|---|---|
| 1. Thiết lập chuyến đi · 2. Khám phá sở thích · 3. Shortlist · 4. So sánh · 5. Tuyển chọn · 6. Kết quả khả thi · 7. Lịch trình · 8. Cảnh báo / dự phòng | 1. Hàng đợi review · 2. Gán nhãn · 3. Danh sách địa điểm + chi tiết · 4. Theo dõi bằng chứng · 5. Phiên chuyến đi · 6. Analytics sản phẩm / pilot · 7. Theo dõi hệ thống · 8. Acquisition / UTM |

## 5. Ngoài phạm vi MVP

- User Web: chỉ đường từng bước, đặt chỗ và thanh toán, tính năng mạng xã hội, cộng tác nhóm lớn, thành phố ngoài Đà Lạt.
- Admin Web: nhiều cấp admin, quy trình duyệt nhiều bước, ma trận quyền chi tiết, CRM, hệ thống chăm sóc khách hàng, billing, quản lý booking, nền tảng quản lý campaign, quản lý tài khoản nâng cao, nền tảng kiểm duyệt, dashboard doanh nghiệp.

---

## 6. Triển khai — màn nào ở đâu

Một app React (`web/`, Vite). `App.tsx` chọn bề mặt theo đường dẫn; mỗi bề mặt có bảng route riêng.

Tên địa điểm hiển thị cho người dùng luôn qua `data/placeName.ts` (`displayName`: viết hoa chữ đầu, bỏ phần quảng cáo sau gạch / dấu hai chấm / ngoặc, bỏ chữ ngoại ngữ, tối đa 44 ký tự cắt ở ranh giới từ): áp lúc nạp snapshot (`Place.name`, tên gốc ở `Place.fullName` cho tìm kiếm) và lên mọi phản hồi harness có `id`/`place_id` kiểu Google (`tidyPlaceNames` trong `user/journey.ts`). Admin giữ tên gốc.

| Màn (§) | File | Backend |
|---|---|---|
| Landing (§1) | máy tính: `user/screens/Landing.tsx` (nút bắt đầu: có phiên thì vào `/app`, chưa có thì tới `/app/login`; người đã đăng nhập có thêm "Dùng thử khách": phiên khách mới, tài khoản giữ nguyên) + cảnh 3D `user/landing/{scene,terrain}.ts`; điện thoại: `user/screens/GetApp.tsx` thay cho **mọi** trang người dùng (`/`, `/app/...`; chọn bằng `user/landing/device.ts`, `UserApp.tsx`) — web không có bản điện thoại, ứng dụng sẽ có sau; dữ liệu thật trích từ snapshot ở `user/landing/*.json` | — |
| Đăng nhập (§2.1) | `user/screens/Auth.tsx` (Google, "Dùng thử, không cần tài khoản" = khách mới sạch, đồng ý điều khoản), `user/screens/AuthEmailForm.tsx` (form email + mật khẩu, kiểm ô, mọi trạng thái ở bảng §2.1), `user/screens/AuthReset.tsx` (Quên mật khẩu hai bước, 6 ô mã, đếm ngược gửi lại), `user/screens/AuthMascot.tsx` + `user/css/auth.css` (linh vật theo dáng), `user/account.ts` (401 ở bất kỳ lời gọi harness nào → màn đăng nhập) | `harness` — `/api/auth/*` (`google`, `register`, `login`, `password/forgot`, `password/reset`, `options`, `guest`, `logout`), `/me` |
| Khung app (mọi trang không thuộc luồng chuyến: Dành cho bạn, Chuyến của tôi, Đã lưu, Đã xem gần đây, Thông báo, Cài đặt, Hôm nay mở từ link) | `user/home/Frame.tsx` (phủ toàn màn hình: thanh bên là cột icon hẹp (kiểu Pinterest), tên mỗi nút hiện thành tooltip khi rê chuột hoặc focus bàn phím; các thẻ trắng rời nhau: (1) logo (bấm về `/app`); (2) Dành cho bạn · Chuyến của tôi · Đã lưu · Đã xem gần đây; (3) Cài đặt (trang hồ sơ) · Hỗ trợ (`user/screens/Support.tsx`, câu hỏi chung với landing ở `user/faq.ts`); hai thẻ giữa nằm giữa chiều cao cột; Đăng xuất ở đáy cột; nút "Khám phá nơi muốn đến" (đủ chữ, icon la bàn) chỉ có ở trang Dành cho bạn, cố định ở góc dưới bên phải ngay trên tab chat "Hỏi TripGuardian" (chat ở trang chủ giống hệt ở Lựa chọn, `AssistantFloat home`); bấm nút mở bảng chọn kiểu chuyến (`TagPicker` trong `user/home/dialogs.tsx`: 10 chủ đề có ảnh, chọn nhiều, và một hàng "Đi cùng ai"; "Bỏ qua" hoặc "Xem nơi hợp với mình · N") rồi vào thẳng Lựa chọn, các tag đã chọn thành tin đầu tiên của chat; các trang khác không có (chủ dự án 2026-10-30: không để nút hiện lẻ loi); mục đang mở là ô vuông đen; **không** có Hôm nay; trong luồng chuyến (Lựa chọn, trang nơi, Lịch trình, Hoàn tất) thanh bên gập vào một dải mỏng ở mép trái (`RailDock` trong `user/home/Frame.tsx`): mũi tên đôi mờ nhấp nháy nhẹ giữa dải, rê chuột vào dải hoặc focus bàn phím thì thanh bên trượt ra phủ lên trang (nền mờ phía sau), rời chuột 0,28 giây thì gập lại; trang chủ và các trang khung giữ thanh bên như thường; thanh bên của các trang này **không** có nút Trò chuyện / Lựa chọn / Lịch trình (ba nút đó chỉ ở các màn của luồng chuyến, `Sidebar` nhận `path`: `/understand`, `/explore…`, `/plan`, `/done`; bước chưa tới thì mờ, không bấm được, tooltip "kể chuyến đi trước đã"); thanh chuyến đang lập chỉ hiện khi chuyến chưa chốt lịch, chốt rồi thì ẩn; thanh là một viên thuốc kính mờ, rộng vừa nội dung, canh giữa khoảng giữa cột icon và cột phải: ảnh tròn có vòng tiến độ quanh ảnh + tên chuyến (số người, số nơi đã chọn, "Đang ở <bước>") và nút tim + "Đi tiếp" đen, không có dãy bước; nó nổi trên trang ở đáy, không đẩy thứ gì dịch đi), `user/home/Chats.tsx` (hai nút tròn cạnh ảnh đại diện (`user/home/Who.tsx`: ở trang chủ nằm đầu cột phải kèm tên và @nickname, bấm ảnh mở hồ sơ để chỉnh; ở các trang khác là ảnh nhỏ + hai nút ở góc trên phải): chuông Thông báo → `/inbox`, và Đoạn chat — danh sách bạn bè kiểu Messenger: tìm, lọc Tất cả / Chưa đọc / Đang hoạt động, chấm tin chưa đọc), `user/home/dialogs.tsx` (chủ đề, kể chuyến mới, bạn bè, gửi lịch trình; cửa sổ chat gắn góc dưới phải tối đa ba, thu nhỏ thành ảnh đại diện, trang phía sau vẫn dùng được), `user/social.ts`, `user/css/home.css` (`.tg-home` dùng bộ màu mận / hồng `.tg-rose` của luồng); bố cục theo mẫu `docs/design/mock/designs/homepage/` | `harness` — `friends`, `users`, `messages` (`docs/ACCOUNTS.md` §8), `me/library` (§9) |
| Dành cho bạn — trang chủ app | `user/screens/Discover.tsx`, `user/home/themes.ts` (10 chủ đề cố định, đủ hai hàng 5 thẻ; 5 chủ đề đầu hiện sẵn: Săn mây, Cà phê, Rừng thông, Bên hồ, Ngày mưa; nút "Xem thêm" ở đầu mục mở 5 chủ đề còn lại: Cắm trại, Thác nước, Vườn hoa, Kiến trúc, Chùa, bấm "Thu gọn" để về 5; ô tìm hiện mọi chủ đề khớp), ảnh thật trong `public/img/home/`; câu của chủ đề thành tin đầu của chat ở Lựa chọn); bố cục theo bảng điều khiển du lịch mẫu: giữa là ô tìm (gợi ý "Kể mình nghe chuyến Đà Lạt bạn đang mơ tới…", không có phím tắt `/`), thẻ ảnh lớn (tiêu đề + phụ đề, chip số địa điểm có thật trong snapshot, hiện khi snapshot tải xong; trang chủ, Chuyến của tôi, Hỗ trợ, Thông báo, Hồ sơ mở ngay không chờ snapshot, các trang còn lại hiện khung chờ trong khi tải (snapshot tải ngay khi đã đăng nhập); không có nút) và "Gợi ý để bắt đầu" (thẻ chủ đề chỉ có nhóm + tên, thẻ đầu nâng và phóng nhẹ, không nghiêng); cột phải tô nhạt gồm hồ sơ (`Who`), lịch tháng (`user/home/MiniCalendar.tsx`, đánh dấu ngày của chuyến đang lập chỉ khi chuyến có ngày; chuyến **đã chốt lịch** còn phía trước tô đen các ngày của nó (dải đầu–cuối), rê chuột hoặc focus vào một ngày đó thì hiện thẻ nhỏ của chuyến: ảnh nơi được đánh giá cao nhất kèm "Còn N ngày", tên chuyến, ngày đi, số người, ba nơi nổi bật có sao; bấm thẻ mở lịch của chuyến; danh sách chuyến đọc `GET /api/harness/trips`, hiện ngay bản lần trước) và "Trending" (`user/home/Pulse.tsx` + `user/css/pulse.css`, đọc `GET /api/harness/pulse`; chủ sản phẩm chốt 2026-11-04: khối ngắn, hướng ảnh, không "Xem thêm", không số liệu; hai tab *Sự kiện* · *Địa điểm* đổi bằng hai mũi tên hoặc tên tab (tab nào không có gì thì ẩn), mỗi tab tối đa năm hàng, mỗi hàng một dòng: ảnh sát mép trái có số hạng, tên (dài quá thì "…"), loại, sao và một dòng lý do hiện sẵn dạng chip có ngọn lửa ("Hot trên TikTok", "Khách đang đổ về"…); mọi hàng cùng một kiểu (thẻ trắng, chip vàng hổ phách theo ảnh hero, 1–3 ngọn lửa là mức xu hướng, không hiện số); nơi không có ảnh được phép hiện thì bị bỏ; tab Sự kiện liệt kê các sự kiện có ngày chính xác chưa kết thúc, gần nhất trước: ảnh là ảnh của bài đã báo sự kiện (liên kết ngoài, không gửi referrer, ghi nguồn ở tooltip), thiếu ảnh thì dùng ảnh của nơi tổ chức khi nơi đó có trong snapshot, không thì ô lịch; dòng phụ là ngày và nơi diễn ra, chip "Còn N ngày" / "Đang diễn ra"; tab Địa điểm xếp theo điểm xu hướng của server; thứ hạng của nơi là điểm 0–100 do server tính, `docs/CORPUS.md` §Nhịp "Hạng xu hướng"; dòng ngày cập nhật hoặc "Chưa làm mới từ dd/mm"; harness cũ chưa có mục `trend` thì web xếp `hot` / `top` xen kẽ); chưa có bản tin thì giữ "Top xu hướng": danh sách 5 chủ đề dạng thẻ có ô số pastel (01–05; rê chuột thì nâng và nghiêng)); bấm một chủ đề hoặc ảnh ở "Gợi ý để bắt đầu" mở blog `user/home/ThemeBlog.tsx` + `user/css/blog.css` (thẻ giấy kem kiểu bưu thiếp: ảnh trong khung, tem ở góc, luôn 5 tab dọc bên phải, trượt để giữ chủ đề đang mở trong tầm nhìn, phím mũi tên đi qua cả 10; dưới lời mô tả chỉ có dòng nhóm và nút "Bắt đầu với ý tưởng này" (câu của chủ đề thành lượt đầu); nền phía sau làm mờ; ảnh bay ra từ thẻ vừa bấm bằng Web Animations, đổi tab thì ảnh hiện từ trên xuống; Esc / bấm ngoài đóng); Enter ở ô tìm hoặc "Bắt đầu với ý tưởng này" của chủ đề tạo chuyến và mở thẳng Lựa chọn, chữ đã gõ thành tin đầu của chat ở đó (`user/home/dialogs.tsx` `useBegin`, `user/startTrip.ts`); cỡ chữ của trang chủ (`user/css/home.css`) đã tăng 10% so với bản trước | `harness` — `me/library`, event `theme_open` |
| Trò chuyện (§2.2–2.4): một khung chat, không có màn riêng | `user/ui/TripChat.tsx` trong khung "Hỏi TripGuardian" (`user/ui/Assistant.tsx`: thả từ góc dưới phải hoặc ghim cạnh lưới ở Lựa chọn; trang chủ cùng giao diện, phụ đề "Hỏi gì về Đà Lạt cũng được"): mọi tin là `decision.trip`, harness chọn agent (`docs/PLACE_DECISION.md` §19 "Một khung chat"); lượt hiện bằng các thành phần của chat cũ trong `user/screens/understand/` (`Turn.tsx` lượt chat + các bước + câu hỏi, `Ask.tsx` thẻ hỏi và sân khấu ảnh, `Deck.tsx`, `Cards.tsx`, `Blocks.tsx` khối tag / món / tiện ích, `Places.tsx` thẻ nơi, `LodgingCards.tsx`, `Composer.tsx` `shrink` cho ảnh gửi); trang chủ: tin đầu tiên tạo chuyến (`startTrip`) rồi trả lời ngay tại trang chủ; nơi của một câu trả lời là thẻ ảnh (`PlaceStrip` ở `understand/Places.tsx`: ảnh cả thẻ, tên và sao trên ảnh, tim ở góc; 1 nơi một thẻ ngang, 2 nơi chia đôi, nhiều hơn thì trượt ngang có hé thẻ kế và mũi tên), tên các nơi đó trong lời trả lời là liên kết mở nơi (`Rich` `places`); tim = thêm vào chuyến (`select` / `drop` của Decision); clip (chủ dự án 20/11/2026): block `clips` của `place_clips` hiện một dòng như dòng sân khấu ảnh (ba ảnh bìa dọc, tiêu đề, số clip và các nơi, nút ▶), bấm mở **stage clip** (`ClipStage` ở `user/screens/understand/Clips.tsx`, `css/clips.css`) trên cùng nền mờ của sân khấu ảnh: một clip dọc cao ở giữa, clip trước và sau ló ra trên / dưới bằng ảnh bìa của chúng, lăn chuột / vuốt / ↑ ↓ / nút tròn để sang clip khác (nghỉ 450 ms giữa hai lần), bấm vào clip để dừng (lớp bấm chừa mép dưới cho thanh thời gian, âm thanh, toàn màn hình của TikTok), bên phải là nơi của clip (mở trang nơi), Thích nơi này (như tim), tác giả, lời của họ, Mở trên TikTok, số thứ tự; điện thoại chỉ giữ nơi, Thích, Mở trên TikTok dưới clip; trên sân khấu ảnh, thẻ nơi có clip (snapshot `videos`) có nút "▶ N clip" mở stage clip của nơi đó chồng lên (nền mờ giữ tới khi stage cuối đóng: `useStage` đếm stage đang mở); player TikTok dùng chung ở `user/ui/clips.tsx` (`FeedPlayer`, `warmPlayer`, `poster`); ảnh bìa clip là keyframe `f1`, cho phép có người (chủ dự án 20/11/2026); khung chat thả từ góc rộng 460px, ở trang chủ là thẻ cao phủ cột phải (480px, gợi ý xếp dọc); chat còn trống (màn chào) thì khung chỉ cao vừa lời chào và bốn thẻ, tin đầu tiên mới giãn hết chiều cao; đầu mọi khung chat có nút "Trò chuyện mới" (mờ khi chat trống hoặc đang trả lời; khung ghim hẹp chỉ còn dấu +): gửi `new_chat` kèm bản chụp tin, server lưu xong mới quay về màn chào, chuyến giữ nguyên; danh sách Lựa chọn đổi theo event `view`; lịch sử chat của mỗi chuyến giữ trong trang (`logs`), lần đầu đọc transcript của Trip; "Vì sao không gợi ý?" của trang nơi hỏi trong chat; `/app/understand` (link cũ) mở Lựa chọn với chat mở | `harness` :8769 — `decision.trip`; `/read/trip/stage`, `/lodging/suggest` |
| Chọn nơi, Chi tiết, So sánh, thanh "Đã chọn" (khả thi + lịch ngầm), trợ lý (§2.5–2.9) | `user/screens/{Explore,PlaceDetail,Compare}.tsx` (tai thỏ ở mép trên giữa màn là công tắc hai cách xem: *Lưới ảnh* · *Bản đồ lịch trình* (`ViewSwitch` ở `ui/SplitPlan.tsx`); lịch trình chi tiết là bước con của bản đồ, mở bằng nút trong bản đồ; Lịch trình không có tai thỏ, breadcrumb của nó bắt đầu bằng nút *Bản đồ lịch trình* quay về Lựa chọn với bản đồ mở, lịch thu lại vào bản đồ (`tg-nav-back`); cột lọc có "Xem và nới giới hạn" mở chat; mục "Giới hạn của bạn" trong cột lọc ghi từng giới hạn một dòng kèm số nơi bị loại, `limitLines` trong `Explore.tsx`, nơi đóng cửa mọi ngày của chuyến không có dòng; danh sách "Đã chọn N nơi" của `SelectedBar` ghi mỗi nơi: sao, loại, khu, thời lượng, giá; thẻ nơi giữ một hàng thao tác cố định chiều cao: chọn hay bỏ một nơi không làm các thẻ bên dưới dịch chỗ), `user/ui/{PlaceCard,SelectedBar,Assistant}.tsx`, `user/ui/CardTags.tsx` (thẻ nơi và thẻ chỗ ở hiện **một dòng hai khối**: khối *lợi* (xanh: điều khớp, tiện ích, cho mang thú cưng) và khối *hại* (vàng: đánh đổi, chưa rõ), mỗi khối gồm tối đa 4 tag rút ngắn cách nhau dấu phẩy, hai khối chia đều dòng; thiếu khối nào thì ghi chú xám thú cưng thế chỗ; chữ rút ngắn tối đa (bỏ "N người nhắc", "bạn muốn", nguồn "theo menu"; "Độ đông: đông" thành "Đông"); rê chuột hiện tooltip sáng với câu đầy đủ, không chữ "Lợi"/"Hại"; chính sách thú cưng không bao giờ là hại: cho phép = lợi, còn lại là ghi chú xám; thẻ đã chọn tô terracotta nhạt kèm dấu tích, không viền đen; sao Google màu vàng), `user/ui/SplitPlan.tsx` (nút đôi **Lưới ảnh | Bản đồ** ở đầu trang, cạnh tiêu đề, thay ổ khóa; Bản đồ = danh sách thành hàng gọn (ảnh cao bằng thẻ; tên, loại · thời lượng · ★, khu, tag, rồi hàng khóa · so sánh · bỏ và nút chính; không còn vạch độ tin cậy trên thẻ) trong thẻ trắng bo góc cao bằng bản đồ, bản đồ lớn bên phải chỉ hiện lịch trình với tab từng ngày (một bản đồ cho mọi ngày: đổi tab chỉ dời camera; mã, style và kết nối của bản đồ được đọc khi trang rảnh và khi rê vào "Bản đồ" (`warmMap` ở `screens/plan/TripMap.tsx`), ảnh nền offline có sẵn hiện ngay trong lúc chờ bản đồ thật), nút "Xem chi tiết lịch trình" ở góc trên phải của bản đồ lập lịch và mở Lịch trình, bản đồ phóng ra thành trang lịch (View Transition `tg-nav-plan`, `css/motion.css`), rê chuột trên hàng thì chấm nơi đó sáng lên; trên màn hẹp bản đồ phủ cả màn hình, có nút đóng), `user/ui/ExploreSide.tsx` (cột lọc trái của Lựa chọn: tìm theo tên, nhóm, khu vực; `ExploreBar` = số nơi + sắp xếp (`SortMenu`: Hợp nhất / Đánh giá tốt nhất / A→Z / Z→A; một nút bo tròn: nhãn mờ, lựa chọn đậm hơn một bậc; thẻ riêng, không `<select>`; ↑ ↓ Enter Esc) + chip bộ lọc; `browseCards` lọc / xếp trang đang xem; nhóm *Tất cả* dựng ở `Explore.tsx`), `user/ui/PlaceSheet.tsx` ("Xem chi tiết": modal mở từ lưới, anchor, trợ lý, thanh "Đã chọn"; URL `?place=<id>`, Back / Esc đóng; ảnh bay vào chỗ bằng View Transitions, không hỗ trợ thì FLIP; tab Tổng quan · Hình ảnh · Video · Xem 360° · Gợi ý lịch trình · Đánh giá (tab Hình ảnh hiện mọi ảnh qua luật không người của `photo_allow.json`, `useAllPhotos` ở `data/store.ts`, còn ảnh đầu trang chi tiết chỉ giữ vài ảnh đẹp nhất; tab Video chỉ có với nơi có clip TikTok: lưới clip dọc (ảnh bìa là keyframe của mình), rê chuột xem nhanh, bấm mở trình xem từng clip; clip luôn phát qua player nhúng của TikTok (server không giữ video): kết nối tới TikTok mở sẵn khi rê vào tab Video hay một clip (`warmPlayer`), trình xem hiện ngay keyframe của clip rồi player mờ dần lên khi sẵn sàng, clip trước và sau được nạp sẵn ở trạng thái dừng nên ↑ ↓ chuyển ngay; tab Xem 360° chỉ có với nơi có mô hình 3D, xem hàng Xem 360° bên dưới; tab Đánh giá hiện mọi lời đã thu, mới nhất trước, tải dần khi cuộn: `Reviews` trong `PlaceSheet.tsx`, `reviewsOf` ở `lib.ts`); tab Tổng quan có hàng Điện thoại (link `tel:`, số Việt Nam viết cách nhóm, đầu 0 đổi thành +84 trong link) và Trang web (mở tab mới, `rel="noopener noreferrer"`, hiện tên miền, trang Facebook hiện "Facebook") từ `identity.phone` / `identity.website` của serving record qua `projection/serving.json` (`phone`, `website` trong `Place`); thiếu thì **ẩn** hàng (`user/ui/contact.tsx`, `user/css/contact.css`); tab Tổng quan mở đầu bằng đoạn giới thiệu dựng từ dữ liệu có thật (loại, khu, điểm Google, điều hay được khen / cần lưu ý, xu hướng điểm), có thêm "Nổi tiếng vì" dưới tên và các khối của `user/ui/PlaceDetails.tsx` (Tổng tiền, Gọi món gì / làm gì, Giờ và mùa đẹp, Đường đi, Trời xấu, Đi cùng ai với x của chuyến lên đầu, Chuẩn bị, Cần cảnh báo, Nơi tương tự), mỗi dòng kèm số người nhắc và lời của họ, khối hoặc dòng không có dữ liệu thì **ẩn**, không hiện ô trống; thêm khối "Tiện ích và dịch vụ" từ danh sách của Google; `web/scripts/export_snapshot.py` đưa khối `details` của serving vào snapshot; `PlaceDetail.tsx` bọc nó ở chế độ trang cho link chia sẻ), `user/ui/useStagedList.ts` (chuyển cảnh lưới khi danh sách đổi: giữ / gỡ / thêm / thay hết), `user/pd/` (`more(group, n)` hiện trang `n` của một tab), `user/ui/Pager.tsx` (số trang dưới lưới của mọi tab: trang đầu, cuối và quanh trang đang xem; "Nơi a–b trong N"), ô tìm trên hàng tab của `Explore.tsx` (gõ là tìm trên mọi tab theo tên / loại, `read/decision/search`; kết quả ghi tab của từng nơi, cuối là nơi trùng tên không có trong gợi ý kèm lý do), `user/screens/Lodging.tsx` (tab "Chỗ ở" có số đếm như các tab khác (`useLodgingList` do `Explore` giữ); thẻ cùng markup với `PlaceCard` (nhãn loại, tim, `Trust`, phút từ trung tâm); cuối hàng thông tin có link điện thoại và trang web của chỗ ở (cùng `contact.tsx`, ẩn khi không có); lưới mọi chỗ ở trong corpus như các nhóm khác, không nhãn "cần chọn" hay lời nhắc; quanh các nơi đã chọn lên đầu, còn lại theo gu rồi điểm; chia trang bằng `Pager` như các tab khác, mỗi trang đọc `?offset=`; `set_lodging` / `clear_lodging`) | `harness` :8769 — stage `decision`, `preview`, `read/decision/lodging`, `reports` Thanh "Đã chọn" chỉ cho biết trạng thái và có nút "Lập lịch"; Lựa chọn không hiện dải cảnh báo hay gợi ý bỏ nơi (quá tải xử lý ở Lịch trình). Nút tim trên thẻ là "Lưu" (xem lại sau, huy hiệu ở thanh bên), "Thêm vào chuyến" mới đưa nơi vào danh sách xếp lịch. Khách không gọi `GET .../eve` (route chỉ cho thành viên, trả 403). Trợ lý Lựa chọn hiện thẻ địa điểm dưới câu trả lời bằng `PlaceStage` của Trip (sự kiện `places` từ `src/decision/assistant.py`, chỉ nơi công cụ trả về mà câu trả lời nhắc tên), và nút "Vì sao không gợi ý?" trên `PlaceSheet` (qua `ui/askAssistant.ts`). |
| Lịch trình, Tối ưu (§2.10) | `user/screens/Plan.tsx` (điều phối + hộp thoại) và `user/screens/plan/` (`Choose` chọn phương án (lần đầu, tờ giấy "Vì sao có N phương án?" nói bằng số vì sao lịch không chứa hết: thời gian cả chuyến so với thời gian các nơi cần, nơi nào không mở cửa trong khung giờ các ngày; nếu mỗi ngày trung bình dưới 4 giờ thì nhắc chỉnh giờ đi chơi ở trò chuyện, kèm một bảng so sánh các phương án theo cùng các hàng: vì sao có, lợi ích, hạn chế, giữ lại, tạm bỏ (tên các nơi), đi lại, chi phí, độ vững, `WaysTable`; "So sánh chi tiết" mở lại đúng bảng đó), `Overview` tổng quan, `DayView` + `reorder.ts` từng ngày kéo thả, `GhostSlot` thẻ gợi ý cho khoảng trống (nằm ngay chỗ trống của danh sách ngày: hàng tối đa 3 thẻ trắng xếp chồng từ trái qua phải như thiết kế cũ, mỗi thẻ ảnh nhỏ + tên + một dòng "≈ N phút đi thêm · giá", rê chuột đưa thẻ lên trước, bấm thẻ mở chi tiết; sau thẻ cuối là nút tròn "+": bấm "+" mở màn Thêm trải nghiệm với các nơi của khoảng trống đứng đầu; `note` của thẻ trước luôn hiện dưới hàng; ẩn khi đang kéo thứ tự), nút "Thêm trải nghiệm" là một hàng rộng nét đứt có biểu tượng "+", (dòng đường giữa hai nơi = `road_min` "≈ N phút · ước tính" (OSRM, không có hệ số đèo), đệm `buffer_min` hiện riêng; lịch cũ không có `road_min` thì lấy cả khoảng travel), `candidates.ts` + `Find.tsx` (Thêm / Đổi trải nghiệm theo thiết kế cũ: ô tìm, bộ lọc bên trái — Nguồn *Tất cả* (cả danh mục Đà Lạt trừ chỗ ở, 40 nơi mỗi lần) / *Gợi ý* / *Đã lưu*, Loại trải nghiệm theo nguồn, danh sách dài thì cuộn trong khung — và thẻ kết quả; mở đè lên nửa bản đồ của màn ngày để cột ngày bên trái vẫn thấy) + `pickers.tsx` (`LodgingPicker`: Chọn chỗ nghỉ) trên `panels.tsx` (`SidePanel` / `PlacePanel`: thẻ nổi gọn ở góc phải như danh sách gợi ý tìm kiếm — ảnh nhỏ, tên, một dòng thông tin, một dòng lý do (mã lý do của Decision như `same_kind` đổi thành câu, nơi khớp nhiều khoảng trống chỉ hiện một lần), nút ngắn *Thêm* / *Đổi* / *Chọn*; ô tìm, tab *Gợi ý* / *Đã lưu*; nơi đã lưu nhưng không thuộc lựa chọn hay dự phòng của chuyến thì *Thêm* chọn nơi đó ở Lựa chọn rồi xếp lại lịch, vì server chỉ đổi / thêm trực tiếp nơi của hai nguồn kia), `fill.tsx` (`FillSheet` bảng danh sách chữ cho Đi với / Lưu ý / Nhịp độ / Ngân sách; `TripDates` khối Ngày đi; `RouteSheet` điểm xuất phát + cách tới; sau mỗi lần lưu, `useTripEdit` dựng lại lịch rồi gọi `reload()` vì lịch giữ id của hành trình), `Journey.tsx` (màn hành trình cả chuyến, vẽ như sơ đồ lộ trình cùng bảng màu Lịch trình: mỗi ngày một bảng trắng, các mục đúng như màn từng ngày và đúng thứ tự — *Xuất phát* (tên lấy từ `useRoutes`, giờ mục đầu), khối Tự do / Nghỉ / Ăn tự chọn (kể cả "ghé chỗ ở gửi đồ" của ngày đến sớm), điểm dừng có ảnh / giờ / thời lượng, *Kết thúc ngày* — treo trên và dưới một đường nét đứt uốn lượn, tối đa 7 mốc một hàng (5 khi hẹp, 3 trên điện thoại), hàng sau chạy ngược lại; số chấm chỉ đếm điểm dừng; chặng đi ghi trên đường; đường nét đứt đi tiếp từ *Kết thúc ngày* ra rìa bảng, qua ô *Nghỉ đêm*, vào thẳng *Xuất phát* của ngày sau; cuộn tới đâu vẽ tới đó; có *Quay lại sửa*), nút "Chốt kế hoạch này" mở màn Hành trình, *Chốt hành trình* mới gọi `confirm` rồi sang Phản hồi; không còn thẻ "Giờ ghé"; `parts.tsx` thẻ bên, `TripMap`), `user/css/itinerary.css`; bố cục theo mẫu `docs/design/mock/designs/itinerary/`; `user/ui/RouteStory.tsx` (sơ đồ hành trình, mở từ Tổng quan), `user/planning/` (thẻ bên có "Chuẩn bị trước khi đi" từ `checklist` của phương án; thanh tổng kết ghi "có thể thêm tới … cho trò chơi, thuê đồ" từ `metrics.extras_max_vnd`); trợ lý chat của Lịch trình (nút bên phải, phím `/`) là `user/ui/Assistant.tsx` với `stage="planning"` (khung kính mờ trung tính; nút mở là quả cầu tròn ở mép phải; trạng thái đầu có lời chào, 4 gợi ý dạng thẻ 2×2; ô nhập dạng viên thuốc, nút gửi tròn chỉ sáng khi có chữ, quầng sáng quay quanh ô khi đang trả lời, ba chấm khi chờ), dùng chung với Lựa chọn, tin nhắn tách theo màn; `say` trong `user/planning/planning.tsx` gửi `{stage:"planning", operation:"turn", payload:{text}}`, hiện câu trả lời, thẻ nơi (không tự mở ra, tim = lưu nơi) và thẻ "Ngày N đã đổi" từ `diff.days` (bấm để mở ngày đó); lịch mới nhận như một lượt `act` (map, ngày, nút Hoàn tác có sẵn), `user/css/plan-chat.css`; chỗ ở hiện ở thẻ bên, "Đổi chỗ ở" / "Chọn chỗ nghỉ" mở thẻ chọn chỗ nghỉ bên phải (ô tìm khách sạn, tab Gợi ý / Đã lưu); chưa có chỗ ở thì hiện 3 chỗ ở Planning gợi ý, chọn ngay tại chỗ (`pick_lodging`); Lựa chọn không nhắc chọn chỗ ở; không còn thẻ "Độ tin cậy của lịch" (`plan/Trust.tsx` chỉ còn dùng cho nhãn tin cậy của thẻ nơi / chỗ ở) hay "Phương án dự phòng" (18/11/2026); khối "Ngày đi" (`fill.tsx` `TripDates`) và Trending (`plan/TripPulse.tsx`, dùng lại `home/Pulse.tsx`); banner đêm trước có thêm giờ đến / giờ về (`EveTimes`, eve `times`) | `harness` :8769 — stage `planning` (`recommend` cho Tối ưu, `turn` cho trợ lý chat) Lỗi tải (429, 409 `stale_data_version`, 5xx, mất mạng) được giải thích riêng trong `user/journeyErrors.ts`; chuyến đã chốt thay nút "Chốt kế hoạch này" bằng nhãn "Kế hoạch đã chốt". |
| Phương tiện lên Đà Lạt / Phương tiện về (§2.10) | `user/screens/plan/WayIn.tsx` (bốn thẻ Ô tô · Xe máy · Xe khách · Máy bay: giờ ước, km, giá vé, "Nhanh nhất"; chuyến chưa kiểm được hiện "Chưa rõ", không có chuyến bay đã crawl thì máy bay không bao giờ hiện "Đi được"; thẻ Xe khách / Máy bay liệt kê từng chuyến backend trả cho ngày đi (và ngày về ở Đường về): hãng/nhà xe, giờ đi–đến, điểm dừng, giá, nguồn + tuổi dữ liệu, tối đa 4 chuyến rồi "Xem thêm"; offer chỉ có link thì hiện nút link; nút mua mở trang nhà cung cấp ở tab mới và gửi `booking_click`; nút đặt phòng ở dòng Chỗ nghỉ), `user/booking.ts`, `user/css/wayin.css`; xuất phát lấy từ `searchInput.context.origin`: có toạ độ thì gửi `lat,lng`, chỉ có chữ thì gửi `origin` (tên người dùng nói) để server tra bảng thành phố; tra không ra thì vẫn hiện "Xuất phát từ <tên>" và nói chưa có dữ liệu chuyến, không bịa toạ độ; điểm xuất phát là hàng `OriginRow` (`plan/fill.tsx`): chưa có thì ô gõ địa chỉ (`/api/harness/geo`) nằm ngay trong hàng, có rồi thì tên + *Đổi* mở lại ô đó; chọn gợi ý là lưu (`{kind:"edit", target:"origin"}`); Phương tiện về không hỏi lại. Thẻ Máy bay / Xe khách có dòng *Cửa tới cửa ≈ … cho N người* (gọi xe nhà → sân bay/bến theo giá tỉnh xuất phát + vé rẻ nhất × số người + gọi xe sân bay/bến Đà Lạt → chỗ ở đã chọn, hoặc trung tâm khi chưa chọn), bấm mở từng chặng (km, hãng · dịch vụ, giá); mỗi chặng dùng hãng và loại xe đã chọn ở `tg.ride.v1`, hãng đó không có giá thì lấy hãng rẻ nhất có giá và ghi "(rẻ nhất có giá)"; chặng nào thiếu giá thì dòng ghi *Chưa ra tổng cửa tới cửa: thiếu giá …* và không cộng; thẻ Ô tô / Xe máy chỉ km và giờ. Gọi xe giữa các điểm: `plan/Rides.tsx` + `user/rides.ts` + `css/rides.css` — khi chuyến không có xe riêng (tới bằng máy bay / xe khách, hoặc đi taxi / Grab, hoặc chưa nói), mỗi ngày có thanh *Gọi xe giữa các điểm* (chọn Xe máy / Ô tô, tổng cước cả ngày theo hãng đã chọn hoặc hãng rẻ nhất) và dưới mỗi chặng một hàng ghost so ba hãng (rẻ nhất viền xanh, chip ghi dịch vụ được chọn như beTaxi 4 chỗ / taxi Lado; hãng chưa công bố giá ở vùng đó mờ đi "chưa có giá", hãng không có loại xe đang chọn mờ đi "không có xe máy"); bấm một hãng là chọn cho cả chuyến (lưu `localStorage` `tg.ride.v1`), chân trang tổng quan thêm *Gọi xe (hãng) ≈ … ước tính cả chuyến*. Xe máy: một xe mỗi người; ô tô: loại nhỏ nhất đủ chỗ | `harness` — `GET /api/harness/journey`, `GET /api/harness/booking/offers`, `GET /api/harness/rides` (`docs/BOOKING.md`), sự kiện `booking_click` |
| Dòng chi phí chỗ nghỉ (§2.10) | `user/screens/plan/LodgingCost.tsx` (dưới chi phí địa điểm ở chân trang tổng quan: số đêm × giá đêm, giá đúng ngày hay giá tham khảo Maps kèm tuổi; vượt phần ngân sách chỗ ở thì chỉ là cảnh báo, không chặn chốt), kiểu `LodgingBudget` ở `user/planning/types.ts` | `planning` — `variant.lodging_budget` (`validate.lodging_budget`), cảnh báo `lodging_over_budget` |
| Bài viết về địa điểm (`/app/posts`, nút "Bài viết" ở thanh bên) | `user/community/` — `Posts.tsx` (một màn: cột trái là các nơi có bài, cột phải là bản đồ; tab Nơi nổi bật · Bài mới · Của tôi; bản đồ trống chấm; rê chuột vào một nơi thì chấm của nơi đó hiện, nổi lên và bản đồ bay tới nơi đó (zoom 15), rê chuột ra 0,45 giây sau thì về toàn cảnh (đủ để rê tới chấm); chấm của nơi đang rê chuột có chùm tối đa ba thẻ ảnh xòe phía trên (không cần bấm; bấm một thẻ mở trình xem ảnh); rê chuột vào một bài thì chùm đổi sang ảnh của bài đó; bấm thẻ nơi thì cột trái hiện đoạn giới thiệu ngắn của nơi (`Intro` của `user/ui/PlaceDetails.tsx` đọc `details.intro`: phần tóm tắt giọng hướng dẫn viên, "Đọc thêm" mở phần thuyết minh và dòng nguồn; nơi chưa có `intro` thì `About` như cũ; kèm `KnownFor` và một lời thật của người đã đến; mọi câu có nguồn, `docs/CORPUS.md` §Giới thiệu địa điểm) rồi các bài của nơi đó, mỗi bài một thẻ (ảnh, tiêu đề, đoạn đầu, tác giả; bài biên tập của TripGuardian (`/data/posts.json`, `web/scripts/export_posts.py`) có nhãn "TripGuardian biên tập", cuối bài có dòng nguồn), nút "Xem chi tiết nơi này" mở `PlaceSheet`, `?at=<id>`; ô tìm ở đầu cột, `?q=`), `PostMap.tsx` (nền vector OpenFreeMap "positron" như bản đồ Lịch trình; không có WebGL hoặc mạng thì dùng bản ghép OSM `public/img/map`), `Search.tsx` (ô tìm không điền sẵn chữ: nơi có bài kèm ảnh, tên, sao, số bài, rồi chủ đề; Enter mở kết quả đúng chữ đã gõ; ô tìm ở trang chủ Dành cho bạn dùng cùng thành phần, thêm hàng cuối "Lên chuyến đi" và Enter vẫn mở Tìm hiểu), `Reader.tsx` (`/app/posts/:id`, trang đọc nền trắng, chữ serif; chi tiết chuyến đi là các thẻ nhỏ dưới tên tác giả; phản ứng, bình luận và bài khác về nơi đó dưới bài), `Compose.tsx` (`/app/posts/new?at=<id>`, khối chữ và ảnh thêm bằng nút, dán hoặc kéo thả; thẻ, quyền xem, chi tiết chuyến ở hộp "Sẵn sàng đăng?" thả xuống từ nút Đăng bài; nháp tự lưu), `data.ts`, `user/css/posts.css`. Bài chỉ gắn được với nơi có trong snapshot; một bài giới thiệu Khám phá 3D do TripGuardian viết tay (`community/featured.ts`, không từ corpus) được ghim: thẻ tối viền sáng chạy quanh ở đầu danh sách Nơi nổi bật / Bài mới (`FeaturedBanner` trong `Tour3d.tsx`), trong bài là các khối ảnh mô hình 3D (`tour`; chỉ hiện nơi có trong `/space3d/index.json`, bấm mở trang nơi để chọn tab Khám phá 3D) | chưa có route harness: bài, phản ứng, bình luận và nháp lưu ở `localStorage` của trình duyệt (`tg.posts.v1`), kèm vài bài mẫu gắn tag "Bài mẫu" |
| Khám phá 3D — mô hình 3D (§2.6) | `user/ui/Space3d.tsx` + `user/css/space3d.css` (tab Khám phá 3D của `PlaceSheet.tsx`, chỉ hiện với nơi có trong `/space3d/index.json`; bấm tab là chuyển cảnh ngay sang trang 3D toàn màn hình: tờ chi tiết mờ dưới lớp màu kem, ảnh chờ (ảnh tổng quan của chính mô hình) phóng mượt từ nút tab ra cả cửa sổ và tiến nhẹ vào trong, mô hình thật hiện bằng crossfade ngay khi vẽ xong khung đầu (chờ lâu thì hiện dòng nhỏ "Đang mở mô hình 3D…"); trong mô hình, tour đi bộ ở tầm mắt dọc lối đi từ điểm này sang điểm kế (qua cổng, vào thẳng trong nhà qua cửa, không nhấc mái; mẫu `scripts/diorama/index.template.html` §Walking tour), điểm không có lối nối thì vẫn bay; nơi chưa có route tay thì viewer tự dựng đường dẫn lúc nạp (`buildGuide` trong `scripts/diorama/index.template.html`: đọc mặt đất từ một lượt chụp độ cao nhìn từ trên xuống, nhận nước bằng một lượt chụp màu, mỗi chặng là đường rẻ nhất vòng qua nước / tường / bậc) rồi vẽ mũi tên và đi bộ ở tầm mắt như nơi có route (chủ dự án 11/11/2026: camera đi theo mũi tên cho đỡ quay; kéo chuột thì người dùng tự xoay, không bị giới hạn); nút Quay lại / Esc / nút Back của trình duyệt chạy ngược cảnh về thẻ ảnh trong tab; `prefers-reduced-motion` chỉ mờ dần). Mô hình chạy trong iframe cùng origin, nằm trong một lớp cố định riêng trên `<body>` (màn dive là dialog Radix không modal portal vào lớp đó). Dựng trước (warm) để vào là thấy ngay: rê chuột 150 ms, focus hoặc bấm vào tab / ảnh chờ 3D; hoặc thẻ chi tiết mở mà người dùng đứng yên 2 s trên máy ≥ 4 nhân, không bật tiết kiệm dữ liệu (không dựng ngay khi mở thẻ: iframe cùng origin chung luồng chính, thẻ sẽ khựng). Dựng xong vẽ một khung rồi tạm dừng; Quay lại thì về toàn cảnh, tạm dừng, giữ 90 s rồi gỡ (giải phóng GPU); mỗi lúc chỉ một mô hình. Mở thẻ của nơi có mô hình là tải trước script viewer, dữ liệu nơi và ảnh chờ; `web/server.mjs` cho `viewer-<hash>.js` cache vĩnh viễn, `index.json` / `places/` / `posters/` cache 5 phút kèm làm mới nền. GPU yếu (Intel / AMD tích hợp, điện thoại, phần mềm) bắt đầu không GTAO, pixel ratio ≤ 1,25, bóng 1024; máy vẫn dưới ~25 khung/giây thì tắt GTAO và về pixel ratio 1 (`web/space3d/chrome.js`), giao diện trong khung ở `web/space3d/` (`viewer.html`, `chrome.js`; `?host=full` chừa chỗ cho nút Quay lại và gửi `space3d:back` khi Esc), danh sách nơi đã duyệt ở `web/space3d/places.json`; `node web/scripts/build_space3d.mjs` sinh `web/public/space3d/`, `node web/scripts/shots_space3d.mjs <base> poster` sinh ảnh chờ | tĩnh, không gọi backend |
| Ảnh trong chat Trip | `user/screens/understand/Places.tsx` (đĩa xoay `PlaceStage`) | `trip.infrastructure.knowledge.Knowledge.view` lấy mỗi cảnh một ảnh từ `RetrievalEngine.scene_photos` (không người, không mờ); nơi chưa có nhãn giữ ảnh cũ |
| Phản hồi (§2.12) | `user/screens/Done.tsx` | `harness` — `feedback` |
| Chuyến của tôi, Đã lưu, Đã xem gần đây, Hồ sơ (§2.11) | `user/screens/{Account,Recent}.tsx`, `user/store.ts` (Đã lưu nơi theo tài khoản); Chuyến của tôi (chuyến chưa chọn nơi nào không hiện; chuyến cũ còn ở bước chat mở thì được đưa sang Lựa chọn trước, `resumeTrip`; danh sách hiện ngay bản lần trước rồi làm mới), ba tab gạch chân *Đang lên kế hoạch* (đã sang Lựa chọn hoặc Lịch trình nhưng chưa chốt: pill "Chưa chốt lịch", bấm thẻ mở đúng bước) / *Sắp đi* (pill đếm ngược: đỏ trong 7 ngày, cam trong 21 ngày, xanh xa hơn; "Đang diễn ra", "Chưa chọn ngày") / *Đã hoàn thành* (pill "Đã đi", kèm liên kết *Phản hồi*); mỗi chuyến là thẻ kiểu bộ sưu tập: ảnh ghép của tối đa ba nơi trong chuyến, ưu tiên khác loại (tham quan, ăn uống, mua sắm…), một ảnh lớn và hai ảnh nhỏ (ít nơi thì ít ô, chưa có nơi thì ảnh hero; `TripMosaic` trong `Account.tsx`), dưới ảnh là tên chuyến + pill, ngày, số người và dòng đậm "N nơi" (đã chọn / trong lịch); tên chuyến là nút mở cả thẻ, góc dưới phải có nút *Gửi cho bạn bè* và *Xóa*; không có nút tạo chuyến (chuyến mới tạo từ Dành cho bạn), đếm số nơi tham quan khác nhau trong lịch đã chốt và có "Gửi cho bạn bè" cho chuyến đã qua Tìm hiểu; Đã lưu (tiêu đề "Địa điểm yêu thích"): thẻ ảnh `tg-fav` (chip khu vực góc dưới phải của ảnh; tên + pill sao; các hàng có icon: loại, giờ mở cửa, một tag điểm cộng; dòng đậm giá tham khảo khi có; hàng nào thiếu dữ liệu thì ẩn), không nhóm theo ngày; hàng ô tab chữ nhật chỉ có *Tất cả* và các nhóm đang có nơi đã lưu (Tham quan & thiên nhiên · Ăn uống & cà phê · Mua sắm · Khác), thêm hoặc bỏ một nơi thì tab đổi theo ngay; bấm thẻ mở tờ chi tiết (`openPlace`), không chuyển sang trang `/explore/place` của luồng lập chuyến; rê vào thẻ hiện hai nút tròn *Thêm vào chuyến* và *Xóa khỏi yêu thích* (chủ dự án 11/11/2026); Đã xem gần đây chỉ hiện địa điểm, thẻ ảnh nhóm theo ngày (Hôm nay / Hôm qua / dd/mm); Hồ sơ: ảnh bìa + ảnh đại diện, tên, nickname, giới thiệu, bốn số (chuyến có lịch, đã đi, đã lưu, bạn bè) | `harness` — `trips`, `/me`, `/me/avatar`, `/me/notification-prefs`, `/calendar/disconnect`, `/me/library` |
| Hôm nay (§2.13; không có trong điều hướng, mở từ thông báo / link), Hộp thông báo | `user/screens/Today.tsx`, `user/today.ts`, `user/screens/Inbox.tsx`, `user/notify.ts`, giờ đến / giờ về sau chốt (`EveTimes` từ `plan/EveBanner.tsx`) và Trending (`plan/TripPulse.tsx`) ở cột bên, `public/sw.js`, `public/manifest.webmanifest`; event web: `user/events.ts` | `harness` — `today`, `companion`, `calendar`, `push`, `notifications`, `events` |
| Hướng dẫn có linh vật (§2.14) | `user/tour/` (`steps.ts` điểm dừng trỏ `data-tour="<id>"`, `place.ts` chỗ đứng của linh vật, `TourProvider.tsx` bọc `Shell` trong `UserApp.tsx`), `user/css/tour.css`, ảnh `public/img/tour/`; kiểm chỗ đứng: `node web/scripts/test_tour_place.mjs` | — (chỉ phía web) |
| Admin, mọi màn (§3) | `admin/AdminApp.tsx`, `admin/screens/`, `admin/api.ts` | `review` :8765 — `/api/queue`, `/api/labels{,/next,/stats,/photo,/frame}`, `/api/decision{,s}` |
| Admin: Hôm nay, Phiên, Phân tích, Insights, Nhu cầu của một nơi, Người dùng, Xu hướng tiêu dùng (§3.5–3.7, §3.9–3.10) | `admin/analytics.ts`, `admin/screens/{Dashboard,Sessions,Analytics,AnalyticsTabs,Insights,Places,Users,UserDetail,Trends}.tsx` | `analytics` :8770 (private, chỉ đọc) |

Client hành trình chung: `user/journey.ts`. Contract `/api/harness`, router, handoff và retry ở `docs/AGENT_HARNESS.md`.

Dữ liệu chỉ-đọc của corpus mà cả hai bề mặt dùng để hiển thị địa điểm: `web/public/data/snapshot.json`, sinh bằng `python web/scripts/export_snapshot.py` sau `python -m corpus aggregate`. Không có file đó thì mọi màn báo lỗi tải dữ liệu.

Chuyển trang: `router.ts` `navigate` bọc việc đổi đường dẫn trong View Transitions (`web/src/viewTransition.ts`, kiểu `user/css/motion.css`): trang cũ giữ nguyên trên màn hình tới khi trang mới dựng xong rồi hai trang giao thoa mờ ~280 ms, nên trang nặng không giật giữa chừng. Không bọc khi: chỉ đổi query (tờ chi tiết nơi), `replace`, Admin, đã có một transition đang chạy (ảnh bay của tờ chi tiết, của "Lên lịch chuyến của bạn", rời landing), hoặc trình duyệt không hỗ trợ / giảm chuyển động (khi đó `tg-flow` mờ dần 150 ms như trước). Mọi chỗ cần View Transition gọi `startTransition` ở file này, không gọi `document.startViewTransition` trực tiếp.

Các dòng của một thẻ nơi (`user/ui/cardLines.ts`): tối đa 3 lý do, đánh đổi, 2 cảnh báo. Lựa chọn chỉ có dạng lưới.

Ứng dụng (`/app`) vẽ ở 82,5% cỡ gốc (`html.tg-scaled` trong `tokens.css`, `vite.config.ts` đổi px thành rem).

Dữ liệu snapshot (hàng chục MB) được tải ngầm ngay khi đã vào app và đọc trong worker (`data/snapshotWorker.ts`, `data/store.ts`), nên mở Lựa chọn không bị khựng. Luồng chỉ có hai bước Lựa chọn · Lịch trình (`STEPS` ở `user/trip.tsx`; chat nằm cạnh danh sách, không phải một bước); `/done` (Phản hồi) là trang sau khi chốt lịch, không phải một bước.

Chạy cả stack: `README.md`. Hệ thị giác, font, màu: `docs/UX_Design_Brief.md` §7.
