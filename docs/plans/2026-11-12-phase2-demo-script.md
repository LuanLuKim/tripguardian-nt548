# Kịch bản video demo Phase 1–2 (bản gọn) — TripGuardian

> SE373 · Nhóm 44 · Đề tài 08 Tour Guide Agent · Đà Lạt. Lập 12/11/2026, thay bản dài `docs/submission/phase-1-2/VIDEO_SCRIPT.md` trên nhom-44.
> Thời lượng: **5–6 phút**. Một người vừa thao tác vừa nói, không cần diễn. Nhân vật và dữ liệu chuyến đi là hư cấu.

## Nguyên tắc

- Video chỉ chứng minh **yêu cầu tối thiểu** của Phase 1 và Phase 2 (bảng đối chiếu cuối file). Mỗi yêu cầu cần ít nhất một khoảnh khắc rõ ràng trên màn hình.
- Hai nửa: **web thật** (phần 1–5) và **phía sau** (phần 6, terminal trên repo nhom-44).
- Không khoe tính năng ngoài yêu cầu (3D, linh vật, cộng đồng). Lướt qua nếu nó nằm trên đường đi.
- Phần chưa xong thì không quay như đã xong. Phần "đạt một phần" nói đúng như vậy (bảng cuối).

## Chuẩn bị

| Việc | Ghi chú |
|---|---|
| Web | Dùng bản đang chạy trên server (prod) hoặc `./run.sh start` rồi mở `http://127.0.0.1:5173/`. Cần ở **mạng UIT** để model trả lời |
| Repo cho phần 6 | Checkout `main` nhom-44 (`885439d4` hoặc mới hơn), venv đã cài `pip install -e ".[dev]"`, có `data/` từ gói Drive và `.env` |
| Trình duyệt | Cửa sổ ẩn danh, zoom 100%, 1920×1080, tắt thông báo hệ thống |
| Terminal | Font ≥ 16 pt, nền tối. Mở sẵn 4 tab ở gốc repo nhom-44 (lệnh ở phần 6) |
| Chạy thử | Đi hết luồng 1 lần với đúng câu thoại. Chạy trước các lệnh phần 6 để biết thời gian; lệnh chậm thì quay kết quả có sẵn |
| Không lộ | `.env`, key, email thật, token. Không mở Admin có tên người dùng thật |

Quay bằng OBS 1080p 30 fps. Cắt bỏ đoạn chờ model trả lời (giữ 1–2 giây để người xem thấy hệ thống đang chạy).

## Kịch bản

### 0. Mở đầu (0:00–0:20)

**Hình:** landing TripGuardian.
**Lời:** "Nhóm 44, đề tài Tour Guide Agent cho Đà Lạt. TripGuardian giúp người đi tự túc chọn đúng nơi trước khi lên lịch, rồi kiểm tra lịch có đi được thật không. Video này demo các yêu cầu tối thiểu của Phase 1 và Phase 2."

### 1. Vào ứng dụng (0:20–0:35) · Phase 1: codebase ứng dụng

**Thao tác:** bấm `Bắt đầu` → `Dùng thử, không cần tài khoản` → đồng ý điều khoản → trang chủ.
**Lời:** "Đây là web thật đang chạy, có tài khoản, khách và lưu chuyến đi trên Postgres."

### 2. UC-01 — Hiểu chuyến đi (0:35–1:45) · agent loop, tool, skill, structured output

**Thao tác:**
1. Bấm tạo chuyến mới, gõ:
   > "Ngày 28/11 mình đi Đà Lạt 3 ngày 2 đêm với 2 đứa bạn, khoảng 3 triệu một người, thích cà phê view đồi và chụp ảnh, không thích chỗ quá đông, tụi mình thuê xe máy."
2. Chờ agent trả lời. Agent ghi nhận ngày, số người, ngân sách, sở thích, phương tiện và **chỉ hỏi phần còn thiếu** (ví dụ xuất phát từ đâu, đã có chỗ ở chưa).
3. Trả lời một câu bằng chip, một câu bằng `Chưa chắc`.
4. Mở **Tóm tắt chuyến đi**: chỉ vào phần giới hạn cứng (ngân sách, xe máy) và phần sở thích mềm ("không thích đông").

