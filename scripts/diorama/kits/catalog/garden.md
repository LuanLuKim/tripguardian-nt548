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
| `type` | string, required | Một trong các type garden bên dưới |
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

### `garden_letters` — chữ khối đứng rời

Chữ đùn 3D có lỗ rỗng thật, mép bevel nhỏ, mặt trước local +z. Bảng glyph
nhúng trong kit, không tải font hoặc dùng ảnh chữ; phù hợp LANGBIANG g00/g19/
g20/g24/g31 và biển tên giữa vườn hoa. Ví dụ có LANGBIANG nhiều màu và
«Thung Lũng Tình Yêu»; kiểm thử `checks/test_garden_letters.mjs` build/boot.

| Option | Kiểu / mặc định | Ý nghĩa, mẫu ảnh và bẫy |
| --- | --- | --- |
| `text` | string / `"GARDEN"` | A–Z, 0–9, khoảng trắng, ♥, Đ và dấu tiếng Việt; chữ thường dùng glyph hoa thu nhỏ 78%. Ký tự lạ là khoảng trống, không gây lỗi. Không tự ngắt dòng |
| `height` | positive number / `3` | Chiều cao chữ hoa, mét; dấu trên có thể cao hơn. Chọn đủ lớn để đọc từ overview như LANGBIANG g20/g31 |
| `letterHeights` | positive number[] / `[1]` | Chu kỳ hệ số cao từng chữ có glyph, giữ nguyên chiều ngang; hai chữ A cao nổi bật ở LANGBIANG g19/g20. Không dùng mảng rỗng hoặc giá trị ≤0 |
| `depth` | positive number / `.45` | Độ dày khối; giữ tỷ lệ thật, không biến chữ thành tấm mỏng |
| `spacing` | nonnegative number / `.16` | Khoảng cách giữa advance chữ, mét; dấu nghiêng/bevel có thể vượt advance nên cần chừa khe |
| `colors` | color[] / `["#fff4dc"]` | Chu kỳ theo chữ có glyph, không tính khoảng trắng; g19/g20 có trắng, xanh, vàng, đỏ, hồng. Không dùng mảng rỗng |
| `font` | enum / `rounded` | `rounded` bevel mềm nhỏ, `block` bevel nhỏ hơn; không đổi bộ glyph hoặc tải font |
| `arc` | finite number / `0` | Bán kính cong, mét; 0 thẳng, bán kính dương đưa hai đầu về +z và quay mặt chữ theo cung. Dùng bán kính lớn so với chiều dài biển; âm đảo hướng cong |
| `tilt` | finite number / `0` | Biên jitter nghiêng từng chữ quanh z, độ; seed cố định, chân khối vẫn chạm đất. Gợi nhịp chữ LANGBIANG; tránh nghiêng quá mức làm chữ chồng nhau |
| `plinth` | enum / `none` | `none` chữ chạm đất, `bar` bệ liên tục theo cung, `stones` đế nhỏ rời từng chữ; không tự tạo đường đi |
| `plinthHeight/plinthColor` | number/color / `.16/#a79c83` | Cao và màu bệ; bệ thấp chỉ dùng khi ảnh có bằng chứng |
| `outline` | boolean hoặc color / `false` | Lớp khối viền lưng mỏng tối, true dùng `#445344`; không phải polygon biên. Tránh viền đậm dày lấn màu chữ |
| `terrain` | object / `{}` | Cùng profile `[z,y][]`, `width`, `bend`, `crossSlope` của garden_field; lấy mẫu chân từng chữ trong tọa độ local, cộng `position.y`; không tự raycast sang terrain của object khác |
| `position/rotation/id` | option chung | Đặt datum, hướng mặt biển và subject tour; dấu và chữ đều được đưa vào envelope world-space, mesh cùng màu được gộp |

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

