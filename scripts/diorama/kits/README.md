# Architecture kits

List kit basenames in `place.kits` (for example `["church"]`); `build.py` inlines
`kits/church.js` at `/*__KITS__*/` before building objects and hashes the final scripts.
Place data can live at `places/<slug>/place.json`, with evidence in its sibling `photos/`.

- `registerObjectType(type, builder)`: `builder(object)` adds geometry to `scene`.
- `registerInteriorKit(name, builder)`: `builder(building, {roof, front})` returns
  `{group, ceiling?, door?, front?}`. `group` is the furnishing; optional ceiling
  moves with `roof`; door/front override the built-in entrance/cutaway layer.
  A missing/unknown `building.interior.kit` keeps the building closed and removes
  its interior stops. An interior stop selects its building through `building`;
  only an omitted building id falls back to `role: "main"`.

Builders share module scope: `THREE`, `mesh`, `box`, `detail`, `material`, `palette`,
`vietnameseRoof`, `roofRecords`, `contactShadow`, `walkableGeometries` and
`modelEnvelopes` are reachable. Use `mesh` or `box`/`detail` so the object loop
collects transformed vertices into framing envelopes. `box`/`detail` batching is
available only during object builders: interior builders run after batches flush
and must return a `THREE.Group` containing their own meshes instead. For nested/instanced meshes,
add any extra framing points to `currentEnvelope`. Add paved geometry to
`walkableGeometries` if a route traverses it; add contact shadows as needed.

A cutaway-capable building must register each roof tier in `roofRecords` with
`{group, parameters, tiers, thickness, ridgeOrnament}` (`vietnameseRoof` does this).
The object loop stamps each new record with its owning `objectId` and base height.
`hotspot.cutaway` selects that object; `building.cutaway.lift` defaults to 7.4 m.
Keep kit declarations scoped (for example an IIFE), and do not include script tags.
`example.js` is a box fixture used only by `test_generic.mjs`.

## nature

`kits: ["nature"]` nạp họ cảnh quan, hồ, đồi, suối/thác và khu cắm trại dùng chung.
Đơn vị mét; local +x ngang vách, +z hướng xuống hồ chân thác, +y hướng lên.
Không phân nhánh theo tên nơi hoặc viết JavaScript riêng cho từng nơi. Ví dụ đầy đủ:
`examples/nature.place.json`; kiểm thử build/boot, hình học và mặc định cũ:
`checks/test_nature_landscape.mjs`, `checks/test_nature_extension.mjs`.

Common options for all types: `id: string` (required, unique; semantic root is
`<id>-nature`), `position: [x,y,z] = [0,0,0]`, `rotation: number = 0` (degrees around y).
Coordinates inside each object are local. Palette fields accept CSS colour strings.
Seeds are deterministic integers, not site-specific procedural code. Colours come
from the source photos (owner 2026-11-04: vivid, true to photos, not grey or cold);
the viewer adds one warm grade pass, so write real colours, not greyed ones.

### `nature_terrain`

Rock escarpments, undercut cliffs or valley sections. Prenn g11/g12/g22/g25 show the
wide low rock lip and recessed walking space; use other photos to author another section.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `size` | `[width,height,depth]` / `[28,8,12]` | Span and default cross-section dimensions. With explicit section, height also sets strata range. |
| `section` | `[z,y,widthScale?][]` / `[[-d/2,0],[-d/2,h],[d/2,.94h],[.05d,.22h],[-.1d,0]]` | Ordered closed solid cross-section; optional width multiplier defaults to 1. Allows an overhang without filling the path below. |
| `jaggedness` | number / `.32` | Small lateral relief and rim height variation. |
| `segments` | positive integer / `28` | Across-cliff subdivisions. |
| `strata` | nonnegative integer / `12` | Thin rock courses; 0 for a plain grassy valley mass. |
| `boulders` | nonnegative integer / `12` | Small grounded stones at the foot. Use 0 beside narrow paths. |
| `moss` | boolean / `true` | Low foam patches near the highest section row; scaled to that row and raycast onto the actual cap. Unsupported candidates are skipped. |
| `seed` | integer / `1` | Stable relief/stone/patch placement. |
| `color` | colour / `#9b9685` | Rock or terrain colour. |
| `seamColor` | colour / `#797b6a` | Fine strata line colour. |
| `boulderColor` | colour / `color` | Stone colour (falls back to rock default). |
| `mossColor` | colour / `#929f80` | Foam cap colour. |

### `nature_water`

Flat pools, streams and valley lakes. Prenn g21/g25 establish the calm, muddy pool;
it is not a bright-blue swimming pool.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `size` | `[width,depth]` / `[24,18]` | Default ellipse dimensions. |
| `outline` | `[x,z][]` / 48-point ellipse | Explicit shoreline polygon. |
| `level` | number / `.035` | Surface above object base; not walkable. |
| `color` | colour / `#a4b0a0` | Opaque studio water, no mirror/refraction dependency. |
| `ripples` | nonnegative integer / `22` | Candidate fine elliptical arcs, clipped inside the shoreline. |
| `rippleCenter` | `[x,z]` / `[0,0]` | Impact centre for ripples. |
| `rippleColor` | colour / `#e1e6dc` | Quiet ripple line colour. |
| `seed` | integer / `3` | Stable arcs. |

### `nature_cascade`

One profile-driven builder covers wide curtain falls or repeated short cascades. Prenn
g11/g21/g25 show its width/height ratio; g12/g22 show the lip standing in front of the path.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `width` | number / `16` | Upstream sheet width. |
| `profile` | `[z,y][]` / `[[0,8],[.5,7.6],[1.2,.035]]` | Ordered downstream centreline, from rock top to pool. Last y must match the pool level (foam bottoms sit there). Duplicate the object for separate cascade tiers. |
| `ribbons` | positive integer / `80` | Across-sheet resolution and stream detail density. |
| `segments` | positive integer / `36` | Downstream subdivisions, sampled by profile arc length. |
| `edgeWaviness` | number / `.16` | Small irregularity at the sheet margins, in metres. |
| `flowVariation` | number 0–1 / `.5` | Seeded colour blend towards foam, creating quiet vertical flows. |
| `spread` | number / `.05` | Fractional widening at impact. |
| `color` | colour / `#c9d5ce` | Continuous water sheet colour. |
| `foamColor` | colour / `#e1e6dc` | Fine stream lines and low impact foam. |
| `seed` | integer / `5` | Stable streaks/foam. |

### `nature_path`

Visible stone paving, route support, joints, optional handrails. Prenn g10/g13/g14
show paved pool margins and blue railings; g22 shows the wooden handrail behind the curtain.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `points` | `[x,y,z][]` / `[[-5,0,0],[5,0,0]]` | Piecewise path centreline; y is its local underside. |
| `width` | number / `3.2` | Paved width including rounded joint caps. |
| `thickness` | number / `.1` | Paving thickness. |
| `jointSpacing` | number / `1.1` | Across-path stone joint spacing. |
| `edges` | boolean / `true` | Low kerb on both sides. |
| `color` | colour / `#d3cec0` | Paving. |
| `jointColor` | colour / `#b7b5a6` | Fine slab seams. |
| `edgeColor` | colour / `#aaa892` | Kerb. |
| `railHeight` | number / absent (no rails) | Handrail height above paving. |
| `railSides` | `(-1\|1)[]` / `[-1,1]` | Side of each directed segment; +1 is its local right. |
| `postSpacing` | number / `1.8` | Maximum handrail post spacing. |
| `railColor` | colour / `#7e8879` | Posts and two horizontal rails. |

### `nature_bridge`, `nature_deck`

Shared plank-platform builder; bridge has a sagging profile, deck is flat. Neither
is asserted to exist at Prenn. The example demonstrates them for camping/valley photos
showing suspended timber crossings, stakes, ropes or viewing platforms.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `size` | `[width,length]` / bridge `[2.8,14]`, deck `[7,5]` | Local z follows the span. |
| `height` | number / bridge `1.3`, deck `.3` | End deck surface height above base. |
| `sag` | number / `.45` (bridge only) | Middle drop; must be less than height minus thickness/foot level. |
| `footY` | number / `0` | Local ground level for grounded posts. |
| `thickness` | number / `.14` | Plank depth. |
| `plankWidth` | number / `.28` | Length of a plank along the span. |
| `postSpacing` | number / `2.5` | Maximum spacing along side rails. |
| `rails` | boolean / `true` | Both long-side rails; span ends stay open. |
| `railHeight` | number / `1.05` | Height above the sagging surface. |
| `ropeRadius` | number / `.028` | Rope/rail radius. |
| `color` | colour / `#95826c` | Timber. |
| `railColor` | colour / `#7e8879` | Ropes and posts. |

### `nature_tent`

Họ lều và cabin trên sàn: `style` chọn đúng hình dáng có trong ảnh. Mặc định vẫn là
lều chữ A. Chỉ dựng nơi ảnh có bằng chứng; Prenn không dùng lều. Không tự đăng ký
tour nội thất: hai bộ ảnh Bên Suối / Lon ton đều dưới ngưỡng bốn ảnh nội thất.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `size` | `[width,height,depth]` / `[3,2.1,3.6]` | Canvas dimensions. |
| `baseHeight` | number / `.12` | Floor/platform height. |
| `guySpread` | number / `.8` | Peg distance outside canvas sides. |
| `color` | colour / `#b7ae91` | Muted fabric. |
| `floorColor` | colour / `#95826c` | Floor. |
| `doorColor` | colour / `#626d60` | Dark triangular flap. |
| `ropeColor` | colour / `#7e8879` | Guy ropes. |

Các tùy chọn mở rộng dưới đây chỉ tác động khi chọn một `style` mới; không đổi
hình học, màu, seed hoặc route của lều chữ A và các type cũ.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `style` | enum / `"a_frame"` | `safari`: vách đứng, mái tối, hiên mở (Bên Suối g00/g03/g20); `bell`: nón tròn có cột giữa (Lon ton g00/g04/g12); `glass_a_frame`: mái tam giác, mặt kính chia khung gỗ (Bên Suối g02/g05/g19); `dome`: lều vòm có sườn cong (ví dụ tổng hợp, không thêm vào nơi thiếu bằng chứng). Giá trị lạ báo lỗi. |
| `size` | `[width,height,depth]` / nhánh mới `[4.5,3,4.8]` | Kích thước thân lều; chiều cao tính trên sàn. Bell/dome dùng hai bán kính `width/2`, `depth/2`, không dùng footprint chữ nhật làm thân lều. |
| `baseHeight` | number / `.12` | Chiều dày sàn; nếu đã có `nature_deck` riêng thì đặt `.035` và đặt chân lều trên mặt deck, tránh hai sàn dày chồng nhau. |
| `wallHeight` | number / safari `.6*height`, bell `.5` | Vách đứng dưới mái; chặn trên ở `.85*height`. Không biến safari thành tam giác sát đất. |
| `roofColor` | colour / `#697163` | Mái phủ safari / mái cabin; không nhuộm tối toàn bộ vách canvas. |
| `roofOverhang` | number / `.35` | Độ vươn mái safari mỗi bên và phía sau. Chừa khoảng giữa hai lều cho mái và dây neo. |
| `porchDepth` | number / `.55` | Phần hiên mái safari vươn về local +z; sàn riêng phải đủ dài. |
| `openWidth` | number / `.46` | Bề rộng cửa mở safari theo tỷ lệ width. Cửa là khoảng rỗng thật, không phải hình tam giác vẽ lên vách kín. |
| `frameColor` | colour / `#95826c` | Cột safari, cột giữa bell, khung cabin và sườn dome. |
| `frameRadius` | number / `.045` | Bán kính thanh chéo khung cabin kính; dùng nét nhỏ, không tạo khung quá dày. |
| `glassColor` | colour / `#a6b4ad` | Mặt kính cabin dạng matte; không phụ thuộc phản chiếu hay truyền sáng thời gian thực. |
| `doorWidth` | number / `min(1.05,.3*width)` | Khung cửa giữa cabin; chiều cao tự giới hạn `min(2.05,.68*height)`. |
| `segments` | integer / `40` | Số múi lều bell; nét may lấy mỗi bốn múi. Dome dùng vòm và sườn cố định, không dùng tùy chọn này. |
| `guySpread` | number / `.65` | Khoảng cọc neo safari/bell; không áp dụng cho cabin kính/dome. |
| `seamColor` | colour / `#8d927e` | Nét may vải / đường mái mảnh. Tránh tương phản đen. |

### `nature_path` — đá rời và lối ván

Giữ nguyên API đường lát ở trên. `pattern` chỉ đổi cách thể hiện mặt đi, không đổi
`points` hay cách tính mặt dốc/cap. Phù hợp đá rời Bên Suối g03/g20, Lon ton g00/g04
và ván ven suối Bên Suối g07/g11. Không dùng `nature_water` làm nền đường.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `pattern` | enum / `"paved"` | `"stepping"`: từng viên đá đa giác; `"boardwalk"`: từng ván gỗ; `"paved"`: hành vi cũ. Giá trị lạ báo lỗi. |
| `stepLength` | number / `.65` | Chiều dài mục tiêu của đá theo đường; chia đều mỗi đoạn nên chiều dài thực có thể nhỏ hơn. |
| `stepGap` | number / `.22` | Khoảng hở giữa đá; giữ nhỏ để route đọc như lối đi bộ. |
| `stoneWidth` | number / `min(.8,.88*width)` | Bề rộng viên đá ở tỷ lệ bước chân; `width` vẫn là hành lang hỗ trợ route. Chỉ tăng riêng stoneWidth nếu ảnh có phiến đá lớn. |
| `stagger` | number / `.12` | Biên độ lệch ngang tổng của đá, có seed; đừng đặt quá lớn ở lối hẹp. |
| `seed` | integer / `17` | Biến thiên đá tái lập. |
| `plankWidth` | number / `.24` | Nhịp ván dọc đường `boardwalk`; khe ván nhỏ `.013` m. |

Đá/ván dùng instancing. Slab/cap hỗ trợ route được gộp thành mesh ẩn
`<id>-route-support`, không đổ dải màu vào khe đá. Đường vẫn liên tục cho mũi tên;
đây không phải mô phỏng bước chân trên từng viên. Tay vịn dùng API cũ; kerb bị tắt
trong hai pattern này. Chừa lối khỏi deck/lều: cạnh sàn cao cần đoạn tiếp cận đúng cao độ.

### `nature_canopy`

Bạt trắng kéo căng có đỉnh cao, mép võng và các cạnh mở; không phải lều thấp kín
(Bên Suối g06/g10). Bạt có bề mặt cong, cột và dây neo instanced.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `size` | `[width,height,depth]` / `[8,4.2,6]` | Khung phủ bạt, height cấp đỉnh mặc định. |
| `peaks` | `[x,z,height][]` / `[[0,0,height]]` | Đỉnh trong local footprint, chia bạt theo thứ tự x. Nhiều đỉnh phải có x khác nhau và nằm trong khung. |
| `edgeHeight` | number / `2.1` | Cao độ góc bạt. |
| `edgeSag` | number / `.5` | Độ võng giữa hai góc; giữ `edgeHeight-edgeSag` đủ cao ở cạnh có người đi. |
| `curvature` | number / `.42` | Độ lõm từ đỉnh về mép; tránh bạt phẳng như mái tôn. |
| `segments` | integer / `16` | Chia mỗi mép; bề mặt chia tám vòng về đỉnh. |
| `guySpread` | number / `.8` | Khoảng neo vượt góc bạt; cần chừa ngoài footprint. |
| `color`, `poleColor`, `ropeColor`, `seamColor` | colour / `#dfdfd0`, `#95826c`, `#7e8879`, `#b3b7a6` | Màu bạt matte, cột, dây và viền mảnh. |

### `nature_stream`

Suối đá có bờ, đá cuội và nét dòng nước, tùy chọn lối ván men một bờ
(Bên Suối g07/g11/g13/g16). Nước và lòng suối không phải mặt hỗ trợ route.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `points` | `[x,y,z][]` / `[[0,0,-8],[0,0,0],[1,0,8]]` | Tim suối có cao độ; tối thiểu hai điểm khác nhau. Chia thêm điểm cho khúc cong, tránh góc gấp ngược. |
| `width`, `bankWidth` | number / `3.5`, `.85` | Rộng nước và bờ mỗi bên. |
| `level` | number / `.04` | Mặt nước trên tim suối; không phải cao độ tuyệt đối. |
| `boulders`, `boulderScale` | integer / `42`; number / `.65` | Số mục tiêu và cỡ đá seed, phân bố ở bờ và trong dòng. Loại đá có footprint chạm hành lang ván + `.1` m; tối đa 50 lần thử/đá nên cấu hình quá chật có thể nhận ít đá hơn. |
| `flowLines` | integer / `65` | Nét nước ngắn theo hướng dòng. |
| `seed` | integer / `11` | Bố trí đá và nét dòng tái lập. |
| `color`, `bankColor`, `boulderColor`, `foamColor` | colour / `#a4b0a0`, `#b4b39d`, `#a19f8e`, `#e1e6dc` | Bảng màu nước/bờ/đá/nét nước trầm. |
| `boardwalk` | object / không có | Chỉ dựng khi ảnh có lối gỗ; không mặc định thêm cầu hay sàn. |
| `boardwalk.side` | `-1\|1` / `1` | Bờ theo hướng points; +1 là bên phải của tim. |
| `boardwalk.width`, `.gap` | number / `1.8`, `.35` | Bề rộng lối và khoảng từ mép nước; gap nên đủ cho đá bờ để không xuyên ván. |
| `boardwalk.height`, `.thickness`, `.plankWidth` | number / `.18`, `.12`, `.24` | Cao độ đáy lối trên tim suối, dày ván và nhịp ván. Route nằm ở height + thickness. |
| `boardwalk.railHeight` | number / không có | Có giá trị thì dựng tay vịn; không có thì để mở. |
| `boardwalk.railSides` | `(-1\|1)[]` / phía nước | Theo hướng đi của lối ván, không phải hướng camera. |
| `boardwalk.color`, `.railColor` | colour / `#95826c`, `#7e8879` | Màu ván và tay vịn. |

Lối ván là child `<id>-boardwalk-nature` của suối, đã ghi geometry route ở đúng
world transform. Không nhân đôi position/rotation khi đặt suối xoay. Cần nối route
đúng tim lối; khúc suối cong không có nghĩa route thẳng vẫn đi trên ván.

### `nature_lights`

Dây bóng rủ giữa cột, không có mái hay tường (Bên Suối g08/g09/g17; Lon ton g02/g09/g22).

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `points` | `[x,y,z][]` / `[[-4,0,0],[4,0,0]]` | Chân cột; các đoạn dây nối theo thứ tự. Điểm trùng không tạo thêm cột. |
| `height`, `sag` | number / `3.4`, `.45` | Cao dây trên chân cột, độ rủ giữa nhịp; chừa mái lều và khoảng đầu người. |
| `bulbSpacing`, `bulbRadius` | number / `.75`, `.07` | Khoảng bóng và bán kính bóng; không phóng to để giả ánh sáng ban đêm. |
| `postRadius`, `wireRadius` | number / `.04`, `.009` | Bán kính cột và dây. |
| `postColor`, `wireColor`, `bulbColor` | colour / `#95826c`, `#707969`, `#e4dcc3` | Cột gỗ, dây trầm và bóng ấm. |
| `glow` | number / `.12` | Emissive nhẹ; không tạo PointLight theo từng bóng, không đổi ánh sáng studio toàn cảnh. |

### `nature_firepit`

Vòng đá quanh tro và củi, ghế thân gỗ xếp theo góc; không dùng bệ đá vuông hay sàn
mini làm ghế (Bên Suối g09/g17, Lon ton g02).

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `radius`, `stones` | number / `.85`; integer / `18` | Bán kính tim vòng và số đá. |
| `stoneSize` | `[tangent,height,radial]` / `[.37,.28,.32]` | Kích thước toàn phần của đá vòng, không phải bán kính; chọn theo chu vi, tránh vòng thành một khối đặc. |
| `seats` | `[angleDegrees,distance,length][]` / `[[0,2.2,1.8],[120,2.2,1.8],[240,2.2,1.8]]` | Ghế thân gỗ, góc 0 ở +z, chiều dài tiếp tuyến vòng; `[]` bỏ ghế. |
| `seatHeight` | number / `.42` | Cao mặt ghế, không phải bán kính thân gỗ. |
| `seed` | integer / `5` | Biến thiên đá. |
| `ashColor`, `stoneColor`, `logColor`, `seatColor`, `endColor` | colour / `#828474`, `#a3a18f`, `#7e806b`, `#95826c`, `#b8aa90` | Tro, đá, củi, ghế và mặt cắt đầu gỗ. Không tự thêm lửa lớn hay hiệu ứng phát sáng. |

### `nature_furniture`

Bàn picnic/bàn dài, ghế băng, thân gỗ hoặc ghế gấp đúng tỷ lệ người
(Bên Suối g08/g20, Lon ton g01/g02/g26).

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `kind` | enum / `"picnic_table"` | `picnic_table`, `table`, `bench`, `log_seat`, `folding_chair`. Giá trị lạ báo lỗi. |
| `size` | `[length,height,depth]` / bàn `[2.4,.75,.85]`, bench `[2,.43,.35]`, log `[1.8,.42,.42]`, chair `[.6,.85,.6]` | Chiều dài bàn/ghế theo local x; `rotation` vẫn tính độ. Không dùng deck làm mặt bàn vì deck có route support sai cao độ. |
| `color`, `seatColor`, `endColor` | colour / `#95826c`, `color`, `#b4a58b` | Gỗ, mặt ghế picnic, đầu thân gỗ. |
| `fabricColor`, `frameColor` | colour / `#adb096`, `#7b8375` | Vải và khung ghế gấp; không tác động loại khác. |

### `nature_pavilion`

Sàn gỗ có cột, mái lưới hoặc vải che và bàn dài (Lon ton g01/g22/g26). Hai đầu sàn
mở, không bịa phòng kín hay tour nội thất từ một ảnh sân có mái.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `size` | `[width,height,depth]` / `[8,3.2,7]` | Height là chiều cao cột trên deck, không gồm deckHeight. |
| `deckHeight` | number / `.3` | Mặt sàn có hỗ trợ route; đường tiếp cận phải lên đúng cao độ trước mép sàn. |
| `roof` | enum / `"net"` | `net` có bề mặt mờ và lưới nét mảnh; `shade` là bạt đặc. Giá trị lạ báo lỗi. |
| `netOpacity`, `netSpacing` | number / `.32`, `.22` | Độ đậm và ô lưới; chỉ áp dụng net, không phải ván gỗ làm mái. |
| `netColor`, `roofColor`, `frameColor` | colour / `#7f8978`, `#a7ae9b`, `#95826c` | Nét lưới, mặt mái và khung. |
| `postRadius` | number / `.065` | Bán kính cột mái, không đổi cọc lan can. |
| `tables` | `[x,z][]` / `[[-2,0],[2,0]]` | Vị trí bàn trên deck; `[]` bỏ bàn. |
| `tableSize`, `tableRotation`, `tableColor` | `[length,height,depth]` / `[4.6,.75,.9]`; degrees / `90`; colour / `#95826c` | Bàn picnic dài có ghế hai bên; giữ khoảng đi giữa bàn. |
| `rails`, `railHeight` | boolean / `true`; number / `.9` | Lan can hai cạnh dài; không chặn hai đầu vào sàn. |
| `thickness`, `plankWidth`, `postSpacing`, `ropeRadius`, `footY`, `color`, `railColor` | như `nature_deck` | Tái sử dụng toàn bộ cấu tạo sàn. Không dùng tùy chọn `height` của deck thay cho `deckHeight`. |

### `nature_gravel`

Mảng sỏi có hạt nhỏ instanced, không phải hồ nước đổi màu (Lon ton g02/g09/g14;
khu bếp lửa Bên Suối g09).

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `size` | `[width,depth]` / `[8,6]` | Hình chữ nhật nếu không có outline. |
| `outline` | `[x,z][]` / bốn góc size | Polygon đơn, không tự cắt; mọi hạt được kiểm nằm trong polygon. |
| `thickness` | number / `.055` | Mặt sỏi trên chân object; có route support thật. |
| `granules`, `grainSize` | integer / `240`; number / `.045` | Số hạt mục tiêu và cỡ hạt; polygon quá mảnh có thể nhận ít hạt hơn. |
| `seed` | integer / `19` | Rải hạt tái lập. |
| `color`, `grainColor`, `lightColor` | colour / `#bdb8a6`, `#aba996`, `#cecaba` | Nền và hai sắc độ hạt. Giữ hạt nhỏ, không biến sân sỏi thành bãi đá cuội. |

### `nature_terrace`

Mặt cỏ trên đồi có thành đất giữ mép và nét viền thấp (Lon ton g04/g05/g06).
Ghép nhiều object cùng ramp nghiêng để dựng tầng; không đặt lều lơ lửng trên một khối dốc.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `size`, `outline` | `[width,depth]` / `[12,7]`; polygon / bốn góc size | Mặt bằng tầng cỏ. |
| `height` | number / `.65` | Cao mặt cỏ ở tâm; không cộng thickness ẩn. |
| `slope` | `[risePerX,risePerZ]` / `[0,0]` | Mặt chính xác `height+x*slope[0]+z*slope[1]`; grove/flowerbed đặt trên đó phải dùng cùng slope và cao tâm. |
| `color`, `retainingColor`, `edgeColor` | colour / `#b1bc9d`, `#a5a58e`, `#969e83` | Cỏ, thành và nét mép. |

Mặt cỏ không hỗ trợ route: vẫn phải có path riêng. Chỗ ramp gặp tầng phải trùng
cao độ; tránh để đường ở nửa dốc xuyên một bậc đất thẳng đứng.

### `nature_flowerbed`

Hoa cúc/cosmos có thân, lá, cánh và tâm hoa instanced; khác các chấm hoa của grove
(Lon ton g08/g17; vườn cabin Bên Suối g05). Bụi cắt thấp tiếp tục dùng `nature_grove`
với `trees: []`, `shrubScale` thấp và mật độ lớn.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `size`, `outline` | `[width,depth]` / `[6,2]`; polygon / không có | Bồn hoa; outline lọc vị trí ứng viên trong size, nên size phải bao được outline. |
| `kind` | `"daisy"\|"cosmos"\|"mixed"` / `"mixed"` | Daisy cánh sáng tâm trầm; cosmos tám cánh màu phụ; mixed có một phần ba cosmos. |
| `count` | integer / `100` | Số cây ứng viên theo ô lệch seed; exclusion và outline có thể giảm số thực. |
| `height`, `flowerRadius` | number / `.5`, `.12` | Chiều cao thân có biến thiên, bán kính đầu hoa; không phóng thành cây cảnh khổng lồ. |
| `slope` | `[risePerX,risePerZ]` / `[0,0]` | Neo chân từng cây vào mặt dốc. |
| `exclude` | `[x,z,width,depth][]` / `[]` | Chừa đường, sàn và cửa lều, không tự nhận diện vật cản. |
| `ground`, `groundColor` | boolean / `true`; colour / `#a3af8f` | Lớp nền mỏng; tắt nếu đã có cỏ/tầng cỏ, tránh mảng chữ nhật chồng lên đường. |
| `flowerColors` | colour[] / `[#e3e1d4,#cbb4bd]` | Màu đầu hoa daisy và cosmos; một màu dùng cho cả hai. Mảng rỗng dùng mặc định. |
| `stemColor`, `leafColor`, `centerColor` | colour / `#859573`, `#97a583`, `#b8aa7d` | Thân, lá và tâm hoa. |
| `seed` | integer / `23` | Vị trí và chiều cao tái lập. |

### `nature_grove`

Instanced foam trees, grounded low planting and flower accents. Prenn g15/g18 show
pine planting; g11/g25 show broadleaf cover above the waterfall and around the shore.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `size` | `[width,depth]` / `[12,8]` | Rectangular planting area. |
| `trees` | `[x,z,height?,baseOffset?][]` / `[[-3,0,7],[2,-1,8],[4,2,6]]` | Explicit tree positions; tuple height defaults to 7, extra base to 0. |
| `kind` | `"pine"\|"broadleaf"\|"mixed"` / `"mixed"` | Foam crown family, not literal foliage texture. |
| `crownScale` | number / `1` | Tree crown radius multiplier. |
| `shrubs` | nonnegative integer / `70` | Candidate low shrubs; exclusions reduce actual count. |
| `shrubScale` | number / `.55` | Low-plant scale before seeded variation. |
| `flowers` | number 0–1 / `.18` | Fraction of shrubs receiving tiny flower groups. |
| `flowerColors` | colour[] / `[#b7ad8e,#c3b7b5,#d4d7c5]` | Instance colours cycling over the whole palette; empty arrays use defaults. Applied to white base material. |
| `ground` | boolean / `true` | Thin rectangular planted backing; disable on existing rock cap. |
| `groundColor` | colour / `#b4bda5` | Backing. |
| `slope` | `[risePerX,risePerZ]` / `[0,0]` | Local planted-plane slope. |
| `exclude` | `[x,z,width,depth][]` / `[]` | Shrub exclusion rectangles, not automatic building detection. Place trees outside them explicitly. |
| `leafColor` | colour / `#92a284` | Tree crowns. |
| `trunkColor` | colour / `#837867` | Trunks. |
| `shrubColor` | colour / `#929f80` | Low planting and tree mats. |
| `seed` | integer / `7` | Stable planting layout. |

### Cảnh quan lớn — hợp đồng cao độ

Các nhánh dưới đây chỉ bật bằng type/tùy chọn mới; hình học, màu, seed mặc định
của type cũ giữ nguyên. `baseY: number = 0` cộng cao độ vào `position[1]` của
mọi object nature, dùng để đặt sàn/cabin trên một datum đã biết. Không tự đổi
cao độ của object thuộc kit khác: ghi trực tiếp `position[1]` trong JSON.

`nature_hills` phải đứng trước các object có `terrain: "<hill-id>"`. Grove lấy mẫu
từng gốc, path lấy mẫu cả tuyến; transform vị trí/xoay của cả hai object được tính
đúng world space. Bên trong kit, root đồi có `userData.heightAt(x,z)` trả y **local**
đúng tam giác đã dựng, không phải đường cong xấp xỉ; điểm ngoài footprint báo lỗi.
Không lấy cao đỉnh làm cao mọi cây, không dùng mặt nước làm đường. Nếu đặt object
khác bằng `baseY`, cần tự ghi cao độ lấy từ cùng profile/điểm đã biết trong JSON.

### `nature_lake`

