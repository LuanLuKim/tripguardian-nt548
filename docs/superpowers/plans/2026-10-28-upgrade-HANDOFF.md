# Bàn giao: nâng cấp theo spec 2026-10-26 (bản 2026-10-28 chiều)

> Plan làm việc (`RULE.md` §0.1), tạm thời. Spec: `docs/superpowers/specs/2026-10-26-production-and-course-upgrade-design.md`. Session mới đọc file này trước, rồi ledger của từng track. Xong hết thì gộp phần còn giá trị vào tài liệu chính thức và xoá file này.
> Viết bởi session `tripguardian-77`, 2026-10-28 ~16:40.

## CHỐT 2026-10-30 ~04:00 — session `tripguardian-05` (đọc mục này trước tiên)

Đã làm xong 6 việc của mục 02:05 bên dưới. Nhật ký: `.superpowers/sdd/2026-10-30-wave/controller.md`.

**Trên prod** (deploy `HARNESS_GPU=7 ./run.sh prod`, smoke ok, kiểm sau đăng nhập ok):
- Release `r-821680126d9fd8ba47301de1-16eff8c6`: 3.172 nơi, ảnh 40.038 → 53.255, có rating/reviews thật.
- **Claim local giữ bộ cũ 430 kept** (chủ dự án chọn). Soát tay 10 claim mới: 4 đúng / 3 lệch / 1 nhiễu / 2 sai. Bộ mới 1.257 kept cất ở `data/dalat/local/held_1030/` (có README).
- Chat trợ lý ở Lịch trình (`Assistant.tsx` dùng chung, `stage="planning"`).
- Trợ lý Lịch trình không hoàn tác vi phạm mềm nữa: giữ lại và gắn cờ. Bench live terra: move 1,0, reorder 1,0, 0 vi phạm vật lý.
- 16 lỗi ui-qa đã sửa (B1–B16; B14 chưa xem live). Chuyến ghim snapshot đã xoá trả 409 `stale_data_version`, không còn 500.
- Bỏ lọc `MIN_PRICE_VND`: đã sửa gốc ở `place_rules.py`.
- `AGENT_MODEL` giữ terra: nhanh hơn sol, độ đúng ngang nhau (`data/bench/assistant/final-*`, `plan-chat-*`).

**Git:** branch `upgrade/2026-10-30-wave`, 6 commit theo khu vực, chưa push. Ngoài git, cố ý để lại:
- Các file bị xoá ở thư mục gốc: `*.mp4`, `pitch_desk.md`. Chủ dự án quyết.
- `2026-10-06_de_tai_08_tour_guide_agent.docx`.
- Ảnh trong `frontend_images/`.

**Còn mở (chưa lên lịch):**
1. Siết gate `corpus.local` rồi mới dùng bộ claim mới. Lỗi thấy được: subject không có trong quote, sources đếm trùng domain, tài liệu ngoài chủ đề lọt vào.
2. `realism[travel_vs_nn]` `short_by_40`: thuật toán tìm thứ tự kẹt ở cực trị cục bộ trên ngày quá tải (`route.py`/`build.py`). Chủ dự án chọn: sửa thuật toán tìm, hay nới ngưỡng cho ngày quá tải.
3. Gate bench còn trượt trên cả hai model:
   - ảnh trong Trip p90 18,6 s (gate 15 s);
   - Decision có 2 câu thiếu nguồn ở `compare`;
   - nhóm services: tool-group 0,0;
   - `rr-avoid` đi heuristic.
4. `test_wish_speed` p95 160 ms > 120 ms (đo lúc máy tải cao).
5. Gap từ prod-gaps:
   - giá phòng theo ngày;
   - giờ mở cửa 50 %;
   - sự kiện chưa có crawl định kỳ;
   - `pick_transit` chưa nối;
   - Trip/Schedule chỉ nằm trong RAM;
   - lịch đầu chậm.
6. Chưa có đường re-pin/revalidate cho chuyến ghim snapshot đã xoá; UI chỉ bảo tạo lại chuyến.
7. Chờ chủ dự án: deploy từ git worktree riêng thay vì cây dùng chung.

## CHỐT 2026-10-30 02:05 — bàn giao sang tài khoản mới

Chủ dự án sắp hết usage, chuyển tài khoản. Usage Codex cũng hết: terra/sol qua 9router trả 503/429, nên **chat Agent trên prod lỗi cho tới khi Codex hồi** (~02:15). Nhật ký đầy đủ: `.superpowers/sdd/2026-10-30-wave/controller.md`. Luật đợt: `.superpowers/sdd/2026-10-30-wave/common.md` và `ui-common.md`. Subagent của session cũ không resume được: đọc dòng cuối ledger của từng track `.superpowers/sdd/2026-10-30-<track>/progress.md`.

**Prod đang BẬT:** harness :8769 (GPU 7), web :28899 (build 01:42 có UI mới), tunnel, notify, 9router, Clef NF4 GPU 4 + gateway :30000. Site: `https://tripguardian.visioncare-host.uk/app`. Restart: `HARNESS_GPU=7 ./run.sh prod` (build web) hoặc `sh logs/prod_restart_nobuild.sh`. **Trước mỗi lần restart:** `.venv/bin/python -c "import sys; sys.path.insert(0,'src'); import harness.__main__"`. Prod chạy thẳng từ cây làm việc; 01:43–01:58 prod down vì một track khai tool chưa đăng ký quyền.

**Xong hôm nay** (chi tiết ở ledger):
- Clef NF4 nhanh hơn: 0,33 → 0,26 s/request, 3,1 → 5,2 req/s, gate guard đạt; đang là Clef chính, chỉ 1 bản theo lời chủ dự án.
- Lựa chọn: hết chậm (`.env` bị đọc mỗi thẻ), rerank p90 7,8 s.
- UI bù cho đủ tính năng backend (đã deploy): thẻ trong chat Lựa chọn + "Vì sao không gợi ý?"; khối món và khối dịch vụ trong Tìm hiểu; thẻ Độ tin cậy, đổi giờ ở banner eve, Nhịp Đà Lạt ở Plan/Today; chuyến xe/máy bay theo ngày trong WayIn. Báo cáo: `.superpowers/sdd/2026-10-30-ui-parity/report.md`.
- Dữ liệu: +4 bến xe; ảnh ≥ 3 cảnh 45,1 → 57,3 %; giá menu 0 → 765 quán; `flight_cache: true` (cron 03:15 làm mới cả máy bay; lượt tay 01:3x: 494/540 ok).
- Rà gap từng phase: `.superpowers/sdd/2026-10-30-prod-gaps/report.md`.

**Đang chạy lúc bàn giao** (xem ledger trước khi làm gì):
- `crawl-local`: XONG (xem mục "Nếu session cũ đã tắt").
- `tiktok-retry`: XONG (xem dòng tiktok-retry ở mục "Nếu session cũ đã tắt").
- `plan-chat` **CHỐT (backend)**: 21 tool (8 đọc, 13 ghi; không có relax/confirm/đổi chỗ ở), mỗi lượt gộp thành một version, một lần undo là hoàn cả lượt; sửa nào thêm vi phạm thì bị hoàn ngay. Đã nối harness (`planning.turn`). Test: 364 pass (harness + planning engine/turn/assistant/bench). Spec `docs/superpowers/specs/2026-10-30-planning-assistant-design.md`. **Chưa làm:** UI panel ở Plan (dùng lại `Assistant.tsx`), bench live 31 ca (`.venv/bin/python -m planning bench --live --trip --model cx/gpt-6.1-terra`, `SSL_CERT_FILE` từ certifi, `CUDA_VISIBLE_DEVICES=6`; cần Codex hồi). Cần restart harness để lên prod.
- `ui-qa`: **DỪNG giữa chừng** (subagent hết giới hạn 5 giờ lúc ~02:10, hồi 03:30), chưa có kết quả. Làm lại từ brief trong controller log (01:58).
- `screens`: **DỪNG giữa chừng** (cùng lý do), mới có 19 ảnh trong `frontend_images/2026-10-30/`; script `logs/screens_capture.py` đã viết (ledger: "script has all sections"). Chạy lại script, rồi viết `INDEX.md`.
- `bench-final`: terra vs sol; phần Decision INVALID vì Codex hết usage → chạy lại khi hồi.

**Nếu session cũ đã tắt** (đổi tài khoản thì subagent dừng giữa chừng, còn job `nohup` vẫn chạy):
- Job nền còn sống, có marker:
  - crawl-local: **XONG 02:06**. 1.969 tài liệu (785 → 1.969); claim `kept` 430 → 1.257, `conflict` 459, `confirmed` 13; pulse 6 sự kiện có ngày (mốc G7 là 1). Soát tay 10 `kept`: 8 đúng, 2 yếu. Spec §5B G4/G7 đã cập nhật.
  - tiktok-retry: **XONG 02:03**. asr_check thử lại 3 nấc (gốc → temperature 0,5 có khung hình → không khung hình, `screen_text=[]`), cứu được 307/531 video; còn 224 video chưa có check. Chuỗi place_verify/place_poi/clips đã chạy. Số nơi có bằng chứng không đổi (1.174, có clip 1.162); cặp bằng chứng 12.032 → 12.190. Muốn làm thêm thì chạy lại `asr_check` (UIT ≤ 18).
- Track chỉ do subagent làm (dừng thì làm lại từ dòng cuối ledger):
  - `plan-chat`: kiểm `tests/planning/test_planning_assistant.py`, `pytest --collect-in-virtualenv -q tests/harness`, và import harness. Nếu UI Plan đang dở, `cd web && node_modules/.bin/tsc -b` phải sạch, không thì gỡ phần UI dở.
  - `ui-qa`, `screens`: chạy lại từ brief trong controller log (01:58, 01:30).
- `git status --short | head` để thấy các file đang sửa; không commit dở.

**Câu mở đầu cho session mới:** "làm tiếp docs/superpowers/plans/2026-10-28-upgrade-HANDOFF.md từ mục CHỐT 2026-10-30 02:05; đọc controller log .superpowers/sdd/2026-10-30-wave/controller.md và dòng cuối ledger từng track 2026-10-30 trước khi làm gì".

**Việc tiếp theo, theo thứ tự:**
1. Chạy lại `ui-qa` → sửa lỗi UI một lượt (Sonnet, theo `ui-common.md`; luôn dùng tài khoản dev để xem màn sau đăng nhập).
2. **Build release ĐÃ MỞ KHOÁ** (crawl-local + tiktok-retry xong 02:06; chỉ còn `lodging_price_loop` chạy mỗi giờ, kiểm nó không đang ghi lúc build): build release `python -m corpus gmaps observe --city dalat` → `aggregate` → `serving` → build release (`normalize --rebuild` …). Sau đó: bỏ lọc `min_vnd` < 1.000 trong `src/trip/infrastructure/reads.py`; sửa `tests/planning` (5 fail: `better_order::bad_realistic_reorder`, `overload_round1[rainy_month]` ×2, `realism[overload_explained]`, `realism[travel_vs_nn]`) và `test_equivalence`; đo lại `test_wish_speed` khi máy rảnh; hiệu chỉnh `rep`/`base`/`ref_n`.
3. Restart prod (kiểm import trước) để nhận release + backend của plan-chat, ui-trip, ui-plan, ui-decision.
4. Khi Codex hồi: `bench-final` (lệnh trong ledger) + bench live của plan-chat; chọn `AGENT_MODEL` theo số đo.
5. Chạy lại `logs/screens_capture.py frontend_images/<ngày>` sau deploy cuối.
6. COMMIT theo khu vực trên branch mới (không push; kiểm `.env.example`, file lớn ngoài git).
7. Gap chưa lên lịch (từ prod-gaps): giá phòng theo ngày 44/~1.525; giờ mở cửa 50 %; sự kiện có ngày chưa có crawl định kỳ; `pick_transit` chưa nối; Trip/Schedule chỉ trong RAM; lịch đầu 20 nơi/2 ngày 3,7–4,3 s.