**Lời:** "Mình nói tự nhiên như nói với bạn. Agent tự tách ra hồ sơ chuyến đi có cấu trúc, chỉ hỏi những gì còn thiếu. 'Không thích đông' là sở thích, không phải điều kiện loại nơi."

### 3. Chọn nơi có bằng chứng (1:45–2:55) · RAG có trích dẫn nguồn, người dùng duyệt

**Thao tác:**
1. Shortlist hiện theo nhóm. Chỉ vào một thẻ: **Vì sao phù hợp**, **Đánh đổi**, **Độ tin cậy**.
2. Mở `Chi tiết` một quán cà phê: thông tin thực tế kèm **nguồn và ngày kiểm tra**; phần trải nghiệm có trích dẫn review / clip kèm cỡ mẫu.
3. Hỏi trợ lý: *"Quán này sáng cuối tuần có đông không, có chỗ để xe máy không?"*. Câu trả lời dẫn từ bằng chứng; phần không có dữ liệu thì nói **chưa có bằng chứng**, không đoán.
4. `Thêm vào chuyến` 5–6 nơi, `Bỏ` một nơi. Thanh "Đã chọn" cập nhật số nơi, thời gian, chi phí.

**Lời:** "Mỗi gợi ý có lý do và nguồn. Agent chỉ trả lời từ dữ liệu đã thu thập; không có bằng chứng thì nói là chưa rõ. Người dùng quyết định nơi nào vào chuyến, agent không chọn thay."

### 4. UC-02 — Lịch trình có kiểm tra ràng buộc (2:55–4:00) · validator bằng code, người duyệt trước khi chốt

**Thao tác:**
1. Bấm `Lập lịch`. Màn chờ nói đúng việc đang làm.
2. Lướt ngày 1–3: giờ đến, thời gian ở, thời gian di chuyển, chi phí ước tính, bản đồ tuyến. Chỉ nhãn **Vững / Khả thi / Mong manh** và một dự phòng "Nếu mưa…".
3. Đổi một điểm sang ngày khác → lịch được kiểm lại, cảnh báo hiện ngay tại điểm dừng nếu vướng giờ mở cửa → `Hoàn tác`.
4. Nếu lịch có cảnh báo (ví dụ vượt ngân sách, giờ mở cửa chưa xác nhận): chỉ vào cảnh báo, rồi bấm `Chốt kế hoạch này` → hệ thống hỏi lại → xác nhận.

**Lời:** "Validator là code, không phải LLM: kiểm giờ mở cửa, thời gian đi, ngân sách, thời tiết. Có vi phạm thì hệ thống cảnh báo rõ, còn quyết định cuối cùng là của người dùng: vượt ngân sách vẫn chốt được sau khi xác nhận."

### 5. Dừng rồi chạy tiếp (4:00–4:30) · lưu state

**Thao tác:** đóng hẳn tab đang ở Lịch trình → mở lại `/app` → `Chuyến của tôi` → mở chuyến vừa làm → về đúng bước, đúng các nơi đã chọn và đúng bản sửa cuối.
**Lời:** "Mỗi chuyến đi lưu trên Postgres kèm revision. Tắt ngang rồi mở lại vẫn còn nguyên."

### 6. Phía sau hệ thống (4:30–5:45) · Phase 1 + 2 trên repo

Terminal ở gốc repo nhom-44. Lệnh chạy lâu thì quay kết quả đã chạy trước.

