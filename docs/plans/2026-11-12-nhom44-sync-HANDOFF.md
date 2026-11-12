# Bàn giao: đồng bộ repo nộp đồ án nhom-44 với bản đang chạy (2026-11-12)

Phân tích đầy đủ (bối cảnh, chỗ tốt/tệ, cách port, quyết định): `docs/log/SYNC_2026-11-12.md` trong nhánh WIP (§Vị trí). File này chỉ ghi **trạng thái hiện tại và các bước còn lại**, đủ để session sau làm tiếp mà không phải dò lại.

## 0a. Phiên 4 (12/11 ~22:30): eval UC-01, Bài viết, hồ sơ nộp Phase 1–2

- **Hai nhánh đã commit, chưa push** (quyền ghi GitHub bị chặn trong phiên). Tác giả hohoangluan + `Co-authored-by: LuKimLuan-UIT` (chủ dự án 12/11 ~22:00, áp cho mọi commit đợt này):
  - worktree `/data/work/luanhh/local/tg-port`, nhánh `eval/uc01-gate-rules` (`e6acca23`, `a952bdb3`): bộ case UC-01 theo cổng trước lịch (chỉ `trip` + `care` chặn), lượt bấm thẻ `{deck: {care: [none]}}` gửi `at="gate"`, runner ghép câu trả lời stream, 2 test mới, kết quả `evals/results/20261112T150821Z_uc01.json` (7/12, ràng buộc cứng 94,6%).
  - worktree `/data/work/luanhh/local/tg-web-community`, nhánh `sync/web-community` (`800107e1`, `8c512707`): tính năng Bài viết của local (`web/src/user/community/*`, `posts.css`, sửa `UserApp`/`Frame`/`Pulse`/`icons`) + `docs/web/Role_Web_Functional_Design.md` §2.15 + mẫu `docs/submission/design/search-blog/`. `tsc -b` xanh.
  - Push: `git -c http.extraHeader=… push https://github.com/se373agenticengineering/nhom-44.git <nhánh>`, mở PR, merge (§6).
