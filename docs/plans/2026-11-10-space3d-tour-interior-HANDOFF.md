# Bàn giao: tour 3D đi theo đường, vào thẳng trong nhà, animation mới, nơi chủ yếu nội thất (2026-11-10 tối)

Chủ dự án yêu cầu, giao cho phiên khác làm. Việc dựng 3D hàng loạt vẫn chạy nền, xem mục đầu của [bàn giao 3D](2026-11-10-3d-scale-HANDOFF.md).

## Trạng thái (2026-11-10 ~23:30, đọc trước)

| Việc | Trạng thái |
|---|---|
| 1. Animation vào 3D | **Xong.** `Space3d.tsx` + `space3d.css`: bỏ canvas vạch màu và loé sáng. Pha `in → wait → reveal → open → out`: tờ chi tiết mờ dưới lớp kem (`__veil`), poster phóng 760 ms từ thẻ ra cửa sổ và tiến nhẹ (scale 1 → 1,07), mô hình crossfade 650 ms khi có `space3d:ready`, chờ lâu thì hiện dòng nhỏ "Đang mở mô hình 3D…"; Back chạy ngược 680 ms. `reducedMotion`: chỉ mờ. `tsc` sạch. |
| 2. Tour đi theo đường | **Xong ở template**, mục `// === Walking tour` trong `index.template.html`. Hai điểm nối bằng một chặng `route` thì camera hạ xuống tầm mắt (1,7 m trên `routeHeight`), đi dọc chặng nhìn trước 7 m (cúi/ngẩng ≤ ~15°), rồi nâng lên khung `fitSpot` của điểm đích. Bắt đầu 5 m trước điểm xuất phát để đi xuyên cổng; dừng đi bộ 4 m trước điểm đích (tượng, lư hương đứng ngay trên điểm route). Lùi (←) đi ngược chặng; nếu camera của điểm đang đứng đã ở phía trước theo hướng đi thì nhập chặng ở chỗ gần camera nhất, chặng còn quá ngắn thì bay như cũ. Thời gian theo quãng đường (10 m/s đi bộ, đoạn hạ/nâng nhanh gấp 2,5), 2,6–8 s; cuộn chuột scrub được (`flight.ms` thay hằng 1400, patch trong `build_space3d.mjs` đã đổi theo). Cây đứng trên đường đi bị ẩn trong lúc đi. Không có route (`route: []`) hoặc hai điểm không kề nhau: bay như cũ. |
| 3. Vào thẳng trong nhà | **Xong ở template.** Điểm có `insideView` không còn nhấc mái / làm trong suốt tường trước (cutaway chỉ còn ở điểm không có nội thất). Vào: đi tới cửa (`interior.approach` → `entry`; sảnh chính dựng sẵn thì đi lệch qua chậu bonsai giữa hiên rồi vào cửa 2,2 m), đèn nội thất và độ tối bên ngoài đổi theo vị trí camera khi qua cửa (`hallDepth`). Ra: đi ngược qua cửa rồi theo chặng tới điểm kế. `checks/test_market_places.mjs` đổi kỳ vọng (điểm `stairs` của Chợ Mới giữ mái). Hook kiểm: `window.__walk(from, to, q)` dừng camera ở phân đoạn q. |
| 4. Nơi chủ yếu nội thất | **Bỏ** (chủ dự án 11-10 23:40: "k cần thì khỏi"). Trong 25 nơi ≥ 1000 review có nhiều ảnh nội thất, ít ảnh ngoài, chỉ ~7 nơi đặc biệt (Cafe Tùng, Là Việt, DEEM, On The Rocks…), phần còn lại là spa, buffet, quán bình dân, chuỗi; cần chế độ nội thất của auto3d + kit cà phê/bar chung, không đáng. Hạng `I` thử trong `hot_places.py` đã gỡ. |

