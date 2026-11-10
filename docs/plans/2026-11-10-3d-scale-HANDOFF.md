# Bàn giao: dựng 3D hàng loạt Đà Lạt (2026-11-10, cập nhật chiều)

Đọc trước: [thiết kế](2026-11-09-3d-scale-design.md) (chủ dự án đã duyệt), [kế hoạch](2026-11-09-3d-scale-plan.md) (Task 1–9). File này nói **đã làm tới đâu, việc tiếp theo, bẫy đã gặp**. Các file bàn giao 3D ngày 11-04 vẫn còn (gộp ở Task 9).

## TẠM DỪNG 2026-11-10 ~23:50 (đọc trước nhất)

Chủ dự án yêu cầu dừng mọi process để admin cấp thêm GPU. Đã dừng: chuỗi `after_queue_tierAB_20261110.sh` (639063) và lượt `auto3d.py run` của nó, 3 worker `bridge/serve.py`, server tĩnh :8471 / :8472, harness dev :8779, analytics :8770, vite :5199 / :5173. Harness prod :8769, web :28899, notify, tunnel đã được dừng trước đó (không phải phiên này). 9router và `model_gateway` vẫn chạy (CPU).

Trạng thái lúc dừng: 33 `ready` (chưa chấm: Thiên Đường Săn Mây, Cầu Đất `caudat`, `chuyencuanang`), 9 `published`, 3 `needs_human`, 2 `failed:colour` (Hồ Xuân Hương, Lời Của Gió). Dừng giữa chừng (chạy tiếp được, auto3d lưu từng bước): `build` dalatedenseela; `colour` chodalat congvienanhsan doichecaudat; `shoot` dicungmua garungquananca happyhillcoffe khudulichthuyt khuvuichoidala langbianglandk lavenderdalat nongtraihoatin novadreamsroya reocampsitedal sanmaycaugobin thefloresthoat tramkyuc. 14 nơi đặc biệt (`logs/diorama/special_pick_20261110.txt`) **chưa chạy**.

**Chạy lại khi có máy:** bật bridge + server :8471 (`scripts/diorama/stack.sh up`, kiểm `stack.sh status`), rồi
`python3 scripts/diorama/batch/auto3d.py run dalatedenseela chodalat congvienanhsan doichecaudat dicungmua garungquananca happyhillcoffe khudulichthuyt khuvuichoidala langbianglandk lavenderdalat nongtraihoatin novadreamsroya reocampsitedal sanmaycaugobin thefloresthoat tramkyuc` (không `--redo`), sau đó `auto3d.py run $(cat logs/diorama/special_pick_20261110.txt)`. Hai file `bridge/req/*.taken*` còn lại là yêu cầu chụp đã bị bỏ dở, xoá được.

## Cập nhật 2026-11-10 ~23:30

Chuỗi `after_queue_tierAB_20261110.sh` (PID 639063) đang ở Thiên Đường Săn Mây; sau đó còn 19 nơi `failed:*` và 14 nơi đặc biệt. Đã chấm 5 nơi mới `ready`:
- Đạt: Ký Ức Đà Lạt (tạm). Sửa tay rồi đạt: Thung Lũng Vàng (`lake2thunglungvang`), Hoa Sơn Điền Trang `khudulichsinht` (`lake2khudulichsinht`).
- `needs_human`: Thác Cam Ly (lần làm lại thứ hai vẫn ra ba mảng trắng phẳng, không có bậc đá granite hồng, hồ dưới thác như dốc đất; cần sửa tay hoặc sửa `nature_cascade`, đừng `--redo` nữa), Cáp Treo (có `nature_line` + `white-mast-silhouette` trong place.json nhưng không thấy tháp trắng và dây cáp trong render; nền xanh neon).
- Chưa xử lý: Hồ Xuân Hương, Lời Của Gió (`failed:colour`), Tiệm nướng trong rừng (`needs_human`, `round_limit_or_stall`).

**Bẫy mới (màu nước):** grade cuối kéo sắc ô-liu (hue ~0,15–0,37) về xanh lá, nên nước màu ô-liu / vàng đục đọc thành cỏ hoặc đất. Đặt giá trị `colorMap` của nước ngoài dải đó, tông xanh ngọc đục (`#5f8a80`, `#3f6f68`), kể cả khi ảnh thật hơi vàng.

## Cập nhật tối 2026-11-10 ~19:15

**Đang chạy nền:**
| Job | PID | Log | Làm gì |
|---|---|---|---|
| Queue hạng B `--parallel 5` (cũ) | 3086426 | — (log rỗng) | còn Ký Ức Đà Lạt |
| Chuỗi sau đó (cũ) `after_shutdown_20261110.sh` | 3214022 | `logs/diorama/after_shutdown_20261110.log` | crawl xong; chờ queue rồi chạy lại Cáp Treo, Thung Lũng Vàng, Hoa Sơn Điền Trang |
| Chuỗi mới `logs/diorama/after_queue_tierAB_20261110.sh` | 639063 | `logs/diorama/after_queue_tierAB_20261110.log` | chờ hai PID trên → `run hoxuanhuong loicuagio tiemnuongtrong --redo` → `run thaccamly --redo --kit nature …` → `run thienduongsanm --redo --kit garden …` (note trong `logs/diorama/note_<slug>_20261110.txt`) → `run` 19 nơi `failed:*` (`logs/diorama/failed_retry_20261110.txt`) → `run` 14 nơi đặc biệt (`logs/diorama/special_pick_20261110.txt`) |

