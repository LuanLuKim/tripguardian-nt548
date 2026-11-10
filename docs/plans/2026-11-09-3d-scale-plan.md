# Kế hoạch triển khai: dựng 3D hàng loạt cho địa điểm nổi tiếng Đà Lạt

> **Cho agent thực thi:** BẮT BUỘC dùng superpowers:subagent-driven-development (khuyên dùng) hoặc superpowers:executing-plans, làm từng task. Bước dùng ô `- [ ]` để đánh dấu.

**Mục tiêu:** quy trình tự động, chạy lại được, dựng mô hình 3D đạt chất lượng cho mọi nơi hot của Đà Lạt có đủ ảnh, kể cả nơi chưa có trong corpus (thêm qua corpus như thường lệ).

**Kiến trúc:** code 3D chuyển từ `logs/splat/diorama/` (ngoài git) vào `scripts/diorama/`; dữ liệu sang `tripguardian-store/splat/diorama/`. `auto3d` là máy trạng thái: script làm mọi bước tất định; sol hàm ghi notes và chấm checklist; bước dựng / sửa do agent sol một phiên (hoặc sol hàm v2 nếu đề thi chứng minh ngang). Nơi mới đi qua corpus: hàng đợi đề cử `navigate` → `gmaps resolve` → filter / counts / list / crawl / photos / photo_scenes / build.

**Công nghệ:** Python 3.12 (`.venv`), Node (`/home/vannk/node/bin`), Three.js engine `index.template.html`, Codex CLI qua 9router (`run_agent.sh`), Playwright (corpus), pytest.

**Spec:** [docs/plans/2026-11-09-3d-scale-design.md](2026-11-09-3d-scale-design.md)

## Ràng buộc chung

- Tài liệu tiếng Việt; code, comment, identifier, tên file tiếng Anh (`RULE.md` §0).
- Không bịa địa điểm: nơi chỉ được dựng khi có FID Maps thật và ≥ 8 ảnh `exterior` + `view` (giá trị `evidence_min: 8`).
- Corpus là offline; module chỉ giao tiếp qua public API (`__init__.py`), không deep import.
- Ngưỡng nằm ở `config/diorama.yaml`: `evidence_min: 8`, `pass_ok_ratio: 0.8`, `max_rounds: 5`, `stall_rounds: 2`, `parallel: 3`, `builder: agent`.
- Không trần cứng về token; dừng khi hai vòng liền điểm checklist không tăng hoặc tới 5 vòng → `needs_human`.
- Model con: sol (`cx/gpt-6.1-sol`); terra chỉ ở vai đề thi chứng minh đạt. Không Gemma.
- Không deploy, không publish release corpus. `publish` của 3D chỉ cập nhật `web/space3d/places.json` + build + check + poster.
- Màu theo ảnh thật, rực rỡ, không đơn sắc, không lạnh.
- Không commit / push khi chưa được chủ dự án yêu cầu: các bước "Commit" dưới đây chỉ `git add` + đề xuất message, chờ lệnh. Đọc `git status` trước (nhiều phiên cùng sửa cây).
- Trước khi phát agent: `ps -eo stat,args | awk '$1~/D/' | grep -E "mount|bwrap"` phải rỗng.

## Trọng tâm review (các tình huống không task nào thử được hết)

1. Nơi có ảnh của **nơi bên cạnh** hoặc chi nhánh trùng tên: `drop_photos` phải loại trước cổng bằng chứng; gate tính sau khi bỏ (test ở Task 4).
2. Agent trả `place.json` hỏng hoặc không boot dù đã hết vòng → dừng `failed:boot`, không ghi đè bản cuối boot được (test ở Task 4).
3. Chạy lại giữa chừng (máy reboot, Ctrl-C) → tiếp từ đúng stage, không lặp bước đã tốn token (test ở Task 4).
4. Kit mới làm đổi render của 29 nơi đã duyệt → `shots_space3d.mjs check` phải 29/29 (Task 7).
5. Maps đòi đăng nhập / captcha giữa lúc crawl → corpus dừng với `LoginRequired`; quy trình báo chủ dự án, không thử lách (Task 8).

---

### Task 1: Tách code vào `scripts/diorama/`, dữ liệu sang store

