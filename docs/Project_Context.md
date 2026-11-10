# TripGuardian — Project Context

Tài liệu này trả lời *vì sao* và *cho ai*. Luồng hệ thống: `docs/ARCHITECTURE.md`; màn hình theo vai trò: `docs/Role_Web_Functional_Design.md`; brief thiết kế: `docs/UX_Design_Brief.md`; dữ liệu địa điểm: `docs/CORPUS.md`.

## 1. Tóm tắt dự án

TripGuardian giúp người dùng **chọn đúng địa điểm trước khi tạo lịch trình**, phạm vi kiểm chứng ban đầu là Đà Lạt. Người dùng có thể bắt đầu từ một ý tưởng mơ hồ, một số nơi đã lưu (TikTok, Facebook, Google Maps…), vài nơi nhất định muốn đi, hoặc một lịch sơ bộ cần kiểm tra.

Hệ thống: (1) hiểu nhu cầu và ràng buộc của chuyến, bắt đầu từ User Profile nếu được phép; (2) tìm và kiểm tra nơi phù hợp; (3) loại hoặc cảnh báo lựa chọn không khả thi; (4) giúp so sánh và chọn; (5) kiểm tra tổ hợp đã chọn; (6) xếp lịch khả thi và giải thích đánh đổi.

TripGuardian không phải "AI tạo lịch trình". Giá trị nằm ở ba câu hỏi:

> Nơi nào hợp với chuyến này? Vì sao chọn nơi đó thay vì nơi khác? Các nơi đã chọn có thật sự đi được cùng nhau không?

## 2. Vấn đề: nhiều thông tin, khó ra quyết định

Người đi du lịch không thiếu gợi ý; khó là biến gợi ý rời rạc thành một chuyến đi thật. Họ phải tự kiểm nơi còn hoạt động không; đối chiếu giờ, giá, vị trí, thời gian đi; đánh giá độ hợp với gu và người đi cùng; nhận ra nơi trùng trải nghiệm; quyết định giữ / bỏ; kiểm tra mọi lựa chọn có vừa thời gian và ngân sách. Đây là bài toán **ra quyết định dưới nhiều ràng buộc**, không chỉ tìm địa điểm hay tối ưu tuyến. Nhiều phương án hơn có thể làm khó quyết định hơn và dễ hối tiếc hơn [1].

## 3. Người dùng mục tiêu

Người **tự lên kế hoạch chuyến tự túc**. MVP ưu tiên: chuyến 2–4 ngày; cá nhân, cặp đôi, nhóm nhỏ; tự chọn điểm đến và hoạt động; đi xe máy, ô tô, taxi hoặc gọi xe; phải tự tổng hợp từ nhiều nguồn. Người dùng được mô tả bằng **hai trục độc lập**, không bằng nhóm người.

### 3.1. Hai trục

```text
Trạng thái bắt đầu  (có sẵn trong input)          → luồng bắt đầu từ đâu
Mức dẫn dắt         (suy từ hành vi trong phiên)  → cách hệ thống hỏi và giải thích
```

Trạng thái bắt đầu đọc được từ thứ người dùng gõ / dán nên không cần hỏi. Mức dẫn dắt không thấy được ở lượt đầu nên khởi động từ mặc định chung rồi chỉnh theo từng lượt. Không trục nào trực tiếp quyết định địa điểm.

### 3.2. Trạng thái bắt đầu

| Trạng thái | Ví dụ | Luồng |
|---|---|---|
| Chưa có ý tưởng rõ | "Đi Đà Lạt 3 ngày với người yêu, chưa biết đi đâu." | Khám phá → thu hẹp → giải thích → kiểm khả thi |
| Có nơi đã lưu | "Lưu 15 chỗ trên TikTok, không biết chọn chỗ nào." | Nhóm và kiểm danh sách → thu hẹp |
| Có nơi bắt buộc | "Chắc chắn quay lại Hồ Tuyền Lâm, tìm thêm vài chỗ mới." | Xác nhận anchor → tìm quanh anchor → kiểm tra |
| Có lịch sơ bộ | "Đã lên 8 nơi cho 3 ngày, kiểm tra giúp." | Kiểm khả thi → so sánh → tối ưu → xử lý xung đột |

Mọi trạng thái vào cùng một ô nhập; hệ thống tự phân loại. Người dùng đổi luồng lúc nào cũng được; lối tắt "tôi đã có danh sách, kiểm tra giúp" luôn hiện.

### 3.3. Mức dẫn dắt

