# Thiết lập, chạy và test

Hướng dẫn đầy đủ cho máy phát triển. Bản rút gọn để chạy thử nằm ở `README.md` §Thiết lập nhanh. Production trên gpu156: `docs/OPERATIONS.md`.

## 1. Cần cài trước

| Thứ | Phiên bản | Dùng cho |
|---|---|---|
| Python | ≥ 3.12 | toàn bộ backend |
| Node | ≥ 20.19 (đang dùng 24) | `web/` |
| Docker | bất kỳ | Postgres, OSRM, SearXNG |
| Google Chrome bản thường | mới nhất | Playwright mở Chrome qua `channel="chrome"` khi crawl |
| Git Bash | chỉ Windows | `run.sh` là shell script, dùng `netstat` / `taskkill` |
| ffmpeg, GPU | chỉ khi crawl | ASR video TikTok |

```sh
git clone https://github.com/hohoangluan/tripguardian && cd tripguardian
python -m venv .venv && source .venv/bin/activate      # Windows: .venv/Scripts/activate
pip install -e ".[dev]"                                # thêm .[asr] khi chạy ASR; chunkformer: pip install --no-deps
python -m playwright install chromium                   # browser headless cho test parser và crawl
cd web && npm install && cd ..
cp .env.example .env                                    # điền key: docs/LLM_PROVIDER.md
```

## 2. Từng phần