**Files:**
- Create: `scripts/diorama/` (chuyển từ `logs/splat/diorama/`: `batch/*.py|*.mjs|*.md` mẫu, `kits/`, `bridge/{serve.py,shot.py,request.py}`, `index.template.html`, `build.py`, `check_place.mjs`, `place_assertions.mjs`, `shoot.py`; `logs/splat/agents/run_agent.sh` → `scripts/diorama/run_agent.sh`)
- Create: `scripts/diorama/paths.py`, `scripts/diorama/paths.mjs`
- Modify: `web/scripts/build_space3d.mjs:14` (mặc định `DIORAMA_DIR` → code, thêm `DIORAMA_DATA`)
- Modify: `scripts/README.md` (nhóm `diorama/`), `README.md` §Cấu trúc thư mục
- Data: `logs/splat/diorama/{places,out_*,bridge/out,batch/{inventory,osm_dalat,skip}.json,batch/{groups,match,footprints,samecheck}}` → `/data/work/luanhh/local/tripguardian-store/splat/diorama/`
- Test: `tests/diorama/test_paths.py`

**Interfaces:**
- Produces: `paths.CODE: Path` (thư mục `scripts/diorama`), `paths.DATA: Path` (env `DIORAMA_DATA`, mặc định `<repo>/../tripguardian-store/splat/diorama`), `paths.REPO: Path`; `paths.mjs` export `CODE`, `DATA`, `REPO` cùng nghĩa. Mọi script đọc / ghi `places/`, `out_*`, `bridge/out` qua `DATA`, đọc kit / engine / prompt qua `CODE`. Không còn chuỗi `/workingspace_aiclub` hay `logs/splat` trong `scripts/diorama/`.

- [ ] **Bước 1:** viết `tests/diorama/test_paths.py`: `test_data_env_override` (đặt `DIORAMA_DATA=/x` → `paths.DATA == Path("/x")`), `test_default_data_outside_repo` (mặc định không nằm dưới `REPO`), `test_no_hardcoded_paths` (grep `scripts/diorama/**/*.{py,mjs,sh}` không có `workingspace_aiclub` hay `logs/splat`).
- [ ] **Bước 2:** `.venv/bin/python -m pytest tests/diorama/test_paths.py -v` → FAIL (chưa có module).
- [ ] **Bước 3:** chạy toàn bộ `test_*.mjs` / `test_*.py` ở gốc `logs/splat/diorama` một lần, ghi đạt / trượt. Chỉ những file đạt và còn kiểm hành vi engine / kit chuyển vào `scripts/diorama/checks/`; file một lần (`inspect_*`, `verify_*`, `compare_*`, `test_<nơi>.mjs` trượt), `BRIEF_*` đã chạy, `*.bak*`, `chain*.sh` chuyển sang `/data/work/luanhh/nas/tripguardian/archive-20261109/diorama/` (`RULE.md` §0.3).
- [ ] **Bước 4:** chép code, chuyển dữ liệu (`rsync -aH` rồi so số file, chỉ xoá bản cũ khi khớp), viết `paths.py` / `paths.mjs`, sửa mọi chỗ dùng `D = Path(__file__).parent.parent` thành `CODE` / `DATA` theo vai trò, `run_agent.sh` lấy `REPO` từ vị trí file.
- [ ] **Bước 5:** pytest đạt; `node scripts/diorama/check_place.mjs conga` in `boot ok`; `node web/scripts/build_space3d.mjs` rồi `node web/scripts/shots_space3d.mjs http://127.0.0.1:8472 check web/shots/space3d_after` → 29/29 ok (cần HTTP 8472, Task 2 bước 1 có thể làm trước).
- [ ] **Bước 6:** `git add scripts/diorama tests/diorama web/scripts/build_space3d.mjs scripts/README.md README.md`; message đề xuất `chore(diorama): move 3D pipeline code into scripts/diorama, data to tripguardian-store`.

### Task 2: Hạ tầng một lệnh

**Files:**
- Create: `scripts/diorama/stack.sh` (`up | status | down`)
- Modify: `scripts/diorama/batch/hot_places.py` (nơi `reviews` / `kit` rỗng không làm lỗi; xuất JSON trước khi in)
- Test: `tests/diorama/test_hot_places.py`