**Cập nhật 2026-11-11: xong việc 2–3, deploy prod 11/11 cùng 100 nơi và warm mô hình (xem DEV_LOG `space3d-web`).**
- Chợ Mới vào `inside`: lỗi không phải `hallTop` mà là `hallBlocks` coi đoạn cửa → chỗ đứng trong nhà (cả hai đầu nằm trong khối) là cắt xuyên tường, nên camera nhảy lên nóc rồi rơi xuống. Nay đoạn có hai đầu cùng trong nhà là đi trong nhà (`inHall`).
- Ra khỏi nhà (Cam Ly 6 → 7, Dalat Palace 5 → 6): giữa hai điểm trên mặt đất bị nhà chắn thì đi bộ vòng qua 1–3 góc nhà (`hallDetour`, cách mép 2 m), chỉ khi không vòng được mới vượt nóc. Điểm vượt nóc mang cờ `air`: camera nhìn về điểm đích (không còn nhìn trời trống), bay nhanh như đoạn hạ / nâng, độ cao không bị làm mượt xuống dưới nóc.
- Vào nhà từ chính điểm của nó khi điểm đứng xa cửa (Cam Ly: điểm 6 ở phía tây, cửa phía đông): đi bộ từ điểm đứng vòng nhà tới cửa thay vì rơi từ trên không xuống cửa.
- Đã xem bằng ảnh: Chợ Mới 2 ↔ 3 ↔ 4, Cam Ly 5 ↔ 6 → 7, Dalat Palace 4 ↔ 5 → 6, Linh Sơn 0 → 1, 3 → 4 → 5, 1 → 0, Bơ Tơ Rơn Nun 2 → 3 → 4, Euro Garden (`route: []`, bay như cũ). Còn chấp nhận được nhưng chưa đẹp: Bơ Tơ Rơn Nun 3 → 4 lúc nâng lên khung điểm cổng camera lướt sát mái lá (~0,5 s); Dalat Palace 5 → 4 (lùi ra khỏi sảnh) nửa đầu nhìn ra xa rồi mới quay lại toà nhà.
- Dalat Palace: chặng route 5 → 6 trong `place.json` cắt qua khối `palace` (97 × 35 m), vùng nội thất chỉ là sảnh 14 × 25 m nên code không biết; lối ra hiện vượt nóc. Sửa dữ liệu route nếu muốn đi bộ vòng.
- Hồi quy: `checks/test_*.mjs` 16/16 exit 0; `shots_space3d.mjs check` 38/38; `test_space3d_scroll.mjs` đạt trên GPU (`SPACE3D_GL=gpu`; trên swiftshader máy tải ~66 thì quá giờ ở điểm 5, không phải lỗi logic). Đo trên GPU khi đi bộ: Chợ Mới / Cam Ly / Dalat Palace median 8–10 ms mỗi khung.
- Máy có GPU: `bridge/serve.py` tự dùng GPU (ANGLE gl-egl, RTX 2080 Ti, GPU 0) nếu Chromium headless tới được, không thì swiftshader (`DIORAMA_GL=swiftshader` để ép). `shots_space3d.mjs` / `test_space3d_scroll.mjs` nhận `SPACE3D_GL=gpu`. `shots_space3d.mjs` chờ `domcontentloaded` thay vì `load` (font Google chậm làm treo một nơi).
- Hook kiểm: `window.__walk(from, to, q)` nay trả thêm `raw` (các điểm đi trước khi lấy mẫu lại).

**Còn dở cũ (dừng 23:50 vì cấp GPU), đã xử lý ở mục trên:**
- Đã xem bằng mắt và đạt: Linh Sơn (qua cổng, vào chánh điện né chậu bonsai, ra cửa sang Quan Âm, lùi 2 → 1 bay như cũ vì camera điểm 2 ở phía trước), Bơ Tơ Rơn Nun (vào/ra theo trục cửa), Dalat Palace (vào sảnh), Cam Ly (vào nhà thờ).
- Chưa đạt / chưa kiểm sau sửa cuối: **Chợ Mới** vào `inside` ra khung nâu kín (camera trong khối nhà; kiểm vị trí camera bằng `window.__walk(2,3,q)` + `__inspect().cameraPosition`, nghi `hallTop` mặc định 12 m thấp hơn nhà chợ nhiều tầng hoặc `dimmingSize` 98×68 làm vùng chặn quá rộng); **Cam Ly** ra 6 → 7 và **Dalat Palace** ra 5 → 6 cắt xuyên mái / tường, đã thêm `hopOver` (vượt lên trên nóc nhà có nội thất khi đoạn nối cắt qua nó) nhưng chưa render lại. Euro Garden (`route: []`) chụp quá giờ khi máy tải cao, chưa thấy khung.
- Script kiểm: `/tmp/claude-2420/…/scratchpad/walkshots.py` (mất khi dọn /tmp); cách làm: build bằng `build.py` vào `out_wt<tên>`, chép sang `out_local_wt<tên>` có symlink `vendor`, mở `http://127.0.0.1:8471/…` bằng chromium swiftshader, gọi `__walk(from,to,q)` rồi chụp.
- Sau khi đạt: `node web/scripts/build_space3d.mjs` + `shots_space3d.mjs check` (patch `flight.ms` nhận cả template cũ lẫn mới); deploy prod hỏi lại.
- `tests/agents/test_runtime.py` có 3 test thời gian fail khi máy tải ~55, fail cả trên code đã commit, không liên quan.