**Dữ liệu.** Dữ liệu không nằm trong git. Tải `tripguardian-data-<ngày>.zip` mới nhất từ [Drive của nhóm](https://drive.google.com/drive/folders/1LeEgIdoioyCAM64WV3VLGeKYA-X5yEGT?usp=sharing), giải nén tại gốc repo:

```sh
python -m zipfile -e tripguardian-data-<ngày>.zip .
```

Gói trả về `data/`, `web/public/data/snapshot.json` (dữ liệu web hiển thị) và `tests/fixtures/{gmaps,tiktok}` (trang crawl thật cho test parser). Các file này chứa review và tài khoản người thật nên không vào repo public. Gói không có `video.mp4` của TikTok (chỉ ASR cần). Bản `--no-photos` không có ảnh Maps, khi đó `/admin/labels` không hiện ảnh.

**Key model.** Trip Understanding, chọn câu hỏi và mọi phase cần model gọi API UIT, chỉ trả lời trong mạng campus. Key và endpoint ở `.env`. Lỗi chứng chỉ `llm.uit.edu.vn`: tạo CA bundle một lần mỗi máy (`docs/LLM_PROVIDER.md` §Chứng chỉ TLS).

**OSRM** (thời gian di chuyển cho Planning). Chạy `bash scripts/osrm_setup.sh` một lần mỗi máy: tải OSM Việt Nam, dựng chỉ mục vào `osrm-data/`, mở `127.0.0.1:5000`. Lần sau chỉ chạy lại container (dòng `docker run ... -p 127.0.0.1:5000:5000` cuối script). Không có OSRM thì Planning ước lượng thô và gắn cảnh báo. Endpoint và TTL ở `config/live.yaml`; `LIVE_CONTACT` trong `.env` là liên hệ gửi kèm request.

**Postgres** (tài khoản, hành trình, event, thông báo). Điền `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_URL_READONLY` trong `.env`, rồi `./run.sh db`: tạo container `tripguardian-pg` ở `127.0.0.1:5433`, role, database và chạy migration (chạy lại an toàn). `./run.sh db-backup` sao lưu vào `data/backup/pg/`.
- Quên mật khẩu qua thư: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` (`docs/ACCOUNTS.md` §2c).
- Đăng nhập Google, Calendar, web push: `APP_BASE_URL`, `GOOGLE_*`, `TOKEN_ENC_KEY`, `VAPID_*` (`.env.example`, `docs/ACCOUNTS.md`).
- Nhập hành trình cũ dạng file: `python -m harness import-files data/harness/sessions data/harness/feedback.jsonl`.

**Agent endpoint và web search.** `AGENT_BASE_URL` trỏ `127.0.0.1:<cổng>` thì `./run.sh start` tự bật 9router (cần `npm i -g 9router`; không có thì Agent trả lời theo policy dự phòng). `./run.sh prod` bật thêm SearXNG (`127.0.0.1:8888`, Docker; `docker/searxng/README.md`) cho tool `web_search` của Trip agent. `web_base_url` trống ở `config/trip.yaml` thì agent không có tool web.

**Chỉ mục ngữ nghĩa** (ảnh / câu → "vibe", "chỗ như này"). Có sẵn trong gói dữ liệu ở `data/index/`. Harness nạp embedder trên GPU `HARNESS_GPU` (mặc định `0`). Dựng lại: `python -m corpus index` (`docs/CORPUS.md` §Chỉ mục ngữ nghĩa).

**Chỉ khi crawl.** Đăng nhập tài khoản phụ một lần mỗi máy: `python -m corpus login tiktok`, `python -m corpus login gmaps` (profile ở `.browser/`, đã gitignore). Chạy dịch vụ và Planning lodging không cần đăng nhập.

**Đóng gói dữ liệu mới** (người giữ dữ liệu): `python scripts/pack_data.py [--no-photos] [--out <thư mục>]` rồi đưa zip lên Drive. Cái gì bị bỏ và vì sao: docstring của script. Sửa `data/` xong mà web cần thấy: `python web/scripts/export_snapshot.py` trước khi đóng gói.

## 3. Chạy

```sh
./run.sh start   # 9router + harness + analytics + review + web dev + worker thông báo; in URL khi mọi cổng đã trả lời
./run.sh stop    # dừng mọi tiến trình script này khởi động
```

| Dịch vụ | Cổng | Lệnh tương đương |
|---|---|---|
| Web (Vite) | 5173 | `/` landing · `/app` · `/admin` |
| Agent harness (Trip, Decision, Planning) | 8769 | `python -m harness serve` |
| Analytics (private) | 8770 | `python -m analytics serve --port 8770` |
| Trang review / gán nhãn | 8765 | `python -m corpus review` |
| 9router (endpoint của Agent) | theo `AGENT_BASE_URL` | `9router` |
| SearXNG (`web_search`, chỉ prod) | 8888 | container `tripguardian-searxng` |

Log ở `logs/run/<tên>.log`. Production: `./run.sh prod`, `./run.sh prod-stop`; prod chạy từ bản đông cứng `.prod_src/`, sửa `src/` không vào prod tới lần deploy sau (`docs/OPERATIONS.md`).

CLI/API từng module chạy riêng khi cần: `python -m trip serve` (:8766), `python -m decision serve` (:8767), `python -m planning serve` (:8768). User Web dùng harness và journey chung; contract ở `docs/AGENT_HARNESS.md`.

**Client thử Trip (Streamlit).** Kiểm riêng Trip Understanding qua đúng Harness HTTP/SSE, không thay User Web:

```sh
python -m harness serve
streamlit run scripts/trip_tester.py     # mặc định nối http://127.0.0.1:8769, đổi ở sidebar
```

**Chụp toàn luồng User Web** với harness thật (Khám phá → Chọn nơi → Lịch trình → Phản hồi) vào `web/shots/app/`: `node web/scripts/shots_app.mjs [http://127.0.0.1:5173]`. Script dùng Chromium đầy đủ trong `.cache/ms-playwright/chromium-1169` (bản headless shell treo trên server dùng chung); `playwright-core` của web ghim 1.52.0 để khớp.

**Dữ liệu web.** Web đọc địa điểm từ `web/public/data/snapshot.json`; sinh lại bằng `python web/scripts/export_snapshot.py` sau khi aggregate. Gallery mỗi nơi (≤ 12 ảnh, ảnh đầu là ảnh bìa) ở `web/public/data/covers.json`, sinh bằng `python web/scripts/pick_covers.py`: YOLO loại ảnh có người chiếm khung, pHash bỏ ảnh gần trùng, Gemma (task `photo_rank`, cache `.cache/photo_rank.json`) chấm độ đẹp. Chạy GPU + host LAN vài giờ; `--resume` chạy tiếp, `--dry-run --ids a,b` in thứ hạng. Xong thì chạy `make_thumbs.py`.

## 4. Xây dữ liệu từng bước

Lệnh đầy đủ của từng giai đoạn nằm trong tài liệu giai đoạn đó. Đường chính:

```sh
# 1. Place Intelligence (docs/CORPUS.md §CLI)
python -m corpus gmaps all --city dalat --headed     # search → filter → counts → list → crawl → qc → observe
python -m corpus gmaps photos && python -m corpus gmaps photo_observe
python -m corpus tiktok all --city dalat --headed
python -m corpus aggregate && python -m corpus serving   # serving cũng biên dịch snapshot cho phần online
python -m corpus snapshot                            # chỉ biên dịch lại snapshot từ data/serving/places.json
python -m corpus views all --city dalat              # khí hậu, lịch, vùng hạn chế → data/dalat/views/
python -m corpus pulse --city dalat                  # bản tin xu hướng → data/dalat/pulse/ (cron: docs/OPERATIONS.md §4)
python -m corpus index                               # chỉ mục ngữ nghĩa → data/index/
python -m corpus normalize --rebuild --publish --city dalat  # dựng release từ dữ liệu đã lưu, kiểm rồi chuyển pointer
python web/scripts/export_snapshot.py --view both    # snapshot cho User Web và Admin

# 2. Corpus đã đủ cho Place Decision chưa (docs/PLACE_DECISION.md §17)
python -m decision evaluate                          # 30 Trip State ẩn → data/decision/eval.json

# 3. Lập lịch từ một Decision Output (docs/PLANNING.md §CLI và API)
python -m planning build    <decision_output.json>
python -m planning variants <decision_output.json> [--weather forecast.json]
python -m planning lodging  <decision_output.json>
python -m planning evaluate                          # 30 chuyến ẩn qua Decision → Planning (cần OSRM)

python -m bench latency --scale 1,5,20               # độ trễ phần dùng corpus → data/bench/latency/
```

Phase cần model cần mạng UIT; gặp captcha thì giải trong cửa sổ trình duyệt (`--headed`). `normalize` không có `--rebuild` chỉ báo membership / source / schema; `--rebuild` không `--publish` dựng release staging, không đổi pointer.

Journey giữ corpus binding qua Trip → Decision → Planning và restore / copy; đổi release pointer không chuyển journey đã pin. Muốn deployment nhận release mặc định mới thì restart toàn harness. Contract và rollback: `docs/CORPUS.md` §Chuẩn hóa và release offline.

## 5. Test

```sh
python -m pytest -q                      # không gọi mạng; thiếu gói Drive thì test parser Maps/TikTok tự skip
python -m pytest -q tests/planning       # một giai đoạn
python scripts/journey_sim.py [--monkey N]   # mô phỏng người dùng đi hết Trip → Decision → Planning trên dữ liệu thật, không gọi model
```

`journey_sim.py` ghi báo cáo ở `data/journey_sim/report.json`; `--agent` chạy 5 kịch bản gõ chữ qua Gemma trên UIT (từ chối chạy nếu `AGENT_BASE_URL` không phải UIT) và in thời gian từng lượt.

| Marker | Cần gì | Thiếu thì |
|---|---|---|
| `live` | model thật | bị `addopts` loại khỏi lần chạy mặc định (`pyproject.toml`) |
| `pg` | `TEST_DATABASE_URL=<DATABASE_URL>`, mỗi test một schema tạm | tự skip |
| `corpus` | `data/snapshot/current` (`python -m corpus snapshot`) | tự skip |

**Đo matrix local từ `src/`** (cần Postgres, `bwrap`, `.env`, model gateway; không deploy / build): `scripts/local_stack.sh start | status | stop`. Mặc định web `127.0.0.1:28919` → harness `:8879`; đổi bằng `LOCAL_WEB_PORT` / `LOCAL_HARNESS_PORT`. Smoke một ca:

```sh
PROD_JOURNEY_BASE=http://127.0.0.1:28919 .venv/bin/python scripts/prod_journey_e2e.py --only solo_f_cafe_photo --jobs 4 --run-id local-smoke
```

Stack local dùng DB schema riêng, config CPU overlay, cache / log / PID riêng; corpus và `web/dist` chỉ đọc, không chạy worker thông báo. `stop` giữ schema và bằng chứng. Số đo CPU không so trực tiếp với GPU prod. Không chạy cả matrix trên gateway dùng chung khi chưa được phép.

**Web** (CI không chạy): `cd web && npm run build` (có `tsc -b`). Test Node ở `web/scripts/test_*.mjs`, chạy `node --test web/scripts/<file>`:
- chạy được ngay: `test_server_security.mjs` (proxy public), `test_planning_state.mjs`;
- mở Chromium với fixture riêng: `test_overload_ui.mjs` (do `tests/harness/test_overload_browser.py` dựng);
- `test_journey.mjs` cần `journey.ts` biên dịch trước (`JOURNEY_JS`).

## 6. Đóng góp code

- Mỗi task một branch từ `main` (`feat/<giai-đoạn>-<việc>`, `fix/...`), mở PR vào `main`; không push thẳng `main`.
- Trước khi mở PR: `python -m pytest -q` xanh. CI (`.github/workflows/test.yml`) chạy đúng lệnh này.
- Theo `RULE.md`: tài liệu tiếng Việt, code tiếng Anh, chỉ gọi module khác qua `__init__.py`, đổi hành vi thì sửa tài liệu của giai đoạn đó.
- Không commit `.env`, `data/`, `.browser/`, `logs/`, `snapshot.json`, `tests/fixtures/{gmaps,tiktok}` (đã gitignore). Repo public: không đưa nội dung crawl (review, bình luận, tên tài khoản người thật) vào git.
