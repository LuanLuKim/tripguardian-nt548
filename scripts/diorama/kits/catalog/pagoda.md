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

