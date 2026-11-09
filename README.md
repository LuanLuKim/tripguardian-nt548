# TripGuardian

> **Dự án học tập, phi thương mại.** Không dùng code, dữ liệu hay nội dung crawl (review Google Maps, video và bình luận TikTok) cho mục đích thương mại. Nội dung crawl thuộc về tác giả gốc và chỉ dùng cho nghiên cứu trong dự án này.

Hệ thống place intelligence + lập lịch trình cá nhân hóa: giúp người dùng **chọn đúng địa điểm trước khi tạo lịch trình**, rồi kiểm tra tổ hợp đã chọn có đi được cùng nhau không. Phạm vi kiểm chứng ban đầu: Đà Lạt.

Bốn giai đoạn, mỗi giai đoạn một package và một tài liệu:

```text
Place Intelligence  src/corpus/   offline: địa điểm → fact / signal / estimate có bằng chứng
Trip Understanding  src/trip/     người dùng cần gì cho chuyến này → Search Input
Place Decision      src/decision/ → shortlist → người dùng tuyển chọn → Decision Output
Planning & Valid.   src/planning/ + src/live/ → phương án, chỗ ở, độ vững → Plan Output
```

Phần dùng chung: `src/harness/` (HTTP/SSE, hành trình chung), `src/agents/` (Agent, tool, skill), `src/accounts/` + `src/db/` (tài khoản, Postgres), `src/companion/` (chế độ Đang đi), `src/analytics/`, `src/notify/`, `src/mailer/` (thư SMTP), `src/requirements/`, `src/social/`, `src/bench/` (đo độ trễ). Giao diện: `web/`.

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| `docs/Project_Context.md` | Vì sao, cho ai, User Profile, nguyên tắc sản phẩm, phạm vi MVP, thước đo |
| `docs/ARCHITECTURE.md` | Bản đồ hệ thống: bốn giai đoạn, ranh giới module, constraint, cấu hình, quyết định thiết kế |
| `docs/AGENT_HARNESS.md` | Agent/tool/skill, router, hành trình chung, revision/retry, HTTP và SSE |
| `docs/CORPUS.md` | Place Intelligence: nguồn, vai trò model, pipeline, gate, data model, CLI, đo chất lượng |
| `docs/NORMALIZED_CORPUS_RECHECK.md` | Tái kiểm normalized data, đọc audit/nhãn strong, integrity/release và coverage |
| `docs/TRIP_UNDERSTANDING.md` | Trip State, chọn câu hỏi, ngân hàng câu hỏi, Search Input, CLI và API |
| `docs/TRIP_UNDERSTANDING_QA.md` | Inventory field/tag, thông tin cốt lõi và tùy chọn, QA prompt → hoàn tất field, mẫu case và bàn giao Planning |
| `docs/PLACE_DECISION.md` | Sàng lọc fail-closed, xếp hạng, đa dạng, khả thi của tổ hợp, Decision Output, CLI và API |
| `docs/PLANNING.md` | Live Context, chia ngày, thứ tự, chỗ ở live, độ vững, dự phòng, Plan Output, CLI và API |
| `docs/PLANNING_PERFORMANCE.md` | Báo cáo tương thích chuyến dài và số đo tối ưu Planning bảy / mười bốn ngày |
| `docs/ACCOUNTS.md` | Đăng nhập Google, phiên, hồ sơ, avatar, xóa tài khoản, liên kết Calendar, Postgres |
| `docs/SECURITY.md` | Ranh giới tin cậy, xác thực, phân quyền, chống lạm dụng, bí mật, khoảng trống bảo mật |
| `docs/COMPANION.md` | Chế độ Đang đi (màn Hôm nay, check-in, gợi ý tại chỗ), xuất Google Calendar có xác nhận, thông báo |
| `docs/ANALYTICS.md` | Event server / web, server analytics private, chỉ số Admin, Insights |
| `docs/BOOKING.md` | `Offer` + adapter deeplink (xe khách, máy bay, chỗ ở), phương án đi từ nhà tới chỗ ở, API và `booking_click` |
| `docs/Role_Web_Functional_Design.md` | Chức năng Web theo vai trò, từng màn, và màn nào nằm ở file nào |
| `docs/UX_Design_Brief.md` | Brief UI/UX: nguyên tắc, cách hiển thị chất lượng dữ liệu, hệ thị giác |
| `docs/UI_SPEC_USER_WEB.md` | Đặc tả trang User Web cho designer / Figma |
| `docs/UI_SPEC_FLOW_LAYOUT.md` | Luồng chuyển màn, kiểu chuyển cảnh và bố cục từng màn User Web |
| `docs/UI_SPEC_LANDING.md` | Đặc tả landing: màn đầu 3D và ba bước (máy tính), trang Dùng ứng dụng (điện thoại) |
| `docs/LLM_PROVIDER.md` | Model nào đảm nhận vai trò nào: endpoint, key, chứng chỉ, ASR local |
| `docs/log/DEV_LOG.md` | Nhật ký **code đang có gì** theo từng tính năng |
| `docs/log/AGENT_FAILURES.md` | Nhật ký lỗi của coding agent, làm bằng chứng trước khi nâng thành rule |

