# Vận hành production

Production chạy trên gpu156, public qua Cloudflare tunnel. Trang này mô tả deploy, vị trí file, sao lưu, cron và kiểm tra sức khỏe. Cách chạy dev và cổng từng dịch vụ: `README.md` §Chạy. Ranh giới bảo mật của bản public: `docs/SECURITY.md`.

## 1. Deploy

```sh
./run.sh prod       # backup + migrate db → thumbnail → build web (build:prod) → SearXNG → 9router → harness :8769 → web/server.mjs :28899 → worker thông báo → chờ harness warm-up → tunnel → smoke test
./run.sh prod-stop  # dừng tất cả (tunnel gồm cả), không đụng cron
./run.sh prod-restart   # khởi động lại dịch vụ prod trên .prod_src/ hiện có: không build, không đông cứng, không migrate
./run.sh prod-rollback  # quay về bản đông cứng mà lần deploy trước thay ra (.prod_src.prev), rồi khởi động lại
./run.sh prod-check     # prod đang chạy bản nào, và config/ hiện tại có nạp được bằng code đó không
```

- Tunnel chỉ mở sau khi harness warm xong (dòng `Journey warmup:` trong `logs/run/harness.log`, khoảng 2 phút), để khách đầu tiên không trả giá nạp lạnh; quá `WARMUP_WAIT` giây (mặc định 300) thì mở tunnel luôn.
- `prod` dừng dịch vụ cũ trước khi bật bản mới: lệnh bị ngắt giữa chừng để prod tắt. Chạy tách khỏi terminal (`nohup ./run.sh prod > logs/run/deploy.log 2>&1 &`) và đọc dòng smoke ở cuối log.
- Biến môi trường: `SKIP_CLEF=1` không bật Clef tự host (Judge fail-open, guard quy tắc tắt); `HARNESS_GPU` (mặc định `0` trong `run.sh`) là GPU harness nạp embedder. Từ 09/11/2026 Clef chưa host (không đủ GPU), prod chạy `SKIP_CLEF=1`; từ 13/11/2026 chủ dự án chỉ còn GPU 0 cho harness nên prod chạy `HARNESS_GPU=0 SKIP_CLEF=1` (trước đó `HARNESS_GPU=2`); `PUBLIC_PORT` (28899); `TUNNEL_TOKEN_FILE` (mặc định `~/.cloudflared/tripguardian.token`, không có file thì không có tunnel). Danh sách đầy đủ: đầu `run.sh`.
- **Prod chạy từ bản đông cứng `.prod_src/`**, không phải `src/`: `prod` chép `src/` → `.prod_src.new/`, kiểm import, dừng dịch vụ cũ, đổi tên rồi khởi động harness + worker thông báo với `PYTHONPATH=.prod_src`. Trước khi đổi, `freeze_src` kiểm mọi `config/*.yaml` của các giai đoạn nạp được bằng bản chép (`scripts/config_check.py`) rồi ghi `.prod_src/RELEASE` (commit, số file `src/`/`config/` chưa commit, giờ đông cứng). Bản bị thay giữ lại ở `.prod_src.prev` cho `prod-rollback`; rollback chỉ đổi code, không đổi `web/dist`, `config/` hay database. Bản chép nằm cùng độ sâu với `src/` vì code tìm gốc repo bằng `Path(__file__).parents[N]`. Sửa `src/` (người hay agent, kể cả worker quá tải `spawn` nạp lại `planning` mỗi lượt) không vào prod tới lần deploy sau. Không sửa tay `.prod_src/`; nằm ngoài git.
- **Chỉ `src/` được đông cứng; `config/` và `data/` prod đọc thẳng từ repo.** Sửa một file `config/*.yaml` có hiệu lực ở lần nạp kế của prod (worker quá tải nạp lại mỗi lượt, các tiến trình khác lúc khởi động lại), không đợi deploy. Mọi loader đều từ chối khóa lạ (`Settings(**raw)`, pydantic `extra="forbid"`), nên một khóa YAML mà `.prod_src/` chưa biết làm prod lỗi khi nạp. Tham số mới: đặt default trong code, chỉ ghi vào YAML sau khi đã deploy bản code biết khóa đó. Kiểm trước và sau khi sửa config: `./run.sh prod-check` (nạp mọi file settings bằng code prod; venv cài `src/` dạng editable nên script báo lỗi nếu code không thật sự nạp từ `.prod_src/`).
- `web/server.mjs` chỉ phục vụ phần public: landing, `/app`, `/assets`, `/img`, `/data`, ảnh `/media` (jpg), thumbnail `/media/thumb` (WebP) và proxy `/api/harness/*`, `/api/auth/*` (keep-alive); `/admin`, analytics, mọi `/api` khác và video trả 404. Cần Postgres đang chạy (`./run.sh db`).
- Route hostname → cổng nằm trong dashboard Cloudflare của tunnel; `prod` in ra các route nhận được để thấy ngay khi token sai.
- Tiến trình chạy bằng `nohup`; tiến trình chết giữa chừng không tự lên lại. Sau khi máy khởi động lại, cron `@reboot` (§4) chạy lại `prod`.

