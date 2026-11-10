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
