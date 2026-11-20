# Bàn giao: lịch hiện nhanh, "Tối ưu lịch" ra lịch tối ưu thật, quá tải ba hướng (18/11/2026)

Chủ dự án yêu cầu ngày 18/11/2026. Phiên trước chưa làm phần này. Đọc `docs/PLANNING.md` (§Thuật toán ⓑ, §Quá tải, §Vòng người dùng sửa) trước khi sửa.

## Trạng thái (cập nhật 18/11/2026, phiên làm)

- Thay đổi của phiên 18/11 trước (§0) **đã deploy** 03:29 theo yêu cầu chủ dự án, trước khi làm phần này.
- Đã làm và **đã deploy** 18/11 04:16 (+ bản sửa `optimize.py` 04:26), **chưa commit** (DEV_LOG `planning-fast-optimal-2026-11-18`): §3A hai tầng (preview không tìm hướng, tìm hướng ở nền + pool worker khởi động sẵn), "Tối ưu lịch" tất định (`optimize.py`, không model), §3B ngưỡng `short` + dòng Lưu ý, §3C ba hướng. Chi tiết và số đo: `docs/PLANNING.md` §Tối ưu lịch, §Quá tải, §Giới hạn đã biết.
- Còn mở: lịch chính của ca quá tải nặng (`family_12_in_3` 1,3 s, `must_go_kept` 0,6 s) nằm ở vòng xử lý nơi thừa tuần tự trong `build.schedule_trip`; preview / create đạt mục tiêu theo p90, hai ca này chưa. Bấm Lập lịch ngay khi vừa chọn xong (không có thời gian xem bản đồ) thì create còn chờ việc tìm hướng (p90 1,7 s).

## 0. Trạng thái cây làm việc khi bàn giao

- Thay đổi của phiên 18/11 **chưa commit, chưa deploy**: mục `ux-speed-trends-2026-11-18` trong `docs/log/DEV_LOG.md`. Phần liên quan trực tiếp:
  - `src/planning/layout.py` `fill_first`: chưa có số ngày thì xếp đầy ngày 1 rồi mới sang ngày 2.
  - Không còn câu hỏi trước khi lập lịch; Ngày đi là khối `TripDates` (`web/src/user/screens/plan/fill.tsx`).
  - Web đã bỏ thẻ Phương án dự phòng, Độ tin cậy của lịch và nút Tổng quan ở thanh dưới màn ngày.
- Cây dùng chung với các phiên khác: chỉ commit path của mình, deploy (`./run.sh prod`) chỉ khi chủ dự án bảo.
- Không dùng GPU để test (chủ dự án 17/11). Máy có 40 lõi CPU.

## 1. Chủ dự án muốn gì

1. **Lịch hiện nhanh, gần như thời gian thực.** Bấm Lập lịch hoặc sửa lịch thì thấy lịch ngay. Lịch đầu tiên được phép chưa tối ưu đường đi. Màn chọn nơi (Lựa chọn, chế độ Bản đồ có tab Ngày 1 / Ngày 2: `web/src/user/ui/SplitPlan.tsx`, đọc `GET /api/harness/sessions/<id>/preview`) cũng phải nhanh như vậy.
2. **"Tối ưu lịch" ra lịch tối ưu thật.** Mục tiêu tối ưu:
   - đường đi ngắn nhất tính cả lượt đi và về khách sạn (chưa có chỗ ở thì tính từ nơi đầu đến nơi cuối của ngày);
   - các ngày cân đối nhau;
   - trải nghiệm tốt: đúng giờ đẹp, đủ bữa, đúng nhịp, không ngày nào quá nặng.

   Tức là tối đa hóa UX của việc lập lịch, thỏa đúng nhu cầu người dùng.
3. **Quá tải chỉ khi bất khả kháng.**
   - Trước hết rút thời gian ghé của các nơi, nhưng không bao giờ dưới một mức tối thiểu. Mức đó là ngưỡng nới cuối cùng của mỗi nơi.
   - Lịch không quá tải phải thực tế: người dùng thấy hợp lý và trải nghiệm tốt, không phải lịch chỉ đúng về toán.
   - Khi quá tải thật thì đưa **ba hướng**: tiết kiệm nhất, nhiều trải nghiệm nhất, hợp gu nhất.
   - Chủ dự án hỏi tăng thread có nhanh hơn không: xem §4.