**Chủ dự án chốt (19:30):** trong 76 nơi mới lên A/B, chỉ làm nơi đặc biệt, đẹp, nổi tiếng ("cái nào đặc biệt thì làm, không thì thôi"). Đã chọn 14 nơi: Chợ Đêm, Mê Linh, Langfarm, Bình Minh Ơi, Túi Mơ To, Nhà Bên Rừng, Làng Nấm, XQ Sử Quán, Maze Bar, Thung Lũng Đèn, Đồi Thiên Phúc Đức, Dapa Hill, Rừng Thông Mơ, Nhớ Hoài. Không chạy `queue --tier A,B` (nó sẽ lấy cả 76). Yêu cầu web mới (tour đi theo đường, vào thẳng trong nhà, animation mới, nơi chủ yếu nội thất): [bàn giao riêng](2026-11-10-space3d-tour-interior-HANDOFF.md).

**Đã làm tối nay:**
- Chấm 11 nơi `ready` chưa chấm. Đạt: Vé Xe Trượt Datanla (tạm), Vùng Ngoại Ô, Mây Mây, Cloud9. Sửa tay rồi đạt: An Tuyền Lâm, Cà phê Nhật Nguyên, Hồ Tuyền Lâm (tạm), Thôn 13, Dốc Nhà Bò (tạm). Làm lại (`needs_human`, đã xếp vào chuỗi): Thác Cam Ly (kit chính đang là `church`, thác là mảng trắng phẳng, hồ đọc như cỏ), Thiên Đường Săn Mây (thiếu vòng tròn xanh, hồ gương, sàn kính).
- `photo_scenes` cho 134 nơi vừa crawl ảnh (hạng C + 3 nơi B). Kiểm trước: chỉ đúng các nơi đó bị gán lại. UIT trả 429 (giới hạn 40 request đồng thời, chủ dự án đang chạy OCR cùng key) → chạy 3 lượt mới đủ. **Đã báo chủ dự án là xong phần Gemma**; phần 3D còn lại không gọi Gemma (build và colour mặc định dùng sol).
- `hot_places.py 1000`: 76 nơi mới lên A/B (27 nhà hàng, 18 cà phê, 17 khách sạn, 4 điểm tham quan, …), gồm Chợ Đêm, Mê Linh, Langfarm, Làng Nấm, XQ, Dapa Hill. Queue A,B trong chuỗi mới sẽ chạy chúng và thử lại 19 nơi `failed:*`.
- **`failed:shoot` hàng loạt (19 nơi) là do timeout chụp 30 s của Playwright khi load máy ~45–50, không phải do cảnh quá nặng** (đa số chỉ 65–420k tam giác). `bridge/serve.py`: chụp mỗi view tối đa 90 s; worker tự `execv` khi `serve.py` đổi (giữ pid, `stack.sh` vẫn nhận). Đã khởi động lại 3 worker lúc rảnh, không mất request.

**Bẫy mới:**
- Bước colour đổi nước thành xám rất thường gặp (5/11 nơi tối nay). Sửa: đặt lại *giá trị* trong `colorMap` cho khóa màu nước (`edit_place.py`), không sửa `color` của object, vì `colorMap` ánh xạ đè lên. Renderer làm nước tươi hơn mã màu: `#4f8790` ra xanh ngọc rõ.
- Khung tổng quan chỉ đo mặt đế (y = -3), nên khu dốc cao (Dốc Nhà Bò) bị cắt mép trên dù đã giảm `frameFill`. Sửa: `site.overviewSubjects` = mọi id object + `overviewAllAngles: true`.

**Việc tiếp theo:** chấm từng nơi khi chuỗi chạy xong (`review_sheet.py` → xem ảnh → `opus_review.py`). Khi hạng B xong và đã chấm: publish các nơi đạt + Chênh Vênh, rồi chạy một lần `build_space3d`; deploy prod phải hỏi lại. Commit `scripts/diorama` (đã sửa `bridge/serve.py`) chỉ khi được yêu cầu.

## Bàn giao lúc chủ dự án tắt máy (2026-11-10 ~15:15)

Phiên điều phối dừng, các job dưới đây vẫn chạy nền trên gpu156 (`nohup`). Phiên sau **không cần khởi động lại gì**, chỉ chấm và nối tiếp.

**Đang chạy nền:**
| Job | PID | Log | Xong thì |
|---|---|---|---|
| Queue hạng B `--parallel 5` | 3086426 | `logs/diorama/queue_tierB_20261110c.log` | mọi nơi tới `ready` / `needs_*` / `skip` / `failed:*` |
| Crawl ảnh hạng C (134 nơi; 81 xong lúc 15:10) | 2679996 | `logs/diorama/tierC_photos_20261110.log` | `photos.json` mới trong `data/gmaps/places/<fid>/` |
| Chuỗi sau đó `logs/diorama/after_shutdown_20261110.sh` | 3214022 | `logs/diorama/after_shutdown_20261110.log` | (1) chờ crawl C xong → crawl ảnh 3 nơi hạng B thiếu ảnh (`DATA/batch/photo_targets_tierB_short_20261110.json`: Hồ Xuân Hương, Lời Của Gió, Tiệm nướng trong rừng); (2) chờ queue xong → tự chạy 3 lượt `--redo --note` trong `DATA/batch/rerun_after_queue_20261110.txt` (Cáp Treo, Thung Lũng Vàng, Hoa Sơn Điền Trang), log `logs/diorama/rerun_<slug>_20261110.log` |

