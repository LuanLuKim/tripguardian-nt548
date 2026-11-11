# Kế hoạch: tổ chức lại và viết lại tài liệu

Spec làm việc (`RULE.md` §0.1), ngày 2026-11-11, chờ chủ dự án duyệt. Chưa sửa file nào ngoài file này.

## 1. Vì sao phải làm

Tài liệu đúng nội dung nhưng không đọc nổi:

| Vấn đề | Số đo |
|---|---|
| Ba file giai đoạn quá lớn | `CORPUS.md` 202 KB (954 dòng, trung bình 211 ký tự/dòng, có đoạn 4.500 ký tự), `TRIP_UNDERSTANDING.md` 131 KB, `PLANNING.md` 108 KB, `PLACE_DECISION.md` 72 KB |
| Một file trộn bốn loại nội dung | giải thích + tra cứu (schema, CLI, config) + lịch sử có ngày + hành vi tới từng câu chữ |
| Lịch sử trong tài liệu chính thức (trái §0.1) | mốc ngày: 36 / 14 / 11 lần ở CORPUS / TRIP / PLANNING; "đã gỡ / trước đây": 15 / 26 / 25 lần |
| Cơ chế agent tả rải rác | `trip`, `decision`, `planning` dùng cùng một mẫu (`agent`, `assistant`, `tools`, `tool_schemas`, `guard`, `policy`, `skills.yaml`) trên lõi `src/agents/`, nhưng mỗi file giai đoạn tả lại theo cách riêng |
| Chồng chéo | 5 file UI (`Role_Web_Functional_Design`, `UX_Design_Brief`, `UI_SPEC_USER_WEB`, `UI_SPEC_FLOW_LAYOUT`, `UI_SPEC_LANDING`); `TRIP_UNDERSTANDING_QA` §5.1 chép bảng 71 feature của `config/ontology.yaml` |
| Thiếu | kiến trúc frontend `web/src/` (router, store, journey client, SSE, CSS); hệ 3D (`scripts/diorama/`, `web/public/space3d/`) chỉ có trong 7 file plan/bàn giao; chưa có bảng thuật ngữ |
| Code trỏ vào tài liệu | 427 chỗ dạng `docs/X.md §Y` trong `src/ tests/ scripts/ config/ web/` (CORPUS 121, TRIP 72, PLANNING 72, DECISION 56); chưa có gì kiểm các chỗ trỏ này còn đúng |

**Xong khi:**
- Người mới đọc `ARCHITECTURE.md` trong 10 phút là hiểu hệ thống.
- Muốn hiểu một thuật toán bất kỳ thì đọc ≤ 3 file, tổng ≤ 40 KB.
- Mọi chỗ code trỏ vào tài liệu đều trỏ tới mục có thật, có test chặn.

## 2. Nguyên tắc mới

**Đọc theo tầng.** Mỗi tầng chỉ nói việc của tầng đó và trỏ xuống tầng dưới.

| Tầng | Đọc trong | File | Ngân sách |
|---|---|---|---|
| 1. Hệ thống làm gì | 2 phút | `README.md` phần đầu | 1 màn hình |
| 2. Kiến trúc toàn cục | 10 phút | `docs/ARCHITECTURE.md` | ≤ 12 KB |
| 3. Một giai đoạn / hệ con | 10 phút | `docs/<stage>/README.md` | ≤ 10 KB |
| 4. Một nhóm thuật toán / agent | 15 phút | `docs/<stage>/<topic>.md` | ≤ 20 KB |
| 5. Chi tiết | khi cần | docstring, tên test, `config/` | không giới hạn |
| Vì sao | khi thắc mắc | `docs/adr/` | ≤ 3 KB mỗi file |

Ngân sách tính bằng KB, không bằng dòng, vì dòng ở đây rất dài. 20 KB ≈ 6 nghìn token: một agent đọc trọn được một lần.

**Bốn loại nội dung, bốn chỗ:**
- Giải thích (chạy thế nào, vì sao): `README.md` của stage và file chủ đề.
- Tra cứu (contract, CLI, config key, đo): `reference.md` của stage.
- Quyết định có ngày: `docs/adr/`.
- Hành vi tới từng câu chữ (câu hỏi, giọng điệu, ngưỡng): docstring, tên test, `config/`. Tài liệu chỉ trỏ tới.

**Quy ước viết:**
- Mỗi đoạn ≤ 5 dòng, xuống dòng theo câu.
- Có sơ đồ (mermaid) thì không tả lại bằng chữ.
- Không ngày tháng, không "trước đây / đã gỡ".
- Mỗi thuật toán có file code và test chứng minh.

