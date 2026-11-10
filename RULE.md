# RULE.md

## 0. Ngôn ngữ
- Tài liệu (docs, spec, plan, README, dev log) viết tiếng Việt, kể cả khi người dùng viết tiếng Anh.
- Code, comment, identifier, tên file, tên schema, commit message viết tiếng Anh.
- Trong tài liệu, giữ nguyên thuật ngữ kỹ thuật và identifier (`POI`, `VERIFIED`, `Fact`, …) như trong code.
- Viết tối giản: ngắn, chính xác, đúng chức năng; không lặp nội dung đã có ở tài liệu khác, chỉ trỏ tới.

## 0.1 Tài liệu chính thức
- Tài liệu chính thức là các file trong `docs/` và thư mục con của nó (ví dụ `docs/log/`), được liệt kê trong `README.md`. File không có trong danh sách đó (ví dụ spec/plan làm việc) không phải tài liệu chính thức.
- Mỗi tài liệu giữ **một** nội dung chuyên biệt để không phải đọc tài liệu dài; mỗi nội dung chỉ nằm một nơi. Nơi khác cần thì dẫn sang (`docs/X.md` §N), không chép lại.
- Spec/plan làm việc là tạm thời và chỉ nằm ở `docs/plans/` (không đặt trong `src/`, `.opencode/`, `logs/` hay thư mục công cụ). Khi đã được duyệt và thực hiện, gộp nội dung còn giá trị vào tài liệu chính thức rồi xóa spec/plan. Không giữ thư mục spec/plan lưu trữ. Code hay test cần nhắc tới plan đã xóa thì trỏ vào lịch sử git (`git <commit>:docs/plans/<file>`), không trỏ vào file không còn.
- Không tạo bản dịch song song; thay đổi được sửa thẳng vào tài liệu chính thức.
- Tài liệu chính thức mô tả **đúng code hiện tại**, không nhắc lại hành vi/cấu trúc trước đây, không viết "trước đây làm X, giờ đổi thành Y", không viết theo kiểu plan ("phase sau sẽ thêm Y"). Khi code đổi, sửa thẳng đoạn mô tả cũ, không thêm ghi chú lịch sử.
- Ngoại lệ: `docs/log/DEV_LOG.md` (giữ **Hiện tại** + **Trước đó** theo đúng khuôn mẫu của chính nó) và `docs/log/AGENT_FAILURES.md` (nhật ký bằng chứng lỗi) là log theo thiết kế, không phải tài liệu mô tả hiện trạng — không áp dụng quy tắc "chỉ giữ hiện tại" ở trên cho hai file này. Báo cáo đo trong `docs/reports/` cũng vậy: đúng tại ngày ghi trong báo cáo, không sửa theo code; số đo hiện hành thì ghi vào tài liệu của module.

## 0.3 Bố cục repo
- Mỗi loại file một chỗ (bảng ở `README.md` §Cấu trúc thư mục): code `src/<package>/`, test `tests/<package>/`, ngưỡng `config/`, script và client thử `scripts/` (nhóm ở `scripts/README.md`) hoặc `web/scripts/`, tài liệu `docs/`, ảnh / mock thiết kế `docs/design/`, hồ sơ dự thi `submission/`.
- Không đặt tài liệu `.md` trong `src/` (trừ `SKILL.md` mà code nạp lúc chạy).
- Không thêm thư mục mới ở gốc repo khi một thư mục có sẵn đã đúng loại.
- Không giữ bản sao lưu trong repo (`.env.bak*`, `*.bak*`, `.prod_src.bak*`, file ghi hình): chuyển sang `archive-<ngày>/` trên NAS (`docs/OPERATIONS.md` §3).
- Thứ không phải code (venv, cache, trọng số model) nằm ngoài repo; trên gpu156 là `tripguardian-store/`, repo chỉ giữ symlink.
- Symlink `.venv`, `.venv-vllm`, `.cache` dùng chung cho mọi phiên và prod: không xóa, không trỏ sang chỗ khác (kể cả `~/.cache`), không thay bằng thư mục thật. Thiếu thì tạo lại đúng đích `tripguardian-store/<venv|venv-vllm|cache>` (`docs/OPERATIONS.md` §2). Cần cache riêng cho một lệnh thì đặt biến môi trường (`PLAYWRIGHT_BROWSERS_PATH`, `HF_HOME`, …) cho lệnh đó, không đụng symlink. Browser của Playwright ở `tripguardian-store/cache/ms-playwright`.