**Việc của phiên sau (theo thứ tự):**
1. Chấm mọi nơi `ready` chưa có `opus_review` (lệnh liệt kê bên dưới): `review_sheet.py <slug>` → xem ảnh → `opus_review.py <slug> ok|redo "..."`. Lỗi rẻ thì sửa tay bằng `DATA/batch/edit_place.py` + `DATA/batch/reshoot.sh <slug> <tag>` (đã làm cho Lá Phong, Suối Bình Yên, Puppy Farm, TLTY). Nơi không đạt: thêm dòng vào `rerun_after_queue_20261110.txt` rồi chạy `auto3d.py run <slug> --redo ... --note "..."`.
   `python3 -c "import json,glob;[print(f.split('/')[-2]) for f in glob.glob('/data/work/luanhh/local/tripguardian-store/splat/diorama/places/*/auto3d.json') if (s:=json.load(open(f)))['stage']=='ready' and not any(h.get('step')=='opus_review' for h in s['history'])]"`
2. Ảnh mới (hạng C + 3 nơi B): chạy `EXTRACTOR_ON_UIT=1 .venv/bin/python -m corpus gmaps photo_scenes --city dalat`. Lệnh này không lọc theo nơi; nó bỏ qua nơi có `input_hash` không đổi, nhưng **kiểm trước** xem có bao nhiêu nơi ngoài 137 nơi trên bị gán nhãn lại (đổi prompt / config gần đây sẽ làm gán lại hàng loạt; dữ liệu này dùng chung với prod). Rồi `hot_places.py 1000` xem nơi nào lên A/B → `auto3d.py run <fid>`; 3 nơi B: `auto3d.py run <slug> --redo`.
3. Khi hạng B xong và đã chấm: publish các nơi đạt + Chênh Vênh bản mới bằng một lần `build_space3d` (chủ dự án đã đồng ý); **deploy prod hỏi lại**.
4. Còn lại: `--redo --extra-kit nature` cho Terracotta, Quảng trường Lâm Viên, Euro Garden, Hoàng Long; Task 9; commit `scripts/diorama` (sửa hôm nay chưa commit) khi được yêu cầu.

**Kết quả chấm tới 15:10:** đạt 15 nơi hạng B (Datanla, TLTY, Lang Biang, Đồi Mộng Mơ, Puppy Farm, Mongo Land, Fresh Garden, Lá Phong, Horizon, Swiss-Belresort, Suối Bình Yên, KDL Cao Nguyên Hoa, …; xem `opus_review` trong `auto3d.json`). Thác Cam Ly vừa `ready`, **chưa chấm**.

**Bẫy mới:** builder đôi khi đặt `site.overviewPolar` theo radian (Suối Bình Yên 1,15 → nhìn thẳng từ trên); `colorMap` của bước colour hay đổi màu nước thành xám (Lá Phong, Suối Bình Yên, TLTY) → đặt lại `color` của object nước.

## Cập nhật đêm 2026-11-10

**4 nơi cảnh quan đã chốt `ready` (Opus xem ảnh, ghi bằng `opus_review.py`):** Lang Biang (`cbm12303`), Datanla (`r1110khudulichthacd`), Thung Lũng Tình Yêu (`r1110bthunglungtinhy`), Đồi Mộng Mơ (`r1110doimongmodalat`). Sửa tay trước khi chụp lại (bản gốc `place.before_<tag>.json` cạnh `place.json`):
- Datanla: bỏ `site.overviewFov: 8` / `overviewPolar`; camera chạm trần khoảng cách 600 nên khung tổng quan cắt mất thác chính (cao 130 %).
- TLTY: `overviewAzimuth 125`, `overviewPolar 50` (góc cũ nhìn vào mặt dốc xanh lớn, cổng bị cắt); hồ `#4f8274` (màu cũ đọc như bê tông xám).
- Đồi Mộng Mơ: 850k → 637k tam giác (đường hầm tim 5 vòm `coverSpacing .42`, ruộng hoa thưa hơn, `north-forest` density .12), vì ảnh tổng quan ở góc 125 bị quá giờ.
- Sửa tay `place.json`: giữ `colorMap` **một dòng**. Script chụp lại: build `places/<slug>/place.json` → `out_<slug>/` rồi `bridge/shot.py <tag> --out out_<slug>` (như `colour_by_model.shoot`).

**Đang chạy:** `auto3d.py queue --tier B --n 58 --parallel 3` (xem PID / log mới ở dưới). Chết thì chạy lại đúng lệnh (tiếp chỗ dở). Mỗi nơi xong: `review_sheet.py`, xem ảnh, `opus_review.py`.

**Chủ dự án trả lời (11-10 chiều):** (1) Chênh Vênh bản mới được lên web, **gộp chung một lần với các nơi hạng B** khi xong và đã chấm: `auto3d.py publish <slug…>` các nơi đạt rồi `node web/scripts/build_space3d.mjs` + `shots_space3d check`; deploy prod vẫn hỏi lại. (2) Hạng C: "crawl thêm ảnh đi" → đang chạy `logs/diorama/tierC_photos_20261110.sh` (134 nơi, `GMAPS_PHOTO_TARGETS=DATA/batch/photo_targets_tierC_20261110.json`, `GMAPS_PHOTO_CHIPS=1`, profile `gmaps_b2`); xong thì `EXTRACTOR_ON_UIT=1 corpus gmaps photo_scenes` chỉ cho các nơi đó, **không** serving / snapshot / release; rồi `hot_places.py` xem nơi nào lên hạng A/B.