Hồ Tuyền Lâm / Xuân Hương / Đa Thiện, hồ chân đồi: shoreline khép kín có dải bờ
nông, đảo thật khoét khỏi nước, cỏ/lau và cầu tàu tùy chọn. Không thêm hồ vào một
nơi chỉ có suối. Mặt nước opaque matte, không phải mặt hỗ trợ tour.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `size` | `[width,depth]` / `[70,45]` | Ellipse mặc định; cũng là miền chọn ripple, nên bao hết outline. Hỗ trợ hồ khoảng 200 m. |
| `outline` | `[x,z][]` / ellipse 16 điểm | Polygon đơn theo thứ tự quanh bờ; không tự cắt. |
| `smooth`, `segments` | boolean / `true`; integer / `128` | Spline centripetal kín; false giữ polygon gốc. Tránh góc lõm quá hẹp: offset bờ không phải bộ xử lý polygon tự cắt. |
| `level` | number / `.06` | Mặt nước trên chân object. |
| `shoreWidth` | number / `1.5` | Bờ mở ra ngoài và dải nước nông vào trong; 0 bỏ cả hai. Chừa bề rộng này khỏi đường. |
| `color`, `shoreColor`, `shallowColor` | colour / `#8faaa2`, `#b7b6a0`, `#b1bfb0` | Nước sâu, bờ đất và nước nông; giữ tương phản nhẹ. |
| `islands` | object[] / `[]` | Mỗi đảo có `position:[x,z]=[0,0]`, `size:[w,d]=[6,4]`, `outline` tùy chọn theo local đảo, `height=.35` trên nước, `color=#a5b298`, `shoreColor` theo hồ. Đảo phải nằm hoàn toàn trong hồ, không chồng nhau hoặc dải bờ nông. |
| `fringe`, `fringeHeight`, `fringeColor` | integer / `180`; number / `.55`; colour / `#919f7e` | Cỏ ven bờ instanced; 0 bỏ cỏ. Không tăng chiều cao để giả rừng. |
| `reeds`, `reedColor` | number 0–1 / `.3`; colour / `#9e9b78` | Tỷ lệ cụm có thân lau mảnh. |
| `ripples`, `rippleColor`, `seed` | integer / `45`; colour / `#e1e6dc`; integer / `31` | Nét mặt hồ nhỏ, cắt trong bờ/ngoài đảo, bố trí tái lập. |
| `jetty` | object / không có | API `nature_deck` với `position`, `rotation` **local hồ**; mặc định size `[2.4,8]`, height `level+.35`, footY `level-.2`. Có route support đúng world transform. Đặt chân route ở tim ván. |

### `nature_hills`

Khối đồi có đáy và thành đất thật: đồi chồng, đỉnh Langbiang, tầng trà/hoa;
profile hạ thấp phía sau sân tạo mép đồi nhìn xuống thung lũng. Nhà kính ở Chênh
Vênh g12–g17 là cảnh xa, không phải công trình thuộc quán. Đồi không tự hỗ trợ route.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `size`, `segments` | `[width,depth]` / `[70,45]`; `[nx,nz]` / `[72,52]` | Grid mặt đồi; tăng chia tại taluy gấp, không cần nhân số mesh. |
| `height`, `bottom` | number / `0`, `0` | Datum cộng vào mặt trên và đáy thành đất. Bottom phải thấp hơn mặt trên. |
| `profile` | `[z,y][]` / không có | Cao độ theo z, cộng height; hai đầu giữ y ngoài miền profile. Cùng một đồi có thể chứa sân cao, taluy và đáy thung lũng. |
| `profileSmooth` | boolean / `true` | Smoothstep giữa mốc; false nội suy thẳng để khớp datum bậc thang/sân. |
| `profileBend` | number / `0` | Dịch z lấy profile theo `bend*cos(π*x/width)^2`; làm mép đồi cong trong mặt bằng như mép sân Chênh Vênh, không đổi vị trí các khối masses. Cần lấy mẫu lại cây/đường ở mép. |
| `edgeFalloff` | `[xMargin,zMargin]` / `[0,0]` | Thu mặt đồi về bottom trong dải mép; tạo taluy bên/mũi đồi mềm thay cho khối hộp cắt đứng. Không đặt nhà hoặc route trong dải này nếu chưa lấy mẫu lại cao độ. |
| `masses` | object[] / hai đồi rộng cao 12/9 m | Mỗi khối: `center:[x,z]=[0,0]`, `size:[width,height,depth]` bắt buộc, `power=1.35`. Dome cosine có chân êm, các khối cộng cao độ. `[]` dùng riêng profile, tránh đồi vô tình dưới nhà. |
| `peak` | object / không có | Cùng cấu trúc masses, `power=.65` cho đỉnh nhọn hơn; không phải tấm phông đứng. |
| `terraceHeight` | number / `0` | 0 là đồi êm; số dương tạo các contour bậc nối bằng ramp êm. Tăng grid khi bậc nhỏ. |
| `color`, `highColor`, `sideColor` | colour / `#a7b397`, `#91a185`, `#ada991` | Màu chân/cao đồi vertex-colour và thành đất matte; không đổi vật liệu trắng dùng chung. |
| `contourSpacing`, `contourColor` | number / `3`; colour / `#89977f` | Nét contour đúng giao tuyến tam giác; 0 bỏ nét. |
| `bands`, `bandRadius`, `bandColor` | boolean / `false`; number / `.16`; colour / `#859777` | Dải trà/hoa thấp chạy theo contour; cần contourSpacing > 0, không bịa ruộng ở nơi ảnh không có. |
| `greenhouses` | object / không có | Hàng mái nhà kính thấp, thân và mái gable instanced riêng; lấy cao độ bốn góc, đặt tại góc cao nhất để mái không xuyên đất. Dành cho đáy thung lũng thoải, không rải lên vách dốc. |
| `.rows`, `.columns` | integer / `9`, `10` | Số hàng/cột nhà kính. |
| `.position`, `.rotation` | `[x,z]` / `[0,0]`; degrees / `0` | Tâm và hướng lưới trong local đồi. |
| `.roofSize`, `.spacing`, `.wallHeight` | `[w,rise,d]` / `[3,.7,7]`; `[dx,dz]` / `[w+.6,d+1]`; number / `.45` | Tỷ lệ mái thấp và khoảng hàng; không phóng thành các tòa nhà cao. |
| `.outline`, `.excludePolygons` | polygon / không có; polygon[] / `[]` | Lọc tâm theo local đồi. Mái vượt footprint đồi được bỏ; vẫn phải chừa buffer quanh đường/polygon. |
| `.color`, `.wallColor`, `.frameColor` | colour / `#deded2`, `#c8cbc0`, `#a6ad9e` | Mái sáng mờ, thân thấp và linework ridge/gable mảnh. |
| `.blocks` | object[] / không có | Nhiều cụm lưới kế thừa option greenhouses, mỗi cụm ghi đè rows/columns/position/rotation/roofSize…; hợp thung lũng g12–g17 có các lô mái lệch hướng. Mỗi cụm thêm ba draw call, giữ số cụm ít; không lồng blocks. |

### `nature_grove` — rừng dốc

Nhánh mới bật khi có `density`, `terrain` hoặc `kind:"kesiya"`; các cấu hình grove
cũ không đi qua nhánh này. Thông ba lá Đà Lạt có thân thẳng trống, tán thưa ở phần
ba trên; broadleaf dùng cụm tán mềm cho hai bờ Vườn Địa Đàng g00/g05/g13/g21.

| Tùy chọn | Kiểu / mặc định trong nhánh mới | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `size`, `density` | `[w,d]` / `[40,30]`; cây/m² / `.12` | Rải theo ô lệch seed; giới hạn 6000 ứng viên. Cỡ 100–800 cây vẫn chỉ vài draw call. |
| `kind` | `kesiya` hoặc `broadleaf` / thông | Kesiya tán phần ba trên, không phải thông Noel hình nón; pine/mixed trong nhánh mới cũng dùng tán thông. |
| `trees` | `[x,z,h?,baseOffset?][]` / tự rải | Có trees thì không tự rải; h mặc định 11, baseOffset 0. |
| `treeHeight`, `edgeFalloff` | `[min,max]` / `[9,14]`; number / `2` | Dải cao cây và khoảng giảm mật độ ở biên chữ nhật; 0 không giảm. |
| `terrain` | string / không có | Id đồi dựng trước; lấy mẫu mỗi gốc và bụi theo world transform. Không có thì dùng slope `[0,0]` như grove cũ. |
| `outline`, `excludePolygons` | polygon / không có; polygon[] / `[]` | Miền trồng và clearing local grove; áp dụng cả cây explicit lẫn bụi. Cần buffer bằng bán kính tán nếu muốn toàn bộ tán chừa lối. `exclude` chữ nhật vẫn dùng được. |
| `trunkRadius`, `crownScale` | number / `.11`, `1` | Bán kính thân và tỷ lệ tán; giữ thân thanh mảnh. |
| `shrubs`, `shrubScale` | integer / `ceil(w*d*.3)`; number / `.5` | Thảm thấp instanced, không rải chấm hoa nhiều màu trong rừng. |
| `ground`, `groundColor` | boolean / `true`; colour / `#a7b397` | Nền phẳng theo slope khi không có terrain; terrain luôn dùng mặt đồi sẵn. |
| `leafColor`, `trunkColor`, `shrubColor`, `seed` | colour / `#889d80`, `#837867`, `#9aaa8c`; integer / `7` | Bảng trầm đồng nhất và vị trí tái lập. |

### `nature_path` — bám đồi

`terrain:string` mặc định không có; bật lấy mẫu mặt `nature_hills` từng đoạn theo
`sampleSpacing:number=.75` m và cộng `heightOffset:number=.04` cùng y của từng
point. Route support vẫn là slab/ván thật. Điểm ngoài đồi báo lỗi. Tuyến quá dốc
phải viết bậc thang/đổi hướng trong JSON; không tự biến vách đứng thành đường đi.

### `nature_cascade` — nhiều tầng

`tiers:object[]` mặc định không có, giữ nguyên curtain Prenn; danh sách rỗng báo lỗi.
Phù hợp Datanla, Pongour và Cam Ly: một object chứa các tầng đá, sheet ngắn và hồ
giữa tầng. Không mặc định thêm thác lớn vào suối Vườn Địa Đàng.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `tiers[].x`, `.z` | number / `0`, `index*4` | Tim ngang và mép đá theo dòng +z. |
| `.top`, `.bottom` | number / `(N-index)*2.4`, `top-2.4` | Cao độ lip/hồ local; top phải lớn hơn bottom. |
| `.width`, `.run`, `.poolDepth` | number / width object (16), `1.1`, `2.8` | Bề rộng sheet, tiến ngang khi đổ và khoảng hồ sau sheet; đặt z tầng sau đúng cuối hồ, top sau bằng bottom trước. |
| `rockMargin`, `footY` | number / `2`, `0` | Đá dư hai bên dòng và chân khối đá. FootY phải thấp hơn top thấp nhất. |
| `rockColor`, `seamColor`, `poolColor` | colour / `#9b9685`, `#797b6a`, `#a4b0a0` | Đá lớp, nét thớ và hồ chân từng tầng. |
| `ribbons`, `segments`, `seed` | integer / `48`, `20`, `5+index` | Resolution và seed từng sheet; các option màu/flow/spread cũ vẫn áp dụng. |

### `nature_line`

Tuyến cáp Hồ Tuyền Lâm / coaster Datanla: profile 3D, tháp theo tuyến, dây/rail,
cabin/cart cách đều theo chiều dài và hai trạm. Không đăng ký route đi bộ trên dây.

| Tùy chọn | Kiểu / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `kind` | `cable\|coaster` / `cable` | Dây đôi với cabin treo hoặc rail đôi, giằng và xe thấp; giá trị lạ báo lỗi. |
| `points` | `[x,y,z][]` / `[[-20,0,0],[0,4,0],[20,8,0]]` | Profile chân tuyến, spline centripetal. Với terrain mặc định hai đầu ±20 m. Không tự khẳng định tuyến thực từ ảnh một trạm. |
| `terrain`, `sampleSpacing`, `heightOffset` | không có, `.75`, `.04` | Cùng cơ chế bám đồi của path; y point là offset trên mặt đồi. |
| `height`, `towers` | number / cable `8`, coaster `1.2`; integer / `max(2,ceil(length/18)+1)` | Cao tuyến trên profile và số tháp/chân; tối thiểu hai tháp. Coaster cần nhiều chân hơn theo ảnh. |
| `sag`, `gauge`, `lineRadius`, `postRadius` | number / `.8`, cable `1.8` / coaster `.7`, `.022` / `.035`, `.16` / `.07` | Võng dây (không áp dụng coaster), khoảng dây/rail và bán kính nét/tháp. Không cho sag lớn hơn khoảng hở địa hình. |
| `vehicles` | integer / `7` | Cabin/cart phân bố đều, instanced; 0 bỏ xe. |
| `stations` | boolean / `true` | Hai trạm hộp ở đầu, không tự tạo tour trong trạm. |
| `stationSize`, `stationHeight` | `[w,h,d]` / `[5,h,4]`; number / cable `height+1`, coaster `3` | Kích thước trạm trên chân profile. Trạm cần đón được độ cao dây. |
| `postColor`, `lineColor`, `frameColor` | colour / `#8b9283`, `#737d70`, `#899181` | Tháp, dây/rail và giằng. |
| `vehicleColor`, `glassColor`, `stationColor` | colour / `#b6a08b`, `#a1b2a8`, `#bcb9a7` | Thân xe, kính matte và hai trạm. |

### `nature_stream` — rapids ở overview

`rapids:object` mặc định không có, giữ nguyên suối Bên Suối. `rapids.count=24`
tạo cụm bọt thấp và nét dòng ngắn; `rapids.scale=.65` m điều khiển cỡ cụm, không
phải bức tường nước. Bọt/nét ghềnh được cắt trong hai bờ và hai đầu suối, không tràn
ra đế khi tăng scale. Tăng width/boulderScale cùng rapids để đọc được dòng giữa
đá lớn ở Vườn Địa Đàng g18/g20/g21; bờ phải có tán cây nhưng không che kín tim suối.
`excludePolygons:polygon[]=[]` chừa footprint đá quanh cầu/sàn trong local suối,
có buffer theo bán kính đá; không xóa mặt nước dưới cầu. Màu dùng `foamColor` cũ.

### Evidence and authoring pitfalls

- Keep physical dimensions, object positions, section/profile coordinates, cameras,
  stops and paths in JSON. An OSM file with `main: null` is not a building footprint.
- Cliff lips need real clearance in front of the *whole* water profile, not only its
  start/end. Test by raycasting towards the rock. Rock strata must follow section width
  multipliers; full-width lines otherwise float outside tapered ends.
- A path below an overhang still needs body-width clearance at head height. Loose
  boulders must not be scattered into it. Water and terrain are never route supports.
- Mixed mesh topology cannot be merged as walkable geometry: the kit normalizes to
  non-indexed position/normal buffers. Planks, plants and rails are instanced; ordinary
  unnamed meshes are batched by material within their owning object only.
- A sloping path uses explicit slab corners (including tilted round caps), not Euler
  pitch/yaw boxes. Grove backing is the exact `slope` plane, not compounded rotations.
  Plank backing sits below board faces to avoid coplanar depth flicker.
- At grade changes a cap follows the lower envelope of both incident slope planes,
  split along their intersection: no averaged-slope hump above the walking slabs.
  Very sharp bends/grade changes need wider paths or intermediate points authored in
  JSON; this is slab union geometry, not a civil-engineering road fillet solver.
- Moss uses real rock ray hits and section width multipliers, not a flat strip at
  the maximum height. Narrow/sloped caps can accept fewer patches than `segments`.
- Custom vertex-coloured water clones its material. Mutating a cached white material
  would turn unrelated flower instances black because they have no vertex colours.
- Do not put a deck, bridge, tent, shrine or neighbouring attraction in a place just
  because the kit supports it. `places/thacprenn/PHOTOS.md` records inclusions/exclusions.
- No interior is registered here: Prenn has zero interior photos. The kit does not
  fabricate cutaway/inside stops. Any future real interior must use the shared interior
  registry and `batch/INTERIOR_RULES.md`, not a fake exterior camera through a wall.

## pagoda

### Màu theo ảnh

Các tùy chọn dưới đây chỉ đổi vật liệu, không đổi hình khối. Bỏ qua tùy chọn
thì giữ nguyên màu mặc định. `palette` là bảng màu cục bộ của một object;
`interior.palette` áp dụng riêng cho `quan_am_gallery`, không lan sang object khác.
Màu nhập là sRGB thực từ ảnh, không giảm chroma để bù ánh sáng của viewer.

| Trường | Type / mặc định | Ý nghĩa / mẫu ảnh |
| --- | --- | --- |
| `palette` / `interior.palette` | `object={}` | Các màu semantic bên dưới; dùng cho các mảnh ceramic, hộ pháp, tượng và xe. Khác với `pagoda_building.colors` vốn là màu cấu kiện của family. |
| `.cream` | `color="#e4dfd0"` | Lan can, viền cửa, mặt tượng, nóc xe; Linh Phước g04/g10, Linh Ẩn g00/g15. |
| `.stone` | `color="#b9b3a4"` | Bệ, chân cột, nét nếp áo; g01/g04/g15. |
| `.wall` | `color="#c7bd9d"` | Tường và tầng tháp khảm sành; Linh Phước g00/g01/g04. Annex dùng `.cream` cho vỏ, `.wall` cho màn đứng. |
| `.sage` | `color="#80968b"` | Ngói mặc định/tháp, áo hộ pháp; Linh Phước g01/g06/g09. `roofColor` của hall/annex vẫn ưu tiên hơn. |
| `.edge` | `color="#a5b4a6"` | Gờ, đầu mái cong, đường xoắn cột và mào rồng; g04/g06/g08. |
| `.line` | `color="#8d8878"` | Nét mặt, vòng trang trí, dầm phụ; g09/g23. |
| `.dark` | `color="#4e5149"` | Hốc cửa, mắt/giày hộ pháp, gầm xe; g04/g09/g10. |
| `.rose` | `color="#a18b7c"` | Áo choàng hộ pháp, đầu/chân rồng, mái màn đứng; g08/g09. |
| `.gold` | `color="#b7a37c"` | Giáp, mũ, tay hộ pháp, trang trí mái, viền nội thất; g09/g23. |
| `.mosaicColors` | `color[]`, không đặt | Mảnh khảm relief và màu mảnh sành trong shader trên toàn bộ vật liệu ceramic; Linh Phước g04/g09. Không đặt: relief giữ `["#d5ceba","#9bac9e","#c3af89","#b69d92"]`, shader giữ bốn sắc độ nhân màu hiện có. Lặp màu trắng trong mảng để kiểm soát tỷ lệ sành trắng, không đổi mật độ/hình học. |
| `pagoda_court.jointColor`, `.curbColor` | `color="#b4b0a1"`, `"#e4dfd0"` | Ron sân và gờ cạnh bê tông, g05/g10. |
| `pagoda_garden.groundColor` | `color="#b9c0aa"` | Nền cây; g10. |
| `pagoda_garden.shrubColors` | `color[2]=["#a7b397","#96a486"]` | Hai màu bụi cây; g10. |
| `pagoda_garden.crownColor`, `.trunkColor` | `color="#98a58c"`, `"#938778"` | Tán và thân cây; g10. |
| `pagoda_landscape.treeColors` | `color[3]=["#87977f","#94a48c","#a3b098"]` | Ba sắc tán thông; Linh Ẩn g03/g15. |
| `pagoda_landscape.trunkColor` | `color="#8e8372"` | Thân cây; g15. |
| `pagoda_bus.windowColor` | `color="#87968f"` | Kính bên và kính trước; g10. Màu thân dùng `color`, nóc/khung dùng `palette.cream`. |
| `pagoda_icon.trimColor` | `color="#b9b3a4"` | Nét giáp hộ pháp; Linh Ẩn g05/g12. |
| `pagoda_icon.accentColor` | `color=armorColor??"#b7a37c"` | Đai ngang hộ pháp, cho phép đỏ riêng với giáp vàng; g05/g12. |
| `pagoda_icon.robePanelColor` | `color`, không đặt (giữ `color` của áo) | Mảng giáp trước ngực tô bằng vertex color trên mesh áo có sẵn, đai dưới dùng `accentColor`; Linh Ẩn g05/g12. Không thêm mesh hay thay silhouette; cần đặt khi giáp khối bị áo che. |
| `quan_am_gallery.wallColor` | `color="#c5bfa9"` | Vỏ trong khảm sành; g23/g24. |
| `.woodColor`, `.woodPanelColor` | `color="#947d64"`, `"#a3947b"` | Thân bàn và panel gỗ sơn; g23/g31. |
| `.runnerColor`, `.runnerTrimColor` | `color="#415969"`, `"#b7ac88"` | Thảm và viền; g23. |
| `.statueDetailColor` | `color="#ded6c1"` | Mặt, tay, cánh sen tượng; g21/g23. |
| `.haloColor`, `.robeLineColor` | `color="#c7b78d"`, `"#82795f"` | Nền hào quang và nét áo; g23. |
| `.ceilingPanelColor`, `.ceilingLightColor` | `color="#dadfda"`, `"#c2d0ca"` | Ô sáng dưới trần và màu phát sáng, cường độ giữ nguyên; g23/g24. `ceilingColor` hiện có đặt nền trời xanh. |

Use `"kits":["pagoda"]`. Coordinates and dimensions are metres; `position:[x,y,z]`
is the base, `rotation` is degrees about Y, and local +Z faces the forecourt.
All objects take `id:string` (required), `type:string` (required),
`position:number[3]` (required), `rotation:number=0`. Repeated foliage/flowers use
instances; solid details are batched by material without merging independent roofs.
Use the general family below for new monasteries; the original ceramic builders
remain available, unchanged, for Linh Phuoc. No builder branches on a place name.

Working complete family example: [`examples/pagoda.place.json`](examples/pagoda.place.json).
Build from diorama with `python3 -B build.py kits/examples/pagoda.place.json pagoda_checks/example/`.
`node test_truclam.mjs` builds and boots it, tests a differently sized/rotated
anonymous fixture, the Truc Lam route, and byte-identical Linh Phuoc geometry.

### General family object types

| Type | Purpose / corresponding photos |
| --- | --- |
| `pagoda_building` | One configurable builder: hall (Truc Lam g00/g02/g03/g19), three-passage gate (g06), open bell pavilion (g01), small garden pavilion (g04/g08), tiered tower for other places. |
| `pagoda_path` | Miter-joined visible paved strip with cross joints; green/stone garden paths g09/g14/g26. |
| `pagoda_landscape` | Calm low planting, flowers and layered sage foam pines; g07–g12/g14–g18/g21–g26. |
| `pagoda_stairs` | Straight ground-supported steps with optional rail; main-hall steps g00/g02, gate approach g06. |
| `pagoda_statue` | Simplified seated/standing Buddhist figure on a lotus pedestal; garden silhouette g12. No inferred identity. |
| `pagoda_water` | Muted ellipse/rectangle pond or lake fragment, ripples and optional shore stones. Catalogue only at Truc Lam: no pond invented from unrelated evidence. |
| `pagoda_stupa` | Dome or stacked polygonal stupa with finial. Catalogue only here: excluded g05 is **not** modelled at Truc Lam. |
| `pagoda_furniture` | Low incense burner (g00/g01/g02) or garden bench. |
| `pagoda_court` | Existing tiled rectangular court, used for the main forecourt g01/g07. |

### `pagoda_building`

| Option | Type / default | Meaning |
| --- | --- | --- |
| `form` | `"hall"\|"gate"\|"pavilion"\|"tower"`, `"hall"` | Structural family, not a place-specific profile. Gate has real three arch voids; pavilion/tower have open posts. |
| `footprint` | `number[2]=[14,9]` | Width/depth of foundation. Copy OSM oriented envelope without scaling. |
| `height` | `number=5` | Height of lowest roof eaves above base. |
| `plinth` | `number=.42` | Foundation top height; must be below height. Use ≤paving height for a flat walk-through gate. |
| `columnRadius` | `number=.18` | Timber shaft radius, cap/base scale proportionally. |
| `veranda` | `number=1.7` | Hall front wall setback from foundation front; less than depth. |
| `bays` | `integer=5` | Hall door bays and corresponding post rhythm. |
| `doorHeight` | `number=height*.63` | Hall door leaf height above plinth. |
| `openingStyle` | `"rectangular"\|"arched"`, `"rectangular"` | Hall lintel silhouette; shallow carved timber arches in g13/g19, not Gothic openings. |
| `lintelRise` | `number=.35` | Rise of the optional shallow arched lintel above the door head. |
| `lanterns` | `object`, omitted | Hall eave-hung timber lanterns, g03/g19. |
| `lanterns.count`, `.height`, `.width` | `integer=bays`, `number=.45`, `number=.22` | Even spacing, body height and nominal body width. Muted trim/wood colors follow building palette. |
| `sign` | `string`, omitted | Optional hall/gate sign, never an automatic place name. |
| `signWidth`, `signHeight` | `number=footprint[0]*.39`, `number=height*.085` | Gate nameplate size; suspended at the front eave, above the central arch. Hall retains original cream .85 m sign. |
| `levels` | `integer=3` | Tower storeys; ignored for other forms. |
| `storeyHeight` | `number=height+(roof.rise??1.7)+1.2` | Tower level spacing; default clears the preceding roof and ridge ornament. Keep overrides equally clear. |
| `taper` | `number=.88` | Width/depth multiplier per tower level. |
| `core` | `object={}` | Continuous rear stair/support core for towers with multiple storeys; prevents floating floors. Catalogue variant, not present at Truc Lam. |
| `core.size` | `number[2]=[topWidth*.28,topDepth*.28]` | Core width/depth; topWidth/topDepth include taper^(levels−1). Keep overrides inside every floor. |
| `core.offset` | `number[2]=[0,-topDepth*.28]` | Local X/Z core center; rear offset keeps the front bay open. Check explicit bell/core dimensions together. |
| `core.color` | `color=colors.wall` | Muted load-bearing wall finish. |
| `railing` | `boolean=false` | Front/back timber railing on pavilion/tower. Not a closed gate. |
| `bell` | `object`, omitted | Suspended bell in first pavilion/tower storey. |
| `bell.height` | `number=1.5` | Bell body height. |
| `bell.radius` | `number=.55` | Bell body radius. |
| `bell.color` | `color="#958767"` | Muted bronze; body hangs from a real support. |
| `colors` | `object={}` | Optional per-object palette, fields below. |
| `colors.wall` | `color="#d1bc87"` | Ochre plaster walls / gate piers. |
| `colors.roof` | `color="#9a8065"` | Roof surfaces. |
| `colors.wood` | `color="#69564a"` | Posts, beams, doors and clerestory frames. |
| `colors.trim` | `color="#b7aa8c"` | Roof edge, opening trim and arch relief. |
| `colors.stone` | `color="#c5bfb0"` | Foundation and post feet. |
| `roof` | `object={}` | Roof controls below; all tiers register for future cutaways. No inside stop without verified interior evidence. |
| `roof.tiers` | `integer`: hall/gate `2`, pavilion/tower `1` | Hall/pavilion roof count; gate currently supports one or two; tower uses one per storey. |
| `roof.rise` | `number`: hall `2`, gate lower `2` / upper `1.04`, pavilion/tower `1.7` | Ridge minus eave height. Set explicitly for a coherent two-roof gate. |
| `roof.gap` | `number`: hall `1.7`, pavilion `1.25` | Vertical distance between tier eaves; gate top eaves use lower eaves +1.15. |
| `roof.shrink` | `number`: hall `.88`, pavilion `.72` | Upper tier width multiplier; pavilion also scales depth. |
| `roof.depthShrink` | `number=.64` | Hall upper tier depth multiplier. |
| `roof.overhang` | `number=.7` | Eave extension outside the tier footprint. |
| `roof.curl` | `number=.7` | Corner lift, preserving the Vietnamese roof silhouette. |
| `roof.curve` | `number=.15` | Roof face curvature. |
| `roof.thickness` | `number=.14` | Roof shell thickness. |
| `roof.ornament` | `boolean=true` | Shared roof ridge ornament. |
| `roof.tileSpacing` | `number=.45` | Fine roof line spacing; too small aliases at long distance. |
| `roof.soffit` | `boolean=false` | Timber underside card, g03/g19. Attached in roof-local coordinates, including deep rotated plans, and moves with its roof. |

### Paving, steps and planting

| Type / option | Type / default | Meaning |
| --- | --- | --- |
| `pagoda_path.points` | `number[2][]=[[-4,0],[4,0]]` | Local X/Z control points, linear segments, no duplicate consecutive points. |
| `.width` | `number=3.4` | Full paved width; leave ≥.7 m each side of the runtime arrows and extra room at turns. |
| `.surfaceY` | `number=.10` | Top above object base. Indexed extrusion includes ground-supported sides. |
| `.grid` | `number=1.2` | Cross-joint spacing along each leg. |
| `.color`, `.jointColor` | `color="#c8c7b8"`, `"#a8aa9c"` | Surface and subdued cross joints. |
| `pagoda_court.size` | `number[2]`, required | Existing rectangular court width/depth. |
| `.grid`, `.color` | `number=2`, `color="#d6d0c1"` | Existing grid and surface palette. Top .08 m; edge curb .20 m. |
| `pagoda_stairs.width`, `.steps` | `number=5`, `integer=5` | Width and count. Local +Z is the lowest end. |
| `.rise`, `.run` | `number=.15`, `number=.35` | Per-step rise/tread length. Each step reaches down to base, no floating slabs. |
| `.rail`, `.railColor` | `boolean=false`, `color="#e4dfd0"` | Side posts and sloped coping. |
| `.color` | `color="#b9b3a4"` | Stone tread/riser. |
| `pagoda_landscape.size` | `number[2]=[10,8]` | Garden patch dimensions. |
| `.shape` | `"rectangle"\|"ellipse"`, `"rectangle"` | Planting footprint; whole low shrubs/blossoms stay inside it. Explicit tree crowns may overhang. |
| `.density` | `number=.55`, range 0–1 | Deterministic probability per cell, not a global count. |
| `.spacing` | `number=1.4` | Low-plant cell spacing. |
| `.flowers` | `number=.2`, range 0–1 | Share of planted cells carrying small muted blossoms. |
| `.groundColor` | `color="#bcc2ab"` | Ground plane at .025 m. |
| `.shrubColors` | `color[3]=["#a6b299","#94a58b","#b2bda1"]` | Three shrub tones; use exactly three. |
| `.flowerColors` | `color[3]=["#baa5a2","#d6cdb0","#a8b9b9"]` | Three blossom tones; use exactly three. |
| `.trees` | `number[3][]= []` | Local `[x,z,height]` pines. Foam crown geometry comes from the template, batched by variant. |
| `.border`, `.borderColor` | `boolean=false`, `color="#b9b3a4"` | Optional low stone edge. Keep outside paving and route ribbon. |

Low shrubs share a cached 200-triangle two-lobe foam prototype; pines retain the
template's layered crowns. Density changes count, not prototype complexity.

### Small structures and objects

