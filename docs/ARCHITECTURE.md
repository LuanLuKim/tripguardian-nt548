# Kiến trúc — TripGuardian

Bản đồ hệ thống: có những phần nào, nối nhau ra sao, quy tắc nào áp cho mọi phần. Chi tiết nằm ở tài liệu của từng phần; trang này chỉ trỏ tới. Phạm vi kiểm chứng: **Đà Lạt**. Vì sao và cho ai: `docs/Project_Context.md`.

## 1. Nguyên tắc hệ thống

- Thiếu bằng chứng thì `unknown`; không bao giờ bịa fact hay địa điểm. `unknown` ≠ `false`.
- Input của người dùng mô tả **chuyến đi**, không mô tả địa điểm.
- Offline **ghi** Place Intelligence; online chỉ **đọc** nó và chỉ ghi lịch trình, tài khoản, User / Session Profile. Live context chỉ sống trong request, không thành tri thức về địa điểm. Check-in và thông báo không phải bằng chứng về địa điểm.
- Physical constraint không có đường code nào nới. Hệ thống cảnh báo; quyết định cuối thuộc người dùng: lịch có vi phạm vẫn hiện và chốt được.
- User Profile là prior, xếp sau constraint và bối cảnh chuyến hiện tại.
- Code gọi model theo **vai trò** (§4); model không ghi fact, không tạo địa điểm, không tự xác nhận khả thi.

## 2. Mô hình constraint

| Loại | Ý nghĩa | Nới được? | Khi vi phạm |
|---|---|---|---|
| Physical | Bất khả thi thực tế (đóng cửa 17:00, đến sớm nhất 18:10) | **Không** | Loại khỏi lịch hoặc giữ ở wishlist kèm lý do; cảnh báo |
| User hard | Yêu cầu rõ của người dùng (trần 30 phút mỗi chặng) | Chỉ khi người dùng xác nhận | Hỏi có nới không, **luôn kèm cái giá đã tính** |
| Soft preference | Sở thích để xếp hạng | Có | Chỉ đổi thứ tự |

Package `requirements` là contract dùng chung cho Trip, Decision, Planning: kiểm phạm vi trước (`not_applicable`), rồi `pass | fail | unknown`. Bằng chứng trượt thì loại; yêu cầu an toàn chưa rõ vẫn hiện sau mọi nơi đạt; `unknown` khác theo `unknown_policy` của yêu cầu (`exclude` mặc định, `flag`). Ý định và ví dụ: `docs/TRIP_UNDERSTANDING.md` §9; semantics bằng chứng: `docs/PLACE_DECISION.md` §6.2.

## 3. Bốn giai đoạn và các package

```text
PLACE INTELLIGENCE  (offline)   địa điểm → fact / signal / estimate có bằng chứng   ── serving record, snapshot
        ▼
TRIP UNDERSTANDING              người dùng cần gì cho CHUYẾN NÀY → Trip State        ── Search Input
        ▼
PLACE DECISION                  shortlist → người dùng tuyển chọn                    ── Decision Output
        ▼  + Live Context
PLANNING & VALIDATION           tổ hợp đã chọn có đi được cùng nhau không            ── Plan Output
```

| Giai đoạn | Code | Tài liệu | Contract ra |
|---|---|---|---|
| Place Intelligence | `src/corpus/` | `docs/CORPUS.md` | serving record (§Bản ghi địa điểm) |
| Trip Understanding | `src/trip/` | `docs/TRIP_UNDERSTANDING.md` | Search Input (§9) |
| Place Decision | `src/decision/` | `docs/PLACE_DECISION.md` | Decision Output (§15) |
| Planning & Validation | `src/planning/`, `src/live/` | `docs/PLANNING.md` | Plan Output (§Plan Output) |

