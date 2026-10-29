# Nhật ký lỗi của agent

Bằng chứng về các kiểu lỗi lặp lại của coding agent, để quyết định cái nào đáng thành rule. Không phải file hướng dẫn: một lỗi không tự động thành rule.

**Nhóm lỗi:** `CONTEXT` (đọc sai / thiếu ngữ cảnh) · `SCOPE` (sửa thứ không liên quan) · `REASONING` (vá triệu chứng) · `ARCHITECTURE` (phá ranh giới module) · `CONTRACT` (hỏng schema / API public) · `IMPLEMENTATION` · `OVERENGINEERING` · `TESTING` · `PERFORMANCE` · `RELIABILITY` · `SECURITY` · `STOP` (sửa tiếp sau khi đã xong) · `OTHER`.

**Nâng thành rule** khi thỏa ít nhất một điều: cùng kiểu lỗi xảy ra nhiều lần · một lần cũng đủ gây rủi ro nặng về tính đúng, bảo mật, mất dữ liệu · vi phạm một bất biến nền tảng · một rule ngắn ngăn được cả nhóm lỗi mà không gây tác dụng phụ. Khi nâng: viết rule chung nhỏ nhất, không mã hóa sự cố cụ thể, ghi ID lỗi gốc ở đây, giữ mục này làm bằng chứng.

**Mẫu một mục:**

```markdown
## F00N — <tên ngắn>

**Ngày:** YYYY-MM-DD · **Nhóm:** `CATEGORY` · **Task:** agent được yêu cầu làm gì
**Kỳ vọng:** kết quả đúng nhỏ nhất.
**Thực tế:** agent đã làm gì (không suy đoán).
**Bằng chứng:** file, diff, lệnh / test, lỗi.
**Hậu quả:** hành vi sai · diff thừa · coupling · tốn token · lỗi ẩn · …
**Nguyên nhân gốc:** thiếu ngữ cảnh | suy luận sai | task mơ hồ | thiếu rule | bỏ qua rule có sẵn |
giả định sai về kiến trúc | kiểm chứng không đủ | `UNKNOWN`
**Lẽ ra nên:** cụ thể, tối thiểu.
**Rule:** `NONE | WATCH | ADD | MODIFY | REMOVE` + lý do
**Tái diễn:** số lần · lỗi liên quan · **Trạng thái:** `OPEN | UNDER_OBSERVATION | RESOLVED | PROMOTED_TO_RULE`
```

---

## Các mục

## F001 — Dò lỗi trên probe tự dựng thay vì đường đã chạy được

**Ngày:** 2026-10-28 · **Nhóm:** `CONTEXT` · **Task:** spec §3 việc 1 "Playwright treo với site lớn"
**Kỳ vọng:** chạy lại đúng đường crawl đã chạy tốt (`corpus.crawl.open_sessions` với env của `logs/tiktok_poi_loop.sh`), xem có treo không; chỉ khi đường thật hỏng mới dựng probe để khoanh lỗi.
**Thực tế:** agent viết `logs/pw_probe.py` gọi Playwright trần (không qua `browser.py`, không env của repo), chạy 6 biến thể × 4 site, đợi ~25 phút. Mọi biến thể treo; agent dò tiếp D-Bus, QUIC, mạng.
**Bằng chứng:** `logs/pw_probe_2026-10-28_nodbus.out` (child timeout 356 s mọi biến thể), trong khi `logs/tiktok_poi_1027.log` ngày 27/10: 709 nơi, 0 timeout.
**Hậu quả:** tốn thời gian và token; kết luận "crawl hỏng" trong khi crawl thật vẫn chạy; 26 tiến trình Chrome mồ côi.
**Nguyên nhân gốc:** thiếu ngữ cảnh — không xem log của lần crawl thành công gần nhất trước khi dò.
**Lẽ ra nên:** đọc log crawl gần nhất và script đã chạy nó, rồi chạy `logs/crawl_path_check.py` (đi qua `corpus.crawl`, cùng env).
**Rule:** `ADD` — `RULE.md` §7: kiểm đường đã chạy được trước khi kết luận hỏng; lỗi rẻ để tránh, tốn nhiều khi mắc.
**Tái diễn:** 1 · **Trạng thái:** `PROMOTED_TO_RULE`
