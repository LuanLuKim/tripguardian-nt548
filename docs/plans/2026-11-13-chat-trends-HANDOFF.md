# Bàn giao: chat Hiểu chuyến đi kiểu ChatGPT, sự kiện có ngày, khối xu hướng (13/11/2026)

Trạng thái: **chưa commit, chưa deploy**. Mọi thay đổi nằm trong working tree của `main` (xem `git status`). Prod vẫn chạy `.prod_src/` cũ.

## Chủ dự án đã chốt (13/11/2026)

- Giữ trả lời ngắn trong bong bóng như cũ; chỉ học điểm hay của ChatGPT. Bản thử "bài research đọc web lúc hỏi" (25–40 s mỗi lượt, có lúc 1 phút) đã bỏ vì quá chậm. Patch của bản thử để tham khảo: `/tmp/claude-2420/-data-work-luanhh-local-tripguardian/2b033e18-3ff2-40d6-b140-7b5982d9444e/scratchpad/research-article-full.patch` (thư mục tạm, có thể mất khi máy khởi động lại).
- Câu hỏi xu hướng / sự kiện / mùa: trả lời ngắn + một khối "bài post" bên dưới (giống ChatGPT), chỉ đúng phần được hỏi. Khối do code dựng từ dữ liệu chuẩn bị mỗi đêm, không do model viết lúc hỏi.
- Hàng không có ảnh hiện như đoạn bài viết (không ô ngày: "thô, xấu").
- Crawl dữ liệu xu hướng mỗi đêm: sự kiện từ web; TikTok 200 nơi mỗi đêm; Maps để sau.

## Đã làm (code + test, xem `docs/log/DEV_LOG.md` mục `chat-style-2026-11-13`, `trends-events-2026-11-13`)

1. **Web chat** (`web/src/user/screens/understand/`): `Turn.tsx` dòng "đang làm gì" kiểu ChatGPT (một dòng xám, bước hiện tại, gập sẵn), `Sources.tsx` (chip nguồn dưới lời, `SourceChip` cuối câu), `Rich.tsx`, `Places.tsx` (thẻ không tự mở, tiêu đề có nghĩa), `Trends.tsx` (khối xu hướng), CSS trong `css/chat.css` (`.tg-tr*`, `.tg-src*`).
2. **Văn phong agent** (`src/trip/agent/prompt.py` `ASSISTANT`: Trends, Voice): không đọc số video / đánh giá, không "theo dữ liệu", không mở đầu "Tham khảo:" cho xu hướng, "có gì hot" thì nói sự kiện có ngày + mùa trước.
3. **Module `corpus.events`** (`src/corpus/events/`, `config/web_events.yaml`, prompt `EVENT_EXTRACT` trong `corpus/llm/tasks.py`, CLI `python -m corpus events --city dalat`): sự kiện tháng này và tháng sau từ SearXNG, gate bằng code, gộp trùng, ảnh `og:image` (bỏ ảnh banner dùng chung). Tài liệu: `docs/CORPUS.md` §Sự kiện sắp tới. Test: `tests/events/`.
4. **Nhịp đọc sự kiện có ngày** (`corpus/pulse/{signals,compute,render,__init__}.py`, `config/pulse.yaml` `event.web_fresh_days`): thay các sự kiện từ claim (chỉ có tháng, tên rác). Mục sự kiện mới **mang thêm `status`, `months`** để `.prod_src` cũ vẫn đọc được (xem F006).
5. **TikTok `poi_refresh`** (`src/corpus/crawl/tiktok/poi_refresh.py`, `config/queries.yaml` `tiktok.poi_refresh_per_run: 200`): liệt kê lại trang nơi TikTok, không đăng nhập, không tải video → `data/tiktok/poi_recent/`; `signals.tiktok_videos` gộp với `poi_crawl`. Đã chạy thử 5 nơi (thấy video tới 09/11).
6. **Khối xu hướng trong chat** (`src/trip/api/blocks.py` `trends_block`, `trend_kinds`; `Knowledge.trend_rows` / `_intro`; engine phát khối khi lượt có `xu_huong` hoặc gọi `trends`): mục theo câu hỏi (sự kiện / mùa / nơi đang được nhắc). Test: `tests/trip/test_trends_block.py`. Đo thật: "tháng 11 có sự kiện gì" 6 s, "có gì đặc biệt" 10,6 s.
7. `scripts/trends_daily.sh` (events → poi_refresh → pulse), `docs/OPERATIONS.md` §4 đã ghi dòng cron mới.