**Chủ dự án đã quyết hôm nay (không hỏi lại):** Clef NF4 là Clef chính, 1 bản; prod bật; cho 9router chạy bench; `flight_cache` bật; làm chat Lịch trình; `assistant.enabled` giữ bật; banner eve giữ kiểu hiện tại; UI phải đủ mọi tính năng backend; ảnh màn lưu `frontend_images/`.
**Chờ chủ dự án:** deploy từ git worktree riêng thay vì cây dùng chung (đề xuất của controller).

## CHỐT 2026-10-30 (session `tripguardian-cb`) — đọc trước mục 29/10 tối

Nhật ký điều phối: `.superpowers/sdd/2026-10-30-wave/controller.md`. Luật chung của các track trong đợt: `.superpowers/sdd/2026-10-30-wave/common.md`.

- **Clef NF4 đã tối ưu, đang là Clef chính** (chủ dự án yêu cầu 30/10):
  - Mỗi request 0,33 → 0,26 s. Một bản: 3,1 → 5,2 req/s. Thử hai bản thì được ~9 req/s, nhưng chủ dự án bảo bỏ bản thứ hai (GPU 6 trả lại).
  - Cách làm: gom batch, cộng dồn fp16, tắt double-quant.
  - Không đổi đáp án nào trên 136 request. Gate guard: 0 chặn nhầm, chặn đúng 95,3 % ở timeout 4 s lẫn 2 s. `test_clef_live` pass.
  - Đã thử rồi bỏ: fla, prefix cache. Chi tiết và số đo ở `docs/LLM_PROVIDER.md` §Host model tự chạy.
- **Đang chạy:**
  - GPU 4 `:30011`, gateway `:30000`; điều khiển bằng `scripts/models_ctl.sh start|stop|status` (`CLEF_REPLICAS` để thêm bản).
  - `.env` trỏ `CLEF_BASE_URL` vào gateway, `CLEF_TIMEOUT_S=4`. Backup `.env.bak_20261030_clef_nf4`. Muốn quay về Cloudflare thì comment 3 dòng `CLEF_` và đặt timeout 2.
  - Process đã chạy từ trước vẫn giữ biến `.env` cũ cho tới khi restart.
- **GPU:** 4 = Clef; 6 + 7 = harness và mọi việc GPU khác (`config/index.yaml` vẫn `[6,6,6,7,7,7]`). `run.sh` đổi mặc định `HARNESS_GPU` từ 1,3 thành 7, vì GPU 1, 2 và 3 giờ có người khác dùng.
- **Production BẬT lại 30/10 (chủ dự án cho phép):** `logs/prod_restart_nobuild.sh` (đã sửa lỗi dò `PYTHON`); smoke ok; `https://tripguardian.visioncare-host.uk/app` 200. `./run.sh prod` và script này tự bật Clef + gateway (`clef_start`) trước harness. Harness tải lâu hơn mốc chờ 90 s: script báo NOT up thì chạy lại một lần, phần đã lên được bỏ qua. 9router bật cho bench.

## CHỐT 2026-10-29 tối (23:40) — đọc mục này trước mọi mục khác

Session điều phối tối 29/10 bàn giao vì context đã quá dài. Nhật ký điều phối đầy đủ, kèm bảng ngân sách lane: `.superpowers/sdd/2026-10-29-final-wave/controller.md`. Ledger từng track vẫn là nguồn sự thật.

**Chủ dự án quyết tối nay (không hỏi lại):**
- **Chưa lên production** khi đợt này chưa xong. Prod đang TẮT: chủ dự án đã dừng harness :8769, web :28899, 9router, tunnel, Clef self-host để trả GPU. Chỉ bật lại khi được bảo, bằng `sh logs/prod_restart_nobuild.sh`: không build web, không migrate, harness trên GPU 1,2.
- **Clef chạy trên Cloudflare Workers AI.** `.env` đã đổi, backup ở `.env.bak_20261029_clef`. `tests/trip/test_clef_live.py -m live` pass.
- **Bỏ Gemma self-host** vì chiếm GPU dùng chung. Biến `SELFHOST_EXTRACTOR_*` đã comment trong `.env`. Không bật lại; không đặt `EXTRACTOR_ON_SELFHOST` / `EXTRACTOR_ALSO_SELFHOST`. vLLM trên 2 card 11 GB không chạy được vì không còn chỗ cho KV (ledger `2026-10-29-selfhost-vllm`).
- **Mỗi lane Gemma tối đa 38 request đồng thời, tính chung mọi agent.** Còn 2 lane: LAN và UIT. Mỗi bên gọi phải được chia ngân sách riêng. Một process chỉ đặt `EXTRACTOR_ON_UIT=1` sẽ tự lấy đủ 38.
- **DeepSeek R1-Distill (:8899) không dùng cho `asr_check`.** Lý do: khớp Gemma 64 %, để lọt lời bài hát, mất chữ trên màn hình.
- **Job ảnh G3:** chờ chạy hết rồi mới build release.

**Track XONG trong tối** (chưa commit; chi tiết ở ledger `.superpowers/sdd/2026-10-29-<track>/`):
- `asst-core`: guard R1–R8, prompt, khung bench.
- `asst-knowledge`: route/journey thật qua `src/harness/trip_live.py`, 50 ca bench.
- `asst-perceive`: lượt ảnh/link trong engine, 37 ca.
- `asst-decision`: chatbot Lựa chọn trên lõi chung. Dòng nối harness `trip_reader` đã gắn.
- `asst-bench`: Task 1–2. Sửa ảnh băng chuyền nhiều thẻ; giữ `covered_tools: write`.
- `crawl`: G9 phone/website; giá "tối đa X" lưu `min=None, up_to`; G8 thêm 8 vùng Vexere; G6/G10 1.279 nơi dịch vụ.
- `services-tool`: tool `find_services`, bến xe Maps của 10 vùng.
- `dish`: hai nguồn `menu_photo` và `review_order` đã bật, đo trên dữ liệu dở.
- `release-audit`: `wrong` > `correct` là bình thường, không có bug.
- `tiktok-verify`: sửa chuỗi kiểm video; job còn chạy.

**Job nền còn chạy:**
- `logs/crawl_photos_g3.sh` (PID 1736842): runner xong, đang `photo_scenes` (516/3167 lúc 23:34) rồi `index vectors`. Marker `CRAWL_PHOTOS_G3_DONE`.
- `logs/tiktok_verify_followup.sh` (PID 2285355): asr_check / place_verify lần 2 trên UIT, rồi `place_poi` và `clips`. Marker `TIKTOK_VERIFY_FINAL_DONE` trong `logs/tiktok_verify.log`.
- `logs/lodging_price_loop.sh` (PID 742479): chạy mỗi giờ, để nguyên.
- Đã xong: local extract (17:58), dish menu LAN và UIT (19:46), `dish_review_check` (18:38), crawl dịch vụ G6.

**Việc tiếp theo, theo thứ tự:**
1. Khi hai marker trên đã có:
   - Đo crawl-photos sau G3, theo HANDOFF trong ledger `crawl-photos`.
   - `crawl-local`: lượt `local extract` 17:58 có thể chưa gồm 1.312 tài liệu mới của lượt search. Kiểm, nếu thiếu thì chạy lại `local extract` (chỉ tài liệu mới) + `local group`. Sau đó `python -m corpus pulse --city dalat` và cập nhật spec §5B G4/G7.
   - Đo lại dish: `.venv/bin/python .superpowers/sdd/2026-10-29-dish/measure.py`. Nguồn nào cận dưới Wilson < 0,8 thì tắt trong `config/dishes.yaml`.
   - Đo TikTok: `.venv/bin/python .cache/tmp/measure.py`. Mốc trước: 1.172 nơi có bằng chứng, 1.157 có clip.
2. Build lại release theo đúng thứ tự: `python -m corpus gmaps observe --city dalat` (để có G9) → `aggregate` → `serving` → build release (`normalize --rebuild` …). Lần trước lỗi vì crawl ghi file giữa chừng, nên chỉ build khi không còn job crawl nào ghi. Sau build:
   - Bỏ bộ lọc `min_vnd` < 1.000 trong `src/trip/infrastructure/reads.py`.
   - Sửa 7 test planning trượt (5 đã biết + 2) và `test_equivalence`.
   - Chạy lại `tests/decision/test_wish_speed.py` khi máy rảnh.
   - Hiệu chỉnh `rep` 0,3 / `base` / `ref_n` bằng số thật.
3. Bench cuối terra vs sol, cần 9router. Lệnh nằm trong HANDOFF ledger `2026-10-29-asst-bench`. 9router không phải prod, nhưng hỏi chủ dự án trước khi bật riêng nó. Chưa có kết quả thì giữ `AGENT_MODEL=cx/gpt-6.1-terra`.
4. **Hỏi chủ dự án:** guard trên Clef Cloudflare chặn đúng 90,7 % câu R1–R6 (gate 95 %), không chặn nhầm câu nào. Có 4 câu lọt: "em đi khách", "dịch vụ kích dục", "party bay lắc … hàng", "bẫy chim … thú quý hiếm". Cloudflare chấm chúng đúng 0,0. Đề xuất: `CLEF_TIMEOUT_S=4`, và thêm regex vào `input_guard` hoặc viết lại câu hỏi R1–R3.
5. Việc nhỏ còn treo:
   - Ghi chú hai nguồn món mới trong `docs/CORPUS.md`.
   - `docs/LLM_PROVIDER.md`: Clef về Cloudflare, bỏ self-host.
   - Lựa chọn: p90 11,65 s vượt gate 11 s; chat chưa hiện thẻ.
   - Bến xe các vùng còn thiếu (Đồng Nai, Bình Dương, …).
   - `CONTROLLER EDIT record.py` của dish (tùy chọn).
6. **COMMIT** khi xong đợt: tạo branch trước (đang ở `main`), commit theo khu vực, kiểm `.env.example` và file lớn (`.venv-vllm`, `.cache/hf` 16 GiB checkpoint phải nằm ngoài git), không push.
7. Deploy chỉ khi chủ dự án bảo.

**Bổ sung 23:55:**
- **GPU (chủ dự án quyết, cập nhật ~00:05):** chỉ dùng GPU 4 cho Clef flash NF4, GPU 6 và 7 cho mọi việc khác, mỗi card 3 worker. Dồn đầy card rồi mới chuyển việc. Không dùng GPU 0, 3, 5 (của người khác). Đã đặt:
  - `config/index.yaml`: `gpus: [6, 6, 6, 7, 7, 7]`. 4 worker trên một card bị OOM ở 234 nơi.
  - `logs/prod_restart_nobuild.sh`: `HARNESS_GPU=7`.
  - `run.sh` vẫn mặc định `HARNESS_GPU=1,3`: nhớ ghi đè khi chạy.
- **Ảnh G3: XONG.** Bước `index vectors` lúc đầu rải worker ra cả 8 card nên đã bị dừng. Chạy lại trên GPU 7 được 4.439 vector (lỗi 237 nơi do OOM), rồi chạy bù 237/237 nơi với 3 worker, 0 lỗi. Việc còn lại: đo crawl-photos sau G3 theo ledger `crawl-photos`.
- **Việc mới, chủ dự án giao: tăng tốc Clef NF4 mà giữ nguyên độ chính xác.** Server hiện có 1 worker và xử lý tuần tự: 0,33 s/lượt, ~3,1 req/s; 8 lượt cùng lúc thì mỗi lượt ~2,6 s. Script đo: `logs/clef/latency_probe.py <gateway url>`. Thứ tự làm, mỗi bước đều đo độ chính xác lại:
  1. Tắt `bnb_4bit_use_double_quant` trong `scripts/clef_server.py`.
  2. Gộp request vào cùng một lượt forward (batch động).
  3. Prefix cache cho phần câu hỏi cố định.

  Gate: bộ guard 102 câu vẫn 0 chặn nhầm và chặn đúng ≥ 95,3 % (`python -m bench assistant --guard`, env `CLEF_BASE_URL` trỏ gateway thử); `tests/trip/test_clef_live.py -m live` pass; xác suất trả về lệch không đáng kể so với bản hiện tại. Chạy bản thử trên GPU 6 (không đụng GPU 4), đạt rồi mới thay server :30011. Server :30011 do session khác bật; chủ dự án đã cho tối ưu.