## Yêu cầu (nguyên văn chủ dự án, 11-10 tối)

> tui muốn nơi nào có nội thất ít cái bên ngoài thì hiện nội thất các thứ decor bên trong, đổi animation đẹp hơn animation tới chỗ xem 3d xấu quá, tui muốn thứ tự đi vào như thứ tự mỗi tên nghĩa là bấm 1 thì bấm 2 sẽ đi qua cổng ở số 1 kiểu nó theo đường đi, không cần mở như hình 3 mà cho đi thẳng vào bên trong xem nội thất ấy

Ảnh kèm theo (Chùa Linh Sơn): (1) màn chuyển vào 3D với vạch màu cầu vồng và chữ "Đang bước vào…"; (2) tổng quan có điểm dừng 1–9, điểm 1 là cổng tam quan, điểm 2 là lối đi giữa sân; (3) điểm 4–5 mở chánh điện kiểu cắt: mái nhấc lên, tường trước trong suốt.

Bốn việc, theo thứ tự nên làm:

### 1. Đổi animation vào màn 3D
- Code: `web/src/user/ui/Space3d.tsx`. Hiện là "dive" kiểu Link Start: poster phóng to, phòng tối dần, vạch màu cầu vồng lao qua (canvas `tg-s3v__streaks`), loé sáng rồi hiện mô hình; Back chạy ngược. Chủ dự án thấy xấu.
- Hướng làm: bỏ vạch màu và loé sáng. Poster (ảnh tổng quan của chính mô hình) phóng mượt từ thẻ ra toàn cửa sổ, đồng thời zoom nhẹ vào mô hình. Mô hình thật hiện lên bằng crossfade khi khung đầu đã vẽ, dùng tông kem của mô hình chứ không nền tối. Back chạy ngược lại. Giữ `reducedMotion`: chỉ fade.
- Giữ nguyên cách tải: iframe cùng origin, gỡ frame thì GPU được giải phóng, tab chỉ có ở nơi nằm trong `/space3d/index.json`.

### 2. Tour đi theo đường, đúng thứ tự số
- Muốn: đang ở điểm 1, bấm 2 (hoặc nút tiếp, phím →, cuộn chuột) thì camera **đi dọc lối đi** từ 1 sang 2 ở tầm người, qua cổng ở điểm 1, như người đi bộ. Không bay vòng cung trên không như hiện nay.
- Code (template dùng chung cho mọi nơi): `scripts/diorama/index.template.html`
  - `moveTo()` (~dòng 2453): `flight` nội suy từ camera tới camera, có `arc` nhấc lên không trung. Nhà có nội thất thì dùng `buildInteriorFlightPath`.
  - `openSpot()` / `goTour()` / `nextTour()` (~2476–2545); `fitSpot(spot)` cho khung nhìn tại mỗi điểm.
  - `place.route` + `routeSegments` (~2278): mỗi chặng (leg) là polyline 2D đã làm tròn (`roundWalkingPath`), có `routeHeight(x,z)` bám mặt đất. `tourRoute(from)` đang chỉ vẽ mũi tên chặng kế tiếp.
  - `web/space3d/scroll.js` (được chèn vào template): cuộn chuột đi từng chặng theo `flight.scrub` / `flight.q`. Đường đi mới phải scrub được theo `q`.
- Hướng làm: nếu có chặng route nối điểm i với i+1 thì `flight` đi theo spline của chặng đó. Mắt cao ~1,6–2 m trên `routeHeight`, nhìn theo hướng đi, tốc độ đều theo quãng đường. Tới gần điểm đích thì hoà dần về khung `fitSpot` của điểm đó. Không có route (nhiều nơi `route: []`) thì giữ cách bay cũ. Lùi (←) đi ngược chặng. Cây hoặc vật che tầm mắt trên đường: dùng `setForegroundVisibility`, đang ẩn cây che điểm dừng.