| Tham số | Tín hiệu | Điều chỉnh |
|---|---|---|
| `guidance` | độ dài câu trả lời; có tự nêu tiêu chí; bấm chip hay gõ; gọi tên khu vực | chip / gợi ý sẵn hay câu mở; độ dài giải thích; hỏi cách dùng hay hỏi thẳng tiêu chí |
| `effort_budget` | tỉ lệ `Không chắc` / `Bỏ qua`; trả lời cụt; đòi xem gợi ý trước | số lượt hỏi còn lại; lúc chuyển sang đề xuất và học qua phản hồi |
| `control` | sửa bản hiểu nhu cầu; critique đề xuất; chỉnh từng tiêu chí | độ chi tiết tùy chỉnh; hiện tiêu chí chỉnh tay hay chỉ kết quả |

Mặc định: `guidance` trung–cao, `effort_budget` 3–5 lượt, `control` trung. Giải thích thừa thì bỏ qua được, thiếu thì chuyến hỏng, nên mặc định nghiêng về dẫn dắt nhiều, bù bằng progressive disclosure (trả lời ngắn trước, "vì sao" mở khi cần). Cuối phiên ba tham số ghi vào Behavioral Defaults (§6.2) làm điểm khởi động phiên sau.

### 3.4. Thuộc tính đổi kết quả

Phải biết hoặc đánh dấu `unknown` trước khi tìm địa điểm:

| Thuộc tính | Ảnh hưởng |
|---|---|
| Số ngày, ngày cụ thể | sức chứa, thời tiết, cuối tuần |
| Đi với ai, số người | nhịp độ, giờ kết thúc ngày, hoạt động tối, ngân sách |
| Phương tiện | bán kính khả thi, rủi ro mưa và đèo |
| Nơi lưu trú | neo khoảng cách cả chuyến |
| Ràng buộc thể chất | loại cứng |

Từng đến Đà Lạt hay chưa không đổi cách hỏi; chỉ khi người dùng nêu nơi đã đi thì nơi đó thành `visited` cho novelty (§6.2). Không suy đoán tuổi, giới tính hay đặc điểm cá nhân để đổi đề xuất hay cách hỏi.

## 4. Vì sao Đà Lạt

Khảo sát Traveloka × YouGov (gần 12.000 người, chín thị trường châu Á–Thái Bình Dương), nhóm Việt Nam: 53% dùng mạng xã hội để tìm điểm đến mới, 41% hỏi bạn bè / người thân, 41% đọc website / blog; khi lập kế hoạch 47% dùng mạng xã hội, 35% nền tảng du lịch, 32% Google Maps / Waze / Grab [2]. Mỗi nguồn giỏi một việc (mạng xã hội để khám phá, Maps cho vị trí và đường, review cho trải nghiệm, trang chính thức cho vận hành), người dùng vẫn phải tự nối chúng thành quyết định.

Trải nghiệm ở Đà Lạt rải nhiều khu; mùa đông khách, giao thông và lượng người đổi hẳn tính khả thi của lịch [3], [4]. Vì vậy khoảng cách, thời gian và điều kiện đi phải vào ngay từ **bước chọn địa điểm**, không đợi tới khi danh sách đã chốt.

## 5. Nhu cầu cốt lõi

Người dùng không cần thêm một danh sách. Họ cần: giảm công sức nghiên cứu; giảm rủi ro chọn sai; thu hẹp lựa chọn; hiểu đánh đổi (vì sao A hợp hơn B); kiểm tra khả thi; **giữ quyền quyết định**; có phương án thay khi kế hoạch không khả thi. Trọng số đổi theo trạng thái bắt đầu (§3.2):

| | Chưa có ý tưởng | Đã lưu nơi | Có nơi bắt buộc | Có lịch sơ bộ |
|---|---|---|---|---|
| Khám phá địa điểm | Cao | Trung bình | Trung bình | Thấp |
| Thu hẹp lựa chọn | Trung bình | Cao | Trung bình | Thấp |
| So sánh | Cao | Cao | Trung bình | Trung bình |
| Kiểm danh sách có sẵn | Thấp | Cao | Trung bình | Cao |
| Kiểm khả thi | Cao | Cao | Cao | Cao |
| Tối ưu, xử lý xung đột | Thấp | Trung bình | Cao | Cao |

## 6. User Profile và cá nhân hóa

Nếu người dùng cho phép, hệ thống dựng **User Profile** từ tín hiệu hành vi để làm điểm xuất phát, không bắt mô tả lại sở thích từ đầu. Profile cho biết: thường chọn kiểu trải nghiệm nào, gần đây quan tâm gì, đã trải nghiệm gì, cái gì có thể mới với họ, thói quen đi chơi. Profile chỉ là **prior**, không phải sự thật về người dùng và không thay constraint của chuyến hiện tại.

### 6.1. Nguồn dữ liệu

