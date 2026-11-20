# Event và Analytics

Số liệu Admin từ event thật. Ghi: `src/harness/events.py` (harness), `web/src/user/events.ts` (web). Đọc: `src/analytics/` (server private). Màn: `web/src/admin/screens/Analytics.tsx`, `AnalyticsTabs.tsx`, `Sessions.tsx`, `Insights.tsx`, `Users.tsx` + `UserDetail.tsx` (§5), `Trends.tsx` (§6), hàng "Hôm nay" ở `Dashboard.tsx`, panel "Nhu cầu" ở `Places.tsx`.

## 1. Event

Bảng `events`: `at, user_id, journey_id, source (server | client), name, props, app_version`. Không chứa email, tên, số điện thoại hay chữ người dùng gõ (trừ `q` của ô tìm nơi). Ghi lỗi không làm hỏng request gây ra nó.

**Server** (harness): sau mỗi mutation hành trình, `name = <stage>.<operation>[.<act type>]`, props `revision, latency_ms, first_ms` (tới event SSE đầu), `path` (`agent | fallback | heuristic:exact_command`, từ event nội bộ `trace` của adapter `Tools`), `error` khi mutation thất bại, `compiled` khi Trip vừa ra Search Input, `refined` khi câu gõ ở Chọn nơi đi qua Trip. Lượt Trip thêm `kind, qid, exit (skip | unsure)`. Act thêm `place_id, reason, with_id, group, id, objective, pace`. `planning.confirm` thêm `places, hard_checks, hard_fail, hard_unknown, robustness`. Ngoài ra: `journey.create`, `journey.copy {source}` (lấy về chuyến bạn gửi), `preview.<status>`, `places.search {q, hits}`, `why_not`, `page_more`, `feedback.submit`, `auth.login`, `auth.consent`, `companion.<operation>`, `calendar.connect | apply | disconnect`, `notify.prefs {paused, kinds_off}`, `profile.remember {on}`, `profile.edit {fields}`, `profile.delete`, `profile.pause {paused}` (hồ sơ cá nhân hóa, `docs/TRIP_UNDERSTANDING.md` §17). Lần replay theo receipt không ghi lại.

**Client**: `POST /api/harness/events {events: [...]}`, tối đa 50 event / 32 KiB mỗi lô; tên và prop ngoài allowlist bị bỏ. Không phiên thì chỉ giữ `page_view`, `landing_cta`. Web gom lô 10 giây hoặc 20 event, gửi bằng `sendBeacon` khi rời / ẩn tab.

| Tên | Props |
|---|---|
| `page_view` | `route` |
| `landing_cta` | `utm_*` |
| `card_impression` | `place_id, group, rank` (một lần mỗi nơi mỗi hành trình; chỉ làm mẫu số: thẻ hiện mà không bấm không có nghĩa là không thích) |
| `detail_open` | `place_id, from` |
| `theme_open` | `theme` (chủ đề ở trang chủ; nguồn của Đã xem gần đây, `docs/ACCOUNTS.md` §9) |
| `evidence_play` | `place_id, video_id` |
| `compare_open` | `a, b` |
| `outbound_click` | `kind (maps | tiktok | booking), place_id` |
| `booking_click` | `offer_id, provider, kind (coach | flight | stay)` (bấm mở trang đặt điền sẵn của một `Offer`, `docs/BOOKING.md`; `journey_id` ở envelope) |
| `tab_hidden` | `stage, ms` (thời gian rời tab) |
| `today_open`, `install_prompt_seen` | — |
| `suggestion_open` | `place_id, kind` |
| `push_permission` | `result` |

**Phiên bản**: `app_version` = git sha ngắn + hash `config/*.yaml`, tính khi harness khởi động; gắn vào event và hành trình.

**Dữ liệu cũ**: `python -m harness import-files` nạp hành trình file và sinh các mốc phễu từ trạng thái đã lưu (`props.imported`, giờ = giờ sửa file, không dùng để tính thời gian; không biết được `preview`).

## 2. Server analytics

