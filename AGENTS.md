# Hướng dẫn cho agent

Hệ thống place intelligence + lập lịch trình cá nhân hóa.

**Bắt buộc tuân theo:** `RULE.md`. Rule thường trực chỉ nằm một chỗ ở đó; `CLAUDE.md` chỉ import file này.

**Mục lục tài liệu, cách thiết lập, cách chạy, cách test:** `README.md`. Không chép danh sách tài liệu vào đây.

## Vào việc từ đâu

| Việc | Đọc |
|---|---|
| Hiểu toàn hệ thống trước khi sửa | `docs/ARCHITECTURE.md` |
| Sửa một giai đoạn | tài liệu của chính giai đoạn đó (`docs/CORPUS.md`, `TRIP_UNDERSTANDING.md`, `PLACE_DECISION.md`, `PLANNING.md`) — mỗi file có §Ranh giới module / §CLI và API trỏ thẳng vào code |
| Biết code đã làm gì, đã sửa gì | `docs/log/DEV_LOG.md` (chỉ khi cần) |
| Đổi prompt, model, key | `docs/LLM_PROVIDER.md` |
| Sửa Web | `docs/Role_Web_Functional_Design.md` (§6 = màn nào ở file nào) |

## Bất biến không được phá

- Tài liệu viết **tiếng Việt**; code, comment, identifier, tên file viết **tiếng Anh** (`RULE.md` §0).
- Offline ghi Place Intelligence. Online chỉ đọc nó; online chỉ ghi lịch trình và user / session profile.
- Không bao giờ bịa địa điểm. Không có bằng chứng → `unknown`, không phải `false`. Hard constraint: có bằng chứng trượt thì loại; chưa rõ thì vẫn hiện, xếp sau, chỉ cảnh báo ở ô Đánh đổi của thẻ nơi và khi xếp lịch (chủ dự án 04/11/2026).
- Physical constraint không có đường code nào nới được. Hệ thống chỉ cảnh báo, quyết định cuối cùng luôn của người dùng: lịch có vi phạm vẫn hiện và chốt được (chủ dự án 08/11/2026).
- User Profile là prior, không phải fact hay constraint: bối cảnh chuyến đi hiện tại thắng, `unknown` ≠ không thích, đã đến ≠ đã thích.
- Module **chỉ** giao tiếp qua public API (`__init__.py`). Không deep import.
- Gọi model theo **vai trò** (ASR, Extractor, Judge, Agent); model cụ thể nằm trong config, key trong `.env`.
- Mỗi nguồn ngoài (TikTok, Google, …) có module và thư mục dữ liệu riêng; không gộp.

Lỗi lặp lại của agent được ghi làm bằng chứng ở `docs/log/AGENT_FAILURES.md` trước khi được nâng thành rule.