**Chỉ chuyển file cần tách.** Các file đã ngắn (`ACCOUNTS`, `SECURITY`, `COMPANION`, `BOOKING`, `ANALYTICS`, `OPERATIONS`, `LLM_PROVIDER`) giữ tên và chỗ, chỉ làm gọn. Như vậy bớt được số chỗ code trỏ phải sửa.

## 3. Cây tài liệu đích

```text
README.md                       giữ; bảng §Tài liệu sửa theo cây mới
docs/
  ARCHITECTURE.md               viết lại (khuôn §4.1)
  GLOSSARY.md                   mới: fact / signal / estimate, unknown, hard / physical constraint,
                                serving record, release, journey pin, Trip State, Search Input, …
  Project_Context.md            giữ, làm gọn: sản phẩm, người dùng, nguyên tắc; cơ chế User Profile chuyển sang trip/profile.md
  adr/                          mới: NNNN-<slug>.md
  agents/
    README.md                   mẫu agent chung: runtime, vòng lặp, tool, guard, policy, skill, ngân sách model
    harness.md                  router, handoff, journey, revision / retry, HTTP và SSE
  corpus/     README.md collect.md observe-aggregate.md tags-index.md release-serving.md knowledge.md reference.md
  trip/       README.md state.md questions.md understanding.md profile.md perception.md agent.md reference.md qa.md
  decision/   README.md screening.md ranking.md curation.md feasibility.md agent.md reference.md
  planning/   README.md live-context.md lodging.md days-route-schedule.md validate-robustness.md
              revise.md eve-expert.md agent.md reference.md
  web/
    README.md                   mới: kiến trúc frontend (router, store, journey client, SSE, CSS token, tour)
    screens.md                  chức năng từng màn, User + Admin, màn ↔ file
    design.md                   hệ thị giác, quy tắc hiển thị dữ liệu, bố cục, chuyển cảnh, giọng điệu
    landing.md                  landing và trang Dùng ứng dụng
  space3d/
    README.md                   mới: Khám phá 3D là gì, chọn nơi nào, pipeline auto3d, viewer, dữ liệu, cổng chất lượng
  ACCOUNTS.md SECURITY.md COMPANION.md BOOKING.md ANALYTICS.md LLM_PROVIDER.md OPERATIONS.md   giữ
  reports/ log/ plans/ design/  giữ
```

## 4. Khuôn mẫu

### 4.1 `ARCHITECTURE.md`

```text
1. TripGuardian trong một đoạn
2. Sơ đồ ngữ cảnh: người dùng, Admin, nguồn ngoài (Google, TikTok…), model theo vai trò
3. Sơ đồ container: web, harness, trip / decision / planning serve, Postgres, model server, cron offline, prod .prod_src
4. Một chuyến đi từ đầu tới cuối: sequence Trip → Decision → Planning qua journey
5. Bản đồ code: package → việc → tài liệu (bảng); đồ thị phụ thuộc (giữ §3 hiện có)
6. Bất biến (≤ 10 dòng, mỗi dòng trỏ ADR)
7. Xuyên suốt: model theo vai trò, config, release pin, ranh giới module, test, deploy
```

### 4.2 `README.md` của một stage

```text
1. Làm gì (3 câu); vào gì → ra gì (trỏ reference.md §Contract, 1 ví dụ JSON ngắn)
2. Sơ đồ pipeline bên trong (mermaid, mỗi bước ghi file code)
3. Bảng "muốn hiểu X → đọc file nào"
4. Giới hạn đã biết
```

### 4.3 Thẻ thuật toán (trong file chủ đề, ≤ 40 dòng mỗi thẻ)

```text
### <Tên> — `file.py`
Bài toán      : 1–2 câu
Vào → Ra      : kiểu dữ liệu
Các bước      : pseudocode 5–10 dòng
Vì sao        : 1–3 câu, trỏ ADR nếu có
Config        : key trong config/<x>.yaml
Số đo         : số hiện hành + lệnh đo
Test          : tests/<pkg>/test_x.py::test_y
```

### 4.4 Thẻ agent (`<stage>/agent.md`, chỉ ghi phần khác `agents/README.md`)

```text
Vai trò, được gọi khi nào (router / stage), context vào (trỏ contract)
Tool: bảng tên | làm gì | đọc / ghi gì | file
Guard và policy riêng, skill (`skills.yaml`, `SKILL.md`)
Model: vai trò, ngân sách, timeout; điều kiện dừng; hỏng thì người dùng thấy gì
Đo: bench nào, số hiện hành
Sơ đồ sequence một lượt chat
```