**Interfaces:**
- Produces: `stack.sh up` bật 3 worker `bridge/serve.py`, HTTP `127.0.0.1:8471` (thư mục `DATA`) và `:8472` (`web/public`); `stack.sh status` in một dòng mỗi dịch vụ + 9router (`/v1/models`) + kiểm D-state, mã thoát ≠ 0 khi thiếu. `hot_places.rows(min_reviews:int) -> list[dict]` với khóa `fid,name,group,reviews,ext,view,int,tier,kit`.

- [ ] **Bước 1:** test `test_rows_tolerate_missing_reviews` (bản ghi `identity.reviews = None` → `reviews == 0`, không lỗi) và `test_tiers` (ext 8 → `A`; ext 3 + view 5 → `B`; ext 3 + view 4 → `C`; fid trong `web/space3d/places.json` → `done`), dùng fixture nhỏ.
- [ ] **Bước 2:** pytest → FAIL.
- [ ] **Bước 3:** tách `rows()` khỏi phần in, viết `stack.sh`.
- [ ] **Bước 4:** pytest đạt; `bash scripts/diorama/stack.sh up && bash scripts/diorama/stack.sh status` → mọi dòng `ok`, bridge 3 worker.
- [ ] **Bước 5:** `git add`; message `feat(diorama): stack.sh and hot_places rows()`.

### Task 3: Corpus — gieo đề cử nơi hot

**Files:**
- Create: `config/navigate_seed.yaml` (khối `dalat:` danh sách `{name, area_hint, why}`)
- Modify: `src/corpus/navigate/compare.py` (tách `_queue` thành hàm công khai), `src/corpus/navigate/__init__.py` (export `enqueue_nominees`, `seed`), CLI `navigate` thêm phase `seed`
- Modify: `docs/CORPUS.md` §sol dẫn đường + bảng CLI (một dòng `navigate seed`)
- Test: `tests/navigate/test_navigate_seed.py`

**Interfaces:**
- Produces: `corpus.navigate.enqueue_nominees(city: str, rows: list[dict]) -> int` (ghi nối `data/<city>/navigate/resolve_queue.jsonl`, bỏ tên trùng theo `fold`, trả số dòng mới); `corpus.navigate.seed(city: str, path: Path | None = None) -> int` (đọc `config/navigate_seed.yaml`, mỗi dòng `{name, area_hint, aspect: "seed", why}`); CLI `python -m corpus navigate seed --city dalat`.

- [ ] **Bước 1:** test `test_enqueue_dedups_by_folded_name` ("Biệt thự Hằng Nga" và "biet thu hang nga" → 1 dòng), `test_seed_reads_config_and_is_idempotent` (gọi `seed` hai lần → lần hai trả 0), `test_pending_includes_seed` (`pending_nominees` trả tên gieo khi chưa có trong `resolved.jsonl`); `navigate_dir` trỏ vào `tmp_path` qua fixture có sẵn trong `tests/navigate/conftest.py`.
- [ ] **Bước 2:** pytest → FAIL.
- [ ] **Bước 3:** cài đặt; viết `config/navigate_seed.yaml` với các nơi spec §2 nêu là thiếu: Biệt thự Hằng Nga (Crazy House), Nhà thờ Domaine de Marie, Trường Đại học Đà Lạt, Trường Cao đẳng Sư phạm Đà Lạt, Thác Pongour, Vườn quốc gia Bidoup Núi Bà, Đường hầm đất sét, Trang trại bò sữa Dalat Milk, Dinh II; cộng thêm Biệt điện Trần Lệ Xuân, Thác Voi, Đồi cỏ hồng, Ga Trại Mát, Hầm rượu vang Vĩnh Tiến, Thác Đambri. Nơi ngoài `area` sẽ bị `resolve` trả `rejected`; nơi đã có thành `already_held` — đúng ý.
- [ ] **Bước 4:** `.venv/bin/python -m pytest tests/navigate -v` đạt (cả test cũ).
- [ ] **Bước 5:** `git add`; message `feat(navigate): seed nominees from config into the resolve queue`.

### Task 4: `auto3d` v2 — máy trạng thái, cổng, checklist

