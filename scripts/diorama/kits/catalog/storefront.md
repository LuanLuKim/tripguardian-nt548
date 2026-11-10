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

