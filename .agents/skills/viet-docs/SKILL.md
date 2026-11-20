---
name: viet-docs
description: Viết hoặc sửa tài liệu tiếng Việt của TripGuardian (README, docs/*.md, handoff, báo cáo) cho người đọc thật, không "giọng AI". Dùng khi được nhờ viết / viết lại / rút gọn README, tài liệu kiến trúc, hướng dẫn cài đặt, báo cáo, hoặc khi chủ dự án chê tài liệu dày chữ, khó đọc, văn phong máy.
---

# Viết tài liệu tiếng Việt

Rule thường trực vẫn ở `RULE.md` §0–§0.1 (tiếng Việt, mỗi nội dung một chỗ, chỉ mô tả code hiện tại). Skill này lo **cách viết**.

## Trước khi viết: ai đọc, đọc để làm gì

Viết một câu trả lời cho mình trước: "Người đọc là ai, đọc xong phải làm được gì?"

| Tài liệu | Người đọc | Đọc xong phải làm được |
|---|---|---|
| `README.md` | người mới, giảng viên, nhà tuyển dụng | biết dự án làm gì, xem demo, chạy thử trong 15 phút, biết liên hệ ai |
| `docs/SETUP.md` | người cài máy mới | cài đủ từng phần, biết phần nào tùy chọn |
| `docs/ARCHITECTURE.md` | người sắp sửa code | biết module nào làm gì, dữ liệu chảy ra sao |
| tài liệu giai đoạn | người sửa đúng giai đoạn đó | tìm được contract, thuật toán, file code, test |

Nội dung không giúp người đọc đó làm được việc đó thì bỏ hoặc trỏ sang tài liệu khác.

## README là mặt tiền

Thứ tự: ảnh/demo → một câu dự án làm gì → giá trị chính (3–4 gạch) → sơ đồ → chạy nhanh → tái lập kết quả → tài liệu → tác giả.
- Vừa khoảng một màn hình rưỡi trước phần "Chạy nhanh".
- Chi tiết cài đặt, biến môi trường, sự cố: sang `docs/SETUP.md`.
- Không đưa vào README: quy ước làm việc nhóm, ranh giới module, nhật ký tính năng (đã có ở `RULE.md`, `docs/`).
- Dự án du lịch phải có minh họa: ảnh giao diện, sơ đồ mermaid. Ảnh trong git không chứa nội dung crawl (ảnh Maps, review, tài khoản TikTok).

## Sơ đồ trước, chữ tối thiểu (chủ dự án 2026-11-20)

- Tài liệu kỹ thuật (architecture, giai đoạn, agent, ops) dựng quanh **sơ đồ mermaid**: luồng, thành phần, sequence một lượt. Sơ đồ là nội dung chính, không phải phụ họa.
- Chữ chỉ để nói thứ sơ đồ không nói được: vì sao, giới hạn, lệnh chạy. Chữ không tả lại sơ đồ.
- Câu nào bỏ đi mà người đọc vẫn làm được việc thì bỏ. Ưu tiên bảng ngắn hơn đoạn văn.
- Luôn giữ tài liệu ở dạng gọn nhất; mỗi lần sửa, xóa được chữ thì xóa.

## Câu chữ

- Câu ngắn, chủ ngữ rõ. Một đoạn ≤ 4 dòng.
- Động từ cụ thể: "chạy", "tải", "điền", "mở". Tránh "thực hiện việc", "tiến hành", "đảm bảo rằng".
- Số liệu có đơn vị và nguồn: "1.773 địa điểm (snapshot 2026-11-18)", không "rất nhiều địa điểm".
- Thuật ngữ kỹ thuật và identifier giữ nguyên, bọc backtick: `Trip State`, `unknown`, `./run.sh start`.
- Viết như người trong nhóm giải thích cho bạn cùng lớp, không như brochure.

### Dấu hiệu "giọng AI" cần sửa

| Kiểu | Ví dụ cần tránh | Viết lại |
|---|---|---|
| Mở bài sáo | "Trong bối cảnh du lịch ngày càng phát triển, …" | vào thẳng: "TripGuardian giúp chọn nơi trước khi xếp lịch." |
| Tính từ quảng cáo | "mạnh mẽ", "toàn diện", "tối ưu", "liền mạch", "vượt trội" | nói con số hoặc hành vi cụ thể |
| Ba ý cho đủ nhịp | "nhanh chóng, chính xác và hiệu quả" | giữ ý có bằng chứng |
| Câu dịch từ tiếng Anh | "Điều này cho phép người dùng có thể …" | "Người dùng …" |
| Lạm dụng in đậm, emoji, gạch đầu dòng | mỗi dòng một chữ đậm | chỉ đậm chỗ người đọc dễ sai |
| Kết luận tóm tắt lại | "Tóm lại, hệ thống …" | bỏ |
| Từ Hán Việt nặng | "tiến hành triển khai", "nhằm mục đích" | "chạy", "để" |

## Kiểm trước khi giao

1. Đọc lại như người mới: làm theo đúng từng lệnh trong phần chạy nhanh có được không? Lệnh nào chưa chạy thử thì ghi rõ.
2. Mọi đường dẫn, lệnh, cổng, tên file có thật trong repo (`ls`, `grep`).
3. Không câu nào mô tả hành vi cũ hoặc kế hoạch tương lai (`RULE.md` §0.1).
4. Đếm lại: có đoạn nào > 4 dòng, có bảng nào > 12 hàng không? Có thì tách hoặc chuyển sang tài liệu chi tiết.
5. Người viết (chủ dự án) đọc duyệt bản cuối. AI viết nháp, con người chịu trách nhiệm nội dung.
