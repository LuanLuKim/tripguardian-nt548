# Bàn giao: đánh giá hệ thống và hướng cải thiện kiến trúc (2026-11-10)

Phiên trước được chủ dự án giao đánh giá toàn hệ thống (sản phẩm, thuật toán ba giai đoạn, UI/UX, tài liệu, cấu trúc repo, production). File này giữ kết quả đánh giá, việc đã làm, việc còn dở và thứ tự nên làm tiếp. Phiên nhận tập trung vào **cải thiện kiến trúc**; phần sản phẩm ở §4 là phản hồi để chọn việc.

Mỗi nhận định ghi rõ nguồn. Chỗ ghi "chưa kiểm" là suy đoán, phải kiểm trước khi sửa.

## 0. Cập nhật 11/11/2026 (đọc trước)

Chủ dự án quyết định: màn Chọn nơi **không bao giờ** nhắc hay chặn khi chọn ít; gợi ý thêm chỉ qua ghost place trong Lịch trình. Mục 3 ở §4 bị loại.

Đã làm (cùng commit với file này):

- Baseline Planning xanh. Ba ca `realistic_cases` (`worker_meeting`, `family_kid_nap`, `short_by_40`) trôi theo dữ liệu: chỗ ở thay Homestay Lily cách trung tâm ~70 phút, Thung lũng Tình Yêu giờ 3–5 giờ và đóng 17:00. Đã chỉnh ca, giữ ý định ban đầu. `an_hour_short` chỉ trượt vì hạn giờ khi máy tải. `qa_sweep` bỏ qua khi thiếu công cụ (chưa từng vào git). Golden lệch 1 phút do quy tắc dời nơi.
- Lỗi thật đã sửa: thẻ hướng khác sau khi chọn một hướng ghi nhầm nơi không vừa là "Bạn đã bỏ khỏi lịch" (`engine._offered_variants`). Ngày bình minh kéo về đầu khung (05:30) dù nơi mở 06:45 (`layout._first_entry`).
- Vận hành (A1 phần phát hiện, A2, A3): `RELEASE` trong `.prod_src`, `.prod_src.prev`, `./run.sh prod-restart | prod-rollback | prod-check`, `scripts/config_check.py` chạy khi đông cứng. CI: Python 3.12, job build web.
- Đo: phiếu phản hồi hỏi "Bạn còn phải tìm gì?" (migration 008). Header `X-TG-Synthetic` từ E2E và smoke; analytics mặc định loại hành trình đó. Sửa CSS chip đang chọn mất chữ khi rê chuột.
- Ca E2E `elderly_slow_family`: trợ lý lúc đó chưa ghi được giờ ăn (`frame.meals.by` thêm sau lần chạy). Ca `contradiction_slow_but_many`: người dùng đổi sang đi nhiều nơi, `pace = packed` là đúng, tiêu chí chấm cũ sai.

Còn mở: A1 đầy đủ (đông cứng `config/` cùng release), A4 (systemd, cảnh báo), A5–A7, A9, A10; chữ đầu tiên của Trip (cần đo lúc máy rảnh, và đổi luồng kiểm lời của Clef trước khi hiện); Chọn nơi mở mặc định ở shortlist (chủ dự án chưa quyết, nghiêng về không giới hạn); mức chi cao cấp chưa vào điểm; khung mặc định 14:00 / 12:00; chạy lại E2E sau deploy; tìm hướng quá tải quá hạn ("chưa tìm xong các hướng", E2E `contradiction_slow_but_many`): `route.order_day` vét cạn ngày 7 nơi suýt vừa tốn ~2 s mỗi lần thử (ca 10 nơi / 2 ngày: tìm nối giờ 10 s). Đã thử cho các lần thử dùng `exact_n = 6`: nhanh 9,9 s → 0,6 s nhưng đổi thẻ hướng `cost` ở `test_lodging_before_a_direction_choice…`, nên chưa áp dụng; cắt tỉa theo cận dưới đường đi không giúp vì các ngày đó đều còn vi phạm; bố cục mobile 390 px của màn Phản hồi lộ rail và link "Bỏ qua điều hướng" (có sẵn từ trước, `frontend_images/2026-11-11-feedback-search-for/done-mobile.png`).