**Lỗi hệ thống tìm thấy:** NOTES chỉ thấy *tên* loại object (`kits_summary()`), nên khai `kit_gap` sai: Cáp Treo Đà Lạt bị `needs_kit` vì "không kit nào có cabin cáp treo", trong khi `nature_line kind: cable` có cabin, tháp, hai trạm. Đã giao sol thêm một dòng mô tả cho mỗi loại (brief `DATA/batch/briefs/BRIEF_kits_summary_gloss.md`). Các nơi `needs_kit` vì lỗi này chạy lại **sau khi queue xong** (danh sách + lệnh: mục "Chạy lại sau queue" bên dưới).

**Chạy lại sau queue:** danh sách + lệnh ở `DATA/batch/rerun_after_queue_20261110.txt` (mỗi dòng `slug | tham số auto3d.py run`; hiện: Cáp Treo, Thung Lũng Vàng, Hoa Sơn Điền Trang). Thêm dòng khi chấm loại một nơi. Công cụ sửa tay: `DATA/batch/edit_place.py` (giữ `colorMap` một dòng, sao lưu `place.before_<tag>.json`), `DATA/batch/reshoot.sh <slug> <tag>`.

**Đã sửa thêm (chưa commit, `scripts/diorama` nằm ngoài git ở checkout này):**
- `index.template.html` (sol): `overviewFov` hẹp (8, chép từ ví dụ Bên Suối / Lon Ton) trên khu 100–160 m làm camera chạm trần 600 m và cắt khung (Datanla, Mongo Land). Nay khi chạm trần mà vẫn tràn thì nới fov vừa đủ (≤ 36°), log `overview-bbox` có `fov`; nơi đã vừa khung không đổi. `checks/test_overview_fit.mjs`.
- `auto3d/prompts.py`: `kits_summary()` có một dòng mô tả mỗi loại (sol); NOTES được dặn thêm `nature` khi ảnh có hồ / thung lũng rừng / thác (`garden_water` chỉ cho ao nhỏ). Lý do: Thung Lũng Vàng, Hoa Sơn Điền Trang chỉ chọn `garden`, ra bãi cỏ phẳng không có nước.
- Queue khởi động lại lúc 14:2x để nạp hai sửa trên, rồi 14:45 với `--parallel 5` (chủ dự án hỏi chạy song song nhiều hơn; bridge vẫn 3 worker, lượt thứ 4–5 chủ yếu nằm ở bước build của sol, yêu cầu chụp xếp hàng trong `bridge/req/`, chờ tối đa 900 s): PID 3086426, log `logs/diorama/queue_tierB_20261110c.log`. Đừng tăng nữa khi load máy còn ~75/40 nhân: view swiftshader quá 30 s → `failed:shoot`.

## Cập nhật tối 2026-11-10

**Git:** `scripts/diorama` + `tests/diorama` đã vào git trên nhánh riêng **`feat/diorama-scripts`** (từ HEAD của `chore/prod-cleanup-20261109`): `6d45cb2` (toàn bộ pipeline), `9d81672` (chữ đứng, `--note`, ngân sách tam giác, công cụ chấm). Commit bằng worktree tạm, nên ở checkout chính các file vẫn hiện untracked (nhánh hiện tại có ~750 thay đổi đã stage của phiên khác, không đụng). Commit tiếp: `git worktree add <tmp> feat/diorama-scripts`, `rsync -a --delete --exclude node_modules --exclude __pycache__ scripts/diorama/ <tmp>/scripts/diorama/` (+ `tests/diorama/`), commit, `git worktree remove`. Chưa push, chưa merge. Sau khi merge thì xoá bản gốc `logs/splat/diorama/`.

**Công cụ mới (dùng cho mọi nơi):**
- `python3 scripts/diorama/batch/review_sheet.py <slug> [tag]` → `DATA/batch/review_<ngày>/cmp_<slug>.jpg` (ảnh thật trên, render tổng quan + 2 orbit dưới). Đây là cổng chấm thật.
- `python3 scripts/diorama/batch/opus_review.py <slug> ok|needs_kit|needs_human|redo "<lý do>"` ghi quyết định vào `auto3d.json` (đừng chạy khi lượt auto3d của nơi đó còn sống).
- `auto3d.py run <slug> --redo [--kit K --extra-kit E] --note "<nhận xét chấm ảnh>"`: note vào cả NOTES và mọi vòng build, giữ qua `--redo`, `--note ""` để xoá. Viết note tiếng Anh, cụ thể: cái gì sai trong render, ảnh nào cho thấy cái đúng, bố cục mong muốn.
- `node scripts/diorama/check_place.mjs <slug> --tris`: tam giác theo object. Bridge render bằng swiftshader, mỗi view có 30 s; load máy ~60/40 nhân (ffmpeg / torch của việc khác cùng tài khoản) nên cảnh > ~700k tam giác mất view → `failed:shoot`. Brief build nay đòi ≤ ~650k. Sửa tay: `garden_field` `spacing` + `rowSpacing` ≥ 0,9, `leavesPerPlant` 3, `nature_grove` `density` thấp hơn; rồi `auto3d.py run <slug>` (chạy tiếp ở shoot).
- Kit `garden`: **`garden_letters`** (chữ khối đứng, nhiều màu, dấu tiếng Việt, ♥, `arc`, `tilt`, bệ; không font ngoài). Dùng cho LANGBIANG, "Thung Lũng Tình Yêu", "Mộng Mơ Dalat", "I ♥ Đà Lạt".