| Nguồn | Giá trị | Ma sát | Khi nào xin |
|---|---|---|---|
| Link tự dán cho chuyến này | anchor trực tiếp và gu ngầm (6 link đều là quán cà phê view đồi → gu rõ) | không | ngay trong ô nhập |
| Google Maps Saved Places | nơi có ý định trải nghiệm | trung bình | sau đề xuất đầu tiên |
| Google Maps Timeline (lát cắt du lịch) | `visited` cho novelty; `pace`, `max_leg_min` đo từ hành vi | cao | khi người dùng nói đã đi mà quên đi đâu |
| TikTok saved / favorites | Recent Interests, Exploration Gap | cao | ngoài phạm vi MVP |
| Chuyến TripGuardian trước | lựa chọn và trải nghiệm đã có | không | tự có |
| Thao tác trong TripGuardian | add, remove, lock, compare, replace | không | tự có |

Tín hiệu bên ngoài chỉ đến qua file người dùng chủ động tạo (Google Takeout, file Timeline xuất từ điện thoại, "Tải dữ liệu của bạn" của TikTok); không đọc ngầm tài khoản. Mọi nguồn tùy chọn; không có nguồn nào thì profile bắt đầu từ quyết định trong app.

**Thời điểm xin.** Lần đầu dùng: không xin, không banner. Sau giá trị đầu tiên: mời một lần, bỏ qua được. Tốt nhất: xin đúng lúc hệ thống thiếu thông tin, nói rõ đổi lấy gì (ví dụ "đi rồi mà quên đi chỗ nào" → mời tải Timeline để lọc nơi đã đi). Không bao giờ chặn người dùng để chờ dữ liệu.

**Tối thiểu hóa** (mọi nguồn file): một lần import = một mục đích, nói rõ lấy gì, không đồng ý trọn gói; cắt lát trước khi nạp (chỉ Đà Lạt và chuyến đi xa); chỉ lưu feature dẫn xuất (`visited`, `pace`, `dwell`), xóa dump thô sau khi trích trong thời hạn đã công bố; cho người dùng xem đã trích gì và xóa từng mục. Nơi thường ngày (nhà, trường, chỗ làm) tách khỏi hành vi giải trí trước khi dùng.

### 6.2. Cấu trúc User Profile

| Nhánh | Là gì | Ví dụ | Quy tắc |
|---|---|---|---|
| Demonstrated Preferences | kiểu trải nghiệm thường chọn trong hành vi thật | `coffee high`, `nature high`, `quiet medium` | dùng để xếp hạng, không phải hard constraint |
| Recent Interests | chủ đề đang chủ động tìm hiểu | `camping rising`, `coffee stable` | hành động có chủ đích (search, save, share) nặng hơn xem tình cờ; giảm trọng số theo thời gian |
| Experience History | đã trải nghiệm gì | `coffee extensive`, `camping none` | tránh lặp quá nhiều cái quen, tìm cái mới cho khách quay lại; chưa trải nghiệm ≠ không thích: thiếu bằng chứng thì `unknown`, không phải `dislike` |
| Behavioral Defaults | thói quen lặp lại làm mặc định khi lập chuyến | `pace balanced`, dwell 60–90 phút, `crowd tolerance low`; cùng ba tham số dẫn dắt §3.3 | chỉ giảm input ban đầu; người dùng đổi được cho từng chuyến |

### 6.3. Exploration Gap

Recent Interest cao + Experience thấp / không có → **trải nghiệm mới tiềm năng** (ví dụ camping). Nhờ vậy hệ thống hỏi được cả "người dùng có thể muốn khám phá gì tiếp", tránh chỉ lặp lại lịch sử. Ở MVP, Recent Interests chủ yếu đến từ tín hiệu trong app (compare, critique, lý do bỏ) nên vùng này bắt đầu hẹp và rộng dần theo số phiên.

## 7. Bối cảnh chuyến hiện tại và User Profile

Mỗi chuyến có context riêng: ngày, số ngày, người đi cùng, chỗ ở, phương tiện, anchor, physical constraint, user hard constraint, override của chuyến. **Context chuyến hiện tại luôn thắng hành vi lịch sử**: profile thích hiking nhưng chuyến này đi cùng bố mẹ, hạn chế đi bộ, thì không ưu tiên hiking. Thứ tự xử lý:

```text
Physical Constraints → User Hard Constraints → Current Trip Override → Recent Interests → Demonstrated Preferences
```

### 7.1. Trip-specific Override

Không hỏi lại toàn bộ sở thích mỗi chuyến: profile làm mặc định, chỉ thu thập điều **khác bình thường hoặc chưa biết mà có thể đổi kết quả** (Theo gu thường ngày · Muốn thử điều mới · Đi cùng đối tượng khác · Có yêu cầu riêng). "Lần này không muốn đi cà phê, muốn ngoài trời" → session `coffee = avoid`, `outdoor = high`, `novelty = high`, còn long-term vẫn `coffee = high`. Override chỉ áp cho chuyến hiện tại.