## 2. Hiện trạng (đã đọc code 18/11)

- **Lập lịch.** `engine.create` → `_build_base` (`src/planning/engine.py` ~242) dựng một lịch chính, hoặc các hướng quá tải (`overload.py`, qua `variants.plan_cards`).
  - Thứ tự trong ngày: vét cạn khi ≤ `exact_n` (7) nơi, còn lại nearest-neighbour + 2-opt / or-opt (`days.py`, `route.py`).
  - Chia ngày: `layout.assign` (chèn rẻ nhất + `improve`).
  - Vì vậy lịch đầu đã gần tối ưu trong từng ngày; phần chậm là các lượt mô phỏng và tìm hướng quá tải.
- **Preview của màn chọn nơi.** `engine.preview` gọi cùng `_build_base`, nên khi tập nơi quá tải thì preview cũng chạy cả lượt tìm hướng quá tải (đến `realistic.overload_deadline_s` = 15 s). Đây là nghi phạm chính làm bản đồ ở Lựa chọn chậm. **Đo trước khi sửa.**
- **"Tối ưu lịch".**
  - Web: `optimize` trong `web/src/user/planning/planning.tsx` gọi `api.runRecommend`.
  - Server: `engine.recommend` (`src/planning/engine.py` ~1960) gọi **model** (`proposal_agent`, vai trò Agent) đề xuất chỉnh trên lịch cơ sở, rồi validate.

  Nó **không** phải bộ tìm đường tối ưu toàn chuyến. Kết quả hiện qua thẻ "Mình đã tìm được cách xếp tốt hơn".
- **Quá tải.**
  - Bộ xếp giờ đã rút thời gian ghé tới `short` của record trước khi bỏ nơi (`visit_key`, `time_suitability.duration_loss_min`).
  - Khi vẫn không vừa thì có bốn hướng `DIRECTIONS = ("fit", "travel", "cost", "most")` (`src/planning/overload.py` dòng 27) cùng đề xuất kéo dài ngày.
  - Mỗi việc chạy một tiến trình spawn, chung một hạn 15 s (`overload._in_children`, `_FORK_WAIT_S` 20).
- **Số đo.** Log harness có `planning_create_ms` trong dòng `Harness advance` (đo được: 0,5 ms khi trúng cache, 241 ms một lần thật). Chưa có số đo cho preview hay ca quá tải: cần đo bằng `tests/planning/bench_routes.py`, `bench_edits.py` và một ca quá tải thật.

## 3. Thiết kế đề xuất (phiên sau chốt bằng số đo)

**A. Hai tầng lịch.**
- **Nhanh** (Lập lịch, mọi lần sửa, preview của Lựa chọn):
  - chia ngày tham lam + thứ tự nearest-neighbour + một lượt 2-opt;
  - rút thời gian ghé tới mức tối thiểu khi cần; không tìm hướng quá tải.
  - Mục tiêu: preview ≤ 300 ms, create ≤ 1 s với ≤ 15 nơi / 4 ngày.
  - Nếu tập nơi không vừa ngay cả khi đã rút hết, trả lịch "chưa vừa" kèm khay nơi chưa xếp và nhãn quá tải. Ba hướng chỉ tính khi người dùng mở chúng, hoặc tính ở nền rồi đẩy về (SSE hoặc lần đọc sau).
- **Tối ưu** (nút "Tối ưu lịch"): bộ tối ưu tất định, không model, gồm:
  - (1) chia lại ngày theo cụm khu vực quanh khách sạn: mỗi ngày một vòng đi-về khách sạn, có thể thử k-means theo vị trí rồi cân đối tải;
  - (2) thứ tự tối ưu từng ngày: vét cạn tới `exact_n`, trên mức đó or-opt nhiều lượt;
  - (3) hàm mục tiêu gồm tổng phút xe (cả đi-về khách sạn), độ lệch tải giữa các ngày, phạt giờ ghé (`time_suitability`), bữa ăn, nhịp `per_day`.

  Bộ tối ưu chỉ nhận kết quả khi tốt hơn lịch hiện tại theo hàm này và qua validator. Lịch người dùng đã tự kéo thả: hỏi trước khi thay (đã có `pickAsk` / `dropAsk` làm mẫu). Có thể giữ model proposal làm bước sau (giải thích bằng lời), không làm bước tìm.