Quy tắc làm việc (bắt buộc): `RULE.md`. Hướng dẫn cho agent: `AGENTS.md`.

## Thiết lập

Mục tiêu: clone code, tải gói dữ liệu, chạy được cả hệ thống như máy đang phát triển. Dữ liệu không nằm trong git.

**Cần cài trước:** Python ≥ 3.12 (đang dùng 3.12), Node ≥ 20.19 (đang dùng 24), Git Bash (Windows; `run.sh` là shell script, dùng `netstat`/`taskkill`), Google Chrome bản thường (Playwright mở Chrome qua `channel="chrome"`), Docker (chỉ cho OSRM). Chỉ khi crawl: ffmpeg trên `PATH`, GPU cho ASR.

```sh
git clone https://github.com/hohoangluan/tripguardian && cd tripguardian
python -m venv .venv && source .venv/Scripts/activate   # Linux/macOS: .venv/bin/activate
pip install -e ".[dev]"                                 # thêm .[asr] chỉ khi chạy ASR; chunkformer: pip install --no-deps
python -m playwright install chromium                    # browser headless cho test parser và crawl
cd web && npm install && cd ..
cp .env.example .env                                     # điền key: docs/LLM_PROVIDER.md
```

1. **Dữ liệu.** Tải `tripguardian-data-<ngày>.zip` mới nhất từ [Drive của nhóm](https://drive.google.com/drive/folders/1LeEgIdoioyCAM64WV3VLGeKYA-X5yEGT?usp=sharing), giải nén **tại thư mục gốc repo**: `python -m zipfile -e tripguardian-data-<ngày>.zip .` — gói trả về đúng chỗ `data/`, `web/public/data/snapshot.json` (dữ liệu web hiển thị) và `tests/fixtures/{gmaps,tiktok}` (trang crawl thật cho test parser). Mấy file này trích review và tài khoản người thật nên không nằm trong repo public. Gói không có `video.mp4` của TikTok (chỉ bước ASR khi crawl cần); bản `--no-photos` không có ảnh Maps, khi đó `/admin/labels` không hiện ảnh.
2. **Key.** Trip Understanding, chọn câu hỏi và mọi phase cần model gọi API UIT, chỉ trả lời trong mạng campus; key và endpoint ở `.env`. Lỗi chứng chỉ `llm.uit.edu.vn`: tạo CA bundle một lần mỗi máy — `docs/LLM_PROVIDER.md` §Chứng chỉ TLS.
3. **OSRM** (thời gian di chuyển cho Planning): `bash scripts/osrm_setup.sh` một lần mỗi máy — tải OSM Việt Nam, dựng chỉ mục vào `osrm-data/`, mở `127.0.0.1:5000`. Lần sau chỉ cần chạy lại container (dòng `docker run ... -p 127.0.0.1:5000:5000` cuối script). Không có OSRM thì Planning ước lượng thô và gắn cảnh báo. Endpoint và TTL ở `config/live.yaml`; `LIVE_CONTACT` trong `.env` là liên hệ gửi kèm request.
4. **Postgres** (tài khoản, hành trình, event, thông báo; cần Docker): điền `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_URL_READONLY` trong `.env`, rồi `./run.sh db` — tạo container `tripguardian-pg` ở `127.0.0.1:5433`, role, database và chạy migration (chạy lại an toàn). `./run.sh db-backup` sao lưu vào `data/backup/pg/`. Quên mật khẩu cần thư: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` (`docs/ACCOUNTS.md` §2c). Đăng nhập Google, Calendar và web push cần thêm `APP_BASE_URL`, `GOOGLE_*`, `TOKEN_ENC_KEY`, `VAPID_*` (`.env.example`, `docs/ACCOUNTS.md`). Hành trình cũ dạng file: `python -m harness import-files data/harness/sessions data/harness/feedback.jsonl`.
5. **Agent endpoint và web search.** `AGENT_BASE_URL` trỏ `127.0.0.1:<cổng>` thì `./run.sh start` tự bật **9router** (cần `npm i -g 9router`; không có thì Agent trả lời theo policy dự phòng). `./run.sh prod` bật thêm **SearXNG** (`127.0.0.1:8888`, Docker; `docker/searxng/README.md`) cho tool `web_search` của Trip agent; `web_base_url` trống ở `config/trip.yaml` thì agent không có tool web.
6. **Chỉ mục ngữ nghĩa** (ảnh / câu → "vibe", "chỗ như này"): nằm trong gói dữ liệu ở `data/index/`. Harness nạp embedder trên GPU `HARNESS_GPU` (mặc định `1`); dựng lại: `python -m corpus index` (`docs/CORPUS.md` §Chỉ mục ngữ nghĩa).
7. **Chỉ khi crawl:** đăng nhập tài khoản phụ một lần mỗi máy, `python -m corpus login tiktok`, `python -m corpus login gmaps` (profile lưu ở `.browser/`, đã gitignore). Chạy dịch vụ và Planning lodging không cần đăng nhập.

Người giữ dữ liệu tạo gói mới: `python scripts/pack_data.py [--no-photos] [--out <thư mục>]` (cái gì bị bỏ và vì sao: docstring của script), rồi đưa zip lên Drive. Sửa `data/` xong mà web cần thấy: `python web/scripts/export_snapshot.py` trước khi đóng gói.

## Chạy

```sh
./run.sh start   # 9router + harness + analytics (private) + review + web dev server + worker thông báo, in ra URL khi mọi cổng đã trả lời
./run.sh stop    # dừng mọi tiến trình script này khởi động
```

Production (gpu156, public qua Cloudflare tunnel):

```sh
./run.sh prod       # backup + migrate db → thumbnail → build web (build:prod) → SearXNG → 9router → harness :8769 → web/server.mjs :28899 → worker thông báo → tunnel (token ở ~/.cloudflared/tripguardian.token) → smoke test
./run.sh prod-stop  # dừng tất cả
```

Prod chạy code từ **bản đông cứng `src_live/`** (không phải `src/`): `./run.sh prod` chép `src/` → `src_live.new/`, kiểm import, dừng dịch vụ cũ rồi đổi tên và khởi động harness + worker thông báo với `PYTHONPATH=src_live`. Sửa `src/` (người hay agent, kể cả worker quá tải `spawn` nạp lại `planning` mỗi lượt) không vào prod cho tới lần deploy sau. `src_live*` nằm ngoài git.

`web/server.mjs` chỉ phục vụ phần public: landing, `/app`, `/assets`, `/img`, `/data`, ảnh `/media` (jpg), thumbnail `/media/thumb` (WebP) và proxy `/api/harness/*`, `/api/auth/*` (keep-alive); `/admin`, analytics, mọi `/api` khác và video trả 404. Cần Postgres đang chạy (`./run.sh db`). Route hostname → cổng nằm trong dashboard Cloudflare của tunnel; `prod` in ra các route nhận được để thấy ngay khi token sai. Đổi cổng / token: `PUBLIC_PORT`, `TUNNEL_TOKEN_FILE`. Tiến trình chạy bằng `nohup`; sau khi máy reboot, job cron `@reboot` (nhãn `# tripguardian-reboot`, §Cron production) chạy lại `./run.sh prod`. Tiến trình chết giữa chừng không tự lên lại.

Tốc độ production: `web/scripts/make_thumbs.py` tạo WebP rộng ≤ 480 px cho mọi ảnh bìa vào `data/thumbs/<nguồn>/` (chỉ ảnh mới); `npm run build:prod` = `vite build` + `web/scripts/prod_assets.mjs`: `dist/data/snapshot.json` chỉ giữ trường User Web đọc (27 → 16 MB, `public/data` vẫn đủ cho dev/admin) và mọi file văn bản có bản `.br` / `.gz` (cache theo hash ở `web/node_modules/.cache/tg-prod`). `server.mjs` gửi bản nén client nhận, gắn `ETag` (lần sau 304); `/data` cache 5 phút + revalidate, `/media` 7 ngày, `/assets` immutable.

**Ping production qua Cloudflare (Linux).** `scripts/keepalive.py` dùng Python 3 chuẩn và `curl`, GET `/app` cùng `/api/harness/me` mỗi phút qua domain public. Script không gửi cookie, không tạo tài khoản/journey hay gọi model; query riêng mỗi lượt tránh dùng lại cache. Thành công khi `/app` trả 200 có app shell và API trả đúng 401 với JSON `{"error":"sign in first"}`. Đây là kiểm tra đường HTTP đến backend, chưa kiểm tra DB, model hay toàn bộ hành trình.

Cron trên gpu156: §Cron production (dòng `# tripguardian-keepalive`).

Kiểm tra thủ công và xem log:

```sh
python3 scripts/keepalive.py --base-url https://tripguardian.visioncare-host.uk
tail -n 5 logs/run/keepalive.log
```

Mỗi request giới hạn 15 giây; khóa file tránh chạy chồng. Log ghi giờ UTC, HTTP status, độ trễ và `ok`, xoay vòng tối đa khoảng 3 MiB (`keepalive.log`, `.1`, `.2`); exit code 1 khi lỗi. Tắt ping: xóa riêng dòng có nhãn `# tripguardian-keepalive` trong `crontab -e`. `prod-stop` không xóa cron; khi stack dừng, ping ghi lỗi. Ping không tự khởi động lại tiến trình hay bảo đảm uptime khi máy/mạng ngừng hoạt động; chưa gửi cảnh báo ra ngoài.

**Vị trí trên gpu156 và sao lưu.** Repo nằm trên ổ cục bộ `/data/work/luanhh/local/tripguardian/checkout` (`/workingspace_aiclub/WorkingSpace/Unsorted/luanhh/tripguardian` là symlink tới đây). Thư mục repo chỉ chứa code (cộng `data/`, `logs/` đã gitignore); thứ không phải code nằm ở `/data/work/luanhh/local/tripguardian-store/`: `venv` (`.venv` là symlink), `venv-vllm` (`.venv-vllm`), `cache` (`.cache`; trong đó `hf` → `hf-repo` là trọng số model, `uv` → `uv-repo`), `uv-python` (Python 3.12 mà các venv dùng, không phụ thuộc home), `hf` (model sinh ảnh / 3D), `imggen-venv`, `splat` (dữ liệu dựng 3D), `osm` (bản OSM tải ngày 02/11; code không dùng, OSRM dùng bản trong `osrm-data/`). Docker rootless (Postgres, OSRM, SearXNG) có `data-root` `/data/work/luanhh/local/docker` cùng ổ. Sao lưu ra NAS `/data/work/luanhh/nas/tripguardian/`: `pg-backup/` (dump hằng đêm), `data/` (bản sao `data/`, chép lại bằng `rsync -aH data/ /data/work/luanhh/nas/tripguardian/data/`), `archive-<ngày>/` (log, file làm việc đã dọn khỏi repo).
Khi `:5433` từ chối kết nối hoặc harness báo `PoolTimeout`: xem `df -h /data/work/luanhh/local` và `docker logs --tail 30 tripguardian-pg` trước.

| Dịch vụ | Cổng | Lệnh tương đương |
|---|---|---|
| Web (Vite) | 5173 | `http://127.0.0.1:5173/` (landing) · `/app` · `/admin` |
| Agent harness (Trip, Decision, Planning) | 8769 | `python -m harness serve` |
| Analytics (private) | 8770 | `python -m analytics serve --port 8770` |
| Trang review / gán nhãn | 8765 | `python -m corpus review` |
| 9router (endpoint của Agent) | theo `AGENT_BASE_URL` | `9router` |
| SearXNG (`web_search`, chỉ prod) | 8888 | container `tripguardian-searxng` |

Xe khách cho câu hỏi hậu cần được tra trước mỗi ngày vào cache `data/live/vexere/` (phạm vi: `config/live.yaml` `transit_prewarm`; một nguồn lỗi 8 lần liền thì dừng nguồn đó). Chuyến bay không dùng cache (`config/live.yaml` `flight_cache: false`): mỗi câu hỏi mở Google Flights trực tiếp, prewarm bỏ qua chuyến bay. Máy không có Chrome: `run.sh` tự trỏ Playwright vào Chromium trong `.cache/ms-playwright` cho harness và cho lệnh này. Cron: §Cron production.

CLI/API module chạy độc lập khi cần: `python -m trip serve` (:8766), `python -m decision serve` (:8767), `python -m planning serve` (:8768). User Web dùng harness và journey chung; contract ở `docs/AGENT_HARNESS.md`.

### Cron production

Trên gpu156 (`crontab -e`, giữ các job khác; mỗi job một nhãn để gỡ riêng):

```cron
@reboot sleep 120; cd /data/work/luanhh/local/tripguardian/checkout && PATH=$HOME/node/bin:/usr/local/bin:/usr/bin:/bin ./run.sh prod >> logs/run/reboot.log 2>&1 # tripguardian-reboot
* * * * * /usr/bin/python3 /data/work/luanhh/local/tripguardian/checkout/scripts/keepalive.py --base-url https://tripguardian.visioncare-host.uk >/dev/null 2>&1 # tripguardian-keepalive
*/10 * * * * /data/work/luanhh/local/tripguardian/checkout/scripts/disk_guard.sh # tripguardian-disk-guard
30 2 * * * /data/work/luanhh/local/tripguardian/checkout/scripts/pg_backup_nas.sh # tripguardian-pg-backup
15 3 * * * cd /data/work/luanhh/local/tripguardian/checkout && ./run.sh prewarm >> logs/prewarm_transit.log 2>&1
0 4 * * * /data/work/luanhh/local/tripguardian/checkout/scripts/pulse_daily.sh dalat --once # tripguardian-pulse
```

- `@reboot`: Docker rootless tự lên (linger bật), 120 giây sau chạy lại toàn bộ `./run.sh prod` (build, Clef, harness, web, worker, tunnel, smoke); log `logs/run/reboot.log`.
- `disk_guard.sh`: ổ chứa Docker data-root còn dưới 5 GiB thì ghi `logs/disk_guard.log` và chạy `CHECKPOINT` (ngày 03/11 ổ cũ đầy 100% làm Postgres tắt).
- `pg_backup_nas.sh`: `pg_dump` sang `/data/work/luanhh/nas/tripguardian/pg-backup/` (đổi bằng `PG_BACKUP_DIR`), giữ 14 bản mới nhất, log `logs/pg_backup_nas.log`.
- `prewarm`: cache xe khách (đoạn trên).
- `pulse_daily.sh`: làm mới bản tin Nhịp Đà Lạt (`docs/CORPUS.md` §Nhịp Đà Lạt); bản tin cũ quá `stale_after_days` thì web báo chưa được làm mới.

### Test Trip bằng Streamlit

Một client tối thiểu để kiểm thử riêng Trip Understanding qua đúng Harness HTTP/SSE (không thay thế User Web):

```sh
python -m harness serve
streamlit run tools/trip_tester.py
```

Mặc định app kết nối `http://127.0.0.1:8769`; có thể đổi URL ở sidebar. Cài dependencies dev trước bằng `pip install -e ".[dev]"`.

Chạy thử User Web toàn luồng với harness thật (Khám phá → Hiểu chuyến đi → Chọn nơi → Lịch trình → Phản hồi), chụp từng màn vào `web/shots/app/`: `node web/scripts/shots_app.mjs [http://127.0.0.1:5173]`. Script dùng Chromium đầy đủ trong `.cache/ms-playwright/chromium-1169` (bản headless shell treo trên server dùng chung); `playwright-core` của web ghim 1.52.0 để khớp bản Chromium đó.

Log ở `logs/run/<tên>.log`. Web đọc địa điểm từ `web/public/data/snapshot.json` (trong gói Drive); sinh lại bằng `python web/scripts/export_snapshot.py` sau khi aggregate. Gallery mỗi nơi (≤ 12 ảnh Maps / frame clip, ảnh đầu là ảnh bìa) nằm ở `web/public/data/covers.json`, sinh bằng `python web/scripts/pick_covers.py`: YOLO loại ảnh có người chiếm khung, pHash bỏ ảnh gần trùng, Gemma (task `photo_rank`, cache `.cache/photo_rank.json`) chấm độ đẹp và mức thể hiện nơi đó (chạy GPU + host LAN vài giờ; `--resume` chạy tiếp chỗ dừng, `--dry-run --ids a,b` in thứ hạng; tạm dừng `logs/tiktok_lan_uit_lane.sh` khi chạy). Xong thì chạy `make_thumbs.py`.

## Xây dữ liệu và chạy từng bước

Lệnh đầy đủ của từng giai đoạn nằm trong tài liệu của giai đoạn đó. Đường chính:

```sh
# 1. Place Intelligence (docs/CORPUS.md §CLI)
python -m corpus gmaps all --city dalat --headed     # search → filter → counts → list → crawl → qc → observe
python -m corpus gmaps photos && python -m corpus gmaps photo_observe
python -m corpus tiktok all --city dalat --headed
python -m corpus aggregate && python -m corpus serving   # serving cũng biên dịch snapshot cho phần online
python -m corpus snapshot                            # chỉ biên dịch lại snapshot từ data/serving/places.json
python -m corpus views all --city dalat             # khí hậu, lịch, vùng hạn chế → data/dalat/views/ (docs/CORPUS.md §View toàn cầu)
python -m corpus pulse --city dalat                  # Nhịp Đà Lạt: bản tin xu hướng từ dữ liệu đã crawl → data/dalat/pulse/ (docs/CORPUS.md §Nhịp Đà Lạt; mỗi 24 giờ: scripts/pulse_daily.sh)
python -m corpus index                               # chỉ mục ngữ nghĩa: vector theo GPU (vectors) rồi gộp vào data/index/ (compile)
python -m corpus normalize --city dalat              # chuẩn hóa, báo membership/source/schema; không đổi serving pointer
python -m corpus normalize --rebuild --city dalat    # dựng release staging chỉ từ dữ liệu đã lưu, không model/network
python -m corpus normalize --rebuild --publish --city dalat  # dựng, kiểm chứng rồi chuyển release pointer
python web/scripts/export_snapshot.py --view both    # User Web theo release; Admin có snapshot riêng
python -m bench latency --scale 1,5,20               # độ trễ phần dùng corpus (data/bench/latency/)

# 2. Đo xem corpus đã đủ cho Place Decision chưa (docs/PLACE_DECISION.md §17)
python -m decision evaluate                          # 30 Trip State ẩn → data/decision/eval.json

# 3. Lập lịch trình từ một Decision Output (docs/PLANNING.md §CLI và API)
python -m planning build    <decision_output.json>
python -m planning variants <decision_output.json> [--weather forecast.json]
python -m planning lodging  <decision_output.json>   # chỗ ở cạnh tranh làm neo mỗi ngày
python -m planning evaluate                          # 30 chuyến ẩn qua Decision → Planning
```

Journey giữ corpus binding qua Trip → Decision → Planning và restore/copy; đổi release pointer
không chuyển journey đã pin. Sau khi cập nhật code hoặc muốn deployment nhận release mặc định
mới, restart toàn harness theo quy trình đang dùng. Build `publish=false` không cần restart.
Contract và rollback: `docs/CORPUS.md` §Chuẩn hóa và release offline.

Phase cần model cần mạng UIT; gặp captcha thì giải trong cửa sổ trình duyệt (`--headed`). `evaluate` của Planning cần OSRM đang chạy và không chạy trong CI.

## Test

```sh
python -m pytest -q                      # không gọi mạng; thiếu gói Drive thì test parser Maps/TikTok tự skip
python -m pytest -q tests/planning        # một giai đoạn
python scripts/journey_sim.py [--monkey N]           # mô phỏng người dùng đi hết Trip → Decision → Planning trên dữ liệu thật, không gọi model hay mạng; báo cáo ở data/journey_sim/report.json; `--agent` chạy 5 kịch bản gõ chữ qua Gemma trên UIT (từ chối chạy nếu `AGENT_BASE_URL` không phải UIT) và in thời gian từng lượt
```

Đo matrix local từ `src/` hiện tại (cần Postgres, `bwrap`, `.env`, model gateway đang có; không deploy/build): `scripts/local_stack.sh start`, `status`, `stop`. Mặc định web `127.0.0.1:28919` → harness `:8879`; đổi bằng `LOCAL_WEB_PORT`/`LOCAL_HARNESS_PORT` khi start. Ví dụ smoke **một ca**: `PROD_JOURNEY_BASE=http://127.0.0.1:28919 .venv/bin/python scripts/prod_journey_e2e.py --only solo_f_cafe_photo --jobs 4 --run-id local-smoke`. DB schema riêng; config CPU overlay, cache/log/PID riêng dưới `.superpowers/sdd/2026-11-03-prod-e2e/local-harness/`; corpus và `web/dist` chỉ đọc, không notify worker. `stop` chỉ dừng tiến trình của stack, giữ schema và bằng chứng; số đo CPU không so trực tiếp với GPU prod. Không chạy cả matrix trên gateway dùng chung khi chưa được phép.

Test gọi mạng hoặc model thật nằm sau marker `live` và bị `addopts` loại khỏi lần chạy mặc định (`pyproject.toml`). Test marker `pg` cần Postgres: `TEST_DATABASE_URL=<DATABASE_URL> python -m pytest -q` (mỗi test một schema tạm); thiếu biến thì tự skip. Marker `corpus` cần `data/snapshot/current` (`python -m corpus snapshot`); thiếu thì tự skip.

Web (CI không chạy): `cd web && npm run build` (có `tsc -b` kiểm kiểu). Test Node ở `web/scripts/test_*.mjs`, chạy bằng `node --test web/scripts/<file>`: `test_server_security.mjs` (proxy public, không cần dịch vụ ngoài) và `test_planning_state.mjs` chạy được ngay; `test_understand_ui.mjs` / `test_overload_ui.mjs` mở Chromium với fixture riêng (`test_overload_ui.mjs` do `tests/harness/test_overload_browser.py` dựng); `test_journey.mjs` cần `journey.ts` biên dịch trước (`JOURNEY_JS`).

## Hồ sơ dự thi

Không thuộc tài liệu chính thức (`RULE.md` §0.1), chỉ để tra khi cần:

| Tệp | Nội dung |
|---|---|
| `submission/TECHNICAL_REPORT.md` | Proposal & Technical Specification (đặc tả kỹ thuật, số đo kèm ngày) |
| `submission/PITCH_EVIDENCE_20261017.md`, `submission/evidence/` | Bằng chứng chạy thật cho phần thuyết trình (2026-10-17) |
| `submission/pitch_desk.md`, `submission/PRESENTATION_TRIPGUARDIAN.md` | Kịch bản 13 slide, 11 phút 15 giây; nội dung thuyết trình |
| `submission/ARCHITECTURE_MODULES.md` | Kiến trúc các module hỗ trợ (Live Context, …) cho ban giám khảo |
| `submission/2026-10-06_de_tai_08_tour_guide_agent.docx` | Đề đồ án |
| `submission/surveys/` | Hai khảo sát người dùng (CSV) và notebook lọc / trực quan hóa |
| `submission/research/` | Ý tưởng, báo cáo kiểm và tóm tắt bench dùng làm nguồn cho báo cáo |

## Làm việc nhóm

- Mỗi task một branch từ `main` (`feat/<giai-đoạn>-<việc>`, `fix/...`), mở PR vào `main`; không push thẳng `main`.
- Trước khi mở PR: `python -m pytest -q` xanh. CI (`.github/workflows/test.yml`) chạy đúng lệnh này trên mỗi PR.
- Bắt buộc theo `RULE.md`: tài liệu tiếng Việt, code tiếng Anh, chỉ gọi module khác qua `__init__.py`, sửa tài liệu của giai đoạn khi đổi hành vi.
- Không commit `.env`, `data/`, `.browser/`, `logs/`, `snapshot.json`, `tests/fixtures/{gmaps,tiktok}` (đã gitignore). Repo public: không đưa nội dung crawl (review, bình luận, tên tài khoản người thật) vào git; dữ liệu chung đi qua gói zip ở §Thiết lập.

## Ranh giới

Mỗi giai đoạn chỉ giao tiếp với giai đoạn khác qua public API của package (`__init__.py`), không deep import; mỗi nguồn dữ liệu ngoài có module và thư mục dữ liệu riêng. Chi tiết và lý do: `RULE.md` §2, `docs/ARCHITECTURE.md` §3.