**Trạng thái từng nơi (tối 11-10):**
| Nơi | Trạng thái | Ghi chú |
|---|---|---|
| Lang Biang `khudulichlangb` | needs_kit → chờ chốt | sol (brief `DATA/batch/briefs/BRIEF_kl_garden_letters.md`) đã thêm chữ LANGBIANG nhiều màu, tag `kl5final`; bố cục đạt. Màu nhạt (ô-liu) vì sandbox sol không có mạng → đang chạy `colour_by_model.py khudulichlangb --rounds 2` (log `logs/diorama/colour_langbiang_20261110.log`). Xong: chụp lại, xem, `opus_review.py khudulichlangb ok "..."`. |
| Đồi Mộng Mơ `doimongmodalat` | ready (auto3d) | Bản `garden+nature` có cầu kính qua thung lũng, vòm tim, hồ, nhà gỗ, chòi: **đạt về nội dung**. Góc tổng quan cũ nhìn vào mặt cắt đất cam lớn → đã đặt `site.overviewAzimuth: 125` (bản trước: `place.before_azimuth.json`), đang chụp tag `az125doimongmodalat`. Xem rồi `opus_review.py doimongmodalat ok "..."`. |
| Datanla `khudulichthacd` | đang chạy (colour) | Chạy lại `--kit nature --extra-kit garden --note` (một hẻm đá, thác chính nhiều bậc, suối, hồ, sàn ngắm). Bản trước bị loại: 3 cụm thác rời trên dốc thoải. Chấm bằng review_sheet khi `ready`; so với Thác Prenn (`bridge/out/knregthacprenn`). |
| Thung Lũng Tình Yêu `thunglungtinhy` | đang chạy (build vòng 2) | Chạy lại với note (thung lũng dốc xuống hồ, không bãi trống). Hai lần `failed:shoot` vì 1–1,28M tam giác; đã giảm tay còn ~560–615k (bản gốc `place.before_spacing.json`). |
| 6 nơi `ready` cũ | ready | Xuân Hương (đạt), Vườn Địa Đàng, QUÊ, Đường Hầm Điêu Khắc, Terracotta, Quảng trường (tạm đạt). |

PID lúc bàn giao: Datanla 1634300, TLTY 1960161, colour Lang Biang 2048107. Chết thì `auto3d.py status` rồi `auto3d.py run <slug>` (không `--redo`) để chạy tiếp.

**Câu hỏi chủ dự án vẫn chưa trả lời:** (1) build `build_space3d` cho Chênh Vênh bản mới; (2) publish các nơi `ready`; (3) Task 8 corpus: `corpus build` ghi `data/` dùng chung với prod, cần duyệt. Hầm vang Vĩnh Tiến chỉ 227 review (dưới ngưỡng hot 1000) nên ưu tiên thấp.

**Việc tiếp theo cho phiên sau (theo thứ tự):**
1. Chốt 4 nơi trên bằng `review_sheet.py` + `opus_review.py` (nơi nào chưa đạt: `--redo --note` cụ thể, không ép qua).
2. `auto3d.py queue --tier B --n 58 --parallel 3` (55 nơi còn lại; có hồ / đồi / thác / chữ đứng thì kit đã đủ). Mỗi nơi xong: review_sheet, chấm, note nếu cần chạy lại. Không quá 3 lượt song song.
3. `--redo --extra-kit nature --note` cho Terracotta, Quảng trường Lâm Viên, Euro Garden, Hoàng Long (thiếu hồ / đồi).
4. Task 8 (sau khi chủ dự án duyệt), Task 9 (`docs/SPACE3D.md`, gộp các bàn giao).

## Cập nhật chiều 2026-11-10 (các mục "Việc tiếp theo" bên dưới đã cũ)

**Trạng thái `auto3d.py status`:** 9 published, 6 ready, 1 needs_kit, 1 skip.
- **published** (một phiên khác publish theo yêu cầu chủ dự án "lấy dữ liệu 3D mới nhất thêm vào production", 09:12): Ana Mandara, Chênh Vênh, Dinh I, Euro Garden, Hoàng Long Ohayo, Rừng Thông Núi Voi, Vạn Thành, Nobi, IXORA. Trong số đó, Opus chỉ chấm *đạt* cho Vạn Thành, Nobi và Ana Mandara; các nơi còn lại *tạm đạt*. **Chênh Vênh đã được làm lại** (đồi + thung lũng nhà kính, màu thật), nhưng bản mới chỉ lên web khi chạy `build_space3d`.
- **ready, chưa publish:** Xuân Hương (đạt: cối xay gió có cánh), Vườn Địa Đàng, QUÊ, Đường Hầm Điêu Khắc, Terracotta, Quảng trường Lâm Viên (đều tạm đạt). Lý do từng nơi: `reason` + mục `opus_review` trong `history` của `auto3d.json`.
- **needs_kit:** Đồi Mộng Mơ. Cầu kính nằm bẹt trên cỏ, vòm cây tròn chứ không phải trái tim. Chạy lại bằng `auto3d.py run doimongmodalat --redo --extra-kit nature`.
- Bảng ảnh thật cạnh render: `DATA/batch/review_20261110/` (`after_*.jpg` = sau kit). Bảng gửi chủ dự án: `DATA/batch/ready_for_owner_20261110.jpg`.

