# Thiết kế: vận hành TripGuardian cho đồ án NT548 (nhóm 8)

> Spec làm việc (`RULE.md` §0.1). Trạng thái: **chờ chủ dự án duyệt**. Ngày 2026-11-20.
> Repo: fork `LuanLuKim/tripguardian-nt548` (public) của `hohoangluan/tripguardian`.

## 1. Mục đích

Đồ án NT548 (DevOps) lấy TripGuardian làm sản phẩm và xây **phần vận hành** quanh nó: CI/CD bằng GitHub Actions; triển khai có load balancer, phân luồng traffic, blue/green để update và rollback; scale cơ bản; AI ops và DataOps ở mức đồ án. Bốn thành viên cùng làm trên fork.

Chủ dự án chốt (20/11):
- Chỉ làm trên nền TripGuardian. Phần chức năng **giữ y như upstream**; chỉ phần vận hành là riêng của NT548, vì mỗi môn chấm một đồ án khác.
- Không dùng Kubernetes để chạy hệ thống thật (quota cloud không chắc), dùng Cloudflare. Kubernetes chỉ là bản demo chạy trong CI để lấy điểm cộng.
- Bản NT548 chạy riêng cạnh prod trên gpu156, **dùng chung venv và mọi tài nguyên dùng chung được** để tiết kiệm.

## 2. Mục tiêu, không làm, thất bại

| | |
|---|---|
| Mục tiêu | (1) PR nào cũng qua CI xanh trên runner của GitHub. (2) Push `main` → tự deploy lên gpu156 bằng blue/green, có canary chia luồng, rollback một lệnh trong < 1 phút. (3) Scale được harness / web lên N bản sau load balancer, có số đo trước / sau. (4) AI ops: chia luồng theo trọng số giữa các bản model, chặn deploy bằng eval. (5) DataOps: kiểm một corpus release trước khi bản NT548 phục vụ nó; đổi / lùi release dữ liệu như đổi code. (6) Demo Kubernetes (`kind`) trong CI cho cùng ý tưởng blue/green. |
| Không làm | Không đổi hành vi sản phẩm. Không chạy Kubernetes trên gpu156 hay cloud. Không mua Cloudflare Load Balancing (trả phí). Không chép `data/` (274 GB). Không thay prod: prod TripGuardian vẫn chạy bằng `./run.sh prod`. |
| Coi là thất bại dù chạy được | Prod TripGuardian bị chậm, chết, mất dữ liệu, hay bị ghi vào `data/` vì bản NT548. Secret (token, `.env`) lên repo public. Code từ PR của người lạ chạy được trên gpu156. Fork lệch chức năng so với upstream tới mức không merge lại được. |

## 3. Ràng buộc đã biết

| Ràng buộc | Bằng chứng | Hệ quả cho thiết kế |
|---|---|---|
| gpu156 dùng chung, user `luanhh`, không root | `id`; `docs/OPERATIONS.md` §2 | systemd `--user`, Docker sẵn có, `bwrap` có ở `/usr/bin/bwrap` |
| Prod giữ cổng 8769, 28899, Postgres 5433, SearXNG 8888; `local_stack.sh` giữ 8879/28919 | `run.sh`, `scripts/local_stack.sh` | NT548 dùng dải 187xx / 388xx (đã kiểm còn trống 20/11) |
| Phiên Planning sống trong RAM của harness | `src/planning/session.py:348` (`Store._mem`); `docs/PLANNING.md` §cuối: restart dựng lại từ Postgres | Load balancer phải **sticky** theo người dùng; chuyển màu thì bản mới tự dựng phiên từ Postgres |
| Người dùng mang cookie `tg_session` | `src/harness/server.py:58` | Sticky bằng `hash $cookie_tg_session consistent` |
| Harness warm ~2 phút, chưa có `/healthz` / `/readyz` | `docs/OPERATIONS.md` §1; grep `server.py` | Chưa có endpoint thì chờ dòng `Journey warmup:` trong log; endpoint thật làm ở upstream (§9) |
| Mỗi harness nạp embedder ~2,4 GiB GPU; `online_device: cpu` chạy được, chậm hơn | `config/index.yaml:6` | Mỗi màu 1 harness trên GPU; bản thứ 2 trở đi hoặc bản trong CI chạy CPU |
| Hai màu dùng chung một database | blue/green | Migration phải tương thích ngược (thêm cột / bảng trước, bỏ sau ít nhất một lần deploy) |
| Repo public | GitHub | Self-hosted runner chỉ nhận `push main` và `workflow_dispatch`, có environment cần duyệt |
| `pyproject.toml` thiếu `trafilatura`, `cryptography`, `fastapi` | CI run `44738562042`: 158 file test lỗi import, 0 test chạy | Sửa ở nhiệm vụ đầu (§8, T1) |
| Push lên fork không tự tạo run; `workflow_dispatch` qua API thì có | 20/11 | Kiểm lại sau khi bấm bật Actions trên giao diện fork |