### 4.5 ADR (`docs/adr/NNNN-<slug>.md`, ≤ 3 KB)

```text
# NNNN. <Quyết định>
Ngày, người quyết: …
Bối cảnh: 2–4 câu
Quyết định: 1–3 câu
Hệ quả: được gì, mất gì, code nào thực thi (file, test)
```

ADR không bao giờ sửa nội dung. Đổi quyết định thì viết ADR mới và ghi "thay ADR NNNN" ở đầu ADR cũ.

## 5. Ánh xạ nội dung cũ → mới

Mục nào không có trong bảng là hành vi chi tiết hoặc lịch sử. Hành vi chi tiết về docstring / test / config; lịch sử về ADR (nếu là quyết định) hoặc bỏ (đã có git).

### 5.1 `CORPUS.md` → `docs/corpus/`

| Mới | Lấy từ |
|---|---|
| `README.md` | Mục tiêu, Phạm vi, Nguyên tắc, Nguồn và mỗi nguồn chứng minh điều gì, Vai trò model, Pipeline, Ba loại output, Trạng thái |
| `collect.md` | §1 Discover (cả Dữ liệu thô), §2 Extract, §3 Resolve, sol dẫn đường, Resolve nominee |
| `observe-aggregate.md` | §4 Observe, §5 Aggregate, §6 Kiểm tra và định tuyến, §7 Publish và review, §8 Refresh, Vòng lặp tự động |
| `tags-index.md` | Membership tag offline, Chỉ mục ngữ nghĩa, Agent đọc kho (`card`, `find`, `vocabulary`) |
| `release-serving.md` | Bản ghi địa điểm, Data model, Chuẩn hóa và release offline, Place Decision dùng corpus thế nào |
| `knowledge.md` | Tri thức bản địa, View toàn cầu, Nhịp Đà Lạt, Chi tiết địa điểm, Giá phòng theo ngày, Giá chuyến bay |
| `reference.md` | CLI, Kiểm soát chi phí và hiệu năng, Đo chất lượng, Mở rộng, Xử lý lỗi, Đầu vào cần có |
| ADR hoặc bỏ | Sai lệch cho bản demo (cần chủ dự án xem) |

### 5.2 `TRIP_UNDERSTANDING.md` + `_QA.md` → `docs/trip/`

| Mới | Lấy từ |
|---|---|
| `README.md` | §1, §2, §4 Luồng xử lý |
| `state.md` | §3 Trip State (Ngân sách, Tầng dữ liệu đầu vào) |
| `questions.md` | §5 Chọn câu hỏi (chỉ luồng đang bật theo cờ `discovery`), §6 Next, §12 Nguyên tắc đặt câu hỏi, Câu hỏi cổng; §13 Giọng điệu thu về 5 dòng + trỏ prompt |
| `understanding.md` | §7 Tín hiệu an toàn, §8 Bản hiểu nhu cầu, §10 Điều chỉnh theo người dùng |
| `profile.md` | §17 Hồ sơ cá nhân hóa + cơ chế ở `Project_Context.md` §6–§10 |
| `perception.md` | §18 Phong cách và ảnh, §20 Ảnh và link người dùng gửi |
| `agent.md` | §19 Trợ lý Đà Lạt (lõi chung chuyển lên `agents/README.md`) |
| `reference.md` | §9 Search Input (cả Ăn chay theo ngày), §14 CLI và API, §15 Ví dụ, §16 Đánh giá |
| `qa.md` | `TRIP_UNDERSTANDING_QA.md` bỏ §5.1 (trỏ `config/ontology.yaml`), §3 trỏ `reference.md`; §10 bàn giao Planning: đối chiếu code, còn giá trị thì chuyển sang `planning/` |
| `web/screens.md` | §11 Trải nghiệm người dùng |

### 5.3 `PLACE_DECISION.md` → `docs/decision/`

| Mới | Lấy từ |
|---|---|
| `README.md` | §1, §2, §3 Luồng xử lý |
| `screening.md` | §4 Resolve, §5 Truy xuất ứng viên, §6 Sàng lọc constraint |
| `ranking.md` | §7 Độ hợp bối cảnh, §8 Xếp hạng, §9 Đa dạng và cỡ shortlist |
| `curation.md` | §10 So sánh, §11 Thẻ ứng viên, §12 Người dùng tuyển chọn, §14 Chạy lại khi đầu vào đổi |
| `feasibility.md` | §13 Khả thi của tổ hợp |
| `agent.md` | §19 Trợ lý Lựa chọn |
| `reference.md` | §15 Output, §16 Ví dụ, §17 Đánh giá, §18 CLI và API, §20 Tag và subtag |