**Files:**
- Create: `config/diorama.yaml` (giá trị ở Ràng buộc chung)
- Create: `scripts/diorama/auto3d/{__init__.py,gate.py,checklist.py,state.py,prompts.py,builder.py,steps.py,cli.py}`; `scripts/diorama/auto3d.py` còn là lối vào mỏng gọi `auto3d.cli.main()`
- Test: `tests/diorama/test_gate.py`, `test_checklist.py`, `test_pipeline.py`

**Interfaces:**
- `gate.check(fid: str, drop: list[str] = []) -> Gate` — `Gate(ok: bool, ext: int, view: int, reason: str)`; đếm từ `data/gmaps/photo_scenes/<fid>.json` (ảnh `keep`, không `stale`), trừ `drop`; `ok = ext + view >= evidence_min`; `reason = "no_exterior_evidence"` khi trượt.
- `checklist.verdict(items: list[dict]) -> tuple[bool, float]` — item `{id, status: ok|weak|missing|wrong, blocking: bool, cause: data|kit}`; điểm = tỉ lệ `ok`; đạt khi điểm ≥ `pass_ok_ratio` và không item `wrong` có `blocking`.
- `checklist.next_action(scores: list[float], max_rounds=5, stall_rounds=2) -> "continue" | "stop"`.
- `checklist.kit_blocked(items) -> bool` — có item `blocking` với `cause == "kit"`.
- `state.Place(slug)` — như bản cũ (`auto3d.json` trong `DATA/places/<slug>/`), thêm `scores: list[float]`, `ledger(step, tokens)` ghi nối `DATA/batch/ledger.jsonl`.
- Stage: `new → prep → gate → notes → build → boot → shoot → review → (build | colour) → ready`; kết thúc `skip | needs_kit | needs_human | failed:<stage> | published`.
- `builder.Builder` protocol: `build(place, feedback: str | None) -> BuildResult(ok: bool, tokens: int, log: str)`. Hai cài đặt: `AgentBuilder` (gọi `run_agent.sh sol <brief> <log> medium <ảnh bằng chứng…>`; brief = luật `BRIEF_place.template.md` + danh mục kit + ví dụ dán sẵn + notes + phản hồi review gần nhất + tóm tắt các vòng trước; agent tự boot / chụp / xem ≤ 3 lần trong phiên) và `FunctionBuilder` (sol hàm: lần đầu trả cả `place.json`, các lần sau trả bản vá `{"add":[], "update":[{id, …}], "remove":[ids], "hotspots":[…], "route":[…]}` áp bằng `builder.apply_patch(place: dict, patch: dict) -> dict`).
- `prompts.NOTES` trả `{skip, kit, kit_gap: [..], evidence: [gNN ≤ 8], drop_photos, signature: [{id, what, photos, must: bool}], layout, interior, interior_photos, stops}`; `prompts.REVIEW` nhận ảnh render + ảnh bằng chứng đặt cạnh nhau theo điểm dừng, trả `{items: [{id, status, blocking, cause, fix}]}` theo đúng `signature` ids.
- Bước tất định trước boot: `route_fix.mjs <slug>`, tên ảnh `gNN.jpg`, bỏ id trùng.
- CLI: `queue [--tier A,B] [--n N] | run <fid|slug>… [--kit K] [--builder agent|function] | status | gallery [out] | publish <slug>… | add "<tên>" | exam <slug>…`.