## 0.2 Thiết kế giao diện
- Không dùng skill `baoyu-design` cho thiết kế của dự án này. Khi cần skill thiết kế UI, chỉ dùng `ui-ux-pro-max`.
- Khi chỉnh UI, bám mẫu người dùng chỉ định; chỉ đổi phần được yêu cầu.
- Sau mỗi lần chỉnh UI, lưu ảnh chụp giao diện vào `frontend_images/` ở gốc dự án và gửi đường dẫn để người dùng xem lại trước khi lên production. Không chỉ lưu ảnh trong `/tmp`.

## 1. Nguồn sự thật
- Code + test mô tả hành vi runtime.
- Schema/interface public định nghĩa contract giữa các module.
- Tài liệu phải khớp với code đã ship.

## 2. Ranh giới
- Module chỉ giao tiếp qua interface public có kiểu.
- Không import phần nội bộ của module khác.
- I/O, LLM, network chỉ nằm ở biên module.
- Mỗi nguồn dữ liệu ngoài (TikTok, Google, …) có module/thư mục con riêng cả trong code lẫn trong thư mục dữ liệu; không gộp nhiều nguồn vào một file hay một thư mục.

## 3. Contract
- Input/output public có kiểu.
- Validate dữ liệu không tin cậy (bên ngoài/LLM/người dùng) tại biên.
- Không bịa giá trị còn thiếu.

## 4. Thay đổi tối thiểu
- Thay đổi nhỏ nhất đủ để giải quyết trọn vẹn yêu cầu.
- Không refactor, đổi tên, di chuyển, hay format lại code không liên quan.

## 5. Không kiến trúc phỏng đoán
- Chỉ xây những gì yêu cầu hiện tại cần.
- Ưu tiên code trực tiếp hơn abstraction, factory, hook, framework chưa dùng đến.

## 6. Test
- Test hành vi đã thay đổi.
- Không nới lỏng hay xóa test hiện có chỉ để code pass.
- Sửa nguyên nhân, không sửa test.

## 7. Ngữ cảnh
- Tìm trước, đọc tối thiểu cần thiết.
- Bắt đầu từ public API → schema → test → implementation.
- Không quét repo mù quáng.
- Trước khi kết luận thứ gì hỏng: xem lần chạy thành công gần nhất (log, script, env) và chạy lại đúng đường đó. Probe tự dựng chỉ để khoanh lỗi khi đường thật đã hỏng (F001).

## 8. Production
- Prod chạy từ bản đông cứng `.prod_src/`, không phải `src/`; không sửa tay `.prod_src/`. Chỉ deploy (`./run.sh prod`) khi chủ dự án yêu cầu; lệnh dừng dịch vụ cũ trước nên phải chạy tách khỏi terminal (`docs/OPERATIONS.md` §1).
- Mỗi job cron mang nhãn `# tripguardian-<tên>` và có trong `docs/OPERATIONS.md` §4; đổi đường dẫn script mà cron gọi thì sửa crontab cùng lúc.
- GPU và Docker dùng chung với người khác: không dừng tiến trình hay container không do dự án này tạo.

## 9. Hoàn thành
- Chạy bước kiểm chứng rẻ nhất mà đủ.
- Review diff để loại thay đổi không liên quan.
- Dừng khi hành vi yêu cầu chạy đúng và test liên quan pass.