## Việc còn mở (theo thứ tự)

1. **Commit.** Test đủ đã chạy 13/11 13:22: `pytest tests --ignore=tests/diorama` → 5567 qua, 1 lỗi `tests/decision/test_wish_speed.py::test_first_run_p95_within_budget` (p95 196 ms > 120 ms), lỗi y hệt trên bản sạch (`git stash`), tức có từ trước, do máy bận; `tests/diorama` lỗi trùng tên file test từ trước; `cd web && npx tsc -b` qua. Nếu sửa thêm thì chạy lại. Commit theo memory `nhom44-commit-authors` / attribution hiện hành; không push từ gpu156 (memory `git-push-gpu156`).
2. **Ảnh đẹp như ChatGPT.** Hiện ảnh sự kiện là `og:image` của trang (hay là banner). Hướng: lúc `corpus events`, tìm ảnh theo tên sự kiện (SearXNG `categories=images`), loại ảnh logo / banner (ảnh dùng chung nhiều sự kiện, ảnh quá nhỏ), lưu `image` + nguồn ảnh. Mục mùa (`season`) chưa có ảnh và chưa có câu mô tả: cùng cách, hoặc lấy ảnh nơi tiêu biểu trong kho.
3. **Cần chủ dự án cho phép** (đã bị chặn ở bước xin quyền, không tự lách):
   - Chạy lượt `poi_refresh` đầu cho cả 731 nơi: `PLAYWRIGHT_BROWSERS_PATH=$PWD/.cache/ms-playwright CORPUS_BROWSER_CHANNEL=chromium PYTHONPATH=src .venv/bin/python -m corpus tiktok poi_refresh --city dalat --limit 731` (~1 giờ).
   - Đổi cron: thay dòng `tripguardian-pulse` bằng `0 4 * * * /data/work/luanhh/local/tripguardian/scripts/trends_daily.sh dalat # tripguardian-trends`.
4. **Maps đánh giá mới** chưa có job: cần `gmaps crawl` (đăng nhập Google) rồi `observe` qua Extractor LAN (`192.168.20.150:8899/8900` không phản hồi ngày 13/11; `corpus events` dùng vai trò Judge trên UIT).
5. **Lời cho câu "người mới… có gì đặc biệt"** còn yếu (nêu nơi rồi hỏi "Bạn đi từ đâu?"); prompt đã thêm thứ tự sự kiện → mùa → nơi nhưng chưa đo lại.
6. Deploy (chỉ khi chủ dự án yêu cầu, `docs/OPERATIONS.md` §1): sau deploy mới thêm khóa mới vào config nào prod đọc với loader strict.

## Cẩn thận (sự cố trong phiên, `docs/log/AGENT_FAILURES.md` F005, F006)

- Prod đọc **trực tiếp** `config/` và `data/*/latest.json`, chỉ `src/` được đóng băng. Cron `pulse` chạy `src/` của repo. Sau mỗi lần chạy `corpus pulse` bằng code mới, kiểm: `PYTHONPATH=.prod_src .venv/bin/python -c "from corpus import pulse; pulse.bulletin('dalat'); pulse.trends('dalat')"`; lỗi thì dựng lại bằng `PYTHONPATH=.prod_src .venv/bin/python -m corpus pulse --city dalat`.
- `config/events.yaml` là đợt đông khách nhập tay cho lập lịch, không phải config của `corpus.events` (`config/web_events.yaml`).

## Cách kiểm nhanh

- Một lượt chat thật không đụng prod: script `live_turn.py` trong scratchpad ở trên (dựng `bench.assistant.engine_for("live")`, in lời, log, khối); cần 9router `:20128`, OSRM `:5000`.
- Dựng lại dữ liệu: `PYTHONPATH=src .venv/bin/python -m corpus events --city dalat` (~1–2 phút, cache theo trang) rồi `-m corpus pulse --city dalat` rồi kiểm `.prod_src` như trên.