## 8. Cập nhật User Profile

```text
External Signals + Quyết định trong TripGuardian → User Events → diễn giải → Session Profile
    → bằng chứng lặp lại / mạnh? ── không → chỉ session
                                 └─ có    → cập nhật Long-term Profile
```

Không cập nhật long-term chỉ từ một click hay một hành động đơn lẻ.

### 8.1. Session Profile

Mỗi chuyến một Session Profile, đổi nhanh theo hành vi: người dùng liên tục bỏ cà phê, chọn hoạt động ngoài trời thì đề xuất trong phiên thích nghi ngay, không có nghĩa gu cà phê dài hạn đổi.

### 8.2. Tín hiệu trong app

| Mức | Hành động |
|---|---|
| Mạnh | lock / must-go, nói rõ không thích, remove lặp lại, chọn sau khi so sánh, "thêm kiểu này" |
| Trung bình | add, save, compare, replace |
| Yếu | mở chi tiết, xem, dừng lâu |
| Rất yếu | chỉ hiện ra |

Không bấm ≠ không thích: nơi hiện ra mà không được tương tác chưa đủ để giảm preference.

### 8.3. Lý do của quyết định

`remove` không có nghĩa là ghét cả loại trải nghiệm. Bỏ thác A vì "xa quá" thì giảm `travel tolerance`, không giảm `nature`. Khi hữu ích cho đề xuất tiếp theo, hỏi lý do ngắn: Xa quá → travel tolerance · Đông quá → crowd tolerance · Giá cao → price sensitivity · Không hứng thú → experience preference · Đã từng đi → experience history.

### 8.4. Học từ so sánh

Chọn giữa hai nơi giống nhau thì học phần khác nhau. A (yên, xa, thiên nhiên) thắng B (đông, gần, thiên nhiên): không tăng `nature` (cả hai đều có), mà ghi `quietness > shorter travel`.

### 8.5. Sau chuyến đi

Lịch dự kiến → chuyến thật → nơi đã ghé → phản hồi → Experience History + bằng chứng preference. Ghé thăm chỉ chứng minh `experienced = true`, không chứng minh `liked = true`; chỉ phản hồi hoặc quyết định lặp lại mới tăng độ chắc về preference.

### 8.6. Cập nhật dài hạn

Preference dài hạn chỉ đổi khi có nhiều tín hiệu độc lập, hành vi lặp lại, tín hiệu chủ đích mạnh, hoặc người dùng nói rõ. Ví dụ bỏ cà phê ở chuyến 1, chuyến 2, rồi chuyến 3 chọn ngoài trời thay cà phê → gu cà phê có thể giảm. Một hành động trong một chuyến không ghi đè được.

### 8.7. Độ chắc, xu hướng, độ mới

Mỗi thuộc tính giữ `value`, `confidence` (chắc đến đâu), `trend` (ổn định / tăng / giảm) và freshness (tín hiệu mới nặng hơn tín hiệu quá cũ). Ví dụ `coffee high · confidence high · declining`, `camping medium · medium · rising`.

## 9. Vai trò của User Profile trong đề xuất

Profile không trực tiếp chọn nơi; nó chỉ cho tín hiệu cá nhân hóa sau khi constraint đã kiểm.

```text
Place Intelligence + Trip Context + User Profile
  → lấy ứng viên → sàng constraint → hợp bối cảnh → hợp gu + quan tâm gần đây + novelty + đa dạng → shortlist
```

Constraint quyết định nơi nào **đi được**; Trip Context quyết định nơi nào **hợp chuyến này**; Profile quyết định trong các nơi hợp lệ, nơi nào **có khả năng hợp người này hơn**.

## 10. Vòng lặp cá nhân hóa

```text
Hành vi bên ngoài → User Profile → bắt đầu chuyến → đề xuất → quyết định → Session Profile → đề xuất thích nghi
  → kết quả chuyến → gộp + độ chắc → cập nhật Long-term Profile → chuyến sau
```

Dữ liệu ngoài chủ yếu giải quyết **cold start**; càng dùng nhiều, quyết định trong app càng quan trọng hơn vì có kèm context của từng lựa chọn.

## 11. Nguyên tắc User Profile

- Không hỏi lại điều đã biết đủ chắc.
- Hành vi quan sát được là bằng chứng, không phải sự thật.
- `unknown` ≠ không thích; đã đến ≠ đã thích.
- Quan tâm gần đây có thể khác gu dài hạn.
- Context chuyến hiện tại thắng hành vi lịch sử.
- Một sự kiện đơn lẻ không ghi đè long-term profile.
- Cá nhân hóa phải giúp khám phá, không tạo filter bubble.
- Người dùng luôn sửa hoặc ghi đè được suy luận của hệ thống.