| Type / option | Type / default | Meaning |
| --- | --- | --- |
| `pagoda_statue.height` | `number=3` | Nominal figure scale above pedestal; standing top is .947×height, seated top .757×height, plus baseHeight. |
| `.pose` | `"seated"\|"standing"`, `"seated"` | Robe/knee/head silhouette. |
| `.baseHeight` | `number=.4` | Pedestal height; lotus touches it. |
| `.color`, `.baseColor` | `color="#e4dfd0"`, `"#b9b3a4"` | Figure and pedestal. |
| `.hairColor` | `color="#4e5149"` | Muted hair cap. |
| `.halo`, `.haloColor` | `boolean=false`, `color="#b7a37c"` | Optional fine halo behind head. |
| `pagoda_stupa.kind` | `"dome"\|"tiered"`, `"dome"` | Hemisphere shrine or polygonal stacked storeys. |
| `.radius`, `.height`, `.tiers` | `number=2`, `number=7`, `integer=5` | Radius, total height, polygonal tier count (tiered only). |
| `.color`, `.baseColor` | `color="#b7a37c"`, `"#b9b3a4"` | Muted stupa/stone palette. |
| `pagoda_water.size` | `number[2]=[12,8]` | Water/bank dimensions. |
| `.shape` | `"ellipse"\|"rectangle"`, `"ellipse"` | Flat water shape. Current stone ring follows an ellipse; set stones=0 for a rectangular shore. |
| `.stones` | `integer=24` | Shore-stone instance count; 0 omits. |
| `.color`, `.bankColor`, `.stoneColor` | `color="#9fbbb4"`, `"#adaf9c"`, `"#b9b3a4"` | Water, bank plane, shore. Water is opaque studio card, not a simulation. |
| `pagoda_furniture.kind` | `"incense"\|"bench"`, `"incense"` | Burner bowl with three sticks, or low garden bench. |
| `.size` | `number[3]=[1.8,1.5,1.4]` | Width / nominal height / depth. For benches set `[2,.9,.65]` (seat about .47 m). |
| `.color`, `.baseColor` | `color="#948d78"`, `"#b9b3a4"` | Bronze/timber and stone supports. |

### Original ceramic types (compatibility API)

These remain unchanged, including their studio proportions and palette. Their
options describe the established Linh Phuoc reference, not a surveyed generic facade.

| Type | Options: type=default; omitted means not built |
| --- | --- |
| `pagoda_hall` | `footprint:number[2]` required; `height:number=6`; `facadeTiers:integer=2`; `sideTurrets:boolean=true`; `roofColor:color="#80968b"`; `sign:string` omitted; `interior:object` omitted; `cutaway.lift:number=7.4` viewer control. Ceramic relief/dragon posts/portal correspond to Linh Phuoc g00/g04/g05/g12. |
| `pagoda_tower` | `footprint:number[2]` required; `levels:integer=7`; `storeyHeight:number=4.1`. Original ceramic bell tower g01/g03/g07/g11. |
| `pagoda_annex` | `footprint:number[2]` required; `height:number=5`; `roofColor:color="#80968b"`; `roofOverhang:number=.3`; `outline:number[2][]` omitted (local concave wall polygon); `wings:object[]` omitted (`position:number[2]`, `size:number[2]`, `rotation:number=0`, `eave:number=height+.2`, `rise:number=2.4`); `screen:object` omitted (`position:number[3]`, `width:number`, `height:number`, `base:number=0`, `depth:number=3`); `bridge:object` omitted (`start/end:number[3]`, `width:number=2.2`, `steps:integer=15`); `roofStatue:object` omitted (`position:number[3]`, `height:number=4`). Low shrine/concave southern hall/screen/bridge in Linh Phuoc g01/g02/g03/g06/g07/g08/g11. |
| `pagoda_dragon` | `points:number[3][]` required; `radius:number=.75`; `tailRadius:number=radius`; `headScale:number=1`; `bodyColor:color="#ada391"`; `mosaicColors:color[3]=["#bdb5a4","#acb3a1","#b6aa91"]`; `scaleRelief:number=.045`; `crestHeight:number=.36`; `feet:number[2][]= []`. Broad relief head and thin ceramic scales, Linh Phuoc g08/g12. |
| `pagoda_guardian` | `height:number=4.8`. Helmeted guardian with face/cape/pole, Linh Phuoc g03. |
| `pagoda_garden` | `size:number[2]` required; `shrubSpacing:number=1.3`; `trees:number[3][]= []`; `treesPerCluster:integer=1`; `crownRadius:number=3`. Original rectangular low sage bed/layered tree clusters. Prefer `pagoda_landscape` for the new foam family. |
| `pagoda_bus` | `size:number[3]=[2.6,3.2,10.5]`; `color:color="#a69689"`. Existing coach massing, Linh Phuoc g10. |

Existing `registerInteriorKit('quan_am_gallery', …)` is also preserved. It takes
building `size:[width,height,depth]`, and `interior` options:
`rotation:number=building.rotation`, `floor:number=.48`,
`ceilingHeight:number=size[1]`, `statueHeight:number` required,
`sideStatueHeight:number` required, `sideCount:integer` required (≥2),
`offeringHeight:number=1.05`, `offeringWidth:number=2.1`,
`runnerWidth:number` required, `ceilingColor:color` required,
`goldColor:color="#b7a37c"`. Viewer `entry/approach:number[3]`,
`safeApproach:boolean=false`, `lights.altar/fill:number[3]` are world-space camera/light
data, not geometry. See `batch/INTERIOR_RULES.md`; do not apply this standing-statue
gallery to a different monastery without matching evidence. Truc Lam has only two
interior photos, so this run deliberately registers **no new interior kit/stop**.

### Tượng có silhouette riêng: `pagoda_icon`, `pagoda_statue_row`

Các type mới không thay đổi `pagoda_statue` hoặc `pagoda_guardian` cũ. Dùng ảnh xác định
dáng tượng; không gán danh tính từ màu sắc. Tất cả kích thước, vị trí và màu ở JSON.

| Option | Type / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `pagoda_icon.kind` | `"quan_am"\|"buddha"\|"maitreya"\|"guardian" = "quan_am"` | Quan Âm đứng áo dài có nếp, mão/khăn và tay giơ (Linh Ẩn g00/g03/g18/g19); Phật ngồi kiết già (Chùa Tàu g00/g05); Di Lặc bụng tròn, chuỗi hạt, miệng cười (Linh Ẩn g17); hộ pháp giáp, mũ, trượng (g05/g12). Không dùng một hình nón thay cho cả bốn dáng. |
| `.height` | `number=3` | Chiều cao tượng, không gồm bệ; hỗ trợ đến 70 m. Vòng hào quang tùy chỉnh có thể vượt chiều cao tượng. |
| `.baseHeight`, `.baseSteps` | `number=.4`, `integer=3` | Tổng chiều cao bệ và số cấp, không phải chiều cao mỗi cấp. Đài sen nằm trên bệ. |
| `.baseWidth` | `number=height*.475` khi đứng; `height*.9` khi ngồi | Bề ngang chân bệ; ghi rõ từ ảnh khi bệ cao/rộng khác mặc định. |
| `.baseDepthRatio` | `number=.8` | Chiều sâu chân bệ / bề ngang. |
| `.color`, `.baseColor` | `color="#e4dfd0"`, `"#b9b3a4"` | Trắng ngà, vàng trầm hoặc đồng bằng CSS color; vật liệu matte, không chrome. |
| `.folds` | `integer=30` | Số nếp áo tượng đứng; nét mảnh bám đáy nếp xoắn, vòng thân chia đủ mịn theo số nếp. Hai dáng ngồi dùng 28/22 nếp cố định theo silhouette. Tránh mật độ quá cao gây alias. |
| `.hairColor` | `color=color` | Tóc/búi đầu Phật ngồi; không nhuộm đen khăn Quan Âm. |
| `.armorColor`, `.staffColor` | `color="#b7a37c"` | Giáp/mũ và trượng hộ pháp. |
| `.crownColor`, `.vaseColor` | `color=color` | Chi tiết giữa mão và bình nhỏ của Quan Âm. |
| `.beadColor` | `color="#b9b3a4"` | Chuỗi hạt Di Lặc. |
| `.halo`, `.haloColor` | `boolean=false`, `color="#b7a37c"` | Hào quang mảnh; chỉ thêm khi ảnh có bằng chứng. |
| `.haloRadius` | `number=.14`, Di Lặc `.10` | Bán kính / chiều cao tượng, không phải mét. |
| `pagoda_statue_row` | cùng option tượng; riêng `height=2.5`, `baseHeight=.3` | Lặp cùng một prototype, instancing theo từng vật liệu; Linh Ẩn g13/g15. |
| `.count`, `.spacing` | `integer=8`, `number=3` | Số tượng và khoảng cách tâm; hàng mặc định nằm dọc local X. `rotation` xoay cả hàng. |
| `.placements` | `number[3][]`, bỏ qua | Tọa độ local `[x,y,z]` từng tượng; thay thế `count/spacing`. Các tượng cùng dáng và kích thước. Không để thân cây xuyên mặt tượng. |

### Tam quan xây: `pagoda_gate`

| Option | Type / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `.style` | `"brick"\|"stone" = "brick"` | Tam quan gạch có vòm và trụ trang trí (Linh Ẩn g02); cổng đá hai tầng bên đường (g06). Ba lối là lỗ mở thật, không phải mảng sơn tối. |
| `.footprint`, `.height` | `number[2]=[15,3]`, `number=5` | Bề ngang/chiều sâu thân cổng và cao đến diềm chính. Cổng đá còn mái tầng trên. |
| `.plinth` | `number=.08` | Chân tường; không tự tạo nền cao chắn lối. Cổng trên cao cần thang và sàn đỡ riêng. |
| `.colors` | `object` | Kế thừa palette family; `wall` mặc định gạch `#ad8870`, đá `#bcb9aa`; `trim/wood/stone` như family. |
| `.sign` | `string`, bỏ qua | Biển dưới diềm giữa, không tự thêm tên địa điểm. |
| `.signWidth`, `.signHeight` | `number=width*.45`, `number=.45` | Kích thước biển, kiểm tra không che đỉnh vòm. |
| `.walls` | `object`, bỏ qua | Tường nối hai phía, thay cho hall thấp giả tường. |
| `.walls.length`, `.height`, `.depth` | `number=10`, `2.2`, `.7` | Chiều dài mỗi cánh, chiều cao và chiều dày. Tọa độ local theo cổng, cần sàn đỡ nếu cổng nâng cao. |

### Chính điện đá, cánh thấp và trang trí mái

Các option sau thuộc `pagoda_building`; chỉ kích hoạt nhánh mới khi
`facade.style="stone"`. Mái kép vẫn dùng `roofRecords` độc lập. Không lồng thêm
`pagoda_hall` để tạo nội thất: chính đối tượng này chứa cả vỏ và đồ thờ.

| Option | Type / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `.facade.style` | `"stone"`, bỏ qua | Mặt tiền khối đá, cửa giữa và cửa tròn: Chùa Tàu g01/g04/g11/g13. Các hall cũ không đổi khi bỏ qua. |
| `.facade.wallThickness` | `number=.3` | Vỏ rỗng thật, không khối đặc che nội thất. |
| `.facade.roundWindows` | `number[2][]=[[-width*.32,height*.67],[width*.32,height*.67]]` | Tâm cửa `[x,y]` local trên mặt tiền; `[]` bỏ cửa. Lỗ tròn có khung và song mảnh. |
| `.facade.windowRadius` | `number=.55` | Bán kính chung của cửa tròn, giữ cửa trong diện tường. |
| `.facade.courseHeight`, `.blockWidth` | `number=.65`, `1.4` | Mạch ngang/dọc so le của đá hồng. Không vẽ mạch chạy xuyên cửa. |
| `.facade.jointColor` | `color="#927f79"` | Màu linework mạch đá, giữ tương phản nhẹ. |
| `.doorWidth`, `.doorHeight` | `number=2.5`, `height*.60` | Lỗ cửa giữa thật; cửa đóng tách riêng để viewer mở khi vào trong. |
| `.facade.doorColor` | `color=colors.wood` | Màu lá cửa đóng hoặc nền tối của lỗ cửa, độc lập với cột đỏ. |
| `.signWidth`, `.signHeight` | `number=width*.43`, `.55` | Biển phía trên cửa; chỉ tạo nếu có `.sign`. |
| `.roof.crest` | `boolean=false` | Diềm/rồng cuộn và bánh xe vàng trầm trên sống mái: g04/g11. Gắn theo từng mái, đi cùng cutaway. |
| `.roof.rise` | `number=1.5` trong nhánh đá | Mái thấp rộng; các thông số `tiers/gap/shrink/depthShrink/curl/curve/...` dùng như family. |
| `.wings` | `object[]=[]` | Các cánh thấp có mái riêng, Chùa Tàu g04/g11; footprint không tự suy từ hall. |
| `.wings[].position` | `number[2]`, bắt buộc | Tâm local X/Z theo hall. |
| `.wings[].footprint`, `.height` | `number[2]=[10,8]`, `number=3` | Bề ngang/sâu và chiều cao cánh. |
| `.wings[].rotation` | `number=0` | Độ quanh local Y. |
| `.wings[].roofRise`, `.curl` | `number=1`, `.35` | Độ cao sống mái và cong góc riêng. |
| `.wings[].text` | `string`, bỏ qua | Chữ lớn sơn trực tiếp trên tường, không dựng biển nổi. Nội dung phải do JSON cung cấp từ ảnh. |
| `.wings[].textWidth`, `.textHeight`, `.textColor` | `number=wingWidth*.84`, `wingHeight*.38`, `color="#4e5149"` | Bề ngang/cao/màu chữ; tránh bịa chữ khi không đọc được ảnh. |
| `.wings[].textPosition` | `number[2]=[0,wingHeight*.55]` | Tâm X/Y local của dòng chữ. Canvas trong suốt, chữ có tỷ lệ tự nhiên, không tạo bảng nền sáng. |
| `.wings[].openings` | `number[3][]= []` | Hốc cửa đóng `[x,width,height]` bắt đầu từ plinth, viền mảnh; g04/g11. Không phải lối vào nội thất có thể tham quan. |

### Thang rồng, lư hương trên đế và nền thông

| Option | Type / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `pagoda_stairs.dragon` | `object`, bỏ qua | Hai lan can rồng nối theo độ dốc thang, đầu/mắt/sừng/râu và sống lưng: Chùa Tàu g00/g05/g07. Khác `rail` thẳng; không cần bật cả hai. |
| `.dragon.height`, `.radius`, `.color` | `number=.8`, `height*.13`, `color="#b7a37c"` | Độ cao trang trí, bán kính thân và màu; thang vẫn có khối chịu lực phía dưới. |
| `pagoda_furniture.standHeight` | `number=0` | Đôn đá dưới lư hương, nâng toàn bộ lư: Chùa Tàu g01/g10/g11. `size[1]` vẫn là chiều cao lư, chưa gồm đôn. |
| `pagoda_landscape.surface` | `"needles"`, bỏ qua | Nền lá thông với các nét rải instancing, không đăng ký làm mặt lát. g02/g07/g08/g16. Dùng `groundColor` nâu đất trầm. |
| `.needleCount` | `integer=round(width*depth*3)` | Số nét lá; tán, hoa và mật độ bụi vẫn điều khiển độc lập. Không dùng lớp nền phủ lên thang/court. |
| `.clearings` | `number[4][]= []` | Khoảng trống local `[x,z,width,depth]` cho đường đi/đế tượng; loại toàn bộ bụi và nét lá trong khoảng, không khoét mặt nền. Cây trong `.trees` vẫn phải đặt tránh lối đi. |

### Nội thất `buddhist_altar`

Dùng `interior.kit="buddhist_altar"` cho `pagoda_hall` hoặc
`pagoda_building` với `facade.style="stone"`. Hall phải có `size:[width,height,depth]`
cho camera/ánh sáng. Vỏ đỏ, ba tượng đứng vàng, cột đỏ và trần ô vàng với tranh vòm
theo Chùa Tàu g17/g19/g22/g26. Chỉ mở nội thất khi có ít nhất bốn ảnh nội thất;
Linh Ẩn không đủ ảnh, không tạo thêm stop. Cặp stop ngoài/inside phải chọn cùng hall.

| `interior` option | Type / mặc định | Ý nghĩa và lưu ý |
| --- | --- | --- |
| `.rotation` | `number=hall.rotation` | Góc vỏ nội thất, trần và đồ thờ; không mặc định theo trục thế giới. |
| `.floor`, `.ceilingHeight` | `number=.46`, `size[1]-.5` | Cao sàn local và cao trần tính từ sàn. Trần gắn mái chính để cutaway, hạ kín khi vào. |
| `.statueHeight`, `.statueSpacing` | `number=2.7`, `width*.19` | Cao mỗi tượng không gồm bệ và khoảng cách ba tâm. Không tạo thêm hàng tượng bên hông. |
| `.altarHeight`, `.altarWidth`, `.altarZ` | `number=.6`, `width*.64`, `-depth*.32` | Cao bệ tượng, ngang tường đỏ, trục Z local tường thờ. |
| `.offeringWidth` | `number=width*.47` | Bàn lễ cao 1 m, ở trước bệ; không đặt sát camera. |
| `.goldColor`, `.redColor`, `.wallColor` | `color="#b6a076"`, `"#92564e"`, `"#c4b5a0"` | Vàng matte, sơn đỏ trầm, tường trong. |
| `.floorColor`, `.ceilingColor` | `color="#b7b5a7"`, `"#85775e"` | Nền đá và nền tối giữa ô trần. |
| `.cofferSize`, `.domeRadius` | `number=.65`, `min(width,depth)*.19` | Nhịp ô vàng instancing và bán kính tranh vòm tám múi. Vòm phải nằm trong trần và giữa dầm. |
| `.entry`, `.approach`, `.safeApproach`, `.lights` | như viewer hiện có | Tọa độ thế giới của cửa/lối vào và đèn, xem `batch/INTERIOR_RULES.md`. Không dùng góc bay xuyên vách. |

Kiểm thử mở rộng: `node test_pagoda_extension.mjs`; regression:
`node test_linhphuoc.mjs`, `node test_truclam.mjs`,
`python3 -B -m unittest test_viewer test_landscape`.

### Framing cho tượng khổng lồ

| Option viewer trong JSON | Type / mặc định | Ý nghĩa và giới hạn |
| --- | --- | --- |
| `site.overviewHeightFill` | `number=.88` | Tỷ lệ chiều cao vùng trống được dùng khi fit tổng quan. Tượng cao có thể dùng `1.10–1.14` để tận dụng phần giữa phía trên header; viewer tự giới hạn theo chiều cao màn hình để giữ biên tối thiểu 24 px. Phải kiểm tra không che chữ ở mọi orbit. Không thay tỷ lệ hình học. |
| `site.overviewAllAngles` | `boolean=false`, option viewer có sẵn | Khi bật, dùng `overviewSubjects` ở cả orbit, không chỉ góc đầu. Bắt buộc đưa tượng cao vào subjects để orbit không chỉ ôm đế và cắt đầu. |
| `hotspots[].frameRoute` | `boolean=true` | `false` chỉ bỏ walk/8 m đầu đường khỏi tập điểm fit camera của stop; tuyến đi, pin và hoạt ảnh không đổi. Dùng cho cận cảnh tượng/lư hương khi muốn giữ vị trí đứng trên đường nhưng không kéo camera về sân xa. |

### Pitfalls and authoring boundaries

- Every route leg must have actual paving, not a grass plane passing a raycast.
  New extruded paths carry a sequential index to match template BoxGeometry
  walkable surfaces; mixing indexed/non-indexed surfaces prevents viewer boot.
- Avoid overlapping coplanar courts. Keep foreground garden patches away from
  buildings, route strips, steps and burner/bench footprints. An open pavilion
  is not an invitation to fill its floor with shrubs.
- A gate sign on the masonry plane can disappear behind the pitched roof in raised
  views. The family suspends its board at the front eave; test a mesh-only sight ray
  because linework raycasts have a broad default tolerance.
- Keep tower floor spacing above the preceding ridge ornament; a fixed short
  storey pitch is not safe when height or roof rise changes. Stupa finials and
  statue necks must connect, not merely belong to a ground-touching group.
- Tree instance framing must use transformed bounding corners, never prototype
  vertices at world origin. Low planting should read as clustered foam, not a
  uniform bead grid. Preserve clear sight lines to each stop's signature anchor.
- Use `site.outline` for a tight rotated plinth, then `overviewSubjects`,
  `overviewAzimuth/Polar` and `frameFill` to reach about 80% free width without
  clipping the plinth or tree tips. Do not shrink an OSM footprint to fit a slab.
- Defaults are reusable **studio proportions**, not measured facts. JSON owns
  site layout, sizes, heights, palette overrides, route points, evidence,
  captions and cameras. Other places need JSON, not new geometry code, for the
  listed family forms; unusual unlisted architecture must not be invented.

## stay

`kits/stay.js` is a data-only lodging family: use several `stay_building` objects
for wings, hotel blocks or homestay cabins, not a new builder per address.
Complete executable example: `kits/examples/stay.place.json`; build/boot coverage:
`node test_dalatpalace.mjs`. The example is fictional, not evidence of a real place.

All lengths are metres, rotations radians around +Y. Coordinates within options
are **local to the object**; `position` and tour cameras/anchors/entry/lights are
world coordinates. Local +Z is the default garden frontage. Storeys are zero-based.
Use the OSM outline and derive `rotation` before authoring facade edge indices.

### Common object options

| Option | Type / default | Meaning / evidence |
| --- | --- | --- |
| `id` | string, required | Unique object/envelope name. |
| `type` | string, required | Một trong các loại đối tượng bên dưới. |
| `position` | `[x,y,z]`, `[0, terrain(0,0),0]` | World base; supplied Y is absolute, not an offset. Ground it using the site terrain. |
| `rotation` | number, `0` | Local-to-world orientation; same angle for house, paths and garden. |

### `stay_building`

One shell builder serves a multi-storey hotel, stepped colonial hotel or small
pitched-roof homestay. Foundation follows `outline`; no neighbouring OSM polygon
is inferred to belong to the place. `size[1]` is eaves/roof-base height, not ridge height.

| Option | Type / default | Meaning / photo cue |
| --- | --- | --- |
| `size` | `[width,height,depth]`, `[18,9.6,12]` | Envelope and rectangular fallback; OSM/proportions. |
| `outline` | `[x,z][]`, size rectangle | Local polygon without a repeated last vertex; stepped hotel wings. |
| `storeys` | integer, `3` | Equal floor-to-floor heights = height/storeys; count visible levels. |
| `floorHeight` | number, `.3` | Ground-floor offset above base and foundation top. |
| `bayWidth` | number, `3.5` | Target facade rhythm; actual bay count rounds each edge length. |
| `windowWidth` | number, `1.65` | Window width, capped to 60% of actual bay. |
| `windowHeight` | number, `2.2` | Window height, capped to floor height minus 1 m. |
| `wallColor` | CSS hex, `#e6e1d4` | Muted plaster: g00/g01/g08. |
| `trimColor` | CSS hex, `#f2ecdd` | Cornices, mullions, arcade piers. |
| `glassColor` | CSS hex, `#82968e` | Muted glazing; green doors/windows g01/g06. |
| `shutters` | CSS hex or false, absent | Optional paired louvred shutters. |
| `cornice` | boolean, `true` | Upper course and repeated corbels; g01/g02. |
| `roof.kind` | `flat / gable / hip / mansard`, `flat` | Biên dạng mái theo ảnh; mái dốc cần footprint chữ nhật. |
| `roof.color` | CSS hex, `#777b70` | Muted roof tone. |
| `roof.rise` | number; mansard `3`, gable/hip `depth × .30` | Độ cao mái dốc, đồng thời dùng cho metadata khung hình; mái flat bỏ qua. |
| `roof.terrace` | object, absent | Open-sided rooftop pergola: Dalat Palace g00/g08. Moves with the cutaway roof. |
| `roof.terrace.position` | number[3], `[0,0,0]` | Offset from the roof base, not from the ground. Keep it on the roof footprint. |
| `roof.terrace.size` | `[width,height,depth]`, `[16,3,8]` | Post envelope; canopy overhang is .2 m. |
| `roof.terrace.spacing` | number, `4` (minimum `.8`) | Target post/rib pitch; width is divided into equal bays. |
| `roof.terrace.archRise` | number, `0` | Optional shallow curved braces below the canopy, g00. Zero omits them. |
| `roof.terrace.frameColor` | CSS hex, building trim | Slim columns and beams. |
| `roof.terrace.color` | CSS hex, roof color | Muted canopy tone. |
| `roof.terrace.canopy` | boolean, `true` | False leaves an uncovered pergola frame. |
| `arcade` | object, absent | Open external gallery, not an arch painted on a solid outer wall. |
| `arcade.edges` | integer[], absent | Polygon edge indices with an arcade: g00/g03/g08. |
| `arcade.levels` | integer[], `[0,1,2]` | Floors carrying arches; other levels retain normal glazing. |
| `arcade.depth` | number, `2.4` | Recess of shell wall behind gallery line. |
| `arcade.windowWidth` | number, building windowWidth | Smaller inner windows behind the outer arcade. |
| `arcade.windowArched` | boolean, `false` | Optional inner arched trim; external arches remain independent. g00 uses rectangular inner bays. |
| `arcade.shutters` | CSS hex or false, building shutters | Override only the recessed gallery windows; false avoids doubled visual density. |
| `arcade.wallColor` | CSS hex, building wallColor | Recessed wall tone, not the external spandrels. |
| `balconies` | object, absent | Individual balconies on non-arcaded edges above ground floor. |
| `balconies.width` | number, window width + `.65` | Slab/rail width; use photos of that hotel, not a family-wide assumption. |
| `balconies.depth` | number, `.8` | Projection beyond facade. |
| `balconies.color` | CSS hex, `#6d5c49` | Slender railing. |
| `crown` | object, absent | Optional roof pavilions and pediment, as in g00/g08. |
| `crown.pavilions` | object[], `[]` | Each `{position:[x,y,z]=[0,0,0], size:[w,h,d]}`; position relative to roof base. |
| `crown.pediment` | object, absent | `{position:[x,y,z]=[0,0,0], size:[w,h], text?:string}`; faces local +Z. |
| `entrance` | object, absent | Real door opening, canopy, stairs and optional lettering: g01/g02/g04. |
| `entrance.edge` | integer, required when present | Edge containing the entrance. Prefer a plain, non-arcaded edge. |
| `entrance.offset` | number, `0` | Distance along outward-facing facade local +X from its midpoint; not the polygon's vertex order. Door, canopy and stairs share it for either winding. |
| `entrance.width / height` | numbers, `2.8 / 3.1` | Clear opening; keep camera/entry within it. |
| `entrance.canopyWidth / canopyDepth` | numbers, `6 / 2.5` | Small projecting roof, ribbed structure. |
| `entrance.canopyColor` | CSS hex, `#777b70` | Muted translation of glass/metal canopy. |
| `entrance.sign` | string, absent | Lettering above door; absent means no invented branding. |
| `entrance.steps` | integer, `3` | Shallow approach steps across floorHeight. |
| `cutaway.lift` | number, viewer default `7.4` | Roof lift at the outside stop. All tiers/crown/ceiling move together. |
| `role` | string, absent | Set `main` for fallback interior resolution; explicit stop building IDs are safer. |

### Grounds object types

| Type / option | Type / default | Meaning / photo cue |
| --- | --- | --- |
| `stay_paving.size` | `[w,ignored,d]`, `[15,0,10]` | Rectangular paved court when points are absent; g08/g15. |
| `stay_paving.points` | `[x,y,z][]`, absent | Local polyline; straight paving segments join at shared nodes. |
| `stay_paving.width` | number, `3` | Polyline width; allow route ribbon and rounded bends, not just centreline. |
| `stay_paving.thickness` | number, `.12` | Actual mesh height above base. All solid faces are registered for route raycast. |
| `stay_paving.color` | CSS hex, `#c7c5b7` | Muted stone. |
| `stay_paving.jointSpacing` | number, `1.2` | Fine paving pattern pitch, clipped to segment/rectangle. |
| `stay_paving.jointColor` | CSS hex, `#b9b9ab` | Low-contrast joint instances. |
| `stay_garden.size` | `[w,ignored,d]`, `[10,0,5]` | Bed/lawn dimensions; g06/g11/g15. |
| `stay_garden.shape` | `rectangle / ellipse`, `rectangle` | Formal rectangle or curved bed. |
| `stay_garden.height` | number, `.18` | Soil/lawn plate height. |
| `stay_garden.color` | CSS hex, `#b7c0a5` | Base green. |
| `stay_garden.spacing` | number, `.8` | Plant mat spacing, with deterministic jitter. |
| `stay_garden.planting` | boolean, `true` | Low foliage coverage; false for plain lawn. |
| `stay_garden.flowers` | boolean, `true` | Small muted flower drifts. |
| `stay_garden.flowerColor` | CSS hex, `#b696a0` | Main bloom; alternate warm neutral gives variation. |
| `stay_garden.hedge` | boolean, `true` | Low clipped perimeter; no automatic route exclusion, place beds clear of walks. |
| `stay_grove.trees` | `[x,z,height][]`, `[[0,0,9]]` | Local tree positions and heights. |
| `stay_grove.species` | `pine / cypress`, `pine` | Layered foam pine or tall clipped spindle, g06/g10/g15. |
| `stay_grove.understory` | boolean, `true` | Eight low shrubs around each trunk. |
| `stay_grove.color` | CSS hex, `#a4b291` | Sage canopy. |
| `stay_sign.size` | `[w,h,d]`, `[5,1.5,.4]` | Freestanding name slab, g07. |
| `stay_sign.text` | string, empty | Photo-supported inscription. |
| `stay_sign.color / textColor` | CSS hex, `#939e99 / #f2ecdd` | Stone background / lettering. |
| `stay_pool.size` | `[w,ignored,d]`, `[8,0,4]` | Rectangular pool, coping and rim. Only instantiate with pool evidence. Not used at Dalat Palace. |
| `stay_pool.color` | CSS hex, `#a2bab7` | Quiet opaque water, no animated shader. |
| `stay_furniture.benches` | `[x,z,yaw][]`, `[]` | 1.8 m benches, seat at .47 m; yaw defaults to 0. |
| `stay_furniture.lamps` | `[x,z,height][]`, `[]` | Small square lanterns; height defaults to 3.8 m. |
| `stay_furniture.urns` | `[x,z,height][]`, `[]` | Flowering stone urns, g01/g15; crown height defaults to 1.6 m. |
| `stay_furniture.flowerColor` | CSS hex, `#b696a0` | Urn bloom tone. |

### Interior kit `stay_lounge`

Set `building.interior.kit = "stay_lounge"`; create an outside stop with
`cutaway: building.id, insideView: insideStop.id`, followed by `interior:true,
building:building.id`. The geometry is an illustrative sealed room, not an inferred
hotel floor plan. Photo cues: g19 timber panelling; g29/g31 fireplace, club chairs,
parquet, curtains, chandelier and flat coffered plaster ceiling. Use no interior
when evidence is insufficient. The ceiling belongs to the roof record; it lowers
before entering. See `batch/INTERIOR_RULES.md` for the full camera/lifecycle contract.