## 1. Trạng thái khi bàn giao

**Đã sửa trong working tree, chưa commit, chưa deploy:**

| Việc | File | Kiểm chứng |
|---|---|---|
| Ngày trống nhận một nơi khi tổng đường tăng ≤ `spread_extra_min` (default 45, trong `settings.py`) | `src/planning/{layout,settings}.py`, `tests/planning/test_planning_layout.py` | 21 test layout đạt; 4 nơi cùng khu / 3 ngày ra 2-1-1 thay vì 4-0-0 |
| `day_conditions` mang `weather_cause`; web gọi đúng nguyên nhân thay nhãn cố định "Mưa lớn hoặc dông" | `src/planning/{conditions,build,engine}.py`, `web/src/user/screens/plan/parts.tsx`, `web/src/user/planning/types.ts`, `tests/planning/test_planning_conditions.py` | 30 test conditions đạt; `tsc -b` sạch; ảnh `frontend_images/2026-11-10-weather-cause/conditions.png` |
| Ba câu tài liệu sai so với code | `docs/AGENT_HARNESS.md` §1 (Clef không đứng trước Agent), §2 (cổng lập lịch không cần read-back), `README.md` (`HARNESS_GPU` mặc định 0) | đối chiếu `src/trip/api/engine.py`, `src/harness/dispatch.py`, `run.sh` |
| Ghi nhận prod đọc `config/` trực tiếp | `docs/OPERATIONS.md` §1, `docs/log/AGENT_FAILURES.md` F004, `docs/log/DEV_LOG.md` | — |

**Test Planning còn dở.** Chạy đủ `tests/planning` với thay đổi trên: 1154 đạt, 15 trượt. Chạy lại 15 test đó với hành vi cũ (`spread_extra_min = 0`): 10 vẫn trượt, tức đã hỏng sẵn trong working tree:

```text
test_planning_engine.py::test_lodging_before_a_direction_choice_updates_its_explanation_and_tray
test_planning_overload.py::test_an_hour_short_offers_a_longer_day_that_holds_everything
test_planning_overload_parallel.py::test_spawned_hung_child_is_killed_by_the_shared_deadline
test_planning_overload_round1.py::test_fitting_places_does_not_waive_the_days_fixed_meals[family_kid_nap, worker_meeting]
test_planning_overload_round1.py::test_reviewed_case_matches_independent_expectations[family_kid_nap, short_by_40, worker_meeting]
test_planning_qa_sweep.py::test_sweep_uses_real_handoff_shape_and_valid_meal_wishes
test_planning_realism.py::test_realism[overload_explained]
```

Năm test đạt với hành vi cũ nhưng trượt trong lần chạy đủ, **chưa chạy lại với giá trị 45** (bị ngắt khi chủ dự án yêu cầu dừng mọi tiến trình):

- `test_planning_lodging_golden.py::test_the_lodging_variants_of_the_sample_trip_match_the_golden_file`: nhiều khả năng đổi thật do quy tắc dời nơi. Xem diff rồi mới `UPDATE_GOLDEN=1`.
- Bốn test trong `test_planning_overload_parallel.py` (`a_timed_out_child_takes_its_grandchildren_with_it`, `children_share_one_deadline_and_keep_a_fast_answer`, `deadline_keeps_a_checked_main_draft_when_directions_are_slow`, `the_longer_day_is_searched_while_the_directions_are`): đều là test hạn giờ, máy lúc đó tải ~60 trên 40 lõi. Nghi do tải, chưa kiểm.