## 12. Khám phá nhu cầu

Không phải ai cũng nói rõ mình muốn gì. Thay vì questionnaire cố định, TripGuardian hội thoại ngắn và **chỉ hỏi khi câu trả lời có thể đổi kết quả** ("thiên về nghỉ ngơi hay khám phá nhiều nơi?", "thoải mái đi bao lâu mỗi ngày?", "có kiểu nơi nào chắc chắn không muốn?"). Mỗi câu cho phép: chọn gợi ý, gõ tự do, `Không chắc`, bỏ qua, hoặc xem đề xuất trước. Mức hỗ trợ theo hành vi trong phiên (§3.3), không theo nhóm người định sẵn. Có profile thì chỉ hỏi phần khác bình thường hoặc chưa biết (§7.1); chưa có (cold start) thì bắt đầu từ chính chuyến đi.

Trước khi tìm nơi, hệ thống hiện bản hiểu nhu cầu ngắn: thông tin chuyến, anchor, hard constraint, preference (đánh dấu phần lấy từ profile), phần còn chưa chắc. Người dùng sửa trực tiếp được, kể cả suy luận từ profile.

### 12.1. Nguyên tắc đặt câu hỏi

| # | Nguyên tắc | Căn cứ |
|---|---|---|
| 1 | **Chỉ hỏi câu có giá trị thông tin cao nhất**: mỗi lượt chọn câu đổi tập ứng viên nhiều nhất; câu không đổi kết quả thì bỏ. | chọn câu hỏi để học nhanh preference khi cold start [11]; hỏi làm rõ khi yêu cầu mơ hồ / thiếu [12] |
| 2 | **Hỏi làm rõ trước khi lập kế hoạch**: agent tự nhận ra thông tin thiếu và hỏi trước khi gọi tool / xếp lịch, không đoán. | Ask-before-Plan [13] |
| 3 | **Constraint phải rõ trước khi lập kế hoạch**: ngân sách, thời gian, thể chất được biết hoặc đánh dấu `unknown` trước khi tìm nơi (thứ tự §7), không có nghĩa luôn hỏi đầu tiên (`docs/TRIP_UNDERSTANDING.md` §5). | TravelPlanner: agent LLM hay bỏ sót ràng buộc [14] |
| 4 | **Hỏi cách dùng, không hỏi thuộc tính**: "chuyến này để làm gì / đi với ai" dễ trả lời hơn "thích loại POI nào". | [8] |
| 5 | **Có gợi ý + cho gõ tự do**: lựa chọn sẵn nhưng không khóa input. | guidance cao cho kết quả khớp hơn [9] |
| 6 | **`Không chắc` hợp lệ nhưng không phải điểm dừng**: ghi `unknown`, không suy thành không thích; khai thác gián tiếp qua đề xuất + phản hồi thay vì hỏi dồn. | lối tắt "không ý kiến" [16]; critiquing [17]; CRS kết hợp hỏi và đề xuất [24] |
| 7 | **Làm rõ từ chủ quan** ("chill", "yên", "đẹp") trước khi dùng làm tiêu chí. | [10] |
| 8 | **Hỏi "vì sao" tới nhu cầu gốc, tối đa 1–2 bậc**: "muốn đi đồi chè" → "muốn chỗ thoáng, ít người" mở ra lựa chọn thay thế. | laddering [18] |
| 9 | **Để LLM sinh câu mở / ví dụ biên** khi mô tả mơ hồ; câu trả lời vẫn chuẩn hóa về field của Trip Context. | generative active task elicitation [15] |
| 10 | **Cho trả lời bằng hình** khi khó diễn đạt kiểu trải nghiệm. | chọn ảnh để suy travel profile [21] |

### 12.2. Cài đặt

Ngân hàng câu hỏi, cách chọn câu tiếp theo, điều kiện dừng, giọng điệu: `docs/TRIP_UNDERSTANDING.md` §5, §7, §12, §13. Ở đây chỉ giữ **vì sao** (§12.1) và cách điều chỉnh theo người dùng (§12.3).

### 12.3. Điều chỉnh cách hỏi theo người dùng

Không chia persona có kịch bản riêng. Ngân hàng câu hỏi dùng chung; thứ đổi theo người dùng là **mức hướng dẫn, dạng câu, độ sâu**. Người mới hưởng lợi từ gợi ý sẵn, người am hiểu thích nêu tiêu chí trực tiếp [25]; người dùng CRS chia nhiều nhóm theo mức muốn tự kiểm soát [26]; động cơ du lịch đổi theo kinh nghiệm [20].