| Option under `interior` | Type / default | Meaning |
| --- | --- | --- |
| `kit` | string, required | `stay_lounge`. |
| `size` | `[w,h,d]`, `[7,4,10]` | Room clear enclosure, true-scale furniture independent of room size. |
| `offset` | `[x,y,z]`, `[0,floorHeight,0]` | Room centre relative to shell base. Ceiling uses the same transform. |
| `facing` | `1 / -1`, `1` | Door on room +Z, rotated 180° for a rear-facing entrance. |
| `doorWidth / doorHeight` | numbers, `2.8 / 3.1` | Room portal; align exactly with exterior door. |
| `wallColor / woodColor / trimColor` | CSS hex, `#e8dfcb / #76614c / #b8a17b` | Plaster, timber, muted metal/linework. |
| `floorColor` | CSS hex, `#b69b7f` | Parquet substrate. |
| `panelHeight` | number, `1.3` | Low panelling and frames. |
| `wallFrames` | boolean, `false` | Upper focal-wall gold linework and plaster pilasters, g29/g31; not invented paintings. |
| `ceilingGrid` | `[columns,rows]` or false, `[2,3]` | Flat coffered plaster grid with fine inset mouldings, g29/g31. False retains a sealed plain ceiling and perimeter cornice. Use positive integer counts with cells wider/deeper than .44 m. |
| `upholsteryColor / curtainColor` | CSS hex, `#a7b4aa / #9da99b` | Club chair and curtain palette. |
| `fireplace` | `{width?:number}` or false, enabled | Focal fireplace/mirror; width defaults to 2.5 m. |
| `chairs` | `[x,z,yaw][]`, four chairs | Defaults `[[-2,-1,0],[2,-1,0],[-2,1,π],[2,1,π]]`; seats .44 m, backs 1.095 m, avoid camera aisle. |
| `table` | `[x,z]`, `[0,0]` | Round table/flower vase centre; table top .69 m. |
| `carpet` | `[w,d]` or false, `[4.6,3.6]` | Width capped at room width minus 1 m; lies under furniture. |
| `carpetColor` | CSS hex, `#9e9f8f` | Muted rug. |
| `windows` | number[], `[-2.5,1.6]` | Window/curtain Z positions on both side walls. |
| `chandelier` | `{z?:number,drop?:number}` or false, enabled | Z defaults to −1 m, drop defaults to 1 m from ceiling. |
| `floorY` | number, viewer fallback building Y | Absolute finished floor, used by flight/interior region logic. |
| `entry / approach` | world `[x,y,z]`, viewer fallback | Eye-level doorway / unobstructed exterior approach, aligned along room axis. |
| `safeApproach` | boolean, false | Enable viewer's over-roof exterior detour, then doorway-level entry. |
| `boundsCenter / boundsDepth` | world `[x,y,z]` / number, building centre/depth | Required for correctly classifying an offset room during entry/exit. |
| `ridgeHeight` | number, building roof/size fallback | Safe-flight obstacle height above building base, include roof pavilions. |
| `dimmingSize` | `[w,d]`, building footprint | Local region kept lit inside; must cover the room. |
| `lights.altar / lights.fill` | world `[x,y,z]`, viewer-derived | Warm focal and gentle fill light positions, active only at inside stop. |

### Pitfalls and limits

- Dalat Palace has two different elevations. g00/g03/g08 read **DALAT PALACE**;
  g09 reads **DU PARC HOTEL DALAT** and is excluded. Do not discard a valid
  opposite elevation just because its architectural vocabulary differs.
- Use `Vector3.fromArray` for JSON vectors: copying an array with `Vector3.copy`
  produces invalid roof bounds and breaks cutaway framing.
- A polyline centreline can be paved while its final approach or rounded ribbon
  is not. Test the whole route strip and physically connect every apron.
- A rectangular rooftop terrace must fit the **entire** stepped footprint, not
  only its centre. Check each post foot and canopy edge; the flat slab top is
  .18 m above roof base, so use terrace position Y=.18 for exact contact.
- Lettering uses an 80 px base on a 1024×192 face and shrinks to fit long names.
  Choose a clear viewing angle; increasing slab dimensions cannot fix tree occlusion.
- A very long overview lens can reach the viewer's 600 m orbit-distance limit.
  Check all six default orbit angles, not just initial; Palace uses FOV 20° and
  frameFill .77 so the rotated plinth stays on-screen without changing its metres.
- Do not reuse a shared material for the cutaway front. Its opacity changes;
  the kit clones that layer so unrelated walls do not fade.
- Pitched roof `hip`/`gable` uses the rectangular `size`, while flat roofs and
  foundations follow arbitrary `outline`. Split a pitched complex into blocks.
- Grounds are flat at the supplied base Y. Subdivide/slightly step objects for
  slopes; this is not a terrain-draping or surveyed-hotel reconstruction kit.
- Repeated details use instances or material batches. Furniture is simplified
  studio geometry; stone, panelling, arch rings and glazing are not photo textures.

### Mở rộng nhà phố và biệt thự nghỉ dưỡng

Các trường dưới đây đều tùy chọn; dữ liệu không khai báo giữ nguyên hình học
khách sạn cổ điển. Kích thước bằng mét, góc bằng radian; tọa độ con theo hệ local.
Không có nhánh theo tên địa điểm. Mỗi nguồn ảnh xác nhận hình dáng, không xác nhận
mặt bằng khảo sát. Mẫu `examples/stay.place.json` minh họa cả phần mở rộng.

#### Tùy chọn mới của `stay_building`

| Trường | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `storeyHeights` | number[] / không có | Chiều cao từng tầng tính từ `floorHeight`; độ dài mảng thay `storeys`. Cho nhà phố có hiên cao (Ami g00/g07). Tổng mảng + `floorHeight` phải bằng `size[1]`; khi vắng giữ cách chia tầng cũ. |
| `facadeEdges` | integer[] / mọi cạnh | Cạnh có cửa và ban công; các cạnh còn lại là tường kín, vẫn có phào. Nhà lô sát hàng xóm (Ami g07). Không suy diễn cửa trên tường chung. |
| `windowSill` | number / `.65` | Đáy cửa so với sàn tầng; `.2–.3` cho cửa cao sát sàn (Ami g01/g06). Khi khai báo, chiều cao cửa không vượt `chiều cao tầng − windowSill − .2`; khi vắng giữ giới hạn cũ trừ `1`. |
| `windowWidthRatio` | number / `.6` | Tỷ lệ tối đa giữa cửa và một nhịp. `.75–.8` cho cửa Pháp rộng; vẫn phải chừa trụ. |
| `windowFrameColor` | CSS hex / `trimColor` | Màu khung và mullion riêng, không phải màu kính. Khung xanh Kỳ Hòa g01/g06, kính vẫn dịu và matte. |
| `arcade.kind` | `arch / colonnade` / `arch` | `colonnade`: cột tròn và dầm ngang thẳng, không có spandrel vòm. Hiên sâu Kỳ Hòa g01/g08. |
| `arcade.columnRadius` | number / `.3` | Bán kính thân cột; đế và đầu cột nhỉnh hơn. Không dùng đường kính thay bán kính. |
| `arcade.columnColor` | CSS hex / `trimColor` | Màu thân cột; vàng dịu theo g08 Kỳ Hòa. |
| `arcade.ceilingColor` | CSS hex / `wallColor` | Mặt dưới sàn phủ hiên colonnade, hoặc hiên vòm có `upperRecess`. Không để hiên lộ trời khi tầng trên về đường mặt tiền. `arcade.wallColor` cũng áp dụng cho tường lùi mang cửa vào. |
| `arcade.archRise` | number / nửa bề rộng vòm | Độ vồng riêng, tạo vòm elip nông với chân thẳng. Hai vòm lớn Ami g00/g07. Không áp dụng cho colonnade. |
| `arcade.upperRecess` | number / `arcade.depth` | Độ lùi của tầng không mang gallery; `0` đưa tầng trên về đường mặt tiền. Tránh để ban công nhà phố chìm sau vòm tầng trệt. |
| `arcade.walkable` | boolean / `false` | Sàn gallery nằm đúng cao độ `floorHeight`/đáy tầng và được đăng ký raycast. Dùng cho đường đi lên sân hiên và vào cửa; không thay bằng route trên terrain. |
| `balconies.edges / levels` | integer[] / mọi cạnh không có gallery, mọi tầng > 0 | Chọn mặt và tầng mang ban công. Ami chỉ mặt trước; không thêm ban công trên tường sát hàng xóm. |
| `balconies.railThickness` | number / `.045` | Tiết diện lan can; `.025` cho sắt mảnh Ami. Giá trị quá nhỏ dễ alias ở overview. |
| `balconies.railSpacing` | number / chia mặt trước thành 6 nhịp | Khoảng cách tối đa nan mặt trước; hai cạnh hồi cũng có tay vịn và nan. Mặc định nan hồi cách `.2`. |
| `balconies.railHeight` | number / `.95` | Chiều cao lan can trên mặt sàn ban công. Không phóng lớn theo kích thước phòng. |
| `balconies.band` | object / không có | Phào sàn liên tục qua các nhịp ban công, chỉ trên `edges/levels` đã chọn; mặt tiền nhà phố Ami g00/g07. Không dùng nếu ảnh chỉ có ban công rời. |
| `balconies.band.height / depth / overhang` | number / `.25 / .9 / .15` | Chiều dày phào, chiều sâu và độ vươn mỗi đầu. Cùng `trimColor`; không thay đổi chiều sâu lan can. |
| `entrance.canopy` | boolean / `true` | `false` bỏ mái che và gân mái; hợp với cửa đã nằm sau hiên vòm (Ami g07). Bậc dùng `steps:0` nếu do `stay_terrace` tạo. |
| `crown.pediment.glazing` | boolean hoặc object / không có | Ô kính tam giác trong đầu hồi, không phải mảng tường trắng đặc; Kỳ Hòa g00/g01/g07. `true` dùng mặc định. |
| `crown.pediment.glazing.color / frameColor / mullions` | CSS hex / màu kính và trim của nhà; integer / `5`, tối thiểu `2` | Màu kính, màu nét biên/đố và số nhịp chia. Đố đứng tự cắt theo dốc tam giác; không dùng số cửa nguyên hình chữ nhật vượt ra ngoài đầu hồi. |
| `roof.inset` | number / `1.1`, tối đa `.35 × min(w,d)` | Độ thu vào tại vai mansard; Ami g00/g07. Không dùng nhiều khối hộp tối xếp thành tầng giả. |
| `roof.overhang` | number / `.3` | Độ vươn diềm mansard mỗi bên. |
| `roof.shoulder` | number / `.82` | Phần tỷ lệ `roof.rise` dành cho mái dốc đứng; phần còn lại tạo chóp nông. `rise` mansard mặc định `3`. |
| `roof.seamSpacing / seamColor` | number / mansard `.55`, gable/hip không có; CSS hex / `#84877e` | Nhịp hàng slate và màu nét mảnh; gable/hip chỉ tạo khi khai báo `seamSpacing`. Kỳ Hòa g00/g09. Duy trì tương phản thấp, không dùng texture ảnh. |
| `roof.dormers` | object[] / `[]` | Cửa mái thuộc group mái, cùng di chuyển khi cutaway. Chỉ dùng với mansard. Ami g00. |
| `roof.dormers[].edge / offset` | integer / `2`; number / `0` | Cạnh chữ nhật `0` sau, `1` trái, `2` trước, `3` phải; offset theo local X của mặt hướng ra ngoài. Không dùng chỉ số outline bất kỳ cho mái chữ nhật. |
| `roof.dormers[].width / height / depth` | number / `1.8 / 2 / 1.2` | Khối cửa mái, phào đầu cong và kính; vị trí Z tự bám mặt dốc. Không làm khối quá sâu xuyên mái phía đối diện. |
| `roof.dormers[].y` | number / `.45` | Đáy cửa mái so với chân mái, không phải mặt đất. |

Envelope phụ để chụp cận: `<id>-gallery-<edge>-<storey>`,
`<id>-balcony-<edge>-<storey>` (gộp mọi nhịp), `<id>-roof`.
Chúng được tạo khi có `facadeEdges`, `balconies.edges`, `arcade.kind` hoặc mansard.
Dùng `hotspot.subjects` trỏ thẳng envelope phụ thay vì lấy cả tòa nhà.
Với nhà cao, khai báo `site.overviewSubjects` và `overviewAllAngles:true` để fit
cả mái ở mọi orbit; gom cả cây, bệ và hàng xóm vào envelope tổng quan.
`site.frameFill` thường `.78–.8`; nhà hẹp cao có thể bị giới hạn bởi chiều cao vùng
trống trước khi đạt 80% chiều rộng. Không làm rộng lô hoặc làm bẹt nhà để đạt tỷ lệ.

#### Các loại đối tượng mới

| Loại / trường | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `stay_context.size` | `[w,h,d]` / `[3,12,10]` | Khối hàng xóm kín, không cửa, không chữ hoặc texture. Ami g07: hai nhà ép sát lô. Không dùng thay một công trình thuộc khách sạn. |
| `stay_context.color / roofColor` | CSS hex / `#bcbab1 / #aaa99e` | Tường và nắp mái trung tính; khối bắt đầu đúng `position[1]`. |
| `stay_terrace.size` | `[w,h,d]` / `[8,2.1,3]` | Sân hiên nâng, sàn nắp và tường đỡ. Ami g04/g05/g07; Y là chân đế, mặt sàn tại Y+h. |
| `stay_terrace.color / capColor / rampColor` | CSS hex / `#c7c5b7 / #f2ecdd / #aeb0a6` | Tường đỡ, mặt sàn/bậc/bo dốc, mặt dốc. |
| `stay_terrace.garage` | object / không có | Khoang mở thật dưới sàn với tường cuối, trần, mặt dốc và gờ hai bên. Không phải hình cửa dán trên tường kín. |
| `garage.x / width` | number / `−.22w / 3` | Tâm ngang và bề rộng cửa. Phải nằm hoàn toàn trong sân hiên. |
| `garage.height` | number / `h−.25`, bị chặn ở `h−.2−floorHeight`, tối thiểu `.05` | Chiều cao thông thủy khoang, tự trừ nền nâng để trần không xuyên sàn. |
| `garage.floorHeight / streetHeight` | number / `0 / 0` | Cao độ đáy dốc trong khoang và đầu ngoài đường, so với chân object. `floorHeight` tối đa `h−.3`; muốn dốc xuống, `streetHeight` > `floorHeight`. |
| `garage.run / kerbHeight` | number / `3 / .16` | Chiều dài dốc ra local +Z và chiều cao gờ. Mặt dốc hoàn thiện cao thêm `.07`. |
| `stay_terrace.stairs` | object / không có | Thang từ đường lên hiên, cùng hệ tọa độ garage. Không đặt thang chồng vào dốc. |
| `stairs.x / width / run / steps / streetHeight` | number / `.25w / 2 / 2.5 / 8 / 0` | Tâm ngang, bề rộng, tổng chiều dài thang ra +Z, số bậc, chân thang so với chân object. Mỗi bậc có mặt đỡ và raycast riêng. |
| `stay_planter.size` | `[w,h,d]` / `[3,.7,.8]` | Bồn tường thật có đất và tán cây trồng dày; Ami g04/g06. Không chỉ là hộp có các quả cầu trên nắp. |
| `stay_planter.color / leafColor` | CSS hex / `#c6c5b7 / #a4b291` | Vỏ bồn và lá. |
| `stay_planter.spacing` | number / `.32`, tối thiểu `.15` | Nhịp lá instanced. Bồn rất hẹp phải còn đủ lòng sau hai thành `.13`. |
| `stay_planter.flowers / flowerColor` | boolean / `true`; CSS hex / `#c6b7b2` | Chấm hoa nhỏ dịu; không dùng màu bão hòa. |
| `stay_planter.text / textColor` | string / không có; CSS hex / `#f2ecdd` | Chữ trên mặt +Z, không có chữ thì không tạo texture. Không tự bịa thương hiệu. |
| `stay_vines.width / drop / strands` | number / `5 / 3 / 16` | Bề rộng điểm treo, chiều rủ tối đa và số dây. Ami g01/g06: lá nhỏ buông dọc tường, không phải dải hedge thẳng đứng. Y object là điểm treo. |
| `stay_vines.seed / color` | integer / `1`; CSS hex / `#95a388` | Bố trí xác định và sắc lá chính; một sắc sage phụ tạo chuyển nhẹ. |
| `stay_vines.openings` | `[cx,cy,w,h][]` / `[]` | Vùng cửa cần tránh, trong mặt local XY (Y âm phía dưới điểm treo); thêm khoảng tránh `.16` cho mép lá. Xoay object để áp lên mặt bên; không che kín ô cửa. |
| `stay_fence.length / height / spacing` | number / `8 / 1.15 / .28` | Hàng rào picket trắng có thanh dọc, hai thanh ngang, trụ và đầu trụ. Kỳ Hòa g07. Nhịp tối thiểu `.12`. |
| `stay_fence.picketWidth / color` | number / `.095`; CSS hex / `#eeece0` | Bề rộng thanh và màu matte. |
| `stay_fence.gateWidth / gateX` | number / `0 / 0` | Khoảng cổng trống và tâm ngang; cả thanh ngang lẫn picket đều chừa lối. Không có cánh cửa tự suy diễn. |
| `stay_pergola.size` | `[w,h,d]` / `[5,2.8,3]` | Bốn cột, dầm biên và thanh lam mở; Kỳ Hòa g07. Không có mái đặc. |
| `stay_pergola.spacing / frameColor` | number / `.6`, tối thiểu `.25`; CSS hex / `#f2ecdd` | Nhịp lam và màu khung. Chân cột tại Y object, cần tự đặt đúng nền. |

`stay_terrace` không đào terrain: toàn bộ đáy garage/mặt dốc phải nằm trên subgrade.
Đặt cao độ đường qua paving JSON để tạo dốc xuống khoang; không phủ một tấm paving
liền lên miệng garage. Thang, sàn và dốc được đăng ký walkable. Envelope phụ:
`<id>-garage`, `<id>-ramp`, `<id>-stairs`, `<id>-deck`.

#### Sân vườn và nội thất bổ sung

| Trường | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và lưu ý |
| --- | --- | --- |
| `stay_paving.pattern` | `grid / cobble / stepping` / `grid` | `cobble`: mạch nhỏ so le cho sân Kỳ Hòa g04/g09 (chỉ rectangle); `stepping`: các tấm đá rời trên polyline cho Ami g02. Không lát xám toàn bộ khu resort. |
| `stay_paving.stepLength / stepGap` | number / `.65 / .25` | Chiều dài đá và khe xanh; dùng `width` cho bề ngang. Khe là khe hình học thật, không phải vạch sơn. `stepping` không có points dùng đường thẳng 6 m. Nền `stay_garden` bên dưới phải có `planting:false`, `flowers:false` hoặc nằm ngoài bề ngang đá; không để lá/hoa che mặt đi bộ. |
| `stay_grove.species` | thêm `round / bonsai` | `round`: một tán cầu cắt tròn trên thân thấp; `bonsai`: ba tán mềm xếp tầng thấp. Kỳ Hòa g00/g04/g09. Không dùng thông thu nhỏ thay cây cầu. |
| `stay_grove.crownRatio` | number / `.45` | Bán kính XZ so với chiều cao của cây `round`; chọn từ ảnh, tránh lấn đường đi. |
| `interior.doorOffset` | number / `0` | Tâm cửa local X trên mặt +Z của phòng, phải trùng `entrance.offset` sau biến đổi. Hiên hai vòm Ami cần cửa nằm trong một vòm, không sau trụ giữa. |
| `interior.floorPattern / tileSpacing` | `parquet / tile` / `parquet`; number / `.8` | Nền tile với mạch nhỏ matte (Ami g08/g10); nhịp tối thiểu `.3`. Không dùng texture đá bóng. |
| `interior.reception` | object / không có | Quầy, mặt đá, nan đứng ở mặt quầy, nền nan ngang và chữ theo ảnh Ami g08/g09. Đặt `fireplace:false`, `chairs:[]`, `chandelier:false` nếu ảnh không có. |
| `reception.position / width / height / depth` | number[3] / `[0,0,−d/2+.8]`; number / `3 / 1.02 / .7` | Vị trí chân và kích thước quầy; top thêm `.08`, không phóng quầy theo phòng. |
| `reception.topColor` | CSS hex / `#d6d2c5` | Mặt đá dịu trên quầy. |
| `reception.backdropWidth / backdropHeight` | number / `min(w−1,width+1) / h−.35` | Nền nan gỗ trên tường cuối, giữa trục phòng, không đi theo offset quầy. |
| `reception.text` | string / không có | Chữ trên nền gỗ; absent không tạo biển. |
| `reception.textColor` | CSS hex / `interior.trimColor` | Màu chữ tách khỏi màu nan gỗ để còn đọc được trong ánh sáng sảnh. |
| `reception.openShelves` | boolean / `false` | Quầy có chân/vách, kệ dưới và cốc nhỏ thay mặt trước kín; theo Ami g08. Khoang là rỗng thật, không sơn hình chữ nhật lên khối đặc. |
| `interior.sofas` | `[x,z,yaw?,width?][]` / `[]` | Sofa theo Ami g08/g11; yaw mặc định `0`, rộng `1.8`; mặt đệm `.52`, tựa tối đa `1.0` m. Không đặt trong đường camera. |
| `interior.cushionColor` | CSS hex / `#c6b5a8` | Màu gối nhỏ trên sofa. |

Nội thất chỉ dựng khi đủ ảnh theo `batch/INTERIOR_RULES.md`. Nhóm cửa, front,
ceiling và lighting dùng cùng lifecycle `stay_lounge`; vẫn phải kiểm tra ba yaw,
mái xuống khi ở trong và đường bay đi qua cửa thật. Không coi phòng minh họa là
mặt bằng thực của khách sạn.

## market

Reusable covered-market family. List `"market"` in `kits`. All dimensions are metres;
local **+z faces the customer**, +x follows the shopfront, `rotation` is degrees about y.
No slug, place name, surveyed dimensions, or photo-specific layout is embedded in the kit.
The defaults describe a small generic market, not an inferred survey. Use the complete
buildable/boot-tested example at `kits/examples/market.place.json` and
`node test_cholacnghiep.mjs` as the contract check.

### Object types

| Type | Purpose / default `size: [width, depth]` | Photo evidence / use |
| --- | --- | --- |
| `market_hall` | Enclosed hall, recessed central entrance, roof, clerestory and optional sign; `[18,12]` | g00/g01/g11/g14: Chợ Lạc Nghiệp hall, shallow metal roof, cream posts, green shutters |
| `market_stalls` | Connected open-front units, counters, shutters and optional striped awning; `[12,3.5]` | g08/g15: alley and covered rows; g03/g09/g16: outdoor trading |
| `market_canopy` | Four-post open shelter, perimeter beams, optional counter; `[5,4]` | g09/g16: independent fabric-covered trading shelters |
| `market_frontage` | Same shell builder as hall, with upper-storey windows; `[18,12]` | Generic street-front family; example only, **not** a neighbouring shop added to this place |
| `market_paving` | Real raycastable paved slab with batched joints and optional curb; `[30,30]` | g00/g09/g11: concrete market court and g08/g15 alley |
| `market_planting` | Bordered/unbordered low planted strip with batched shrubs/flowers and optional template foam pines; `[12,3]` | Studio framing vocabulary; individual plant locations are not surveyed facts |

### Common options (all types)

| Option | Type / default | Meaning |
| --- | --- | --- |
| `id` | string; required for tour subjects | Root is named `<id>-market`; used for envelope/roof ownership |
| `position` | `[number,number,number]`; `[0,0,0]` | World translation; base elevation, not mesh centre |
| `rotation` | number; `0` | Degrees about y; also rotates paving, plants and pine positions |
| `size` | `[number,number]`; see type table | Positive footprint width/depth; awnings and roof overhang are extra |
| `colors` | object; `{}` | Partial palette override, keys below; remaining keys retain defaults |
| `colors.wall/trim/roof/metal/wood/dark` | CSS hex string; `#ddd3b8/#eee7d5/#7d9087/#718078/#8c7864/#59645c` | Masonry, fine trim, roof, shutters/metal, counters/base, recess |
| `colors.paving/joint/soil/leaf` | CSS hex string; `#d3cdbc/#b5b09f/#b4bca4/#92a17f` | Fallback slab, seam, bed and foliage colours |

Core viewer options (`role`, `evidence`, `subjects`, `walk`, `site`, `route`, etc.) remain
template data, not market-specific geometry options. Do not claim orientation/size as
measured when OSM has `main: null` or an empty `buildings` array.

### Hall / frontage / stall options

| Option | Type / default | Meaning / photo correspondence |
| --- | --- | --- |
| `height` | number; hall `4.6`, frontage `6.4`, stalls `3.1` | Eave height; g00/g14 one-storey hall and lower stall roofs |
| `bays` | integer; hall/frontage `max(3,round(width/3.6))`, portal hall `5`, stalls `max(2,round(width/2.8))` | Repeated openings. A hall with portal divides this count evenly across its two wings (at least one each) |
| `shutters` | boolean or boolean[]; `false` | Closed corrugated green door per bay; arrays repeat, g00/g14 |
| `goods` | string or string[]; `"produce"` | `produce`, `textiles`, `flowers`, `none`; array repeats by bay. Small counters and trays/folded cloth; g00/g15/g16. Flower variant is generic, not excluded flower-shop evidence |
| `display` | object; absent | Optional hanging garment rail for textile bays; g00 |
| `clerestory` | boolean; `true` | Glaze gable closure rather than masonry; g00 triangular green infill. Relevant to hall/frontage gables |
| `clerestorySpacing` | number; `1.5` | Gable mullion pitch, g00/g14 |
| `storeyHeight` | number; `3.1` | Frontage ground-storey eave; only `market_frontage` |
| `upperWindows` | integer; `max(2,round(width/2.4))` | Frontage upper-window count; only `market_frontage` |
| `roof` | object; see roof table | Every shell/canopy roof is registered independently |
| `monitor` | object; absent | Raised roof lantern/crown behind the sign; g00/g14. Hall/frontage only |
| `awning` | object; hall/frontage absent, stalls `{}` | Add front awning. `false` disables default stall awning. g08/g15 |
| `sign` | object; absent | Optional lettering; no label is invented when absent |
| `portal` | object; absent | Large recessed centre entrance on hall; frontage may use the outer portal frame but retains its shopfront bays |

### Roof options (hall / frontage / stalls / canopy)

Partial options merge with type defaults: changing only `roof.color` **does not change
roof kind or rise**. `height` is the low eave, not the high end of a skillion.

| Option | Type / default | Meaning / photo correspondence |
| --- | --- | --- |
| `roof.kind` | `gable\|hip\|flat\|skillion`; hall/frontage `gable`, stalls `skillion`, canopy `hip` | Shallow hall gable (g00/g14), lean-to rows (g15), fabric hip shelter (g09/g16), generic flat street roofs. Unknown values throw |
| `roof.rise` | number; hall/frontage `min(width*.13,2.8)`, stalls `.45`, canopy `.65` | Ridge/high-edge rise over eave; ignored by flat |
| `roof.overhang` | number; `.35`, canopy `.2` | Eave projection beyond footprint on every side |
| `roof.thickness` | number; `.13` | Sheet thickness; hip uses joined plane surfaces |
| `roof.color` | CSS hex; `colors.roof` | Sheet/fabric studio tone |
| `roof.seamSpacing` | number; `.65` | Corrugation pitch; `0` omits linework |
| `roof.seamColor` | CSS hex; `colors.trim` | Muted fine seam colour |

Hip roofs adapt their ridge axis to **both** wide and deep footprints. Shell gables and
lean-to sides are physically closed below the roof; open canopies intentionally are not.
Chợ Lạc Nghiệp không có cutaway/interior vì chỉ một ảnh nội thất phù hợp.
Chợ nhiều tầng dùng `market_building` và `market_interior` bên dưới khi đủ bằng chứng.

`monitor` options: `width` (number, `width*.3`), `depth` (number, hall depth),
`height` (number, main eave + main rise + `.8`), `offset` (`[x,z]`, `[0,0]`),
`glazed` (boolean, `true`), and `roof` (the full roof options above, merging defaults
`kind: gable`, `rise: 1.2`, `overhang: .18`). Width/depth must stay inside the parent
roof and its eave must be above the parent roof. Walls connect to the main roof;
the crown has its own roof record. This expresses a reusable raised centre bay,
not a second place-specific building builder.

### Portal / sign / awning options

| Option | Type / default | Meaning / photo correspondence |
| --- | --- | --- |
| `portal.width` | number; `width*.28` | Clear width inside frame, g00/g14 central gateway |
| `portal.height` | number; `height+.25` | Lintel centre height |
| `portal.depth` | number; `1` | Projection/thickness of entrance frame |
| `portal.recess` | number; `1.8` | Dark entrance backing behind front wall; hall only |
| `portal.goods` | goods enum; `textiles` | Two low counters at sides of entrance, leaving centre clear; hall only |
| `portal.flag` | boolean; `false` | Thin pole and muted fabric rectangle on portal, g00/g11/g14 |
| `sign.text` | string; absent | Literal name, no hard-coded market identity |
| `sign.width` | number; portal width + `.65`, otherwise width*.75 (hall/frontage) or width*.7 (stalls) | Signboard width |
| `sign.height` | number; `1.15` | Board height |
| `sign.background/color/frame` | CSS hex; `#d8d9bd/#637e83/#eee7d5` | Board, lettering and border. Lettering is canvas-backed and fits board width |
| `awning.depth` | number; `1.8` | Front projection; `0` omits geometry |
| `awning.height` | number; `2.9` | Attachment height at wall |
| `awning.drop` | number; `.42` | Lower front edge relative to wall |
| `awning.stripeWidth` | number; `.65` | Approximate stripe width; fits whole frontage |
| `awning.colors` | nonempty CSS hex[]; `[#b5b6a1,#d5ceba]` | Alternating fabric tones; g08/g15 |
| `awning.posts` | boolean; `true` | Front corner posts; thin diagonal side braces remain when posts are disabled |

Canopies accept `height` (default `2.8`), `roof`, and scalar `goods` (default `produce`).
Other hall-specific options do not apply to canopies.

`display.hanging` (boolean, `false`) enables hanging garments only when `goods` is
`textiles`; `display.railHeight` (number, `2.25`), `display.length` (number, `.62`),
`display.spacing` (number, `.55`), and `display.colors` (nonempty CSS hex[],
`[#a89486,#9aa69b,#b4a3a2]`) set rail height, cloth length, garment pitch and palette.
Rails have real posts and hooks; keep garments above the counter.

### Paving / planting options

| Option | Type / default | Meaning |
| --- | --- | --- |
| `top` | number; `.10` | Paving top relative to base |
| `thickness` | number; `.09` | Paving thickness |
| `color` | CSS hex; `colors.paving` | Paving slab colour |
| `jointSpacing` | number; `2` | Square slab pitch; `0` omits joints |
| `jointColor` | CSS hex; `colors.joint` | Joint colour |
| `curb` | boolean; `true` | Low perimeter curb |
| `floor` | number; `.08` | Planting bed top |
| `soilColor/leafColor` | CSS hex; `colors.soil/leaf` | Ground cover / shrub tone |
| `spacing` | number; `1.1` | Approximate shrub density; only used without `points` |
| `points` | `[x,z][]`; absent | Explicit local shrub positions instead of seeded scatter |
| `shrubSize` | number; `.5` | Base shrub radius, deterministic per-plant variation |
| `flowers` | number `0..1`; `.18` | Probability of a small flower cluster on each shrub |
| `seed` | number; `1` | Stable scatter/variation seed |
| `border` | boolean; `true` | Low cream bed edge |
| `pines` | `[x,z,height][]`; `[]` | Template foam pine positions in the bed's local frame |

### Pitfalls / reuse checklist

- Preserve true footprint dimensions when available. This source OSM is empty; its
  courtyard, stalls, tree positions and north orientation are explicitly illustrative.