## 4. Các hướng đã cân nhắc

| Hướng | Được | Mất | Chọn? |
|---|---|---|---|
| A. Chỉ chạy trên gpu156 bằng script, không Compose | Ít công, dữ liệu thật | Không kiểm được trong CI, người không có quyền vào gpu156 không thử được | Không |
| B. Kubernetes trên cloud | Đúng giáo trình | Dữ liệu 274 GB + GPU không lên được, tốn quota, khó hiểu | Không (chủ dự án loại) |
| **C. Nginx + quy trình blue/green dùng chung cho CI và gpu156** | Diễn tập đủ chuỗi deploy → canary → rollback trong CI với dữ liệu mẫu; deploy thật trên gpu156; ai cũng thử được bằng Docker Compose ở máy mình | Hai môi trường (CI và gpu156) phải giữ cùng một cấu hình Nginx và cùng script | **Chọn** (chủ dự án 20/11) |
| + K8s `kind` trong CI | Điểm cộng, không tốn quota | Thêm một bộ manifest | Làm sau cùng, bỏ được |

Làm trực tiếp trên prod TripGuardian bị loại: prod có người dùng thật, cây làm việc dùng chung nhiều phiên, và đồ án cần lịch sử commit / PR của bốn thành viên.

## 5. Kiến trúc

### 5.1 Trên gpu156

```text
Internet ─► Cloudflare tunnel "nt548" (hostname riêng, gói free)
              │
              ▼
        nginx  :38800  (container, network host)  ── access log JSON: color, upstream, status, ms
          │  /api/harness/*, /api/auth/*  ── split_clients theo cookie → màu; hash $cookie_tg_session → bản
          │  phần còn lại (landing, /app, /assets, /data, /media)
          ▼
   ┌──────────── blue ─────────────┐   ┌──────────── green ────────────┐
   │ web    :38801 (server.mjs)    │   │ web    :38811                 │
   │ harness:18701 (GPU) 18702 (CPU)│  │ harness:18711 (GPU) 18712 (CPU)│
   │ release: releases/<sha-A>     │   │ release: releases/<sha-B>     │
   └───────────────────────────────┘   └───────────────────────────────┘
              │ dùng chung, chỉ đọc                       │
              ▼                                           ▼
  venv · uv-python · HF cache (tripguardian-store) · data/ prod (ro-bind) · OSRM · SearXNG · 9router / model gateway
  Postgres prod :5433 → schema riêng `nt548` (cả hai màu cùng schema)
  Ghi riêng: tripguardian-store/nt548/{releases, work/<color>, logs, state}
```

- **Cô lập** theo đúng cách `scripts/local_stack.sh` đã làm: `bwrap` ro-bind `data/` của prod, thư mục ghi riêng cho mỗi màu, schema Postgres riêng, từ chối cổng prod. Script NT548 tái dùng logic đó, không viết lại.
- **Release** = cây của một commit (`git worktree` / `git archive`) + `web/dist` đã build + `RELEASE.json` (sha, thời điểm, corpus release đang ghim, kết quả CI). Đặt ở `tripguardian-store/nt548/releases/<ngày>-<sha>/`, giữ 5 bản gần nhất.
- **Tiến trình** chạy bằng unit `systemd --user` mẫu `nt548-harness@<color>-<n>`, `nt548-web@<color>`, `Restart=on-failure`. Nginx và tunnel là unit riêng.
- **Web** của mỗi màu proxy tới harness của chính màu đó (`HARNESS_PORT`). Khi một màu có hơn một harness, Nginx gửi thẳng `/api/harness/*` tới nhóm harness của màu đó, sticky theo `tg_session`.

### 5.2 Quy trình deploy (blue/green + canary)

```text
push main ─► CI (GitHub runner) xanh ─► job deploy (self-hosted runner gpu156, environment "nt548" cần duyệt)
   1. release.sh <sha>       dựng release, kiểm config (scripts/config_check.py), kiểm import
   2. migrate                chỉ migration tương thích ngược; sao lưu schema nt548 trước
   3. start <idle color>     bật harness + web của màu rảnh trên release mới
   4. wait-ready             /readyz (hoặc dòng warmup) ≤ 300 s, rồi smoke trực tiếp vào cổng màu đó
   5. canary 10%             đổi trọng số split_clients, nginx -s reload (không rớt kết nối)
   6. watch 10 phút          từ access log: tỷ lệ 5xx và p95 của màu mới so với màu cũ
   7. promote 100% | rollback 0%
   8. giữ màu cũ chạy 30 phút (rollback tức thì), sau đó dừng
```