| Thời điểm | Hình | Lời |
|---|---|---|
| 4:30 | `ai/src/agents/assistant/loop.py`, đoạn `StateGraph`: node `agent` → `execute` → `review` | "Agent là một đồ thị LangGraph: model chọn tool, node execute chạy tool qua schema Pydantic, node review gửi lại câu trả lời sai luật." |
| 4:45 | `ls skills/` rồi mở `skills/interpret-trip-requirements/SKILL.md` | "Ba skill có contract: hiểu yêu cầu chuyến đi, lập lịch, thuyết minh. Trip agent nạp skill từ thư mục này." |
| 4:55 | `python -m evals.run --uc uc01` (hoặc mở `evals/results/20261112T150821Z_uc01.json`) | "Bộ eval UC-01 có 12 case, chạy bằng một lệnh, kết quả ra JSON. Lần chạy hôm nay: 7/12 case đạt, đọc đúng ràng buộc cứng 94,6%. Năm case fail là lỗi thật của agent, đã thành issue để sửa." |
| 5:10 | `python -m planning evaluate --uc02` | "UC-02 có 6 case vàng cho validator: chạy ngày đóng cửa, mưa lớn, vượt ngân sách. Kết quả 6/6." |
| 5:20 | `python -m agents.trace --trip-id <id>` (file trace có sẵn, xem ghi chú dưới) | "Mỗi lượt agent ghi một file trace JSONL theo run_id: lượt gọi model, từng tool call kèm tham số, kết quả, thời gian, token." |
| 5:35 | kết quả `pytest` (dòng tổng) và tab Issues / Milestones của repo | "Gần 5.500 test tự động. Phần còn thiếu đã lên milestone Phase 3." |

**Trace để quay:** server prod hiện chưa chạy bản có trace JSONL. Tạo một trace thật trên máy có `data/` và `.env` bằng lệnh ở `docs/plans/2026-11-12-phase2-report-outline.md` §Phụ lục C, rồi `python -m agents.trace --trip-id demo-uc01`. Lần chạy 12/11 ra 5 dòng: `run_start` → `skill` → `model_call` (22.311 token vào, 18.944 từ cache) → `tool_call record_fact` → `run_end` (7,7 s).

**Lưu ý khi quay phần 2:** nếu nhóm đi có trẻ em, bấm "Không có" ở mục lưu ý sức khỏe sẽ bị hỏi lại (lỗi đã ghi thành issue). Câu thoại mẫu ở phần 2 là nhóm bạn, không có trẻ em, nên không gặp lỗi này. Đừng đổi câu thoại sang nhóm có trẻ em.

### 7. Kết (5:45–6:00)

**Lời:** "Phase 1 và 2 đã xong phần tối thiểu: agent loop có tool, skill, log; ba use case chạy được; RAG có nguồn; lưu và tiếp tục chuyến đi; workflow LangGraph có bước người duyệt. Phase 3: kho tri thức có giấy phép cho thuyết minh, MCP, eval đầy đủ."

## Đối chiếu yêu cầu ↔ phần trong video

| Yêu cầu | Phase | Phần | Ghi chú khi nói |
|---|---|---|---|
| Repo, CI, codebase ứng dụng và agent | 1 | 1, 6 | CI có workflow nhưng GitHub Actions không khởi động (billing tài khoản); test chạy tay |
| Agent loop ≥ 2 tool, 1 skill, log từng bước | 1 | 2, 6 | 84 tool, 3 skill, trace JSONL |
| 1 use case từ ứng dụng tới agent, ≥ 10 eval case | 1 | 2, 6 | UC-01, 12 case, 7/12 đạt |
| RAG có trích dẫn nguồn | 2 | 3 | Bằng chứng địa điểm có nguồn + ngày. Kho tri thức thuyết minh (UC-03) mới có truy xuất + eval, chưa nối vào agent: **không quay như đã xong** |
| Lưu state, dừng rồi chạy tiếp, nén context | 2 | 5 | Nén context = cửa sổ lịch sử + Trip State; nói một câu ở phần 6 nếu còn thời gian |
| Workflow LangGraph có bước người duyệt | 2 | 3, 4, 6 | Người duyệt ở tầng ứng dụng (chọn nơi, chốt lịch có cảnh báo). Chưa dùng `interrupt()` của LangGraph |
| ≥ 3 use case chạy được | 2 | 2, 3, 4 | UC-01 · Chọn nơi có bằng chứng · UC-02 |

## Sau khi quay

- [ ] Không lộ `.env`, key, email, token, tọa độ nhà.
- [ ] Mỗi dòng của bảng đối chiếu có một khoảnh khắc rõ trên màn hình.
- [ ] Chữ đọc được ở 720p.
- [ ] Ghi link video vào báo cáo Word (mục 1).