- Do not model neighbouring Agribank, flower shops or street facades merely because
  they appear in Maps photos. Consult the place's `PHOTOS.md` first.
- Keep route centre **and full ±0.8 m arrow strip** on `market_paving`, clear of shell,
  awning posts, shelters and planted strips. Do not register beds as walkable to hide gaps.
- A gateway is not an extra column pasted over ordinary bay columns: centre bays are
  removed when a hall portal is present. Leave enough space for both wings.
- Use positive dimensions/counts/pitches and nonempty arrays. Keep sign/portal inside
  the intended facade, awning height above goods and tree crowns inside the plinth.
- Geometry uses per-material merging and instancing. Do not emit one mesh per produce
  item, shrub, stripe or paving joint. Instanced vertices are explicitly added to envelopes.
- Thin linework can alias at distant software-GL orbits. Bridge timings are not evidence
  of interactive performance on real hardware.
- A textile stop must look **under** the awning, not merely fit the roof envelope.
  Check garment sightlines; a separate canopy can occlude a correctly framed stall.
  Approach long alley rows from the open end to avoid a foreground stall roof.

### Mở rộng: chợ nhiều tầng và chợ phố

Các kiểu dưới đây dùng chung `id`, `position`, `rotation`, `colors` như trên; mọi
kích thước là mét. Không có nhánh theo tên nơi. Các builder cũ không đổi mặc định.
`size` luôn là `[width,depth]`; riêng ô dùng `radius`. Tầng, màu, số quầy, footprint,
biển hiệu và vị trí xe/cột đều do JSON quyết định. Test: `test_market_extension.mjs`,
`test_market_places.mjs`, `test_cholacnghiep.mjs`; example có đủ bảy kiểu mới.

| Kiểu | Mẫu ảnh phục vụ | Mặc định / lưu ý |
| --- | --- | --- |
| `market_building` | Chợ Mới g02/g07: khối cao tầng, lam ngang, fins, gờ cây | `[24,16]`, 6 tầng; nhận polygon lõm, không thay bằng bounding box |
| `market_entrance` | Chợ Mới g03/g06/g14: thang rộng, mái lattice, biển lớn | `[12,5]`; +z là chân thang, −z là chiếu nghỉ |
| `market_shophouses` | Chợ Mới g04/g05, Nam Thiên g04/g05/g08: phố 2–4 tầng | `[24,7]`, 4 nhà, 3 tầng; mỗi nhà có cấu hình riêng |
| `market_umbrella` | Nam Thiên g01/g03: ô biển tròn một trụ, nhiều múi | Bán kính 1,8; không phải mái hip bốn cột |
| `market_shed` | Nam Thiên g02/g03/g08: mái tôn dài trên cột | `[18,5]`; cột trung gian, không có tường kín |
| `market_goods` | Nam Thiên g01/g03: quầy và thùng rau quả sát nền | `[3,1]`; thùng đứng độc lập, không cần mái |
| `market_street` | Nam Thiên g02/g06/g07, Chợ Mới g05: đường, đèn và xe đỗ | `[30,24]`; chỉ massing xe máy, không mô phỏng giao thông |

#### `market_building`

| Option | Kiểu / mặc định | Nghĩa, bẫy cần tránh |
| --- | --- | --- |
| `footprint` | `[x,z][]` / hình chữ nhật theo `size` | Polygon cục bộ; chấp nhận hai chiều winding và điểm cuối lặp. Giữ nguyên thứ tự cạnh, không tự cắt nhau |
| `upperFootprint` | `[x,z][]` / `footprint` | Đường bao phần tầng cao; phải nằm trong tầng đế |
| `storeys`, `podiumStoreys` | integer / `6`, `storeys` | Tổng tầng và tầng bắt đầu dùng polygon tầng cao; số tầng từ ảnh, không suy ra từ OSM thiếu tag |
| `groundHeight`, `storeyHeight` | number / `4.8`, `3.2` | Cao độ deck đầu tiên tính từ base; chiều cao tầng trên |
| `floorY` | number / `.15` | Cao độ sàn trệt; phải thấp hơn `groundHeight` |
| `recess`, `columnSpacing` | number / `.8`, `4` | Độ lùi kính tầng trệt và khoảng cột tối đa; cửa vào không bị cột chặn |
| `terracotta`, `glassColor` | CSS color / `#ab8d78`, `#84958b` | Lam đất nung và kính matte trầm; không dùng vật liệu bóng/saturated |
| `finColor`, `finSpacing`, `finWidth` | color/number/number / `#bda58e`, `1.7`, `.10` | Màu, bước, bề rộng fins đứng; giữ nhịp rõ ở overview |
| `louvres.spacing/thickness/depth` | number / `.45/.13/.5` | Bước đứng, dày và nhô của lam ngang thật, được instancing |
| `planters` | object hoặc `false` / `{}` | Gờ cây trên các tầng; `false` bỏ cả gờ lẫn cây |
| `planters.every/depth/spacing` | integer/number/number / `1/.7/.85` | Nhịp tầng có cây, sâu gờ, khoảng bụi cây; không đặt spacing bằng 0 |
| `planterColor` | CSS color / `#a49a83` | Màu thành gờ; foliage dùng `colors.leaf` |
| `roofGarden` | object hoặc `false` / `{}` | Mảng cây thấp trên mái; chỉ lấy điểm bên trong polygon tầng cao |
| `roofGarden.spacing` | number / `2` | Bước lưới bụi cây mái; không tự thêm cây cao chưa có bằng chứng |
| `entrance` | object / không có; riêng building có `market_interior` mặc định `{edge:2,width:interior.doorWidth ?? 5}` | Tạo khoảng mở thật ở tầng trệt, không dán portal lên mặt kính kín; polygon khác cần edge/offset theo ảnh |
| `entrance.edge/width/offset` | integer/number/number / `2`, `size[0]*.3`, `0` | Index cạnh polygon gốc (từ 0), rộng thông thủy, lệch theo +x mặt đứng; cửa phải nằm trong cạnh |
| `interior.kit` | string / không có | `market_interior` bật nội thất; không bật khi ảnh bị loại hoặc chưa đủ bằng chứng |

Deck và toàn bộ các tầng trên đăng ký chung một roof record để cutaway mở thật
tầng trệt. Dùng `hotspot.cutaway: <id>` ở stop ngoài; stop ngay sau có
`interior:true`, `building:<id>`, stop ngoài có `insideView:<insideId>`.
Trong phòng mái hạ xuống, trần kín; rời phòng mọi phần phục hồi.

#### `market_entrance`

| Option | Kiểu / mặc định | Nghĩa, mẫu ảnh và bẫy |
| --- | --- | --- |
| `rise`, `steps`, `landing` | number/integer/number / `.9/6/1.2` | Cao tổng, số bậc, sâu chiếu nghỉ sau; khớp cao độ sàn hall |
| `stoneColor`, `rails` | color/boolean / `colors.trim`, `true` | Màu thang và tay vịn hai bên cùng độ dốc; không cắt tuyến đi |
| `stepLineColor` | color / `colors.joint` | Nét mảnh ở mũi từng bậc; với thang interior, đặt field này trên building, không đặt trong `interior` |
| `canopy` | object hoặc `false` / `{}` | Mái lattice hở như Chợ Mới g06/g14; không phải slab kín |
| `canopy.width/depth/height` | number / `width+2`, `depth+landing`, `4.6` | Kích thước mái và cao độ cục bộ; trụ phía sau, không chặn thang |
| `canopy.pitch/slatWidth/slatHeight` | number / `.45/.10/.3` | Bước lam ngang, rộng/dày lam; pitch phải dương |
| `canopy.color` | color / `colors.wood` | Màu lam; khung dùng `colors.metal` |
| `sign` | object / không có | Các field sign chung ở trên; biển đặt trên fascia trước, không bịa chữ |

#### `market_shophouses`

| Option | Kiểu / mặc định | Nghĩa, mẫu ảnh và bẫy |
| --- | --- | --- |
| `houses` | object[] / `count` nhà mặc định | Mỗi phần tử là một nhà; dữ liệu quyết định biến thiên, không random màu/tầng |
| `count/storeys/storeyHeight/windows` | integer/integer/number/integer / `4/3/3/2` | Số nhà khi không có `houses`, tầng, chiều cao tầng, cửa mỗi tầng |
| `gap`, `wallColors` | number/color[] / `.12`, không có | Khe nhà, palette lặp theo nhà; thiếu palette dùng `colors.wall` |
| `balcony` | object hoặc `false` / `{}` | Ban công ở mỗi tầng trên; g04/g05, không dồn thành một dải cửa cao |
| `balcony.depth/height/spacing` | number / `.8/.9/.28` | Nhô sàn, cao lan can, bước thanh dọc; lane đi bộ phải tránh ban công |
| `awning`, `roof` | object hoặc `false` / mái bạt `{height:storeyHeight-.3,depth:1.1,posts:false}`, roof `{kind:flat,overhang:.16}` | Dùng các field chung; `awning:false` bỏ bạt; roof không nhận `false` |
| `houses[].width/storeys/storeyHeight/windows` | number/integer/number/integer / `width/count`, kế thừa hàng | Kích thước/nhịp riêng từng nhà; footprint hàng bằng tổng width + khe |
| `houses[].color/glassColor` | color / palette hàng, `colors.dark` | Màu tường và recess tầng trệt |
| `houses[].balcony/awning/roof` | object / kế thừa hàng | Override từng field; balcony/awning nhận `false` |
| `houses[].sign/goods` | object/goods enum / không có | Biển tầng trệt và quầy trước nhà; chỉ ghi chữ có trong ảnh |

#### Ô, mái chợ, thùng hàng và đường

| Kiểu / option | Kiểu / mặc định | Nghĩa và bẫy |
| --- | --- | --- |
| umbrella `radius/height/rise/segments` | number/number/number/integer / `1.8/2.5/.65/12` | Bán kính, cao mép, độ vồng, số múi; tán không lấn tuyến đi |
| umbrella `fabricColors/goods` | color[]/goods enum / `[#bdad97,#d4cbb7]`, `produce` | Màu múi luân phiên; batch theo màu, chỉ một trụ giữa |
| shed `height/postSpacing/bays/goodsZ` | number/number/integer/number / `3.2/3/max(2,round(width/2.8))/0` | Cao mép, bước cột tối đa, số quầy, lệch quầy theo z |
| shed `roof/goods/sign` | object/enum hoặc enum[]/object / `{kind:gable,rise:.7}`, `produce`, không có | Mái tôn/linework dùng roof chung; cột đỡ tới cao mái thật |
| shed `roof.ridgeAxis` | `x\|z` / `x` | Sống mái gable chạy dọc chiều dài +x; `z` giữ trục mái hall. Không áp dụng cho mái flat/skillion/hip |
| goods `kind/crates` | goods enum/integer / `produce/4` | Quầy mẫu chung và số thùng trên nền phía +z; không chặn lối bằng thùng |
| street `junction/roadWidth` | `[x,z]`/number / `[-width*.3,depth*.2]/7` | Tâm giao đường và bề rộng hai nhánh; chọn trong footprint đế |
| street `roadColor/markColor/crossings` | color/color/boolean / `#aaa99e/#d5d0bb/true` | Màu đường, vạch, có zebra hai nhánh; đường là mặt raycast thật |
| street `top` | number / `.075` | Cao mặt đường; đặt cao hơn paving nền nếu hai slab chồng nhau để không mất màu asphalt |
| street `trafficLights` | `{position:[x,y,z],rotation:number}[]` / `[]` | Vị trí cục bộ, base `[0,0,0]`, quay 0°; hình khối đèn, không animation |
| street `motorbikes/bikeColors` | `[x,z,yawDegrees][]`/color[] / `[]`, `[#8c9990,#a28c7e,#b9b4a1]` | Xe đỗ instancing; yaw thiếu = 0; bánh đứng, trục ngang, chừa lối đi |

#### Interior kit `market_interior`

Cấu hình nằm trong `building.interior`. Mẫu Chợ Mới g09/g10/g13/g16/g18;
không tự dùng ảnh quán ăn/cửa hàng khác. Tuân thủ `batch/INTERIOR_RULES.md`.

| Option | Kiểu / mặc định | Nghĩa và bẫy |
| --- | --- | --- |
| `size/offset` | `[width,depth]`/`[x,z]` / `building.size - .6`, `[0,0]` | Phòng cục bộ trong polygon; offset cho hall không đối xứng |
| `height/floorY` | number / `4.6`, `building.position.y + (building.floorY ?? .15) + .03` | Cao trần và cao độ sàn thế giới; sàn phòng cao hơn shell 3 cm; override theo deck thật, camera cao sàn +1.6 |
| `ambientFill` | number / `.14` | Indirect fill nhẹ bằng material riêng trong phòng; không thêm đèn point bật thường trực. Giữ thấp để palette không bị phẳng/sáng gắt |
| `wall/wood/floorColor/ceilingColor/beamColor/jointColor/stallColor` | color / `colors.trim/wood`, `#ccc6b5/#d7d2c4/#a5aa9e/#ada997/#aaa58d` | Palette trầm của phòng; material front tách riêng để fade không ảnh hưởng tường khác |
| `aisleWidth/stalls/stallDepth` | number/integer/number / `4/5/2.5` | Lối giữa, số quầy mỗi bên, chiều sâu quầy; gói hàng lộ ra lối, không chôn trong tường |
| `tileSize/lightSpacing` | number / `.6/2.4` | Mạch lát và nhịp đèn tuýp; trần nền liên tục, không nhìn ra trời giữa đèn |
| `doorWidth/doorHeight/signs` | number/number/string[] / `5/3.8`, không có | Khoảng mở cửa và chữ quầy lặp; không bịa tên cửa hàng |
| `stair` | object hoặc `false` / `{}` | Thang trung tâm làm điểm cuối hành lang; không đặt trước camera |
| `stair.width/depth/rise/steps/position` | number/number/number/integer/`[x,z]` / `aisleWidth*.8/4/2.4/14/[0,-depth/2+3]` | Kích thước, cao tổng, số bậc, vị trí cục bộ; không xuyên trần |

| `entry/approach` | world `[x,y,z]` / cửa local `[0,floor+1.6,d/2+.25]`, phía ngoài `d/2+3` | Tự đổi offset/yaw sang world; override theo cửa thật, đặc biệt facade không vuông. Building có interior và thiếu `entrance` tự mở edge 2 rộng `doorWidth ?? 5`; polygon khác phải khai báo edge/offset thật |
| `boundsCenter/boundsDepth/dimmingSize` | world vector/number/`[w,d]` / tâm sàn world, `d`, `[w+2abs(offset.x),d+2abs(offset.z)]` | Bounds bay theo tâm phòng; dim core lấy tâm building nên phải bao cả offset, tránh làm tối tiền cảnh phòng. Không dùng chiều sâu sai từ `building.size[2]` |
| `safeApproach/ridgeHeight` | boolean/number / `true`, đỉnh bbox mái/tầng cao trừ base Y | Đường bay vượt cả khối tầng trên và khoảng lift, không dùng trần phòng làm đỉnh mái; khai báo lại khi cửa có hình học đặc biệt |
| `lights.altar/lights.fill` | world `[x,y,z]` / local `[0,floor+.7h,∓.22d]` | Hai đèn core chỉ bật inside; tên altar là API, không thêm bàn thờ |

`cutaway.lift` là contract core viewer, đặt đủ cao cho khối tầng trên. Mọi
override được giữ nguyên. Kiểm tra inside ở yaw −4°/0°/+4° và cutaway ngoài
qua render bridge; waypoint mặc định không thay thế kiểm chứng cửa polygon.

## storefront

Reusable cafés, restaurants, bakeries, spas and shops. Load `"kits": ["storefront"]`.
Use `kits/examples/storefront.place.json` as a complete JSON-only fixture; build and
boot are covered by `test_gach1988.mjs`. No slug, brand or surveyed coordinate is
hard-coded in the kit. Dimensions are metres; local +z is the entrance; `rotation`
is clockwise-looking-down Three.js y rotation in **degrees**. `size` order differs
between buildings `[width,height,depth]` and landscape `[width,depth]`.

All object types share `id: string` (required, unique framing/roof owner),
`position: [number,number,number] = [0,0,0]` (local origin at the supporting ground),
`rotation: number = 0` (degrees). Supply absolute support elevations for terraces
on slopes. Keep walkable surfaces continuous; garden surfaces are never walkable.

| Type | Purpose / photo cues |
| --- | --- |
| `storefront` | One configurable shell: arched or glass shopfront, masonry wall, roof, veranda, balcony, awning and fascia. Gạch g03/g07/g12 = cream arcade; g08/g09 = brick arches. |
| `storefront_paving` | Stone apron, garden path or timber boardwalk; optional rise and guardrails. Gạch g10/g12 stepping route is translated to continuous paving for the walking strip. |
| `storefront_garden` | Lawn or seeded low leaf/flower drift with optional border. g00/g01/g03/g07. |
| `storefront_grove` | Instanced pine, cypress or broadleaf with optional low planting. g00/g05/g12. |
| `storefront_terrace` | Paved seating terrace, real-scale tables/chairs, optional octagonal umbrellas and railing. g06/g08. |
| `storefront_sign` | Freestanding signboard or open entrance arch. g13 arch; building fascia is `storefront.sign`. |
| `storefront_pergola` | Four-post slatted garden structure, optionally planted. Generic supported feature; Gạch placement is illustrative, not evidence for the excluded g15 structure. |
| `storefront_steps` | Ascending stair flight, registered as walkable. g12. |
| `storefront_room` (interior kit) | Sealed room, plank ceiling, arched side panels, coffee/pastry counter, furniture and plants. g16–g19. |

### Building options (`storefront`)

| Option | Type / default | Meaning / evidence |
| --- | --- | --- |
| `size` | number[3], `[12,4,7]` | Width, total wall height, depth; estimate only when footprint absent. |
| `storeys` | positive integer, `1` | Evenly divides total wall height into shopfront rows, with upper floor slabs/bands. Upper slabs lift with the owned roof for ground-floor cutaway. Two-storey glass shophouse is in the example. |
| `floorY` | number, `.18` | Finished floor above object origin; foundation extends to ground. |
| `wall`, `trim`, `wood` | CSS color, `#d7c8a8`, `#eee7d9`, `#75604f` | Muted plaster, arch edge, joinery. |
| `foundation` | CSS color, `#a69c88` | Low plinth/stone skirt; g12. |
| `facade` | object, `{}` | Front opening configuration. |
| `facade.kind` | `arched` / `glass` / `solid`, `arched` | Cream/brick arcade; modern glazed café; closed shop/spa frontage. |
| `facade.bays` | positive integer, `3` | Evenly spaced front bays. Odd bay count gives a central interior door. |
| `facade.openingWidth` | number, `width/(bays+1)*.76` | Clear arch width, less than bay spacing. |
| `facade.openingHeight` | number, `min(3.1,(height-floorY)/storeys-.3)` | Arch crown height above each floor. Must exceed half opening width. |
| `facade.glass` | CSS color, `#899c94` | Opaque studio glazing; not photoreal transparent glass. |
| `facade.brick` | object / absent | Optional instanced front brick joints, clipped away from openings; g09. |
| `facade.brick.height`, `.width`, `.joint` | number / number / CSS color, `.19` / `.48` / `#ba9782` | Course pitch, brick length, mortar color. |
| `roof` | object, `{}` | Registered liftable roof; independent from veranda roof. |
| `roof.kind` | `hip` / `gable` / `flat`, `hip` | Muted pitched roof or parapeted flat roof; g12 / g09. |
| `roof.rise`, `.overhang` | number, `1.5`, `.28` | Ridge above wall; horizontal eaves extension. |
| `roof.color`, `.lineColor` | CSS color, `#77776c`, `#9a9381` | Roof surface and fine course lines. |
| `roof.parapet` | boolean, `true` | Perimeter curb on a flat roof only. |
| `veranda` | object / absent | Open front arcade and separately liftable canopy. g03/g07. |
| `veranda.depth`, `.height` | number, `2.4`, `floorY+(height-floorY)/storeys-.3` | Front projection; ground-storey canopy soffit height above object origin. |
| `veranda.openingWidth` | number, `width/bays-.32` | Clear veranda arches. |
| `veranda.balcony`, `.railSpacing` | boolean / number, `false` / `.35` | Optional rooftop balustrade and spindle pitch; g04/g06. |
| `awning` | object / absent | Sloping fabric canopy with valance; g12. |
| `awning.depth`, `.drop`, `.color` | number / number / CSS color, `1.5` / `.45` / trim | Projection, fall, fabric color. |
| `sign` | object / absent | Fascia above front/veranda. Text never inferred from brand. |
| `sign.text`, `.width`, `.height`, `.y` | string / number / number / number, `""` / `width-.3` / `.65` / `height-.3` | Label, board width/height, board center elevation; g03/g12. |
| `sign.background`, `.color` | CSS color, wood / trim | Board and lettering. |
| `cutaway.lift` | number, viewer default `7.4` | Vertical displacement of all building-owned roof records at exterior cutaway stop. |
| `role` | string / absent | Use `main` for viewer fallback; explicit interior building id is preferred. |

### Landscape, seating and signage options

| Type / option | Type / default | Meaning |
| --- | --- | --- |
| paving `size`, `height` | number[2] / number, `[4,10]` / `.09` | Slab footprint/top above origin. |
| paving `color`, `joint`, `grid` | CSS color / CSS color / number, `#d0c8b8` / `#b8b1a1` / `1` | Surface, fine joint tint and pitch. |
| paving `surface` | `stone` / `timber`, `stone` | Timber uses .22 m plank pitch along local z. |
| paving `rise` | number, `0` | Additional top elevation at local +z edge, for a grounded ramp. |
| paving/terrace `rail` | object / absent | Full perimeter guardrail; omit on through paths. |
| rail `color`, `spacing` | CSS color / number, wood / `.5` | Rail tint and spindle pitch. |
| garden `size`, `kind` | number[2] / `bed` or `lawn`, `[5,8]` / `bed` | Patch footprint; lawn has no shrubs, flowers or border. |
| garden `height`, `color` | number / CSS color, `.06` / `#b5bda4` | Supporting ground mat elevation/tint. |
| garden `density`, `seed` | number / integer, `3` / `17` | Low plants per square metre, deterministic placement. |
| garden `rows`, `plantScale` | integer / number, `0` / `1` | `0` scatters naturally; positive count makes garden flower bands (g07). Scale changes low foliage/head size, not count. |
| garden `leaf` | CSS color, `#8e9f80` | Primary foliage tint; one-third varied lighter sage. |
| garden `flowers` | CSS color[] / `false`, `[#c5bbb0,#aa91a3,#b7a277]` | Palette cycling through small heads, or no flowers. |
| garden `border`, `borderColor` | boolean / CSS color, `true` / `#b1a48c` | Fine continuous perimeter, not giant scattered rocks. |
| grove `trees` | array of `[x,z,height?]`, `[[0,0,4]]` | Local tree centers; omitted individual height is `4`. |
| grove `kind`, `color`, `trunk` | `pine` / `cypress` / `broadleaf`, `pine`; CSS colors `#8e9f80`, `#8c806b` | Foam crown profile and muted colors. |
| grove `understory` | boolean, `true` | Five low shrubs at every tree base; keep clear of route ribbon. |
| terrace `size`, `height`, `color` | number[2] / number / CSS color, `[6,5]` / `.1` / `#c5b89e` | Paved seating platform. |
| terrace `tables` | `[x,z,yawDegrees?][]`, `[[-1.5,0],[1.5,0]]` | Table centers/orientations; two spindle chairs per table, .47 m seat top and .94 m back top. |
| terrace `umbrellas` | `[x,z,radius?,topHeight?][]`, `[]`; radius `1.8`, height `2.65` | Umbrellas above platform; grounded pole and base. g08. |
| terrace `wood`, `fabric` | CSS color, `#75604f` / `#d8c9a7` | Furniture and umbrella colors. |
| sign `kind`, `size` | `board` / `arch`, `board`; number[2], `[3,1]` | Board width/height, or arch clear width/crown height. |
| sign `height`, `text`, `color`, `textColor` | number / string / CSS color / CSS color, `2.2` / `""` / wood / trim | Board top height, lettering, supports/board and letters. `height/text/textColor` do not affect arches. |
| pergola `size`, `height`, `spacing` | number[2] / number / number, `[5,4]` / `2.7` / `.45` | Plan, beam height, slat pitch. |
| pergola `color`, `vines`, `leaf` | CSS color / boolean / CSS color, wood / `true` / sage | Structure and optional roof-margin planting. |
| steps `size`, `steps`, `rise`, `color` | number[2] / integer / number / CSS color, `[3,2]` / `4` / `.15` / `#b7b0a0` | Width/run, tread count, rise per tread, stone tint. Highest tread at local −z. |

### Interior options (`building.interior`)

Use `kit: "storefront_room"`. Exterior cutaway stop immediately precedes the
`interior: true, building: "<id>"` stop. Interior eye camera, entry, approach and
lights are **world-space** and belong in JSON, including rotated fixtures.
The room returns a real door, furnishing group and a closed ceiling attached to
the owned roof. No roof opening or sky is used as interior lighting.

| Option | Type / default | Meaning / photos |
| --- | --- | --- |
| `size` | number[2], `[building.width-.45,building.depth-.45]` | Room may be a smaller partition inside the shell. |
| `floorY`, `height` | number, building.position.y + (building.floorY or `.18`) / `min(3.5,(building.height-localFloorY)/storeys-.1)` | **World-space** room datum; height is clear ceiling above it. Tile finish extends 8 mm above datum. Elevated shells subtract the supporting datum exactly once. |
| `wall`, `wood`, `floor`, `joint` | CSS color, `#d7c8a8` / `#75604f` / `#afa797` / `#bfb7a7` | Plaster, joinery, tiles and seams; g16/g17. |
| `tileSize` | number, `.5` | Square floor grid pitch. |
| `ceiling`, `plankWidth`, `beams` | CSS color / number / boolean, `#93745e` / `.26` / `true` | Sealed timber ceiling, fine plank seams and transverse beams; g17. |
| `doorWidth`, `doorHeight` | number, `2.4` / `3` | Clear central door through the room front. Match exterior central bay. |
| `windows` | number[], `[-2,0,2]` | z positions of arched landscape panels on both side walls. |
| `windowWidth`, `windowHeight`, `windowColor`, `trim` | number / number / CSS color / CSS color, `1.4` / `2.5` / `#a7b5a5` / trim | Muted opaque view panels, not invented real photos; g17/g18. |
| `counter` | object / `false`, `{}` | Coffee and pastry counter, omitted for shop/spa rooms. |
| `counter.position`, `.width`, `.label` | number[2] / number / string, `[0,-depth/2+.8]` / `4.2` / `""` | Counter center, width and optional wall label. g16/g19; label is supplied, never inferred. |
| `counter.labelY` | number, `1.8` | Label height above floor; omit label for evidence without lettering. |
| `counter.backdrop` | object / absent | Optional opaque arched back-bar panel, g16. |
| backdrop `width`, `height`, `color` | number / number / CSS color, `3` / `3` / `#8a9e99` | Back-bar arch clear size and muted blue/green tint. |
| `clock` | object / absent | Small wall clock with hour marks and hands, g16. |
| clock `position`, `radius` | local number[3] / number, `[-width*.25,localFloorY+2.6,-depth/2+.13]` / `.25` | Building-local clock center and radius; localFloorY = world floorY minus building.position.y. |
| `tables` | `[x,z,yawDegrees?][]`, `[[-3,0],[3,0]]` | Same furniture as terrace; `[]` for empty circulation. g17. |
| `plants` | number[2][], two rear corners inset .5/.6 | Potted low foliage; g16. |
| `hideFront` | boolean, `false` | Return shell front as cutaway front layer; use only when needed for close exterior view. |
| `entry`, `approach` | world number[3], required for reliable entry flight | Door waypoint and exterior alignment waypoint. Keep all shell/arcade columns clear of the eye path. |
| `safeApproach`, `ridgeHeight` | boolean / number, viewer `false` / wall height | Enable safe high exterior approach; actual peak height above object origin. |
| `boundsDepth`, `boundsCenter` | number / world number[3], viewer building depth / position | Optional safe-flight room bounds; set for a smaller or offset room. |
| `dimmingSize` | number[2], viewer building width/depth | Exterior-dimming rectangle in the entrance-aligned coordinate system. |
| `lights.altar`, `lights.fill` | world number[3], viewer-derived | Soft focal light (counter) and fill; enabled only at interior stop. |

### Pitfalls and limits

- Do not make Shape holes cross the outside boundary: triangulation fills the
  intended arch. The kit leaves a 12 mm hidden sill and tests the complete entry ray.
- Instance colors use a white base material, preventing double-multiplied dark plants.
- `walkableGeometries` receives transformed pavement only, never lawn. Test both
  raw and rounded walking strips and the edges of the ground arrows.
- The shared viewer normalizes invisible walking buffers to non-indexed
  position/normal buffers before merging. This permits mixing box-based storefront
  paths with non-indexed garden/nature paths; the mixed-kit fixture covers it.
- Front glazing must leave the central doorway open; use an odd number of bays for
  an interior entrance. Room partitions, furniture and world-space waypoints must agree.
- Only the viewer-selected supported interior opens a shell. Missing/unknown kits
  remain glazed/closed and have their invalid inside stops removed.
- Box/detail batching is not available in interior callbacks. This kit merges local
  ordinary meshes and instances repeated leaves, joints, spindle rails and furniture.
- Each pitched/flat roof and veranda canopy has its own owner-stamped roof record.
  Ceilings stay in roof-local coordinates, not a second world transform.
- Upper-storey slabs also belong to the liftable roof group; facade bands remain
  fixed. Never leave an opaque slab above an exploded ground-floor interior.
- The interior floor finish clears the shell foundation by 8 mm; tile seams sit
  above that finish rather than sharing a coplanar face with another material.
- `interior.floorY` is world-space like the viewer's flight contract, while
  `storefront.floorY` is local to its ground. Do not add the slope elevation twice.
- Interior anchors can coincide with the eye camera. The shared viewer skips
  hidden/non-finite pin projections before writing SVG leader coordinates.
- `site.overviewPolar` can be necessary to reach ~80% free-width fill without cropping
  a deep garden plinth; a higher top-down view may be height-bound instead.
- Gạch has no OSM building polygons. Both branded shells are evidence-backed, but
  their adjacency, size, orientation, garden boundary and room layout are illustrative.
  Excluded g11/g15 must not reappear as geometry or hotspot evidence.
- This is a studio kit, not a facade survey or a promise of identical architecture
  across the whole batch. Choose options from each place's evidence; omit unknown features.

### Cấu kiện mở rộng: nhà hàng sân vườn và chủ đề Tây Nguyên

Các type dưới đây vẫn dùng chung `id`, `position`, `rotation`; không chứa nhánh theo
tên địa điểm. `size` của công trình là `[width,height,depth]`, riêng vườn đá/cầu là
`[width,depth]`. Chỉ chọn cấu kiện có ảnh làm bằng chứng. Các palette mặc định đều
là màu studio mờ, không lấy nguyên độ bão hòa của ảnh.

