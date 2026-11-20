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

## F005 — Ghi đè một file `config/` có sẵn khi tạo config cho module mới

**Ngày:** 2026-11-13 · **Nhóm:** `CONTEXT` · **Task:** thêm module `corpus.events` (sự kiện từ web) kèm file config của nó
**Kỳ vọng:** chọn tên file chưa tồn tại, hoặc kiểm `git ls-files config/` trước khi ghi.
**Thực tế:** agent ghi `config/events.yaml` bằng `cat >` mà không kiểm; file đó đã có (đợt đông khách Noel / Tết nhập tay, `src/live/events.py` đọc, prod đọc config trực tiếp). Phát hiện khi `git status` hiện `M` thay vì `??`, khôi phục bằng `git checkout -- config/events.yaml` sau khoảng 12 phút, config mới đổi tên `config/web_events.yaml`.
**Bằng chứng:** `git show HEAD:config/events.yaml`; `logs/run/harness.log` 12:55–13:07 không có request POST (không lượt lập lịch nào chạy trong khoảng đó).
**Hậu quả:** không có trên prod lần này; nếu một lượt lập lịch chạy trong khoảng đó, `live.events._table` (`@cache`) đọc bảng rỗng và lịch Noel / Tết mất cờ đông khách.
**Nguyên nhân gốc:** kiểm chứng không đủ — ghi file bằng shell thay vì công cụ Write (công cụ đó từ chối ghi đè file chưa đọc).
**Lẽ ra nên:** tạo file mới bằng Write, hoặc `test -e` / `git ls-files` trước `cat >`; đặt tên config theo module (`web_events.yaml`).
**Rule:** `WATCH` — cùng họ với F004 (đụng `config/` khi prod đọc trực tiếp); nâng thành rule nếu lặp lại.
**Tái diễn:** 1 · liên quan F004 · **Trạng thái:** `RESOLVED`

## F006 — Ghi snapshot dữ liệu prod đọc trực tiếp với hình dạng mới mà code prod chưa đọc được

**Ngày:** 2026-11-13 · **Nhóm:** `CONTRACT` · **Task:** nối sự kiện có ngày (`corpus.events`) vào Nhịp Đà Lạt
**Kỳ vọng:** chạy thử `pulse` mà prod vẫn đọc được `data/dalat/pulse/latest.json`.
**Thực tế:** agent chạy `python -m corpus pulse` bằng `src/` mới; mục `event` mới (`signals.source = "web"`) thiếu `status` / `months` mà `.prod_src/corpus/pulse/render.py` cần, nên `bulletin` (khối Trending trang chủ) và tool `trends` của prod ném `KeyError 'status'` khoảng 8 phút (12:59–13:08), tới khi agent kiểm bằng `PYTHONPATH=.prod_src` và dựng lại snapshot bằng code prod.
**Bằng chứng:** `PYTHONPATH=.prod_src python -c "from corpus import pulse; pulse.bulletin('dalat')"` → `KeyError: 'status'`; `logs/run/harness.log` không có 5xx trong khoảng đó.
**Hậu quả:** không người dùng nào gặp lần này; cron `pulse` 04:00 chạy `src/` nên đêm đó prod lỗi lại nếu không sửa. Đã sửa: mục web mang thêm `status`, `months` (test `test_dated_web_events_replace_the_month_only_claims`), render cũ hiện "Diễn ra tháng 11 · 3 nguồn".
**Nguyên nhân gốc:** giả định sai về kiến trúc — dữ liệu `data/` (snapshot Nhịp) prod đọc trực tiếp như `config/` (F004), và cron offline chạy `src/` chứ không phải `.prod_src/`.
**Lẽ ra nên:** trước khi chạy job offline ghi file prod đọc, render thử bằng `.prod_src` (hoặc ghi ra thư mục tạm); field mới chỉ được thêm, không đổi nghĩa field cũ.
**Rule:** `WATCH` — cùng họ F004 / F005 (prod đọc trực tiếp thứ nằm ngoài `.prod_src/`); ba lần trong một tuần, nên cân nhắc nâng thành rule: "đổi hình dạng của file prod đọc trực tiếp (`config/`, `data/*/latest.json`) phải qua kiểm bằng `.prod_src` trước".
**Tái diễn:** 1 · liên quan F004, F005 · **Trạng thái:** `RESOLVED`

## F007 — Chạy `vite build` trong `web/` để kiểm CSS, ghi đè web prod

**Ngày:** 2026-11-13 · **Nhóm:** `RELIABILITY` · **Task:** chỉnh giao diện Lịch trình theo phản hồi, kiểm tra CSS còn biên dịch được sau khi xóa rule cũ.
**Kỳ vọng:** kiểm bằng `npx tsc --noEmit` hoặc dựng ra thư mục tạm (`vite build --outDir <scratchpad>`), không chạm `web/dist`.
**Thực tế:** chạy `npx vite build` trong `web/`; outDir mặc định là `web/dist`, thư mục `web/server.mjs` (:28899, prod) đọc trực tiếp. Bản dựng từ cây làm việc chưa commit (không qua `prod_assets.mjs`, không nén) được phục vụ ~1–2 phút (16:59 → 17:00).
**Bằng chứng:** `ls -la web/dist` mtime 16:59; khôi phục bằng `cp -a web/.deploy-build` (bản deploy 01:52–01:55, cùng giờ server khởi động 01:55:46), `diff -rq web/.deploy-build web/dist` rỗng, `index-DDLe3y0E.js` phục vụ lại.
**Hậu quả:** deploy ngoài ý chủ dự án trong ~2 phút; người vào lúc đó có thể nhận asset chưa duyệt (service worker tự cập nhật ở lần tải sau).
**Nguyên nhân gốc:** giả định sai về kiến trúc (không nhớ `web/dist` là thư mục prod đọc trực tiếp; `OPERATIONS.md` có ghi).
**Lẽ ra nên:** không bao giờ build vào `web/dist` ngoài quy trình deploy; kiểm bằng `tsc` hoặc `--outDir` tạm.
**Rule:** `ADD` — một lần đã gây deploy ngoài ý muốn lên prod; đề xuất thêm vào `RULE.md`: "Không ghi vào `web/dist` (prod đọc trực tiếp) ngoài quy trình deploy; dựng thử thì dùng `--outDir` tạm." Chờ chủ dự án duyệt.
**Tái diễn:** 1 · **Trạng thái:** `OPEN`