- `ops/nt548/deploy.sh {release|start|stop|weight <blue%>|promote|rollback|status}`; trạng thái (màu nào, release nào, trọng số) ở `tripguardian-store/nt548/state/active.json`.
- **Rollback** = trọng số về màu cũ + reload Nginx: < 1 phút, không cần build. Workflow `nt548-rollback.yml` (`workflow_dispatch`) gọi đúng lệnh này.
- Ngưỡng tự rollback ở bước 6 (mặc định, chỉnh trong `ops/nt548/canary.yaml`): 5xx của màu mới > 2 % và > 2× màu cũ, hoặc p95 > 1,5× màu cũ, trên tối thiểu 50 request; ít request hơn thì chạy thêm `prod_journey_e2e.py` (tập con) vào màu mới để có đủ mẫu.
- Người dùng giữ màu theo cookie trong lúc canary: một người không nhảy qua lại giữa hai bản.

### 5.3 Trong CI (GitHub runner)

| Workflow | Khi chạy | Việc |
|---|---|---|
| `test.yml` (có sẵn, của upstream) | PR, push `main` | pytest + build web. Không sửa ngoài `workflow_dispatch` |
| `nt548-ci.yml` | PR, push `main` | ruff (lỗi thật), kiểm `docker compose config`, `nginx -t`, test của script `ops/nt548/` |
| `nt548-bluegreen-rehearsal.yml` | PR chạm `ops/`, push `main` | Docker Compose dựng Nginx + 2 màu với **dữ liệu mẫu** (`tests/fixtures` + snapshot nhỏ), harness `online_device: cpu`; chạy đủ chuỗi §5.2 bước 3–7 cộng rollback; kiểm không request nào rớt trong lúc đổi (k6 hoặc vòng `curl`) |
| `nt548-deploy.yml` | push `main` sau khi hai job trên xanh | job trên self-hosted runner gpu156, cần duyệt ở environment `nt548` |
| `nt548-rollback.yml` | tay | rollback |
| `nt548-k8s-demo.yml` | tay + hằng tuần | `kind`: Deployment `web`, `harness-blue`, `harness-green`, Service đổi `selector`; `kubectl scale`; kiểm đổi / lùi màu |
| `nt548-upstream-sync.yml` | hằng ngày | fetch `hohoangluan/tripguardian` `main`; nếu mới thì mở PR "sync upstream" vào fork để CI chạy trên đó |

### 5.4 Scale cơ bản

- Web không giữ trạng thái: thêm bản = thêm cổng trong upstream Nginx.
- Harness: thêm bản CPU (`online_device: cpu`) vào nhóm của màu; sticky giữ phiên đúng bản. Bản mới không có phiên trong RAM sẽ dựng lại từ Postgres khi người dùng tới (cơ chế có sẵn).
- Đo: `scripts/journey_sim.py` / `scripts/prod_journey_e2e.py --jobs N` vào cổng Nginx với 1 bản và 2 bản harness; ghi bảng p50 / p95 / lỗi vào báo cáo NT548.

### 5.5 AI ops

- **Phân luồng model:** `scripts/model_gateway.py` đã cân bằng tải (ít request đang chờ nhất) và bỏ qua upstream lỗi. Thêm trọng số cho từng upstream (`--gemma-url URL@weight`) để canary một bản model / server mới (ví dụ vLLM bản mới 10 %). Ghi theo upstream: số request, lỗi, độ trễ. Đây là thay đổi ở `scripts/`, có ích cho cả sản phẩm → đề xuất PR lên upstream sau khi chạy ổn (§9).
- **Chặn deploy bằng eval:** bước trong `nt548-deploy.yml`, chạy trước bước canary: tập nhỏ cố định của bench có sẵn (`tests/bench`, `config/prod_journey_cases.yaml`) vào màu mới; thấp hơn ngưỡng thì không chuyển traffic. Chỉ chạy trên gpu156 (cần model thật), không chạy trên PR.
- **Phiên bản prompt / model / config** theo vai trò ghi vào `RELEASE.json` (đọc từ config và `docs/LLM_PROVIDER.md`), để mỗi lần rollback biết đang lùi về model nào.