- **4 issue lỗi UC-01 chưa tạo**: nội dung sẵn ở `docs/plans/2026-11-12-uc01-eval-issues.md` (kèm bình luận cho #35).
- Hồ sơ nộp: `docs/plans/2026-11-12-phase2-demo-script.md` (kịch bản video gọn), `docs/plans/2026-11-12-phase2-report-outline.md` (dàn ý + dữ kiện cho agent viết báo cáo md).
- Ngoài phần trên, local không còn tính năng nào thiếu trên nhom-44 (so toàn cây theo bảng đổi đường dẫn; backend/AI local trùng `.prod_src`).
- Token LuKimLuan-UIT thứ hai cũng đã dán vào chat: thu hồi.

## 0. Trạng thái (phiên 3, 12/11 ~21:40)

**Đồng bộ đã xong trên GitHub.** `main` nhom-44 = `885439d4`. Không còn PR mở.

| PR | Nội dung | Merge |
|---|---|---|
| #63, #59, #60, #62 | PR của đồng đội (phiên 1) | `f172ba87` … `56efba26` |
| #61 | UC-02 + sửa: vượt ngân sách chỉ cảnh báo, vẫn chốt (`validate.WARN_ONLY` / `blocking()`, thẻ chỉ vượt ngân sách vẫn `confirmable`, engine không chạy `bounded`, ghi chú giá chỉ ở `uc02.itinerary`, nút Chốt không khóa) | `ad13063b` |
| #65 | web UI (bản server, gồm cả UI chưa commit của local) | `c29589d4` |
| #66 | 3D: viewer, 107 nơi, diorama | `f9c38275` |
| #67 | backend: harness, accounts, live, migration 008 (gồm 5 file backend chưa commit đang chạy trên prod) | `c518942d` |
| #68 | AI: planning, trip, decision, corpus, bench, config | `8480b151` |
| #69 | vận hành + tài liệu, `docs/log/SYNC_2026-11-12.md` (§6 tác giả, §7 kết quả test) | `885439d4` |

- Bình luận đổi ý tưởng ngân sách đã đăng lên #61 và #36; mô tả #36 có thêm ghi chú.
- #65–#69: commit merge tạo bằng git trên gpu156 rồi push `main` (GitHub tự đánh dấu PR đã merge), vì plugin quyền riêng tư chặn gửi email co-author qua API.
- **Test** (cây = `main` trừ file workflow): 1 fail · 5.486 pass · 438 skip, fail duy nhất `ai/tests/trip/test_knowledge.py::test_weather_at_the_center` (fail cả trên local `main`). `tsc -b` xanh. Log: `tg-sync-2026-11-12/test_wip_server.txt`, `test_pr61_fix2.txt`.
- **Tốc độ** `Engine.create` (chuyến mẫu trong test): server 61 / 113 ms / 5,8–6,7 s; sau đồng bộ 26 / 75 ms / 5,1–5,4 s. Chưa rõ vì sao bản sau nhanh hơn.
- **GitHub Actions không chạy** ở mọi commit (job không khởi động: lỗi thanh toán / hạn mức chi tiêu của tài khoản). Cần chủ repo xử lý trong Billing.

**Việc còn lại:**
1. **`.github/workflows/test.yml` chưa lên `main`**: token LuKimLuan-UIT không có quyền `workflow`. Bản vá (Python 3.12 như prod, job `web` build `frontend/` với Node 24): `/data/work/luanhh/local/tg-sync-2026-11-12/ci_workflow.patch`. Áp bằng token có quyền `workflow` hoặc sửa tay trên GitHub.
2. **Thu hồi token GitHub của LuKimLuan-UIT** đã dán vào chat (hai lần).
3. Prod trên gpu156 vẫn chạy cấu trúc cũ từ repo local; chuyển sang cấu trúc mới là deploy riêng, chỉ khi chủ dự án yêu cầu (`SYNC_2026-11-12.md` §8).
4. Repo local (`tripguardian`) vẫn còn các thay đổi chưa commit (đã có trên nhom-44 qua #65/#67/#68); commit ở local là việc riêng của chủ dự án.
5. Dọn khi không cần nữa: worktree `tg-nhom44-trial`, `tg-nhom44-sync`, `tg-pr61`, `tg-pr59`, `tg-local-main`, `tg-port`; ref `refs/nhom44/*`, `refs/sync/*`; nhánh `sync/*` trên nhom-44 (đã merge).

Các mục bên dưới (§2–§5) là lịch sử của phiên 1–2, giữ để tra cứu.

## 1. Yêu cầu của chủ dự án (giữ nguyên ý)

- So repo local với `https://github.com/se373agenticengineering/nhom-44` (repo nộp đồ án, đã bị cập nhật lệch). Phân tích, viết md trước, rồi merge: **PR đang mở trước, bản local sau**.
- Chia thành nhiều lần merge cho hai tài khoản. **hohoangluan** (`hohoangluan2006@gmail.com`): UI/UX, frontend và logic backend liên quan. **LuKimLuan-UIT**: phần còn lại. Người dùng của phiên này là LuKimLuan-UIT.
- **Vượt ngân sách vẫn chốt được, chỉ thêm cảnh báo.** Ghi chú rõ đây là đổi ý tưởng so với PR #61 / issue #36, sửa cả issue nếu cần.
- **UI: ưu tiên bản local** so với baseline nhom-44.
- **Backend: lấy logic bản đang chạy trên server làm chuẩn** (chủ dự án 12/11 tối), merge toàn bộ như một lần cập nhật. Bản server = `.prod_src` (`be1d958` + 5 file backend chưa commit; web dựng 12/11 16:38 gồm cả UI chưa commit).
- **Tác giả commit: quy tắc "Kết hợp"** (chủ dự án 12/11 ~21:00, thay quy tắc trước):
  - Frontend (`frontend/**`): tác giả `hohoangluan <hohoangluan2006@gmail.com>`, **không trailer nào**.
  - Backend + AI (`backend/**` trừ script shell, `ai/**` trừ `ai/scripts`, `evals/**`, `skills/**`, `tests/**`): tác giả hohoangluan + `Co-authored-by: LuKimLuan-UIT <332377520+LuKimLuan-UIT@users.noreply.github.com>`.
  - Vận hành + tài liệu (`run.sh`, `scripts/`, `ai/scripts`, `backend/scripts`, `docs/**`, README / AGENTS / RULE, `.github`, `.gitignore`, `.env.example`) và commit merge: tác giả LuKimLuan-UIT + `Co-authored-by: hohoangluan <hohoangluan2006@gmail.com>`.
  - Một commit không trộn hai loại; committer đặt trùng tác giả.

## 2. Đã xong

| Việc | Kết quả |
|---|---|
| Fetch nhom-44 (không đổi remote, không lưu token) | ref ở `refs/nhom44/{heads,pull,tags}/*` trong repo local. Fetch lại: xem §6 |
| Tìm gốc chung | không có lịch sử chung. `eaeef5b6` (nhom-44) = local `8bf8547f` bỏ `.claude/skills`, `.agents/skills` |
| Commit tổng hợp của local trên gốc nhom | `refs/sync/local-full` = cây `main` local (`be1d958`) bỏ `.claude/`, `.agents/`, cha là `eaeef5b6` |
| Test nền (máy sạch, không `data/`) | nhom `main`: 5 fail / 5159 pass. nhom + 5 PR: 14 fail. Local `main`: 46 fail + 2 lỗi thu thập (thiếu `data/`; trùng tên `test_cli.py` / `test_pipeline.py`) |
| **Merge trên GitHub** (API, token LuKimLuan-UIT, `merge_method=merge`) | **#63 → f172ba87, #59 → 2455e361, #60 → 9ec967bd, #62 → 56efba26**. `main` nhom-44 giờ ở `56efba26` |
| Port local vào cấu trúc mới + giải xung đột | xong trên nhánh WIP (§3) |
| File phân tích | `docs/log/SYNC_2026-11-12.md` trong nhánh WIP; §7 còn chữ `KẾT_QUẢ_TEST` chờ điền |

## 3. Vị trí

| Thứ | Ở đâu |
|---|---|
| Nhánh WIP: nhom `main` (cũ `368a2c2c`) + merge thử 5 PR + port local + sửa #61 | worktree `/data/work/luanhh/local/tg-nhom44-trial`, nhánh local `sync/nhom44-port-wip`, commit `6e5cdb20`. **Không push nhánh này**: các merge thử có tác giả `t <t@t>` |
| Worktree nhom `main` + 5 PR (merge thử, để so) | `/data/work/luanhh/local/tg-nhom44-sync` (nhánh `sync/nhom44`) |
| Worktree riêng PR #61 | `/data/work/luanhh/local/tg-pr61` (detached ở `281f4477`) |
| Worktree riêng PR #59 | `/data/work/luanhh/local/tg-pr59` |
| Worktree local `main` sạch | `/data/work/luanhh/local/tg-local-main` |
| Script port, báo cáo, kết quả test | `/data/work/luanhh/local/tg-sync-2026-11-12/` (`port/port.py`, `port/hunks.py`, `port/report4.json` + `.subs.json` = bảng đổi đường dẫn, `test_*.txt`) |

`port/port.py REPO BASE LOCAL TARGET_DIR REPORT_JSON`: áp thay đổi `BASE→LOCAL` (cấu trúc cũ) lên worktree `TARGET_DIR` (cấu trúc mới) bằng merge ba chiều theo bảng đổi tên của PR #58, rồi đổi chuỗi đường dẫn. `port/hunks.py list|set FILE IDX n|l|b|@file`: xem / giải từng hunk diff3 (`n` = nhom, `l` = local).

## 4. Quyết định đã áp trong nhánh WIP

- Cấu trúc chuẩn là của nhom-44 (`ai/`, `backend/`, `frontend/`, `docs/<chủ đề>/`). Phần chỉ local có: `frontend/scripts/diorama/`, `frontend/tests/diorama/` (đổi tên `test_auto3d_cli.py`, `test_auto3d_pipeline.py` để hết trùng tên module), `frontend/config/diorama.yaml`, `docs/operations/OPERATIONS.md`, `docs/submission/pitch_desk.md`. Fixture ảnh dùng `ai/tests/fixtures/ui/` của nhom.
- `docs/plans/*` của local **không** đưa lên nhom-44 (nhom đã chủ động bỏ). File bàn giao này cũng chỉ nằm ở local.
- `run.sh`: `.prod_src` + `RELEASE` + `prod-restart/rollback/check` của local, đông cứng `backend/src` + `ai/src`. `.gitignore` hợp hai bên.
- **PR #61, sửa trong nhánh WIP** (cần dựng lại thành commit riêng trên nhánh PR, §5 bước 1):
  - `ai/src/planning/engine.py`: hai chỗ `plan_cards(..., bounded=True)` bỏ `bounded`. Engine dùng lại thuật toán quá tải cũ, không tự bớt điểm.
  - `ai/src/planning/overload.py`: `_repair_constraints` chỉ chạy khi `bounded=True` (có comment giải thích).
  - `ai/src/planning/build.py` `itinerary()`: bỏ chèn `visit_fact_notes` ("Chưa có giá." / "Chưa xác minh giờ mở cửa.") vào ghi chú UI; chỉ còn trong `uc02.itinerary`.
  - `confirm`: vi phạm (kể cả `trip_budget`) là cảnh báo, không `raise`. Đây là quy tắc của local từ 08/11.
  - `ai/tests/planning/test_planning_engine.py`: hai test `test_budget_repair_*` thay bằng `test_over_budget_plan_keeps_every_place_warns_and_still_confirms` và `test_far_over_budget_still_confirms_with_the_violation_on_the_plan`; dòng `plan_or_directions(..., bounded=True)` bỏ `bounded`.
  - `tests/evals/test_uc01_runner.py`: cho phép riêng `ai/src/planning/evaluate.py` (bộ chấm offline UC-02) nhắc tới `evals`.
  - `docs/planning/PLANNING.md` §Validator: khôi phục "ngân sách không chặn", thêm **ghi chú đổi ý tưởng**; sửa dòng "chưa giải quyết thì chốt trả 409".
  - `frontend/src/user/screens/Plan.tsx`: UI local (`warned` + hỏi lại) cộng dòng nêu số tiền vượt của #61.
- UI: đã so `frontend/src` với `web/src` local. Chỉ 5 file lệch ngoài đường dẫn, đều là bổ sung chức năng nhỏ của nhom, được giữ: ẩn nút Google khi chưa cấu hình OAuth (`Auth.tsx`, `account.ts`), `weather_unknown`, `REPAIR_TITLE` (`Choose.tsx`), `rule?` / `overload.reason` (`types.ts`). Chi tiết: `tg-sync-2026-11-12/frontend_diff_vs_local.txt`.

## 5. Việc còn lại, theo thứ tự

0. **Kiểm test nhánh WIP.** Lần chạy cuối của `ai/tests/planning backend/tests/harness tests/evals` sau khi sửa #61 chưa xong khi hết phiên; kết quả (nếu còn) ở `tg-sync-2026-11-12/t_plan.txt`. Chạy lại:
   `cd /data/work/luanhh/local/tg-nhom44-trial && /data/work/luanhh/local/tripguardian/.venv/bin/python -m pytest -q -p no:cacheprovider -m "not live"`
   Lần chạy toàn bộ **trước** khi sửa #61: 16 fail + 2 lỗi thu thập (`test_trial.txt`). Sau khi sửa phải còn: lỗi có sẵn trên nhom `main` hoặc local `main` (`ai/tests/trip/test_knowledge.py::test_weather_at_the_center` fail cả trên local `main`), và `backend/tests/harness/test_run_trace.py::test_the_guardrail_verdict_is_traced…` (test của #62: đếm lượt stage `decision`, lệch vì local đổi luồng gate / chat mới; sửa test hoặc helper `decision()`). Những test còn fail do #61 (`test_planning_consistency`, `test_planning_r11` timeout draft, `test_planning_r14` pet note, `overload_parallel`, `backend/tests/harness/test_tools.py` hard meal / overload handoff, golden) **phải xanh** sau khi bỏ `bounded` và bỏ ghi chú UI. Nếu chưa xanh thì tìm nguyên nhân, không cập nhật golden cho qua. Golden chỉ được đổi nếu diff đúng là hành vi mong muốn; lần trước diff golden chỉ là "Chưa có giá." (nay đã bỏ khỏi UI) và `total_travel_min 55→56`.
   Frontend: `cd frontend && npx tsc -b` (lần trước xanh). Test node không cần trình duyệt: 8/8 file xanh. Test Playwright fail cả trên nhom + PR (thiếu Chromium / Vite); không phải lỗi port.
1. **PR #61 trên GitHub.** `git fetch` lại `main` nhom (§6). Trong `tg-pr61`: checkout nhánh `feat/uc02-itinerary-validation` từ `refs/nhom44/heads/…`, merge `main` mới (`56efba26`), áp đúng các sửa ở §4 cho #61 (bản đứng riêng: `confirm` của nhánh này còn `raise` cho mọi vi phạm, nên ít nhất cho `trip_budget` đi qua và đưa `violations` vào output; nút Chốt trong `Plan.tsx` của nhánh này đang `disabled={busy || blocked}`, phải cho chốt khi chỉ vượt ngân sách). Chạy test, commit theo §1 (tác giả commit): phần AI / eval / test / docs tác giả **LuKimLuan-UIT** kèm `Co-authored-by: hohoangluan <hohoangluan2006@gmail.com>`; `Plan.tsx` là commit riêng tác giả **hohoangluan**, không trailer; amend merge `cdbb42d4` thêm trailer co-author (§0). Push lên nhánh PR, rồi merge #61 qua API. Bình luận lên #61 và issue #36: ghi chú đổi ý tưởng (vượt ngân sách → cảnh báo, vẫn chốt; vòng sửa giới hạn không chạy trong engine; gợi ý bớt điểm nên là thẻ tùy chọn), kèm danh sách 12 test #61 làm hỏng và cách sửa.
2. **Port local lên `main` mới** thành các commit/PR tách theo người (bảng §6 của `SYNC_2026-11-12.md`):
   - hohoangluan (không co-author): (a) UI web `frontend/src`, `frontend/public/img`, `frontend/tests` (trừ diorama), `frontend/scripts` (trừ diorama/space3d), `frontend/server.mjs`, `docs/web/*`; (b) 3D `frontend/public/space3d`, `frontend/space3d`, `frontend/scripts/build_space3d.mjs`, `frontend/scripts/diorama`, `frontend/tests/diorama`, `frontend/config`; (c) backend phục vụ web `backend/src/**`, `backend/tests/**`, `backend/migrations`.
   - LuKimLuan-UIT (trailer `Co-authored-by: hohoangluan <hohoangluan2006@gmail.com>`): (d) AI `ai/src`, `ai/tests`, `ai/config`, `ai/scripts`; (e) vận hành và tài liệu `run.sh`, `scripts/`, `backend/scripts`, `backend/tools`, `.gitignore`, `.env.example`, `.github`, `README.md`, `AGENTS.md`, `RULE.md`, `docs/**` (trừ web), `tests/**` gốc, `docs/log/SYNC_2026-11-12.md` (điền §7).
   Cách làm: lấy cây cuối của nhánh WIP (sau khi đã sửa xong), tạo worktree mới từ `main` nhom (sau #61), với mỗi nhóm `git checkout sync/nhom44-port-wip -- <paths>` (và `git rm` file nhóm đó xóa), commit đúng tác giả và trailer theo §1 (kiểm bằng `git log -1 --format='%an <%ae>%n%(trailers)'`), push nhánh `sync/<nhóm>`, mở PR, merge theo thứ tự a→e. Trước khi push: `git diff` của nhóm không được chứa phần đã vào qua #61, `node_modules`, `.cache`; quét bí mật (`ghp_`, `sk-`, `BEGIN … PRIVATE`). Sau bước e: cây `main` phải bằng cây nhánh WIP (trừ các merge thử), chạy lại toàn bộ test.
3. Điền §7 `KẾT_QUẢ_TEST` của `SYNC_2026-11-12.md` (số trước/sau). Sửa cột "Tác giả commit" ở §6 của file đó theo §1 (hohoangluan không co-author; LuKimLuan-UIT kèm co-author hohoangluan). Cập nhật §8 nếu có việc mới.
4. Dọn: `git worktree remove` các worktree `tg-*`; xóa `refs/nhom44/*`, `refs/sync/*` khi không cần nữa.

## 6. Lệnh hay dùng

```sh
# Fetch nhom-44 không lưu token vào config (token: hỏi người dùng, không ghi vào file)
B64=$(printf 'x-access-token:%s' "$TOKEN" | base64 -w0)
git -c http.extraHeader="Authorization: Basic $B64" fetch --no-tags https://github.com/se373agenticengineering/nhom-44.git \
  '+refs/heads/*:refs/nhom44/heads/*' '+refs/pull/*/head:refs/nhom44/pull/*'
# Push một nhánh lên nhom-44
git -c http.extraHeader="Authorization: Basic $B64" push https://github.com/se373agenticengineering/nhom-44.git HEAD:refs/heads/<nhánh>
# Mở / merge PR
curl -s -H "Authorization: token $TOKEN" -X POST https://api.github.com/repos/se373agenticengineering/nhom-44/pulls -d '{"title":…,"head":"<nhánh>","base":"main","body":…}'
curl -s -H "Authorization: token $TOKEN" -X PUT  https://api.github.com/repos/se373agenticengineering/nhom-44/pulls/<n>/merge -d '{"merge_method":"merge"}'
```

Git trên gpu156 là 2.25 (không có `merge-tree --merge-base`, không có ort). Không có `gh`. Remote `origin` của repo local là `hohoangluan/tripguardian` (push từ gpu156 vốn lỗi); không đổi remote.

## 7. Rủi ro và lưu ý

- **Token GitHub của LuKimLuan-UIT đã dán thẳng vào chat** của phiên này. Nên thu hồi và tạo token mới sau khi xong.
- Prod trên gpu156 vẫn chạy cấu trúc cũ từ repo local; đồng bộ này không đổi prod. Chuyển prod sang cấu trúc mới là việc riêng, chỉ làm khi chủ dự án yêu cầu.
- Working tree local còn thay đổi chưa commit (TimePick, Plan/Today, CSS, `harness/session.py`, …) của phiên khác; **chưa** nằm trong port. Không đụng tới chúng.
- #60 đổi system prompt của Trip; chưa đo bằng eval có model thật. #62 bật trace mặc định, chưa có giới hạn dung lượng.
- #61 đổi vùng cấm từ "chỉ cảnh báo" sang "loại nơi `access=no` đã xác minh"; cần chủ dự án xác nhận.