```sh
python -m analytics serve [--port 8770]   # 127.0.0.1, chỉ GET, role tg_analytics (DATABASE_URL_READONLY)
python -m analytics cluster               # mỗi tuần: nhóm ý người dùng viết (vai trò Extractor), cần DATABASE_URL
```

Đăng nhập: tài khoản duy nhất lấy từ `.env` (`ADMIN_EMAIL`, `ADMIN_PASSWORD`; `src/analytics/auth.py`; cookie `Path=/`). `POST /api/analytics/login {email, password}` đặt cookie `tg_admin` (HttpOnly, SameSite=Strict, 12 giờ, token giữ trong bộ nhớ nên khởi động lại là đăng xuất); `POST …/logout`; `GET …/me`. Mọi GET khác trả 401 khi chưa đăng nhập; thiếu `ADMIN_PASSWORD` thì không ai vào được. Sai 5 lần trong 15 phút thì khóa địa chỉ đó 15 phút. Màn đăng nhập: `web/src/admin/Login.tsx`. Trên bản public, `web/server.mjs` proxy các route này và chỉ cho review API đi qua sau khi `/me` trả 200; lệnh khóa tính theo địa chỉ (`x-tg-client-ip`), cookie thêm `Secure` khi tới qua https (`x-tg-secure`).

Vite proxy `/api/analytics` → 8770 (`ANALYTICS_PORT`). `./run.sh start` chạy nó; bản public không chạy và `web/server.mjs` chặn mọi `/api/*` ngoài harness / auth. Bộ lọc chung: `from`, `to` (ngày theo giờ Việt Nam; mặc định 30 ngày), `start_with`, `app_version`.

| GET `/api/analytics/…` | Nội dung |
|---|---|
| `funnel` | Landing, CTA, người đăng nhập; mỗi bước: số hành trình tới, giữ lại so với bước trước có số liệu, phút từ lúc tạo (trung vị), số dừng ở đây và thao tác cuối trước khi dừng |
| `decision` | Thao tác, lý do bỏ, trạng thái lịch xem trước, trang thêm, why-not, so sánh, bấm ra ngoài, tỉ lệ chọn theo vị trí, từ khóa tìm không thấy |
| `trip`, `planning`, `reality`, `notifications`, `agent`, `quality` | Các tab §3 |
| `sessions?reached=&abandoned=1&low_feedback=1&error=1`, `sessions/<id>` | Danh sách và phát lại một hành trình (transcript, log module, receipt, event, phản hồi) |
| `today`, `versions`, `insights`, `clusters`, `places/<id>` | Hàng Hôm nay, phiên bản, Insights, nhóm ý, nhu cầu một nơi |
| `users?test=`, `users/list?test=`, `users/<uuid hex>` | Màn Người dùng (§5): tổng quan, danh sách mọi dòng `users`, một người |
| `trends?test=` | Màn Xu hướng tiêu dùng (§6) |

## 3. Chỉ số

Hành trình do client thử tạo (header `X-TG-Synthetic`, gửi bởi `scripts/prod_journey_e2e.py` và smoke của `run.sh`; harness ghi `synthetic` vào props của `journey.create`) bị loại khỏi phễu, danh sách phiên và các tab, trừ khi gọi với `synthetic=1`. Hành trình bot trước khi có header vẫn còn trong số liệu cũ.

Bước phễu (mỗi hành trình đếm một lần): `journey.create` → `trip.turn` có `compiled` → `trip.advance` → `decision.act.select` → `preview.ready` → `decision.advance` → `planning.confirm` → `feedback.submit`. Event có `error` không tính.