### 5.6 DataOps

- Corpus đã có release bất biến `data/releases/r-*` + con trỏ `current`; journey ghim release (`docs/ARCHITECTURE.md`). NT548 **không ghi** vào đó.
- Bản NT548 có con trỏ release riêng (`tripguardian-store/nt548/state/corpus_release`) trỏ vào một `r-*` của prod. Đổi release dữ liệu = đổi con trỏ đó qua cùng quy trình blue/green (màu rảnh khởi động với release mới).
- `ops/nt548/data_check.py <release>`: kiểm trước khi trỏ vào (schema của các file serving / snapshot, số nơi không giảm quá ngưỡng, không nơi nào thiếu trường bắt buộc, chỉ mục tồn tại). Đỏ thì không đổi.
- Workflow `nt548-data-release.yml` (`workflow_dispatch` + hằng đêm sau cron corpus của prod): phát hiện `r-*` mới → `data_check` → deploy màu rảnh với release đó → canary như code.

## 6. Bố cục file

```text
ops/                       thư mục mới ở gốc: khớp bố cục đích của TripGuardian (production-restructure §3)
  nt548/
    deploy.sh              release / start / stop / weight / promote / rollback / status
    canary.yaml            ngưỡng canary
    canary_watch.py        đọc access log Nginx → quyết promote / rollback
    data_check.py          kiểm corpus release
    nginx/                 nginx.conf.tmpl (split_clients, hash sticky, log JSON)
    systemd/               unit mẫu nt548-harness@, nt548-web@, nt548-nginx, nt548-tunnel
    compose/               docker-compose.yml + Dockerfile cho bản diễn tập (CI, máy cá nhân)
    runner/                hướng dẫn + script đăng ký self-hosted runner
  k8s/                     manifest demo kind
.github/workflows/nt548-*.yml
tests/ops/                 test cho script ops/nt548 (không cần GPU / dữ liệu)
docs/NT548.md              tài liệu chính thức của phần vận hành NT548: kiến trúc, lệnh, cách kiểm thử (liệt kê trong README.md)
docs/reports/              báo cáo đo (scale, canary, rollback) theo ngày
```

Quy ước để không lệch upstream: chỉ thêm file mới; file của upstream chỉ được sửa qua PR lên upstream (§9). Ngoại lệ duy nhất hiện có: `workflow_dispatch` trong `test.yml`.

## 7. Bảo mật

- Self-hosted runner chạy dưới `luanhh` và đọc được dữ liệu prod → chỉ job trong `nt548-deploy.yml`, `nt548-rollback.yml`, `nt548-data-release.yml` được dùng nhãn `gpu156-nt548`; các workflow này chỉ có trigger `push: main` / `workflow_dispatch` / `schedule`, environment `nt548` cần LuanLuKim duyệt. Bật "Require approval for all external contributors" cho fork. Bảo vệ nhánh `main`: cần PR + 1 review + CI xanh.
- Secret (token tunnel, `.env`) chỉ nằm trên gpu156 (`tripguardian-store/nt548/secrets/`, quyền 600) hoặc GitHub Environment secrets; không bao giờ trong repo.
- Runner không có quyền ghi vào thư mục prod: ghi chỉ qua `bwrap` vào `tripguardian-store/nt548/`.

## 8. Chia việc (4 người)

Nguyên tắc: mỗi người giữ một mảng từ đầu đến cuối (code + test + phần tài liệu của mảng đó), làm qua PR, một người khác review. Việc cần vào gpu156 dồn cho người có quyền vào máy.

| Mã | Việc | Người | Cần gpu156 | Phụ thuộc |
|---|---|---|---|---|
| T1 | CI xanh: sửa dependency thiếu (PR lên upstream), test ASR tự skip, tách marker test chậm, `nt548-ci.yml`, bảo vệ nhánh | LuanLuKim | không | — |
| T2 | Nginx: template `split_clients` + sticky + log JSON; Compose diễn tập; `nt548-bluegreen-rehearsal.yml`; kiểm không rớt request | Đình Long (dinhlong06) | không | T1 |
| T3 | `deploy.sh` (release, start/stop, weight, promote, rollback), unit systemd, self-hosted runner, tunnel NT548, `nt548-deploy.yml` / `nt548-rollback.yml` | LuanLuKim | **có** | T2 |
| T4 | `canary_watch.py` + `canary.yaml`; đo scale 1 → 2 harness; báo cáo đo | Quỳnh (DontMadWhenBad) | không (chạy trên Compose), số đo thật cần T3 | T2 |
| T5 | AI ops: trọng số trong `model_gateway.py`, chặn deploy bằng eval, ghi phiên bản model vào `RELEASE.json` | hohoangluan | **có** (model thật) | T3 |
| T6 | DataOps: `data_check.py`, con trỏ release riêng, `nt548-data-release.yml` | hohoangluan | **có** | T3 |
| T7 | Demo K8s `kind` + `nt548-k8s-demo.yml` | Quỳnh | không | T2 |
| T8 | `nt548-upstream-sync.yml`; `docs/NT548.md`; slide / báo cáo cuối | Đình Long (tài liệu chung cả nhóm góp) | không | T1–T7 |