**Tốc độ.** `web/scripts/make_thumbs.py` tạo WebP rộng ≤ 480 px cho mọi ảnh bìa vào `data/thumbs/<nguồn>/` (chỉ ảnh mới). `npm run build:prod` = `vite build` + `web/scripts/prod_assets.mjs`: `dist/data/snapshot.json` chỉ giữ trường User Web đọc (27 → 16 MB; `public/data` vẫn đủ cho dev/admin) và mọi file văn bản có bản `.br` / `.gz` (cache theo hash ở `web/node_modules/.cache/tg-prod`). `server.mjs` gửi bản nén client nhận, gắn `ETag`; `/data` cache 5 phút + revalidate, `/media` 7 ngày, `/assets` immutable.

**Đo sau deploy.** `PYTHONPATH=src .venv/bin/python scripts/prod_journey_e2e.py --jobs 4 --run-id <id>` chạy ma trận kịch bản người dùng thật qua đúng các call HTTP của web (`config/prod_journey_cases.yaml`), ghi `tables.md`.

## 2. Vị trí file trên gpu156

| Đường dẫn | Chứa gì |
|---|---|
| `/data/work/luanhh/local/tripguardian/` | repo: code, cộng `data/`, `logs/`, `.prod_src/` (đã gitignore) |
| `/data/work/luanhh/local/tripguardian-store/` | thứ không phải code: `venv` (`.venv` là symlink), `venv-vllm` (`.venv-vllm`), `cache` (`.cache`; `hf` → `hf-repo` là trọng số model, `uv` → `uv-repo`), `uv-python` (Python 3.12 của các venv), `hf` (model sinh ảnh / 3D), `imggen-venv`, `splat` (dữ liệu dựng 3D) |
| `/data/work/luanhh/local/docker/` | `data-root` của Docker rootless (Postgres, OSRM, SearXNG) |
| `/data/work/luanhh/nas/tripguardian/` | sao lưu NAS (§3) |
| `/workingspace_aiclub/WorkingSpace/Unsorted/luanhh/tripguardian` | symlink tới repo |

`/data/work/luanhh` là thư mục autofs của root: chỉ ghi được vào `local/` và `nas/`.

## 3. Sao lưu

| NAS (`/data/work/luanhh/nas/tripguardian/`) | Cách tạo |
|---|---|
| `pg-backup/` | `scripts/pg_backup_nas.sh` hằng đêm (§4): `pg_dump` nén, giữ 14 bản mới nhất, chỉ chủ sở hữu đọc được; đổi đích bằng `PG_BACKUP_DIR` |

Từ 14/11/2026 NAS **chỉ** giữ `pg-backup/`. Bản sao `data/` (267 GB, chủ yếu `tiktok/videos`) và `archive-20261109/` đã bị chủ dự án xóa để giữ hạn mức `/data/work` (NAS + local cộng chung 1000 GiB): `data/` hiện chỉ có một bản ở local. Không chép `data/` lên NAS lại khi chưa hỏi chủ dự án. Sau khi NAS bị xóa, cron 02:30 tự tạo lại `pg-backup/` (kiểm `logs/pg_backup_nas.log`).

`./run.sh db-backup` là bản dump tại chỗ vào `data/backup/pg/` (giữ 14), `prod` chạy nó trước khi migrate.

## 4. Cron

`crontab -e` của tài khoản chạy prod; giữ các job khác, mỗi job một nhãn để gỡ riêng:

```cron
@reboot sleep 120; cd /data/work/luanhh/local/tripguardian && SKIP_CLEF=1 HARNESS_GPU=1 PATH=$HOME/node/bin:/usr/local/bin:/usr/bin:/bin ./run.sh prod >> logs/run/reboot.log 2>&1 # tripguardian-reboot
* * * * * /usr/bin/python3 /data/work/luanhh/local/tripguardian/scripts/keepalive.py --base-url https://tripguardian.visioncare-host.uk >/dev/null 2>&1 # tripguardian-keepalive
*/10 * * * * /data/work/luanhh/local/tripguardian/scripts/disk_guard.sh # tripguardian-disk-guard
30 2 * * * /data/work/luanhh/local/tripguardian/scripts/pg_backup_nas.sh # tripguardian-pg-backup
15 3 * * * cd /data/work/luanhh/local/tripguardian && ./run.sh prewarm >> logs/prewarm_transit.log 2>&1
0 4 * * * /data/work/luanhh/local/tripguardian/scripts/trends_daily.sh dalat # tripguardian-trends
```