**Đã làm:**
- Task 7 kit (sol high ×2, ≈ 1,95M token; brief + log ở `DATA/batch/briefs/`):
  - `nature`: thêm `nature_lake`, `nature_hills` (đồi tầng, đỉnh, thung lũng nhà kính, `heightAt`), `nature_line` (cáp treo / ray trượt); `nature_grove` thêm rừng thông kesiya bám dốc; `nature_cascade.tiers`; `nature_stream.rapids`.
  - `garden`: thêm `garden_windmill`, turbine, rockery, koi pond, `garden_clay_tunnel`; mở rộng cầu kính (`garden_bridge.style: glass`), vòm tim / canopy, `garden_conifer.form: cloud`, `garden_sculpture` kind `liberty|bust|clay`.
  - Mọi nhánh mới đều tự chọn. Hồi quy đo bằng pixel: Yersin, Vườn hoa, Bên Suối, Lon Ton, Prenn, Cẩm Tú Cầu chênh ≤ 1,5 % pixel. Cẩm Tú Cầu vẫn quá giờ chụp ở vài góc, có từ trước khi sửa kit. `checks/` đều đạt.
- auto3d nhiều kit (sol medium): NOTES có `extra_kits` (0–2), `run --extra-kit NAME`, builder dán catalog mọi kit, boot báo lỗi nếu `place.json` thiếu kit. 202 test đạt.
- **Sửa lỗi `batch/set_colormap.py`:** `colorMap` nhiều dòng hay trùng khóa làm script chèn khóa thứ hai; JSON lấy khóa cuối (bản cũ), nên **mọi sửa màu bị mất âm thầm**. Terracotta, Vườn Địa Đàng và Chênh Vênh đã bị như vậy; đã gộp lại và chạy lại `colour_by_model.py`. Nay script đọc được mọi dạng và luôn ghi lại một dòng. Agent viết tay `place.json` dễ để `colorMap` nhiều dòng.
- Sau khi agent viết tay một nơi: chạy `colour_by_model.py <slug> --rounds 2`. Agent tự chọn màu xám bạc, trái quy tắc "màu thật, tươi" của chủ dự án.

**Đang chạy lúc bàn giao (chiều 11-10, chủ dự án yêu cầu "làm cho xong hết các địa điểm"):**
- `auto3d.py run` Datanla, Thung lũng Tình Yêu, Lang Biang với `--extra-kit nature` (PID 1322374, `logs/diorama/run_landscape_b_20261110.log`). Auto3d chọn `garden+nature`. Datanla đã 0,40 sau vòng đầu, hai nơi kia mới vào `build`.
- `auto3d.py run doimongmodalat --redo --extra-kit nature` (PID 1474496, `logs/diorama/run_doimongmo_20261110.log`). **Lưu ý:** NOTES đổi kit chính sang `stay` (`stay+nature`) trong khi bản cũ dùng `garden`. Cầu kính và vòm tim nằm ở `garden`, nên kiểm kết quả; nếu mất cầu kính thì ép `--kit garden --extra-kit nature --redo`.
- Nếu hai PID đã chết khi bạn đọc: `auto3d.py status` rồi chạy lại đúng lệnh trên (tiếp chỗ dở, không mất state). `failed:*` chạy lại bằng `run <slug>`.

**Yêu cầu chất lượng cho phiên tiếp theo (Opus mạnh hơn, quan trọng):**
- Người chấm trong auto3d dao động ±0,25; **cổng thật là Opus xem ảnh**. Với từng nơi, đặt ảnh thật cạnh render cuối (script ghép ảnh nằm trong history của phiên này: `contact.jpg` ở trên, `bridge/out/<tag>/00_initial.png` ở dưới), đừng tin điểm checklist.
- Mặt bằng luôn là minh họa; chỉ chấm đặc trưng nhận ra ở tầm tổng quan (khối, mái, màu, bố cục, nước, đồi). Bỏ qua chi tiết nhỏ.
- Sau mỗi nơi agent viết tay: `colour_by_model.py <slug> --rounds 2`; kiểm `colorMap` chỉ có **một** dòng. Màu phải thật, tươi (xanh đậm thay xám bạc), đúng quy tắc chủ dự án 11-04.
- Không tự publish, không build web, không deploy khi chưa được hỏi. Chủ dự án chưa trả lời hai câu: (1) có build `build_space3d` để Chênh Vênh bản mới lên web không (phiên khác đang sửa `web/space3d`); (2) có publish 6 nơi `ready` không.
- Quyết định chấm của mỗi nơi nằm trong `reason` và `history[opus_review]` của `auto3d.json`. Đừng chấm lại các nơi đã chấm trừ khi render đổi.