| Tab | Chỉ số |
|---|---|
| Phễu | §2; so sánh hai phiên bản cạnh nhau |
| Trip | Lượt tới khi hiểu xong; chip so với gõ tự do; đường trả lời; bỏ qua / chưa chắc theo `qid`; `unmapped` lặp lại; quay lại; refine |
| Quyết định | §2 `decision` |
| Lịch trình | Thao tác, phương án được chọn, dùng gợi ý tự động, quay về Chọn nơi, độ vững của lịch đã chốt, phút từ vào tới chốt, lỗi |
| Thực tế | **Tỉ lệ check-in lại ở điểm sau** (chỉ số chính), muộn so với lịch, khoảng giữa hai điểm so với lịch, đã đến / bỏ qua / chưa biết, check-in ngoài lịch, lý do bỏ qua, Hợp / Không hợp, thêm từ gợi ý; luôn kèm độ phủ check-in |
| Thông báo | Tỉ lệ cho phép; gửi / mở / có ích (thao tác trong 2 giờ sau khi mở) theo loại và biến thể; bị bỏ theo lý do; **tắt hoặc tạm im trên 1.000 thông báo gửi** (chỉ số chặn) |
| Agent | Theo loại yêu cầu dùng model: số lượt, p50 / p95, tới event đầu, fallback, lỗi. Số liệu theo từng lời gọi của từng vai trò chưa được ghi |
| Chất lượng | Vi phạm hard constraint trên lịch đã chốt (phải bằng 0, khác 0 là báo động), tỉ lệ kiểm tra `unknown`, tỉ lệ lịch xem trước xếp được, phút tới lịch được chấp nhận, bấm ra ngoài + rời tab ở Chọn nơi (proxy cho việc phải tìm ở ngoài) |

Ngưỡng cảnh báo chỉ đặt sau khi có baseline thật (`docs/Role_Web_Functional_Design.md` §3.7).

## 4. Insights

Mỗi mục có nút dẫn tới việc cần làm; chỉ đề xuất, không ghi corpus: từ khóa tìm không thấy (danh sách cần crawl), `unmapped` lặp lại ≥ 2 hành trình (đề xuất ontology), nơi hiện ≥ 10 lần mà bị bỏ ≥ 30% (hàng đợi duyệt), câu hỏi Trip bị bỏ qua nhiều (`config/trip.yaml`), phiên có lỗi hoặc fallback (Phiên chuyến đi). Thêm bảng "Nhóm ý người dùng viết": job `cluster` lấy phản hồi sau chuyến và câu gõ tự do 7 ngày qua, nhóm bằng task `INSIGHT_CLUSTER` (`corpus.llm`), ghi bảng `insight_clusters` (thay nhóm của cùng tuần khi chạy lại).

## 5. Người dùng

Đếm theo **người**, không theo hành trình (khác Phễu). Code: `src/analytics/users.py`.

- **Gán event cho người:** chủ của hành trình (`journeys.user_id`) nếu event có hành trình, nếu không thì `events.user_id`. Nhờ vậy chuyến khách làm rồi đăng nhập (`auth.guest_adopted`) tính cho tài khoản; event của khách đã bị dọn không còn người nên chỉ vào các tổng (hành trình, lượt chốt, phiên khách = số `auth.guest`).
- **Loại:** `account` (`kind = user`), `guest` (`kind = guest`, còn phiên). Tài khoản thử = email `@test.local` / `@example.com` (`TEST_DOMAINS`), bị loại khỏi mọi số trừ khi `test=1`.
- **KPI** của kỳ `[from, to]` so với kỳ ngay trước cùng độ dài: tài khoản, tài khoản hoạt động (có event), quay lại (≥ 2 ngày hoạt động trong kỳ), phiên khách mới và số đăng nhập để giữ chuyến, hành trình tạo, lượt chốt lịch, tài khoản gặp lỗi / fallback.
- **Mỗi người đi tới đâu:** tài khoản tạo trong kỳ; bước (`LADDER`) tính khi người đó từng có event tương ứng không lỗi, ở bất kỳ lúc nào: tạo hành trình → `trip.turn` có `compiled` → `decision.act.select` → `planning.confirm` → `feedback.submit`; "lập chuyến ở ngày khác" = `journey.create` ở ≥ 2 ngày, tính trên người đã tạo hành trình.
- **Giữ chân:** 8 tuần đăng ký gần nhất (thứ Hai, giờ Việt Nam); ô tuần k = phần trăm có event trong tuần k sau tuần đăng ký. Không theo bộ lọc thời gian.
- **Tính năng** (`FEATURES`): số tài khoản đã dùng trong kỳ và tổng lượt (cả khách); lưu, kết bạn, nhắn tin đọc bảng `saved_items`, `friendships`, `messages`. `calendar_links`, `push_subscriptions` không đọc được bằng role này nên Calendar / thông báo đọc từ event.
- **Tín hiệu cần chú ý:** chỉ là số đếm, chưa có ngưỡng (§3): tài khoản gặp lỗi (kèm 5 event lỗi nhiều nhất), có hành trình mà chưa chốt, chưa tạo hành trình, chỉ hoạt động 1 ngày, chấm ≤ 2, khách đăng nhập để giữ chuyến, chưa có prior cá nhân hóa (phương tiện, đi cùng ai, nhớ hồ sơ), tìm nơi không ra, tính năng chưa ai dùng.
- **Một người:** hồ sơ và đồng ý, các bước đã tới, tính năng (số lượt từ trước tới nay), event theo ngày 26 tuần, hành trình (mở phát lại ở Phiên chuyến đi), phản hồi, 60 event gần nhất, số đã lưu / bạn bè / tin nhắn / chuyến / check-in / thông báo.