| Tín hiệu | Cách hỏi | Căn cứ |
|---|---|---|
| Trả lời ngắn, chưa nêu được tiêu chí, chủ yếu bấm chip | hỏi theo cách dùng (nhóm G), luôn có chip, cho "xem gợi ý trước" sớm | [8], [25] |
| Tự nêu tiêu chí, gọi tên khu vực, nhắc chuyến trước | hỏi thẳng tiêu chí; ưu tiên nhóm H (đã đi đâu, muốn mới hay quen) | [20], [25] |
| Chưa có ý tưởng | nhiều câu mở + gợi ý hơn | [15] |
| Có nơi đã lưu / lịch sơ bộ | bắt đầu từ xác nhận anchor (nhóm E) và constraint; ít câu sở thích | §3.2 |
| Trả lời dài, muốn kiểm soát | lựa chọn chi tiết, cho chỉnh từng tiêu chí | [26] |
| Trả lời cụt, nhiều `Không chắc` | ít câu, chuyển sớm sang đề xuất rồi critique | [16], [17], [26] |

Chỉ dùng thông tin người dùng đã cung cấp hoặc thể hiện trong hội thoại.

## 13. Nguồn thông tin

Phân biệt **nguồn để khám phá** và **nguồn đủ căn cứ để quyết định**:

| Nguồn | Giá trị |
|---|---|
| TikTok, Facebook, YouTube, blog | khám phá nơi và kiểu trải nghiệm |
| Bình luận TikTok, cộng đồng | tín hiệu trải nghiệm lặp lại (độ đông, yên tĩnh, đường vào) |
| Google Maps / Places | định danh, vị trí, địa chỉ, giờ hoạt động |
| Trang chính thức | giá, giờ mở, quy định, thông báo |
| Nguồn địa phương | sự kiện, giao thông, cảnh báo |
| Dịch vụ thời tiết / tuyến đường | điều kiện theo thời điểm |
| Người dùng | nhu cầu, constraint, anchor |
| Tín hiệu hành vi được cho phép | cá nhân hóa (§6.1), không phải bằng chứng về địa điểm |

Mỗi nhận định quan trọng về địa điểm có `claim + nguồn + thời điểm thu + độ tin`. Thiếu hoặc mâu thuẫn thì hiện **chưa chắc**, không để AI tự điền. Cách xây và kiểm Place Intelligence: `docs/CORPUS.md`.

## 14. Nguyên tắc sản phẩm

1. **Chọn trước, lập lịch sau**: nơi chỉ vào lịch sau khi đã đánh giá độ hợp.
2. **Ràng buộc trước sở thích**: hard constraint kiểm trước khi xếp hạng theo gu.
3. **Hợp quan trọng hơn nổi tiếng**: độ phổ biến chỉ là một tín hiệu.
4. **Người dùng giữ quyền chọn**: hỗ trợ quyết định, không quyết định thay.
5. **Giải thích cả chọn và bỏ**: người dùng cần thấy đánh đổi.
6. **Không che giấu bất định**: thiếu dữ liệu thì nói là thiếu.
7. **AI không tự xác nhận khả thi**: giờ mở, thời gian, tuyến, ngân sách, constraint kiểm bằng logic tất định.
8. **Cá nhân hóa không vượt qua chuyến đi**: profile là prior, dùng sau khi kiểm constraint; context chuyến hiện tại thắng.
9. **Xin dữ liệu theo mục đích**: mỗi lần xin gắn một mục đích và một ích lợi thấy ngay; không xin trọn gói ở cửa vào, không chặn người dùng chờ dữ liệu.

## 15. Ví dụ

> "Lần đầu đi Đà Lạt, 3 ngày với người yêu, đi xe máy. Lưu khoảng 15 nơi trên TikTok mà không biết chọn chỗ nào. Thích thiên nhiên và cà phê nhưng không muốn chạy xe nhiều."

Hệ thống nhận ra trạng thái **có nơi đã lưu**, đọc và chuẩn hóa danh sách, loại / cảnh báo nơi trái constraint, nhóm nơi trùng trải nghiệm, đề xuất shortlist:

```text
15 nơi đã lưu → 12 nơi xác minh được → 3 nơi trái mong muốn ít chạy xe → 2 cặp trải nghiệm gần giống nhau → 8 ứng viên đáng cân nhắc
```

> "Hai quán A và B đều thiên về view rừng, nằm ở hai khu khác nhau. Bạn không muốn chạy xe nhiều nên có thể chỉ cần chọn một."

Người dùng chọn A → "Giữ A giúp ngày 2 giảm khoảng 35 phút di chuyển so với B." Chọn xong mới xếp lịch.

