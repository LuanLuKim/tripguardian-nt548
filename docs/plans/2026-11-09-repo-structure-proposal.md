# Đề xuất: cấu trúc repo và `src/` sau đợt dọn 2026-11-09

Spec làm việc (`RULE.md` §0.1), chờ chủ dự án chọn. Đợt dọn ngày 09/11 đã làm phần ít rủi ro (bảng ở §1). Các mục §2–§5 đụng code đang chạy prod hoặc cần cả nhóm đồng ý nên chưa làm. Mục nào được duyệt và làm xong thì ghi vào tài liệu chính thức rồi xóa mục đó; hết mục thì xóa file.

## 1. Đã làm ngày 09/11

| Việc | Kết quả |
|---|---|
| `docs/plans/` | bỏ 16 trong 24 plan đã xong hoặc đã cũ (đọc lại được bằng `git show 7c4da01:docs/plans/<file>`); phần bench gộp vào `docs/TRIP_UNDERSTANDING.md` §16, hướng dẫn có linh vật vào `docs/Role_Web_Functional_Design.md` §2.14 |
| Báo cáo có ngày | `docs/NORMALIZED_CORPUS_RECHECK.md`, `docs/PLANNING_PERFORMANCE.md` → `docs/reports/` |
| Vận hành | phần production của `README.md` → `docs/OPERATIONS.md`; cron `@reboot` và `pulse` đã cài |
| Tài sản thiết kế ở gốc | `ui_mock_for_design/` → `docs/design/mock/`, `mascot/` → `docs/design/mascot/` |
| Tài liệu lạc chỗ | `src/corpus/TAG_EXPANSION_NOTES.md`, `src/planning/tripguardian_planning_improvement.md` → `docs/plans/`; `tools/surveys/` → `submission/surveys/`; `.opencode/plans/` bỏ |
| Rác trong git | `frontend_images/` thôi theo dõi (vẫn trên đĩa, đã gitignore); `web/.deploy-build-1030/` (file khóa NFS) bỏ; 4 script nối chuỗi crawl dùng một lần (`after_maps`, `after_rerun`, `after_photos`, `tiktok_now`) bỏ |
| Ghi lại kiến trúc | đồ thị phụ thuộc `docs/ARCHITECTURE.md` §3 tính lại từ import thật; thêm bảng package dùng chung và danh sách import sâu |
| Rule | `RULE.md` §0.3 bố cục repo, §8 production |

## 2. Gỡ import sâu và chặn bằng test (nên làm trước)

`docs/ARCHITECTURE.md` §3 liệt kê 12 chỗ import vượt public API. Cách sửa từng chỗ: thêm tên cần dùng vào `__init__.py` của package đích, đổi import ở nơi gọi, không đổi hành vi.

| Nơi gọi | Import sâu | Đưa ra public ở |
|---|---|---|
| `harness/dispatch.py` | `planning.settings` | `planning/__init__.py` |
| `bench/latency.py` | `decision.settings`, `trip.domain.resolve`, `trip.infrastructure.settings` | `decision`, `trip` |
| `trip/agent/{tools,loop,rules}.py` | `agents.assistant.lc`, `agents.assistant.loop` | `agents/assistant/__init__.py` |
| `bench/assistant.py` | `agents.assistant.guard` | `agents/assistant/__init__.py` |
| `agents/input_guard.py`, `trip/domain/perceive.py`, `trip/infrastructure/{perceive,web}.py` | `corpus.crawl.web` | `corpus/crawl/__init__.py` (hiện chỉ công khai 3 tên cho `live`) |

Sau đó thêm một test chung `tests/test_boundaries.py`: duyệt AST mọi file trong `src/`, import tới package khác chỉ được dừng ở `<pkg>` (hoặc `corpus.<sub>`, `agents.assistant`). Năm test ranh giới riêng hiện có (`tests/{booking,live,planning,retrieval,harness}/…bound…`) giữ nguyên.

Rủi ro: thấp; chỉ đổi đường import. Cần deploy lại để prod nhận (prod chạy `.prod_src/`).

## 3. Gom package nhỏ ở `src/` (tùy chọn)

Hiện có 18 package phẳng. Tên package là contract import nên mọi lần gom đều đổi import ở nơi gọi và ở test.

| Phương án | Đổi gì | Lợi | Giá |
|---|---|---|---|
| **A. Giữ phẳng, nhóm trong tài liệu** (đề xuất) | không đổi code; nhóm theo lớp ở `docs/ARCHITECTURE.md` §3 (đã làm) | không rủi ro | gốc `src/` vẫn 18 thư mục |
| B. Gộp package rất nhỏ | `mailer` (122 dòng, 3 nơi dùng) và `social` (198 dòng, 2 nơi) vào `accounts`; `journey` (266 dòng, 4 nơi) vào `booking` | 18 → 15 package; các phần cùng tài liệu (`ACCOUNTS.md`, `BOOKING.md`) về chung một chỗ | ~15 file đổi import; `accounts` thêm phụ thuộc SMTP |
| C. Namespace `src/tripguardian/<pkg>` | mọi import thành `tripguardian.<pkg>` | đúng chuẩn đóng gói | ~950 file đổi, `run.sh` / `.prod_src` / `PYTHONPATH` / test / script đổi theo; không đáng ở giai đoạn này |

`bench` chỉ là công cụ đo (không package nào import nó) nhưng giữ trong `src/` vì cần `python -m bench` và import các module thật.

## 4. Chia `scripts/` thành thư mục con (tùy chọn)

Nhóm đã ghi ở `scripts/README.md`: `ops/`, `models/`, `corpus/`, `eval/`. Chưa chuyển vì:
- mỗi script tự tính gốc repo theo vị trí của nó (`$(dirname "$0")/..`, `Path(__file__).parents[1]`): phải sửa từng file;
- crontab gọi 4 script theo đường dẫn tuyệt đối, `run.sh` gọi `models_ctl.sh` và `prewarm_transit.py`, 4 test nạp script theo đường dẫn (`tests/test_model_gateway.py`, `tests/test_clef_server.py`, `tests/normalization/test_projection.py`, `tests/bench/test_prod_journey_cases.py`).

Làm trong một commit: chuyển, sửa gốc repo, sửa `run.sh`, test, tài liệu, rồi crontab; chạy tay từng script ops một lần (`disk_guard.sh`, `keepalive.py`) trước khi rời máy.

## 5. Cần chủ dự án quyết

| Việc | Hiện trạng | Đề xuất |
|---|---|---|
| Mock thiết kế cũ | `docs/design/proposal-2026-10/`, `docs/design/redesign-2026-10/` (34 file) | bỏ nếu không còn dùng để so sánh; bản đang theo là `desktop/v3-rose-photo` và `mock/` |
| Lịch sử git nặng | `.git` 1,9 GB (ảnh, video từng commit) | `git gc` an toàn; viết lại lịch sử (`git filter-repo`) giảm mạnh hơn nhưng cả nhóm phải clone lại |
| Ghi chú nghiên cứu nháp | `submission/research/test.log`, `test_task.md`, `sol/` (smoke test và câu hỏi thử của agent) | bỏ, hoặc giữ nếu là nguồn của báo cáo |
| Plan còn mở | `docs/plans/` còn: chỉ mục ngữ nghĩa lớp A, nâng cấp 2026-10-26, đề xuất RAG, tour đợt 2, 3D (3 file bàn giao), ghi chú tag, đề xuất Planning | rà từng file: phần đã có trong code thì gộp và xóa; ba file 3D gộp thành một |