- [ ] **Bước 1:** test gate: `test_gate_counts_exterior_plus_view` (6 ext + 2 view → ok), `test_gate_drops_neighbour_photos` (8 → 7 sau `drop=["g03"]` → không ok, `reason == "no_exterior_evidence"`), `test_gate_ignores_stale`.
- [ ] **Bước 2:** test checklist: `verdict` với 4 ok / 1 weak → `(True, 0.8)`; 5 ok + 1 `wrong` blocking → `False`; `next_action([5,6,6,6])` → `stop`; `next_action([5,6,7])` → `continue`; `next_action([1,2,3,4,5])` → `stop`; `kit_blocked` đúng khi blocking + `cause: kit`.
- [ ] **Bước 3:** test pipeline với step giả (inject): `test_resume_skips_done_steps` (state ở `review` → không gọi lại notes / build lần đầu), `test_kit_gap_stops_at_needs_kit` (notes trả `kit_gap` có item `must` → `needs_kit`, builder không được gọi), `test_stall_goes_needs_human` (điểm review 0.6, 0.6, 0.6 → `needs_human`), `test_boot_failure_keeps_last_good` (builder ghi file hỏng ở vòng 2 → `place.json` trở lại bản vòng 1, stage `failed:boot` chỉ khi chưa từng boot được), `test_gate_fail_skips` (gate trượt → `skip`, `reason` ghi lại, 0 token), `test_apply_patch` (add / update / remove theo id).
- [ ] **Bước 4:** pytest → FAIL.
- [ ] **Bước 5:** cài đặt các module. `add "<tên>"` gọi `corpus.navigate.enqueue_nominees("dalat", [{"name": tên, "area_hint": "", "aspect": "seed"}])` và in chuỗi lệnh corpus phải chạy (Task 8), không tự mở trình duyệt.
- [ ] **Bước 6:** pytest `tests/diorama` đạt.
- [ ] **Bước 7:** `git add`; message `feat(diorama): auto3d v2 state machine, evidence gate, checklist review, agent and function builders`.

### Task 5: Đề thi — chọn builder bằng số đo

**Files:**
- Modify: `scripts/diorama/auto3d/cli.py` (lệnh `exam`)
- Output: `DATA/batch/exam_<ngày>.json`, ảnh `frontend_images/space3d-exam-<ngày>.jpg`

**Interfaces:**
- `exam <slug>…`: với mỗi nơi đã duyệt, chép ảnh + meta sang `x_<slug>` (không chép `place.json`), chạy pipeline hai lần (`--builder agent`, `--builder function`), so với `place.json` đã duyệt: số công trình theo loại, độ lệch tâm công trình chính (m), điểm checklist cuối, số vòng, token; ghép một ảnh: bản duyệt | agent | function.

- [ ] **Bước 1:** `stack.sh status` ok; chạy `python3 scripts/diorama/auto3d.py exam conga dinh3`.
- [ ] **Bước 2:** Opus xem ảnh đề thi (một ảnh). Chọn builder: `function` nếu điểm checklist và nhận xét bằng mắt không thấp hơn `agent` trên cả hai nơi; ngược lại `agent`. Ghi lựa chọn vào `config/diorama.yaml` `builder:` kèm số đo trong comment.
- [ ] **Bước 3:** nếu cả hai builder dưới bản duyệt rõ rệt: sửa prompt / brief (Task 4), chạy lại exam; tối đa 3 lượt rồi báo chủ dự án với ảnh.
- [ ] **Bước 4:** xoá `x_*`; `git add config/diorama.yaml scripts/diorama`; message `feat(diorama): exam command; builder chosen by exam`.

### Task 6: Hạng A

- [ ] **Bước 1:** `python3 scripts/diorama/auto3d.py queue --tier A --n 17 --parallel 3` (14 nơi mới; Đường Hầm Điêu Khắc, Dinh I, Quảng trường Lâm Viên đặt lại `stage: new` trước, giữ ảnh). Chạy nền, log `DATA/logs/auto3d_A_<ngày>.log`.
- [ ] **Bước 2:** `auto3d.py status`: không nơi nào ở `failed:*` vì lỗi hạ tầng (lỗi hạ tầng → sửa, chạy lại `run`).
- [ ] **Bước 3:** `auto3d.py gallery frontend_images/space3d-hang-A-<ngày>.jpg`; Opus xem 100 % 10 nơi đầu, sau đó mẫu 10 % + mọi `needs_*`. Nơi Opus thấy sai mà checklist cho đạt → ghi vào brief / prompt review (bài học), chạy lại nơi đó.
- [ ] **Bước 4:** báo chủ dự án ảnh gallery; publish chỉ khi chủ dự án duyệt.

### Task 7: Kit cảnh quan, rồi hạng B

**Files:**
- Modify: `scripts/diorama/kits/{nature,garden}.js`, `kits/catalog/{nature,garden}.md`, `kits/examples/`
- Create: `scripts/diorama/batch/BRIEF_kland_kitext.md` (từ `BRIEF_kitext.template.md`)