| Package dùng chung | Việc | Tài liệu |
|---|---|---|
| `requirements` | contract yêu cầu và kiểm tra theo hoạt động | §2 |
| `agents` | runtime Agent, tool, skill; `agents.assistant` là lõi trợ lý chat của ba màn | `docs/AGENT_HARNESS.md` |
| `harness` | HTTP/SSE, hành trình chung, router theo stage | `docs/AGENT_HARNESS.md` |
| `accounts`, `db`, `mailer`, `social` | tài khoản, Postgres, thư SMTP, bạn bè / tin nhắn | `docs/ACCOUNTS.md` |
| `booking`, `journey` | `Offer` deeplink; cách đi từ nhà tới chỗ ở | `docs/BOOKING.md` |
| `companion`, `notify` | chế độ Đang đi, Google Calendar; worker thông báo | `docs/COMPANION.md` |
| `analytics` | event, số liệu Admin | `docs/ANALYTICS.md` |
| `bench` | đo Trip Understanding, độ trễ, trợ lý | `docs/TRIP_UNDERSTANDING.md` §16 |

**Ranh giới.** Package chỉ gọi nhau qua public API (`__init__.py`, `RULE.md` §2). `corpus` công khai từng subpackage (`corpus.serving`, `corpus.snapshot`, …); `agents` công khai thêm `agents.assistant`. Phụ thuộc một hướng (import trong `src/`):

```text
corpus, db, mailer, social, accounts  ──►  (không gì)
requirements ──►  corpus.serving, corpus (category_group, load_ontology)
agents       ──►  corpus.llm, corpus.crawl
live         ──►  corpus.crawl            (chỉ open_sessions, maps_search, LoginRequired)
trip         ──►  agents, requirements, corpus.{serving,ontology,snapshot,index,releases,retrieval,llm,crawl,tags,pulse,views}
decision     ──►  agents, requirements, trip, corpus.{serving,ontology,snapshot,releases,retrieval,review,llm,tags,pulse}
planning     ──►  agents, requirements, trip, decision, live, corpus.{serving,ontology,snapshot,releases,retrieval,llm,local,views}
booking      ──►  live, corpus.serving
journey      ──►  live, booking
companion    ──►  decision, live, corpus.serving
notify       ──►  db, live, planning, corpus.{serving,ontology}
analytics    ──►  db, corpus.llm          (corpus.llm chỉ cho job `cluster`)
harness      ──►  trip, decision, planning, agents, accounts, social, mailer, companion, notify, db, booking, journey, live, corpus.{serving,releases,retrieval,pulse}
bench        ──►  trip, decision, planning, harness, agents, live, corpus.*   (không ai import bench)
```

`corpus` không biết giai đoạn sau nó; `live` không biết `planning`. Test chặn: `tests/{planning,live,booking,retrieval,harness}/…bound…`. Nợ ranh giới còn lại (import sâu hơn public API, chưa có test chặn): `harness/dispatch.py` → `planning.settings`; `bench/latency.py` → `decision.settings`, `trip.domain.resolve`, `trip.infrastructure.settings`; `trip/agent/*` → `agents.assistant.{loop,lc}`; `bench/assistant.py` → `agents.assistant.guard`; `agents/input_guard.py`, `trip/{domain,infrastructure}/perceive.py`, `trip/infrastructure/web.py` → `corpus.crawl.web`.

**Hành trình chung.** User Web đi Trip → Decision → Planning qua một journey của `harness`; router chọn module theo stage và gọi `Tools` public của module. Journey pin một corpus binding (release, region, manifest hash, snapshot / index version) cho cả ba module: đổi release pointer không đổi journey đã pin; release đã pin mà mất khỏi đĩa thì trả 409 `stale_data_version`, không phục vụ dữ liệu khác. Budget giữ amount / scope / nguồn trước khi quy đổi; `unknown` và hoạt động giữ nguyên qua handoff. Revision, receipt, retry, khóa, đọc song song: `docs/AGENT_HARNESS.md` §3. Release offline: `docs/CORPUS.md` §Chuẩn hóa và release offline.

## 4. Vai trò model

| Vai trò | Việc |
|---|---|
| ASR | âm thanh → transcript |
| Extractor | việc khối lượng lớn (đọc, lọc, khớp) |
| Judge | chốt chặn trước người (guard nội dung, phân xử) |
| Agent | hiểu câu tự do ở Trip / Decision, đề xuất bố trí nội bộ ở Planning |