- **Clef flash NF4** (`scripts/clef_server.py --quant nf4 --port 30011`, GPU 4, ~8,2 GB; do người khác bật lúc 23:41): đo qua gateway thử `127.0.0.1:30010`, PID trong `logs/clef/gateway_nf4_test.pid`, log `logs/clef/gateway_nf4_test.log`.

  | Timeout | Chặn nhầm (45 câu) | Chặn đúng R1–R6 (43 câu) | Gate |
  |---|---|---|---|
  | 10 s | 0 | 95,3 % | đạt |
  | 4 s | 0 | 95,3 % | đạt |
  | 2 s | 0 | 90,7 % | trượt |

  `test_clef_live` pass. Kết quả ngang bản fp16 cũ và hơn Cloudflare (90,7 %). Muốn dùng: `.env` đặt `CLEF_BASE_URL` = gateway (cổng 30000 với `--clef-url http://127.0.0.1:30011`) và `CLEF_TIMEOUT_S=4`. Chờ chủ dự án đồng ý; hiện `.env` vẫn trỏ Cloudflare. File kết quả: `data/bench/assistant/guard-nf4-t{10,4,2}.json`.

## CHỐT 2026-10-29 chiều — bàn giao từ `tripguardian-31`

Session `tripguardian-31` hết context; chủ dự án sắp đổi account (còn ~34 % usage). Mọi agent đã được dặn dừng ở ranh giới task và ghi `HANDOFF: next = …, state = …` cuối `progress.md`. Đọc dòng đó trước khi giao lại; ledger là nguồn sự thật.

**Chủ dự án quyết hôm nay (không hỏi lại):**
- Trợ lý mới theo spec `docs/superpowers/specs/2026-10-29-assistant-tools-design.md`: terra quyết ý định và chọn tool (chậm chút cũng được), từ khóa / Clef chỉ chạy sẵn vào cache; thẻ hiện trước, chữ sau; lõi chung `src/agents/assistant/` cho cả Tìm hiểu và Lựa chọn; bộ tool dùng hết corpus (§5A), corpus thiếu ghi §5B và crawl bù.
- Rule chặn R1–R8 (spec §4) đã duyệt; câu lạc đề terra tự lái về du lịch; câu du lịch nói thô không chặn.
- Local Expert chạy nền sau chốt lịch (xong, `expert.enabled: true`).
- **Commit khi xong đợt này** (nhiều thay đổi chưa commit): tạo branch trước (đang ở `main`), commit theo khu vực, kiểm `.env.example` và file lớn, không push nếu chưa được bảo.

**Xong trong ngày (ledger `.superpowers/sdd/2026-10-29-<track>/`):** web-user, planning (DP4, Task 9 gỡ đường cũ), profile (thẻ xác nhận bỏ, `patterns.enabled: true`, bất biến "đã đến ≠ đã thích" có test), booking-flights (904 chuyến bay thật, `feasible=True` từ offer, `logs/flight_price_loop.sh` chưa chạy), pulse (+ lỗi gốc "chưa có dữ liệu": context gửi như `system` thứ hai bị 9router bỏ qua → nay là message `user`; bench 11/30 → 1/30), replan-expert (`eve_replan.enabled: true`, 8/8), expert-async.

**Đang dừng giữa chừng (đọc HANDOFF trong ledger):** `asst-core` (lõi + `API READY` đã có, Task 1a/2 xong), `asst-knowledge` (hàm đọc xong, chưa đăng ký hết tool), `asst-perceive`, `asst-decision` (mới bắt đầu), `crawl-photos` (gmaps_b2, G3), `crawl-places` (gmaps_d, G1/G9/G6/G10), `crawl-local` (G4/G7, `local extract`), `crawl-stay-bus` (G5/G8), `dish` (C7/G2). Job nền do các track này khởi động: PID + lệnh dừng trong ledger từng track. Luật crawl chung: `.superpowers/sdd/2026-10-29-crawl-common.md`.

**Ghi chú khi giao lại (17:10):** `asst-core` đã chuyển vòng tool vào `src/agents/assistant/loop.py` (ledger `asst-decision` ghi "core chưa có loop" là trước đó, nay đã có); `tests/trip tests/agents tests/bench` 1.147 pass. `asst-core` còn: Task 3 Clef R1–R8, Task 4 prompt, Task 5 bench, Task 6 bench terra vs sol, docs, xác nhận `cached_tokens` qua 9router (1 lượt). `asst-perceive`: tool xong (71 test), còn nối lượt ảnh trong `engine.py` + slot `photos`/`links`. `crawl-places`: Maps không có giờ cho nơi thiếu giờ (20/20), phone/website đã crawl nhưng chưa vào serving (sửa `observe/gmaps/extract.py` + `serving/record.py`). `crawl-local`: job `local extract` PID 1712601 (`CRAWL_LOCAL_EXTRACT_DONE`), search PID 1726626 (`CRAWL_LOCAL_SEARCH_DONE`).

**Trạng thái cuối 17:20 (mọi agent đã dừng):** `tests/trip tests/agents tests/bench` 1.147 pass (controller chạy lại). Chuỗi build đã `AFTER_CHAIN_DONE` (09:41Z) nhưng `normalize --rebuild` LỖI "source changed during release build: …/photos.json" vì `crawl-photos` ghi ảnh mới cùng lúc; aggregate/snapshot/index đã chạy; `data/releases/current` vẫn là bản 28/10. Build lại release SAU khi các job crawl dưới đây xong (đừng build khi chúng còn ghi). Job nền đang chạy, không tốn token: `crawl-photos` `logs/crawl_photos_g3.sh` PID 1736842 (`CRAWL_PHOTOS_G3_DONE`, dừng `touch logs/crawl_photos_g3.stop`); `crawl-local` extract PID 1712601 (`CRAWL_LOCAL_EXTRACT_DONE`) + search PID 1726626 (`CRAWL_LOCAL_SEARCH_DONE`); `dish` `logs/dish_menu_read.sh` PID 1741764 (`DISH_MENU_READ_DONE`, dừng `touch logs/DISH_MENU_READ.stop`); vòng giá phòng PID 742479 (đã sửa parser Google Travel, giá đổi dạng hiển thị). Gemma LAN đang dùng 24 + 8 + 6 = 38. `asst-knowledge`: 12 tool đọc + `save_place`/`hide_place` đã đăng ký (59 test); còn nối `LiveTools.route`/`journey` trong `src/harness/__main__.py` (chưa nối thì `route_time`, `journey`, `distance(mode)` trả "unavailable"), bench, docs, thử trên dữ liệu thật. `crawl-stay-bus`: G8 xe khách chưa làm. `crawl-places`: G6/G10 chưa làm.

**Job nền khác:** chuỗi build `logs/gmaps_coverage_observe_restart.sh` (PID 646823; đang build release; xong khi `logs/gmaps_coverage_after.log` có `AFTER_CHAIN_DONE`; KHÔNG publish); vòng giá phòng `logs/lodging_price_loop.sh` (PID 742479, dừng `touch logs/lodging_price_loop.stop`); OSRM container.

**Việc tiếp theo, theo thứ tự:**
1. Đọc HANDOFF của từng ledger trên; giao lại track còn dở (mỗi track một agent Sonnet, brief sẵn trong thư mục track): `asst-core` trước, rồi `asst-knowledge` + `asst-perceive`, rồi `asst-decision`; các track crawl chỉ cần trông job.
2. Sau `AFTER_CHAIN_DONE`: kiểm release mới. Bước judge audit cho nhãn `wrong` 36.180 > `correct` 32.432: xem có bình thường không trước khi đề xuất publish.
3. Sau khi crawl bù xong: `python -m corpus serving` + build release; sửa 5 test planning trượt vì dữ liệu mới (`test_planning_realism[travel_vs_nn, overload_explained]`, `test_planning_overload_round1[rainy_month]` ×2, `test_planning_better_order`) và `test_equivalence` (snapshot cũ 16/10); hiệu chỉnh `rep` 0,3 / `base` / `ref_n` (quyết định 10); C2 `gmaps resolve`; rồi `corpus-next` (C4, C8, P6, P8, SearXNG).
4. Bench cuối terra vs sol (Tìm hiểu + Lựa chọn) do `asst-core` chạy; model tốt hơn lên prod.
5. Commit (xem trên). Deploy chỉ khi chủ dự án bảo (memory `prod-deploy-runbook`; viết script restart để chủ dự án chạy bằng `!`): chạy lại `python -m corpus pulse`, `make_thumbs.py`, restart harness :8769 + notify worker.

## CHỐT 2026-10-29 trưa (đọc mục này trước mục 2026-10-28)

**14:00 chuyển giao:** chủ dự án giao toàn bộ việc còn lại cho session `tripguardian-31`. Session `tripguardian-b3` đã dừng, không còn agent nào chạy. Chuỗi build đang chạy là `logs/gmaps_coverage_observe_restart.sh` (observe trên LAN 38 + UIT 38 + self-host 8, trần riêng cho từng endpoint). Việc còn mở nằm ở dòng HANDOFF cuối ledger từng track `2026-10-29-*`.

**Chủ dự án đã quyết mọi mục chờ.** Toàn bộ quyết định nằm trong `.superpowers/sdd/2026-10-29-final-wave/common.md` (§Owner decisions, 13 mục). Không hỏi lại. Tóm tắt: trợ lý đổi sang `cx/gpt-6.1-terra`, đo rồi lên prod model tốt hơn; banner D.3 làm lại thành thẻ ảnh kiểu thẻ lựa chọn của Trip Understanding, có animation, không hiện nguồn Open-Meteo; lọc khớp nhầm rồi nâng `mining_map.json`; crawl Google Flights; nâng precision món rồi bật; thêm dòng tiền phòng riêng (chỉ cảnh báo); Local Expert dùng Gemma LAN, UIT dự phòng; A.5 làm đủ spec, crawl định kỳ ghi vào gaps; E.2 chỉ làm bậc 1 "Đi một vòng", spike 3D để sau prod; ngưỡng do agent tự hiệu chỉnh bằng số liệu; hồ sơ kiểu bộ nhớ ChatGPT, cá nhân hóa ngầm, bỏ thẻ "Lần trước bạn nói…" (hồ sơ vẫn chỉ là prior); tạo DB `tripguardian_test`; bỏ affiliate.

**Host Gemma LAN** là `http://192.168.20.150:8900/v1` (vLLM, 38 luồng). `:9090` chỉ là trang Vite. `.env` đã sửa, bản sao lưu `.env.bak_20261029_8900`. Chuỗi build 928979 (qc trên self-host 8) đã thay bằng `logs/gmaps_coverage_after_lan.sh` (qc LAN 38 → observe LAN 38 + UIT 38 → build → normalize, không publish). Xong khi `logs/gmaps_coverage_after.log` có `AFTER_CHAIN_DONE`.

**Đang chạy (session 2026-10-29, chủ dự án còn ít usage nên chỉ 4 track nhỏ):** `assistant-terra`, `tests-infra` (T1, T2, T3), `web-eve-notes` (W2 banner thẻ ảnh + W3), `mining-map-claims` (C1 + C6). Ledger: `.superpowers/sdd/2026-10-29-<track>/progress.md`.

**Cập nhật 2026-10-29 13:20 (session `tripguardian-31`):** 4 track trên đã xong (ledger từng track). Đã giao 6 track Sonnet chạy nền, mỗi track có `brief.md` + `progress.md` trong `.superpowers/sdd/2026-10-29-<track>/`: `profile` (mục 2, thêm W1), `planning` (mục 3), `replan-expert` (mục 4), `booking-flights` (mục 5), `web-user` (mục 6 trừ W1), `pulse` (mục 7 phần A.5). Chờ `AFTER_CHAIN_DONE` (từ 13:23 chuỗi là `logs/gmaps_coverage_observe_restart.sh`, PID 646823, observe trên LAN 38 + UIT 38 + self-host 8) mới giao: mục 1, `dish` C7, `corpus-next`. Session khác: đọc dòng cuối các ledger này trước, đừng giao trùng. **~13:55:** `tripguardian-b3`/`-75` nhận rồi trả lại; từ ~14:00 `tripguardian-31` điều phối mọi việc 2026-10-29 còn lại (agent của b3 đã dừng; ghi chú chia việc trong `NOTE_DUPLICATE.md` của profile và booking-flights).

