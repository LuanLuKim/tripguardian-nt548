# Dàn ý và nội dung báo cáo Phase 1–2 — TripGuardian (bản giao cho agent viết)

> Lập 12/11/2026. Nguồn sự thật: `main` của repo nộp `se373agenticengineering/nhom-44` tại `885439d4` (sau đồng bộ 12/11). Mọi đường dẫn bên dưới là đường dẫn trong repo đó.
> File này **không phải bản báo cáo**. Nó là dàn ý + dữ kiện đã kiểm để agent khác viết bản cuối (Markdown).

## A. Hướng dẫn cho agent viết

**Sản phẩm cần viết:** một file Markdown "Tóm tắt các phần đã hoàn thành Phase 1–2", nộp cùng video demo. Đặt ở `docs/submission/phase-1-2/PHASE_1_2_SUMMARY.md` trên nhom-44 (thay vai trò của `PHASE_1_2_SUMMARY.docx` cũ). Không xuất Word.

**Người đọc:** giảng viên môn SE373. Họ chấm theo yêu cầu tối thiểu của từng phase (bảng ở §B), không cần hiểu hết code. Viết để họ tìm được bằng chứng của mỗi yêu cầu trong 1–2 phút.

**Quy tắc viết:**
- Tiếng Việt; tên code, lệnh, đường dẫn để trong backtick.
- Dài 4–6 trang khi in (khoảng 1.800–2.800 từ). Bảng nhiều hơn văn xuôi.
- Mỗi yêu cầu: **trạng thái** (Đạt / Đạt một phần / Chưa), **bằng chứng** (đường dẫn file, lệnh chạy, số đo), **giới hạn** nếu có. Chỉ dùng dữ kiện trong file này; không tự thêm số, không làm tròn lên.
- "Đạt một phần" phải ghi rõ phần nào chưa có và việc đó nằm ở đâu trong kế hoạch Phase 3. Không viết lách để một mục trông như đã xong.
- Không nhắc tính năng ngoài yêu cầu quá một dòng (3D, linh vật, Bài viết / cộng đồng, analytics, tài khoản, thông báo). Có thể gom vào một mục "Ngoài yêu cầu tối thiểu" ở cuối §5.
- Giữ đoạn **minh bạch nguồn gốc** (§C.1): codebase là baseline từ MLAI Hackathon 2026, import vào repo môn học 06/11/2026; có dùng công cụ AI hỗ trợ.
- Chỗ chưa có dữ liệu thì để placeholder dạng `[ĐIỀN: …]`, không bịa: họ tên / MSSV, link video, số issue mới.

**Số issue (đã đọc từ GitHub tối 12/11/2026, sau khi chủ dự án gộp issue):**

| Việc | Issue | Trạng thái |
|---|---|---|
| Phân công UC, tag phase-1 / phase-2 | #24 | đóng |
| Video demo + file tóm tắt Phase 1–2 | #25 | mở (chính là đợt nộp này) |
| CI: Actions bị chặn do billing | #26 | mở |
| `evals/` UC-01 ≥ 10 case | #27 | đóng |
| `skills/` 2 skill có contract | #28 | đóng |
| Trace JSONL theo `run_id` | #29 | đóng |
| LangGraph `interrupt()` + checkpointer bền | #30 | mở |
| RAG trích dẫn `[doc_id §section]` (Phase 2) | #31 | đóng, gộp vào #38 |
| UC-01 đúng schema đề + route plan / ask_user / unsupported | #35 | mở |
| UC-02 itinerary + validator + 6 case | #36 | đóng |
| UC-03 nối kho tri thức vào agent + validator trích dẫn | #38 | mở |
| UC-04 sự cố, resume, nén context 5 mục | #41 | mở |
| Báo cáo kỹ thuật §7 (cuối kỳ) | #49 | mở |
| 4 lỗi UC-01 tìm thấy khi chạy eval 12/11 | chưa tạo: nội dung ở `docs/plans/2026-11-12-uc01-eval-issues.md` | `[ĐIỀN: số issue sau khi tạo]` |

Milestone đang mở: M0 Bù Phase 1–2 (11–12/11), M1 P3.1 (13–19/11), M2 P3.2 (20–28/11), M3 P3.3 (29/11–06/12), P3 App điện thoại (12/11–06/12).

## B. Yêu cầu của đề (ảnh lộ trình môn học)

| Phase | Thời gian | Yêu cầu tối thiểu |
|---|---|---|
| 1 · Bootstrap dự án | 07/10 – 27/10 (buổi 1–5) | Đăng ký nhóm, đề tài, use case và người sở hữu · Repo, CI, codebase ứng dụng và codebase agent · Agent loop ≥ 2 tool, 1 skill, có log từng bước · 1 use case chạy từ ứng dụng tới agent, ≥ 10 eval case |
| 2 · Mở rộng năng lực | 28/10 – 10/11 (buổi 6–8) | RAG có trích dẫn nguồn · Lưu state, dừng rồi chạy tiếp, nén context · Workflow LangGraph có bước người duyệt · ≥ 3 use case chạy được |
| 3 · Hoàn thiện và nộp | 11/11 – 06/12 (buổi 9–11) | Eval đầy đủ chạy lại so sánh · Multi-agent hoặc MCP · Kiểm thử an toàn, xem trace · ≥ 5 use case phủ 8 mảng kiến thức; báo cáo, video |

