# Bàn giao: việc còn mở sau 15/11/2026 (xu hướng, Lịch trình)

Thay hai bàn giao 13/11 (`chat-trends`, `web-ui-feedback`, xem lịch sử git). Việc đã làm nằm ở `docs/log/DEV_LOG.md` mục `overload-most-2026-11-15`, `trends-pictures-seasons-2026-11-15` và tài liệu module. Xóa file này khi các mục dưới đã xong.

## Còn mở

1. **Cron Nhịp** (cần chủ dự án tự chạy: lệnh sửa crontab bị bộ phân loại quyền chặn hai lần, 13/11 và 15/11). Thay dòng `tripguardian-pulse` bằng:
   `0 4 * * * /data/work/luanhh/local/tripguardian/scripts/trends_daily.sh dalat # tripguardian-trends`
   Cách an toàn: `crontab -l > /tmp/cron.bak && crontab -l | sed 's#^0 4 \* \* \* .*pulse_daily.sh dalat --once \# tripguardian-pulse$#0 4 * * * /data/work/luanhh/local/tripguardian/scripts/trends_daily.sh dalat \# tripguardian-trends#' | crontab -`. Tới khi đổi, mỗi đêm chỉ `pulse` chạy (sự kiện, ảnh, TikTok không được làm mới).
2. **Đánh giá Maps mới**: `gmaps refresh` đã có và chạy trong cửa sổ đăng nhập `gmaps_e` cổng 9530 (chủ dự án đăng nhập 15/11). Cửa sổ chết (máy khởi động lại, Google hủy phiên) thì đăng nhập lại: `CORPUS_DEBUG_PORT=9530 CORPUS_PROFILE_STATE=1 CORPUS_BROWSER_CHANNEL=chromium PLAYWRIGHT_BROWSERS_PATH=$PWD/.cache/ms-playwright PYTHONPATH=src nohup .venv/bin/python -m corpus login gmaps --profile gmaps_e &`, rồi chủ dự án vào `chrome://inspect` → `localhost:9530`. Chữ của đánh giá mới chưa qua `observe` (Extractor giờ là UIT, chung key với Judge).
3. **"Chat mới hiện lịch cũ"**: chưa tái hiện được; hỏi chủ dự án còn gặp không.
4. Mùa "mùa hồng chín" chưa có nơi ngắm (trang nguồn không nêu nơi nào đủ 2 lần); "Biểu tượng Hoa Dã Quỳ" (tượng đài) đứng đầu nơi ngắm dã quỳ vì mang tên mùa. Nếu chủ dự án thấy chưa đúng: chỉnh `SEE_OWN` / nhóm `SEE_GROUPS` trong `src/corpus/pulse/compute.py`.

## Cách chạy thật không deploy

- Harness prod `:8769`; Vite dev `cd web && npx vite --port 5199` (proxy sang `:8769`). Không bật harness thứ hai. **Không chạy `vite build` trong `web/`** (ghi thẳng `web/dist` prod đọc; `AGENT_FAILURES.md` F007).
- POST bị `403 cross-origin` nếu `Origin` khác `APP_BASE_URL`: trong Playwright `context.route('**/api/**', r => r.continue({ headers: { ...r.request().headers(), origin: PUBLIC } }))`, `PUBLIC` = `APP_BASE_URL` trong `.env`. Đăng nhập bằng *Dùng thử, không cần tài khoản* ở `/app/login`; vào thẳng `/app/understand`; `waitUntil: 'domcontentloaded'`.
- Một lượt chat không qua web: dựng `bench.assistant.engine_for("live")`, gọi `engine.turn(sid, TurnInput(kind="text", text=...), emit)` (cần 9router `:20128`, OSRM `:5000`); chạy từ file script (không phải stdin: worker quá tải `spawn` cần đường dẫn file).
- Dựng lại dữ liệu xu hướng: `PYTHONPATH=src .venv/bin/python -m corpus pulse --city dalat`, rồi `-m corpus events --city dalat` (ảnh cho tên mùa của bản Nhịp vừa dựng), rồi `pulse` lần nữa; sau đó kiểm prod đọc được: `PYTHONPATH=.prod_src .venv/bin/python -c "from corpus import pulse; pulse.bulletin('dalat'); pulse.trends('dalat')"`.