**Cập nhật 2026-10-29 ~16:45 (`tripguardian-31`):** xong `web-user`, `planning`, `profile`, `booking-flights`, `pulse` (gồm sửa lỗi gốc: dữ liệu chuẩn bị gửi như `system` thứ hai bị 9router bỏ qua), `replan-expert` (`eve_replan.enabled: true`, 8/8). Chủ dự án duyệt thiết kế trợ lý mới + rule chặn R1–R8: spec `docs/superpowers/specs/2026-10-29-assistant-tools-design.md` (lõi chung `src/agents/assistant/` cho Tìm hiểu và Lựa chọn, bộ tool dùng hết corpus, §5B corpus còn thiếu). Đang chạy: `asst-core`, `asst-perceive`, `asst-knowledge`, `expert-async`; `asst-decision` giao khi `asst-core` ghi `API READY:`. Ledger `.superpowers/sdd/2026-10-29-<track>/`.

**Cập nhật ~17:00:** `expert-async` xong (Local Expert chạy nền sau chốt lịch, `expert.enabled: true`). Đang chạy thêm: `asst-decision`, crawl bù corpus `crawl-photos` (gmaps_b2, G3), `crawl-places` (gmaps_d, G1/G6/G9/G10), `crawl-local` (G4/G7, `local extract` 785 Document), `crawl-stay-bus` (G5/G8), `dish` (C7/G2); luật chung `.superpowers/sdd/2026-10-29-crawl-common.md`. **Việc cho lượt release:** 5 test planning đọc `data/serving/places.json` thật trượt sau khi chuỗi build ghi lại file lúc 16:15 (`test_planning_realism[travel_vs_nn, overload_explained]`, `test_planning_overload_round1[rainy_month]` ×2, `test_planning_better_order`); ví dụ ngày 1 đi đường 118′ trong khi xếp gần-nhất 98′. Lúc 15:00 trên dữ liệu cũ pass. Xử lý sau khi dữ liệu crawl bù xong và build release, cùng `test_equivalence`.

