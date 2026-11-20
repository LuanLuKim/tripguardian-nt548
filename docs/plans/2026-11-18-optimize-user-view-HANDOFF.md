# Bàn giao: "Tối ưu lịch" nhìn từ phía người dùng (18/11/2026, 04:40)

Chủ dự án hỏi (18/11): đã xem lịch "Tối ưu lịch" xếp ra dưới góc người dùng chưa; đánh giá rồi cải thiện khâu đó. Phiên trước làm dở thì được bảo bàn giao. Đọc trước: `docs/PLANNING.md` §Tối ưu lịch, `src/planning/optimize.py`, `Engine.recommend` / `_optimize_inputs` / `_fresh_layout` trong `src/planning/engine.py`.

## 0. Cập nhật 18/11 (phiên sau): §3 bước 1–3 xong, chưa deploy, chưa commit

- 3 ca ở §2 đã sạch. Nguyên nhân thật:
  - Bữa lỡ của hàm mục tiêu đếm cả bữa mà khung giờ đã qua trước khi ngày bắt đầu (ngày tới 14:00 "lỡ bữa trưa"), nên lịch tự động bị phạt oan. Nay `optimize.meals_missed` bỏ trường hợp đó.
  - Lịch tự động bị chấm lại bằng `simulate_order` nên mất `unpinned` (giờ đẹp nó bỏ vì giờ mở cửa) và validator báo `timed`. Nay seed truyền nguyên `DayResult`, mỗi ngày chọn phương án theo vi phạm validator của ngày → bữa lỡ → `day_value`; act `optimize` mang `unpinned` để đường sửa lịch giữ đúng.
  - `PIN_LOST` 45 → 90: với 45, `reorder_fine` từng bỏ hoàng hôn Công Viên Yersin để bớt 105′ nghỉ ở chỗ ở.
- Chưa làm: §3 bước 2 (đưa bộ kiểm người dùng vào `improves`) không cần nữa vì mọi lịch sau Tối ưu đã qua bộ kiểm; để dành nếu thấy ca mới. §3 bước 4–5 (deploy, thử trên prod) chờ chủ dự án.
- Số đo, test: `docs/PLANNING.md` §Tối ưu lịch, DEV_LOG `planning-fast-optimal-2026-11-18`.

## 1. Trạng thái

- **Prod** (bản đông cứng 04:26) đã có: lịch hiện nhanh, quá tải ba hướng, "Tối ưu lịch" tất định, phạt ngày bị bỏ trống. Deploy 04:16 là deploy đầy đủ, 04:26 chỉ `src/` (đông cứng + khởi động lại như `./run.sh prod`, không build web). Lý do: cây web đang có việc dở chưa duyệt của phiên khác (`Account.tsx`, `css/screens.css`, `css/home.css`).
- **Trong cây, chưa deploy, chưa commit** (sau 04:26):
  - `src/planning/optimize.py`
    - Thêm `seeds`: lịch tự động (schedule_trip) của đúng tập nơi luôn được chấm. Mỗi ngày thử cả thứ tự lịch tự động đưa ra (`build.simulate_order`) lẫn thứ tự tìm được.
    - Hàm mục tiêu thêm: `idle_min` (chờ / ngồi không quá `IDLE_FREE_MIN` 30′, ×0,5), `times_lost` (giờ đẹp bị bỏ, `PIN_LOST` 45 mỗi nơi), `late_min` (về sau giờ kết thúc ngày, ×2).
    - `improves`: nếu bớt được vi phạm hoặc bữa lỡ thì được đi thêm xe; nếu chất lượng ngang nhau thì vẫn không bao giờ tăng phút xe.
  - `src/planning/engine.py`
    - `_fresh_layout` tách ra từ `_rebuild_variant`; `_rebuild_variant` gọi lại nó.
    - `_optimize_inputs` thêm `seeds`, tách `held` (khóa, giờ người dùng đặt, các chỗ người dùng tự sắp với `keep_mine`) khỏi `fixed` (`held` + nơi bình minh, chỉ dùng cho bước tìm).
  - `tests/planning/bench_judge.py` (mới): in mọi ca `realistic_cases` dạng chữ, trước và sau Tối ưu, trên lịch đầu ("fresh") và sau khi dời nơi cuối mỗi ngày sang ngày kế ("shuffle"). Chạy `realistic_checks.CHECKS` cho từng lịch.
  - Test đã chạy: `pytest tests/planning/test_planning_optimize.py tests/planning/test_planning_fast_plan.py tests/planning/test_planning_proposal.py` xanh 14/14. **Chưa chạy lại** `tests/planning` đầy đủ sau các sửa này; chưa chạy lại `bench_optimize.py`.

## 2. Đã thấy khi đọc lịch

Chạy: `.venv/bin/python tests/planning/bench_judge.py <thư mục>`. Script phải giữ `if __name__ == "__main__"`, nếu không worker spawn của bộ tìm quá tải chạy lại cả script và hết hạn ("chưa xếp xong").