**Vận hành hôm nay.** 23:30 chủ dự án yêu cầu dừng mọi tiến trình để admin thêm GPU (máy giờ có 3 card). 23:45 bật lại: prod khởi động từ `.prod_src/` và `web/dist` sẵn có (không freeze, không build) với `HARNESS_GPU=2`, harness dev `:8779` cũng ở GPU 2; smoke và keepalive đạt. Cron `@reboot` vẫn dùng mặc định GPU 0. `run.sh` không có chế độ khởi động lại mà không deploy, nên phiên trước phải nạp hàm của `run.sh` trong một script tạm.

## 2. Số đo làm căn cứ

| Nguồn | Số |
|---|---|
| Ma trận E2E 48 ca `dev-ux-20261109` (`.superpowers/sdd/2026-11-03-prod-e2e/matrix/runs/`) | kiểm tự động 1082/1092; tiêu chí thỏa nhu cầu: đạt 0,625, đạt + một phần 0,883 |
| Cùng lần chạy, độ trễ | `chat_first_word` p50 5,5 s, p90 14,5 s (ngưỡng 8); `chat_turn` p50 6,3 s, p90 15,2 s, max 48 s; `plan_generate` p50 2,6 s, p90 13,5 s, max 49 s; `confirm` p90 8,2 s (ngưỡng 2) |
| Postgres prod, bảng `feedback` (18 dòng, 10 dòng có `more_search`) | 7/10 trả lời vẫn phải tìm thêm ở ngoài; `realistic` trung bình 3,2/5 (9 phiếu); cả hai ghi chú chữ đều nêu **lịch có ngày trống** |
| Postgres prod, bảng `events` (gồm cả bot E2E, 19/64 tài khoản có email kiểu test) | `journey.create` 1136 → `trip.turn` 784 → `trip.advance` 541 → `decision.advance` 419 → `planning.confirm` 323 → `today_open` 21 |

Phễu trên không tách được người thật khỏi bot. Đây là khoảng trống đo lường (§5 P1).

## 3. Kiến trúc và production

Đánh giá chung: ranh giới module, mô hình constraint ba loại, `unknown` ≠ `false`, solver tất định kiểm lại đề xuất của model, journey pin corpus release đều là quyết định đúng và được test chặn. Điểm yếu nằm ở **lớp vận hành quanh code**, không ở thiết kế miền.