**Thứ tự việc còn lại cho xong hết:**
1. Chờ 4 lượt trên xong, chấm bằng ảnh. Nếu ba nơi cảnh quan chưa đạt thì sửa kit `nature` / `garden` bằng sol (brief mẫu ở `DATA/batch/briefs/BRIEF_k*.md`), không ép qua.
2. `queue --tier B --n 58 --parallel 3` (58 nơi hạng B; kèm `--extra-kit` chỉ khi cần). Cầu bridge chỉ có 3 worker, đừng chạy quá 3 lượt song song.
3. Chạy lại bằng `--redo --extra-kit nature` các nơi cần hồ / đồi: Terracotta, Quảng trường Lâm Viên, Euro Garden, Hoàng Long.
4. Task 8 (corpus, xem Việc tiếp theo cũ bên dưới): nơi hot còn thiếu và hạng C hot (134 nơi hạng C ≥ 1000 review).
5. Task 9: `docs/SPACE3D.md`, gộp / xoá các bàn giao, hỏi chủ dự án commit trên nhánh riêng.

**Việc tiếp theo (bản cũ, giữ để tham khảo):**
1. Chạy `build_space3d` (rồi `shots_space3d check`) để bản Chênh Vênh mới lên web. Hỏi chủ dự án trước, vì phiên khác đang sửa `web/space3d`.
2. Hỏi chủ dự án có publish 6 nơi ready không.
3. Task 7 bước 3: `auto3d.py run` Datanla, Thung lũng Tình Yêu, Lang Biang (hạng B; nên `--extra-kit nature`). Opus xem 100 %, rồi chạy lại Đồi Mộng Mơ và các nơi tạm đạt cần hồ / đồi (Terracotta, Quảng trường, Euro Garden, Hoàng Long). Sau đó `queue --tier B --n 58`.
4. Task 8, Task 9 như dưới. `scripts/diorama` vẫn chưa commit.

## Cách làm việc chủ dự án chốt
- Không dùng skill `superpowers:*` (cả cho Codex: đã tắt trong `~/.codex/config.toml`, và `run_agent.sh` truyền `-c 'plugins."superpowers@personal".enabled=false'`).
- Code giao cho **sol 6.1** qua `bash scripts/diorama/run_agent.sh sol <brief.md> <log> <low|medium|high> [ảnh…]` (Codex CLI, sandbox workspace-write + `--add-dir $DATA`); điều phối viên tự chọn effort và **tự review code** (đọc diff, chạy test). Brief viết tiếng Anh, có câu "Implement directly; no process skills, no questions".
- Chất lượng hơn tiết kiệm token; không trần token, dừng theo tiến bộ checklist.
- Không commit / push khi chưa được yêu cầu. Không deploy.

## Đã xong
| Task | Kết quả |
|---|---|
| 1 Tách code / dữ liệu | Code ở `scripts/diorama/` (**chưa vào git: thư mục untracked, chưa commit**), dữ liệu ở `tripguardian-store/splat/diorama/` (`DATA`, đổi bằng `DIORAMA_DATA`). `paths.py` / `paths.mjs`. Hồi quy `shots_space3d.mjs check` 29/29 ok. Bản gốc vẫn ở `logs/splat/diorama/` (chưa xoá; xoá khi đã commit `scripts/diorama`). |
| 2 Hạ tầng | `bash scripts/diorama/stack.sh up|status|down` (3 worker bridge, HTTP 8471/8472, 9router, codex, Chromium). |
| 3 Gieo nơi hot | `python -m corpus navigate seed` đọc `config/navigate.yaml` `seed.dalat`. |
| 4 auto3d v2 | `scripts/diorama/auto3d/` (gate, checklist, state, prompts, builder, steps, cli, exam, site); `python3 scripts/diorama/batch/auto3d.py queue|run|status|gallery|publish|add|exam|calibrate`. Ngưỡng `config/diorama.yaml`. 171 test `tests/diorama/`. Chạy lại tiếp chỗ dở; `failed:*` chạy lại bằng `run <slug>` (giữ notes). |
| 5 Đề thi | Builder **agent** thắng (Dinh III 0,90 / 1 vòng / 89k; Con Gà 0,75 / 4 vòng / 438k); hàm không render được Con Gà. `builder: agent`. Thêm `site.fit_site` (co đế, không token). |
| Hiệu chỉnh người chấm | `calibrate` trên 4 mô hình đã duyệt: người chấm dao động ±0,25 giữa các lần. `pass_ok_ratio: 0.5` (điểm thấp nhất của bản duyệt). Người chấm chỉ định hướng vòng sửa; **cổng thật là Opus xem `gallery` + chủ dự án duyệt**. |
| 6 Hạng A | 17 nơi đã chạy (≈ 3,4M token sol). Bảng dưới. |

### Hạng A (`auto3d.py status`)
| Trạng thái | Nơi |
|---|---|
| ready, **Opus đã xem, đạt** | Dinh I Bảo Đại |
| ready, Opus tạm đạt (làm lại sau kit cảnh quan: thiếu hồ, thô) | Quảng trường Lâm Viên |
| ready, **Opus chưa xem** | Chênh Vênh, Đồi Mộng Mơ, Hoàng Long Ohayo, Rừng Thông Núi Voi, Làng hoa Vạn Thành, QUÊ Garden, Thị Trấn Nobi, IXORA, Vườn Địa Đàng, Xuân Hương Garden |
| needs_kit | Đường Hầm Điêu Khắc (Opus loại: đường hầm bé giữa rừng thông, thiếu tượng đất sét → cần vật thể tượng / đường hầm đất sét) |
| needs_human | Ana Mandara (0,50, 395k), Euro Garden Cầu Đất (0,57) |
| failed:boot | Terracotta (`route_fix.mjs` quá 300 s; **đã sửa**: quá giờ thì bỏ qua route_fix → chạy lại `auto3d.py run terracottahote`) |
| skip | BBQ Mọ Tề (ảnh không đủ bằng chứng ngoại thất) |