| Type | Mặc định và mẫu ảnh | Lưu ý |
| --- | --- | --- |
| `storefront_shelter` | Mái tôn lớn trên cột thép, `[8,3.4,10]`; Bon g00/g08/g14 | Mái có tấm đặc, sóng nổi, xà và giằng; không dùng pergola giả mái kín. |
| `storefront_dining_hall` | Nhà ăn gỗ mở bên, `[7,3.4,18]`; Bích Câu g10, Bon g12/g13 | Mái hai dốc chạy dọc z; bàn ghế cao đúng tỷ lệ. Không tự thêm tour nội thất. |
| `storefront_stilt_house` | Nhà sàn gỗ, `[10,5.4,7]`; Bon g00/g10 | `height` là cao độ mép mái tính từ đất, không cộng thêm chiều cao sàn. |
| `storefront_pavilion` | Cổng bốn cột mái lá hip, `[4,3,3]`; Bon g02/g05 | Giữ thông đường giữa cột; giằng nằm dưới tiết diện mái. |
| `storefront_jars` | Chum đất nhóm hoặc trên kệ; Bon g00/g10 | Thân Lathe, miệng lõm tối, vành và đai riêng; không dùng tán cây giả chum. |
| `storefront_figures` | Tượng gỗ đẽo, `[[0,0,1.6]]`; Bon g03/g05 | Nhân vật hình học tối giản, không suy đoán danh tính/hoa văn. |
| `storefront_mushroom_stair` | Thang xoắn ôm trụ, chiếu nghỉ hình nấm; Bon g05 | Bậc nối vào trụ; cần chừa cả bán kính thang, không chỉ mũ nấm. |
| `storefront_rockery` | Đá, thác bậc, hồ và dương xỉ; Bon g03/g07 | Hồ/đá không được đăng ký walkable. Hướng nước chảy về local +z. |
| `storefront_rope_bridge` | Ván gỗ võng, cột và hai hàng dây; Bon g11 | Nối hai đầu với lối tiếp cận có cùng cao độ; không tự bịa sông bên dưới. |

#### Khung và mái dùng chung

Áp dụng cho shelter/dining hall/pavilion; stilt house chỉ dùng phần mái. Giá trị
mặc định riêng của từng type được ghi cùng hàng. Cột và chi tiết lặp dùng instancing.

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và giới hạn |
| --- | --- | --- |
| `size` | number[3], theo bảng type | Chiều ngang, mép mái, chiều sâu; Bon mái lớn/Bích Câu nhà ăn dài. |
| `postSpacing` | number, `3`; pavilion = depth | Khoảng cách cột tối đa dọc z, tự chia đều; đừng đặt cột giữa cửa. |
| `postWidth` | number, `.16` | Tiết diện cột vuông. Bon g08 thép mảnh, Bích Câu g10 gỗ mảnh. |
| `steel` / `wood` | CSS color, shelter `#767f78`, dining `#75604f`, pavilion `#756650` | Màu khung; shelter dùng `steel`, các nhà gỗ dùng `wood`. |
| `braces`, `trusses` | boolean, `true` | Giằng đầu cột và kèo dưới mái. Mái shed không sinh kèo tam giác. |
| `roof.kind` | `shed` / `gable` / `hip`, `gable`; pavilion `hip` | Một dốc, hai dốc hoặc bốn dốc. Bon g08 mái tôn, g05 mái lá. |
| `roof.ridgeAxis` | `x` / `z`, `x`; dining `z` | Hướng sống mái; Bích Câu g04 đầu hồi hướng lối vào, g10 sống dọc nhà ăn. |
| `roof.rise` | number, `.8`; stilt `1.4`, pavilion `1.5` | Đỉnh so với mép mái; mái shed dốc cao về −z khi ridgeAxis `x`, về −x khi ridgeAxis `z`. Cột/giằng tự theo dốc. |
| `roof.overhang` | number, `.35`; stilt `.65`, pavilion `.6` | Đua mái. Phải tính vào khoảng hở giữa công trình. |
| `roof.material` | `metal` / `thatch`, `metal`; pavilion `thatch` | Lá dùng mái kín và tua ở diềm; không trộn màu kim loại bóng. |
| `roof.color` | CSS color, `#77776c`; pavilion `#9f9274` | Màu tấm mái/lá, luôn mờ. |
| `roof.lineColor` | CSS color, metal `#a4a89e`, thatch `#aa9878`; pavilion `#b8a887` | Sóng nổi hoặc nét diềm lá; đừng dùng trắng gắt. |
| `roof.pitch` | number, metal `.24`, thatch `.12` | Khoảng sóng tôn hoặc tua lá, đơn vị mét. Không đặt 0. |
| `roof.thickness` | number, `.09` | Độ dày tấm kim loại. Không thay cao độ cột. |
| `roof.ribWidth`, `roof.ribDepth` | number, `.028`, `.026` | Bề ngang/cao sóng tôn. Giữ nhỏ để không thành dãy xà. |
| `roof.fasciaColor` | CSS color, `#7d8278` | Nẹp hai mép tôn, Bon g08/g14. |
| `roof.fringe` | number, `.18` | Chiều dài tua lá, Bon g02/g05; chỉ có tác dụng với mái lá. |
| shelter `floor` | object / `false`, `{}` | Sàn có đăng ký walkable; `false` khi đã có sàn riêng. |
| shelter `floor.height`, `.color` | number / CSS color, `.1` / `#999c91` | Cao mặt sàn và màu. Tránh hai mặt sàn trùng nhau. |
| dining/pavilion `floorY` | number, `.12` | Cao mặt sàn tính từ gốc object. |
| dining/pavilion `floorColor` | CSS color, `#b6a594` / `#8c8e7f` | Nền nhà ăn/cổng; Bon g14 nền đá xám, Bích Câu g10 nền gạch trầm. |
| dining `tables` | `[x,z,yaw?][]`, một hàng giữa, bước `3` m | Bàn ghế theo layout ảnh; `[]` để không sinh bàn. Chừa lối cửa/camera. |

#### Nhà sàn, chum và tượng

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và giới hạn |
| --- | --- | --- |
| stilt `stiltHeight` | number, `2.1` | Cao mặt sàn. Phải nhỏ hơn `size[1]`; Bon g00. |
| stilt `wood`, `trim`, `glass`, `joint` | CSS color, `#886951`, `#ac8b69`, `#5d665b`, `#a28365` | Gỗ, nẹp/cánh cửa, ô tối và nét ván. Không tự thêm vòm đá. |
| stilt `plankWidth` | number, `.23` | Bước ván gỗ ngang; Bon g00/g10. |
| stilt `bays` | integer, `3` | Số cụm cửa. Không suy ra số gian từ tên địa điểm. |
| stilt `windowWidth`, `windowHeight` | number, `width/bays*.55`, `(height-stiltHeight)*.55` | Kích thước cửa, có chớp và song mảnh. |
| stilt `balcony.depth`, `.railSpacing` | number, `1.5`, `.28` | Độ sâu ban công và bước con tiện. Bon g00/g10. |
| stilt `balcony.jars` | integer, `9` | Số chum trên ban công; `0` bỏ chum. |
| stilt `balcony.jarHeight`, `.jarColor` | number / CSS color, `.68` / `#9b805a` | Chiều cao và màu chum. Đừng phóng chum cao hơn lan can. |
| jars `entries` | `[x,y,z,height?,radius?][]`, `[[0,0,0,1]]` khi không có kệ, `[]` khi có kệ | Từng chum; height `1`, radius `height*.35`. `y` là đáy, không phải tâm. `entries:[]` tắt chum rời. |
| jars `color`, `colors`, `rimColor` | CSS color / CSS color[] / CSS color, `#987b5d` / absent / `#b39a76` | Thân chung, chu kỳ màu từng chum và nét vành/đai. Màu men được hạ bão hòa. |
| jars `shelf` | object / absent | Kệ gỗ có chân và nhiều hàng chum; có thể dùng đồng thời với `entries`. Bon g10. |
| shelf `size` | number[3], `[4,2.8,.75]` | Ngang/cao/sâu kệ. Không đặt chum sâu hơn kệ. |
| shelf `levels`, `columns` | integer, `3`, `6` | Số tầng và số chum mỗi tầng. Đặt số dương. |
| shelf `base` | number, `.1` | Cao tấm kệ đầu tiên. |
| shelf `jarHeight`, `jarRadius` | number, `min((height-base)/levels*.86,.85)`, `min(width/columns*.36,jarHeight*.32)` | Kích thước chum. Khi override phải tự giữ khoảng hở giữa tầng/cột. |
| shelf `color` | CSS color, `#75604f` | Gỗ kệ. |
| figures `figures` | `[x,z,height?,yaw?][]`, `[[0,0,1.6]]` | Cao `1.6`, yaw `0` độ; xoay cả mặt và tay chân. Bon g03/g05. |
| figures `color`, `faceColor` | CSS color, `#8e7156`, `#ad916d` | Gỗ và sống mũi nhạt; không bịa màu trang phục. |

#### Thang nấm, thác và cầu

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và giới hạn |
| --- | --- | --- |
| mushroom `radius`, `height` | number, `1.6`, `2.8` | Bán kính chiếu nghỉ và đỉnh mũ; Bon g05. |
| mushroom `steps`, `turn`, `startAngle` | integer / number / number, `16`, `240`, `0` | Số bậc, góc quấn và góc bắt đầu (độ). `steps`, `turn` phải dương; `startAngle` có thể âm. |
| mushroom `stairWidth` | number, `.65` | Phần bậc nhô ra ngoài mũ; bán kính bao = radius + stairWidth. |
| mushroom `color`, `ribColor` | CSS color, `#b4a16f`, `#a38f61` | Đất vàng trầm và gân dưới diềm. Không dùng vàng neon từ ảnh. |
| rockery `size`, `height` | number[2] / number, `[7,6]` / `2.8` | Mặt bằng và cao thác. Chiều sâu gồm hồ phía +z. |
| rockery `tiers`, `fallWidth` | integer / number, `4` / `width*.26` | Bậc đá và bề ngang dải nước; nước nối từ bậc cao về hồ. |
| rockery `tierRocks`, `tierRockScale` | boolean / number, `true` / `1` | Đá mặt bậc và hai sườn che lõi thác vuông; Bon g03/g07. Tỷ lệ phải dương, không phóng lớn tới mức lấp dòng nước. |
| rockery `pool` | number[2], `[width*.68,depth*.38]` | Ngang/sâu hồ elip. Không walkable, không gắn route vào hồ. |
| rockery `boulders`, `ferns`, `fernScale` | integer / integer / number, `24`, `20`, `1` | Số ứng viên đá rời, bụi dương xỉ và tỷ lệ lá. Đá gần dòng chảy được bỏ qua. |
| rockery `seed` | integer, `7` | Đá/dương xỉ tái lập được. Bon g03/g07. |
| rockery `color`, `waterColor`, `leaf` | CSS color, `#929587`, `#a8bcb3`, `#7f967b` | Đá, nước đục dịu và dương xỉ; không dùng hồ xanh bể bơi. |
| bridge `size`, `height`, `sag` | number[2] / number / number, `[2.4,7]`, `.8`, `.25` | Ngang/dài, cao đầu cầu, võng giữa. `sag < height-.1`. |
| bridge `plankWidth` | number, `.22` | Bước ván dọc z, có khe nhỏ; không dùng 0. |
| bridge `postSpacing`, `railHeight`, `ropeRadius` | number, `1.8`, `.95`, `.027` | Bước cột, cao tay vịn trên mặt cầu và bán kính dây. Bon g11. |
| bridge `color`, `ropeColor` | CSS color, `#988875`, `#8f8c72` | Ván/cột và dây mờ. Cột hai đầu xuống đất, cột giữa đi theo mặt võng. |

#### Tùy chọn bổ sung cho type hiện có

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và giới hạn |
| --- | --- | --- |
| garden `shape` | `ellipse` / `kidney` / absent | Mảng cong mới; absent giữ nguyên hình chữ nhật. Bích Câu g03/g05. |
| garden `outline` | `[x,z][]` / absent | Điểm điều khiển khép kín, nội suy Catmull-Rom; ưu tiên hơn shape. Không tự cắt nhau. |
| garden `borderRadius` | number, `.065` | Bán kính viền cong; áp dụng cả lawn mới, không đổi lawn chữ nhật cũ. Cây được rải trong outline. |
| grove `kind: "aged"` | enum mới; mặc định cũ vẫn `pine` | Thân già phân nhánh, ngọn lộ gỗ, tán thưa; Bích Câu g06/g07. |
| aged `trunkRadius` | number, `.025` | Bán kính thân theo tỷ lệ chiều cao cây. |
| aged `crownDensity`, `seed` | number 0–1 / integer, `.28` / `23` | Xác suất tán nhỏ ở đầu nhánh và seed tái lập; `0` hoàn toàn trụi. |
| building `facade.kind: "rectangular"` | enum mới, mặc định cũ `arched` | Cửa vuông có nẹp và ô tối; Bích Câu g04. Cửa giữa mở vật lý nếu nội thất được chọn. |
| building `roof.ridgeAxis` | `x` / `z`, `x` | Đổi hướng đầu hồi, không xoay shell; Bích Câu g04. Không đổi contract mái/ceiling. |
| building `cladding` | object / absent | Nét lớp phủ quanh shell; không thay kích thước hay biến tường thành trong suốt. |
| cladding `kind`, `course`, `width` | `stone` / `timber`, `stone`; number `.3`, `.65` | Đá xếp mạch hoặc ván ngang; Bích Câu g04, Bon g00. |
| cladding `joint`, `color`, `seed` | CSS color / CSS color / integer, stone `#c3c1b2` / `#a6a495` / `3`; timber joint `#6f5e4d` | Mạch nhỏ, phù điêu đá nông biến thiên nhẹ; không chồng thêm mặt kín trước cửa. |
| building `sideWindows` | `[side,z,y,width?,height?][]`, `[]` | side ±1, y là tâm local; mặc định `1.2×1.8`. Cửa tối và khung gỗ ở vách bên. Không tạo lối xuyên tường. |
| steps `openRisers` | boolean, `false` | Bậc gỗ hở và xương thang thay khối bậc đặc; Bích Câu g01/g04. |
| steps `rail` | object / absent | Lan can hai bên, không chặn đầu thang; có rail cũng chọn thang bậc hở. |
| steps rail `height`, `spacing`, `color` | number / number / CSS color, `.95` / `.6` / stair color | Cao tay vịn, bước con tiện, màu. Cần chiếu nghỉ và lối nối riêng đúng cao độ. |
| room `windowKind` | `arched` / `rectangular`, `arched` | Khung cảnh matte kín phía sau khung cửa; Bon g12/g13 dùng ô vuông, không lộ trời. |
| room `openSides` | boolean, `false` | Sảnh mở: bỏ cửa đặc, panel chân trời chỉ hướng vào trong, không đổ/nhận bóng, nên ngoại thất không thành hộp kín. Cửa giữa vẫn thông; camera nội thất phải nhìn dọc sảnh về vách sau, giới hạn yaw và kiểm tra kín khung hình. Chỉ dùng cho khung cột mở, không thay tường của shell masonry. Bon g12/g13. |
| room `jars` | object / absent | Cùng schema `storefront_jars`; Bon g10/g14. |
| room jars `position` | number[3], `[0,localFloorY,-depth/2+.5]` | Vị trí kệ trong local room, y là đáy kệ; tránh chồng lên camera/cửa. |
| room `pendants`, `pendantColor` | `[x,z][]` / CSS color, absent / `#b8a58a` | Chao đèn nhỏ có dây treo trần, Bon g12/g13; không tự phát sáng thay ánh sáng interior của viewer. |

Các cấu kiện mới cập nhật toàn bộ transform cha trước khi ghi envelope của instance;
không đưa điểm ở gốc tọa độ vào khung của một nhóm con đã dịch/xoay. Đường mặc định
của các type cũ giữ nguyên để bảo toàn hình Gạch.

Nội thất vẫn theo `batch/INTERIOR_RULES.md`: stop ngoài nhấc mái, stop kế tiếp đóng
mái và dùng camera cao 1.6 m; kiểm tra yaw −4°/0°/+4°. Nếu có mái che lớn bên ngoài,
đặt `interior.approach` ra ngoài mép mái để đường bay cao không xuyên tôn. Bích Câu
chỉ có hai ảnh interior nên không suy đoán thêm phòng kín.

## garden

Data-only vocabulary for flower gardens, parks and flower/strawberry farms. Load
`"kits":["garden"]`; no other kit is required. Complete runnable catalogue:
`kits/examples/garden.place.json`. Build it with
`python3 -B CODE/build.py CODE/kits/examples/garden.place.json out_garden_example/`
từ DATA, với CODE là đường dẫn thư mục script. Chạy
`node CODE/checks/test_garden_landmarks.mjs` để build/boot ví dụ và kiểm tra hồi quy.

### Shared object and boundary options

| Option | Type / default | Meaning / photo correspondence |
| --- | --- | --- |
| `id` | string, required | Unique object and framing subject identifier |
| `type` | string, required | Một trong 23 type garden bên dưới |
| `position` | `[x,y,z]`, `[0,0,0]` | Metres; base datum, not centre height; match OSM/overview |
| `rotation` | number, `0` | Y-axis rotation in degrees; local +z faces south |
| `shape` | string, `ellipse` | Boundary: `ellipse`, `rectangle`, `sector`, `polygon`; surface defaults to rectangle |
| `size` | `[width,depth]`, `[12,8]` | Boundary dimensions in metres |
| `outline` | `[x,z][]`, absent | Local polygon overrides shape/size; use measured footprints |
| `startAngle/endAngle` | number, `0/360` | Ellipse/sector angles in degrees, +x toward +z; sector includes centre |

Position/rotation apply to the whole object, including paths, instances and
walkable surfaces. Boundary options apply to surface, bed, water and shaped path.
Use `shape:polygon` with `outline`; polygons should be simple, not self-crossing.

### Object types and options

`garden_surface` — ground, lawns, polygon plazas; g21 lawn and g02 forecourt.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `color` | color, `#b8bea5` | Muted ground finish |
| `level` | number, `0.025` | Top relative to base datum; slab bottom is −0.06 m |
| `walkable` | boolean, `false` | Register real paving for route raycasts; never mark lawn just to pass a route |
| `jointSpacing` | number, `0` | Optional short slab joints; zero disables |

`garden_path` — straight/polyline paths, rings and branches; OSM footways and g19/g21.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `points` | `[x,z][]`, `[[0,0],[0,-12]]` | Local centreline |
| `legs` | `[x,z][][]`, absent | Multiple centrelines; overrides points |
| `followRoute` | boolean, `false` | Uses place.route; keep position/rotation zero when route coordinates are world-space |
| `shape` | boundary shape, absent | Creates a boundary-centred ring instead of points |
| `closed` | boolean, `false` | Connect final point to first |
| `width` | number, `3.4` | Finished pavement width |
| `level` | number, `0.075` | Top above base datum; underside −0.04 m |
| `color/jointColor` | colors, `#d7d2c5/#bdb9ab` | Paving and fine transverse joints |
| `jointSpacing` | number, `1.5` | Transverse joint interval in metres; must be positive |

`garden_bed` — patterned beds, crop rows, low drifts; g14/g15/g17/g21.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `pattern` | string, `solid` | `solid`, `rings`, `stripes`, `petals`; colours follow radial/linear/angular bands |
| `bands` | integer, `4` | Number of colour bands or angular sectors |
| `colors` | color[], dusty rose/ochre/cream/blue | Blossom palette; a one-item array makes one colour |
| `spacing` | number, `0.85` | Plant spacing with seeded positional jitter |
| `height` | number, `0.36` | Planting height, not slab height |
| `seed` | number, `1` | Deterministic variation; no random geometry between builds |
| `flowersPerPlant` | integer, `3` | Instanced flower heads per foliage mat |
| `leafColor/soilColor` | colors, `#92a080/#9caa8c` | Low foliage and visible bed substrate |
| `foliageForm` | string / absent | `foam` dùng khối lá tròn mịn cho thảm thấp QUÊ/Xuân Hương; vắng giữ lá đa diện cũ. Không tăng height để biến thảm thành cây |
| `border` | boolean, `true` | Low clipped border; false gives an unframed drift |
| `borderWidth/borderHeight` | numbers, `0.28/0.26` | Border cross-section; bottom extends to −0.03 m |
| `borderColor` | color, `#929f7c` | Clipped edging finish |

`garden_water` — lakes/ponds and circular fountains; fountain position/diameter
from OSM `469579685`, glimpse through the entrance in g02, garden context g21.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `rimWidth` | positive number, `0.45` | Perpendicular inset from each boundary edge to water, including concave polygons of either winding |
| `rimColor` | color, `#ddd7c9` | Basin/rim finish |
| `level` | number, `0.25` | Rim top; water recessed 0.08 m below it in a real ring-shaped basin |
| `color` | color, `#a5b8b4` | Opaque studio-model water, no photoreal reflections |
| `fountain` | object, absent | Omit for plain pond/lake |
| `fountain.height/tiers/radius` | number/integer/number, `3/2/1.8` | Column height, bowl count, lowest bowl radius; fine falling water rods |

Water outlines must have a simple, connected inset at the requested rim width.
Collapsed/narrow-neck, self-crossing and zero-width insets throw a descriptive
`RangeError`; reduce `rimWidth` or split the pond into independently evidenced
pieces. The catalogue includes a triangular and a clockwise concave pond, not
only axis-aligned basins. No bounding-box shrink is used for polygon rims.

`garden_arch` — foliage entrance or a light metal garden arch; g01/g02/g07.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `style` | string, `foliage` | `foliage` or `metal`; metal omits leaf cover |
| `arches` | object[], `[{}]` | Any number of openings, first carries optional sign |
| `arches[].x` | number, `0` | Local horizontal offset |
| `arches[].width/height` | numbers, `8/9` | Clear opening width and inner crown height |
| `arches[].depth/thickness` | numbers, `1.5/1.1` | Extrusion and arch band/pier thickness |
| `colors` | color[], sage/rose/light sage | Muted foliage/flower cover palette |
| `coverSpacing` | number, `0.35` | Small irregular leaf-cover spacing in metres; avoid chunky candy stripes |
| `flowerShare` | number, `0.18` | Fraction of seeded cover patches using the second colour, 0–1 |
| `sign` | string, absent | Curved name lettering, never a place-specific default |
| `signColor` | color, `#9d7569` | Letter fill with cream outline |

`garden_structure` — one builder with `gazebo/kiosk/greenhouse/glasshouse`.
Gazebo: g06; kiosk: measured OSM quầy vé. Greenhouse/glasshouse are catalogue
variants for the garden/farm family, **not evidenced at Vườn hoa**.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `kind` | string, `gazebo` | Structure variant |
| `size` | `[width,depth,eaveHeight]`, `[7,7,4]` | Dimensions; kiosk outline overrides plan |
| `outline` | `[x,z][]`, absent | Exact local kiosk slab/wall/flat-roof footprint |
| `roofRise` | number, `2` | Roof rise over eaves; kiosk has flat slab |
| `color/frameColor/roofColor/baseColor` | colors, wood/cream/muted brown/cream | Structural palette |
| `baseHeight` | number, `0.2` | Grounded platform top; eave height in size remains relative to object datum |
| `baseCourseHeight` | number, `0` | Optional fine horizontal base joints; zero disables |
| `roofLineSpacing/roofLineColor` | number/color, `0.4/#a39180` | Gazebo roof course spacing and finish; zero spacing disables |
| `sides` | integer, `6` | Gazebo roof/post count |
| `railings` | boolean, `true` | Gazebo two-bar rails; one open entry bay |
| `bays` | integer, `4` | Greenhouse/glasshouse frame divisions |
| `glassColor` | color, `#bbc9c1` (`#aab8b3` kiosk) | Studio glass |
| `opacity` | number, `0.42` | Glass shell opacity, 0–1 |
| `cropRows` | integer, `3` | Greenhouse planted trough rows; glasshouse stays open |
| `cropColors` | color[], sage/rose | Greenhouse planting palette |

Each structure registers its own roof record. No garden interior kit is
registered: this source set has zero interior photos, so do not invent an inside stop.

`garden_topiary` — clipped shrubs; g14/g15/g21.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `points` | `[x,z,height?,radius?][]`, `[[0,0]]` | Local plants with per-plant overrides |
| `form` | string, `tier` | `tier`, `ball`, `cone`, `column` |
| `height/radius` | numbers, `3/1.3` | Fallback dimensions; ball height derives from radius |
| `color` | color, `#92a080` | Clipped foliage finish |

`garden_grove` — layered sage foam trees, not cone pines; g06/g14/g19/g21.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `points` | `[x,z,height?,radius?][]`, `[[0,0,12]]` | Local tree group |
| `height` | number, `12` | Fallback tree height |
| `radius` | number, `height*0.2` | Fallback crown radius |
| `color/trunkColor` | colors, `#a3b096/#92836d` | Alternating crown and trunk palette |
| `understory` | boolean, `true` | Six low foliage masses around each trunk |

`garden_furniture` — benches or flower pots; secondary model-scale amenities.
Small plant containers are visible along g20's bed edge; sizes and placements
remain illustrative. The excluded g12 portrait/pedestal planter is not modelled.

| Option | Type / default | Meaning |
| --- | --- | --- |
| `kind` | string, `bench` | `bench` or `pot` |
| `points` | `[x,z,rotation?][]`, `[[0,0]]` | Local placement; rotation in degrees |
| `length/color` | number/color, `2.2/#887462` | Bench length and wood finish; seat 0.5 m high |
| `radius/height/potColor` | number/number/color, `0.7/0.9/#ddd7c9` | Tapered pot dimensions and finish |
| `colors` | color[], shared flower palette | Pot flowers |

### Địa hình, ruộng hoa và công viên

Các type bổ sung giữ nguyên builder và mặc định cũ. Kích thước tính bằng mét,
góc bằng độ; `position`/`rotation` vẫn áp dụng toàn object. Mặt trước điêu khắc,
cổng và nhà đón khách hướng local +z. Các mặc định là preset studio dùng chung,
không phải số đo một địa điểm. Mỗi bảng ghi đầy đủ option riêng; option biên
`outline`/`shape`/`size` ở trên cũng dùng cho `garden_field`.

#### `garden_terrain` — bờ đất và thung ruộng liên tục

Phục vụ Cẩm Tú Cầu g14/g22/g33, bờ cỏ Yersin g05. Các hàng ngang nối thành
một mặt đất: đoạn bằng là ruộng, đoạn chênh cao là bờ dốc, không phải hộp xếp.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `size` | `[width,depth]` / `[40,30]` | Bề rộng toàn mặt và chiều sâu profile mặc định |
| `profile` | `[z,y][]` / `[[-d/2,3],[-d*.25,3],[-d*.1,0],[d/2,0]]` | Tiết diện từ bắc xuống nam, z tăng nghiêm ngặt; y là đỉnh đất |
| `bend` | number / `0` | Uốn đường đồng mức theo `bend*(2*x/width)^2` |
| `crossSlope` | number / `0` | Cao độ cộng thêm trên mỗi mét x |
| `segments` | integer / `40` | Số ô theo bề ngang; tăng vừa đủ khi bờ cong |
| `bottom` | number / `-0.1` | Đáy vách kín ở rìa; phải dưới toàn profile |
| `color` | color / `#b8bea5` | Mặt ruộng/cỏ trên đoạn bằng |
| `bankColor` | color / `#b49a82` | Đất lộ ở bờ dốc và mặt cắt ngoài |
| `contourLines` | boolean / `true` | Nét mảnh tại các hàng profile |
| `lineColor` | color / `#ad947e` | Màu nét bờ đất |
| `walkable` | boolean / `false` | Chỉ bật nếu toàn mặt thực sự là lối đi |

Không đặt hai z trùng nhau để tạo vách đứng: dùng khoảng z nhỏ nhưng dương.
Chọn `bend` sao cho rìa vẫn nằm trong plinth. Cao độ là diễn giải từ ảnh, không
thay thế khảo sát. Muốn cây/lối nằm trên đất, cấp cùng profile và hệ tọa độ local.

#### `garden_field` — ruộng hoa instanced theo loài

Cẩm Tú Cầu g08/g14/g19/g25/g29/g32/g35: cẩm tú cầu có khối lá và nhiều đầu
hoa tròn mang hoa nhỏ; hướng dương có thân, lá, đầu đứng và tâm sẫm; cosmos
có thân mảnh và hoa đĩa nằm ngang. Không dùng hoa lùn chung để giả mọi loài.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `species` | enum / `hydrangea` | `hydrangea`, `sunflower`, `cosmos` |
| `shape` | string / `rectangle` | Biên mặc định; `outline` ưu tiên cao hơn |
| `spacing` | positive number / `1.05` | Khoảng cây theo x |
| `rowSpacing` | positive number / `spacing*1.12` | Khoảng hàng theo z |
| `height` | number / `1.05`, `1.65`, `.8` | Chiều cao lần lượt hydrangea/sunflower/cosmos |
| `colors` | color[] / xanh phấn–kem–tím, vàng đất, hồng phấn | Màu đầu hoa theo loài; chọn mảng không rỗng |
| `leafColor` | color / `#8d9d7e` hydrangea, `#8e9b78` khác | Màu lá và thân |
| `soilColor` | color / `#a4ae91` | Mặt nền nối theo địa hình |
| `bands` | integer / `7` | Số dải màu theo z |
| `headsPerPlant` | integer / `3` | Đầu hoa trên mỗi bụi hydrangea |
| `floretsPerHead` | integer / `3` | Hoa nhỏ trên đầu hydrangea; dùng 0–2 cho ruộng rộng, 3–6 cho mảng cận; 0 bỏ lớp hoa nhỏ |
| `headRadius` | number / `.31` hydrangea, `.24` sunflower, `.3` cosmos | Bán kính đầu hoa theo `spacing`; hướng dương tăng cả vành cánh và tâm sẫm |
| `headSegments` | `[widthSegments,heightSegments]` / `[6,3]` | Độ tròn đầu hydrangea; `[8,5]` cho mảng cận nhỏ, không áp toàn cánh đồng vì tăng tam giác |
| `castShadow` | boolean / `false` | Bật bóng riêng cho lá/đầu hoa hero khi cần; AO vẫn giữ tiếp xúc với đất khi false; thân/hoa nhỏ không đổ bóng vi mô |
| `leavesPerPlant` | nonnegative integer / `3` | Số tầng lá sunflower/cosmos, phân bố từ .22 đến .6 chiều cao; 3–5 cho luống dày, không tạo mesh riêng từng lá |
| `leafScale` | `[width,height,depth]` / `[1,1,1]` | Nhân kích thước lá mọi loài; `[2,1.2,2]` gợi tán hướng dương g08/g29; tránh tán tràn tuyến đi hoặc che đầu hoa |
| `jitter` | number / `.18` | Độ lệch vị trí theo khoảng cây/hàng |
| `seed` | integer / `1` | Lặp lại chính xác bố trí qua các build |
| `soilResolution` | positive number / `1.5` | Lưới cắt nền theo exclude/route; giảm để mép chừa trống sát polygon hơn; mặt mỗi ô thích ứng theo bờ dốc |
| `exclude` | `[x,z][][]` / `[]` | Polygon chừa trống để đặt lối đi hoặc công trình |
| `clearRoute/routeMargin` | boolean/number / `false/1.8` | Chừa hành lang quanh place.route (nửa rộng theo mét, cộng khoảng tán); chuyển route world-space về local trước khi lấy mẫu |
| `terrain` | object / `{}` (phẳng y=0) | Lấy mẫu cao độ cho nền, thân, lá và từng bụi |
| `terrain.profile` | `[z,y][]` / `[[-10,0],[10,0]]` | Cùng quy ước với `garden_terrain`; ngoài profile giữ cao độ đầu/cuối |
| `terrain.width` | number / `terrain.size[0]` hoặc `40` | Bề rộng dùng tính bend, phải khớp terrain |
| `terrain.size` | `[width,depth]` / absent | Có thể cấp width qua size thay cho `width` |
| `terrain.bend/crossSlope` | number / `0/0` | Đồng mức cong và dốc ngang như terrain |