| # | Vấn đề | Bằng chứng | Hướng sửa |
|---|---|---|---|
| A1 | Chỉ `src/` được đông cứng. Prod đọc `config/*.yaml` và `data/` từ working tree; mọi loader đều từ chối khóa lạ. Một phiên dev thêm khóa config làm prod lỗi ở lần nạp kế. | `run.sh` `freeze_src`; F004 | Đông cứng `config/` cùng `src/` thành một thư mục release; code tìm `config` qua một hàm gốc thay vì `Path(__file__).parents[N]` rải rác |
| A2 | Deploy lấy code từ working tree chưa commit, không ghi commit, xóa ngay `.prod_src.old`. Không biết prod đang chạy bản nào, không rollback được. | `run.sh` `swap_frozen_src`; `git status` 689 thay đổi chưa commit trên nhánh `chore/prod-cleanup-20261109` | Release có id (`git rev-parse` + cờ dirty) ghi vào log và `/me` hoặc một file; giữ bản trước; lệnh `prod-rollback` |
| A3 | Deploy dừng dịch vụ cũ trước, warm-up khoảng 2 phút: mỗi deploy là downtime. Không có `prod-restart` không build. | `docs/OPERATIONS.md` §1; §1 file này | Thêm `prod-restart`; về sau khởi động bản mới ở cổng phụ, warm xong mới đổi proxy trong `web/server.mjs` |
| A4 | Tiến trình chạy bằng `nohup`, chết thì không tự lên. `keepalive.py` chỉ ghi log, không cảnh báo, không kiểm DB hay model. | `docs/OPERATIONS.md` §1, §5 | Unit `systemd --user` (linger đã bật) với `Restart=on-failure` cho harness, public, notify, tunnel, 9router; keepalive gửi cảnh báo khi lỗi liên tiếp |
| A5 | Agent của prod đi qua một tiến trình 9router cục bộ. Đó là điểm lỗi đơn và trần tải theo một tài khoản. | `docs/LLM_PROVIDER.md` bảng vai trò | Đo tỉ lệ lượt rơi về `policy.py`; ghi rõ trần số người dùng đồng thời; có endpoint dự phòng trong config |
| A6 | Harness là một tiến trình `ThreadingHTTPServer`; Planning nặng CPU chạy trong cùng tiến trình (có worker `spawn` cho quá tải). Prod dùng chung máy với job thí nghiệm, tải 60/40 lõi. p90 ở §2 có phần do tải máy. | `src/harness/protection.py`; `uptime` | Trước khi tối ưu code, đo lại độ trễ khi máy rảnh. Nếu cần nhiều tiến trình: kiểm khóa journey có dùng được qua tiến trình không (chưa kiểm) |
| A7 | Nhiều phiên agent sửa cùng một working tree, trong khi prod deploy từ chính tree đó. 10 test Planning đang trượt mà không ai chịu trách nhiệm. | §1; `docs/log/AGENT_FAILURES.md` F002, F003 | Mỗi phiên một worktree; chỉ deploy từ commit đã qua test; khôi phục baseline xanh trước |
| A8 | CI chỉ chạy `pytest` trên Python 3.13 (prod 3.12.13), không build web, không `tsc`, không lint. | `.github/workflows/test.yml` | Thêm job `npm run build` (đã gồm `tsc -b`), đổi sang 3.12, thêm `ruff` mức tối thiểu |
| A9 | Khoảng trống bảo mật đã tự liệt kê nhưng chưa xử lý: giới hạn theo IP khai báo mà không dùng, không có CSP / `frame-ancestors`, email không xác nhận khi đăng ký. | `docs/SECURITY.md` §8 | Làm theo thứ tự trong chính mục đó |
| A10 | Bốn file quá lớn: `planning/engine.py` 2330 dòng, `trip/api/engine.py` 2102, `corpus/llm/tasks.py` 1910, `harness/dispatch.py` 1134. | `wc -l` | Chỉ tách khi sửa tới (`RULE.md` §4); ưu tiên tách phần dựng view khỏi phần điều phối |

## 4. Phản hồi về sản phẩm và thuật toán

**Vấn đề số một: lịch có ngày trống.** Khoảng 20/48 ca E2E có ngày cuối không hoạt động, và cả hai ghi chú phản hồi thật đều nêu điều này. Bốn nguyên nhân:

1. Khung mặc định ngày đầu bắt đầu 14:00, ngày cuối kết 12:00 (`config/trip.yaml` `frame`). "2 ngày" không nói giờ thành 7 giờ + 4 giờ.
2. Bộ chia ngày chỉ dời nơi sang ngày trống khi tổng đường không tăng. Đã sửa (§1), chưa deploy.
3. Màn Chọn nơi không báo chọn thiếu. `web/src/user/ui/SelectedBar.tsx` có đủ `totals.needed` và `totals.available` nhưng ghi chú trong code nói "never stops or nudges". Một dòng thông tin kiểu "mới đủ khoảng 1/3 ngày" không chặn ai. **Đây là quyết định của chủ dự án.**
4. Chọn một nơi cho ba ngày thì chỉ còn gợi ý mờ (`ghosts`). Nguyên tắc "không tự thêm địa điểm" đúng, nhưng thiếu một nút "lấp ngày này bằng gợi ý đã kiểm" (đã có mẫu `repair_meals`).

**Các điểm khác, theo mức ảnh hưởng:**

