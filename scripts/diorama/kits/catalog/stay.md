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