- Chạy song song: nhiều tập chia ngày ứng viên đánh giá trong process pool (40 lõi); thứ tự từng ngày độc lập nên song song hóa tự nhiên.

**B. Mức tối thiểu khi rút thời gian ghé.**
- Hiện đã rút tới `short` của record. Cần làm rõ và kiểm bằng test hai điều: không bao giờ dưới `short`; thời lượng người dùng nói (`source: user`) không rút.
- Ghi vào `docs/PLANNING.md` như "ngưỡng nới cuối".
- Lịch vừa nhờ rút thì phải ghi chữ cho người dùng (nơi nào ghé ngắn hơn bao nhiêu) ở mục Lưu ý.

**C. Quá tải: ba hướng.**
- Khuyến nghị: giữ **ba**, đúng như chủ dự án nêu:
  - `cost`, tiết kiệm nhất;
  - `most`, nhiều trải nghiệm nhất (giữ nhiều nơi nhất);
  - `fit`, hợp gu nhất.
- Bỏ `travel` thành một hướng riêng: khi bộ tối ưu (A) luôn chạy trên mỗi hướng thì "ít ngồi xe" là thuộc tính của mọi hướng, không còn là lựa chọn. Hai hướng có lúc trùng nhau thì gộp và chỉ hiện các hướng khác nhau (đã có luật bỏ phương án trùng).
- Màn Chọn phương án (`web/src/user/screens/plan/Choose.tsx`, `WaysTable`) đổi theo; bỏ dòng "Di chuyển thuận lợi nhất".

## 4. Trả lời "tăng thread có nhanh hơn không"

- Các hướng quá tải đã chạy song song, mỗi hướng một **tiến trình** (Python GIL: thread không giúp việc tính toán thuần CPU).
- Thêm tiến trình chỉ nhanh hơn khi chia nhỏ việc *bên trong* một hướng: thử các tập nơi con, thứ tự từng ngày.
- Giới hạn thật là chi phí khởi động tiến trình spawn (nạp lại module) và hạn chung 15 s.
- Hướng làm: process pool khởi động sẵn một lần khi harness warm (không spawn mỗi lần), chia việc theo tập con / theo ngày.
- Đo trước: thời gian spawn so với thời gian tính của một hướng trên ca quá tải thật.
- **GPU không giúp** (chủ dự án hỏi 18/11):
  - Việc tốn thời gian là mô phỏng từng ngày (giờ mở cửa, bữa ăn, giờ ghim, đệm), rẽ nhánh nhiều và viết bằng Python, không phải phép tính ma trận lớn.
  - Kích thước nhỏ (≤ 5040 thứ tự một ngày), nên chi phí chép dữ liệu sang GPU lớn hơn phần lợi.
  - Chỉ riêng tổng phút xe của mọi hoán vị thì tính được trên GPU, nhưng đó không phải chỗ chậm.
  - GPU còn để dành cho video (chủ dự án 17/11).
  - Đòn bẩy đúng: 40 lõi CPU qua process pool khởi động sẵn, cộng cache mô phỏng sẵn có.

## 5. Tiêu chí xong

- Preview Lựa chọn và lịch đầu: p90 đạt mục tiêu §3A trên các ca `tests/planning/realistic_cases.py` và một chuyến thật quá tải. Ghi số đo vào `docs/PLANNING.md`.
- "Tối ưu lịch":
  - không bao giờ tệ hơn lịch hiện tại theo hàm mục tiêu;
  - tổng phút xe (cả đi-về khách sạn) giảm hoặc bằng trên bộ bench;
  - không vi phạm validator;
  - không model trong vòng tìm.
- Quá tải chỉ khi rút về `short` vẫn không vừa; tối đa ba hướng `cost` / `most` / `fit`, không hiện hướng trùng.
- Test: cập nhật `tests/planning` (golden bằng `UPDATE_GOLDEN=1`, chỉ khi diff là thay đổi có chủ đích), thêm test cho ngưỡng `short`, cho ba hướng, cho bộ tối ưu.
- Web (`Plan.tsx`, `Choose.tsx`, `SplitPlan.tsx`): chụp ảnh qua Vite 5211, đăng nhập bằng `DEV_ACCOUNT_*` trong `.env` (cách đăng nhập: memory `dev-login-account-in-env`).
- Cập nhật `docs/PLANNING.md`, `docs/UI_SPEC_USER_WEB.md`, DEV_LOG.