Định nghĩa: `docs/CORPUS.md` §Vai trò model. Model nào đang giữ vai nào, endpoint, key: `docs/LLM_PROVIDER.md`. Output của Agent được validate theo schema và guard nghiệp vụ (quyền, grounding) trước khi act chạy; call lỗi hoặc chậm thì Trip / Decision dùng `policy.py`, Planning giữ baseline đã kiểm. Solver / validator, không phải model, quyết định khả thi (`docs/AGENT_HARNESS.md` §1, §5; `docs/PLANNING.md` §Agent đề xuất nội bộ).

## 5. Cấu hình và dữ liệu

Mọi ngưỡng nằm trong `config/`, không trong code:

| File | Của ai | Nội dung |
|---|---|---|
| `cities.yaml`, `queries.yaml`, `gsearch.yaml`, `navigate.yaml` | corpus | thành phố, vùng quét, category, trần crawl; tìm Google theo nơi; sol dẫn đường |
| `ontology.yaml` | corpus + profile | feature ontology có version |
| `category_defaults.yaml`, `companions.yaml`, `dishes.yaml`, `seasons.yaml` | corpus | mặc định theo nhóm category; từ vựng đi cùng ai, món, mùa (nhập tay, có nguồn) |
| `index.yaml`, `styles.yaml`, `scenes.yaml` | corpus | chỉ mục ngữ nghĩa, tag phong cách, nhãn cảnh ảnh |
| `local.yaml`, `pulse.yaml`, `views.yaml` | corpus | tri thức bản địa, Nhịp Đà Lạt, view toàn cầu |
| `tags.yaml` | corpus (trip, harness đọc qua `corpus.tags`) | tag / subtag, ngưỡng chia nhóm, xếp hạng xu hướng (`docs/PLACE_DECISION.md` §20) |
| `serving.yaml` | corpus | ngưỡng serving record |
| `trip.yaml` | trip | ngân hàng câu hỏi, ngưỡng dừng hỏi, trợ lý |
| `agents.yaml`, `security.yaml` | agents, harness, trip | giới hạn call / queue; guard chat, giới hạn request, giải mã ảnh (`docs/AGENT_HARNESS.md` §5) |
| `decision.yaml` | decision | trọng số xếp hạng, cỡ shortlist, ngưỡng sàng |
| `planning.yaml` | planning | nhịp độ, ngày, mục tiêu, độ vững, dự phòng, chỗ ở |
| `live.yaml`, `climate.yaml`, `holidays.yaml`, `events.yaml`, `advisories.yaml`, `airports.yaml` | live | endpoint và TTL nguồn live; khí hậu, lễ, sự kiện, cảnh báo thiên tai, sân bay (nhập tay; không có dòng ≠ an toàn) |
| `booking.yaml`, `journey.yaml` | booking, journey | tham số nhà cung cấp, tuổi giá phòng; ngưỡng chọn cách đi (`docs/BOOKING.md`) |
| `companion.yaml`, `notifications.yaml`, `mail.yaml` | companion, notify, mailer | gợi ý tại chỗ; loại thông báo, mẫu câu, giờ yên lặng; thư đi (bí mật ở `.env`) |
| `eval_trips.yaml`, `bench_*.yaml`, `prod_journey_cases.yaml` | decision, planning, bench | chuyến ẩn, ca đo trợ lý, ma trận kịch bản prod |

| Dữ liệu | Ở đâu |
|---|---|
| Thô và observation, mỗi nguồn một thư mục | `data/<nguồn>/` (`RULE.md` §2) |
| Place Intelligence | `data/intel/`, `data/serving/`, `data/snapshot/`, `data/releases/` (`docs/CORPUS.md` §Data model) |
| Cache live có TTL | `data/live/` (`docs/PLANNING.md` §Ranh giới module) |
| Người dùng: tài khoản, hành trình (bảng `journeys`), event, chuyến đang đi, Calendar, thông báo | Postgres `tripguardian-pg` `127.0.0.1:5433`, schema `migrations/`, `./run.sh db`; role `tg_app` ghi, `tg_analytics` chỉ đọc và không thấy bảng bí mật |
| Avatar | `data/accounts/avatars/` |
| Phiên CLI/API module độc lập | `data/{trip,decision,planning}/sessions/` |

Phiên module là `State` có phiên bản; một act sinh `State` mới và `scope.py` quyết định phần nào phải tính lại.

## 6. Các vòng phản hồi