Cuối mỗi phase: gắn tag trên repo và nộp video demo ngắn. Nộp đợt này: **1 video demo + 1 file tóm tắt**. Mỗi phase chỉ dùng kiến thức đã học tới lúc đó, nên báo cáo không trình bày MCP / multi-agent như phần của Phase 2.

## C. Dàn ý báo cáo và nội dung từng mục

### 1. Thông tin chung (≈ 0,3 trang)

- Tiêu đề: "TripGuardian — Tóm tắt Phase 1 và Phase 2". Dòng phụ: SE373 · Nhóm 44 · Đề tài 08 Tour Guide Agent · Điểm đến Đà Lạt · ngày nộp.
- Bảng thành viên: lấy từ `docs/submission/TEAM.md` (4 tài khoản GitHub: LuKimLuan-UIT, hohoangluan, dinhlong06, dthanhman; mảng phụ trách; UC sở hữu). Cột họ tên / MSSV: `[ĐIỀN]`.
- Repo: `github.com/se373agenticengineering/nhom-44` (private). Commit nộp: `885439d4` hoặc commit gắn tag (§C.9). Video: `[ĐIỀN: link]`.
- **Minh bạch nguồn gốc** (giữ ý của bản cũ): codebase là baseline TripGuardian do thành viên nhóm phát triển cho MLAI Hackathon 2026, import vào repo môn học ngày 06/11/2026 (commit `eaeef5b`). Ngày 12/11/2026 nhóm đồng bộ repo nộp với bản đang chạy trên server (PR #65–#69, ghi chép ở `docs/log/SYNC_2026-11-12.md`). Có dùng công cụ AI (Claude Code) hỗ trợ code và tài liệu; nhóm kiểm tra trước khi nộp.

### 2. Tổng quan hệ thống (≈ 0,5 trang)

Nội dung:
- Bài toán: người đi tự túc mất nhiều thời gian lọc blog / TikTok / Maps mà vẫn không biết nơi nào hợp, nơi nào đông, lịch có đi nổi không. TripGuardian giúp **chọn đúng nơi trước khi lên lịch**, rồi **kiểm tra tổ hợp đã chọn có đi được cùng nhau không**.
- Bốn giai đoạn, mỗi giai đoạn một package, giao tiếp qua public API (`__init__.py`):

| Giai đoạn | Package | Việc |
|---|---|---|
| Place Intelligence (offline) | `ai/src/corpus/` | Địa điểm → fact / signal / estimate có bằng chứng và nguồn |
| Trip Understanding | `ai/src/trip/` | Hội thoại tự do → Trip State có cấu trúc → Search Input |
| Place Decision | `ai/src/decision/` | Shortlist, lọc cứng, xếp hạng có giải thích, người dùng tuyển chọn → Decision Output |
| Planning & Validation | `ai/src/planning/`, `backend/src/live/` | Chia ngày, thứ tự, thời gian di chuyển, thời tiết, validator, độ vững, dự phòng → Plan Output |

- Phần dùng chung: lõi agent `ai/src/agents/` (vòng LangGraph, tool, skill, trace); harness HTTP/SSE `backend/src/harness/`; tài khoản + Postgres `backend/src/accounts/`, `backend/src/db/`; giao diện React + MapLibre `frontend/` (User Web và Admin Web).
- Bất biến sản phẩm (nêu ngắn, vì nó giải thích nhiều quyết định ở §4–§6): không bịa địa điểm; thiếu bằng chứng là `unknown`, không phải `false`; hệ thống chỉ cảnh báo, quyết định cuối cùng của người dùng (lịch có vi phạm vẫn hiện và chốt được sau khi xác nhận).
- Hình gợi ý: sơ đồ 4 giai đoạn + harness + web. Nguồn để vẽ: `docs/architecture/ARCHITECTURE.md` §3, `docs/submission/ARCHITECTURE_MODULES.md`.

### 3. Đối chiếu Phase 1 (≈ 1 trang)

Một bảng chính (Yêu cầu · Trạng thái · Bằng chứng), sau đó mỗi dòng một đoạn ngắn.

| Yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|
| Đăng ký nhóm, đề tài, UC và người sở hữu | Đạt (nộp bù) | `docs/submission/TEAM.md`: 4 vai trò, 7 UC phủ K1–K8, mỗi người sở hữu ≥ 1 UC; đề bài `docs/submission/2026-10-06_de_tai_08_tour_guide_agent.docx` |
| Repo, CI, codebase ứng dụng và agent | Đạt; CI chưa chạy được trên GitHub | Repo theo module `ai/`, `backend/`, `frontend/`, `evals/`, `skills/`. Workflow `.github/workflows/test.yml` có trên `main`; GitHub Actions không khởi động job vì lỗi thanh toán / hạn mức của tài khoản. Biên bản chạy tay: §3.2 |
| Agent loop ≥ 2 tool, 1 skill, log từng bước | Đạt | §3.3 |
| 1 UC từ ứng dụng tới agent, ≥ 10 eval case | Đạt | UC-01: Web → harness → Trip agent → Trip State. `evals/uc01/cases.yaml` 12 case, chạy thật 12/11: 7/12 đạt; §3.4 |
| Tag + video | Đạt (nộp bù) | Tag `phase-1` → `eaeef5b`; tag `phase-2` hiện ở `eb3ba29` (trước đồng bộ 12/11; xem §C.9) |

**3.1 Codebase.** Python 3.12 (agent, backend), React/TypeScript (web). Module chỉ gọi nhau qua public API. Model gọi theo **vai trò** (Extractor, Judge, Agent, ASR), model cụ thể nằm ở config, key ở `.env` (`docs/services/LLM_PROVIDER.md`).

**3.2 Test và CI (biên bản chạy tay ngày 12/11/2026, trên cây `main` sau đồng bộ, máy không có `data/`, `pytest -m "not live"`):** 5.486 pass · 1 fail · 438 skip, không lỗi thu thập. Test fail duy nhất `ai/tests/trip/test_knowledge.py::test_weather_at_the_center` cũng fail trên bản local trước đồng bộ (chưa sửa). Frontend `npx tsc -b` không lỗi. Nguồn: `docs/log/SYNC_2026-11-12.md` §7. Skip phần lớn do thiếu dữ liệu ngoài git (review crawl không đưa lên repo vì quyền tác giả).

**3.3 Agent loop, tool, skill, log.**
- Vòng agent: `ai/src/agents/assistant/loop.py`, hàm `run_loop`. Đồ thị LangGraph `StateGraph(LoopState)` có ba node: `agent` (gọi model, stream), `execute` (chạy tool call qua `ToolNode` của LangGraph, từng call theo thứ tự model đưa), `review` (luật của stage gửi lại câu trả lời sai luật cho model một lần). Cạnh có điều kiện `agent → execute | review | END`, `execute → agent`, `review → agent`. Giới hạn bước: `recursion_limit = 2·max_steps + 4`; tối đa 4 lỗi tool mỗi lượt (`MAX_TOOL_FAILS`) rồi dừng và trả lời dự phòng. Tham số tool sai schema bị từ chối và trả lỗi cho model, không tới tool.
- Tool: **84 tool** đăng ký qua decorator `read_tool` / `action_tool` (`ai/src/agents/assistant/`), mỗi tool một model Pydantic làm schema, docstring là mô tả model đọc. Ví dụ theo nhóm: đọc dữ liệu (`search_places`, `get_place`, `place_evidence`, `compare_places`, `why_here`, `why_not`), dữ kiện sống (`weather`, `climate`, `route_time`, `distance`), ghi hồ sơ chuyến (`record_fact`, `resolve_relative_date`, `ask_user`, `quick_replies`), thao tác lịch (`move_place`, `swap_place`, `reorder_day`, `undo`), web (`web_search`, `web_read`).
- Skill: 3 skill có contract đầy đủ ở `skills/` (frontmatter `name`, `description`, `version`, `owner`, `tools`; mục khi nào dùng, đầu vào, đầu ra, các bước): `interpret-trip-requirements` (Trip agent nạp từ `skills/` vào đầu system prompt), `itinerary-planning`, `site-narration` (UC-03, xem §4.1).
- Log từng bước: trace JSONL theo lượt chạy, `ai/src/agents/trace.py`; mô tả ở `docs/architecture/AGENT_HARNESS.md` §6. Mỗi request `turn` có `run_id`; file `<DATA_DIR>/traces/<trip_id>/<run_id>.jsonl`, mỗi dòng một bước: `run_start`, `guardrail`, `skill`, `model_call` (thời gian, TTFT, token vào / ra / cache, số tool call), `tool_call` (tên, tham số, kết quả, ms, lỗi), `review` (lý do gửi lại), `outcome` (`agent` / `fallback` / …), `error`, `run_end` (tổng thời gian, tổng token, chi phí ước tính). Trước khi ghi: tọa độ làm tròn 2 chữ số, trích review / quote thay bằng `[omitted]`, chuỗi > 200 ký tự bị cắt. Đọc lại: `python -m agents.trace --run-id <id>` hoặc `--trip-id <id>`. Ví dụ trace thật: Phụ lục C.
- Hình gợi ý: sơ đồ node `agent → execute / review → agent`; một đoạn JSONL 6–8 dòng (Phụ lục C).

**3.4 UC-01 và eval.**
- Luồng: người dùng gõ tự do trên web → `POST` tới harness (`backend/src/harness/`) → Trip engine (`ai/src/trip/`) chạy vòng agent với skill `interpret-trip-requirements` → Trip State (mỗi trường có giá trị, nguồn là câu gốc, trạng thái xác nhận) → khi đủ thông tin thì ra Search Input cho Place Decision. Thiếu thì agent hỏi đúng phần thiếu; mâu thuẫn thì đánh dấu.
- Ràng buộc cứng (ngày, số người, ngân sách, phương tiện) tách khỏi sở thích mềm ("không thích đông").
- Eval: `evals/uc01/cases.yaml` **12 case**, đủ 5 loại bắt buộc của đề (`full`, `missing`, `conflict`, `english`, `unsupported`) + 7 case `other`. Bộ chấm giấu khỏi agent: chỉ `turns` đi vào agent, `expect` ở lại bộ chấm. Một lượt là câu người dùng gõ, hoặc thao tác bấm trên thẻ cổng trước lịch (`{deck: {care: [none]}}`), đúng như web gửi. Chạy: `python -m evals.run --uc uc01` (`--dry-run` chỉ kiểm file case). Kết quả ra `evals/results/<run_id>.json`: từng case có kỳ vọng / thực tế / pass / độ trễ; tổng có `pass_rate`, `route_accuracy`, `hard_constraint_accuracy`, `latency_p50_s`.
- Chấm theo **cổng trước lịch** của Trip đang chạy (chủ dự án 10/11/2026): chỉ ngày đi và nhóm `care` (lưu ý sức khỏe, đi lại, ăn uống) chặn lập lịch; số người, phương tiện, nhịp, ngân sách, chỗ ở được hỏi nhưng bỏ qua được. Case thiếu những mục này kỳ vọng `plan` và chấm việc agent **không tự đoán** (giá trị phải là `null`).
- **Kết quả chạy 12/11/2026** (`evals/results/20261112T150821Z_uc01.json`, code `e6acca23`): **7/12 case đạt (58,3%)**, đọc đúng ràng buộc cứng **94,6%** (mục tiêu của đề ≥ 90%), route đúng 58,3%, độ trễ p50 **4,6 s** mỗi case. Chi tiết và 5 case fail: Phụ lục B. Cả 5 case fail đều là lỗi thật của Trip, đã viết thành issue (§7), không phải lỗi chấm.
- Lịch sử bộ case (ghi ngắn, để giải thích nếu giảng viên so với bản cũ): bản 11/11 (11 case) coi ngân sách và số người là bắt buộc. Sau khi đồng bộ 12/11 lấy Trip của server làm chuẩn, bản đó chỉ đạt 1/11 vì lệch luật cổng, không phải vì agent sai. Bộ case được chỉnh theo luật cổng, runner sửa lỗi không đọc được câu trả lời dạng stream, thêm 1 case.
- Bộ benchmark có sẵn từ baseline (không thay `evals/`, chỉ bổ sung): `ai/config/bench/bench_*.yaml`, **397 case** cho trợ lý (lõi 45, guardrail 102, tri thức 50, ảnh 32, hội thoại thật 27, dịch vụ 8, tag 13, tổng hợp 30, trợ lý Chọn nơi 49, trợ lý Lịch trình 41). Chạy bằng `python -m bench` (`docs/testing/BENCHMARKS.md`).

### 4. Đối chiếu Phase 2 (≈ 1,5 trang)

| Yêu cầu | Trạng thái | Bằng chứng tóm tắt |
|---|---|---|
| RAG có trích dẫn nguồn | Đạt một phần | Bằng chứng địa điểm có nguồn + ngày (chạy trong app); kho tri thức UC-03 có truy xuất + eval, chưa nối vào agent |
| Lưu state, dừng rồi chạy tiếp | Đạt | Postgres có revision, idempotent theo `request_id`, web khôi phục đúng bước |
| Nén context | Đạt một phần | Cửa sổ lịch sử cắt theo khối + Trip State mang nội dung đã nói; chưa có tóm tắt bằng model |
| Workflow LangGraph có bước người duyệt | Đạt một phần | LangGraph cho vòng agent; người duyệt ở tầng ứng dụng; chưa dùng `interrupt()` + checkpointer bền |
| ≥ 3 use case chạy được | Đạt | UC-01 · Chọn nơi có bằng chứng · UC-02 (+ Đang đi) |

**4.1 RAG có trích dẫn nguồn.** Hai lớp, viết tách bạch:

(a) **Bằng chứng địa điểm, đang chạy trong app.**
- Corpus Place Intelligence dựng offline từ review Google Maps và video / bình luận TikTok (`docs/corpus/CORPUS.md`): mỗi fact / signal giữ nguồn, ngày, cỡ mẫu. Chỉ mục ngữ nghĩa (LanceDB) cho tìm kiếm theo câu / ảnh ("chỗ như này").
- Agent truy xuất qua tool (`search_places`, `place_evidence`, `compare_places`, `why_here`…). Kết quả mang nguồn và ngày; trường corpus không có trả `"unknown"`, và lỗi tool hướng dẫn model "không có dữ liệu thì nói vậy, đừng đoán" (`ai/src/trip/agent/knowledge_tools.py`).
- Trên web: thẻ nơi có "Vì sao phù hợp / Đánh đổi / Độ tin cậy"; Chi tiết có giá trị + nguồn + ngày kiểm tra, xu hướng bình luận kèm cỡ mẫu và link về clip gốc.
- Giới hạn cần ghi: nguồn là nội dung crawl, chỉ dùng nghiên cứu, không có giấy phép tái sử dụng; không đưa lên repo public.

(b) **Kho tri thức thuyết minh UC-03 (đang làm, Phase 3).**
- `ai/knowledge_base/dalat/docs/`: **21 tài liệu** Markdown (20 tài liệu thật từ Wikipedia / Wikivoyage vi + en, CC BY-SA 4.0, lấy 09/11/2026; 1 tài liệu cài lệnh giả để thử prompt injection). Bảng nguồn và giấy phép sinh tự động: `ai/knowledge_base/dalat/SOURCES.md`.
- Package `ai/src/knowledge/`: cắt theo mục (`chunking`), truy xuất lai BM25 + embedding `BAAI/bge-m3` gộp RRF (`retrieval`), định dạng trích dẫn `[doc_id §section]` (`citations.CITATION`), bộ chấm (`evaluation`).
- Eval retrieval-only (`evals/uc03/golden.jsonl`, 30 câu; kết quả `evals/uc03/results/2026-11-11_hybrid.json`, k = 5):

| Loại câu | n | Recall@5 | MRR |
|---|---|---|---|
| date | 8 | 1,00 | 0,875 |
| general | 10 | 1,00 | 0,883 |
| cross_lingual | 4 | 0,50 | 0,175 |
| compare | 3 | 0,67 | 0,611 |
| injection | 1 | 1,00 | 0,200 |
| no_answer | 4 | — | — |

- Chưa xong (ghi thẳng): hàm kiểm trích dẫn `check_citations` mới có khung (`NotImplementedError`); tool `retrieve_knowledge` mà skill `site-narration` khai báo chưa đăng ký vào agent, nên thuyết minh có trích dẫn chưa chạy trong app; câu hỏi khác ngôn ngữ còn yếu (Recall 0,5). Kế hoạch: Phase 3, milestone M1.

**4.2 Lưu state, dừng rồi chạy tiếp.**
- Mỗi hành trình (journey) là một dòng bảng `journeys` trên Postgres (`backend/src/harness/pgstore.py`, migration `backend/migrations/001_init.sql`): envelope `jsonb` + `stage`, `revision`, `user_id`. Ghi bằng `UPDATE … WHERE revision = <revision đã đọc>`; người ghi thứ hai nhận 409 thay vì đè.
- Mutation idempotent theo `request_id`: gửi lại cùng request trả receipt đã lưu, không chạy lại. Web lưu request đang chờ trong `localStorage`, tải lại trang thì gửi lại đúng ID.
- Khởi động lại server khôi phục module từ snapshot đã commit, **không gọi lại LLM** để phát lại phiên.
- Người dùng: đóng tab giữa chừng → `Chuyến của tôi` → mở lại đúng bước, đúng lựa chọn, đúng bản sửa cuối (video phần 5).
- Nguồn: `docs/architecture/AGENT_HARNESS.md` §3.

**4.3 Nén context.**
- `ai/src/agents/assistant/context.py`: model đọc system prompt tĩnh → cửa sổ lịch sử → `CURRENT CONTEXT` (Trip State hiện tại dạng JSON) → câu mới của người dùng.
- `window()`: giữ nguyên văn tối đa 24 lượt người dùng (`HISTORY_KEEP`); vượt thì bỏ 12 lượt cũ nhất một lần (`HISTORY_DROP`), để phần đầu prompt giữ nguyên 12 lượt liền và cache prompt của nhà cung cấp còn hiệu lực. Nội dung các lượt bị bỏ vẫn còn trong Trip State, nên không mất thông tin đã thu.
- Thẻ địa điểm / ảnh chỉ giữ 2 lượt gần nhất trong `CURRENT CONTEXT` (`SLOT_KEEP`).
- Trace ghi `tokens_cached` mỗi lượt gọi model, đo được hiệu quả cache.
- Chưa có: tóm tắt hội thoại bằng model (kế hoạch: UC-04, Phase 3).

**4.4 Workflow LangGraph có bước người duyệt.**
- LangGraph: vòng agent ở §3.3 (`StateGraph`, `ToolNode`, checkpointer `MemorySaver` theo `thread_id` từng lượt).
- Bước người duyệt (tầng ứng dụng, không phải node của đồ thị):
  1. Tóm tắt chuyến đi: người dùng xem và sửa Trip State trước khi tìm nơi.
  2. Tuyển chọn: agent đề xuất shortlist, **người dùng** thêm / bỏ / khóa; agent không tự chọn.
  3. Quá tải: Planning đưa ba phương án, người dùng chọn; agent không chọn thay.
  4. Chốt lịch: vi phạm (vượt ngân sách, giờ mở cửa chưa xác nhận…) hiện ngay tại điểm dừng; bấm Chốt thì hệ thống hỏi lại, người dùng xác nhận mới chốt. Quy tắc "vượt ngân sách chỉ cảnh báo, vẫn chốt được" là đổi ý tưởng so với PR #61 ban đầu (ghi chú trong `docs/planning/PLANNING.md` §Validator).
  5. Ghi ra ngoài: xuất Google Calendar luôn **xem trước → xác nhận**.
- Chưa có: `interrupt()` của LangGraph + checkpointer bền (Postgres) để dừng đồ thị chờ người duyệt. Hiện state bền nằm ở harness (§4.2), không ở checkpointer. Kế hoạch Phase 3 (UC-04 / UC-05).

**4.5 Ba use case chạy được.**

| UC | Mô tả | Chạy ở đâu | Eval / kiểm chứng |
|---|---|---|---|
| UC-01 Thu thập nhu cầu thành hồ sơ chuyến đi | Hội thoại tự do → Trip State → Search Input; hỏi phần thiếu, đánh dấu mâu thuẫn | Web: Tạo chuyến / Tìm hiểu | `evals/uc01` 12 case, 7/12 đạt, ràng buộc cứng 94,6% (§3.4) |
| Chọn nơi có bằng chứng (Place Decision) | Shortlist theo nhóm, lọc cứng: có bằng chứng trượt thì loại, chưa rõ thì vẫn hiện, xếp sau, cảnh báo ở ô Đánh đổi; giải thích, so sánh, tuyển chọn | Web: Chọn nơi | `bench_decision_assistant.yaml` 49 case; test `ai/tests/decision/` |
| UC-02 Lịch trình nhiều ngày có kiểm tra ràng buộc | Chia ngày, thứ tự, thời gian di chuyển OSRM, thời tiết Open-Meteo, giờ mở cửa, ngân sách; validator bằng code; nhãn độ vững; dự phòng; hoàn tác | Web: Lịch trình | `evals/uc02/golden.yaml` **6 case vàng, 6/6 đạt** (12/11/2026, `python -m planning evaluate --uc02`, 0 lỗi grounding; chuyến 3 ngày p50 20 ms, p95 3,2 s); `bench_planning_assistant.yaml` 41 case |
| (thêm) Đang đi | Sau khi chốt: thẻ từng điểm, check-in tự nguyện, Calendar có xác nhận | Web: Hôm nay | `docs/services/COMPANION.md` |

Sáu case UC-02: lịch 3 ngày thoải mái; nhóm có ngân sách 1,5 triệu (vượt → cảnh báo `trip_budget`, vẫn chốt); mưa lớn (nơi ngoài trời); nơi đóng cửa thứ Hai; gia đình đi chậm; vùng cấm. Validator kiểm từng lịch bằng `check_uc02_itinerary` (`ai/src/planning/evaluate.py`).

### 5. Kiến trúc kỹ thuật tóm tắt (≈ 0,5 trang, tùy chọn)

Chỉ viết nếu còn chỗ. Một hình + 5 gạch đầu dòng:
- Web React → harness HTTP/SSE (`backend/src/harness/`) → engine của từng stage → vòng agent dùng chung → tool đọc corpus / dữ kiện sống.
- Router và handoff giữa stage: `docs/architecture/AGENT_HARNESS.md` §2.
- Guardrail chặn câu ngoài phạm vi trước khi tới model (dòng `guardrail` trong trace); bench guardrail 102 case.
- Dữ kiện sống: OSRM (thời gian đi), Open-Meteo (thời tiết), có TTL và cảnh báo khi thiếu (`backend/config/live/live.yaml`).
- Physical constraint (giờ đóng cửa, thời gian đi) không có đường code nào nới; hệ thống chỉ cảnh báo, người dùng quyết.

### 6. Phân công và đóng góp (≈ 0,3 trang)

- Bảng UC ↔ chủ sở hữu ↔ mảng K từ `docs/submission/TEAM.md` §Sở hữu use case.
- Đóng góp trong Phase 2 trên repo nhom-44 (theo PR đã merge ngày 11–12/11):
  - dthanhman: khung `evals/` + bộ UC-01 (#59), contract đầy đủ cho skill + Trip nạp skill từ `skills/` (#60), trace JSONL theo `run_id` (#62), bỏ qua test khi thiếu dữ liệu / phụ thuộc tùy chọn (#57, #63).
  - dinhlong06: tái cấu trúc repo theo module `ai/` `backend/` `frontend/` (#58), sửa gói dữ liệu và OAuth Google; UC-02 validation (#61, nhóm sửa lại thành "vượt ngân sách chỉ cảnh báo").
  - hohoangluan: web UI, 3D, backend phục vụ web, AI (planning, trip, decision, corpus) đồng bộ từ bản đang chạy (#65–#68).
  - LuKimLuan-UIT: điều phối, tài liệu, vận hành, đồng bộ (#69), kho tri thức UC-03; chỉnh bộ eval UC-01 theo cổng trước lịch và chạy eval có model ngày 12/11 (cùng hohoangluan).
- Tên tác giả commit "Lonh" là tài khoản dinhlong06. Số PR ở trên đã kiểm với lịch sử Git; PR của hai nhánh mới (§9) điền sau khi mở.

### 7. Hạn chế đã biết (≈ 0,4 trang)

- **Giấy phép dữ liệu:** corpus địa điểm dựng từ review Google Maps và TikTok, chỉ dùng nghiên cứu, không có trong repo. Đề yêu cầu nguồn cho phép tái sử dụng kèm `source_url`, `license`, `retrieved_at`: đã làm cho kho tri thức UC-03 (CC BY-SA 4.0), bộ POI có giấy phép là việc Phase 3.
- **CI:** GitHub Actions không chạy được do thanh toán / hạn mức của tài khoản; bản workflow cập nhật (Python 3.12 như server, thêm job build web Node 24) chưa lên `main` vì token không có quyền `workflow`. Biên bản test chạy tay ở §3.2.
- **Model chỉ chạy trong mạng UIT:** eval có model và demo cần ở campus hoặc endpoint thay thế trong `.env`.
- **Bản đang chạy trên server** dùng cấu trúc thư mục cũ; trace JSONL, `evals/` và `skills/` hiện chỉ có trên repo nộp (chưa deploy).
- **Điện thoại:** web thiết kế cho máy tính; app điện thoại là milestone "P3 · App điện thoại" (#52–#54).
- **Lỗi UC-01 tìm thấy khi chạy eval 12/11** (đã viết thành issue, milestone M1; số issue `[ĐIỀN]`):
  1. Nhóm có trẻ em: bấm "Không có" ở mục lưu ý tại cổng trước lịch vẫn không qua cổng (tín hiệu `kids` do người dùng nói không được đánh dấu đã xử lý). Đây là lỗi nặng nhất: người dùng thật đi cùng trẻ em có thể kẹt ở cổng.
  2. Nói "không ai cần lưu ý gì về sức khỏe hay ăn uống" bằng lời không ghi được `care`; chỉ bấm nút mới ghi.
  3. "đi với 2 người bạn" bị ghi 2 người thay vì 3.
  4. Ngày tiếng Anh "starting December 20, 2026" không được ghi.
  5. (thuộc #35) mâu thuẫn số ngày và điểm đến ngoài dữ liệu: agent nói đúng trong câu trả lời nhưng không lưu vào Trip State, nên bộ chấm không thấy.
- Các mục "Đạt một phần" ở §4.

### 8. Kế hoạch Phase 3 (≈ 0,4 trang)

Milestone trên GitHub (đọc 12/11/2026): M1 P3.1 Dữ liệu hợp lệ, RAG, UC-01/02 (13–19/11) · M2 P3.2 Mock, đặt chỗ, sự cố, an toàn, MCP (20–28/11) · M3 P3.3 Eval regression, trace, báo cáo, video (29/11–06/12) · P3 App điện thoại (12/11–06/12). Issue chính: #32–#38 (M1), #39–#43, #45, #51, #70 (M2), #46–#50 (M3), #52–#54 (app). Bảng nội dung:

| Milestone | Hạn | Nội dung chính |
|---|---|---|
| M1 · Dữ liệu hợp lệ, RAG, UC-01/02 | 19/11 | POI và khu vực hạn chế có `source_url` / license; kho tri thức vi / en; UC-03 thuyết minh có trích dẫn chạy trong app (`retrieve_knowledge`, `check_citations`) |
| M2 · Mock, đặt chỗ, sự cố, an toàn, MCP, PWA | 28/11 | mock thời tiết + đặt chỗ; UC-05 xác nhận trước thanh toán; UC-04 sự cố, `interrupt()` + checkpointer bền; UC-08 + case tấn công; UC-10 MCP server; PWA |
| M3 · Eval, trace, báo cáo, video | 06/12 | `python -m evals.run --all` chạy 2 lần so sánh; trace mỗi UC; báo cáo cuối; video ≤ 15 phút; tag `phase-3` |

Bộ UC dự kiến (phủ K1–K8): UC-01 (K1, K5) · UC-02 (K1, K2, K7) · UC-03 (K3) · UC-04 (K4, K5) · UC-05 (K5, K8) · UC-08 (K3, K8) · UC-10 (K6, K8); dự phòng UC-06 (K6, K7).

### 9. Cách chạy lại và kiểm chứng (≈ 0,3 trang)

```sh
git clone https://github.com/se373agenticengineering/nhom-44.git && cd nhom-44
pip install -e ".[dev]"
python scripts/unpack_data.py tripguardian-data-<ngày>.zip   # gói dữ liệu trên Drive nhóm
cp .env.example .env                                          # key: docs/services/LLM_PROVIDER.md
python -m pytest -q -m "not live"                             # test
python -m evals.run --uc uc01 --dry-run                       # kiểm file case, không cần model
python -m evals.run --uc uc01                                 # eval UC-01 có model (mạng UIT)
python -m planning evaluate --uc02                            # 6 case vàng UC-02, không cần model
python -m agents.trace --trip-id <trip_id>                    # đọc trace
./run.sh start                                                # chạy toàn bộ, web ở http://127.0.0.1:5173/
```

Tag: `phase-1` → `eaeef5b`; `phase-2` → `eb3ba29` (11/11, trước các PR #59–#69). **Quyết định của nhóm** `[ĐIỀN]`: giữ nguyên, hay gắn tag mới (ví dụ `phase-2-final`) ở commit chứa báo cáo này. Báo cáo ghi đúng commit đã chọn.

**Trạng thái repo lúc lập dàn ý (12/11/2026 ~22:30).** `main` nhom-44 = `885439d4`. Hai nhánh đã commit ở máy gpu156, **chưa push** (cần quyền ghi GitHub):

| Nhánh | Commit | Nội dung |
|---|---|---|
| `eval/uc01-gate-rules` | `e6acca23`, `a952bdb3` | bộ case + runner UC-01 theo cổng trước lịch, 2 test mới cho runner (11/11 test xanh), kết quả chạy 12/11 làm mốc regression |
| `sync/web-community` | `800107e1`, `8c512707` | tính năng Bài viết của bản local (trang chính, tìm, đọc, viết; lưu trình duyệt) + tài liệu `docs/web/Role_Web_Functional_Design.md` §2.15 + mẫu thiết kế `docs/submission/design/search-blog/` (`tsc -b` xanh) |

Sau khi hai nhánh lên `main`, số commit trong báo cáo đổi theo. Agent viết lấy commit cuối của `main` lúc viết.

## Phụ lục A. Bảng đối chiếu yêu cầu ↔ báo cáo ↔ video

| Yêu cầu | Mục báo cáo | Phần video (`docs/plans/2026-11-12-phase2-demo-script.md`) |
|---|---|---|
| Đăng ký nhóm, UC, người sở hữu | §1, §6 | — |
| Repo, CI, codebase | §3.1, §3.2 | 1, 6 |
| Agent loop ≥ 2 tool, 1 skill, log | §3.3 | 2, 6 |
| 1 UC + ≥ 10 eval case | §3.4 | 2, 6 |
| RAG có trích dẫn | §4.1 | 3 |
| Lưu state, chạy tiếp, nén context | §4.2, §4.3 | 5 |
| LangGraph + người duyệt | §4.4 | 3, 4, 6 |
| ≥ 3 UC | §4.5 | 2, 3, 4 |

## Phụ lục B. Kết quả eval UC-01 (chạy 12/11/2026)

Lệnh `python -m evals.run --uc uc01`, model Agent qua endpoint trong `.env` (mạng UIT), dữ liệu Đà Lạt đầy đủ. File: `evals/results/20261112T150821Z_uc01.json`, `git_sha = e6acca23`.

| Chỉ số | Giá trị |
|---|---|
| Số case | 12 (đủ 5 loại bắt buộc) |
| Đạt | 7 (58,3%) |
| Route đúng | 58,3% |
| Đọc đúng ràng buộc cứng (ngày, số ngày, số người, ngân sách) | 94,6% |
| Độ trễ p50 mỗi case | 4,6 s |
| Token | không đo (`null`: Trip chưa xuất token qua public API; trace JSONL có token theo lượt) |

| Case | Loại | Kết quả | Lý do fail |
|---|---|---|---|
| uc01-001 | full | Fail | Có trẻ em: bấm "Không có" ở mục lưu ý vẫn bị cổng hỏi lại |
| uc01-002 | missing | Đạt | |
| uc01-003 | conflict | Fail | Agent nói ra "20/12–24/12 chưa khớp với 3 ngày" nhưng không ghi mâu thuẫn vào Trip State |
| uc01-004 | english | Fail | Không ghi ngày "December 20, 2026"; có trẻ em (như 001) |
| uc01-005 | unsupported | Fail | Agent trả lời đúng "chỉ hỗ trợ Đà Lạt" nhưng Trip State không có nhánh `unsupported` |
| uc01-006 | other | Đạt | (thiếu ngân sách: vẫn lập lịch, không tự đoán ngân sách) |
| uc01-007 | other | Đạt | (thiếu số người: không tự đoán) |
| uc01-008 | other | Đạt | |
| uc01-009 | other | Đạt | (thiếu ngày: hỏi lại) |
| uc01-010 | other | Đạt | (không có gì: hỏi ngày và lưu ý) |
| uc01-011 | other | Đạt | (sửa ngân sách ở lượt 2: giá trị sau thắng) |
| uc01-012 | other | Fail | Nói "không ai cần lưu ý" bằng lời không ghi được; "2 người bạn" ghi thành 2 người |

Gợi ý trình bày: một bảng chỉ số + bảng case rút gọn (chỉ case fail), kèm một câu: "Eval tìm ra 5 lỗi thật của Trip; mỗi lỗi đã thành issue để sửa trong M1."

## Phụ lục C. Tạo một trace thật để minh họa

Server đang chạy chưa có trace JSONL, nên tạo trace bằng một lượt Trip trên repo nhom-44 (máy có `data/` và `.env`, mạng UIT):

```sh
python - <<'EOF'
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(".env")
from agents import trace
from trip import TurnInput, create_engine
engine = create_engine(Path("data"))
sid = engine.create("first", "nothing")["id"]
with trace.start(Path("data/traces"), "demo-uc01", stage="trip", operation="turn"):
    engine.turn(sid, TurnInput(kind="text", text="Ngày 28/11 mình đi Đà Lạt 3 ngày 2 đêm với 2 bạn, "
                "khoảng 3 triệu một người, thích cà phê view đồi, tụi mình thuê xe máy."), lambda e, d: None)
EOF
python -m agents.trace --trip-id demo-uc01
```

`SSL_CERT_FILE` trong `.env` là đường dẫn tương đối tính từ gốc repo: chạy lệnh ở gốc repo.

**Trace thật, tạo 12/11/2026 22:11** (một lượt Trip, câu ở trên; dòng `tool_call` rút gọn tham số):

```json
{"run_id": "0a324255dad24d00", "trip_id": "demo-uc01", "seq": 1, "kind": "run_start", "stage": "trip", "operation": "turn"}
{"run_id": "0a324255dad24d00", "trip_id": "demo-uc01", "seq": 2, "kind": "skill", "stage": "trip", "name": "interpret-trip-requirements"}
{"run_id": "0a324255dad24d00", "trip_id": "demo-uc01", "seq": 3, "kind": "model_call", "node": "agent", "step": 1, "ms": 3691, "ttft_ms": 2264, "tokens_in": 22311, "tokens_out": 228, "tokens_cached": 18944, "tool_calls": ["record_fact"], "failed": false}
{"run_id": "0a324255dad24d00", "trip_id": "demo-uc01", "seq": 4, "kind": "tool_call", "node": "execute", "name": "record_fact", "args": {"facts": [{"field": "intent", "op": "set", "value": "plan", "quote": "[omitted]", "how": "said"}, {"field": "companions", "op": "add", "…": "…"}]}, "…": "…"}
{"run_id": "0a324255dad24d00", "trip_id": "demo-uc01", "seq": 5, "kind": "run_end", "status": "ok", "total_ms": 7727, "tokens_in": 22311, "tokens_out": 228, "cost_estimate": 0.0}
```

Điểm nên nêu khi trình bày: skill được ghi trước vòng lặp; một lượt model gọi `record_fact` để ghi nhiều trường cùng lúc; `quote` (câu gốc của người dùng) bị thay bằng `[omitted]` trước khi ghi đĩa; 85% token vào lấy từ cache prompt (18.944 / 22.311), nhờ thứ tự prompt ở §4.3; `cost_estimate = 0` vì model tự host của UIT có đơn giá 0 trong `ai/config/agents/trace.yaml`.