## 6. Xu hướng tiêu dùng

Người dùng thích gì và lập chuyến ra sao. Code: `src/analytics/trends.py`. Mọi số là **số hành trình** (người khi event không có hành trình) trong kỳ, không có điểm gộp có trọng số; hành trình thử (`synthetic`) và tài khoản thử bị loại như §5.

- **Nơi:** mỗi `place_id` đếm hành trình thấy thẻ (`card_impression`), xem chi tiết (`detail_open`), chọn (`decision.act.select`), thích (`place_like` với `value = on`), bỏ (`decision.act.drop`), mở Maps / TikTok (`outbound_click`), check-in, người lưu (`saved_items`), lịch đã chốt có nơi đó (`trips` + `trip_stops`). **Tỉ lệ chọn** = hành trình chọn sau khi đã thấy thẻ (`chosen_seen`) / hành trình thấy thẻ; cột Chọn còn gồm chọn qua trò chuyện. Trả 300 nơi, xếp theo chọn + vào lịch + xem + thích. Tên lấy từ snapshot của Admin, nơi không còn trong snapshot thì từ `trip_stops.name`.
- **Đang lên:** hành trình quan tâm (xem, chọn, thích, mở ngoài) trong 7 ngày cuối kỳ so với 7 ngày trước đó; là ứng viên để đối chiếu với Trending của trang chủ (`docs/CORPUS.md` §Nhịp), không tự ghi vào đó.
- **Lịch nhiều người lập** (lịch đã chốt tạo trong kỳ): số ngày, nơi mỗi ngày (trung vị), số ngày từ lúc chốt tới ngày đi (trung vị), giờ tới nơi, thứ trong tuần của điểm dừng, cặp nơi cùng một lịch và cặp đi liền nhau trong một ngày (chỉ cặp lặp lại ở ≥ 2 lịch).
- **Khách muốn gì:** từ yêu cầu Trip đã hiểu (`outputs.trip`) của hành trình tạo trong kỳ; trường bối cảnh chỉ tính khi `sources` khác `default`: đi cùng ai, số người, số ngày, phương tiện, mục đích, ngân sách mỗi người (dải), tháng và thứ bắt đầu, sở thích người dùng nói (`soft_weights` có `source = user`), kiểu đã thích, loại nơi, món, cảm hứng. Envelope trung bình ~0,6 MB nên phần này được đọc một lần mỗi `updated_at` và giữ trong tiến trình server (`_ASKS`); server đọc sẵn lúc khởi động ở luồng nền.
- **Từ khóa:** chủ đề trang chủ được mở (`theme_open`), cụm từ tìm nơi (`places.search`, kèm số lần không ra kết quả), lý do bỏ.