Thứ tự: T1 → T2 → (T3 ∥ T4 ∥ T7) → (T5 ∥ T6) → T8. Đường găng: T1 → T2 → T3.

## 9. Phần đưa về TripGuardian (upstream)

Theo nguyên tắc "chức năng giữ y upstream", các thay đổi sau làm thành PR từ fork vào `hohoangluan/tripguardian`, không giữ riêng trên fork:
- Thêm dependency thiếu vào `pyproject.toml` + `uv.lock` (T1).
- `/healthz`, `/readyz` cho harness (khớp GĐ2 của `production-restructure`). Chưa có thì `deploy.sh` chờ dòng warmup trong log.
- Trọng số trong `model_gateway.py` (T5), sau khi chạy ổn trên NT548.

## 10. Tiêu chí xong (demo cho đồ án)

1. Mở PR có lỗi test → CI đỏ, không merge được; sửa → xanh.
2. Merge → deploy tự chạy tới bước canary 10 %; trang `status` hiện hai màu, trọng số, release.
3. Cố ý deploy một bản trả 500 → `canary_watch` tự rollback, người dùng đang ở màu cũ không thấy lỗi.
4. `nt548-rollback` bằng tay: < 1 phút.
5. Bảng đo 1 vs 2 harness.
6. Đổi corpus release qua blue/green; `data_check` chặn một release hỏng (tạo giả trong CI).
7. Canary 10 % cho một upstream model trong gateway, số liệu theo upstream.
8. `kind`: đổi selector blue → green → blue trong CI.
9. Prod TripGuardian không bị ảnh hưởng: so `prod-check` và tải máy trước / sau.

## 11. Rủi ro

| Rủi ro | Chặn |
|---|---|
| GPU dùng chung không đủ cho 2 màu × embedder | Màu thứ hai chạy embedder trên CPU khi GPU thiếu; `deploy.sh` kiểm `nvidia-smi` trước khi chọn |
| Migration không tương thích ngược làm màu cũ lỗi | Bước migrate từ chối migration có `DROP` / `RENAME` khi màu cũ còn chạy; lùi phải qua hai lần deploy |
| Harness cần dữ liệu thật, bản diễn tập trong CI không khởi động được với dữ liệu mẫu | Nếu không dựng được snapshot nhỏ: harness stub trả cùng route trong CI, ghi rõ trong báo cáo; diễn tập thật ở gpu156 |
| Fork lệch upstream | `nt548-upstream-sync.yml` + quy ước §6 |
| Tải máy cao làm canary rollback nhầm | So màu mới với màu cũ cùng lúc (không so ngưỡng tuyệt đối); tối thiểu 50 request |

## 12. Câu hỏi còn mở (chủ dự án trả lời)

1. Ai trong bốn người vào được gpu156 (SSH, user nào)? Bảng §8 đang giả định LuanLuKim và hohoangluan vào được, Đình Long và Quỳnh không.
2. Hostname cho bản NT548: thêm một route `nt548.<domain>` → `127.0.0.1:38800` vào **tunnel có sẵn của prod** (dùng chung, ai giữ dashboard Cloudflare thì thêm), hay tạo tunnel riêng? Đăng nhập Google trên hostname mới cần thêm redirect URI trong Google Console, nếu không thì bản NT548 chỉ dùng tài khoản mật khẩu / khách.
3. Hạn nộp NT548 và tiêu chí chấm: quyết định T7 (K8s) và T6 (DataOps) làm đủ hay rút gọn.

Mặc định đã chọn (sửa được): bản NT548 dùng chung key / quota model của prod, nhưng bước eval và e2e chỉ chạy tập nhỏ cố định để không ăn quota.

## 13. Để người làm tự quyết

Tên cổng cụ thể trong dải 187xx / 388xx; cách sinh snapshot nhỏ cho CI; công cụ bắn tải (k6 hay script Python); định dạng log JSON của Nginx; chi tiết unit systemd.