## 16. Vai trò của AI

LLM dùng để: hiểu ngôn ngữ tự nhiên và yêu cầu mơ hồ; trích preference; diễn giải tín hiệu hành vi và lý do quyết định cho profile; trích bằng chứng về địa điểm từ video, bình luận, trang web (luôn kèm span nguồn); tổng hợp bằng chứng; sinh câu hỏi thích ứng; giải thích kết quả.

LLM **không** tự quyết: giờ mở có hợp lệ không, hai khoảng thời gian có xung đột không, ngân sách có vượt không, tuyến có khả thi không, lịch có vi phạm hard constraint không. Những việc này do logic tất định. Model cũng không ghi fact về địa điểm: model trích observation, rule tổng hợp, model mạnh hơn kiểm nơi rủi ro cao, người duyệt phần vẫn bị đánh dấu.

## 17. Phạm vi MVP

**Trong phạm vi:** Đà Lạt; người tự lên kế hoạch chuyến tự túc 2–4 ngày, cá nhân / cặp đôi / nhóm nhỏ; trip context; khám phá nhu cầu; nhập nơi đã lưu; anchor và must-go; tìm và kiểm địa điểm (agent xây, người duyệt theo rủi ro); shortlist; so sánh; người dùng tuyển chọn; khả thi; lịch nhiều ngày; tối ưu tuyến; cảnh báo và dự phòng.

**Ngoài phạm vi:** dẫn đường từng ngã rẽ; nền tảng đặt chỗ đầy đủ; mạng xã hội du lịch; cộng tác phức tạp cho nhóm lớn; phủ toàn Việt Nam; import Google Maps Timeline và file dữ liệu TikTok; suy đoán nhân khẩu học; cam kết mọi thông tin real-time; để LLM tự tạo dữ kiện còn thiếu.

## 18. Thước đo thành công

Đánh giá bằng chất lượng quyết định, không chỉ bằng việc có ra lịch hay không.

| Mục tiêu | Chỉ số |
|---|---|
| Đúng constraint | tỉ lệ vi phạm hard constraint |
| Có căn cứ | độ phủ bằng chứng |
| Không bịa | tỉ lệ nhận định không có nguồn |
| Khả thi | tỉ lệ lịch khả thi |
| Giảm công sức | thời gian tới khi chấp nhận lịch |
| Giảm tìm ngoài | số lần tìm / tab bên ngoài |
| Giúp lựa chọn | tỉ lệ chọn được từ shortlist |
| Dễ hiểu | người dùng hiểu lý do chọn / bỏ |
| Cá nhân hóa | kết quả đổi hợp lý khi preference đổi |
| Minh bạch | bất định được cảnh báo đúng |
| Ổn định | tỉ lệ lịch vững / dễ vỡ |

Ngưỡng mục tiêu chỉ đặt sau khi có baseline và pilot.

## 19. Baseline đánh giá

So trên cùng các tình huống với: **(1) người dùng tự tìm** (TikTok, Google Search, Maps, review) và **(2) AI travel planner thông thường** (nhập yêu cầu, nhận lịch ngay). TripGuardian: Hiểu → Kiểm → So sánh → Chọn → Xác thực → Xếp lịch. Câu hỏi đo: có giảm thời gian lập kế hoạch, giảm vi phạm constraint, giảm số lần sửa lịch, giúp tự tin hơn khi chọn, cho lịch khả thi hơn không.

## Tài liệu tham khảo

[1] J.-Y. Park and S. Jang, “Confused by too many choices? Choice overload in tourism,” *Tourism Management*, vol. 35, pp. 1–12, 2013.

[2] Traveloka and YouGov, “Travel Redefined: Understanding and Catering to the Diverse Needs of APAC Travellers,” 2024.

[3] Công an tỉnh Lâm Đồng, “Nâng cao ý thức chấp hành luật giao thông đường bộ trong các dịp lễ, Tết.”

[4] Cổng thông tin điện tử tỉnh Lâm Đồng, “Đà Lạt: Nỗ lực chống ùn tắc giao thông.”

[5] Wanderlog, “Wanderlog travel planner.”

[6] Mindtrip, “AI-powered travel, personalized to you.”

[7] Tripadvisor, “Plan your trip with Tripadvisor's AI travel assistant.”

[8] I. Kostric, K. Balog, and F. Radlinski, “Soliciting User Preferences in Conversational Recommender Systems via Usage-related Questions,” RecSys 2021.

[9] L. Ziegfeld, D. Di Scala, and A. H. M. Cremers, “The effect of preference elicitation methods on the user experience in conversational recommender systems,” *Computer Speech & Language*, 2025.

[10] F. Radlinski et al., “Subjective Attributes in Conversational Recommendation Systems: Challenges and Opportunities,” AAAI 2022.

