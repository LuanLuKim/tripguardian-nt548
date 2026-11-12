# Issue cần tạo trên nhom-44 từ lần chạy eval UC-01 (12/11/2026)

Chưa tạo được vì quyền ghi GitHub bị chặn trong phiên. Mỗi mục dưới đây là một issue: label `bug`, `area:agent`; milestone `M1 · P3.1 Dữ liệu hợp lệ, RAG, UC-01/02 (13–19/11)` (số 6). Mục cuối là bình luận cho #35.

Bối cảnh chung (đặt đầu mỗi issue): phát hiện khi chạy `python -m evals.run --uc uc01` ngày 12/11/2026 trên `885439d4`, với bộ case đã chỉnh theo cổng trước lịch (nhánh `eval/uc01-gate-rules`).

---

## 1. [Bug][UC-01] Nhóm có trẻ em: bấm "Không có" ở mục lưu ý (care) tại cổng trước lịch vẫn không qua cổng

**Hiện tượng.** Người dùng nói có trẻ em ("2 người lớn và 1 bé 5 tuổi"). Ở cổng trước lịch, bấm **Không có** cho mục *Có điều gì về sức khỏe, đi lại hay ăn uống cần lưu ý?*: `care = none` được ghi, nhưng `readiness_missing` vẫn trả `care`, cổng hỏi lại đúng câu đó. Người dùng không qua được cổng, trừ khi chọn một lựa chọn khác như "Tránh dốc, bậc thang".

**Nguyên nhân (đọc code).** `ai/src/trip/domain/required.py`: lựa chọn `none` của tab `care` chỉ ghi `signal_handled` cho tín hiệu có `source == "inferred"` hoặc `from_companion`. Tín hiệu `kids` do người dùng tự nói có `source == "user"` nên vẫn `handled = False`. `readiness.missing` coi `care` là chưa xong khi còn `pending_signals(state)`.

**Tái hiện.**

```python
eng.turn(sid, TurnInput(kind="text", text="Nhà mình 2 người lớn và 1 bé 5 tuổi đi Đà Lạt 3 ngày từ 20/12/2026, tổng ngân sách 10 triệu."), emit)
eng.turn(sid, TurnInput(kind="deck", answers={"care": ["none"]}, at="gate"), emit)
readiness_missing(eng.store.get(sid).state)  # [('care', ...)]: vẫn thiếu
```

**Kỳ vọng.** "Không có" là câu trả lời cho mục care: đánh dấu đã xử lý cả tín hiệu `kids` / `elderly` do người dùng nói (vẫn giữ `companions = kids` và tag mềm hợp trẻ em), rồi qua cổng.

**Case eval:** `uc01-001` (full), `uc01-004` (english).

## 2. [Bug][UC-01] Nói "không ai cần lưu ý gì về sức khỏe hay ăn uống" bằng lời không ghi được care

**Hiện tượng.** Người dùng gõ: *"Mình đi Đà Lạt 2 ngày từ 20/12/2026 với 2 người bạn, ngân sách 6 triệu. Không ai cần lưu ý gì về sức khỏe hay ăn uống."* Agent hiểu đúng, có lần còn nói *"mình chưa ghi được thông tin đó"*, nhưng `care` vẫn trống, cổng vẫn hỏi lại. Chỉ bấm nút "Không có" trên thẻ mới ghi được.

**Kỳ vọng.** Câu phủ định rõ ràng ghi `care = none` (nguồn `user`, quote là câu gốc), như khi bấm nút. Tool `record_fact` / prepass cần nhận được trường này.

**Case eval:** `uc01-012`.

## 3. [Bug][UC-01] "đi với 2 người bạn" bị ghi people = 2 thay vì 3

**Hiện tượng.** *"Mình đi Đà Lạt … với 2 người bạn …"* → `people = 2`. Người nói cộng 2 người bạn là 3 người.

**Kỳ vọng.** `people = 3`, `companions = friends`. Nếu chưa chắc thì hỏi lại, không ghi số sai với độ tin cậy cao. Đây là ràng buộc cứng (chỉ số "trích đúng ràng buộc cứng ≥ 90%" của #35).

**Case eval:** `uc01-012`.

## 4. [Bug][UC-01] Ngày tiếng Anh "starting December 20, 2026" không được ghi start_date

**Hiện tượng.** *"I want to visit Da Lat for 3 days starting December 20, 2026. There will be 2 adults and 1 child. Our total budget is 10 million VND."* → `days = 3`, `people = 3`, `budget_vnd = 10000000` đúng, nhưng `start_date = None`, nhóm `trip` vẫn thiếu, agent hỏi phương tiện thay vì ghi ngày.

**Kỳ vọng.** `start_date = 2026-12-20` (đề yêu cầu song ngữ vi / en). Kiểm `resolve_relative_date` / prepass với định dạng tháng chữ tiếng Anh.

**Case eval:** `uc01-004`.

---

## Bình luận cho #35

Hai mục của issue này đang fail trên bộ chấm:

- **Mâu thuẫn số ngày** (`uc01-003`: "3 ngày từ 20/12/2026 đến 24/12/2026"): agent **có nói ra** chỗ chưa khớp ("Khoảng 20/12–24/12 chưa khớp với 3 ngày; bạn muốn chốt theo thời lượng hay ngày về?") nhưng không ghi vào `meta.conflicts` (Trip chỉ ghi mâu thuẫn cho `pace`, `crowd_tolerance`), nên route vẫn là `plan`.
- **Điểm đến ngoài dữ liệu** (`uc01-005`, Bangkok): agent trả lời đúng ("Mình chỉ hỗ trợ chuyến đi Đà Lạt…") nhưng Trip State không có nhánh `unsupported`, nên bộ chấm chỉ thấy `ask_user`.

Kết quả lần chạy: 7/12 case đạt, trích đúng ràng buộc cứng 94,6%. Các lỗi khác tách thành issue riêng (điền số sau khi tạo).