### 3. Bỏ kiểu "mở nhà" (cutaway), đi thẳng vào trong
- Hiện tại: điểm có `cutaway` thì `hallCutaway` nhấc mái (`cutaway.lift` 7,4) và làm tường trước trong suốt (ảnh 3). Điểm có `interior` thì `configureInteriorView`, `exteriorDim`, `altarLight`, `interiorFill` lo phần bên trong.
- Muốn: camera đi qua cửa vào trong ở tầm mắt; mái và tường giữ nguyên, nhìn nội thất từ bên trong. Gợi ý: ẩn mặt tường hoặc mái nằm giữa camera và target (raycast theo `objectId`), chỉnh near-plane, bật đèn nội thất, ra khỏi nhà thì hiện lại. Bỏ cutaway khỏi tour; để code cũ thì chỉ dùng khi không có nội thất.
- Kit nội thất đã đăng ký: `registerInteriorKit` (`pagoda`, `buddhist_altar` ở `kits/pagoda.js`, `stay_lounge` ở `kits/stay.js`); xem `scripts/diorama/kits/README.md` (mục interior).

### 4. Nơi nhiều ảnh nội thất, ít ảnh ngoại thất: dựng nội thất
- Hiện tại `batch/hot_places.py` xếp hạng chỉ bằng ảnh `exterior` + `view` (A: ext ≥ `evidence_min`; B: ext + view ≥ `evidence_min`; còn lại C). Nơi có 20–30 ảnh `interior`/`room` mà ít ảnh ngoại thất (nhiều quán cà phê, nhà hàng, bar, khách sạn) thì rơi vào C và bị bỏ.
- Muốn: những nơi này hiện **nội thất**: bàn ghế, quầy, đèn, cây, màu tường, tranh, cửa sổ nhìn ra ngoài. Không bịa: chỉ dựng cái có trong ảnh interior (quy tắc "không bịa", `AGENTS.md`).
- Hướng làm: thêm một hạng nội thất trong `hot_places.py` (ext + view < `evidence_min` và interior ≥ ngưỡng, ghi ngưỡng vào `config/diorama.yaml`). auto3d có chế độ nội thất: NOTES và build lấy ảnh interior làm bằng chứng; vỏ nhà tối giản kèm cửa; tour chủ yếu bên trong (dùng việc 3). Có thể cần thêm kit nội thất chung cho cà phê / nhà hàng / bar (giao sol khi đủ lớn, xem `scripts/diorama/run_agent.sh`, brief mẫu `DATA/batch/briefs/`).
- Chọn nơi: chủ dự án chỉ muốn nơi **đặc biệt, đẹp, nổi tiếng** ("cái nào đặc biệt thì làm, không thì thôi"); không làm chuỗi (Lotteria, KATINAT, Phê La…) hay khách sạn thường. Lập danh sách ứng viên, hỏi chủ dự án trước khi chạy hàng loạt.

## Ràng buộc
- `scripts/diorama/index.template.html` **đang được chuỗi dựng 3D dùng** (PID 639063, `logs/diorama/after_queue_tierAB_20261110.sh`): mỗi lần build chép template lúc đó. Sửa trên bản sao (ví dụ worktree của nhánh `feat/diorama-scripts`, cách làm ở mục "Git" của bàn giao 3D), kiểm xong mới thay file thật một lần, hoặc chờ chuỗi chạy xong.
- `web/space3d/*` và `Space3d.tsx` đang có thay đổi chưa commit của phiên khác (nhánh `chore/prod-cleanup-20261109`). Chỉ sửa phần thuộc việc này.
- Kiểm: bridge chụp bằng swiftshader (`bridge/shot.py <tag> --out out_<slug>`, timeout mỗi view nay 90 s); hồi quy `shots_space3d.mjs check` mọi nơi đã publish (38 nơi trong `web/space3d/places.json`); test template ở `scripts/diorama/checks/`; xem bằng mắt Chùa Linh Sơn (`DATA/linhson.json`: 9 điểm, 7 chặng route, `chanh-dien` dùng `cutaway: main-hall`, `chanh-dien-inside` có `interior`) và một nơi `route: []`.
- Sau khi đổi template phải build lại mọi nơi: `node web/scripts/build_space3d.mjs`. Chủ dự án đã đồng ý build một lần cùng đợt publish hạng B. **Deploy prod phải hỏi lại.**
- Không dùng skill `superpowers:*`. Tự code (Edit/Write); chỉ giao sol khi việc thật lớn và tách được. Không commit / push khi chưa được yêu cầu.