Không giảm spacing vô hạn: hàng nghìn cây đã dùng instance, không cần mỗi cánh
là mesh riêng. `exclude`/`clearRoute` chừa cả cây lẫn nền; các ô nền cắt
bảo thủ theo lưới nên mép trống có thể rộng hơn polygon tới soilResolution.
Chừa các tuyến bằng `exclude` hoặc `clearRoute`; tránh cây xuyên đường. Profile
trong field là local: nếu dịch field, phải dịch profile tương ứng, không dán
profile world-space vào field có position khác. Không suy luận mùa hoa từ preset.
Tâm và cánh hướng dương dùng vật liệu hai mặt riêng để không biến mất ở orbit
phía sau; không đổi side của material dùng chung cho các type cũ.

#### `garden_bridge` — cầu cong với lan can và tay đá

Cẩm Tú Cầu g20/g21/g27/g31: cầu dài, cong mềm, lan can vàng mảnh và tay đá
mọc từ ruộng. Không dùng `garden_path` nâng cao vì sẽ tạo vách đặc dưới cầu.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `points` | `[x,z][]` / `[[-18,3],[-7,-2],[7,-2],[18,3]]` | Catmull–Rom centreline; ít nhất hai điểm |
| `deckHeight` | number / `4.5` | Cao độ mặt sàn trên datum |
| `rise` | number / `.35` | Độ vồng sin dọc nhịp |
| `width/thickness` | number / `3/.32` | Bề rộng mặt cầu và dày kết cấu |
| `railHeight` | number / `1.05` | Chiều cao lan can trên mặt sàn |
| `balusterSpacing` | positive number / `.85` | Khoảng thanh đứng theo chiều dài thực |
| `segments` | integer / `100` | Phân đoạn dọc sàn và tay vịn |
| `lattice` | boolean / `true` | Thanh chéo mảnh giữa các cột lan can |
| `color/railColor/jointColor` | color / `#c6b17d`, `color`, `#b09c6d` | Sàn, tay vịn và mạch sàn |
| `hands` | object[] / `[]` | Các tay đỡ độc lập; không tự đoán vị trí |
| `hands[].position/rotation` | `[x,y,z]`/number / `[0,0,0]/0` | Gốc và góc bàn tay trong hệ local của cầu |
| `hands[].height/width` | number / `7/height*.72` | Chiều cao và ngang khối tay |
| `hands[].color/lineColor` | color / `#c0c1b3/#969d8d` | Đá và nét khớp ngón/lòng tay |

Tay có cổ, lòng, bốn ngón cong và ngón cái riêng; quay mặt local +z về phía
nhìn. Đặt lòng tay ôm sàn, không chặn lối hay để tay nổi. Không tự tạo tuyến
tham quan lên cầu nếu ảnh chưa xác nhận lối tiếp cận.

#### `garden_stairs` — bậc đất hoặc bậc trời công xôn

Yersin g05 dùng `ground`; Cẩm Tú Cầu g18/g26/g34 dùng `sky` có khoảng không
dưới bậc và hai xương đỡ, không có khối đặc xuống nền. Bậc lên theo local −z.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `kind` | enum / `ground` | `ground` hoặc `sky` |
| `steps/rise/tread` | integer/number/number / `16/.28/.6` | Số bậc, cao mỗi bậc và sâu mặt bậc |
| `width/taper` | number / `3.6/0` | Ngang bậc đầu, phần thu hẹp đến bậc cuối (0–<1) |
| `thickness` | number / `.14` | Dày bậc sky; ground có riser kín |
| `stringerRadius` | number / `.09` | Bán kính xương sky |
| `landing` | number / `0` | Sâu chiếu nghỉ phía trên; 0 không tạo |
| `color/frameColor/jointColor` | color / `#e4e0d4`, `color`, `#c4c1b4` | Bậc, xương và nét mép bậc |
| `walkable` | boolean / `true` | Đưa mặt bậc vào raycast; sky chụp ảnh nên đặt false |

Tổng cao là `steps*rise`; gắn bờ đất và chiếu nghỉ đúng cao độ trong JSON.
Không để tuyến đi xuyên sky stair hay qua bờ đất chưa có bậc.

#### `garden_platform` — sàn quan sát một trụ

Cẩm Tú Cầu g11/g17: sàn đỏ không mái, một cột cao, giằng đỡ dưới sàn.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `size` | `[width,depth]` / `[5,4]` | Mặt sàn chữ nhật |
| `height/poleRadius` | number / `7/.25` | Cao sàn và bán kính trụ |
| `railHeight` | number / `1.05` | Lan can hai thanh ngang và thanh đứng |
| `color` | color / `#a86f62` | Đỏ đất dịu cho toàn kết cấu |

Gốc position là chân trụ, không phải mặt sàn. Không thêm mái gazebo hay thang
không có trong ảnh. Mặt sàn có raycast nhưng không tự nối route.

#### `garden_swing` — cổng gỗ và ghế treo

Cẩm Tú Cầu g00/g03: hai cột gỗ, đà ngang, dây treo, ghế ván và biển chữ.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `width/height/postRadius` | number / `5.4/4.3/.15` | Rộng hai cột, cao khung và tiết diện tròn |
| `seatWidth/seatHeight` | number / `width*.67/.55` | Dài ghế và cao mặt ghế |
| `back` | boolean / `true` | Hai thanh tựa sau ghế |
| `color/ropeColor` | color / `#8a7762/#b9ae94` | Gỗ và dây treo |
| `sign` | string / absent | Chữ biển; không tạo nếu không cấp |
| `signColor` | color / `#e3dcc7` | Chữ sáng trên bảng gỗ |

Ghế treo là vật cản thật: đặt route vòng qua bên, không đi xuyên giữa ghế.

#### `garden_sculpture` — phù điêu, tượng và bệ

Yersin g00/g04/g06/g10: khối đá góc cạnh trên bệ sẫm, gương mặt chạm nổi có
trán, hốc mắt, mũi, ria, râu nhọn, nếp áo; trừu tượng studio, không phải ảnh dán.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `kind` | enum / `relief` | `relief`, `statue`, `plinth`, `hand` |
| `size` | `[width,height,depth]` / `[6,4,1.5]` | Khối đá/tượng; height chưa gồm bệ |
| `plinthHeight/plinthScale` | number / `.7/1.04` | Cao bệ và hệ số ngang; chiều sâu bệ bằng 1.12 depth |
| `color/plinthColor` | color / `#c7bfa6/#636d66` | Đá và bệ |
| `faceWidth` | number / `.25` | Bán ngang mặt theo width |
| `reliefDepth` | number / `.64` | Độ nhô cơ sở của gương mặt |
| `highlightColor/shadowColor/lineColor` | color / `#d3cbb4/#9a9784/#afa78f` | Các mặt đá và nét đục |
| `height/width` | number / `7/height*.72` | Riêng kind hand: thay cho size, giống hands của bridge |
| `lineColor` (hand) | color / `#969d8d` | Nét khớp tay |

`hand` không tạo bệ; position/rotation đặt trực tiếp trên toàn object. `statue`
là người đứng trung tính trên bệ; `relief` là preset chân dung có râu, không
được dùng để khẳng định nhận dạng nhân vật thiếu ảnh. `plinth` chỉ có bệ.
Không phóng riêng mũi/mắt thành chi tiết rời như đồ chơi; giữ tương quan khối đá.

#### `garden_conifer` — thông, bách và tường cây

Yersin g00/g08/g11/g14: thân mảnh, tán nón nhiều tầng và chùm lá nhỏ, thay
cho hình nón trơn ở những cảnh cần độ chi tiết cao. Type topiary cũ giữ nguyên.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `form` | enum / `pine` | `pine`, `cypress`, `wall` |
| `points` | `[x,z,height?,radius?,baseY?][]` / `[[0,0]]` | Cây/hàng cây, có override cao độ chân cây trên bờ |
| `height/radius` | number / `9/1.7` | Cao và bán kính tán cơ sở |
| `texture` | boolean / `true` | Chùm lá instanced quanh từng tầng |
| `color/tipColor/trunkColor` | color / `#8c9e85/#9eac92/#8b826e` | Tán, tán xen kẽ và thân |

`wall` là các khối cắt bo tròn liên tiếp; đặt gần nhau để khép kín, không nhét
qua bậc/lối. Chân cây trên bank phải dùng baseY đúng, không tự raycast đo đất.

#### `garden_shelter` — nhà kính nông trại, mái nhọn đón khách

Cẩm Tú Cầu g01/g02/g08/g14/g33: nhà đón khách khung kim loại, mái kính nhọn;
nhà nhựa dài mái vòm hoặc răng cưa ở mép ruộng. Mỗi nhà đăng ký roof record.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `kind` | enum / `greenhouse` | `greenhouse` kín hoặc `shed` có cổng mở |
| `roof` | enum / `arched` | `arched`, `sawtooth`, `gable` |
| `size` | `[width,depth,eaveHeight]` / `[10,24,3]` | Ngang, dài và cao mép mái |
| `roofRise` | number / `2` | Vồng/đỉnh mái trên mép |
| `bays` | positive integer / `ceil(depth/3)` | Số nhịp khung dọc nhà |
| `frameRadius` | number / `.035` | Bán kính thanh mái; cột vuông cạnh gấp đôi |
| `frameColor/glassColor/baseColor` | color / `#9aa69b/#c9cec2/#d7d2c5` | Khung, tấm mái/nhựa và nền |
| `opacity` | number / `.8` | Độ kín tấm mái 0–1; opaque matte phù hợp overview |
| `wallColor` | color / `#8fa0a0` | Vách shed; mảng cạnh cửa mặc định `#889c9e` |
| `openingWidth` | number / `width*.65` | Cửa shed mở ở +z |
| `sign/signColor` | string/color / absent, `#e2ddcc` | Chữ biển trên cửa shed |
| `cropRows` | nonnegative integer / `0` | Hàng trồng thấp bên trong; không dùng cho nhà đón khách |

Không dùng opacity thấp cho cả cụm nhà để tránh chồng trong suốt mất khối.
`shed` vẫn là mái che ngoại thất, không phải interior kit. Chỉ dựng nội thất khi
đủ ít nhất bốn ảnh nội thất đúng công trình theo `batch/INTERIOR_RULES.md`.

#### Option mới trên type hiện có

| Type / option | Kiểu / mặc định | Ý nghĩa / ảnh / bẫy |
| --- | --- | --- |
| `garden_path.kerbWidth` | number / `0` | Rộng kerb đá, Yersin g08/g11; 0 giữ builder cũ nếu không có terrain/tileRows |
| `garden_path.kerbHeight` | number / `.18` | Cao kerb trên mặt lát, không phải chiều cao nền |
| `garden_path.kerbColor` | color / `#b8b8a7` | Đá viền dịu |
| `garden_path.tileRows` | integer / `1` | Chia mạch dọc lối; kết hợp jointSpacing cho lưới lát |
| `garden_path.terrain` | object / absent | Cao độ theo cùng contract terrain của field; chân lối phải khớp đất |
| `garden_furniture.kind` | enum / `bench` | Thêm `lamp`; bench/pot giữ nguyên |
| `garden_furniture.height` (lamp) | number / `4.2` | Cột vườn nhỏ, Yersin g09/g15; không thêm đèn đường khổng lồ |
| `garden_furniture.frameColor/glassColor` (lamp) | color / `#797d70/#e2decb` | Thân/chụp và ô đèn; không tự tạo nguồn sáng ban ngày |

Nhánh path mới dùng `points`, `legs`, `followRoute`, `closed`, `width`, `level`,
`jointSpacing`, `color`, `jointColor` với mặc định như bảng cũ; `shape`/`size`/
`outline` tạo vòng lát khi `closed:true`. Các góc nối miter giữ mặt lát kín,
không đặt kerb cắt ngang lối. Nền thích ứng theo chỗ đổi dốc (sai số 6 mm);
mạch lát là linework. Đoạn quá ngoặt cần đủ rộng cho tuyến đi đã bo góc.

### Công trình vườn và vật thể nhận diện

Các nhánh mới chỉ bật khi JSON chọn đúng type/option; mặc định 18 type cũ giữ
nguyên hình học, màu và transform (checksum trong `checks/test_garden_landmarks.mjs`).
Ví dụ có đủ biến thể; test build và boot ví dụ trong DATA. Không dùng tên địa điểm
trong builder. `position`/`rotation` theo quy ước chung; phần lặp được instance hoặc
gộp theo vật liệu. Không đăng ký tour nội thất từ những vật thể ngoại thất này.

#### `garden_windmill` — cối xay Hà Lan bốn cánh nan

Xuân Hương g00/g01/g08/g14: thân tháp thuôn, nẹp sáng, mái chóp, cửa và nan cánh.
Không nhân đôi tháp chỉ để thể hiện hai màu chụp ở thời điểm khác nhau.

| Option | Kiểu / mặc định | Ý nghĩa / bẫy |
| --- | --- | --- |
| `height/radius/topRadius` | number / `9/2/radius*.48` | Cao thân, bán kính chân/đỉnh; chưa gồm mái và cánh |
| `sides/roofRise` | integer/number / `8/1.4` | 8 cạnh hoặc 32 cho tròn; cao mái trên thân |
| `hubHeight/sailLength/sailWidth` | number / `height*.88/height*.59/sailLength*.18` | Cao hub, bán kính cánh, ngang dải nan; không phải đường kính rotor |
| `sailAngle` | degrees / `45` | Pha quay bốn cánh trong mặt phẳng local xy, hướng +z |
| `gallery/galleryHeight` | boolean/number / `false/height*.36` | Sàn vòng có lan can; chỉ bật khi có bằng chứng |
| `color/trimColor/roofColor` | color / `#ae655e/#e2ddcc/#756b62` | Thân, nẹp và nan, mái |
| `hubColor/openingColor` | color / `roofColor/#697971` | Trục và ô cửa tối, không dán ảnh |
| `courseSpacing/lineColor` | number/color / `.24/#995d57` | Bước vạch ngang và màu nét; spacing phải dương |

#### `garden_turbine` — turbine ba cánh

Euro Garden Cầu Đất g03/g11/g15: cột trắng thuôn, nacelle ngang và cánh dài mảnh.
Không dùng kiosk hoặc path giả cánh. Tổng cao có thể vượt height một bladeLength.

| Option | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `height/mastRadius/bladeLength` | number / `60/height*.022/height*.45` | Cao tâm rotor, bán kính chân cột, dài cánh; height tới 80 m |
| `bladeAngle` | degrees / `15` | Pha rotor ba cánh |
| `color/hubColor/baseColor` | color / `#deded3/#c5c9c0/#b9b9aa` | Cột/cánh, nacelle, chân đế |

#### `garden_bridge.style: "glass"` — cầu kính treo

Đồi Mộng Mơ g11/g13: kính xanh nhạt, tay vịn trắng, hai cổng trụ và cáp võng.
`style` mặc định vắng: giữ cầu cong vàng cũ. Chỉ nhánh glass dùng bảng dưới;
không dùng `points/deckHeight/rise/hands/lattice` của cầu cũ trong nhánh này.

| Option | Kiểu / mặc định | Ý nghĩa / bẫy |
| --- | --- | --- |
| `ends` | `[x,y,z][2]` / `[[-15,3,0],[15,3,0]]` | Hai đầu sàn local; khác x/z, có thể khác cao độ |
| `width/sag/thickness` | number / `2.4/.65/.12` | Rộng sàn, độ võng giữa nhịp, hạ xương cạnh dưới kính |
| `railHeight/segments` | number/integer / `1.2/48` | Cao tay vịn, phân đoạn sàn; segments ≥2 |
| `towerHeight/towerRadius/footY` | number / `5/.13/0` | Trụ cao trên đầu cầu, bán kính và cao chân trụ |
| `cableRadius` | number / `.055` | Bán kính cáp chính; dây treo mảnh hơn |
| `frameColor/railColor/glassColor` | color / `#a2ada7/#dedfd4/#aec5c6` | Xương/cáp, lan can, kính matte nhạt |
| `opacity` | number / `.72` | Độ kín kính; raycast vẫn dùng đúng sàn kể cả khi trong suốt |

Sàn đăng ký walkable sau transform; bố trí chiếu nghỉ đúng y của mỗi end.
Không nối route xuyên khoảng trống hoặc suy ra nối liền các cụm ảnh chưa xác nhận.

#### `garden_arch` — chuỗi cổng và canopy

Đồi Mộng Mơ g14: cổng tim phủ hoa; Vạn Thành g06/g13/g15: ô/chong chóng treo.
Không cấp các option kích hoạt dưới đây thì `arches` và sign cũ giữ nguyên.

| Option | Kiểu / mặc định | Ý nghĩa / bẫy |
| --- | --- | --- |
| `outline` (nhánh cổng) | string / absent | `"heart"` bật tim; không phải polygon của surface |
| `repeat/pitch` | integer/number / absent (`5` khi bật nhánh)/`2.7` | Số khung và bước về local −z; repeat >0 bật cổng tròn lặp |
| `width/height/thickness` | number / `4/4.6/.18` | Ngang, cao toàn khung, bán kính thanh phủ lá |
| `style` | enum / `foliage` | `metal` bỏ lá/hoa, không đổi outline |
| `frameColor/colors` | color/color[] / `#c2bc9f` / `[#8c9c7d,#b68c9d,#d6c9b5]` | Khung và lá/hoa; mảng màu phải không rỗng |
| `coverSpacing/flowerShare` | number / `.17/.35` | Bước phủ và tỷ lệ hoa, chỉ nhánh chuỗi |
| `canopy` | enum / absent | `umbrella` hoặc `pinwheel`; ưu tiên hơn outline, thay khung bằng giàn cột và vật nhỏ treo |
| `rows/elementRadius` | integer/number / `3/.42` | Số vật ngang mỗi giàn và bán kính ô/chong chóng |

Nhánh chuỗi không dùng `arches/sign`; lát path riêng dưới cổng. Cột canopy nằm
hai mép, không đặt hàng giữa tuyến đi. Màu nhỏ dịu, tránh ô lớn che hết vườn.
Lớp lá sage liên tục và hoa nhỏ riêng được instance hai mặt; không chia màu
thành sọc lớn. Chân tim mở hai bên, không có thanh nhọn cắt qua lối đi.

#### `garden_conifer.form: "cloud"` — niwaki/bonsai

QUÊ g03/g09/g24/g26, Hoàng Long g07/g13: thân uốn, cành ngang, từng đệm lá dẹt.
Form mặc định vẫn `pine`; `points` và baseY dùng như conifer cũ.

| Option | Kiểu / mặc định | Ý nghĩa / bẫy |
| --- | --- | --- |
| `height/radius/padLevels` | number/integer / `5/2.2/5` | Cao cây, độ vươn cành, số tầng đệm; dùng 1–8 m tùy ảnh |
| `twist/texture` | number/boolean / `.23/true` | Độ uốn theo chiều cao; các chùm kim nhỏ instanced |
| `color/tipColor/trunkColor` | color / `#839276/#97a488/#887a65` | Đệm lá, đầu sáng, thân/cành |
| `pot` | boolean / `false` | Chậu dưới datum cây; position.y là mặt chậu, không phải đáy |
| `potHeight/potRadius/potColor` | number/number/color / `H*.16/R*.65/#a59680` | Chậu thuôn; H/R lấy override tại từng point |

#### `garden_rockery`, `garden_koi_pond` — đá lớn và hồ cảnh

QUÊ g07/g13/g18/g22/g27: đá đứng, đá tròn viền hồ, thác nhỏ và cá koi.
Không phải builder hồ vùng hay thác cảnh quan lớn của nature.

| Type / option | Kiểu / mặc định | Ý nghĩa / bẫy |
| --- | --- | --- |
| rockery `rocks` | `[x,z,radius,height,baseY?,depthRadius?][]` / `[[-2,0,1.8,2],[1,0,1.4,3.5],[0,2,1.6,1.2]]` | Đá nhóm instanced; baseY=0, depthRadius=radius*.8 |
| rockery `color/seed` | color/integer / `#999481/1` | Màu đá, pha quay; một phần đá sáng `#aaa18e` |
| koi `size/shape/outline` | boundary / `[12,8]/ellipse/absent` | Viền hồ polygon hoặc ellipse như boundary chung |
| koi `level/color` | number/color / `.18/#839c93` | Cao mặt nước, nước matte; không walkable |
| koi `rockColor/rockSpacing/rockRadius` | color/number/number / `#999481/1.5/.8` | Màu, bước và cỡ đá viền; không phải rim bê tông liên tục |
| koi `seed/koi/koiColors` | integer/integer/color[] / `1/16/[#c18b60,#ddd7c4,#a96d5e]` | Pha đá/cá, số ứng viên cá và màu; cá ngoài outline bị bỏ |
| koi `waterfall` | object / absent | Thác đá nhỏ; không cấp thì không có |
| `waterfall.position` | `[x,z]` / `[0,-(size[1] hoặc 8)/2]` | Đầu thác trong hệ local hồ |
| `waterfall.height/width/depth/tiers` | number/integer / `2.8/3.5/2.4/3` | Cao, ngang, vươn xuống hồ, số bậc; tiers >0 |
| `waterfall.color` | color / `#cfdbd3` | Nước đổ và nét sáng `#e3e7da` |
| koi `steppingStones` | `[x,z,radius?][]` / `[]` | Đá bước walkable, radius=.65; mặt level+.16 |
| koi `stoneColor` | color / `#bfb6a0` | Màu đá bước; nối đủ gần nếu dùng cho route |

#### `garden_sculpture.kind: "liberty" / "bust" / "clay"`

Vạn Thành g11/g17: hình người áo dài giơ đuốc; Euro g06: đầu tượng lớn;
Đường Hầm g09/g10/g13: đôi đầu nhìn nhau, g00/g08: đất nung chạm khắc.
`kind` mặc định vẫn `relief`; không đổi các preset cũ. Không nhận dạng chân dung
hay tạo texture ảnh; mặt là khối trán, mắt lõm, mũi và miệng studio.

| Option | Kiểu / mặc định (chỉ kind mới) | Ý nghĩa / bẫy |
| --- | --- | --- |
| `size` | `[width,height,depth]` / `[4,8,3]` | Thân/tượng chưa gồm bệ; liberty height là đỉnh đuốc |
| `plinthHeight/plinthScale/plinthColor` | number/number/color / `.7/1.04/#8e8d7b` | Bệ; liberty dùng bệ cao theo ảnh, không phóng to đầu |
| `color` | color / `#a5b1a0`, clay `#a56f53` | Đá xanh dịu hoặc terracotta |
| `highlightColor/shadowColor/lineColor` | color / `color/#767d70/shadowColor` | Mặt sáng, hốc và nét khắc |
| `torchColor` | color / `#c5ad78` | Ngọn đuốc liberty hoặc clay đứng |
| `figure` | enum / absent | Riêng clay: `standing` chọn người áo dài giơ tay; mặc định đầu tượng |

#### `garden_clay_tunnel` — hành lang đất nung và cổng vòm dày

Đường Hầm g00/g08: lối thấp giữa vách đất đỏ dày; các đầu vòm và dải phù điêu
làm đường hầm đọc được từ overview. Mặc định hở trời như ảnh; `roofed` chỉ bật
khi có bằng chứng mái vòm kín. Không dùng khối terrain để giả lối đi xuyên tường.

| Option | Kiểu / mặc định | Ý nghĩa / bẫy |
| --- | --- | --- |
| `kind` | string / absent | Vắng dựng hành lang; `wall` dựng vách nhiều cửa vòm xuyên thật, như cổng đất nung Đường Hầm |
| `size` | `[width,height,length]` / `[7,5,18]` | Ngang ngoài, cao vách, dài theo local z |
| `wallThickness/roofed` | number/boolean / `1.25/false` | Dày vách và mái barrel vault tùy chọn; width >2*thickness |
| `floorLevel/floorColor` | number/color / `.08/#c5ac89` | Sàn bên trong walkable; hai đầu mở, không tự nối route |
| `bays` | positive integer / `4` | Số mảng relief mỗi bên, không phải số cổng chặn hành lang |
| `color/reliefColor` | color / `#a46f52/#ba8764` | Đất nung, relief và ba dải khắc trên vách |
| `sign/signColor` | string/color / absent / `#dfc5a1` | Biển đầu +z; không tự thêm tên địa điểm |

Height phải lớn hơn width/2 để vòm có chân. Các đầu vòm rỗng thật, sàn được
transform vào walkable; nhánh roofed không có tour nội thất. Tường không có
lối ngang xuyên qua: đặt cửa/đầu hành lang theo đúng hướng ảnh và route.

Riêng `kind:"wall"`: `size:[width,height,thickness]` mặc định `[18,6,1.7]`,
`openings:3`, `openingWidth:width/(openings*1.65)`, `springHeight:height*.48`.
Các kích thước phải chừa trụ và đỉnh vòm trong vách; cửa không được chồng nhau.
Màu `color/reliefColor/floorColor` như hành lang; mỗi cửa có ngưỡng walkable
cao `.06`. Nhánh wall không dùng `roofed`, `bays`, `floorLevel` hay `sign`.
Các kích thước, bước lặp và số phần tử mới được kiểm tra trước khi tạo mesh;
không dùng số âm hoặc khoảng cách 0 để tắt chi tiết.

### Pitfalls and limits

- Use OSM `main` by meaning: here it is a ticket kiosk, not a large visitor hall.
- Preserve x east / z south consistently; a sign error in ribbon rotation crossed a real route.
- Flower triangles must face up; leaf mats must sit below blossoms.
- Walkable geometry must be non-indexed before the template merges it. Every route
  leg needs visible paving, including turns and arrow width, not just a lawn fallback.
- Large flat sites need enough overview depth precision: Vườn hoa uses the
  existing `site.overviewNear:2` camera option so a 6 cm lawn/subgrade gap does not
  flicker at 300+ m viewing distance. Close hotspot cameras retain template defaults.
- Vegetation and repeated frame/joint geometry are instanced; ordinary meshes are
  merged per material in each object. Envelope bounds include actual instances.
- Nested pot instances must update ancestor world matrices before capturing
  envelopes; the catalogue exercises translated and rotated furniture roots.
- Gazebo cone vertices, rafters and roof courses share the same angular phase;
  rotate unit cone geometry before applying unequal width/depth scaling.
- Các type cũ giữ datum phẳng. Ruộng dốc dùng `garden_terrain`, `garden_field`
  và path có `terrain`; không ghép slab cao để thay bờ đất liên tục.
- Paths, camera choices, cropping extent, colours, planting layouts, measured
  footprints and exclusions belong in `place.json`, not branches in the kit.

## church

Kit nhà thờ/nhà nguyện: `kits: ["church"]`; ví dụ chạy được ở
`kits/examples/church.place.json`. Mọi kích thước là mét, `position` là datum
chân công trình, `rotation` là độ quanh Y; mặt tiền quay về local **+z**.
Không suy kích thước/hướng từ tên địa điểm. Số liệu trong ví dụ là minh họa.

### Chọn loại

| Type | Dùng cho mẫu ảnh | Lưu ý |
| --- | --- | --- |
| `church_aframe` | Khung gỗ, mái sát đất và hiên chữ A Cam Ly | Giữ preset cũ; không dùng để ép mặt tiền xây gạch. `size: [width, depth]`. |
| `church_basilica` | Basilique Pháp, tháp chuông, gian cánh, hậu cung Con Gà | `size: [width, depth]` là nave giữa; `nave.aisleWidth` cộng hai bên. `tower`, `transept`, `apse` điều khiển từng khối. |
| `church_gabled` | Mái dốc, tường đầu hồi xây, Thánh Tâm/Mai Anh; nhà nguyện hiện đại/gothic | Ghép nave, mặt tiền, mặt sau, dormer và buttress; không kèm sân/thang tự động. |
| `church_facade` | Mặt tiền xây độc lập hoặc khối phụ | Cùng schema với `church_gabled.facade`; đặt chính xác z, không chồng hai mặt tường. |
| `church_stairs` | Hai thang hẹp sát đầu hồi Mai Anh; thang cong trắng Thánh Tâm | Một flight mỗi object, đường Bézier trong x/z; không phải bậc xòe hình quạt. |
| `church_forecourt` | Podium, bậc thẳng rộng và sân hoa văn Thánh Tâm | Podium ở đầu **−z** của sân; thang đi xuống theo +z. |
| `parish_arcade` | Veranda vòm nhọn 2–4 tầng hoặc tu viện nhiều dormer | `size: [width, depth]`; khác `parish_house` dùng `[width,height,depth]`. |
| `church_shrine` | Tượng trong vòng oval đứng hoặc tượng trên sân tròn | `ring: false` để chỉ dùng tượng/sân. Không tạo ảnh/nhãn tôn giáo giả. |

Các type cũ vẫn dùng được: `church_plaza` (podium/bậc cong),
`church_monument` (tượng trên cột), `church_benches` (ghế sân),
`parish_house` (nhà thấp), `bell_frame`, `marian_grotto` (hang đá có tượng),
`garden_statue`, `camly_gate`, `parish_ground`, `parish_path`, `parish_walkway`,
`parish_bed`, `parish_planting`, `parish_grove`, `formal_garden`, `parish_playground`.