- **Lịch đầu:** cả 17 ca không có sửa tay qua hết các bộ kiểm.
- **Shuffle rồi Tối ưu, trước các sửa ở §1:** 9 ca còn lỗi người dùng thấy ngay.
  - Ví dụ `hotel_breakfast`: ngày 1 ngồi không ở chỗ ở 14:00–15:33, Ga Đà Lạt lúc 19:47 (lỡ hoàng hôn 16:15–17:10), về chỗ ở 21:37 (quá giờ 21:00).
  - Vẫn được nhận vì số vi phạm validator bằng lịch trước (2) và điểm thấp hơn. Lịch tự động thì không có vi phạm nào, nhưng bộ tìm trên ma trận không với tới nó.
- **Sau các sửa ở §1:** còn 3 ca.
  - `couple_slow_dawn`: ngày 3 thiếu bữa trưa; lịch trước Tối ưu cũng thiếu, Tối ưu không sửa được.
  - `friends_packed_bar`: hết về quá giờ, nhưng thành ngày 2 thiếu bữa trưa, và ngày 1 đi 133′ trong khi nearest-neighbour 111′ (`travel_vs_nn`). Cần xem Tối ưu có đổi một lỗi lấy lỗi khác không (bữa lỡ đang so theo `meals_missed` của note mô phỏng, có thể khác cách `realistic_checks.meals` đếm).
  - `seven_days`: Săn mây Panorama Cầu Đất ngày 6 lúc 09:24, ngoài giờ hoàng hôn 16:15–17:10, không có lý do vật lý. Trước Tối ưu lỗi này ở ngày 3: nơi bình minh / hoàng hôn vẫn bị giữ theo ngày hiện tại trong bước tìm (`fixed`), nên chỉ lịch tự động gỡ được, và ở ca này nó không thắng.

## 3. Việc tiếp theo

1. Chạy lại `bench_judge.py` và đọc từng file của 3 ca trên. Quyết định bằng lịch thật, không chỉ bằng số.
   - Bữa ăn: so `objective` (`meals_missed` từ `DayResult.notes`) với `realistic_checks.meals`. Nếu cách đếm khác nhau thì đưa luật của bộ kiểm vào hàm mục tiêu (bữa là thứ người dùng thấy đầu tiên).
   - Giờ đẹp: `times_lost` chỉ đếm `unpinned`. Lịch xếp nơi có ghim ra ngoài khung mà không ghi `unpinned` thì không bị phạt; nên đếm theo `realistic_checks.timed` (giờ ghé có nằm trong khung ghim không).
2. Cân nhắc đưa thẳng các bộ kiểm người dùng (`no_long_wait`, `meals`, `timed`, `open_hours`, `frame_kept`, `pace_kept`) vào điều kiện nhận của `improves`: lịch mới không được có lỗi người dùng nào mà lịch cũ không có. Hiện chúng chỉ nằm trong test (`tests/planning/realistic_checks.py`); muốn dùng ở runtime phải chuyển phần cần thiết vào `src/planning` (không import từ `tests/`).
3. Sau khi sửa: chạy `pytest tests/planning tests/harness`, `bench_optimize.py` (thường và `--shuffle`), `bench_judge.py`. Cập nhật `docs/PLANNING.md` §Tối ưu lịch (hàm mục tiêu mới, luật nhận, số đo) và DEV_LOG `planning-fast-optimal-2026-11-18`.
4. Deploy chỉ khi chủ dự án bảo.
   - Nếu cây web vẫn còn việc dở chưa duyệt của phiên khác: deploy chỉ `src/` như 04:26. Cách làm: source `run.sh` dòng 1–458 với `PYTHON` tuyệt đối và `cd` lại thư mục repo, rồi `freeze_src`, dừng dịch vụ, `swap_frozen_src`, `restart_services`. Chạy tách khỏi terminal, đọc dòng `[smoke]` trong `logs/run/deploy.log`.
   - Không thì `./run.sh prod` đầy đủ (`HARNESS_GPU=0 SKIP_CLEF=1`). 04:53 phiên Account đã deploy riêng web (Chuyến của tôi / Đã lưu), nên việc dở đó không còn là lý do tránh deploy đầy đủ; vẫn kiểm `git status web/` trước khi chạy.
5. Thử thật trên prod: Playwright qua Vite 5211, đăng nhập `DEV_ACCOUNT_*`. Phải sửa header `Origin` cho **cả** `/api/auth/` lẫn `/api/harness/`, nếu không POST bị 403. Chuyến planning của tài khoản dev đọc từ `/api/harness/trips`, mở bằng cách đặt `localStorage['tg.trip.v1'] = {journeyId, decisionId, planningId}`, bấm "Xem lịch" rồi "Tối ưu lịch". Nếu lịch bị đổi thì bấm "Giữ lịch cũ" để trả nguyên trạng.

## 4. Lưu ý

- Test `tests/decision/test_wish_speed.py` (ngân sách 120 ms) hỏng khi máy tải, code Decision không đổi; không thuộc việc này.
- Khi chạy một mình, test `pg` cần `TEST_DATABASE_URL`: `.env` có sẵn, nạp qua dotenv khi chạy cùng test khác. Không chạy test vào `DATABASE_URL` của prod.
- Commit: chỉ path planning của việc này. Không lẫn landing (phiên khác) hay Account (phiên khác). Chưa ai bảo commit.