[11] K. Christakopoulou, F. Radlinski, and K. Hofmann, “Towards Conversational Recommender Systems,” KDD 2016, pp. 815–824.

[12] M. Aliannejadi, H. Zamani, F. Crestani, and W. B. Croft, “Asking Clarifying Questions in Open-Domain Information-Seeking Conversations,” SIGIR 2019.

[13] X. Zhang, Y. Deng, Z. Ren, S.-K. Ng, and T.-S. Chua, “Ask-before-Plan: Proactive Language Agents for Real-World Planning,” Findings of EMNLP 2024.

[14] J. Xie et al., “TravelPlanner: A Benchmark for Real-World Planning with Language Agents,” ICML 2024.

[15] B. Z. Li, A. Tamkin, N. Goodman, and J. Andreas, “Eliciting Human Preferences with Language Models,” ICLR 2025 (arXiv:2310.11589).

[16] J. A. Krosnick et al., “The Impact of ‘No Opinion’ Response Options on Data Quality: Non-Attitude Reduction or an Invitation to Satisfice?,” *Public Opinion Quarterly*, vol. 66, no. 3, pp. 371–403, 2002.

[17] L. Chen and P. Pu, “Critiquing-based recommenders: survey and emerging trends,” *User Modeling and User-Adapted Interaction*, vol. 22, pp. 125–150, 2012.

[18] T. J. Reynolds and J. Gutman, “Laddering Theory, Method, Analysis, and Interpretation,” *Journal of Advertising Research*, vol. 28, no. 1, pp. 11–31, 1988.

[19] J. L. Crompton, “Motivations for Pleasure Vacation,” *Annals of Tourism Research*, vol. 6, no. 4, pp. 408–424, 1979.

[20] P. L. Pearce and U.-I. Lee, “Developing the Travel Career Approach to Tourist Motivation,” *Journal of Travel Research*, vol. 43, no. 3, pp. 226–237, 2005.

[21] J. Neidhardt, R. Schuster, L. Seyfang, and H. Werthner, “Eliciting the users' unknown preferences,” RecSys 2014.

[22] A. Delic et al., “Observing Group Decision Making Processes,” RecSys 2016.

[23] S. Darcy and T. Dickson, “A Whole-of-Life Approach to Tourism: The Case for Accessible Tourism Experiences,” *Journal of Hospitality and Tourism Management*, vol. 16, no. 1, pp. 32–44, 2009.

[24] D. Jannach, A. Manzoor, W. Cai, and L. Chen, “A Survey on Conversational Recommender Systems,” *ACM Computing Surveys*, vol. 54, no. 5, art. 105, 2021.

[25] B. P. Knijnenburg, N. J. M. Reijmer, and M. C. Willemsen, “Each to his own: How different users call for different interaction methods in recommender systems,” RecSys 2011.

[26] R. Mahmud, S. Berkovsky, M. Prasad, and A. B. Kocaballi, “Understanding User Preferences for Interaction Styles in Conversational Recommender Systems: The Predictive Role of System Qualities, User Experience, and Traits,” OzCHI 2025.

[27] S. Kim, J. Lee, and G. Gweon, “Comparing Data from Chatbot and Web Surveys: Effects of Platform and Conversational Style on Survey Response Quality,” CHI 2019.

[28] Z. Xiao et al., “Tell Me About Yourself: Using an AI-Powered Chatbot to Conduct Conversational Surveys with Open-ended Questions,” *ACM Transactions on Computer-Human Interaction*, vol. 27, no. 3, 2020.

[29] A. Gretry, C. Horváth, N. Belei, and A. C. R. van Riel, “‘Don't pretend to be my friend!’ When an informal brand communication style backfires on social media,” *Journal of Business Research*, vol. 74, pp. 77–89, 2017.

[30] A. P. Chaves, J. Egbert, T. Hocking, E. Doerry, and M. A. Gerosa, “Chatbots Language Design: The Influence of Language Variation on User Experience with Tourist Assistant Chatbots,” *ACM Transactions on Computer-Human Interaction*, 2022.

[31] A. P. Chaves and M. A. Gerosa, “How Should My Chatbot Interact? A Survey on Social Characteristics in Human–Chatbot Interaction Design,” *International Journal of Human–Computer Interaction*, vol. 37, no. 8, pp. 729–758, 2021.

[32] “Does Chatbot Language Formality Affect Users' Self-Disclosure?,” CUI 2022 (ACM Conference on Conversational User Interfaces), doi:10.1145/3543829.3543831.

[33] H. V. Luong, *Discursive Practices and Linguistic Meanings: The Vietnamese System of Person Reference*. Amsterdam: John Benjamins, 1990.
