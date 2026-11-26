# Bàn giao 25/11: LangSmith cho AIOps (T4)

Mục tiêu: trace của agent harness thành một nguồn bằng chứng của tóm tắt sự cố (#38). Trace giúp phân biệt "model sau `model-gateway` lỗi hoặc chậm" với "app lỗi". Chủ dự án chốt hạn cho đồ án là 04/12, muốn xong mọi phần trong tuần để còn làm báo cáo và slide trước 09/12.

Phạm vi:
- LangSmith là **nguồn quan sát cho AIOps**, không phải LLMOps.
- Không sửa code sản phẩm (`src/`).
- #16 (eval gate) thuộc DontMadWhenBad, không làm ở đây.

## Trạng thái

- Nhánh `nt548/t4-langsmith`, **chưa push, chưa có PR**.
- Nhánh dựng trên `origin/nt548/t4-incident-llm` (PR #60, chưa merge, cùng sửa `incident.py`), rồi merge `origin/main` vào (commit `15803be`), vì nhánh của #60 chưa có `ops/nt548/compose/`.
- Khi #60 merge, diff của PR mới tự gọn lại.

| Việc | Trạng thái |
|---|---|
| `incident.py`: bằng chứng `trace` (trước / sau alarm: số lượt, tỉ lệ lượt lỗi, p95 thời gian lượt, trung vị lần gọi model) và `trace_error` (run lỗi gom theo loại, tên, dòng đầu của lỗi) | Đã commit (`764ed69`) |
| Luật: model lỗi → giả thuyết đầu, độ tin `high` khi không có deploy; tool lỗi; model chậm ≥ 2 lần. Lệnh gợi ý xem `/metrics` gateway, không trùng | Đã commit |
| Demo mới `llm_errors` (kịch bản #39: LLM giả lỗi 30 %). Demo `llm_slow` có trace | Đã commit |
| `watch --traces-project nt548-{color}`: đọc LangSmith khi có `LANGSMITH_API_KEY`; màu lấy từ tên alarm | Đã commit |
| Gom lỗi cắt ở `Traceback (most recent call last)`, vì LangSmith ghi exception và traceback liền nhau, không xuống dòng | Đã commit |
| `ops/nt548/compose/app.yml`: biến `LANGSMITH_*` cho harness, mặc định tắt, ẩn input / output, project `nt548-<màu>` | Đã commit |
| Test: thêm 6 test trong `tests/nt548/test_incident.py` (21/21 qua trên Windows) | Đã commit |
| `docs/nt548/04-aiops.md`: mục "Trace của agent (LangSmith)", nút trace trong sơ đồ, demo `llm_errors` | Đã commit |
| `.github/workflows/nt548-incident.yml`: `llm_errors` trong `case`; job `watch` cài `langsmith`, nhận secret `LANGSMITH_API_KEY` | Đã commit |
| Push + PR | **Chưa làm** |

Lỗi `fcntl` của `test_sample_data` / `test_data_release` trên Windows đã có sẵn trên `main` (đã kiểm 25/11), không do nhánh này. CI Linux là thước đo.

## Đã kiểm trên máy (25/11)

Kiểm bằng một endpoint LangSmith giả (server HTTP ghi lại request), `ChatOpenAI` + LangGraph gọi `llm_fake` với `FAKE_ERROR_RATE=1`, bật `LANGSMITH_TRACING` và `LANGSMITH_HIDE_INPUTS/OUTPUTS`:
- Trace được gửi lên `/runs/multipart`. Có các run `LangGraph`, `ChatOpenAI` (`run_type` `llm`), `search_places`.
- `inputs` / `outputs` là `{}`. Chuỗi người dùng gõ không xuất hiện trong dữ liệu gửi đi.
- `error` có ghi, dạng `OpenAIAPIError('Error code: 500 - injected failure (FAKE_ERROR_RATE)')Traceback ...`.
- Chưa thử với LangSmith thật: chưa có API key.

Script kiểm nằm ở scratchpad (sẽ mất), dựng lại được trong khoảng 5 phút:
- `capture.py`: HTTP server trả 200, ghi body vào file;
- `probe.py`: `create_react_agent` gọi `llm_fake` trên cổng 18000, `LANGSMITH_ENDPOINT` trỏ vào server ghi.

## Bước tiếp theo

1. Lượt chạy cuối ngày 25/11: `test_incident`, `test_detect`, `test_llm_fake`, `test_harness_stub` qua 46/46. YAML của workflow và `app.yml` hợp lệ.
2. Push (cách push xem memory `nt548-github-workflow`), mở PR vào `main`:
   - ghi rõ PR xếp sau #60;
   - chủ dự án merge;
   - chạy tay workflow `nt548-incident` với `case=llm_errors` để có job summary đưa vào slide.
3. Việc của chủ dự án:
   - tạo tài khoản LangSmith, lấy API key;
   - để key vào GitHub Secret `LANGSMITH_API_KEY`;
   - đặt `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` vào môi trường compose trên máy app. Phần này cần user_data của ASG (#25, T8, chưa có).
4. Khi có key, thử một lần với LangSmith thật: chạy harness thật trên máy (WSL, xem memory `nt548-local-env`) với `FAKE_V1_ERROR_RATE=0.3`, rồi `incident.py summarize --traces` từ `langsmith_runs`. Chụp màn hình trace để làm slide.

## Tình trạng thành viên (kiểm GitHub 25/11)

- DontMadWhenBad chưa có commit, PR, comment hay nhánh nào cho #37, #39, #16, #18, #2 (phần Nginx).
- T8 AWS (#22, #24–#27) chưa ai làm, ngoài network module #23.
- Không có ALB / ASG thì không có alarm thật, `watch` và trace thật trên lab không chạy được. Chủ dự án đã được báo.