- [ ] **Bước 1:** brief mở rộng kit: hồ lớn có bờ, đồi nhiều tầng, đỉnh núi, rừng thông dày, thác nhiều bậc, cáp treo (cột + cabin), điểm ngắm / sàn gỗ, công trình quảng trường lớn; mọi tham số mới có mặc định = render cũ. `run_agent.sh sol … high`.
- [ ] **Bước 2:** hồi quy: build web + `shots_space3d.mjs check` 29/29; `scripts/diorama/checks/` đạt.
- [ ] **Bước 3:** `auto3d.py run` Datanla, Thung lũng Tình Yêu, Khu Du Lịch Lang Biang; Opus xem 100 %; chỉnh kit tới khi ba nơi đạt.
- [ ] **Bước 4:** chạy lại mọi nơi `needs_kit` (gồm Quảng trường Lâm Viên) và `queue --tier B --n 58 --parallel 3`; xem như Task 6 bước 3.
- [ ] **Bước 5:** `git add scripts/diorama/kits`; message `feat(diorama): landscape kit (lake, terraced hills, peak, cable car, viewpoint)`.

### Task 8: Nơi hot còn thiếu + hạng C hot (corpus rồi 3D)

- [ ] **Bước 1:** `python -m corpus navigate seed --city dalat` (Task 3).
- [ ] **Bước 2:** `python -m corpus gmaps resolve --city dalat`, rồi `gmaps filter`, `gmaps counts`, `gmaps list`, `gmaps crawl`, `gmaps qc` (`docs/CORPUS.md` §CLI). Đọc `data/dalat/navigate/resolved.jsonl`: liệt kê `resolved` / `already_held` / `rejected` / `unresolved` cho báo cáo.
- [ ] **Bước 3:** ảnh: viết `DATA/batch/photo_targets_hot.json` (`{"wanted": 40, "places": [{"dir": <fid_dir>}]}`) gồm nơi vừa thêm và nơi hạng C ≥ 1000 review thuộc nhóm tham quan / chợ / cà phê sân vườn (Chợ Đêm, ZooDoo, Mê Linh Coffee Garden, Langfarm Center, Làng Nấm, XQ Sử Quán, Dapa Hill, Đồi Thông Hai Mộ, …); `GMAPS_PHOTO_TARGETS=<file> GMAPS_PHOTO_CHIPS=1 python -m corpus gmaps photos --city dalat`; rồi `gmaps photo_scenes`.
- [ ] **Bước 4:** `python -m corpus build --city dalat` (tới `serving`; **không** publish release). Kiểm `data/serving/places.json` có các FID mới.
- [ ] **Bước 5:** `hot_places.rows(1000)` + các FID gieo (bất kể số review): chạy `auto3d.py run <fid>…`; cổng bằng chứng quyết định; xem như Task 6 bước 3.
- [ ] **Bước 6:** gặp `LoginRequired` / captcha: dừng, báo chủ dự án lệnh `python -m corpus login gmaps` hoặc chạy `--headed`.

### Task 9: Tài liệu chính thức, dọn plan

**Files:**
- Create: `docs/SPACE3D.md` (tiếng Việt: mục đích, sơ đồ quy trình, lệnh, ngưỡng `config/diorama.yaml`, cách thêm nơi mới, kit, màu, hạ tầng, sự cố đã gặp)
- Modify: `README.md` (mục lục tài liệu), `AGENTS.md` bảng "Vào việc từ đâu" (một dòng 3D), `docs/OPERATIONS.md` (`stack.sh`), `docs/log/DEV_LOG.md`
- Delete: `docs/plans/{SPACE_3D_HANDOFF,DIORAMA_BATCH_HANDOFF,AUTO3D_WORKFLOW_HANDOFF}.md`, file spec + plan này

- [ ] **Bước 1:** viết `docs/SPACE3D.md` mô tả đúng code lúc đó (`RULE.md` §0.1: không lịch sử).
- [ ] **Bước 2:** `grep -rn "DIORAMA_BATCH_HANDOFF\|AUTO3D_WORKFLOW_HANDOFF\|SPACE_3D_HANDOFF\|logs/splat" --include=*.md --include=*.py --include=*.mjs .` (trừ `docs/log/`) → rỗng.
- [ ] **Bước 3:** `git add`; message `docs(space3d): one doc for the 3D pipeline; drop 11-04 handoffs and the plan`.