```text
Vòng lựa chọn     Shortlist → tuyển chọn → khả thi → xung đột → tuyển chọn          PLACE_DECISION.md §13–14
Vòng xếp lịch     Planning không xếp được một nơi → tuyển chọn → thay / bỏ / nới    PLACE_DECISION.md §14, PLANNING.md ⓔ
Vòng kiểm tra     Lịch → validate + độ vững → sửa / phương án thay → kiểm lại       PLANNING.md ⓔ ⓕ
Vòng cá nhân hóa  Profile → gợi ý → quyết định → Session Profile → kết quả chuyến
                  → bằng chứng lặp lại / mạnh? → Long-term Profile                  Project_Context.md §8, §10
```

Decision ước lượng **thô** để chọn nhanh, Planning tính **thật** rồi trả ngược nơi gây lỗi: vì vậy hai giai đoạn tách nhau mà vẫn nối vòng.

## 7. Giao diện và cổng

```text
web (Vite :5173)  /        landing
                  /app     User Web (Google hoặc khách) → /api/auth/*, /api/harness/* → harness :8769
                  /admin   Admin Web → review :8765, analytics :8770 (private, chỉ đọc)
notify worker     python -m notify run (không cổng) → Postgres, web push
Postgres          127.0.0.1:5433
```

Bản public (`web/server.mjs` :28899 sau Cloudflare tunnel) chỉ mở `/api/harness/*`, `/api/auth/*`; `/admin`, analytics, mọi `/api` khác trả 404. Prod chạy bản đông cứng `.prod_src/` (`docs/OPERATIONS.md`). Màn theo vai trò: `docs/Role_Web_Functional_Design.md`; hệ thị giác: `docs/UX_Design_Brief.md`; bảo mật: `docs/SECURITY.md`.

## 8. Quyết định thiết kế chính

| Quyết định | Lý do |
|---|---|
| Place Intelligence tách khỏi bối cảnh chuyến | Tri thức địa điểm và nhu cầu từng chuyến có vòng đời khác nhau |
| Khám phá và bằng chứng tách riêng | Nguồn giúp tìm ra nơi chưa chắc đáng tin cho mọi nhận định |
| Trạng thái bắt đầu và mức dẫn dắt độc lập | Trạng thái có sẵn trong input; mức dẫn dắt phải suy từ hành vi |
| Resolve địa điểm của người dùng trước khi đánh giá | Tên đã lưu có thể là alias, trùng, hoặc nơi chưa biết |
| Physical, user-hard, soft tách riêng | Mỗi loại cần cách xử lý xung đột khác nhau |
| Chọn dùng độ hợp không gian thô; xếp lịch dùng thời gian đi thật | Không tính lịch chi tiết trước khi có shortlist |
| Người dùng tuyển chọn trước khi xếp lịch | Hỗ trợ quyết định, không quyết định thay |
| Khả thi đánh giá theo tổ hợp | Các nơi hợp lệ riêng lẻ vẫn có thể thành chuyến bất khả thi |
| Nhịp độ và mục tiêu tối ưu tách riêng | "Thư thả" là cường độ; "tiết kiệm", "ít di chuyển" là mục tiêu |
| Kiểm tra tất định; độ vững đi sau khả thi | Lịch trông hợp lý chưa đủ; lịch đúng vẫn có thể dễ vỡ |
| Dự phòng dùng lại ứng viên bị loại | Phương án thay giải thích được và hợp bối cảnh |
| Chỗ ở có trong corpus; giá / còn phòng tra live | Đặc tính và giá tham khảo là tri thức; đặt được đúng ngày là dữ liệu live |
| Session và long-term profile tách riêng; đã đến ≠ đã thích | Sở thích đổi trong chuyến không viết lại gu dài hạn |
| Corpus do agent xây, kiểm bằng gate và định tuyến rủi ro | Công sức người tăng theo rủi ro, không theo cỡ corpus |
| Cố định vai trò model, không cố định model | Đổi model bằng config khi nhãn review cho thấy tốt hơn / rẻ hơn |
| Phiên là `State` có phiên bản + hàm thuần sinh `State` mới | Undo / redo thật; mỗi act chỉ tính lại phần bị ảnh hưởng |