**Hoãn tới sau reset usage (làm theo thứ tự, mỗi track một agent, brief chung là file common.md ở trên):**
1. Sau `AFTER_CHAIN_DONE`: C3 `python -m corpus serving` + build release; hiệu chỉnh `rep` 0,3 và `base`/`ref_n` bằng số thật; C5 `corpus local extract` 785 Document trên LAN 38; C2 `gmaps resolve` thật.
2. `profile`: DP1, DP2, cá nhân hóa ngầm (quyết định 11), bỏ thẻ xác nhận.
3. `planning`: DP3 (#1, #2, #4, #10), DP4 dòng tiền phòng.
4. `replan-expert`: DP5, DP6, D.2 Local Expert (Gemma LAN). Bật `eve_replan.enabled` khi UI thẻ ảnh xong.
5. `booking-flights`: crawl Google Flights, B1, B2, hiệu chỉnh `config/journey.yaml` bằng tuyến thật.
6. `web-user`: W1 màn "Hồ sơ của tôi" (theo quyết định 11), W4 khung "Đường tới Đà Lạt", W5 carousel `scene_photos` + `make_thumbs.py`, E.2 bậc 1.
7. `dish`: C7 (quyết định 5). `pulse`: A.5 + bản tin UI + tool chatbot; ghi crawl định kỳ vào gaps.
8. `corpus-next`: C4 (`logistics.py` xếp theo danh tiếng, aggregate mang rating/reviews), C8, N1 P6, N3 P8, N5 SearXNG.
8b. Banner D.3 thẻ ảnh đã xong (`frontend_images/eve-banner-cards-level{2,3}.png`), còn: tên nơi dài/thô ("ĐÔI DÉP Camellia Tea Spa, Massage | Đà Lạt (달랏…)") → dùng tên ngắn sạch; tiêu đề phương án còn là `text` server, viết lại cho người; ảnh bìa trên thẻ chưa kiểm `person=no`; chưa thử trên `/plan` thật với `/eve` thật.
8d. Trợ lý đã đổi sang `cx/gpt-6.1-terra` trong `.env` (bench 30 câu: p50 4,02 s / p90 5,34 s, sol 4,63 / 6,62 s; cùng 29/30 nhóm, 0 số không nguồn). Prod chưa restart. Navigator, Decision, Planning cũng theo `AGENT_*` nên giờ chạy terra, chưa test ở đó: chạy test/bench của chúng trước deploy. Quay lại sol: `.env.bak_20261029_terra`.
8c. Test còn trượt sau tests-infra (ledger `2026-10-29-tests-infra`): `tests/decision/test_equivalence.py::test_equivalence_eval_trips_on_the_real_snapshot` (shortlist lệch, nghi do `rep` 0,3 — xét khi hiệu chỉnh ngưỡng); `tests/web/test_landing_3d_structure.py` (landing mất câu "Khám phá bản đồ Đà Lạt"); `test_wish_speed` (flaky khi tải). Test Postgres cần nạp `.env` (`set -a; . ./.env; set +a`).
9. Release + deploy production (memory `prod-deploy-runbook`; viết script restart để chủ dự án chạy bằng `!`).

## CHỐT 2026-10-28 ~21:15 (chủ dự án hết token, kết thúc session; session sau đọc mục này trước)

**Agent nền:** agent Trip vòng 5 (Opus) đã dừng đúng yêu cầu lúc 21:16 và ghi `Trip r5 HANDOFF 21:16` vào ledger chatbot. Còn chạy: agent `NoPeople` (Sonnet, luật không hiện ảnh người). **Trip vòng 5, kết quả:** giữ (1) ánh xạ tên nơi sol viết ("lululola", "Hồ Tuyền Lâm") sang id corpus trước khi chạy tool, tên không khớp hoặc khớp nhiều nơi trả lỗi "không có dữ liệu, đừng đoán" thay vì tốn lần gọi thứ hai (`prefetch.place_id`, `TurnTools._place_ids`); (2) sửa lượt đầu chậm: SigLIP2 nạp hai lần lúc khởi động, nay mỗi model nạp một lần, engine chạy một lượt tìm khi khởi động (`warm_assistant`, `Engine.warmed`), lượt chậm nhất còn 15,4 s (trước 55–118 s). Bench chạy thật (OSRM bật, `data/bench/assistant/20261028-211457-live.json`): p50 8,92 s, p90 13,43 s, 1,47 lần gọi/lượt, 0 số không có nguồn, 29/30 nhóm; 1.015 test pass. Phát hiện chính: 8 lượt chậm nhất đều là câu tìm nơi, vì lượt tìm chạy trước lần gọi model không xong trong `prefetch_wait_s` (1,2 s) nên sol tìm lại và cần lần gọi thứ hai 4–6 s. **Bước tiếp:** cho tìm nơi chờ lâu hơn (~2 s) rồi bench lại; sau đó thử `covered_tools: "write"` (chỉ đưa `record_fact` khi dữ liệu chuẩn bị đã trả lời câu hỏi; đã code và test, tắt mặc định, chưa đo; ghi Ruling). Một lần gọi sol: p50 5,2 s, p90 6,8 s (3,3–8,6 s); lượt một lần gọi có trung vị 7,15 s, nên p50 ≤ 7,5 s cần gần như mọi lượt chỉ một lần gọi (chủ dự án đã quyết tạm không đổi model). Chưa làm: cập nhật `docs/TRIP_UNDERSTANDING.md`, `docs/LLM_PROVIDER.md`, đo lại persona "vague".

**Job nền còn chạy** (kiểm bằng `ps -p <PID>`; log nằm ở `logs/`):

| Job | PID | Log / dấu hiệu xong | Dừng |
|---|---|---|---|
| OSRM (container `tripguardian-osrm`, :5000, tự khởi động lại) | — | `docker ps` | `docker stop tripguardian-osrm` |
| Giá phòng mỗi giờ `logs/lodging_price_loop.sh dalat` | 742479 | `logs/lodging_price_loop.log` | `touch logs/lodging_price_loop.stop` |
| Chuỗi TikTok `logs/tiktok_web_videos_chain.sh web1 dalat` (asr → check → verify → place_poi → vòng poi → clips) | 815404; ASR shard 819829–819832 | `logs/tiktok_web_videos_web1.log`, xong khi có `CHAIN_DONE` (~1–3 giờ); chạy lại an toàn bằng cùng lệnh | `kill 815404` TRƯỚC, rồi các shard |
| Chuỗi crawl Maps `logs/gmaps_coverage_chain.sh` (profile `gmaps_b2`, cổng DevTools 9540) | 801719 (runner 801725) | `logs/gmaps_coverage_dalat.log`; xong khi có `COVERAGE_CHAIN_DONE` | `kill 801719 801725` rồi con python |
| Chuỗi build sau crawl `logs/gmaps_coverage_after.sh` (qc, photo_observe, style_observe, observe với 38 UIT + 8 self-host, rồi `corpus build` + `normalize --rebuild`, KHÔNG publish) | 928979 | `logs/gmaps_coverage_after.log`, xong khi có `AFTER_CHAIN_DONE` | `kill 928979` |

Dùng PID, không dùng `pkill -f` với mẫu nằm trong dòng lệnh của chính mình. Captcha: tab chờ người giải, không tự giải (cổng 9540 cho Maps).

**Sau khi các chuỗi xong, việc cho session sau:** đọc ledger từng track, kiểm release mới (`data/releases/`, chưa publish; chủ dự án quyết publish), cập nhật bảng độ phủ "sau". Chưa phần nào lên prod; deploy chỉ khi chủ dự án bảo.

**Chủ dự án đã trả lời lúc 21:20:** (4) KHÔNG được hiện ảnh có người ở bất kỳ đâu trên thẻ nơi: agent Sonnet `NoPeople` (effort medium) đang siết luật (chỉ hiện ảnh gắn `person=no` đủ tin cậy, loại cảnh `crowd`, lọc cả ảnh bìa cũ, cả carousel Trip), ledger dòng `NoPeople` trong `.superpowers/sdd/2026-10-28-media-scenes/progress.md`; (3) tạm thời KHÔNG đổi model của trợ lý; (2) việc dùng `gmaps_d` để tôi chọn theo hướng nhanh nhất: giữ cho crawl nơi mới sau chuỗi TikTok, và chia đôi hàng đợi sâu chỉ khi chủ dự án chọn nới luật ở mục 1; (1) chủ dự án hỏi hàng đợi sâu có giá trị gì: xem trả lời bên dưới, chưa quyết.

**Hàng đợi sâu (80 nơi + 10 chỗ ở, mỗi nơi > 1.900 review, đang giữ 200):** đây là những nơi đông khách nhất nên nhiều người sẽ chọn nhất. Giá trị nếu lấy được: tăng mẫu review từ 200 lên khoảng 500–1.100 mỗi nơi (Maps dừng tải ở mức đó), giúp thêm bằng chứng cho đông/vắng theo giờ, sạch sẽ, chỗ đậu xe, từ khóa hiếm. Giá trị thực hiện nay là 0, vì luật `too_few` loại cả 3 lần thử. Nếu nới luật thì mỗi nơi có thêm ~300–900 review (≈ 56.000 review mới cho `observe`) nhưng tốn 6–7 giờ một tài khoản (≈ 3–4 giờ nếu chia với `gmaps_d`). Đề xuất của tôi: các nơi này đã có 200 review nên đã đủ cho phần lớn đặc trưng; giữ nguyên luật và bỏ hàng đợi sâu, dùng `gmaps_b2` và `gmaps_d` cho nơi mới. Chỉ nới nếu chủ dự án thấy thiếu bằng chứng ở các nơi đông khách.

**Quyết định còn chờ chủ dự án:**
1. Hàng đợi crawl sâu của Maps (80 nơi + 10 chỗ ở, > 1.900 review mỗi nơi; kỳ vọng gần như không thêm review, 6–7 giờ): bỏ (đề xuất), nới luật `too_few` (≥ 900 review khi đã tới tín hiệu kết thúc), hay hạ trần ~1.000.
2. Dùng tài khoản `gmaps_d` (tripguardian1010) làm gì: crawl Maps cho nơi mới từ TikTok/web (đề xuất, sau khi chuỗi TikTok xong) hay chia đôi hàng đợi sâu.
3. (đã quyết: tạm thời không đổi model.)
4. (đã quyết: không hiện ảnh người; agent NoPeople đang làm.)
5. Câu báo người dùng cho nơi trong vùng hạn chế; gate không gian E.2; xoá `.cache/nfs-stuck-20261028/` khi NFS hồi (cần admin/reboot).

**Quy tắc cho session sau (đã lưu bộ nhớ):** subagent mặc định Sonnet (không truyền `model`), Opus chỉ khi đề xuất và chủ dự án đồng ý; effort chọn theo độ khó (low/medium/high); giữ agent đang chạy để tận dụng cache nhưng không chờ hết hạn rồi mới đổi; không commit; được tự cài thư viện vào `.venv`; giao diện mới dựng trên component của chủ dự án (ảnh ứng viên trước khi giao).

## Cách làm (chủ dự án đã chốt)

- Làm luôn mọi phần làm được. Mỗi track một subagent (Opus hoặc Sonnet tuỳ độ khó), không chia nhỏ theo task.
- Dùng tiếp agent đang chạy để giữ prompt cache, không đặt ngưỡng context cứng. Chỉ đổi sang agent mới khi agent đã nằm yên quá lâu (cache hết hạn) hoặc việc mới không liên quan tới context nó đang giữ.
- Brief chung cho mọi subagent: `.superpowers/sdd/2026-10-28-wave-common.md`. Mỗi track có `brief.md` + `progress.md` trong `.superpowers/sdd/<track>/`. Ledger là nguồn sự thật, tin ledger hơn trí nhớ.
- Working tree dùng chung: không commit, không `git add`. Được tự cài thư viện vào `.venv` hoặc `web/`.
- Phần web mới dựng trên component sẵn có của chủ dự án. Thiết kế còn mơ hồ thì đưa ảnh chụp ứng viên cho chủ dự án xác nhận trước.
- Trình duyệt chạy ngoài sandbox Bash. Captcha do người giải: báo cổng DevTools, không tự giải.
- Search: SearXNG → gsearch (profile `gmaps_a`, đã đăng nhập) → SerpApi (≤ 200 lượt/tháng).

## Đã xong trong ngày (chỉ để tham chiếu)

| Track | Kết quả | Ledger |
|---|---|---|
| Corpus P1 lớp đọc (`card`, `find`) | xong; release `r-3526a43a…` đã publish | `.superpowers/sdd/2026-10-28-corpus-serving-for-sol-and-decision/` |
| Corpus P2 module `web` + Document | xong, có SerpApi dự phòng | `.superpowers/sdd/2026-10-28-corpus-p2-web-documents/` |
| Corpus P5 view khí hậu / lịch / vùng hạn chế | xong; ngưỡng mưa 2,5 mm | `.superpowers/sdd/2026-10-28-corpus-p5-views/` |
| P0 trình duyệt treo | xong: file Chromium kẹt trên NFS, đã cài lại | `.superpowers/sdd/2026-10-28-browser-search/` |
| gsearch (Google qua trình duyệt) | xong; 0/30 captcha trên `gmaps_a` | như trên |
| Lựa chọn Task 8–9 + bảo đảm mỗi mong muốn có nơi trong "Hợp nhất" + web lọc/Thích | xong, đã review | `.superpowers/sdd/2026-10-28-trip-decision-chatbot/progress-decision.md` |
| Planning D.1: lịch đầu p95 | 2,95 s → 1,47 s | `.superpowers/sdd/2026-10-28-planning-d1-speed/` |

## Đang chạy lúc bàn giao (kiểm trước khi làm tiếp)

Subagent nền thuộc session `tripguardian-77`; session đó đóng thì chúng dừng theo. Kiểm theo thứ tự: dòng cuối ledger → `ListAgents` → tiến trình (`pgrep -af corpus`, `docker ps`).

| Việc | Còn lại | Ledger / log |
|---|---|---|
| Chatbot Trip: tốc độ (vòng 3 đã xong, chưa đạt) | Vòng 3 đã làm: ẩn `search_places` và tool ngày, dừng lượt khi mọi lần gọi tool đều trả từ cache, tối đa 2 lần gọi sol mỗi lượt. Bench chạy thật: p50 13,2 s / p90 16,7 s, trung bình 1,67 lần gọi mỗi lượt, 0 số không có nguồn. Cổng là p50 ≤ 7,5 s, p90 ≤ 11 s. Một lần gọi sol qua 9router mất 3,7–10,2 s, nên một lần gọi là đã vượt cổng. Chờ chủ dự án chọn hướng (`service_tier` priority / prompt trả lời ngắn / trả lời không gọi tool khi dữ liệu đã đủ / model nhanh hơn). Cờ `assistant.enabled` vẫn tắt. Còn đo lại persona "vague". | `.superpowers/sdd/2026-10-28-trip-decision-chatbot/progress.md` |
| Crawl web + TikTok | Nối gsearch vào `web`; `corpus web all` cho Đà Lạt; phase mới `tiktok web_videos`; chạy lại vòng `logs/tiktok_poi_loop.sh` nếu còn việc. Job nền ghi trong ledger. | `.superpowers/sdd/2026-10-28-crawl-web-tiktok/progress.md` |
| Crawl giá phòng | Module `gtravel` + `tripcom`; chạy thật trên khoảng 30 chỗ ở; vòng lặp mỗi giờ chạy nền | `.superpowers/sdd/2026-10-28-crawl-lodging-price/progress.md` |
| OSRM | Tải bản đồ VN → extract/partition/customize → container `tripguardian-osrm` ở `127.0.0.1:5000` | `logs/osrm_setup_20261028.log`; kiểm bằng `curl "http://127.0.0.1:5000/route/v1/driving/108.44,11.94;108.45,11.95"` |

Khi OSRM chạy: chạy lại `tests/planning/bench_realistic.py` (số đo trước đây đều đo lúc OSRM tắt) và bench trợ lý (câu hỏi khoảng cách).

### Cập nhật 2026-10-28 ~20:00: thêm ba track Sonnet mới (đều chạy nền, ledger trong `.superpowers/sdd/`)

| Track | Việc | Ledger |
|---|---|---|
| Trip speed vòng 4 | Chủ dự án chọn: `service_tier: priority` + prompt dặn trả lời ngắn; bench chạy thật; chỉ bật cờ nếu đạt cổng | `2026-10-28-trip-speed-r4/` (dòng `Trip r4` trong ledger chatbot) |
| Crawl Maps đủ độ phủ | Kiểm độ phủ từng phase (menu, photos, keywords, visit, crawl, observe, photo_observe, style_observe), chạy phần thiếu nền, KHÔNG dùng profile `gmaps_a`, build release nhưng không publish | `2026-10-28-crawl-gmaps-coverage/` |
| Media A.6 | Nhãn cảnh + có người + trùng + mờ cho ảnh; ảnh tốt nhất mỗi cảnh vào serving; đích ≥ 3 cảnh/nơi; ảnh tốt nhất cũng làm ảnh bìa + gallery 4 cảnh cho thẻ Lựa chọn (chỉ hiển thị, giữ ảnh cũ nếu chưa có nhãn) | `2026-10-28-media-scenes/` |

Hai track crawl web+TikTok và giá phòng bị ngắt vì hết token lúc ~16:50 và đã mở lại bằng agent Sonnet mới lúc 19:50 (ledger giữ nguyên). Việc 1 (Media) bên dưới đã giao.

### Trạng thái tạm 2026-10-28 20:35 (cập nhật lại khi cả 5 agent nền xong)

Agent nền (Sonnet, chạy trong session `tripguardian-1e`): web+TikTok, giá phòng, crawl Maps độ phủ, media A.6, Trip tốc độ vòng 4. Session mới: đọc dòng cuối ledger của từng track trước, rồi mới quyết có mở lại track nào không.

- **Web + TikTok (agent XONG 20:55, đã kiểm; chuỗi nền còn chạy):** gsearch đã nối vào `web` (SearXNG → gsearch khi bị chặn/< 3 kết quả → SerpApi chỉ khi cả hai rỗng; Trip không mở trình duyệt). `corpus web all --city dalat`: 129 query, 1.697 kết quả, 627 video TikTok mới (`tiktok_urls.jsonl`), 853 URL tài liệu, 746/814 tài liệu đọc được; Google CSE trả 118/129 trang, gsearch 8, không tốn SerpApi. Phase `tiktok web_videos`: 622 video mở bằng 3 tab, 0 captcha; 244 (39 %) có `poi`, 121 trong số đó chỉ là khu vực hành chính, 56 ánh xạ vào nơi đã có, 29 chỉ có tên ứng viên, 85 tải về → 76 nơi Maps mới có video. ASR: thêm chờ-thử-lại khi CUDA OOM (30 s × tối đa 120), chạy tới 4 shard mỗi GPU trống (1 shard ~39 video/phút → 4 shard ~148 video/phút trên GPU 6, 4,1 GiB); các dòng OOM cũ trong `data/tiktok/errors.jsonl` chỉ là log, ASR tự lấy lại video chưa có transcript. Không batch (ChunkFormer `batch_decode` mất timestamp mà `asr_check`/`place_verify` cần). 109 test crawl pass (tiktok/web/gsearch). **Job nền:** `logs/tiktok_web_videos_chain.sh web1 dalat` (PID 815404, log `logs/tiktok_web_videos_web1.log`, kết thúc khi log có `CHAIN_DONE`; chạy lại an toàn bằng cùng lệnh) gồm asr (4.799 video, ~35 phút) → asr_check → asr_alt → place_verify → place_poi → vòng poi → verify → clips (cả chuỗi ~1–3 giờ); ASR shard PID 819829–819832. Dừng: `kill 815404` TRƯỚC, rồi kill các shard. Vòng `tiktok_poi_loop.sh` hết hàng đợi (709/709) nên không chạy lại riêng.
- **Giá phòng (XONG 20:50, agent báo cuối, đã spot-check):** 5/5 task, 189 test pass (`tests/crawl tests/serving`). Google Travel chính (URL dựng từ CID của `fid` + tham số `ts`, giá "từ" mỗi đêm đã gồm thuế), Trip.com đối chiếu (HTTP, ~12 khách sạn nổi bật mỗi lần gọi). Chạy thử 30 chỗ × 2 ngày: 28/60 cặp có giá (47 %), 24 cặp không có đề nghị đặt (ghi `null`, không phải `false`), 8 cặp trang không tải xong; 17/30 chỗ ở có giá ≥ 1 ngày; 0 captcha; 4,0 s mỗi cặp. Vòng giờ đầu: 170 giá / 44 chỗ ở trong `data/serving/stay_prices/dalat.json` (trung vị ~616.000 đ/đêm). Còn mở: kiểm ngân sách online chưa đọc `stay_prices` (đã có `stay_prices.load(city, max_age_h)`); mỗi lượt tối đa 120 trang, giá có thể cũ khoảng 1 ngày (mỗi dòng có `observed_at`); 13–17 % trang không tải xong dưới tải máy cao, thử lại lượt sau. Vòng lặp: `logs/lodging_price_loop.sh dalat`, PID 742479, dừng bằng `touch logs/lodging_price_loop.stop`.
- **Giá phòng (cũ):** vòng lặp mỗi giờ `logs/lodging_price_loop.sh dalat` chạy từ 20:19 (dừng: tạo file stop như ledger ghi); chạy thử đầu: 100 giá / 39 chỗ ở; dữ liệu publish ở `data/serving/stay_prices/dalat.json`.
- **Crawl Maps độ phủ (agent XONG 21:10; chuỗi nền còn chạy):** kiểm độ phủ rồi chạy phần thiếu. dalat 1.779 nơi: menu 16/16, keywords 3/3, photos 6/8 (2 nơi lỗi selector ×3), trang chính thức dalat 243/288 và dalat_stay 234/284 (còn lại là web chết DNS/SSL). Chỉ `gmaps_b2` còn đăng nhập (SID tới 11-20); `gmaps`, `gmaps_b`, `gmaps_s*` đã đăng xuất → chạy 1 runner, 4 tab, cổng DevTools 9540. Phase `visit` sửa lỗi (khối `div.C7xf8b` cao 0 nên chờ "visible" không xong → đổi sang `attached`) nhưng KHÔNG chạy hàng loạt: với 6 nơi nhiều review nhất Maps không in dòng "thường dành … ở đây", khớp `docs/plans/CORPUS_HANDOFF.md:234`; đã xoá mọi `visit.json` đã ghi; nếu Maps in lại dòng đó: `GMAPS_PROFILE=gmaps_b2 GMAPS_PHASES=visit GMAPS_CITY=dalat scripts/gmaps_runner.py`. Hàng đợi `crawl`: 80 nơi dalat + 10 chỗ ở đều > 1.900 review (đang giữ 200/trần 5.000); Maps ngừng tải ở ~490–1.160 review nên luật `too_few` (< nửa số hiển thị) loại cả 3 lần thử; kỳ vọng gần như không thêm review; ETA 6–7 giờ cho dalat rồi tới chỗ ở; `GMAPS_STALL_S=7200` đã đặt (mặc định 10 phút sẽ giết và chạy lại mãi). Luật fail-closed giữ nguyên; muốn nới thì chủ dự án quyết (nhận danh sách đã tới tín hiệu kết thúc ở ≥ 900 review, hoặc hạ trần ~1.000). Chuỗi Gemma: `qc` trên self-host (song song 8) cùng `photo_observe` → `style_observe` trên UIT (38); sau đó `observe` với `EXTRACTOR_ALSO_UIT=1` (8 + 38); rồi `corpus build --skip tiktok "gmaps qc" "gmaps observe" "gmaps photo_observe"` + `normalize --rebuild` KHÔNG publish. **Job nền:** `logs/gmaps_coverage_chain.sh` PID 801719 (runner 801725; dừng: `kill 801719 801725` rồi con python; captcha chờ người giải ở cổng 9540: `ssh -L 9540`, `chrome://inspect`); `logs/gmaps_coverage_after.sh` PID 928979 (chờ `COVERAGE_CHAIN_DONE`, log `logs/gmaps_coverage_after.log`, xong khi có `AFTER_CHAIN_DONE`; dừng `kill 928979`). Bảng độ phủ "sau" và số req/s từng làn Gemma sẽ có ở `logs/gmaps_coverage_{qc,photo_observe,style_observe,observe}.log` và ledger `.superpowers/sdd/2026-10-28-crawl-gmaps-coverage/progress.md`. TikTok theo nơi: place_search còn 793, asr 4.730 (đã có chuỗi của track web+TikTok), place_filter 4.601 video chưa xét. `data/releases/current` chưa đổi.
- **Media A.6 (agent XONG 21:15, đã review + 22 test pass):** nhãn từng ảnh ở `data/gmaps/photo_scenes/<fid_dir>.json` (raw `photos.json` không đổi): cảnh (11 loại + `unknown`), có người (yes/no/null + độ tin), mờ/tối, trùng gần (cos ≥ 0,95 trên vector SigLIP2 có sẵn). 33.072/33.072 ảnh đã gắn nhãn (100 %), 3.166/3.172 nơi (6 nơi không có ảnh); nơi có ≥ 3 cảnh dùng được: **46,5 % (1.475)** (chỗ ở 900/1.525, quán ăn 400/1.015, điểm tham quan 120/394; thiếu là do dữ liệu ~10 ảnh/nơi, không do bộ lọc). Kiểm tay 100 ảnh ngẫu nhiên (25 nơi, một người xem): cảnh đúng 96/100, người đúng 96/100; trong 64 ảnh gắn "không người" có 63 đúng (`logs/scenes_sheet/`). Serving: `corpus.serving.scenes` (`for_place`, `pick`, `coverage`) và `RetrievalEngine.scene_photos(place_id)`; `card()` cho LLM không đổi. Thẻ Lựa chọn có thêm `photos` (≤ 4 cảnh, ảnh bìa đầu tiên, không người, không mờ/tối, đã bỏ trùng; nơi chưa nhãn → `[]` và web giữ ảnh cũ; không đọc điểm/thứ hạng); web đặt ảnh cảnh trước gallery cũ ở thẻ, đĩa và sheet, không đổi bố cục. Gemma: lần chạy đầy đủ dùng UIT 12 slot; `config/scenes.yaml` `label.parallel` giờ là null (mặc định 38); không còn job nào chạy; chạy lại cùng lệnh khi có ảnh mới (nơi đã xong nằm cache). Không rebuild release (nhãn đọc thẳng từ `data/gmaps/photo_scenes`, ngoài snapshot). Còn mở: (a) ảnh chụp màn hình thẻ Lựa chọn (`frontend_images/lua-chon-anh-theo-canh-luoi.png`) có thẻ thứ 3 (Atispho) hiện ảnh nhiều người ngồi — kiểm xem đó là ảnh bìa cũ (nơi chưa nhãn) hay nhãn "không người" sai; (b) carousel chat Trip chưa dùng `scene_photos` (nơi không nằm trên thẻ Lựa chọn vẫn dùng ảnh cũ); (c) chưa chụp ảnh màn đĩa xoay; (d) chạy `web/scripts/make_thumbs.py` trước lần build production tới (ảnh cảnh dùng bản gốc 768 px khi chưa có WebP); (e) ngưỡng mờ (blur < 100, dark < 55) đặt trên 310 ảnh, chưa có ảnh mờ thật, chỉnh được lúc chọn ảnh không cần gắn nhãn lại; (f) kế hoạch video (tăng tải lên ~30/nơi, gắn nhãn keyframe) chỉ ghi trong ledger, phụ thuộc track TikTok.
- **Trip tốc độ vòng 4:** `service_tier: priority` + prompt ngắn; chưa có số đo; `assistant.enabled` vẫn `false`.
- **OSRM** chạy (container `tripguardian-osrm`). Bench Planning khi có OSRM: lịch đầu p95 1,33 s; `twenty_in_2` max 3,4 s; đổi chỗ ở max 0,85 s (`logs/planning_realistic/bench_d1_osrm_on.txt`).
- **Subagent mặc định Sonnet**, effort theo độ khó (xem memory `sdd-token-economy`): không truyền `model`; Opus chỉ khi đề xuất và được chủ dự án đồng ý.

### Tài khoản Google cho crawl (kiểm 2026-10-28 21:08, bằng cách mở trang tài khoản từng profile)

| Profile | Tài khoản | Dùng cho |
|---|---|---|
| `gmaps_a` | hoangluanho90@gmail.com | gsearch (Google search qua trình duyệt); không dùng cho crawl Maps |
| `gmaps_b2` | nghuongcute2122@gmail.com | chuỗi crawl Maps đang chạy (cổng DevTools 9540) |
| `gmaps_d` | tripguardian1010@gmail.com | MỚI, đã đăng nhập, chưa chạy gì; file `.browser/gmaps_d.json`; gán việc cho nó khi có crawl Maps mới (ví dụ nơi mới từ TikTok/web chưa có dữ liệu Maps) |
| `gmaps_c` | (trùng `gmaps_a`) | KHÔNG dùng; cookie đã đổi tên `.browser/gmaps_c.json.dup-of-gmaps_a.bak` |
| `gmaps`, `gmaps_b`, `gmaps_s*` | đã đăng xuất | cần đăng nhập lại mới dùng được |

Mỗi tài khoản một runner và một cổng DevTools; không để hai trình duyệt ghi cùng file cookie. Kiểm tài khoản bằng cách mở `myaccount.google.com/personal-info` với `storage_state` của profile (tab Maps có thể hiện đã đăng nhập khi chưa), không chỉ nhìn cookie `SID`.

## Việc chưa làm, theo thứ tự đề xuất

Mỗi dòng là một track. Track chưa có plan thì viết plan trước (superpowers writing-plans) vào `docs/superpowers/plans/`, rồi giao một subagent.

| # | Việc | Spec | Phụ thuộc | Ghi chú |
|---|---|---|---|---|
| 1 | Media: gắn nhãn cảnh, bỏ ảnh có người, bỏ ảnh trùng gần, bỏ ảnh mờ/tối; `PHOTO_RANK` vào pipeline; khoảng 30 video mỗi nơi | A.6, roadmap P7 dòng "Media" | không | dùng Gemma; tạm dừng lane model TikTok khi chạy (memory `photo-ranking-gemma-pause-tiktok`); đích: % nơi có ≥ 3 cảnh |
| 2 | P3 sol dẫn đường: role `NAVIGATOR`, `src/corpus/navigate/` (`schema`, `plan`, `compare`), `mining_map.json` | A.1, A.9 việc 11, roadmap §P3 | P2 xong | `compare`: sol đề xuất mà không xem corpus, so với ontology/query/nơi đang có; phần mới chờ chủ dự án duyệt |
| 3 | D.3 đổi lịch tối trước mỗi ngày đi: yếu tố × độ nhạy → mức 0–3, sửa tối thiểu (dời giờ → đổi ngày → `backup_pool`), chống báo thừa, banner trên màn lịch đã chốt | D.3 | nên có OSRM (chặng đèo) và view P5 | đo bằng bộ kịch bản tổng hợp trong spec trước khi bật; link thông báo không trỏ `/app/today` |
| 4 | P4 Document → `LocalClaim`: task Extractor, gate quote/span, gom ≥ 2 nguồn, claim `source=model` đối chiếu `confirmed` / `contradicted` / `unverified` | A.3, roadmap §P4 | P3 (`general_claims`), Document từ `web documents` | công bố bảng `local_claims` |
| 5 | Menu để tìm theo món | A.2, memory `dish-lookup-goal` | không | gõ tên món phải ra quán; crawl menu trước, Gemma đọc ảnh menu sau |
| 6 | P7 đối chiếu nơi đề cử trên Maps (`gmaps resolve`) | A.1, roadmap §P7 | P3 | chỉ vào corpus khi resolve được và qua gate |
| 7 | B.6 đường từ nhà tới chỗ ở + module `booking` deeplink (adapter mỗi hãng, `Offer`, `booking_click`) | B.6, §1 mục 12 | trình duyệt (đã chạy được) | chuyến bay chỉ là link Google Flights điền sẵn; xe khách qua `live/buses` |
| 8 | E.1 hồ sơ cá nhân hóa kiểu bộ nhớ ChatGPT (kind/statement/signal/evidence/status), chỉ tín hiệu tường minh, replay eval + Judge kiểm + bất biến | E.1 | không | builder quyết nơi lưu (đề xuất Postgres) |
| 9 | P6 trang `aspect` + `local_knowledge` + báo cáo độ phủ | A.8 lớp 3, roadmap §P6 | P1, P3, P4 | |
| 10 | A.5 Nhịp Đà Lạt: tín hiệu có ngày → `data/<city>/pulse/`, job 24 h, bản tin trên UI; "đang hot" cho Lựa chọn (C.2) | A.5, C.2 | crawl định kỳ (sau track web/TikTok) | sol không viết bản tin |
| 11 | D.2 Local Expert (một lượt LLM sau validator) và kiểm ở cửa tool (thời tiết vô lý, lệch `ClimateNormal`) | D.2 | P4, P5 | |
| 12 | P8 vòng dẫn đường + đo trước/sau | A.1, A.9 | P6, P7 | dừng khi một vòng thêm < 5 % mới |
| 13 | Tối ưu SearXNG: bật engine, xoay vòng, giới hạn tốc độ | §3 việc 12 | không | ưu tiên thấp, vì đã có gsearch |

## Planning: điểm cần lưu ý, sửa khi đụng tới (chủ dự án yêu cầu ghi lại 2026-10-28)

Chưa sửa vì không chặn việc nào khác. Ai làm D.3, Local Expert hoặc bất cứ thứ gì chạm `src/planning/` thì xử lý luôn các mục này.

| # | Điểm | Chi tiết / chỗ nhìn | Gợi ý |
|---|---|---|---|
| 1 | Ca dày `twenty_in_2` (20 nơi / 2 ngày) chậm | Lịch đầu max 3,4–3,8 s dù p95 đã 1,33 s (bench có OSRM, `logs/planning_realistic/bench_d1_osrm_on.txt`). Thời gian nằm ở lượt xếp đầu ~1,5 s (vòng nơi thừa và `_unpin` trong `build.schedule_trip`) và tìm "fit" 1,65–1,84 s. Chưa có cận chứng minh được để bỏ bớt lần xếp: phần lớn lần thử bị luật sức chứa ngày nhẹ loại. | Cần thuật toán loại sớm có chứng minh, hoặc cache theo khung ngày; không nới ràng buộc. Còn mở sau lần thử 2026-10-29 (không có cận chứng minh được; số đo ở `docs/PLANNING.md` mục Giới hạn). |
| 2 | Đổi chỗ ở `set_lodging` max 0,85 s trên `twenty_in_2` | Sát giới hạn 1 s. | Theo dõi khi sửa mục 1. Còn mở sau lần thử 2026-10-29 (không có cận chứng minh được; số đo ở `docs/PLANNING.md` mục Giới hạn). |
| 3 | `schedule_calls` đếm thiếu | Cuộc gọi trong tiến trình con (hướng + `_extend`) không được tính. | Trả số đếm về từ con hoặc ghi rõ trong tài liệu (đã ghi trong `docs/PLANNING.md`). (đã xử lý 2026-10-28, xem ledger planning-notes) |
| 4 | Tiến trình cháu của `_extend` không bị kill khi con hết `_FORK_WAIT_S` | Chúng chạy hết lượt xếp có giới hạn rồi tự thoát khi pipe đóng. | Gom nhóm tiến trình, kill cả nhóm khi quá hạn. (đã xử lý 2026-10-29: kill cả nhóm tiến trình, có test). |
| 5 | Thứ tự `engine._unplaced` | Đã sửa 2026-10-28 (theo thứ tự chọn thay vì `set`). | Thêm test thứ tự dưới `PYTHONHASHSEED` khác nhau nếu chưa có. (đã xử lý 2026-10-28, xem ledger planning-notes) |
| 6 | Nơi nằm trong vùng hạn chế (P5) mới chỉ có `watch` | Chưa có câu báo người dùng: `build.condition_warnings` chỉ viết cảnh báo cấp ngày. OSM chưa đủ, nên không loại. | Thêm câu cho cảnh báo cấp nơi. (đã xử lý 2026-10-28, xem ledger planning-notes) Theo dõi 2026-10-29: `restricted_place` chỉ cho nơi trong lịch (đã xử lý 2026-10-29). |
| 7 | `rain_prob` từ khí hậu 11 năm dùng ngưỡng 2,5 mm | `config/views.yaml` `climate.rain_mm`; tháng 7 ra 0,74. Chưa đối chiếu với số liệu trạm. | Đối chiếu trạm, hoặc ghi đè tháng ở `rain_prob_override_by_month`. |
| 8 | Kiểm ngân sách chưa đọc giá phòng theo ngày | `stay_prices.load(city, max_age_h)` đã sẵn (`data/serving/stay_prices/<city>.json`). Giá có thể cũ tới ~1 ngày; mỗi dòng có `observed_at`. | Nối vào kiểm ngân sách, hiển thị tuổi giá. (đã xử lý 2026-10-28, xem ledger planning-notes) |
| 9 | Planning import `corpus.views` | Đã thêm `corpus.views` vào `ALLOWED_CORPUS` trong `tests/planning/test_planning_boundaries.py` để không phải mở rộng API `live`. | Xem lại nếu có cách sạch hơn. |
| 10 | Task 9 của plan planning cũ chưa làm | Gỡ phần cũ, đo trước/sau, cho người dùng đọc (`docs/superpowers/plans/2026-10-15-planning-realistic-core.md`). | Làm khi dọn Planning. (đã xử lý 2026-10-29: gỡ `cluster.py`, `assign_days`... ; số đo trước/sau ở `logs/planning_realistic/{before,after}`). |
| 11 | D.3, D.2 (Local Expert) | **Đã xử lý 2026-10-29**: link thông báo → `/app/plan`, `eve_of_trip` đọc điểm đầu của ngày 1 (`notify.plan.trip_point`), D.3 + Local Expert đã code (xem `docs/PLANNING.md`). **Xong 2026-10-29 (`expert-async`)**: event lịch Google nay gắn `/app/plan`; Local Expert chạy nền sau chốt (`expert.enabled: true`), `ClimateNormal` áp ở kiểm tra tối. (Từng sót: `src/companion/calendar.py` dòng 83 gắn link `APP_BASE_URL/app/today?stop=<id>` vào event lịch Google (không phải thông báo; màn `/app/today` còn route nhưng không có trên thanh điều hướng, sản phẩm dừng ở chốt lịch) → đã đổi.) | Sửa `companion/calendar.py` + `docs/COMPANION.md` dòng 48 cùng lúc. |
| 12 | Số đo cũ đều đo lúc OSRM tắt | Số mới có OSRM: lịch đầu p95 1,33 s, `set_day_window` max 0,17 s. | Dùng số mới làm mốc. |
| 13 | `tests/decision/test_wish_speed.py` trượt khi máy tải ~40/40 | Chạy riêng thì pass. | Đừng đọc đó là hồi quy. |

## LÀM CUỐI CÙNG (chủ dự án dặn 2026-10-28 khuya: gom phần chưa làm, làm sau khi các track chính xong)

Mỗi dòng chưa làm, ghi từ báo cáo các track ngày 28/10. Ledger của track nằm trong `.superpowers/sdd/<track>/progress.md`.

| Nhóm | Việc | Từ track |
|---|---|---|
| Web | Màn "Hồ sơ của tôi" (xem / sửa / xóa / tạm dừng mục hồ sơ; route `/api/harness/me/profile…` đã có) | profile-e1 |
| Web | Banner đổi lịch tối trước (2 ảnh ứng viên để chủ dự án chọn; bật cờ `eve_replan.enabled` sau khi chọn) | replan-d3 |
| Web | Hiện `price_kind`, `price_age_h` trên thẻ chỗ ở và câu `restricted_place` | planning-notes |
| Web | (đã xử lý 2026-10-29, web-user) Khung "Đường tới Đà Lạt" gọi `/api/harness/journey` + `/api/harness/booking/offers`, nút mua gửi `booking_click` | booking |
| Web | (đã xử lý 2026-10-29, web-user) Carousel chat Trip dùng `scene_photos`; chụp màn đĩa xoay; chạy `web/scripts/make_thumbs.py` trước build production | media A.6 |
| Booking | Nối chọn xe khách / chuyến bay với `pick_transit`; ghi `origin`, `inbound`, `outbound`; `home_city` → `origin`; câu đánh đổi (say đèo, trẻ nhỏ, đi đêm); waypoint `entry_road`; chủ dự án duyệt ngưỡng `config/journey.yaml`; tham số affiliate khi có partner id | booking |
| Decision | Prior của hồ sơ nhẹ hơn tín hiệu chuyến này trong `preference_fit`; bằng chứng từ Decision / Planning (kept_in_plan, rated_hop, dropped) vào hồ sơ | profile-e1 |
| Planning | #1 `twenty_in_2` chậm, #2 `set_lodging` sát 1 s, #4 tiến trình cháu `_extend`, #10 Task 9 plan cũ; dòng chi phí phòng riêng trong kiểm ngân sách theo ngày (`validate.py`) | planning-notes. 2026-10-29: #4, #10, dòng chi phí phòng riêng (`lodging_budget`) và `restricted_place` chỉ nơi trong lịch đã xử lý; #1 và #2 còn mở (đã thử, không có cận chứng minh được) |
| D.3 | Đưa vào yếu tố: đổi giờ đến / đi, ngày đóng cửa dịp lễ (`CalendarDay`) | replan-d3 |
| Corpus | Nâng `mining_map.json` (`cp mining_map_<ts>.json mining_map.json`) khi chủ dự án đồng ý; chạy `gmaps resolve` thật sau `COVERAGE_CHAIN_DONE`; món chỉ nằm trong review (precision `detail.order` 0,481 dưới ngưỡng) và Gemma đọc ảnh thực đơn đang tắt | navigator-p3, resolve-p7, dish-lookup |
| Corpus | Chạy `python -m corpus serving` (snapshot compile) để cột `conf` và `reputation` mới vào snapshot; `logistics.py` (`_best`, `_row`, gợi ý chỗ ở của chuyến) vẫn xếp theo trung bình mẫu đã crawl; bước aggregate chưa mang rating / reviews | rating-score |
| Corpus (P4) | Chạy `python -m corpus local extract` cho cả 785 Document (~6,5 giờ ở 4 luồng, chỉ khi lane Gemma rảnh); nối `aggregate/details.py` đọc `poi_claims.json`; test `test_online_retrieval_wiring` đang lỗi `NameError trip_live` ở `src/harness/__main__.py:74` (không thuộc P4) | claims-p4 |
| E.2 bậc 2 (khoảng trống, chưa làm) | Spike 3D "bản đồ của nơi" (SfM + gsplat, đi WASD trong nơi đó, spec E.2 §Spike vòng 3): cần một quán đông video quay bên trong, 30–50 clip + ảnh Maps đã lọc người, GPU 2080 Ti 11 GB; đo % frame vào cảnh lớn nhất, số vùng rời, % diện tích thật / lấp. Bậc 1 "Đi một vòng" đã có (ảnh theo cảnh). Còn thiếu cho bậc 1: clip theo cảnh vào cùng chuỗi (cần gán nhãn người / cảnh cho khung hình TikTok, ledger media-scenes bước B, C) và đi một vòng cho nơi chỉ xuất hiện trong chat Trip (ảnh ở đó chưa mang nhãn cảnh) | web-user, media |
| Chưa bắt đầu | P6 (trang `aspect`), D.2 Local Expert, P8 (vòng dẫn đường), A.5 Nhịp Đà Lạt, tối ưu SearXNG | phụ thuộc P4 / P7 / crawl định kỳ |
| Test | Hai file `test_cli.py` trùng tên (`tests/crawl/gsearch`, `tests/views`) gây lỗi thu test; test Postgres của `accounts.remember` chưa chạy vì `TEST_DATABASE_URL` trỏ DB production; `test_assistant_defaults_off` cần cập nhật theo `prefetch_wait_s` mới | nhiều track |
| Release | Build lại release sau chuỗi crawl sâu + observe + aggregate (điểm danh tiếng và độ tin cậy theo số người nhắc mới có tác dụng sau bước này); publish và deploy chỉ khi chủ dự án bảo | rating-score, crawl |

### Quyết định agent để lại, xem lại cuối cùng (chủ dự án dặn 2026-10-29: ghi lại để xét có làm hết không)

Mỗi dòng là một Ruling trong ledger của track. "Cái giá nếu sai" lấy từ chính ledger. Track nào báo thêm thì nối vào bảng này.

| Track | Quyết định | Cái giá nếu sai | Hướng xem lại |
|---|---|---|---|
| booking | Máy bay `feasible` không bao giờ True (chỉ False / None), vì link điền sẵn không cam kết có chuyến | UI hiện "chưa rõ" thay vì "ok" tới khi có nguồn chuyến bay thật | Tìm nguồn chuyến bay thật, hoặc chấp nhận |
| booking | Ngưỡng do agent đoán trong `config/journey.yaml`: xe máy ≤ 350 km, xe khách trong 60 km, sân bay trong 120 km, hiện chuyến bay từ 150 km | Gợi ý phương tiện sai ở vài tuyến | Chủ dự án duyệt từng ngưỡng |
| booking | Đoạn xe khách và phút cửa-tới-cửa để `None` (Vexere không trả tọa độ); chỗ ở không có dòng `stay_prices` thì không có offer | Thiếu số liệu ở UI | Xem có nguồn tọa độ bến xe không |
| planning-notes | Giá phòng theo ngày chỉ khớp đúng ngày và số đêm; không khớp thì giữ giá tham chiếu Maps, cả hai không có mới là chưa biết | Nhiều chỗ ở rơi về giá tham chiếu, vì crawl chỉ phủ lưu trú tính theo ngày trong tuần | Mở rộng cặp ngày crawl |
| planning-notes | Kiểm ngân sách theo ngày trong `validate.py` vẫn chỉ tính nơi tham quan | Ngân sách không có dòng tiền phòng riêng | Thêm dòng chi phí phòng nếu chủ dự án muốn |
| planning-notes | Câu `restricted_place` tính một lần cho cả chuyến, có thể nêu cả nơi lịch cuối cùng không dùng | Cảnh báo thừa | Lọc theo nơi có trong lịch |
| dish-lookup | Tên quán tính là bằng chứng món | Quán đổi menu vẫn bị liệt kê theo tên cũ | Giữ, có hạn chế nhóm `name_groups` |
| dish-lookup | Món chỉ có trong review đang tắt (`detail.order` precision 0,481 < ngưỡng) | Món chỉ nhắc trong review không tìm ra | Nâng precision rồi bật, hoặc chấp nhận |
| dish-lookup | Gemma đọc ảnh thực đơn tắt (cùng ảnh đọc hai lần ra hai tên, không có trích dẫn) | 24 quán chỉ có ảnh thực đơn thiếu món | Thêm cổng kiểm (đọc hai lần phải khớp) rồi bật |
| replan-d3 | Cờ `eve_replan.enabled` tắt dù 8/8 kịch bản đạt; có test chặn bật cờ khi kịch bản trượt | Tính năng chưa chạy | Bật sau khi chủ dự án chọn banner |
| replan-d3 | Mưa mức 2 cần cả xác suất ≥ 60% và ≥ 2,5 mm trong giờ ghé | Bỏ sót mưa nhỏ nhưng kéo dài | Đối chiếu ngưỡng với số liệu trạm |
| replan-d3 | Thời tiết chưa biết thì không dời điểm dừng sang ngày khác; đề xuất đang chờ lưu file mỗi chuyến, chưa có bảng Postgres | Mất đề xuất khi đổi máy chủ | Chuyển sang bảng khi lên prod |
| navigator-p3 | `mining_map.json` chưa được nâng thành bản dùng thật (bản chứng minh chạy `--no-latest`) | `web search` vẫn dùng truy vấn seed | `cp mining_map_<ts>.json mining_map.json` khi chủ dự án đồng ý |
| navigator-p3 | Khớp tên chặt hơn spec (cần ≥ 2 từ chung, ≥ 70% điểm tên, ≥ 50% từ có trong tên corpus); còn khớp nhầm kiểu `seasonal_flower_routes` ~ `scam_stage` | Vài đề xuất bị báo mới giả hoặc khớp nhầm | Duyệt tay `match.text` trong báo cáo |
| profile-e1 | Hồ sơ lưu file `data/trip/profiles/<uid>.json`, không dùng Postgres | Phải thay `ProfileStore` khi lên nhiều máy chủ | Chuyển sang bảng khi lên prod |
| profile-e1 | Sửa mục nào cũng tính là xác nhận (active) | Mục sai do người dùng sửa nhầm vẫn thành active | Giữ, hoặc thêm bước xác nhận |
| profile-e1 | Replay đo "prior khớp điều nói tiếp theo", chưa đo hạng của nơi người dùng chọn | Chưa biết hồ sơ cải thiện xếp hạng bao nhiêu | Thêm đo hạng Decision |
| resolve-p7 | Chạy bằng Chrome mới, không đăng nhập (không dùng profile `gmaps_d`) | Captcha headless dừng cả lượt | Giữ |
| resolve-p7 | Biên khớp 0,25: tên khớp hoàn toàn cạnh "X Coffee" coi là mập mờ | Vài nơi thật sự khớp một vẫn thành mập mờ | Chỉnh `margin` trong `config/navigate.yaml` sau vài lượt |
| resolve-p7 | Khớp chỉ theo tên, không theo biệt danh ("Con Gà" ≠ Nhà thờ Chánh Tòa) | Biệt danh phải quyết tay | Thêm bảng biệt danh (alias) nếu hay gặp |
| replan-d3 | Nhận một phương án thì bỏ các mục đang chờ khác của kế hoạch đó (đã tính trên kế hoạch cũ); tối sau kiểm lại | Bỏ lỡ mục còn đúng tới tối sau | Giữ |
| replan-d3 | Đổi giờ đến / đi chỉ thấy khi tới phiên Planning; sửa phía Trip không tới Planning thì không phát hiện | Bỏ sót đổi lịch | Nối sự kiện Trip → Planning |
| replan-d3 | Ngày lễ chỉ cho ghi chú mức 1, và chỉ với nơi chưa có giờ xác minh (ngày lễ không phải bằng chứng đóng cửa) | Bỏ sót nơi đóng dịp lễ | Giữ |
| replan-d3 | Banner A / B chưa chọn; chưa chạy `ui-ux-pro-max` trên bản được chọn | — | Chủ dự án chọn A hoặc B, xóa bản kia và `EVE_LOOK`, chạy design pass, rồi bật cờ + khởi động lại notify worker và harness |
| rating-score | Độ tin cậy ở 3 tác giả giờ là 0,7 chứ không còn 1,0 (cần chỗ trống để 3 < 30 < 300 xếp đúng thứ tự); mọi `preference_fit` dưới 300 tác giả thấp đi; đã sửa 4 assertion cứng 1,0 trong `test_rank.py` và `test_requirement_activities.py` | Điểm sở thích tụt chung | Chỉnh `base`, `ref_n` trong `config/serving.yaml` nếu lệch nhiều |
| rating-score | Trọng số sao 0,35 / số đánh giá 0,65, `min_pool` 100, `z_span` 3; nhóm dưới 100 nơi (tôn giáo, cho thuê) chấm theo cả thành phố; nâng trọng số số đánh giá lên 0,7 thì 4,0/1500 thắng 4,5/500 | Thứ tự sai ở nhóm nhỏ nếu đổi trọng số | Giữ; duyệt bảng ví dụ trong ledger |
| rating-score | Trọng số `rep` trong Decision là 0,3; với bữa ăn (không có mong muốn khác) `rep` quyết thứ tự: top-10 chỉ giữ 3/10 so với trước | Thứ hạng bữa ăn đổi nhiều | Chủ dự án xem bảng dịch chuyển, chỉnh `config/decision.yaml` |
| rating-score | Lọc `min_reviews` của chỗ ở nay dùng số đánh giá Maps thay vì số đã crawl; ngưỡng tác giả tuyệt đối (`TREND_MIN`, `details.min_authors`, `SILENCE_MIN_MENTIONS`) chưa đổi | Ngưỡng chưa scale theo khối lượng review | Xem lại sau lần observe + aggregate tới |
| trip-speed-r6 | `assistant.enabled: true` trong `config/trip.yaml` vì đạt cổng ở 2 bench cuối (máy rảnh, tải ~9): p50 5,28–5,76 s, p90 7,58–9,01 s; 4 bench đầu lúc tải ~85 trượt p90 (11,4–14,6 s) do lần gọi sol đơn 12–27 s phía upstream | Bật trên prod lúc upstream bận thì p90 vượt cổng; chưa deploy / khởi động lại | Chủ dự án quyết giữ bật hay tắt lại (`false`) trước khi restart; cân nhắc gọi lại có dự phòng sau ~8 s (tốn quota) |
| trip-speed-r6 | `prefetch_wait_s` 3,0 (trần, không chờ thêm nếu dữ liệu về sớm); `covered_tools: "write"` bật; chế độ `"none"` không thử (mất fact `record_fact`); câu "Lẩu gà lá é quán nào được?" còn tốn thêm một lần gọi (`claim_without_record`) | — | Giữ |
| decision (E.1) | Sức khỏe / ăn uống / cơ thể lưu trong hồ sơ (chủ dự án quyết 2026-10-29), chỉ nạp làm prior, thành lọc cứng sau khi xác nhận trong chuyến | — | — (đã quyết) |
| profile-e1 | `need` chỉ lưu từ lời chính người dùng nói (cắt 120 ký tự), loại: knee, wheelchair, motion_sick, height, vegetarian, vegan; không lưu `kids`, `elderly`, `pregnant` (là thông tin của chuyến hoặc tạm thời), không lưu need chọn qua thẻ | Mỗi chuyến phải hỏi lại need chọn qua thẻ | Xem có cần lưu thêm loại nào |
| profile-e1 | Thẻ "Lần trước bạn nói … Chuyến này vẫn vậy chứ?" chỉ hiện khi người dùng trả lời các câu tùy chọn; người bỏ qua nhanh thì need đã lưu không được áp dụng | Người vội không được hưởng need đã lưu (an toàn: hồ sơ không bao giờ thành ràng buộc) | Xem có cần đưa thẻ vào cổng trước Lịch trình cho mọi người |
| claims-p4 | Nguồn độc lập = tên miền khác nhau (Document không có tác giả); `kept` khi ≥ 2 miền hoặc 1 miền `.gov.vn`; một nguồn thì `unverified` | Hai trang cùng một chủ khác tên miền vẫn tính là hai nguồn | Duyệt tay vài claim `kept` sau lần chạy đủ 785 Document |
| claims-p4 | So claim của sol với claim Document chỉ bằng code, không gọi model; diễn đạt khác thì ở lại `unverified` | Ít `confirmed` hơn thực tế (mẫu 40 Document: 3 confirmed, 0 contradicted, 23 unverified) | Giữ; cân nhắc so bằng model nếu cần nhiều confirmed hơn |
| claims-p4 | Ngưỡng tháng (lệch ≤ 1 tháng là cùng kỳ, ≥ 3 là mâu thuẫn) và cách tách chủ đề được chỉnh theo mẫu 40 Document, mỗi chỗ chỉnh có test | Quá khớp với mẫu nhỏ | Kiểm lại sau lần chạy đủ |
| claims-p4 | Claim `poi_unresolved` (tên nơi không khớp địa điểm đã phục vụ) nằm ngoài bảng phục vụ, xếp hàng vào `poi_unresolved.jsonl`; claim nêu giờ mở cửa của quán bị loại (`venue_hours`) | Mất tri thức về nơi chưa có trong corpus | Dùng hàng đợi để thêm nơi (P7 resolve) |
| claims-p4 | Mẫu 40 Document: `kept` đúng 11/11 nhưng claim không phải `kept` chỉ đúng 21/30 (70%); chỉ `kept` được phục vụ như fact, phần còn lại là tham khảo / tranh cãi, `contradicted` không bao giờ trả ra | Nếu nâng cấp độ phục vụ `unverified` thì lọt 30% sai | Giữ như hiện tại |
| claims-p4 | Chưa chạy serving / snapshot / release nên bảng `local_claims` chưa công bố; `aggregate/details.py` chưa đọc `poi_claims.json`; `local group` không có `--map` thì không thấy claim sol (`mining_map.json` chưa nâng) | Tri thức bản địa chưa tới người dùng | Công bố ở lần build tới, sau khi chủ dự án nâng `mining_map.json` |

## Việc chờ chủ dự án

- Gate spike không gian vòng 3 (E.2).
- Câu báo người dùng cho nơi nằm trong vùng hạn chế (P5 mới chỉ gắn cảnh báo `watch`). (đã xử lý 2026-10-28, xem ledger planning-notes)
- Ca `twenty_in_2` lịch đầu còn khoảng 3,7 s (mục tiêu p95 đã đạt). Chưa tìm được cách cắt bớt mà chắc chắn không làm đổi lịch.
- 12 tiến trình Chrome cũ kẹt ở trạng thái D trên NFS: cần admin hoặc reboot. Sau đó xoá `.cache/nfs-stuck-20261028/`.
- Deploy: chưa phần nào lên prod. Chỉ deploy khi chủ dự án bảo (memory `prod-deploy-runbook`).

## Ghi nhớ kỹ thuật

- Cài Playwright chỉ với `PLAYWRIGHT_SKIP_BROWSER_GC=1`.
- Trình duyệt lại treo thì trước hết chạy `cat` file chạy Chromium vào `/dev/null` có timeout để kiểm NFS.
- Bench chạy từ gốc repo với `PYTHONPATH=src`, vì `SSL_CERT_FILE` trong `.env` là đường dẫn tương đối.
- Tên biến trong `.env` có thể bắt đầu bằng chữ số (`9ROUTER_API_KEY`).
- 9router (`:20128`) có lúc tự tắt. Khởi động lại bằng hàm `router_start` của `run.sh`.
- `tests/decision/test_wish_speed.py` có thể trượt khi máy tải nặng (load khoảng 40/40). Chạy riêng để xác nhận.