### 5.4 `PLANNING.md` → `docs/planning/`

| Mới | Lấy từ |
|---|---|
| `README.md` | Mục tiêu, Phạm vi, Nguyên tắc, Đầu vào, sơ đồ ⓐ→ⓗ, Giới hạn đã biết |
| `live-context.md` | Live Context (OSRM, Điều kiện từng ngày, Trạng thái vận hành theo thời điểm) |
| `lodging.md` | ⓐ Ứng viên chỗ ở, Chỗ ở không làm người dùng chờ |
| `days-route-schedule.md` | ⓑ Chia ngày, ⓒ Thứ tự trong ngày, ⓓ Giờ / tham quan / đệm / nghỉ, Độ phù hợp giờ ghé, Chi tiết địa điểm |
| `validate-robustness.md` | ⓔ Kiểm tra cuối, ⓕ Độ vững, ⓖ Mục tiêu và phương án, ⓗ Dự phòng |
| `revise.md` | Vòng người dùng sửa và góp ý, Tính lại và cache |
| `eve-expert.md` | Đổi lịch tối trước ngày đi, Local Expert |
| `agent.md` | Agent đề xuất nội bộ, Guardrail, Trợ lý Lịch trình |
| `reference.md` | Ranh giới module, Plan Output, CLI và API, Cấu hình, Test, Đo |

### 5.5 Còn lại

| Mới | Lấy từ |
|---|---|
| `agents/README.md` | `AGENT_HARNESS.md` §1, §5; phần lõi trợ lý chung đang nằm ở TRIP §19 và DECISION §19 |
| `agents/harness.md` | `AGENT_HARNESS.md` §2, §3, §4 |
| `web/screens.md` | `Role_Web_Functional_Design.md` (cả §6 màn ↔ file) |
| `web/design.md` | `UI_SPEC_USER_WEB.md` §5–§9, `UX_Design_Brief.md` §3, §4, §6, §7, `UI_SPEC_FLOW_LAYOUT.md` §2–§6. Phần "giao cho designer / câu hỏi mở" bỏ hoặc ADR |
| `web/landing.md` | `UI_SPEC_LANDING.md` |
| `web/README.md` | viết mới từ code `web/src/` |
| `space3d/README.md` | viết mới từ `2026-11-09-3d-scale-design.md`, các bàn giao 3D và code `scripts/diorama/` |
| `adr/` | `ARCHITECTURE.md` §8 Quyết định thiết kế chính; bất biến trong `AGENTS.md`; các câu có ngày trong bốn file giai đoạn |

ADR viết trước (đã thấy rõ trong tài liệu hiện có):
- Offline ghi Place Intelligence, online chỉ đọc.
- `unknown` ≠ `false`: chưa rõ thì vẫn hiện, xếp sau, cảnh báo (04/11/2026).
- Physical constraint chỉ cảnh báo, người dùng quyết (08/11/2026).
- User Profile là prior.
- Module chỉ gọi nhau qua public API.
- Gọi model theo vai trò.
- Mỗi nguồn ngoài một module.
- Journey pin corpus release.
- Prod chạy bản đông cứng `.prod_src/`.
- Chọn nơi không nhắc "chọn ít quá".
- Chỉ dựng 3D cho nơi đặc biệt.

## 6. Chỗ code trỏ vào tài liệu

Có 427 chỗ, nên làm bằng công cụ chứ không sửa tay.

1. `scripts/doc_refs.py`:
   - `check`: liệt kê mọi `docs/<path>.md §<mục>` trong repo, báo chỗ nào file hoặc mục không tồn tại.
   - `rewrite --map <bảng>`: đổi theo bảng ánh xạ ở §5.
2. `tests/test_doc_refs.py` chạy `check`. Từ đó đổi tên mục mà quên sửa chỗ trỏ thì test đỏ.
3. Chạy `check` trên hiện trạng trước để biết bao nhiêu chỗ trỏ đã hỏng sẵn.
4. Quy ước trỏ mới: `docs/planning/lodging.md §Ứng viên chỗ ở`. Trỏ theo tên mục, không trỏ theo số, vì số đổi khi chèn mục.

## 7. Dọn `docs/plans/`

