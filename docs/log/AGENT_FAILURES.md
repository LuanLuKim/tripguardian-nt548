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

## F002 — `git stash` làm mất trạng thái staged của người dùng

**Ngày:** 2026-11-09 · **Nhóm:** `IMPLEMENTATION` · **Task:** kiểm một test hỏng có phải lỗi sẵn trước thay đổi của agent không
**Kỳ vọng:** chạy test trên bản HEAD mà không đụng working tree / index (ví dụ `git worktree add` một thư mục tạm, hoặc đọc kết quả CI / lần chạy trước).
**Thực tế:** agent chạy `git stash && pytest … ; git stash pop`. `stash pop` không có `--index` nên ~370 thay đổi đã staged của người dùng (gồm rename) thành chưa staged / xoá + file mới.
**Bằng chứng:** `git status` trước: toàn `M `/`R `/`D `; sau pop: ` M`/` D`/`A `. Khôi phục bằng `git read-tree <stash^2>` lấy từ `git fsck --unreachable` (commit "index on prod-cleanup-20261109").
**Hậu quả:** suýt mất công chuẩn bị commit của người dùng; khôi phục được vì stash commit chưa bị gc.
**Nguyên nhân gốc:** giả định sai — coi `stash`/`pop` là thao tác trong suốt với index.
**Lẽ ra nên:** không dùng `git stash` trên cây có thay đổi staged của người khác; kiểm bản cũ trong worktree tạm.
**Rule:** `WATCH` — một lần, khôi phục được; nâng thành rule nếu lặp lại.
**Tái diễn:** 1 · **Trạng thái:** `UNDER_OBSERVATION`

## F003 — Phiên khác trỏ lại rồi xóa symlink `.cache` dùng chung

**Ngày:** 2026-11-10 · **Nhóm:** `SCOPE` · **Task:** một phiên chạy test web (`web/src/user/screens/plan/notes.test.mjs`) cần Chromium của Playwright.
**Kỳ vọng:** đặt `PLAYWRIGHT_BROWSERS_PATH=tripguardian-store/cache/ms-playwright` cho lệnh test, không đụng symlink.
**Thực tế:** phiên đó chạy `ln -sfn /home/vannk/.cache .cache` (đích sai), rồi `.cache` biến mất khỏi repo; lặp lại ít nhất hai lần trong 30 phút (2026-11-10 00:20 và 00:45).
**Bằng chứng:** transcript `~/.claude/projects/-data-work-luanhh-local-tripguardian/529ac849-*.jsonl`; `ls -la .cache` → không tồn tại trong khi `tripguardian-store/cache` còn nguyên.
**Hậu quả:** phiên song song hỏng giữa chừng: `run_agent.sh` không thấy `codex`, crawl Maps không thấy Chromium (`Executable doesn't exist at .cache/ms-playwright/...`); có thể làm prod hỏng khi khởi động lại (`.cache/hf` chứa trọng số model).
**Nguyên nhân gốc:** thiếu rule — `RULE.md` chỉ nói "repo giữ symlink", không nói symlink dùng chung, không được đổi.
**Lẽ ra nên:** đặt biến môi trường cho riêng lệnh; thiếu symlink thì tạo lại đúng đích `tripguardian-store/cache`.
**Rule:** `ADD` — chủ dự án yêu cầu ghi rule (2026-11-10): `RULE.md` §0.3, gạch đầu dòng về symlink `.venv`, `.venv-vllm`, `.cache`.
**Tái diễn:** 2 · **Trạng thái:** `PROMOTED_TO_RULE`

## F004 — Thêm khóa mới vào `config/` khi prod đang chạy bản code chưa biết khóa đó

**Ngày:** 2026-11-10 · **Nhóm:** `RELIABILITY` · **Task:** sửa bộ chia ngày của Planning để lịch không còn ngày trống (thêm ngưỡng `spread_extra_min`).
**Kỳ vọng:** thêm ngưỡng mà không đổi hành vi prod cho tới lần deploy sau.
**Thực tế:** agent ghi `spread_extra_min: 45` vào `config/planning.yaml`. Prod chỉ đông cứng `src/` (`.prod_src/`), còn `config/` đọc thẳng từ repo; `planning.settings.load` là `Settings(**raw)` nên khóa lạ ném `TypeError` ở lần nạp kế (worker quá tải `spawn` nạp lại mỗi lượt, tiến trình chính lúc khởi động lại). Khóa nằm trong file khoảng 8 phút rồi được gỡ.
**Bằng chứng:** `run.sh` `freeze_src` chỉ `rsync src/`; `.prod_src/planning/settings.py` `PATH = ROOT / "config" / "planning.yaml"`; sau khi gỡ: `PYTHONPATH=.prod_src python -c "from planning import settings; settings.load(settings.PATH)"` đạt, `logs/run/*.log` không có `unexpected keyword argument`.
**Hậu quả:** không lỗi nào được ghi; nếu một lượt quá tải hoặc cron `@reboot` chạy trong khoảng đó thì Planning của prod hỏng.
**Nguyên nhân gốc:** giả định sai về kiến trúc (tưởng bản đông cứng gồm cả `config/`).
**Lẽ ra nên:** đặt default trong `settings.py`, chỉ ghi khóa vào YAML sau khi prod đã deploy bản code biết khóa (`docs/OPERATIONS.md` §1).
**Rule:** `WATCH` — mọi loader config đều strict (`trip`, `decision`, `planning`, `live`, `harness`, `agents`), nên mọi phiên sửa `config/` đều gặp rủi ro này; đông cứng `config/` cùng `src/` lúc deploy sẽ xóa cả nhóm lỗi.
**Tái diễn:** 1 · **Trạng thái:** `OPEN`
