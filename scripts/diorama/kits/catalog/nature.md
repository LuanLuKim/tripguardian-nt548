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
| `vehicleScale` | number / `1` | Chỉ cáp: phóng cabin và thanh treo (cabin thật 1,2 × 1,35 m). Ở khu rộng ~100 m cabin thật chỉ vài điểm ảnh ở overview; 2–3 cho tuyến đọc được (Cáp Treo Đà Lạt g14/g17/g19). |
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