| Chỗ | Quan sát | Nguồn |
|---|---|---|
| Trip | Chữ đầu tiên của trợ lý tới sau p50 5,5 s vì lời chỉ gửi khi đã là bản cuối. Người dùng thấy "Đang tìm hiểu" lâu. | §2; `docs/TRIP_UNDERSTANDING.md` §4 |
| Trip | Cổng hỏi lại điều đã nói (4 ca), ghi sai fact (3 ca), đoán sai cách tới (1 ca). Ca ngày mơ hồ: lịch có ngày cụ thể dù người dùng chưa nói ngày. | E2E `repeat_question`, `facts_chat`, `vague_user_chill`, `ambiguous_dates_next_weekend` |
| Planning | Điều người dùng nói rõ không vào lịch: bữa tối trước 18:00 (xếp 18:36, 18:59), nhịp chậm mà ngày 1 có 8 lượt ghé. | E2E `elderly_slow_family`, `contradiction_slow_but_many` |
| Planning | Bữa ăn phần lớn để "tự chọn" nên tiêu chí "có quán thật" trượt ở nhiều ca. | E2E `lunch_only_busy_traveller`, `family_kid8_selfdrive` |
| Planning | Ngày bị kéo về 05:30 rồi "Tự do quanh đây 80 phút" trước điểm đầu lúc 07:00. Nghi `pull_early` kéo sớm khi không cần, chưa kiểm. | `frontend_images/2026-11-10-ui-refresh/final/11-lich-trinh-chon-ngay.png` |
| Decision | Màn mở ra 333 nơi trong 12 tab, trong khi luận điểm sản phẩm là "tập quyết định nhỏ". Nhãn "Hợp nhất" đã có; nên mở mặc định ở shortlist, phần còn lại là "xem tất cả". | `frontend_images/2026-11-10-ui-refresh/explore/01-explore.png`; `docs/Project_Context.md` §2 |
| Decision | Mức chi "cao cấp" không đổi thứ hạng; chưa có tín hiệu phân khúc giá trong điểm. | E2E `couple_honeymoon_luxury` |
| Đo | 7/10 phiếu vẫn tìm thêm ở ngoài, nhưng không biết tìm gì. Phiếu phản hồi chưa hỏi. | bảng `feedback` |

## 5. Tài liệu và cấu trúc repo

**Tài liệu.** Nội dung đúng và có trỏ vào code, nhưng ba file giai đoạn đã vượt mức đọc được:

- `CORPUS.md` 202 KB, `TRIP_UNDERSTANDING.md` 131 KB (khoảng 59 nghìn token, một agent không đọc hết trong một lần), `PLANNING.md` 107 KB. Có đoạn dài 4.500 ký tự không xuống dòng.
- Vi phạm `RULE.md` §0.1 (không viết lịch sử): mốc ngày xuất hiện 36 lần ở `CORPUS.md`, 14 ở `TRIP_UNDERSTANDING.md`, 11 ở `PLANNING.md`; cụm kiểu "đã gỡ / không còn / trước đây" lần lượt 15, 26 và 25 lần. `TRIP_UNDERSTANDING.md` §5 mô tả song song hai luồng theo cờ `discovery`.
- Năm file UI chồng nhau: `UI_SPEC_USER_WEB`, `UI_SPEC_FLOW_LAYOUT`, `UI_SPEC_LANDING`, `Role_Web_Functional_Design`, `UX_Design_Brief`.
- Đề xuất: mỗi file giai đoạn chỉ giữ contract, thuật toán, cấu hình, giới hạn (mục tiêu khoảng 300 dòng). Hành vi chi tiết theo từng câu chữ chuyển về docstring và tên test. Quyết định của chủ dự án kèm ngày gom về một file riêng (cần chủ dự án đồng ý vì `RULE.md` §0.1 hiện không có loại tài liệu này). `docs/plans/` có 15 file, nhiều file đã làm xong cần gộp rồi xóa theo đúng rule.

**Cấu trúc repo.**