### Mái và nave

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `church_aframe.roofColor` | color / `#705348` | Màu cả mái chính và hiên; kem/xám cho ảnh mái sáng, không còn bắt buộc nâu. Bỏ trống giữ đúng Cam Ly. |
| `church_aframe.porchRoofColor` | color / `roofColor` | Ghi đè riêng mái hiên; không nhuộm khung gỗ. |
| `church_gabled.size` | `[width,depth]` / bắt buộc | Kích thước nave; không bao gồm dormer, buttress, thang, ban công. |
| `eaveHeight`, `ridgeHeight` | number / `3`, `eaveHeight+width*.9` | Cao mép mái/đỉnh mái; đặt theo tỷ lệ ảnh, ridge phải cao hơn eave. |
| `baseHeight`, `baseColor` | number, color / `.18`, `#b9b4a6` | Sàn/bệ đặc từ datum lên `baseHeight`; nền dưới công trình phải đỡ đúng datum. |
| `wallColor`, `trimColor` | color / `#e5dfcf`, `#e6dfcf` | Tường chính và gờ; matte, màu giảm bão hòa. |
| `roofColor` | color / `#817d72` | Tôn/ngói/mái shingle theo JSON, không phụ thuộc tên nhà thờ. |
| `roofEdgeColor`, `roofCourseColor` | color / `trimColor`, `#989489` | Viền/ridge và nét lớp mái; g00 Thánh Tâm, g15 Mai Anh. Tránh nét quá tương phản. |
| `sideBands` | `{from,to,color}[]` / một dải từ sàn đến eave | Màu tường từng cao độ trên hai hông. Các dải phải nối nhau, không chồng hoặc để hở; đá dưới/hồng trên Mai Anh g21. |
| `sideWindows` | object hoặc `false` / `{}` | Cửa vòm nhọn dọc hai hông; là panel trang trí kín, không phải lỗ nhìn xuyên. |
| `sideWindows.count,y,width,height,color` | number/color / `7,1.4,1.1,2,#89958c` | Nhịp, chân, rộng, cao, kính; `spacing` mặc định `(depth-4)/count`. Không đặt cửa ngoài wall band. |
| `facade`, `rear` | object / `{}` | Cấu hình mặt trước/sau theo bảng bên dưới; kế thừa rộng/eave/ridge/màu nave. Mặt sau mặc định không cross. |
| `dormers` | object / không có | Cửa mái g15/g16 Mai Anh; bảng dormer dùng chung bên dưới. |
| `buttresses` | object / không có | Trụ chống đá g16/g21 Mai Anh; không tự bật khi thiếu bằng chứng. |
| `buttresses.count,height,width,projection` | number / `7,eaveHeight,.7,1` | Số mỗi hông, cao, dày dọc nave, nhô ra; `spacing` mặc định `(depth-2)/count`. |
| `buttresses.color,capColor,jointColor` | color / `#b9b4a6,trimColor,#8d8c80` | Đá, mũ trụ và nét mạch đá. Tránh đặt vào cửa hoặc tuyến đi bộ. |

### Mặt tiền xây (`church_facade`, `church_gabled.facade`/`rear`)

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `width,eaveHeight,ridgeHeight` | number / `18,3,20` | Contour tường chữ nhật + tam giác kín. Trong nave kế thừa kích thước nave. |
| `wallColor,trimColor,edgeWidth` | color/color/number / `#e5dfcf,#e6dfcf,.095` | Tường, nẹp gable và bán kính nẹp; không dùng lattice khung gỗ cho ảnh tường xây. |
| `bands` | `{from,to,color}[]` / `[]` | Ghi đè màu theo cao độ, phần còn lại dùng `wallColor`; dưới đỏ/trên hồng Mai Anh g01/g06/g17. Không chồng dải. Lỗ vòm được cắt qua từng dải. |
| `arches` | object[] / `[]` | N vòm nhọn tùy biến: ba vòm Thánh Tâm g00/g15 hoặc một portal Mai Anh g06. Mỗi vòm phải nằm hoàn toàn trong contour. |
| `arches[].x,y,width,height` | number / `0,0,bắt buộc,bắt buộc` | Tâm ngang, chân vòm, rộng, cao; đỉnh vòm nhọn thật, không phải vòm tròn. |
| `arches[].trimWidth,trimColor` | number/color / `.16,trimColor` | Bề dày viền và màu riêng vòm. |
| `arches[].glassColor,glassPalette,leadColor` | color/color[]/color / `#8d9b98`, bảng muted nội bộ, `#626e68` | Kính, điểm nhấn hình thoi, nét chì; kính ở trên cửa Thánh Tâm g06. |
| `arches[].leaded` | boolean / `true` | Tắt với portal tối/không kính màu Mai Anh. |
| `arches[].doorHeight,doorColor` | number/color / không cửa, `#574b40` | Cửa dưới kính; chia nan thật. Chiều cao cửa phải thấp hơn phần kính. |
| `rose` | object / không có | Cửa hoa hồng Mai Anh g06/g17; contour tường có lỗ thật. |
| `rose.x,y,radius,petals,trimWidth,glassColor` | number/color / `0,bắt buộc,bắt buộc,8,.065,#9aa8a1` | Tâm, cao độ, bán kính, cánh, nét, kính. Đảm bảo cả vòng nằm trong gable. |
| `lancets` | object / không có | Cụm ba cửa nhỏ g22 Mai Anh. Panel phủ tường, không phải cửa đi. |
| `lancets.centres,y,count,width,height,spacing,color` | number[]/number/color / `[0],bắt buộc,3,.45,1.8,.8,#8a7971` | Mỗi tâm tạo một cụm; số và spacing cho phép nhiều biến thể chapel/gothic. |
| `balcony` | object / không có | Hộp ban công nhô ra trên cửa nhỏ Mai Anh g01/g17; có sàn, ba parapet, gờ, console. |
| `balcony.y,width,depth,parapetHeight,color` | number/color / `4.3,3.4,1.8,1.05,wallColor` | Cao độ mặt sàn, rộng, độ nhô, lan can đặc, màu. Ghép đầu thang sát sàn. |
| `balcony.doorWidth,doorHeight,doorColor` | number/color / `1.2,2.5,#574b40` | Cửa dưới có lỗ xuyên wall và móc điều khiển camera; upper portal khai báo riêng trong `arches`. |
| `cross` | object hoặc `false` / `{}` | Thánh giá đỉnh; `height,width,arm` mặc định `1,.13,.65`. Không tự thêm biểu tượng nếu ảnh không có. |

### Thang và sân

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `church_stairs.points` | `[x,z][3]` / `[[0,5],[0,2],[0,0]]` | Chân, control, đầu trên của Bézier. Hai thang Mai Anh là hai object đối xứng; không đổi dấu height. |
| `width,height,bottom,steps` | number / `1.5,4.3,0,24` | Rộng flight, chênh cao, cao chân, số bậc. Chiều dài đường phải đủ cho bậc thật. Mỗi tread đăng ký walkable. |
| `color,railColor,capColor,railHeight` | color/number / `#ae7b68,#e6dfcf,#e6dfcf,.8` | Bậc, hai parapet, tay vịn và chiều cao parapet. `railHeight:0` vẫn giữ gờ mảnh; không dùng để tạo thang hoàn toàn không gờ. |
| `church_forecourt.size,color` | `[w,d]`, color / `[22,15],#d9d2c1` | Sân phẳng ở datum, cao `.08`; phần bệ không tự đỡ nave bên ngoài footprint của sân. |
| `pattern.spacing,color,jointColor` | number/color / `1.2,#bba99a,#bdb5a7` | Ô lát, hình thoi matte và đường mạch: Thánh Tâm g00/g15. Các ô hình thoi được instancing. |
| `podium.width,depth,height,color` | number/color / `sân.width,3,1.2,sân.color` | Bệ tại cạnh −z. Không có object `podium` thì không tạo bệ/thang. |
| `stairs.width,depth,steps,color` | number/color / `sân.width-.8,3,8,sân.color` | Thang thẳng rộng đi xuống từ bệ theo +z; kiểm tra cuối flight nằm trong sân. |

### Khối giáo xứ / tu viện và dormer

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `parish_arcade.size,storeys,storeyHeight,bays` | `[w,d]`, number / bắt buộc, `3,3.6,6` | Nhịp veranda xếp tầng g04/g13 Thánh Tâm hoặc cửa sổ tu viện g02/g12 Mai Anh. Tổng cao = số tầng × chiều cao tầng. |
| `veranda` | boolean / `true` | `true`: vòm nhọn có chiều sâu/lan can; `false`: tường đặc với cửa sổ và shutters từng tầng. |
| `windowStyle` | `pointed` hoặc `rectangular` / `pointed` | Cửa hai đầu và cửa hông khối đặc; chọn `rectangular` cho tu viện g02/g12 Mai Anh. Không đổi hình vòm arcade mở; cửa mỗi đầu luôn quay ra ngoài. |
| `wallColor,trimColor,baseColor` | color / `#e1d4be,#e6dfcf,#b9b4a6` | Màu tường, gờ/sàn, bệ. |
| `windowColor,shutterColor` | color / `#7d8880` (veranda), `#7c8983` (đặc), `#7e786b` | Kính và cửa chớp; ảnh tu viện Mai Anh g10/g12. Không tạo portraits khi không có ảnh nguồn. |
| `roofColor,roofCourseColor,roofRise` | color/number / `#8c8174,#a99b88,2.6` | Mái chính; nhịp mái nhỏ khai báo riêng. |
| `roofGables,gableRise` | integer/number / không có, `2.1` | Hàng đầu hồi nhỏ hai hông Thánh Tâm g04/g13, không phải dormer tách rời. |
| `externalStair` | object / không có | Flight cong ngoài tới veranda tầng kế; g13 Thánh Tâm. |
| `externalStair.side,z,height,width,steps,color,railColor` | number/color / `1,depth/2-1,storeyHeight,1.6,24,#aba99e,trimColor` | Bên +x/−x, vị trí dọc, cao, rộng, số bậc, bậc, parapet. |
| `externalStair.points` | `[x,z][3]` / tự bố trí theo side/z | Ghi đè đường thang để nối chính xác landing; mọi điểm ở local block, không world-space. |
| `porch` | object / không có | Gable cổng giữa tu viện Mai Anh g02/g12. `side,z,width,height`: `-1,0,4.4,4`; dùng +1 ở mặt kia. |
| `dormers` | object / không có | Cùng schema cho `parish_arcade` và `church_gabled`; g02/g10/g12 tu viện, g16 nave. Cùng roof group để cutaway đi theo mái. |
| `dormers.count,width,height,projection,spacing,sides` | number/number[] / `5,1.8,1.8,1.8,(depth-4)/count,[-1,1]` | Mỗi hông có `count` cửa; kiểm projection nhỏ hơn nửa rộng và bay không chồng. Màu kế thừa tường/mái. |

### Tượng / vòng oval

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `church_shrine.pavingRadius,pavingColor` | number/color / `3.2,#d4ccba` | Sân tròn có nét lát và walkable: tượng Thánh Tâm g01. Không chồng với sân cùng cao độ. |
| `plinthHeight,plinthWidth,plinthColor,statueScale` | number/color / `.8,1.5,#b9b4a6,1.4` | Bệ và tỷ lệ tượng; figure cơ bản cao `1.98` m trước scale. |
| `pose,statueColor,veilColor` | `prayer` hoặc `open`, color / `prayer,#dedccf,#ccd1c5` | Tay chắp hoặc mở nhẹ, áo và veil của tượng đứng; g01 so với g02 Thánh Tâm. Không dùng figure tay ngang như thánh giá. |
| `halo,haloColor` | boolean/color / `false,#b7ad8d` | Vòng hào quang mảnh; chỉ bật khi thấy trong ảnh. |
| `ring` | object hoặc `false` / `{}` | Vòng oval đứng Thánh Tâm g02/g12/g20; không phải bồn oval nằm ngang. |
| `ring.width,height,thickness,depth,bottom,z` | number / `3.8,6,.22,.22,.2,-.4` | Kích thước ngoài, bề rộng và chiều sâu viền, cao chân, lùi sau tượng. `thickness` nhỏ hơn bán trục ngắn. |
| `ring.color,lineColor` | color / `#e6dfcf,#89978e` | Màu viền và nét kép; không tự tạo chữ khắc không có bằng chứng. |

### Nội thất và hiệu năng

`interior.kit: "church_nave"` giữ nguyên contract Cam Ly/Con Gà:
`pews` (rows/startZ/spacing/width/aisleWidth/color/frameColor), `altar`
(z/width/crucifixX/crucifixZ), `timber`
(trussSpacing/tieEvery/tieHeights/boardSpacing), `entry`, `approach`, `lights`.
Với `church_gabled`, trần gỗ lấy đúng eave/ridge của nave, cửa thấp dưới ban công
được trả về làm cửa camera; mặt trước và tường hông có lớp fade riêng cho cutaway,
không làm trong suốt vật liệu khối khác.

| Option nội thất | Kiểu / mặc định | Ý nghĩa và điểm cần tránh |
| --- | --- | --- |
| `sanctuary` | object / không có | Hốc hậu cung nhọn, nền kem và gờ nổi g26/g27 Mai Anh. Không tự thêm khi không có ảnh. |
| `sanctuary.width,height,z` | number / `nave.width-3,12,-depth/2+.6` | Rộng/cao/vị trí local; `altar.crucifixZ` phải ở trước mặt hốc (+z), không bị panel che. |
| `sanctuary.color,trimColor,lineColor` | color / `#ddd2b4,#ece1c6,#b8ae95` | Mặt hốc, gờ, nét vòm bên trong. |
| `gallery` | object / không có | Gác phía cửa vào g28 Mai Anh, có sàn, lan can và hai trụ đỡ. |
| `gallery.height,depth,z,color` | number/color / `5.3,2.8,depth/2-gallery.depth/2-.25,#e6dfcf` | Cao sàn, độ sâu, vị trí local z và màu; giữ hành lang camera dưới sàn thoáng. |

Chỉ thêm nội thất mới khi đủ bằng chứng; ngưỡng và ba yaw xem
`batch/INTERIOR_RULES.md`. Nội thất đã có vẫn phải giữ trần kín khi vào, mái nâng ở
stop ngoài và hạ khi vào. Không dùng kiểu vault basilica cho nave không có `nave/apse`.

Chi tiết lặp veranda/cửa sổ/dormer được gộp theo material trong đúng assembly,
không kéo geometry khỏi roof group. Hoa, cây bụi và ô lát dùng instancing.
`parish_planting` tránh footprint các type mới, sân, vòng tượng và các điểm thang;
vẫn cần bố trí bồn/cây và kiểm ảnh để đường cong giữa các điểm không lấn cây.
Đế, tỷ lệ, hướng nhìn, cây thấp lấp khoảng trống, route và số đo riêng địa điểm
luôn ở JSON; không có nhánh theo slug hay tên giáo phận.

## villa

Kit `villa` dựng biệt thự, resort cottage, dinh thự Pháp và khách sạn lớn bằng
JSON; không có nhánh theo tên địa điểm. Ví dụ chạy được:
`kits/examples/villa.place.json`. Kiểm chứng: `test_villa_extension.mjs`,
`test_villa_places.mjs`, `test_villa_regression.mjs`, `test_cadasa.mjs`,
`test_dinh3.mjs`, `test_villa_compat.mjs`.

### Quy ước và tương thích

Kích thước tính bằng mét; `rotation` tính bằng radian quanh +Y; mặt tiền local
+Z. `id` là string bắt buộc, duy nhất. `position` là `[x,y,z]`, mặc định
`[0,0,0]` cho các type mới. Cottage/hotel/court/sign-wall tự bám terrain,
`position[1]` là độ nâng thêm; water/terrace/pool dùng Y tuyệt đối để mặt nước
và deck luôn ngang. Không dùng lawn màu xanh thay hồ. Outline là polygon local
`[x,z][]`; không trộn với tọa độ world của camera/entry/lights.
`site.hill.profile` phải xếp Z **giảm dần** theo contract viewer; xếp ngược sẽ
làm đồi thành mặt cao và chôn hồ/deck. Y mặt nước phải cao hơn terrain/lawn
trên toàn polygon; kit không tự đào hồ hay nâng nước theo từng đỉnh.
Với góc cận cottage, biển tên, court hoặc terrace, đặt `hotspot.frameRoute:false`
(boolean; mặc định viewer là true) nếu đoạn đầu tuyến từ stop trước kéo camera
ra quá xa. Giữ `subjects` trỏ đúng envelope cần xem; không tăng kích thước đồ
nội thất để bù lỗi framing. Overview vẫn dùng `site.overviewSubjects/frameFill`.

Các nhánh `villa` hiện hữu (hip/gable/flat), `villa_lounge`, `villa_drive`,
`villa_lawn`, `villa_flowerbed`, `villa_garden`, `villa_pergola`, `villa_urns`,
`villa_sign`, `villa_grove`, `villa_furniture` giữ hành vi Cadasa/Dinh III.
`villa.roof.pitch` cũ là **độ**, không phải radian. Cottage mới nên dùng
`roof.rise` (mét); `villa.roof.kind: aframe/steep_gable` cũng gọi builder cottage.
Khách sạn Pháp dùng `villa_hotel`, không dùng nhánh mái legacy để giả mansard.

### `villa_cottage` và mái A-frame

Wonder g03/g05/g06/g14: thân trắng thấp, đầu hồi cao, hai mái gần đứng,
ống khói đá dài và hông đá. Mỗi cottage có một roof record riêng.

| Trường | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `footprint`, `wallHeight` | `[w,d]` / `[7.5,10]`; number / `2.7` | Rộng/sâu và cao mép mái; không dùng tổng chiều cao làm wallHeight. |
| `wallColor`, `trimColor`, `stoneColor` | color / `#ece9de`, `#e4e0d1`, `#939084` | Vữa, viền trắng, đá xám lì; g03/g05. |
| `roof.kind` | `aframe/steep_gable` / `aframe` | Ridge chạy local Z, đầu hồi nhìn ra +Z. |
| `roof.rise`, `roof.height`, `roof.pitch` | number / `6.6`, absent, absent | Thứ tự ưu tiên rise → height → pitch (độ, tính từ rộng mái) → 6.6 m; không truyền pitch=1.5 với ý nghĩa radian. |
| `roof.color`, `overhang`, `courseSpacing` | color/number/number / `#6a716e`, `.38`, `.42` | Ngói tối, diềm mái và nét lớp ngói; tránh nét quá dày. |
| `stoneWall` | object/false / `{}` | Hông đá, tắt bằng false khi ảnh không có. |
| `stoneWall.side`, `color` | `-1/1`, color / `1`, stoneColor | Chọn hông −X/+X; không đổi hướng ridge. |
| `chimney` | object/false / `{}` | Khối đá thật từ nền đến chóp, có mũ và miệng khói. |
| `chimney.height,x,z,width,depth,color` | number/color / `wallHeight+rise+.65`, `.45w`, `-.2d`, `.85`, `1`, stoneColor | Cao tổng từ sàn, vị trí và tiết diện; g05/g06. Không đặt quá xa mái. |
| `path` | object/false / absent | Lối phiến đá bám dốc trước cửa; g03/g14. |
| `path.length,width,stepLength,gap,color` | number/color / `5`, `1.15`, `.6`, `.25`, `#c5c2af` | Khoảng cách từ đầu đường tới cuối đường; khe cỏ thật giữa phiến. |
| `path.start,end` | `[x,z]` / `[0,d/2+.4]`, `[0,d/2+.4+length]` | Điểm local; có thể nối chính xác đường resort. |
| `sign` | object/false / absent | Biển tên sẫm hai trụ gỗ ở đầu lối; không phải bảng đá lớn. |
| `sign.text,x,z,rotation` | string/number / `VILLA`, `.55w`, `d/2+3`, `-.2` | Tên do JSON cung cấp, vị trí và hướng local. |

### `villa_cluster`

Wonder g04/g12: nhiều cottage nhỏ rải theo sườn đồi, không phải một dãy nhà
liền. Mỗi căn có envelope riêng (`ids[i]` hoặc `id-01`, `id-02`…), cả cụm cũng
có envelope theo `id`; chọn envelope con để chụp biển/lối đá cận cảnh.

| Trường | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `count,seed,area` | integer/integer/`[w,d]` / `6`, `1`, `[36,36]` | Rải có lưới giãn và jitter xác định, không dùng Math.random. Phải để khoảng cách lớn hơn footprint + lối đá. |
| `positions` | `[x,z,yaw?][]` / absent | Ghi đè count và vị trí sinh tự động; x/z/yaw local trong cụm. Dùng khi ảnh cho bố cục rõ. |
| `ids,names` | string[] / sinh theo id, `VILLA 01…` | Id envelope và chữ biển riêng từng cottage; không bịa tên nhà thật. |
| `cottage` | object / `{}` | Toàn bộ tùy chọn cottage chung, không chứa position/id riêng. |
| `path,sign` | object/false / `{}`, `{}` | Cụm mặc định có lối đá/biển cho mọi căn; cùng schema cottage. `sign.prefix` string mặc định `VILLA`. |

### `villa_hotel`

Golden Sun g00/g07/g08: 4–5 tầng, mansard tối, dormer, nhịp cột/phào,
lan can Pháp mảnh và mái hiên đỏ trầm. Dùng nhiều block cho các cánh khác cao;
không thêm tầng hay dormer khi ảnh không có bằng chứng.

| Trường | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `footprint,outline` | `[w,d]` / `[32,18]`; `[x,z][]` / chữ nhật | Polygon thực và kích thước fallback; nhận được vertex cuối trùng đầu nhưng nên bỏ. |
| `storeys,storeyHeight` | integer/number / `4`, `3.8` | Chiều cao đến chân mansard = tích hai trường, không gồm rise. |
| `wallColor,trimColor,railColor` | color / `#e9e6da`, `#f0ecdf`, `#657065` | Vữa, phào và kim loại mảnh. |
| `facade` | object / `{}` | Nhịp facade theo từng cạnh polygon. |
| `facade.frontEdges` | integer[] / `[2]` | Cạnh mặt tiền cho awning và dormer mặc định; đánh số theo outline, không theo world. |
| `facade.bayWidth,windowWidth,windowHeight` | number / `3.4`, `min(1.8,.6*baySpacing)`, `2.45` | Khoảng nhịp được làm tròn theo cạnh; cửa phải nhỏ hơn nhịp và cao tầng. |
| `facade.pilasters,balconies,awnings` | boolean / `true,true,true` | Tắt độc lập cho resort block giản dị; awning chỉ ở tầng trệt/cạnh frontEdges. |
| `facade.awningColor` | color / `#a46960` | Vải đỏ gạch lì, g00/g08; không dùng khối villa mỏng để giả awning. |
| `roof` | object / `{}` | Mansard polygon, tất cả dormer thuộc roof group để cutaway đồng bộ. |
| `roof.kind,rise,inset,color` | string/number/number/color / `mansard`, `3.6`, `1.7`, `#68716c` | Đỉnh phẳng thụt vào, sườn dốc thật; inset phải nhỏ hơn nửa span hẹp nhất, tránh polygon shoulder tự giao. |
| `roof.seamSpacing,seamColor` | number/color / `.7`, `#92998e` | Nét slate mảnh trên sườn mái. |
| `roof.capSeams,capSeamSpacing,capSeamColor` | boolean/number/color / `true,1.1,#81897f` | Seam mảnh trên nắp mái phẳng như phần mái tối g00/g08; instance cắt theo polygon vai mái, không chạy qua khoảng khuyết. Dùng false để bỏ; spacing tối thiểu .2 m, tương phản thấp. |
| `roof.dormerEdges,dormerSpacing,dormerCount` | integer[]/number/integer / frontEdges, `4.7`, absent | Count nếu có áp dụng trên từng cạnh; không đẩy cửa vào góc nhọn. |
| `roof.dormerWidth,dormerHeight` | number / `1.55,1.8` | Khung trắng có đầu hồi nhỏ; g07. |
| `porch` | object / `{}` | Mái đón giữa cửa, cột và bậc thật, envelope `id-entrance`. |
| `porch.edge,at,width,depth,height,text` | number/string / frontEdges[0], `.5`, `7`, `3.7`, `3.6`, absent | at là phân số 0–1 dọc cạnh; cửa shell và porch dùng cùng tâm. Không đặt column trên đường camera. |
| `interior` | object / absent | Dùng `kit: villa_hotel_lounge`; doorway lấy doorWidth/doorHeight `2.8/3`. Có room thì khai báo `size:[w,H,d]` của building cho camera/light viewer. |

### `villa_water`, `villa_terrace`, `villa_pool`

Wonder g09/g13/g15/g16: mặt hồ nằm ngang, bờ thật, sân gỗ có bàn/ô và hồ bơi
mép tràn. `position[1]` tuyệt đối: đặt trên vùng terrain thấp, không để terrain
chọc qua nước; level không thay cao độ địa hình.

| Type / trường | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| water `size,outline` | `[w,d]` / `[24,18]`; polygon / ellipse 64 đỉnh | Shoreline kín local; không phải contoured lawn. |
| water `level,color` | number/color / `0`, `#a2b6ad` | Nâng mặt nước so với root; màu nước đục studio, không cần shader phản xạ. |
| water `shoreline,shoreWidth,shoreColor` | boolean/number/color / `true,.22,#b5b5a0` | Bờ thấp theo polygon; tắt nếu nối với mảng nước khác. |
| water `ripples,seed,rippleColor` | integer/integer/color / `24,3,#c6d2c5` | Nét sóng được clip vào shoreline; giảm để giữ mặt hồ yên. |
| terrace `size,thickness,color,plankWidth` | `[w,d]`/number/color/number / `[16,10],.24,#b4a28b,.38` | Deck ngang, mặt walkable; tránh dùng Y terrain-varying cho nhà hàng sát hồ. |
| terrace `tables` | `[x,z,yaw?][]` / `[[-4,-1],[0,-1],[4,-1]]` | Vị trí cụm bàn và ghế local. |
| terrace `umbrellas,umbrellaRadius,umbrellaHeight,umbrellaColor` | boolean/number/number/color / `true,1.9,2.8,#e7e2cf` | Ô bát giác có pole và nan mảnh; g09. Khoảng bàn > đường kính ô. |
| terrace/court `chairs,furnitureColor,tableColor` | integer/color/color / `4,#817967,#d1c9b6` | Ghế/bàn café tỷ lệ thật; không scale cả mô hình chỉ để đồ dễ thấy. |
| terrace `rails` | boolean / `false` | Lan can hai cạnh dài khi ảnh có; không chắn tầm nhìn hồ. |
| terrace `supports,supportSpacing,supportColor` | boolean/number/color / `true,4,#9f9d8d` | Trụ dưới deck kéo tới terrain thật; tắt khi deck đã nằm trên một công trình có sẵn. |
| pool `size,deck,depth,color,deckColor` | `[w,d]`/number/number/color/color / `[18,9],2,.8,#9bbab6,#b7a48c` | Basin, mặt nước, deck walkable, coping và rãnh tràn thật. |
| pool `infinitySide` | `-1/1` / `1` | Cạnh local −Z/+Z mở, có mặt nước tràn thẳng đứng; quay object để hướng ra hồ. |

### `villa_court`, `villa_sign_wall` và vườn

Golden Sun g03–g06/g08: `villa_drive` với `surface: stone`, `linear: false`
cho lối cong; ghế/đèn dùng `villa_furniture` (`benches:[x,z,yaw][]`,
`lamps:[x,z][]`, `position:[0,0,0]`). `villa_garden` không formal có
`hydrangeas` (integer, mặc định 12), `shrubs` (8), `hedge` (false), `shape`
(ellipse; rectangle/ribbon/organic) và `size:[w,0,d]`; formal dùng
`planting:{layout:drift,spacing:.46}` để phủ đất dày. Không trồng vào lối đá.

| Type / trường | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| court `size,tileSize,color,accentColor` | `[w,d]`/number/color/color / `[12,16],1.1,#cfcec3,#aeb3aa` | Sân marble có mạch kín, mặt walkable; g05/g06. Y root bám terrain nhưng sân phải đặt trên vùng phẳng. |
| court `tables,umbrellas` | `[x,z,yaw?][]`/boolean / `[[-3,3],[3,3]],false` | Cùng schema terrace; sân bên khách sạn không tự thêm ô. |
| court `bonsai` | object/false / `{}` | Chậu lớn, thân cong và cloud tán; g05. |
| bonsai `position,height,potColor` | `[x,y,z]`/number/color / `[0,0,0],3.2,#777e70` | Tọa độ local court; tránh trùng bàn/camera. |
| bonsai `spread,potRadius` | number/number / `3.4,.85` | Độ trải ngang tán khoảng mét và bán kính miệng chậu; g05/g06 có bonsai lớn, tán rộng thấp. Không scale cả cây theo spread: chiều cao giữ độc lập. Chừa khoảng trống cho ghế bên dưới mép tán. |
| sign-wall `width,height,curve,depth,color` | number/color / `7,1.25,.85,.45,#d0cdbb` | Tường parabol bằng đá, curve là độ phồng +Z; g08. |
| sign-wall `crown,lines,tabletColor,textColor` | boolean/string[]/color/color / `true,[VILLA],#566257,#dbd5ba` | Đầu cong nhô giữa, bảng chữ riêng; không bịa tên ngoài JSON. |

### `villa_hotel_lounge`

Golden Sun g10–g18: tường kem chia ô, piano đen nắp mở, bàn tròn thấp, ghế
bành bọc sáng và bar gương lì. Không tái dùng altar của nội thất dinh thự.

| Trường trong `interior` | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và điểm cần tránh |
| --- | --- | --- |
| `kit,size,offset,rotation` | string/`[w,H,d]`/`[x,y,z]`/number / `villa_hotel_lounge,[12,3.8,12],[0,0,0],0` | Room local với yaw thêm, hỗ trợ facade xiên; trần thuộc roof và nằm đúng cao độ H. |
| `doorWidth,doorHeight` | number / `2.8,3` | Cửa room đồng tâm facade/porch; đưa camera qua đúng cửa. |
| `wallColor,timberColor,trimColor,upholsteryColor,rugColor` | color / `#e7e0d0,#786b57,#f0e8d7,#d9cfb8,#b29a8b` | Vật liệu trầm, không vàng bóng hoặc gương trắng chói. |
| `windows` | number[] / `[-.28d,.08d]` | Vị trí Z cửa hai hông, có rèm và chia kính. |
| `seating` | object[] / hai cụm tại `[-2.6,0,1]`, `[2.6,0,1]`, 3 ghế/cụm | Mỗi cụm: position `[x,y,z]`, chairs integer mặc định3, angles radian[] tùy chọn, tableRadius number `.6`, rug `[w,d]` `[3.6,3.3]`. Ghế cao ~.95m, mặt bàn .57m; giữ thông trục cửa. |
| `seating[].tableStyle,rugPattern` | `"shelf"\|"pedestal"`/boolean / `"shelf",true` | Bàn tròn hai mặt như g10/g12; hoặc một trụ. Họa tiết thảm muted và viền kép như g12/g17, instance nhỏ; false giữ thảm trơn. Tránh đặt cụm ghế vào đường glide. |
| `piano.position,rotation,color,lidAngle` | `[x,y,z]`/number/color/number / `[-.31w,0,-.22d],.3,#41443f,.5` | Piano có thân cong, nắp mở hai mặt, bàn phím trắng/đen và ghế; g12/g13/g15. Hai góc dùng radian; keyboard ở local −Z, xoay hướng đó về camera nếu muốn thấy phím. Nắp không biến mất khi nhìn từ dưới. |
| `bar.position,width` | `[x,y,z]`/number / `[0,0,-d/2+.7],.62w` | Tủ, mặt bàn, chai/ly và gương chia khung; g10/g13. |
| `entry,approach,floorY,lights` | world vectors/number/object / theo viewer | Bắt buộc author theo cửa thật; eye = floorY+1.6. `lights:{altar,fill}` là tên API viewer, không thêm bàn thờ. |
| `boundsCenter,boundsDepth,safeApproach,dimmingSize` | world vector/number/boolean/`[w,d]` / theo viewer | Khai báo vùng room và đường glide; chụp cutaway ngoài, bên trong và yaw −4/0/+4, không hở trời. |

Các mảng đá, ngói, cây, hoa, lát dùng instancing hoặc gộp theo material; không
thêm JavaScript riêng cho place. Envelope, roof record và walkable cap được
đăng ký tại builder. Nét mảnh vẫn giữ trong assembly; không gộp trần vào facade.