## Việc tiếp theo (theo thứ tự)
1. `stack.sh status` — **9router đang MISSING** lúc bàn giao; khởi động lại theo `docs/LLM_PROVIDER.md` / `~/.9router/start-all.sh` trước khi gọi sol.
2. `auto3d.py run terracottahote`.
3. `auto3d.py gallery` → Opus xem 10 nơi chưa xem + 2 `needs_human` (xem `place.best.json` đã khôi phục). Ghi quyết định vào state (`stage` `needs_kit`/`needs_human` + `reason`, như đã làm cho `duonghamdieukh`).
4. Gửi chủ dự án ảnh gallery các nơi đạt → khi duyệt: `auto3d.py publish <slug…>` (cần HTTP 8472; không deploy).
5. **Task 7 kit cảnh quan** (sol high, mở rộng `kits/nature.js`, `garden.js`, catalog, ví dụ): hồ lớn, đồi nhiều tầng, đỉnh núi, rừng thông, thác nhiều bậc, cáp treo, điểm ngắm, quảng trường lớn, **tượng / đường hầm đất sét**. Hồi quy 29/29 + `checks/`. Thử Datanla, Thung lũng Tình Yêu, Langbiang; Opus xem 100 %; rồi `queue --tier B --n 58`; chạy lại `needs_kit`.
6. **Task 8 corpus** (xem bẫy bên dưới): Hầm vang Vĩnh Tiến đã crawl + ảnh nhưng chưa có `photo_scenes` (có lẽ cần `corpus build` tới `serving`); Crazy House (16.608 review, Maps xếp "Khách sạn 3 sao") nằm trong `list/dalat_stay.json` nhưng crawl chưa lấy nơi chỗ ở này — cần tìm phase crawl cho chỗ ở. Rồi lấy thêm ảnh (`GMAPS_PHOTO_TARGETS` + `GMAPS_PHOTO_CHIPS=1`) cho hạng C hot (Chợ Đêm, ZooDoo, Mê Linh, Langfarm, Làng Nấm, XQ, Dapa Hill, Đồi Thông Hai Mộ), `corpus build` (**không publish release**), rồi `auto3d.py run <fid>`.
7. **Task 9**: `docs/SPACE3D.md` chính thức, gộp + xoá 3 file bàn giao 11-04, spec, plan, file này; README / AGENTS / OPERATIONS; hỏi chủ dự án commit (đề xuất nhánh riêng, vì nhánh hiện tại `chore/prod-cleanup-20261109` có nhiều thay đổi đã stage của phiên khác).

## Thay đổi ngoài scripts/diorama (chưa commit)
- `src/corpus/navigate/{compare,__init__}.py`, `src/corpus/__main__.py`, `config/navigate.yaml`, `tests/navigate/test_navigate_seed.py`, `docs/CORPUS.md`: lệnh `navigate seed`.
- `src/corpus/crawl/gmaps/search.py` `parse_feed`: (a) chờ URL có FID khi Maps mở thẳng trang nơi (trước đây mọi tên khớp duy nhất bị bỏ: "Maps listed nothing"); (b) đọc category của khách sạn từ dòng tiêu đề. **Chưa có unit test** cho hai sửa này (đã thử trực tiếp trên Maps).
- `web/scripts/build_space3d.mjs` (đọc `scripts/diorama` + `DATA`), `.gitignore` (`scripts/diorama/vendor/node_modules/`), `scripts/README.md`.
- `RULE.md` §0.3 (rule symlink `.cache` / `.venv`), `docs/log/AGENT_FAILURES.md` F003.

## Bẫy đã gặp
- **`.cache` bị phiên khác trỏ sang `~/.cache` rồi xoá** (F003, nay là rule). Script 3D đọc thẳng `tripguardian-store/cache`.
- Không có Chrome: corpus cần `CORPUS_BROWSER_CHANNEL=chromium PLAYWRIGHT_BROWSERS_PATH=/data/work/luanhh/local/tripguardian-store/cache/ms-playwright`.
- Crawl Maps có đăng nhập: `CORPUS_PROFILE_STATE=1 … --profile gmaps_b2` (thư mục `.browser/gmaps` mặc định đã đăng xuất → `LoginRequired`). Crawl lại nơi nhiều review rất lâu (> 1 h); đặt `PYTHONUNBUFFERED=1` để có log.
- Gemma LAN (192.168.20.150:8900) tắt → `EXTRACTOR_ON_UIT=1` cho filter / photo_scenes.
- Filter corpus loại trường học (Đại học Đà Lạt, Cao đẳng Đà Lạt) — quy tắc có sẵn, giữ nguyên trừ khi chủ dự án đổi.
- Codex sandbox chặn socket: agent không tự chụp bridge được khi viết code; điều phối viên kiểm bằng tay ngoài sandbox.
- Lệnh `exam` / `calibrate` để lại `places/x_*` nếu `--keep`; xoá trước lần chạy sau.