| Chỗ | Vấn đề | Đề xuất |
|---|---|---|
| `.superpowers/sdd/2026-11-03-prod-e2e/` | Thư mục của một công cụ đang chứa bằng chứng E2E và state stack đo; `README.md` §Test và `web/src/user/screens/plan/notes.test.mjs` trỏ vào đó | Chuyển sang `data/e2e/`, sửa hai chỗ trỏ |
| `web/src/user/screens/plan/notes.{test.mjs,fixture.tsx}` | Test nằm trong `src`, còn lại ở `web/scripts/test_*.mjs` | Một quy ước |
| `frontend_images/` (246 MB) và `web/shots/` | Hai nơi chứa ảnh chụp UI | Giữ `frontend_images/`, chia theo ngày như các thư mục mới |
| Gốc repo | `Screen Recording 2026-11-10 130529.mp4` trái `RULE.md` §0.3 | Chuyển NAS |
| `scripts/diorama/` + `tests/diorama/` | Một dự án con (engine, kit, batch, vendor) nằm trong `scripts/` | Thư mục gốc riêng hoặc repo riêng; hỏi chủ dự án |
| `config/` | 46 file phẳng, 10 file `bench_*` | Ưu tiên thấp; nếu gom thì làm cùng A1 |
| Git | pack 1,56 GiB; `docs/design/` 84 MB | Không viết lại lịch sử khi chưa hỏi; từ nay để asset nặng ngoài git |

## 6. Thứ tự nên làm

**P0, độ tin cậy (nên làm trước mọi tính năng):**

1. Khôi phục baseline test: phân loại 5 test còn dở ở §1, rồi xử lý 10 test đã hỏng sẵn (tìm phiên đã sửa `src/planning/{engine,build,ghosts}.py`).
2. A1 + A2: một thư mục release gồm `src/` và `config/`, có id, giữ bản trước.
3. A3: `./run.sh prod-restart`.
4. A4: tự khởi động lại và cảnh báo.

**P1, chất lượng có bằng chứng:**

5. Đo lại độ trễ khi máy rảnh (A6), rồi mới quyết định sửa đường chữ đầu tiên của Trip.
6. Ngày trống: hỏi chủ dự án về mục 3 và 4 ở §4; kiểm `pull_early`.
7. Tách người thật khỏi bot trong `events` (cờ trên tài khoản E2E), để phễu dùng được.
8. Giờ ăn và nhịp người dùng nói phải vào lịch: lần theo `frame.meals.by` và `per_day` trong hai ca E2E đã nêu.

**P2:** A7, A8, A9, làm gọn tài liệu, dọn repo.

## 7. Ràng buộc khi làm

- Không deploy khi chủ dự án chưa yêu cầu. Không thêm khóa mới vào `config/*.yaml` trước khi prod chạy bản code biết khóa đó (F004).
- Không dùng skill `superpowers:*`. Không `git stash` (F002). Không đụng symlink `.venv`, `.venv-vllm`, `.cache` (F003).
- Sửa UI phải lưu ảnh vào `frontend_images/` và chỉ đổi phần được yêu cầu (`RULE.md` §0.2).
- Mọi thay đổi hành vi ở Chọn nơi và Lịch trình liên quan tới "nhắc / chặn người dùng" đều là quyết định của chủ dự án (các mốc 04/11, 08/11, 09/11, 10/11 trong `docs/PLANNING.md`).

## 8. Lệnh kiểm chứng

```sh
# 5 test còn dở (máy nên rảnh)
.venv/bin/python -m pytest -q tests/planning/test_planning_lodging_golden.py tests/planning/test_planning_overload_parallel.py

# config hiện tại có nạp được bằng code prod đang chạy không
PYTHONPATH=.prod_src .venv/bin/python -c "from planning import settings; settings.load(settings.PATH)"

# prod còn sống
python3 scripts/keepalive.py --base-url https://tripguardian.visioncare-host.uk

# ma trận E2E để so với §2
PYTHONPATH=src .venv/bin/python scripts/prod_journey_e2e.py --jobs 4 --run-id <id>
```
