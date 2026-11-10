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