| File | Việc |
|---|---|
| `2026-10-12-corpus-semantic-index-design.md` | Đối chiếu code. Lớp A chưa làm thì giữ; phần đã làm đã ở CORPUS |
| `2026-10-26-production-and-course-upgrade-design.md` (799 dòng) | Đối chiếu từng mục: đã làm thì gộp vào tài liệu mới, quyết định thì thành ADR, chưa làm thì hỏi chủ dự án. Rồi xóa |
| `2026-10-31-guided-tour-design.md`, `…-HANDOFF.md` | Tour đã có (`Role_Web_Functional_Design` §2.14): gộp vào `web/screens.md`, xóa |
| `SPACE_3D_HANDOFF.md`, `DIORAMA_BATCH_HANDOFF.md`, `AUTO3D_WORKFLOW_HANDOFF.md` | `3d-scale-design` đã ghi là thay ba file này. Số liệu và bài học vào `space3d/README.md`, xóa |
| `2026-11-09-3d-scale-design.md`, `…-plan.md` | Phần đã làm vào `space3d/README.md`. Xóa khi batch 3D xong |
| `2026-11-10-3d-scale-HANDOFF.md`, `2026-11-10-space3d-tour-interior-HANDOFF.md` | Giữ khi việc 3D còn chạy |
| `2026-11-09-repo-structure-proposal.md`, `2026-11-10-system-review-HANDOFF.md` | Giữ (chờ chủ dự án quyết). Phần tài liệu (§5) do plan này thay |
| `NORMALIZED_CORPUS_RAG_ONLINE_PROPOSAL.md`, `PLANNING_IMPROVEMENT_PROPOSAL.md` | Đối chiếu code: đã làm thì gộp; chưa làm thì chủ dự án chọn giữ làm đề xuất hay xóa |
| `TAG_EXPANSION_NOTES.md` | Còn mở thì giữ; đã chốt thì thành ADR |

## 8. Thứ tự làm

Mỗi bước là một commit, có kiểm chứng; viết xong mỗi stage thì chủ dự án đọc trước khi sang stage sau.

| Bước | Việc | Kiểm chứng |
|---|---|---|
| 0 | Commit các thay đổi đang dở trong working tree (khoảng 30 file), để diff tài liệu sạch. Sửa `RULE.md` §0.1 (ADR là ngoại lệ có ngày; ngân sách KB; cây thư mục) | chủ dự án duyệt |
| 1 | `scripts/doc_refs.py` + `tests/test_doc_refs.py`; chạy trên hiện trạng | danh sách chỗ trỏ hỏng sẵn |
| 2 | **Thử:** `agents/README.md` + `docs/planning/` + 3 ADR | test doc refs xanh; mỗi file trong ngân sách; mọi file / test được nhắc tồn tại; **chủ dự án đọc và duyệt khuôn** |
| 3 | `decision/`, rồi `trip/`, rồi `corpus/` (mỗi stage một commit) | như bước 2 |
| 4 | `web/`, `space3d/`, `GLOSSARY.md`, làm gọn các file giữ nguyên | như bước 2 |
| 5 | Viết lại `ARCHITECTURE.md` cuối cùng; sửa `README.md` §Tài liệu, bảng "Vào việc từ đâu" trong `AGENTS.md` | người chưa đọc repo hiểu hệ thống trong 10 phút |
| 6 | Dọn `docs/plans/` theo §7; xóa các file cũ đã tách hết | `doc_refs check` sạch |

**Viết đúng code, không chỉ chép lại.** Mỗi thẻ thuật toán và thẻ agent viết sau khi đọc code thật (dùng codegraph nếu đã cài). Chỗ nào tài liệu cũ khác code thì tài liệu mới theo code. Nếu nghi code sai thì ghi vào §10 của file này để chủ dự án quyết, không sửa code trong đợt này.

**Ước lượng:** bước 2 khoảng một phiên; mỗi stage ở bước 3 một phiên (corpus có thể hai); bước 4–6 một đến hai phiên.

## 9. Cần chủ dự án quyết

1. Duyệt cây thư mục §3 và ngân sách §2.
2. Thêm `docs/adr/` vào `RULE.md` §0.1 làm ngoại lệ được ghi ngày, như `DEV_LOG`.
3. Cờ `discovery` của Trip đang bật hay tắt ở prod? Tài liệu chỉ tả luồng đang chạy.
4. `CORPUS.md` §Sai lệch cho bản demo: còn đúng không, giữ ở đâu?
5. Hai đề xuất `NORMALIZED_CORPUS_RAG_ONLINE_PROPOSAL`, `PLANNING_IMPROVEMENT_PROPOSAL`: giữ hay bỏ phần chưa làm?
6. Có cài codegraph (đọc code bằng đồ thị, chạy local) trước bước 2 không?

## 10. Phát hiện khi viết

(Trống. Ghi các chỗ tài liệu cũ khác code trong lúc làm.)