- `@reboot`: Docker rootless tự lên (linger bật); 120 giây sau chạy lại toàn bộ `prod`, log `logs/run/reboot.log`. `SKIP_CLEF=1` vì GPU dùng chung với người khác; muốn Clef tự lên sau reboot thì bỏ biến này.
- `keepalive.py` (§5): ping đường public mỗi phút.
- `disk_guard.sh`: ổ chứa Docker data-root còn dưới 5 GiB thì ghi `logs/disk_guard.log` và chạy `CHECKPOINT` trên Postgres.
- `pg_backup_nas.sh`: §3, log `logs/pg_backup_nas.log`.
- `prewarm` (`scripts/prewarm_transit.py`): tra trước xe khách cho các tuần tới vào cache `data/live/vexere/` (phạm vi `config/live.yaml` `transit_prewarm`; một nguồn lỗi 8 lần liền thì dừng nguồn đó). Chuyến bay không cache (`flight_cache: false`): mỗi câu hỏi mở Google Flights trực tiếp. Máy không có Chrome thì `run.sh` trỏ Playwright vào Chromium trong `.cache/ms-playwright`.
- `trends_daily.sh`: crawl đêm cho Nhịp Đà Lạt rồi dựng bản tin (`docs/CORPUS.md` §Nhịp Đà Lạt, §Sự kiện sắp tới): `corpus events` (sự kiện tháng này và tháng sau từ web, Extractor trên endpoint Judge / UIT), `corpus tiktok poi_refresh` (`poi_refresh_per_run` = 200 trang nơi TikTok, không đăng nhập, không tải video), rồi `pulse_daily.sh --once`. Bước lỗi được ghi và bước sau vẫn chạy; khóa `logs/trends_daily.lock` tránh chạy chồng; log `logs/trends_daily.log` (bản tin: `logs/pulse_daily.log`). Thay dòng `tripguardian-pulse` cũ (chỉ tính lại bản tin, không crawl). Bản tin cũ quá `stale_after_days` thì web báo chưa được làm mới.

## 5. Kiểm tra sức khỏe

`scripts/keepalive.py` (Python 3 chuẩn + `curl`) GET `/app` và `/api/harness/me` qua domain public. Không gửi cookie, không tạo tài khoản/journey, không gọi model; query riêng mỗi lượt để không trúng cache. Đạt khi `/app` trả 200 có app shell và API trả đúng 401 `{"error":"sign in first"}`: chỉ kiểm đường HTTP tới backend, không kiểm DB, model hay cả hành trình.

```sh
python3 scripts/keepalive.py --base-url https://tripguardian.visioncare-host.uk
tail -n 5 logs/run/keepalive.log
```

Mỗi request giới hạn 15 giây; khóa file tránh chạy chồng. Log ghi giờ UTC, HTTP status, độ trễ, `ok`, xoay vòng khoảng 3 MiB (`keepalive.log`, `.1`, `.2`); exit code 1 khi lỗi. Ping không khởi động lại tiến trình và chưa gửi cảnh báo ra ngoài; `prod-stop` không gỡ cron nên khi stack dừng, ping ghi lỗi.

## 6. Sự cố thường gặp

| Dấu hiệu | Xem trước |
|---|---|
| `:5433` từ chối kết nối, harness báo `PoolTimeout` | `df -h /data/work/luanhh/local`, `docker logs --tail 30 tripguardian-pg`, `logs/disk_guard.log` |
| Sau reboot, `docker start tripguardian-pg` báo `error evaluating symlinks from mount source "/home/.../docker/volumes/..."`; `reboot.log` dừng ở `migrate FAILED` | Container lưu đường dẫn mount cũ từ trước khi đổi data-root. Dữ liệu nằm trong volume `tripguardian-pgdata`: `docker rm tripguardian-pg` (không `-v`), rồi `./run.sh db` tạo lại trên cùng volume, rồi chạy lại `prod` |
| Prod tắt sau một lần deploy | `prod` bị ngắt giữa chừng (§1): chạy lại tách khỏi terminal |
| Web báo bản tin Nhịp chưa làm mới | `logs/pulse_daily.log`, dòng `tripguardian-pulse` trong `crontab -l` |
