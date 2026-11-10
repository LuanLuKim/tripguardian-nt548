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

