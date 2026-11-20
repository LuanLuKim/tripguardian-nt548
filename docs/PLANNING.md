# Planning & Validation + Live Context

Bước online thứ ba và cuối. Vị trí trong luồng: `docs/ARCHITECTURE.md` §3. Đầu vào: `docs/PLACE_DECISION.md` §15. Code: `src/live/` (Live Context) + `src/planning/` (lịch trình); CLI và API ở §CLI và API.

Factory nhận public retrieval cùng binding. "Tối ưu lịch" là bộ tìm tất định, không gọi model (§Tối ưu lịch).

## Mục tiêu

Từ **tập địa điểm đã xác nhận** của Place Decision, dựng **lịch trình** đã kiểm tra hoặc các phương án khi quá tải, rồi để người dùng sửa và chốt. Chỗ ở là tùy chọn; khi chưa rõ vẫn dựng lịch với điểm nền mặc định, không ghi mặc định thành nơi lưu trú của người dùng.

Cổng lập lịch chỉ cần ngày bắt đầu + số ngày và nhóm lưu ý sức khỏe / ăn uống; tín hiệu sức khỏe hoặc câu hỏi ăn kiêng còn mở vẫn chặn. `SearchInput.readiness.missing` chỉ chứa `trip` / `care`; `Engine.create` không yêu cầu `readback_ok`, không chặn vì người đi cùng, phương tiện, nhịp độ, ngân sách hay chỗ ở chưa biết (quyết định chủ dự án 10/11/2026). Giờ thiếu dùng `FrameDefaults`, nhịp thiếu dùng `normal`, phương tiện thiếu dùng ước lượng di chuyển sẵn có, ngân sách thiếu không đặt trần; các giá trị đầu vào vẫn `unknown`. Kết quả là lịch bình thường, không gắn nhãn nháp vì thiếu các thông tin này. Trường read-back/digest giữ tương thích, không phải bước duyệt trước lập lịch.
Trang Lịch trình có thể điền thêm đi cùng, phương tiện, nhịp độ, ngân sách (`PLAN_FILL`): `Deck.at="plan"`, `TurnInput.at="plan"`, đọc qua `read/trip/readback` (`fill`). Mỗi câu trả lời dựng lại lịch từ `decision` (chủ dự án 10/11/2026).

Đích: tối ưu có thật (đo được so với baseline), kiểm tra tất định (lịch trông hợp lý là chưa đủ), và giải thích được từng lựa chọn — kể cả cái đã phải hy sinh.

## Phạm vi

Trong: chia ngày; thứ tự trong ngày; khớp giờ mở cửa; chọn thời gian tham quan theo nhịp độ; thời gian đệm và nghỉ; đề xuất chỗ ở (tra live theo yêu cầu); điểm vào / ra thành phố; kiểm tra cuối; độ vững; kế hoạch dự phòng; 2–3 phương án theo mục tiêu; vòng người dùng sửa / góp ý / chọn; Live Context (thời gian di chuyển, thời tiết, chỗ ở, geocode, mặt trời, lễ).

Ngoài: booking và thanh toán; điều hướng turn-by-turn; traffic thời gian thực; giá phòng từ API OTA; nhiều thành phố; cộng tác nhóm; đưa chỗ ở vào Place Intelligence.

## Nguyên tắc

1. **Chỗ ở không bao giờ vào Place Intelligence.** Nó được tra live theo từng request, chỉ sống trong phiên, mang `source` + `fetched_at` (`docs/ARCHITECTURE.md` §1).
2. **Chỗ ở là biến trong bài tối ưu**, không phải danh sách gợi ý rời. Mỗi ứng viên được chấm bằng cách làm anchor đầu / cuối ngày rồi xếp lại cả lịch và đo.
3. **Solver và kiểm chứng tất định.** Agent nội bộ chỉ đề xuất bố trí trên phương án đã dựng; quyền, khả thi và điểm mục tiêu do rule kiểm trước khi áp dụng.
4. **Physical constraint không bao giờ nới ngầm.** Không có đường code nào nới nó.
5. **Không bịa.** Thiếu dữ liệu → `unknown` + gắn cờ, không điền giá trị. Thiếu quán ăn trong tập đã xác nhận → chừa khoảng trống, không tự thêm địa điểm.
6. **Số live luôn có nguồn và thời điểm.** Thời gian di chuyển, giá phòng, thời tiết đều gắn nhãn ước lượng / tham khảo, không phải Fact.
7. **Không xáo lịch âm thầm.** Mỗi thay đổi hiện qua diff; nơi đã khóa không bị dời.

## Ranh giới module

```
src/live/                      Live Context — gọi mạng, đọc-ghi cache; KHÔNG có đường ghi data/intel
  __init__.py                  public API: travel_matrix, route_shape, weather, lodging_near, lodging_seen, geocode,
                               geosearch, flights, flights_url, buses, buses_url, sun_times, holidays, events,
                               advisories, Unavailable
  http.py                      một GET (JSON hoặc trang HTML), một timeout, không retry; lỗi → Unavailable
  cache.py settings.py         cache theo key + TTL → data/live/<source>/; ngưỡng từ config/live.yaml
  osrm/                        ma trận thời gian (/table) + hình lộ trình (/route), service local
  weather/                     Open-Meteo: dự báo theo giờ trong tầm; ngoài tầm → khí hậu theo tháng
  lodging/                     crawl mặt lodging của Maps theo request (Planning không gọi; ứng viên lấy từ corpus)
  geocode/                     text → toạ độ (Nominatim); gợi ý khi gõ (Photon, lỗi → Nominatim)
  flights/                     chuyến bay một ngày từ Google Flights (không còn trong luồng người dùng)
  buses/                       xe khách một ngày từ Vexere (không còn trong luồng người dùng)
  sun.py                       mọc / lặn, công thức NOAA, tính local
  holidays.py events.py        holidays: view CalendarDay + config/holidays.yaml (lớp ghi đè); events: config/events.yaml (nhập tay)
  views.py                     đọc data/<city>/views/*.json (chỉ đọc; thành phố = `views_city` trong config/live.yaml, mặc định dalat)
  advisories.py                config/advisories.yaml (thông báo nhập tay, có nguồn)

src/planning/                  Planning & Validation — rule tất định
  model.py settings.py         kiểu dữ liệu; ngưỡng từ config/planning.yaml
  places.py                    Decision Output + serving record → nơi xếp được + điểm đầu / cuối chuyến
  frame.py                     các ngày của chuyến: ngày, thứ, khung giờ dùng được
  conditions.py                điều kiện từng ngày (DayCond) từ live; hazard, đông khách, đóng cửa dịp Tết; `fetch_live`
  travel.py                    một ma trận OSRM mỗi chuyến, chặng ngắn đi bộ, đường lui thô có nhãn
  traits.py                    fact của một nơi mà mục tiêu / độ vững / dự phòng dùng chung
  lodging.py                   ⓐ vùng tìm → nguồn (corpus `stay` hoặc live) → sàng → xếp theo gu → K ứng viên
  logistics.py                 tra cứu trước khi có phiên Planning: geo, chỗ ở theo tên (chỉ corpus)
  layout.py days.py route.py   ⓑ chia ngày (chèn rẻ nhất + đổi chỗ), số hạng rủi ro của ngày, thứ tự trong ngày
  schedule.py                  ⓒ khớp giờ mở, visit theo pace, đệm, nghỉ
  timefit.py                   độ phù hợp toàn khoảng ghé theo hoạt động, mục đích và ưu tiên buổi
  recommendations.py           gợi ý tùy chọn từ backup_pool, thử xếp và validate trước khi trả
  validate.py                  ⓔ kiểm tra cuối, fail-closed
  robustness.py                ⓕ độ vững 3 mức
  backup.py                    ⓗ dự phòng từ backup_pool
  eve.py                       đổi lịch tối trước mỗi ngày đi (D.3): mức ảnh hưởng, sửa tối thiểu, chống báo thừa
  objectives.py variants.py    ⓖ điểm theo mục tiêu; dựng 2–3 phương án
  optimize.py                  "Tối ưu lịch": chia lại ngày + thứ tự, tất định, không model
  build.py                     ghép một đường: prepare → schedule_trip → with_home
  repair.py scope.py           repair_day; phạm vi chạy lại
  output.py                    Plan Output
  session.py artifacts.py      phiên có phiên bản, undo / redo, snapshot thẻ đã đưa ra
  agent.py guard.py policy.py  một call mỗi lượt chữ; guard; policy từ khóa khi agent lỗi
  proposal.py                 PlanningProposal: schema cũ, chỉ để replay log `recommend` trước 18/11/2026
  tools.py skills.yaml        adapter public cho harness; quyền agent theo module
  engine.py server.py          HTTP + SSE, cổng 8768
  evaluate.py                  đo offline trên 10 chuyến có tên
```

Phụ thuộc một hướng: `planning` → `live`, `decision`, `trip`, `corpus.serving`, `corpus.ontology`, `corpus.snapshot`, `corpus.releases`, `corpus.retrieval` (chỉ đọc; chỉ qua `__init__.py`; RULE §2). `live` không biết `planning`. `decision` không đổi.

Dữ liệu:

| Thư mục | Ghi bởi | Nội dung |
|---|---|---|
| `data/live/<source>/` | `src/live` | cache theo request, có TTL, mỗi mục mang `source` + `fetched_at` (`lodging`, `osrm`, `weather`, `geocode` — chỉ tạo khi nguồn đó được gọi) |
| `data/planning/sessions/` | `src/planning` | phiên API độc lập; `data/planning/eval.json` là kết quả `evaluate` |
| `data/intel/`, `data/serving/`, `data/gmaps/` | chỉ offline corpus | Planning chỉ đọc |

## Đầu vào

Decision Output nguyên dạng (`docs/PLACE_DECISION.md` §15): `confirmed` (id, role `anchor | locked | selected`, visit minutes, flags, relaxed), `backup_pool` (kèm `for` + `reason`), `wishlist`, `trip_context` (bản chụp Search Input), `decision_log`, `feasibility`, `lodging` (chỗ ở người dùng chọn ở Lựa chọn, hoặc `null`), `hidden_ids` (nơi người dùng ẩn; mặc định rỗng).

Quy ước: **mọi ngày bắt đầu và kết thúc ở chỗ ở**, kể cả ngày đầu và ngày cuối. `entry_point` / `exit_point` của Trip State không dời điểm đầu / cuối ngày; ngày đầu / cuối chỉ bị cắt theo `checkin_at` / `checkout_at`.

## Live Context

Mọi hàm trả `None` khi không có dữ liệu; không bịa. `src/live` không import `corpus.aggregate` / `corpus.serving` để ghi, và test khẳng định không có đường ghi tới `data/intel`, `data/serving`, `data/gmaps`.

| Nguồn | Public API | Cách lấy | TTL | Khi lỗi |
|---|---|---|---|---|
| `osrm/` | `travel_matrix(points, mode)`, `route_shape(points, mode)`, `route_steps(points, mode)` | OSRM local trên OSM Việt Nam; `/table` cho ma trận, `/route` cho hình đường của lịch đã chốt; `route_steps` = tên đường từng chặng (nhận chặng qua đèo) | 7 ngày | rơi về ước lượng thô của Planning (`travel.rough_minutes`: đường chim bay × `road_factor` ÷ `rough_speed_kmh`); plan gắn `travel_source = rough` + cảnh báo; độ vững trần "Khả thi" |
| `weather/` | `weather(lat, lng, dates)`, `weather_hourly(lat, lng, day)` | `weather_hourly`: theo giờ một ngày, hai model `best_match` + `gfs_seamless` (mưa %, mm, gió giật, dông, sương mù = mã 45/48 hoặc tầm nhìn < 1 km, `disagree` khi hai model lệch ≥ 0,5 hoặc lệch dông; ngoài tầm → `None`). `weather`: Open-Meteo forecast theo ngày (trong tầm 16 ngày): xác suất mưa, lượng mưa mm, gió giật, dông (`weather_code` 95–99), nhiệt độ thấp / cao nhất (`tmin_c`, `tmax_c`). Tool `weather` của trợ lý trả thêm `tmin_c`, `tmax_c`, `gust_kmh`, `storm`; ngày ngoài tầm không có nhiệt độ dự báo thì kèm `usual_temp_of_month` (trung bình nhiều năm của tháng, nói rõ không phải dự báo). Ngoài tầm → xác suất mưa theo tháng: `rain_prob_override_by_month` trong `config/climate.yaml` (ghi đè tay) > view `ClimateNormal` (`docs/CORPUS.md` §View toàn cầu) > `rain_prob_by_month` (ước lượng tay, chỉ khi chưa dựng view) | 3 giờ / tĩnh | `None` → ngày đó không xét thời tiết, gắn cờ "chưa biết thời tiết"; số nguồn không cho giữ `None` |
| `lodging/` | `lodging_near(…)`, `lodging_seen()` | crawl mặt "Khách sạn" của Maps theo request; Planning **không** gọi (ứng viên chỗ ở chỉ lấy từ corpus, ⓐ) | 24 giờ | — |
| `geocode/` | `geocode(text)` | Nominatim, 1 req/s, User-Agent riêng của dự án | 30 ngày | `None` → hỏi lại người dùng |
| `geocode/` | `geosearch(text, limit=6)` | Photon (OSM, làm cho gõ-tới-đâu-gợi-ý-tới-đó), lỗi → Nominatim | 30 ngày | `Unavailable` → ô tìm hiện "không thấy" |
| `flights/` | `flights(src, dst, day, fetch=True)` | không còn trong luồng người dùng (không hỏi chuyến bay). Google Flights (`hl=vi`, `curr=VND`) qua `corpus.crawl.open_sessions`; đọc `aria-label` của từng dòng chuyến ("Từ … đồng … của <hãng>. Rời … lúc HH:MM … và đến … lúc HH:MM …") | 26 giờ | `Unavailable` (captcha, trang không có dòng nào, trình duyệt chết); không bao giờ trả chuyến giả |
| `buses/` | `buses(origin, day, way, fetch=True)` | không còn trong luồng người dùng (không hỏi chuyến xe). Trang tuyến của Vexere; trang render sẵn nên một GET HTTP stdlib là đủ, không cần trình duyệt: chuyến nằm trong `__NEXT_DATA__` `routeReducer.trips` (giờ đón / đến của `route.schedules[0]`, `fareLarge`, điểm đón / trả). `origin` là toạ độ (tỉnh gần nhất trong `config/live.yaml` `vexere_regions`) hoặc tên tỉnh | 26 giờ | `Unavailable` (trang đổi / bị chặn, tỉnh không có trong bảng) |
| `sun.py` | `sun_times(date, lat, lng)` | công thức NOAA, không mạng, không thêm dependency | — | — |
| `holidays.py` | `holidays(dates)` | view `CalendarDay` (thư viện `holidays` + âm lịch), `config/holidays.yaml` đè tên và thêm ngày | — | chưa dựng view → chỉ file |
| `events.py` | `events(dates)` | `config/events.yaml` (lễ hội, Noel, Tết; nhập tay): `crowd` busy / peak, `closure_risk` | — | ngày không liệt kê = chưa biết sự kiện nào, không phải ngày vắng |
| `advisories.py` | `advisories(dates)` | `config/advisories.yaml` (thông báo thiên tai / đường bị chặn, nhập tay từ thông báo chính thức, bắt buộc có `source`) | — | rỗng = chưa có thông báo trong dữ liệu, **không** phải an toàn |

### OSRM

Thiết lập một lần mỗi máy, `scripts/osrm_setup.sh` + `docs/SETUP.md` §2: tải `vietnam-latest.osm.pbf` (Geofabrik) → `osrm-extract` (profile `car`) → `osrm-partition` → `osrm-customize` → `osrm-routed --max-table-size 300`.

Mode: OSM không có profile xe máy chuẩn. Dùng profile `car` rồi nhân `mode_factor` (`config/live.yaml`: `car 1.0`, `motorbike 0.95`). Chặng ngắn hơn `walk_km` tính đi bộ bằng khoảng cách × `road_factor` ÷ tốc độ đi bộ. Mọi số này hiển thị là **ước lượng**, không nói là thời gian thật của một nhà cung cấp nào. Hình lộ trình (`/route`) gọi với `continue_straight=false` như ma trận `/table`: profile `car` mặc định cấm quay đầu tại điểm dừng, nên hình vẽ sẽ có vòng thừa mà ma trận không tính.

Một ma trận mỗi lượt cho tập điểm = `confirmed` + `backup_pool` có tọa độ + K chỗ ở + chỗ ở của người dùng. Mọi phương án và lần thử thêm backup dùng chung ma trận đó. Item `travel` xuất riêng `road_min` (phút chạy xe/đi bộ) và `buffer_min` (đệm lịch); khoảng `start..end` gồm cả hai, không được hiển thị toàn khoảng là thời gian chạy xe. `distance_km` = đường thẳng × `road_factor` (ước tính, chỉ khi biết toạ độ hai đầu), là số km web dùng để ước cước gọi xe (`docs/BOOKING.md` §Gọi xe).

### Điều kiện từng ngày

Một ngày có thể đổi chính kế hoạch: thời tiết xấu hơn mức "xác suất mưa", cuối tuần / lễ / lễ hội làm đông, dịp Tết nhiều quán đóng cửa, thông báo thiên tai. Engine gọi `conditions.fetch_live` (một lần mỗi lần dựng) lấy `weather` và `signals` (`holiday`, `events`, `advisories` mỗi ngày) từ `src/live`; `prepare()` đổi chúng thành một `DayCond` cho từng ngày có ngày cụ thể. Ngày không có tín hiệu thì không có `DayCond` và lịch giữ nguyên như trước. Cảnh báo ngày xấu (`heavy_weather` / `severe_weather`) gọi đúng nguyên nhân đã vượt ngưỡng: "dông", "mưa lớn" (≥ `heavy_rain_mm`), "gió mạnh" (≥ `heavy_gust_kmh`), hoặc ghép bằng "và"; ngày khô mà gió giật mạnh không bị gọi là mưa. Nguồn thời tiết không trả lời → `weather = None` (cờ "chưa biết thời tiết"); ba file nhập tay không bao giờ làm hỏng chuyến.

| Điều kiện | Cách đọc | Tác động |
|---|---|---|
| Thời tiết | `heavy`: dông hoặc mưa ≥ `heavy_rain_mm` hoặc gió giật ≥ `heavy_gust_kmh`; `severe`: mưa ≥ `severe_rain_mm` hoặc gió giật ≥ `severe_gust_kmh` | `heavy` tính như ngày mưa (`wet` ≥ `rain_high`): đệm lớn hơn, nơi ngoài trời bị phạt khi chia ngày, nơi nhạy cảm có dự phòng, mục tiêu `weather_robust`, kịch bản mưa của độ vững. `severe`: nơi `weather_exposed` **không được xếp** vào ngày đó |
| Thông báo | `advisories.yaml`, phạm vi `city` hoặc vòng tròn `lat, lng, radius_km` | `severe`: nơi trong phạm vi không được xếp (bão chỉ chặn nơi ngoài trời; ngập, sạt lở, cháy, đường bị chặn chặn mọi nơi trong vùng); thấp hơn `severe`: vẫn xếp, có cờ, nơi trong vùng là nhạy cảm (`advisory`) và dự phòng không lấy nơi cùng vùng |
| Vùng hạn chế | view `RestrictedArea` (`docs/CORPUS.md` §View toàn cầu) qua `corpus.views`, thành phố = `views_city` của `config/live.yaml`; chỉ có khi chuyến có ngày | chỉ cảnh báo, không bao giờ loại (OSM chưa đủ): nơi nằm trong vùng là nhạy cảm (`advisory`, mức `watch`) và dự phòng không lấy nơi cùng vùng; `build.restricted_warnings(ctxs, results)` thêm một câu `restricted_place` cho **mỗi nơi có trong lịch** (có `place_id`, nói loại vùng + tên, "kiểm tra trước khi đi", dữ liệu có thể chưa đủ), một lần cho cả chuyến chứ không lặp theo ngày; nơi chưa xếp hoặc đã bị bỏ thì không có câu (gọi từ thẻ phương án trong `schedule_trip`, từ view của engine cạnh `pin_warnings`, và từ `output.build` cho kế hoạch đã chốt); view chưa dựng = chưa biết, không phải không có vùng |
| Đông khách | cuối tuần = `busy`; ngày lễ hoặc sự kiện `peak` = `peak`; một nơi "đông" khi `crowd = high` đã xác minh hoặc `crowd_by_time` của chính nó ≥ `crowd_busy_pct` đúng loại ngày (`weekday` / `weekend` / `holiday`) | nơi đông: thời gian tham quan tăng `crowd_visit_pct`, đệm thêm `crowd_buffer_min`; chia ngày phạt `weights.crowd` × mức × (`crowd_avoid_factor` nếu người dùng tránh đông); ngày `peak` làm nơi đó nhạy cảm (`crowd`) và dự phòng không lấy nơi đông; `crowd_tips` nói giờ vắng nhất từ chính số liệu của nơi |
| Đóng cửa dịp Tết | sự kiện `closure_risk` | cờ mỗi ngày; nơi ăn uống được đệm thêm `closure_buffer_min` và nhạy cảm (`holiday_closure`), dự phòng phải có giờ đã xác minh. Không tự kết luận một quán đóng |

Validate là chỗ duy nhất quyết định: nơi bị hazard mà vẫn có trong lịch là vi phạm `hazard`; không ngày nào xếp được → bản nháp mở được kèm vi phạm `hazard`, người dùng tự quyết định. Dữ liệu vắng thì không kết luận: ngày không có số đo không thành `severe`, và "không có thông báo" không bao giờ được viết thành "an toàn".

Plan Output (qua `shared_output` và view của Engine) thêm `day_conditions` (từng ngày, chỉ khi có điều kiện; ngày xấu mang `weather_cause`, cùng chữ với cảnh báo: "gió mạnh", "dông và mưa lớn") và `crowd_tips`. Web hiện chúng trên ngày đang chọn (`web/src/user/screens/plan/parts.tsx` `Conditions`), gọi ngày xấu bằng `weather_cause`.

### Trạng thái vận hành theo thời điểm

`place_live_status(place)` (đóng cửa tạm, giờ ngày lễ) chỉ chạy ở bước xác nhận cuối, best-effort, timeout mỗi nơi, giới hạn số nơi mỗi phiên. Không tra được → giữ cảnh báo "kiểm tra lại trước chuyến" như giờ `UNCERTAIN` / `OUTDATED` đã có. Không bao giờ sửa giờ trong corpus.

## Thuật toán

### ⓐ Ứng viên chỗ ở — `lodging.py`

0. **Chỗ ở của người dùng:** Decision Output có `lodging` (chọn ở tab "Chỗ ở" của Lựa chọn, `docs/PLACE_DECISION.md` §15), hoặc Trip có `lodging_booked = yes` và `lodging` có toạ độ → chỗ ở đó là `base` (mọi ngày đi và về từ đó); phiên mở ra đã có `lodging_point` (`source: user`, kèm `price_vnd` và `place_id` khi là chỗ ở trong corpus), `lodging.status = booked`; không gợi ý. Đổi chỗ ở = quay lại tab "Chỗ ở" của Lựa chọn.
1. **Vùng tìm:** tâm trọng số của các nơi đã chọn (trọng số = `visit typical`); tách tối đa 2 tâm nếu đường kính cụm > `split_min`.
2. **Nguồn:** chỉ bản ghi serving nhóm `stay` trong vùng (≤ 2 × `radius_km` quanh một tâm),
   `source: corpus`. Giá đêm: nếu `corpus.serving.stay_prices` (qua `stayprice.overlay`) có giá của đúng
   chỗ ở, đúng ngày nhận phòng (`start_date`) và đúng số đêm, và `observed_at` không quá `stay_price_max_age_h`
   (`config/planning.yaml`) thì dùng giá đó (`price_kind: dated`, `price_at` = `observed_at`; thẻ thêm
   `price_age_h`). Không khớp (khác ngày, khác số đêm, quá cũ) thì rơi về `price_per_night` (giá tham khảo
   mặc định Maps, `price_kind: reference`, `price_at` là ngày đọc); không có cả hai thì `price_vnd` là
   unknown (`price_kind: null`), không đoán. Trần giá, điểm giá, thẻ và tổng chi phí đều dùng giá đã chọn
   này; không lấy giá/người làm giá/phòng/đêm. Trần tham khảo = `lodging_share ×
   trip.group_budget(context) ÷ trip.nights(context)` khi quy đổi được tổng nhóm/chuyến.
   Thiếu scope/days/people cần thiết giữ unknown; không suy số phòng/capacity/availability.
   Đây là trần tham khảo, không chứng minh đủ tiền phòng cho cả nhóm vào ngày đi.
   **Dòng tiền phòng theo đêm** (`validate.lodging_budget`, tách khỏi kiểm ngân sách từng ngày vì không
   chặn chốt): mỗi đêm một dòng `{night, date, price_vnd, price_kind, price_age_h, over_vnd}` + `total_vnd`,
   `per_night_cap_vnd` (chính trần ở trên), `over_budget`, `over_vnd`. Trả về trong thẻ phương án
   (`lodging_budget`) và kế hoạch đã chốt (`cost.lodging_nights`). Vượt trần chỉ là cảnh báo
   `lodging_over_budget` (nêu giá, trần, số vượt, nguồn giá + tuổi), không bỏ nơi nào, không thành
   vi phạm. Giá hoặc trần unknown thì `over_budget: null`, không đoán.
3. **Sàng tất định:** ngoài vùng hoặc dưới `min_reviews` → bỏ. Public `requirements` kiểm
   cả eq/ne, scope accommodation và unknown policy. Feature ontology không cho chỗ ở mang
   (`stay_features`) là `not_applicable`; không coi thiếu bằng chứng đó là unknown. Với feature
   áp dụng, safety unknown giữ cờ và xếp sau nơi đạt (§Guardrail); feature khác dùng exclude/flag,
   legacy thiếu policy dùng flag. Unknown được phép giữ ghi `unverified`, không thành pass.
   Chỗ ở đã đặt hoặc người dùng tự chọn được giữ làm neo, không chặn Lập lịch vì requirement;
   cảnh báo `lodging_requirement` nêu rõ unknown hoặc xung đột (ví dụ bậc thang). Quy tắc này
   không áp dụng cho danh sách tự đề xuất: nơi fail vẫn bị loại; unknown theo §Guardrail.
4. **Bể để xếp:** `lodging_pool` chỗ hợp gu nhất (gần hơn thắng khi bằng nhau) để ma trận di chuyển nhỏ.
5. **Xếp hạng** (sau khi ma trận có các ứng viên): `lodging_score = w_pref·pref_fit + w_loc·loc_fit + w_price·price_fit + w_rating·rating_fit` (`lodging_weights`, gu nặng hơn vị trí). `pref_fit` = tổng soft (`love` +1, `avoid` −1) và người đi cùng (`kids`, `parents` → `elderly`, `partner` → `couples` `=suitable`, +1) mà feature `VERIFIED` của chỗ ở khớp, chia số mong muốn; không có bằng chứng → 0, không bao giờ âm (`docs/PLACE_DECISION.md` §8). `loc_fit = 1 − phút trung bình tới các nơi đã chọn ÷ loc_ref_min` (≥ 0). `price_fit` theo trần giá, không giá → 0. `rating_fit` = `provenance.reputation.score` (0..1) của chỗ ở: rating và số review của Maps trên cùng một thang trong nhóm `stay` (`docs/CORPUS.md` Serving record, Uy tín), nên 4,6 sao / 3.000 review hơn 4,9 sao / 500; không có uy tín → rating Maps theo `(rating − 3,5) / 1,5` nếu có, không có → 0. Thẻ hiện rating và số review của Maps (`identity.rating`, `identity.reviews`). Giữ `lodging_k`. Mỗi thẻ mang `fit` ("hợp vì": nhãn feature + số đánh giá nhắc), `avg_min`, `unverified`, `price_at`, `address`.
6. **Trước khi có phiên:** `Engine.lodging_options(decision)` xếp đúng như trên cho bản nháp Decision Output (chưa chốt) để Lựa chọn hiện danh sách; không tạo phiên, cache theo tập nơi + bối cảnh chuyến. Trip đã có chỗ ở thì danh sách vẫn hiện (đổi được). Danh sách gồm **mọi** chỗ ở trong corpus qua được ràng buộc cứng và trần giá, trả theo trang (`offset`, `limit`, mặc định `lodging_list_k` thẻ; kèm `total`). Đã chọn nơi: tối đa `lodging_list_k` chỗ quanh các nơi đó lên đầu, xếp như trên (có `avg_min`); mọi chỗ còn lại theo sau, xếp theo gu rồi điểm đánh giá, không có `avg_min`. Chưa chọn nơi nào: cả danh sách xếp theo gu rồi điểm đánh giá. Mỗi thẻ có cùng trường với thẻ Place Decision (`category`, `area`, `rating`, `why`, `tradeoffs`, `location {center, km, minutes}`, `confidence`) để web vẽ bằng một `PlaceCard`: `why` = điều người dùng muốn (`fit`) rồi điểm mạnh VERIFIED từ 2 người nhắc (giá trị đầu của `polarity`, hoặc `present` / `suitable` / `good` / `included`; không tính `steep_or_stairs`, `cold`), thêm "Gần <tâm>" khi ≤ `near_min`; `tradeoffs` = mặt xấu VERIFIED (giá trị cuối của `polarity`) và "chưa biết ngân sách" khi chưa có ngân sách; `confidence` theo số người viết (≥ 40 cao, ≥ 10 vừa). Cấu hình `polarity`, `center`, `near_min`, `speed_kmh`, `road_factor` lấy từ `decision.load_settings()` qua `Engine(card_cfg=…)` (`tools.py`).
7. Không bắt buộc chỗ ở: thiếu thì lịch vẫn xếp (ngày bắt đầu ở nơi đầu tiên, cảnh báo `base_unknown`), Web chỉ nhắc chọn chỗ ở, không chặn. Cảnh báo theo neo hiện tại: chọn được chỗ ở thì bỏ `base_unknown` ở view và kết quả chốt; undo về chưa có chỗ ở thì hiện lại.

### ⓑ Chia ngày — `layout.py`, `days.py`

- Khung ngày: ngày đầu từ `checkin_at`; ngày cuối đến `checkout_at`; ngày giữa `day_start..day_end`.
- `layout.assign`: mỗi ngày cắt thành các đoạn trống giữa những khối giờ cố định của người dùng; một đoạn chứa số phút còn lại sau bữa và nghỉ. Nơi khó xếp (có giờ trong ngày, ít ngày mở, xa chỗ ở) vào trước, mỗi nơi lấy đoạn và vị trí **thêm ít phút đường nhất** (cộng độ đầy của ngày, ngày lệch khu vực, mưa / đông của ngày theo mục tiêu), rồi đổi chỗ từng nơi giữa các ngày để cải thiện. Nơi thừa vẫn có thể vào khi một ngày nhường hết cho ngày khác hoặc hai ngày đổi nhau. Tất định. Không còn gom cụm và DP trên tập con (`cluster.py`, `assign_days` đã gỡ 2026-10-29).
- Số nơi theo nhịp người dùng nói hoặc suy ra trong chuyến (`sources.pace`: `user` / `inferred`, mức `per_day`): ưu tiên ngày còn dưới mức trước khi gom thêm để tiết kiệm đường; không loại nơi chỉ vì vượt mức nếu ngày khác không chứa được. **Người dùng chưa cho số ngày** (`context.days` trống, khung là `default_days`; từ 18/11/2026, chủ dự án): `_Layout.fill_first`: ngày sau nặng thêm `FILL_FIRST_MIN` (600) phút mỗi bậc thay cho trọng số đầy ngày `BALANCE_MIN`, nên nơi xếp đầy ngày 1 tới khi hết chỗ / hết mức nhịp rồi mới sang ngày 2, và không rải nơi sang ngày trống (trước đó 2 nơi ra 2 ngày, mỗi ngày một nơi). Khi đã có số ngày: Với tập đã xếp đủ, ngày trống không có lịch bận được nhận một nơi từ ngày có ít nhất hai nơi khi mô phỏng cả hai ngày vẫn hợp lệ, giữ đủ bữa và tổng đường tăng không quá `spread_extra_min` (mặc định 45 phút mỗi nơi dời, `planning/settings.py`: một ngày riêng luôn tốn một lượt đi-về từ chỗ ở, nên đòi "không tăng" để lại ngày trống ở mọi chuyến có chỗ ở); chọn nơi dời tốn ít đường nhất, cụm xa vượt ngưỡng thì ở cùng nhau; không đổi tập nơi của bài tìm hướng quá tải.
- Ngày bị kéo sớm tới giờ sớm nhất nơi đó vào được: đầu khung giờ đẹp, hoặc giờ mở cửa nếu muộn hơn (điểm ngắm mở 06:45 không bắt dậy 05:30 để chờ; `layout._first_entry`).
- Chỉ kéo ngày sớm và thêm nghỉ trưa bù khi có ý muốn săn mây / bình minh (`soft_weights`, `time_preferences` hoặc `frame.periods` phù hợp nơi) và giờ ghé thật sự trước khung ngày. Chỉ chọn một nơi nổi tiếng bình minh không phải tín hiệu muốn dậy sớm.
- `days.py` chỉ còn các số hạng rủi ro mà `objectives.metrics` đọc: `day_risk`, `exposed_risk`, `repeats`, `pref_risk`.
- Ghim: anchor giờ cố định ghim ngày + giờ; nơi chỉ mở vài ngày trong chuyến ghim ngày; `locked` cùng ngày người dùng đã chỉ định không đổi. Nơi không vào được ngày nào trả về `leftover`, không bị bỏ ngầm; nơi người dùng bắt buộc đi vẫn được đặt dù không vừa (kiểm tra cuối nói rõ).

### ⓒ Thứ tự trong ngày — `route.py`

- Mỗi ngày mở và kết ở chỗ ở, kể cả ngày đầu và ngày cuối.
- n ≤ `exact_n` (7) nơi mỗi ngày → **vét cạn permutation** (≤ 5040), chấm bằng mô phỏng đầy đủ → tối ưu thật. n lớn hơn → nearest-neighbour + 2-opt + or-opt. Cả hai tất định. Mỗi lần tìm thứ tự tái sử dụng giờ mở, cửa sổ ghim và quy tắc giờ ghé của ngày; cache điểm theo nơi/giờ đến/giờ đi và chặng có hướng, mỗi bảng kết quả tối đa `cache_entries`. Cache này kết thúc cùng lần tìm thứ tự, không dùng lại qua thay đổi bối cảnh; validator vẫn kiểm độc lập.
- Bảo đảm của tìm thứ tự: kết quả không bao giờ tệ hơn nearest-neighbour hay thứ tự seed theo `DayResult.key` (số vi phạm, bữa ăn bị lỡ, giờ kết thúc + phạt giờ) vì tìm kiếm cục bộ bắt đầu từ cái tốt hơn trong hai (test `test_the_order_is_never_worse_than_nearest_neighbour_or_the_given_seed`). Quãng đường ngắn hơn không phải là điểm: thứ tự nearest-neighbour làm mất bữa tối hay giờ mở cửa thì thua. Ca `short_by_40` (1 ngày quá tải): trong 720 thứ tự chỉ 12 thứ tự không vi phạm, ít xe nhất là 118′; nearest-neighbour 98′ nhưng lỡ bữa tối. Check `travel_vs_nn` vì vậy chỉ so với nearest-neighbour khi thứ tự đó chạy qua đồng hồ của engine không tệ hơn ngày đã xếp.
- Buổi: `pins` (`config/planning.yaml`: `sunset_view`, `cloud_hunting`, `live_music`) + `sun_times` → hoàng hôn / đêm ghim cuối ngày; sương / bình minh ghim đầu ngày. Một nơi có nhiều tính năng theo giờ chỉ cần **một**, không lấy giao: nếu người dùng muốn (soft weight dương) một trong số đó thì chỉ giữ các ghim được muốn (`build.prepare`), còn lại ưu tiên khung nằm trong ngày. Khung mà giờ mở cửa của chính nơi đó không chứa nổi (nhạc 18:00 ở quán đóng 18:30) thì không ghim. Ngày nào vẫn hỏng vì hai nơi cùng muốn một buổi → bỏ ghim của nơi xếp muộn nhất trước, tới khi ngày đạt, kèm cảnh báo `pin_dropped`; nơi đó vẫn được ghé, chỉ không đúng giờ đẹp nhất.
- Bữa ăn: tối đa ba khung sáng / trưa / tối trong ngày thực tế. Mỗi điểm có activity `eating` chiếm một khung riêng, ưu tiên trưa / tối và phải hợp giờ mở, giờ ghim, ngày đến / đi. Các điểm ăn được xếp riêng để chia sang ngày có khung phù hợp; không còn khung thì báo `meal_window`, không chuyển ngầm thành tham quan. Giờ đẹp nhất (hoàng hôn, nhạc sống) chỉ là mong muốn mềm: khi giờ đó rơi ngoài mọi khung bữa, bộ chia ngày (`layout._Day._slots_for`) vẫn cho quán nhận khung bữa và đồng hồ ngày bỏ ghim (`pin_dropped`), không để quán bị xếp vào "quá tải" chỉ vì ghim. Quán được nhận diện là bữa sáng từ tên/món/nhóm thực đơn chỉ nhận khung sáng, kể cả gợi ý lấp bữa; không đổi thành bữa trưa. Validator kiểm tra lại độc lập.
- Activity đã chỉ định trong chuyến thắng mặc định của địa điểm. Khi chưa chỉ định, café dùng `coffee`, nhà hàng dùng `eating`; Decision ghi ý định suy ra vào output, không mở câu hỏi meal và không sửa Place Intelligence. `usable_as: meal` không tự biến café thành nhà hàng.
- Khung chưa có điểm ăn thành `meal_free`, thời lượng lấy từ `meal_durations`. Chừa bữa trước visit dài có thể nuốt hết khung; nếu chuyến tham quan kết sớm vẫn hiện bữa còn lại dưới dạng tùy chọn, trong giới hạn ngày. Không bịa nhà hàng. Web gợi ý ăn ngoài hoặc hỏi chỗ ở có phục vụ bữa đó; dịch vụ và giá chưa xác nhận.

### ⓓ Giờ, tham quan, đệm, nghỉ — `schedule.py`

Visit theo pace: thong thả → `long`, cân bằng → `typical`, đi nhiều nơi → `short`. Coffee, ăn và uống chỉ lấy `long` khi có sở thích dương khớp địa điểm đạt `duration_preference_weight`; pace thong thả đơn thuần dùng `typical`. Thời lượng là một khoảng ước tính: mức đã chọn không vừa ca mở cửa, khung bữa ăn hoặc phần còn lại của ngày thì rút dần về mức `short`, không thấp hơn. Kiểm tra độ vững (`robustness.py`) không rút, để "trễ 15 phút" vẫn đo đúng. Đến sớm → `wait`; quá giờ đóng → vi phạm. Đệm = `buffer_min[pace]` + phụ phí theo độ không chắc (mưa, chặng dài, giờ `UNCERTAIN`). Nghỉ chèn theo pace, và chặn "đi liên tục quá `max_consecutive_min` mà không nghỉ". Điểm dừng thiếu giờ mở theo ngày hoặc có trạng thái `UNCERTAIN`/`OUTDATED` mang ghi chú **Chưa rõ giờ mở** ngay trên item, không coi giờ ước tính là đã xác nhận.

**Ngưỡng nới cuối của thời gian ghé** (chủ dự án 18/11/2026). Khi lịch chật, đồng hồ ngày rút thời gian ghé trước khi bỏ một nơi: từ mức của pace xuống dần tới `short` của nơi đó, **không bao giờ dưới `short`**. `short` là ngưỡng nới cuối; thời lượng người dùng tự đặt (`set_visit_duration`, `source: user`: cả ba mức bằng số phút đó) không bao giờ bị rút. Chỉ khi rút hết về `short` mà vẫn không vừa mới là quá tải (§Quá tải). Lịch vừa nhờ rút có một dòng Lưu ý `visit_shortened` trên thẻ: "Để vừa lịch, mình rút ngắn thời gian ghé: Ga Đà Lạt bớt 20′, …" (`build.shortened_warnings`, chỉ nêu nơi bớt từ `SHORTENED_MIN` 10′; số phút lấy từ `time_suitability.shortened_min`). Test `tests/planning/test_planning_fast_plan.py`.

### Độ phù hợp giờ ghé — `timefit.py`, `recommendations.py`

Chấm **toàn khoảng visit** theo hoạt động đang chọn và `context.purpose`; không dùng độ nổi tiếng để suy ra giờ đẹp. Ưu tiên buổi có evidence của user thắng heuristic; ưu tiên riêng cho POI thắng ưu tiên chung cho hoạt động. Hoạt động đã chỉ định rõ không bị đổi theo category. Thiếu giờ mặt trời cho sunrise/sunset → chưa chấm được, không bịa giờ.

Mặc định mềm từ config: sáng 08:00–11:00 cho anchor/hoạt động tốn sức; giữa trưa 11:30–14:30 cho coffee/nghỉ; chiều 14:30–17:30 hoặc sáng cho đi dạo/vườn; tối từ 18:00 cho nightlife/bar. Chụp ảnh ngoài trời ưu tiên ánh sáng ban ngày; giờ ăn do `meal_windows` quyết định; người dùng nói giờ ăn (`frame.meals.by`, ví dụ bữa tối bắt đầu trước 18:00) thì `build.meal_windows_by` dời giờ bắt đầu muộn nhất của bữa đó về giờ ấy (giờ sớm nhất lùi tối đa còn trước đó 60 phút) cho riêng chuyến. Chợ không tự được coi là chợ đêm. Đây là ước lượng có thể cấu hình, không phải nghiên cứu sinh lý hay Fact của địa điểm.

Phạt tính theo phần visit ngoài cửa sổ và phần thời lượng đã rút. Bộ xếp giờ thử đến sớm nhất và đầu cửa sổ ưu tiên, có thể rút tới `short`, giữ giờ mở, bữa ăn, giờ ghim và constraint. Nếu chờ giờ đẹp gây vi phạm hoặc lỡ bữa, thử lịch đến sớm nhất; replay thu gọn thử cả buổi ưu tiên và giờ sớm, rồi so tổng phí. Vẫn giữ guard nhịp: visit không ghim, không phải bữa chính không bị rút khi ngày còn giờ rỗi dài. Phí này tham gia chọn thứ tự và chia ngày. Không tự bỏ nơi đã chọn; thiếu thời gian được báo qua overload.

`time_suitability` giải thích giờ ghé, phần phù hợp, nguồn user/heuristic và phút rút. `recommendations` báo khoảng trống hoặc quá tải. Gợi ý địa điểm chỉ lấy ID thật chưa ghé từ `backup_pool`, kế thừa hoạt động của nơi được thay; thử chèn rồi validate toàn lịch, hard constraint và ngân sách. Cả gợi ý này và pool lấp chỗ (`ghosts`) loại `DecisionOutput.hidden_ids`; không loại nơi đã được người dùng tự chọn. Gợi ý thêm dùng người đi cùng và `details.fit`/suitability đã xác minh để xếp hạng; không chủ động gợi ý bar/uống rượu khi có trẻ nhỏ. Thiếu bằng chứng phù hợp giữ trung tính; ràng buộc safety unknown giữ cờ và xếp sau nơi đạt theo §Guardrail. Đây là prior cho gợi ý, không thêm hard constraint vào lựa chọn của người dùng. Không có ứng viên phù hợp vẫn có thể gợi ý nghỉ. Chỉ act của user mới thêm nơi; thêm sẽ xếp lại ngày và có undo. Tắt `time_suitability.enabled` tắt cả scoring, phí rút và gợi ý này.

Các thẻ sau khi chọn chỗ ở giữ bản nháp theo neo, giá và ma trận có hướng. Khi đổi neo và chưa sửa pace, objective hoặc khung ngày, phương án quá tải được chọn lại tập con theo chỗ ở mới; selection gốc trong Decision Output giữ nguyên. Timeline đang chọn và các chỉnh sửa riêng vẫn được kiểm lại, không tự áp dụng tập con mới. Chọn thẻ chưa có chỉnh sửa riêng dùng đúng timeline đó; `metrics`, bảng so sánh và lịch chi tiết cùng nguồn. Giá chỗ ở cộng đúng một lần vào giá đã biết; chỗ ở chưa có giá được tính là unknown ở cả thẻ và kết quả chốt. `time_budget` khi chốt dùng khung ngày hiện tại sau sửa. Phút tham quan, di chuyển và bữa tự chọn được đo từ các item thực tế; giá bữa tự chọn chưa được xác nhận.

Giảm độ trễ: composer tái sử dụng lịch của cùng tập địa điểm trong một lượt tìm; thẻ theo chỗ ở và phần hiển thị của lịch hiện tại dùng cache có giới hạn. Read hoặc chọn thẻ không đổi bối cảnh không chạy lại bộ xếp lịch, robustness và backup. Đổi tọa độ, giá hoặc chặng di chuyển làm mất hiệu lực cache; validator vẫn kiểm lại trước khi chốt.

### Chi tiết địa điểm — `details.py`

Khối `details` của bản ghi serving (`docs/CORPUS.md` §Chi tiết địa điểm) đổi lịch như sau; nơi không có dữ liệu giữ hành vi cũ.

| Dữ liệu | Tác dụng | Nơi |
|---|---|---|
| `cost.total_vnd` | `cost_of` lấy `base` (vé + gửi xe, một người) thay cho giá vé ước tính; giá theo xe / nhóm (`per_party`) chia cho `people` của chuyến (đi một mình trả cả xe). `metrics.extras_max_vnd` = Σ (`with_extras` − `base`): tối đa các khoản thêm có thể cộng | `places.py`, `objectives.py` |
| `timing.best_time` / `avoid_time` | Điểm thưởng `timing_bonus` và phạt `timing_penalty` theo tỷ lệ **toàn bộ khoảng ghé** nằm trong buổi người đi trước khuyên / khuyên tránh. Phần giao của hai loại khung triệt tiêu; phần ngoài khung trung tính. Chỉ khi `time_suitability.enabled` | `timefit.py`, `details.py` |
| `timing.last_entry` | Nguồn official là giờ bắt đầu muộn nhất (cứng, nằm trong `pin_window`, nên cả bộ xếp lịch lẫn `validate` đều tôn trọng); nguồn review chỉ cảnh báo `last_entry_review` | `schedule.py`, `details.py` |
| `night_road_risk` | Xe máy + visit kết thúc sau hoàng hôn + giá trị đã xác minh: thêm `night_road_penalty` và cảnh báo `night_road` (không có giờ hoàng hôn thì không chấm) | `timefit.py`, `details.py` |
| `best_months` / `avoid_months` | Tháng của ngày trong `avoid_months`: cảnh báo `season_avoid` và lý do dự phòng `season` (nơi thay không được nằm trong tháng tránh); trong `best_months`: dòng "đúng mùa đẹp" ở checklist | `backup.py`, `details.py` |
| `relations.quieter` | Ngày `crowd = peak` và nơi nhạy đông: nơi vắng hơn cùng kiểu được xếp lên đầu danh sách thay | `backup.py` |
| `bring`, `booking`, `scam_stage`, `cold`, `fog_blocks_view`, `schedule` | `checklist` chuẩn bị theo ngày và nơi; dòng sương mù chỉ có khi nguồn thời tiết báo `fog` cho ngày đó (nguồn hiện tại chưa có trường này nên chưa bao giờ hiện); `schedule` khi thứ của ngày trùng lịch cố định | `details.py` |

Mỗi phương án (`variants.py`) mang `checklist` và các cảnh báo mới trong `warnings`; Plan Output giữ lại đúng những thứ đó.

### ⓔ Kiểm tra cuối — `validate.py`

Đường đi giữa các điểm cũng được kiểm lại từ timeline (`_road_gaps`, loại `travel`): từ điểm bắt đầu ngày, mỗi chặng và mỗi lượt ghé phải bắt đầu đúng nơi chặng trước kết thúc; ngày có điểm ghé phải có chặng về điểm kết thúc. Lịch "dịch chuyển tức thời" giữa hai nơi xa nhau không còn qua được (trước đây chỉ kiểm độ dài từng chặng có sẵn, không kiểm chặng bị thiếu).

`context.diet_days` ghép vào `DayCtx` theo ISO date, không thành hard filter toàn chuyến.
Ngày áp dụng, mỗi bữa phải có món chay/thuần chay đúng feature, trạng thái `VERIFIED`, qua public
`requirements`; một thành viên ăn chay chỉ cần quán có món chay, không cần quán thuần chay.
Chỉ quán có **bằng chứng không có món** (`fail`) là vi phạm (ghi ngày và người/cả nhóm, không chịu `relaxed`)
và chặn chốt. Quán chưa rõ (unknown, `UNCERTAIN`/`OUTDATED`) và bữa tự chọn/thiếu quán **không chặn** (chủ dự án
04/11: chưa rõ thì hiện + cảnh báo): `diet.warnings` cho mỗi ngày áp dụng một dòng `diet_unknown` (quán chưa rõ, nhắc
hỏi quán) hoặc `diet_meal_open` (bữa chưa có quán đã xác minh, ô ăn có gợi ý quán đã xác minh), ghi "Ngày N (ISO date)"
và người. Chia ngày ưu tiên ngày đáp ứng; không tự thêm nơi. `ghosts`, `recommendations` và quán dự phòng chỉ gợi ý
quán đạt cho ngày đó; ngày khác không lọc.
Cache ngày bao gồm `diet_days`; phiên lưu/khôi phục giữ nguyên context này. Quán đã chọn bị `fail` giữ thẻ nháp `editable`, có vi phạm theo ngày/người và chưa thể chốt; không tự đẩy người dùng về Lựa chọn. `recovery_actions` có thể đề xuất một action `repair_meals` thêm các quán thật từ pool gợi ý: chỉ đưa ra khi lịch thử qua toàn bộ validator và đủ nơi đã chọn. Khi bấm, engine kiểm action còn được đề xuất, dựng lại và kiểm toàn lịch trước khi lưu; một lần undo hoàn tác toàn bộ nhóm bữa.

Lịch đầy đủ (`DayCtx.require_meals = True`) phải có bữa tương ứng với khung ngày và mỗi visit dài ít nhất `visit.short`. Validator lấy visit từ `items`, kể cả khi `DayResult.order` trống. Cache kiểm ngày xét record của các visit thực tế và thời gian giữa các endpoint travel; đổi giờ mở, thời lượng hoặc chặng không dùng kết quả kiểm cũ.

Nơi **duy nhất** kết luận đạt / không đạt, và kết luận từ chính dòng thời gian cuối cùng. Kiểm tra: ngày đi · giờ mở cửa · chồng lấn · thời gian di chuyển · anchor · hard constraint · địa điểm trùng (cùng **một** nơi xếp hai lần). **Ngân sách không chặn, không cắt** (chủ dự án 04/11): engine gọi `validate` với `NO_BUDGET_CAP`; `validate.budget_warnings` thêm một dòng `budget_over` mỗi ngày chi phí ước tính/người vượt `budget_vnd` (VND/người/ngày), nêu số vượt và 2 nơi tốn nhất để người dùng tự bỏ/đổi. Giờ đẹp (ghim) mà chính ngày đó không thể có (`schedule.pin_hostable` sai: hồ hoàng hôn dời sang buổi sáng ngày cuối) không phải vi phạm `timed`: bản dựng bỏ ghim và `pin_warnings` báo `pin_dropped`; layout vẫn ưu tiên ngày giữ được giờ (khoá `miss`). Quán ăn không nhận ghim mặt trời (bữa ăn giữ giờ bữa), chỉ ghim giờ đồng hồ. Hai nơi "gần trùng" (cùng kiểu, `PLACE_DECISION.md` §9.1) mà người dùng vẫn giữ là lựa chọn của họ: chỉ cảnh báo `near_duplicate`, không chặn. Kiểm "đúng giờ đẹp nhất" (hoàng hôn, bình minh, nhạc): nơi nào bộ xếp lịch đã bỏ ghim giờ để vừa ngày (cảnh báo `pin_dropped`) được ghi trong `DayResult.unpinned`, và mọi lần kiểm lại, kể cả lúc xác nhận, tôn trọng đúng quyết định đó, nên kế hoạch đã hiện ra là hợp lệ thì xác nhận được. Cảnh báo `pin_dropped` viết ngắn ("{nơi} không kịp vào đúng giờ đẹp nhất, mình xếp lúc khác trong ngày"); chỉ thêm "Giữ giờ đó thì vướng …" khi lý do thật sự của nơi đó: giờ mở cửa chưa biết (`hours = None`) không bao giờ là lý do (không thể vi phạm điều chưa biết). Thêm một kiểm `hazard` (nơi bị thời tiết rất xấu hay thông báo `severe` loại khỏi ngày, xem §Điều kiện từng ngày). Trả `ok` + danh sách vi phạm, mỗi vi phạm có `physical: bool` và cái giá đã tính của từng cách sửa. Không phương án nào hợp lệ (vi phạm kể cả vật lý như `hazard`, `hard`) → vẫn mở **một bản nháp mở được** (`editable = true`, `confirmable = false`) với vi phạm ghi ngay trên dòng của nó (`violations`), không có màn rỗng. Vi phạm là **cảnh báo, không phải cổng**: người dùng quyết định cuối cùng, `confirm` chốt được bản có vi phạm và đưa chúng vào Plan Output (`violations`); Web hỏi lại một lần ("Chốt kế hoạch còn cảnh báo?") rồi chốt (chủ dự án 2026-11-08). `confirm` chỉ từ chối khi chưa có phương án, thiếu chỗ ở bắt buộc, còn nơi chưa xếp được hoặc nơi bắt buộc không xếp được.

### ⓕ Độ vững — `robustness.py`

Nhiễu cố định trong config, không random: xuất phát trễ +15 / +30 phút; visit +20%; travel +25%; mưa theo xác suất dự báo. Mỗi kịch bản chạy lại thứ tự đã chọn của từng ngày và đếm số nơi bị mất (ngoài giờ mở, hoặc sau nó không kịp về điểm kết ngày; đệm là thứ hấp thụ trễ). Mưa không random: nơi phơi mưa ở ngày `rain_prob ≥ rain_high` tính là mất; không có dự báo thì bỏ kịch bản này và nói rõ. Ba mức — **Vững** (đủ đệm để chịu vài chậm trễ nhỏ), **Khả thi** (chạy được nếu phần lớn đúng giờ dự kiến), **Mong manh** (đúng về toán nhưng một chậm trễ nhỏ làm hỏng các điểm sau): Vững = mọi kịch bản mất ≤ `solid_max_lost`; Khả thi = các kịch bản `tier: small` mất ≤ `feasible_max_lost`; còn lại Mong manh. `travel_source = rough` → trần "Khả thi".

### ⓖ Mục tiêu và phương án — `objectives.py`, `variants.py`

**Nhịp độ và mục tiêu là hai thứ riêng.** Nhịp độ (`pace`: thong thả · cân bằng · đi nhiều) mô tả cường độ chuyến đi và đổi thành tham số: thời gian tham quan, số nơi mỗi ngày, thời gian nghỉ, độ lớn đệm, mức di chuyển chấp nhận. Mục tiêu mô tả tối ưu theo cái gì.

Năm mục tiêu: `least_travel`, `low_cost`, `weather_robust`, `diverse`, `preference_fit`. Chọn tối đa 3 bằng rule từ Trip State (pace; `budget_vnd` đã biết?; tháng mưa?; `soft_weights`) — không cố định trước.

`metrics.time_penalty` đo phí giờ ghé. `score` giữ hai thành phần: mục tiêu chính, rồi `travel_min + time_penalty` để phân biệt phương án cùng điểm chính.

```
for lodging in K+1 ứng viên:          # 6 + phương án không chỗ ở
    for obj in mục tiêu đã chọn:      # ≤ 3
        p = schedule(layout(places, lodging, obj), obj)
        if validate(p).ok:
            score[(obj, lodging)] = obj.score(p), robustness(p)
best mỗi obj → 2–3 phương án; bỏ phương án trùng (cùng chỗ ở + cùng thứ tự mọi ngày)
```

21 lần dựng lịch mỗi lượt (K+1 chỗ ở × tối đa 3 mục tiêu), dùng chung một ma trận OSRM (toạ độ ứng viên nằm
trong CÙNG ma trận đó) và cache thứ tự theo ngày (khung giờ, điểm mở/đóng), pace, mặt trời, mưa và tập nơi (activity, pins, visit, short) — đổi chỗ ở chỉ đổi
điểm mở/đóng ngày, không chia lại ngày. Mỗi mục tiêu giữ tổ hợp (chỗ ở, lịch) tốt nhất riêng cho nó.
Ngân sách: **< 2 s** khi cache nóng, đo trong `evaluate.py`.

### ⓗ Dự phòng — `backup.py`

Nơi nhạy cảm = ngoài trời + ngày mưa xác suất cao · giờ `UNCERTAIN` / `OUTDATED` · sát giờ đóng · ở khu vực xa. Thay thế lấy từ `backup_pool` (Decision đã kèm `for` + `reason`): cùng khu vực, cùng nhóm, qua được constraint. Không có → nêu rõ "không có phương án thay".

## Đổi lịch tối trước ngày đi — `eve.py`

Sau cờ `eve_replan.enabled` (`config/planning.yaml`). Đo trước khi bật: `tests/planning/eve_scenarios.py` (kết quả `logs/planning_eve/`); test `test_planning_eve_scenarios.py` không cho bật cờ khi bộ kịch bản trượt.

```mermaid
flowchart LR
  F[yếu tố mới] --> A[assess: mức 0–3 từng điểm]
  A -->|0–1| N[ghi chú]
  A -->|2–3, mức tăng, chưa từ chối| R[repair]
  R --> V[Engine.eve_trial + assess lại]
  V --> P[đề xuất chờ chọn theo plan_hash]
```

**Yếu tố** (`Factors`, mỗi nguyên nhân mang `source` + `retrieved_at`): thời tiết theo giờ ở toạ độ từng điểm (`live.weather_hourly`; giờ có số ngoài miền vật lý bị coi là chưa biết, xem cổng tool ở §Local Expert), `Notice` trên chặng qua đèo (bước OSRM có tên bắt đầu bằng `pass_prefixes`) hoặc ở chính điểm, `Event` peak, nơi đóng cửa, khung ngày mới khi giờ đến / đi đổi (`trip_windows`: đến muộn hơn hoặc đi sớm hơn lúc lập lịch, ở Trip hoặc ở màn lịch; đến sớm hơn, đi muộn hơn, giờ không rõ hay đổi sang ngày khác không tạo yếu tố). Nguyên nhân nơi đã bị gắn cờ trong `backups` lúc chốt hạ còn mức 1.

**Độ nhạy** (`sensitivity`, chỉ từ feature): `exposed` / `sheltered` (`weather_exposed`, rồi `setting`), `clear_sky` (`cloud_hunting`, `sunset_view`, `scenic_view`, `fog_blocks_view`), `slope` (`steep_or_stairs`, `rough_road_access`), `crowd` (`crowd = high` hoặc `crowd_by_time` ngày lễ ≥ `crowd_busy_pct`).

| Mức | Khi nào |
|---|---|
| 3 | ngoài trời + dông trong khung / mưa ngày ≥ `severe_rain_mm` / gió ≥ `severe_gust_kmh`; `Notice` severe trên chặng đèo hoặc ở điểm; đóng cửa; điểm rơi ngoài khung ngày mới |
| 2 | trong khung ghé mưa ≥ `rain_prob` **và** ≥ `rain_mm` mm với nơi ngoài trời, cần trời quang, hoặc dốc / bậc; gió ≥ `heavy_gust_kmh` (ngoài trời); sương mù ở nơi cần trời quang; mưa lớn giờ trước khi qua đèo; `Notice` thường trên chặng đèo; `Event` peak × người tránh đông × nơi đông |
| 1 | mưa nhẹ ở nơi ngoài trời; mưa ở nơi có mái / chưa rõ; lễ hội đông với người không tránh đông |

Thiếu dữ liệu không thành nguyên nhân: dự báo `None` không bao giờ thành báo động. Hai model lệch (`disagree`) → nguyên nhân thời tiết tối đa mức 1.

**Sửa tối thiểu** (`repair`, chỉ mức 2–3), thử theo thứ tự, mỗi loại giữ một phương án đổi ít điểm nhất: dời giờ trong ngày (`reorder`) → đổi chỗ với một điểm chưa bị ảnh hưởng của ngày khác chưa tới (hai `move_place`; nguyên nhân thời tiết thì ngày đích phải có dự báo cho điểm đó) → nơi trong `backup_pool` (có mái trước, `swap`) → bỏ điểm (`drop_place`, chỉ mức 3). Khi nguyên nhân là khung ngày mới, hai loại đứng trước: `relay` (xếp lại đúng các điểm đó trong khung mới) và `trim` (bỏ cùng lúc tập điểm nhỏ nhất không kịp trong khung, validator chấp nhận; tính một lần cho cả ngày). Nơi bắt buộc chỉ được dời, không thay, không bỏ. Mức 2 luôn có "Giữ nguyên" (mặc định); mức 3 không có. Mỗi phương án = lịch thử `Engine.eve_trial` (chỉ nhận bốn action trên, không có `relax` → physical constraint không nới; validator như mọi lần sửa, mọi nơi đã chọn phải còn chỗ) **và** `assess` lại với yếu tố mới: điểm được sửa còn < 2, không điểm nào khác lên ≥ 2. Lỗi bất kỳ → bỏ phương án. Chữ cho người đọc (`text` của nguyên nhân và phương án): tên nơi qua `placename.short_name` (bỏ chữ ngoài Latin, ngoặc rỗng, phần thành phố, câu quảng cáo sau dấu `-` / `|` / `,`; không thêm chữ nào ngoài tên trong corpus), nguồn và giờ tra nằm ở `source` / `retrieved_at`, không nằm trong câu. "Điểm bị đổi" = vào / ra lịch, đổi ngày, đổi thứ tự trong ngày; điểm chỉ lệch giờ theo hàng xóm nằm ở `shifted`.

**Chống báo thừa** (`check`): chỉ hỏi về ngày mai (`notify_days`), chỉ khi mức của một điểm tăng lên 2–3 so với lần kiểm trước của cùng `plan_hash`, và nguyên nhân (`key` = yếu tố:điểm:ngày) chưa bị từ chối; D-2..D-`note_days` và mức 1 chỉ là ghi chú. `Store` lưu `data/planning/eve/<journey>.json`: mức, đề xuất chờ chọn và `notes` (điều đã thấy nhưng không hỏi: mức 1, ngày xa) theo `plan_hash`, nguyên nhân đã từ chối theo journey.

**Thu yếu tố** (`gather`, biên I/O): `live.weather_hourly` theo ô lưới 0,02° mỗi ngày cho mọi điểm và nơi dự phòng; `live.events`, `live.advisories` (→ `notices`), `live.holidays` hoặc sự kiện `closure_risk` (→ `holiday`: ghi chú mức 1 cho nơi có giờ chưa xác minh, không phải đóng cửa); `live.route_steps` chỗ ở → các điểm (→ `passes`); `closed_now` = record đang phục vụ có giờ đã xác minh không phủ khung ghé hoặc trạng thái đóng (`CLOSED`, `PERMANENTLY_CLOSED`, `DISABLED`); ngày lễ chỉ là bằng chứng đóng cửa khi có một trong hai điều đó; giờ đến / đi đổi = `day_window_override` của phiên khác `time_budget` của lịch đã chốt, cộng `trip_windows` so Search Input hiện tại của journey (`outputs.trip`, notify truyền vào) với bối cảnh lúc lập lịch; mỗi phương án (trừ giữ nguyên) mang thêm action `set_day_window` đứng đầu, nên nhận phương án là ghi khung mới vào phiên. Nguồn lỗi → phần đó trống (chưa biết).

**Nối** (chỉ khi cờ bật): job `python -m notify run` gọi `check_eve` từ `eve_at` (20:00, `config/notifications.yaml`), mỗi chuyến mỗi tối một lần khi ngày mai là ngày của chuyến → `planning.eve_runner` → `run_eve` (khôi phục phiên Planning từ snapshot của journey, `gather`, `check`, lưu chờ chọn) → thông báo kiểu `eve_replan` khi có điều cần hỏi, theo giới hạn `notify.decide`. Harness: `GET /api/harness/sessions/<jid>/eve` (chờ chọn + `notes` của lịch hiện tại + có hoàn tác không; web hiện `notes` thành dòng lưu ý, tối đa 4), `POST` `operation`: `accept` (cần `confirmed: true`; các action của phương án rồi một lần chốt, lỗi thì hoàn lại), `decline` (chỉ mức 2; nhớ nguyên nhân), `undo` (về lịch trước phương án vừa nhận). `GET .../eve` luôn 200 `{enabled, pending, notes, undo}`: cờ tắt hoặc chưa chốt lịch thì `enabled: false` / danh sách rỗng, không phải lỗi (các `POST` vẫn 409 khi cờ tắt). Web: banner trên `/app/plan` (`web/src/user/screens/plan/EveBanner.tsx`), không hiện gì khi `pending` và `notes` rỗng.

Thông báo của chuyến mở màn lịch đã chốt `/app/plan?journey=<id>` (`config/notifications.yaml` `links`); thông báo tối trước chuyến đọc dự báo ở điểm đầu của ngày 1, không có thì ở chỗ ở, không có nữa thì không đoán (`notify.plan.trip_point`).

## Local Expert — `expert.py`

Một lượt LLM **sau validator**, trên lịch đã chốt, chạy **nền** trong worker `notify` (`Notify.check_expert` → `expert.run_expert`), **không bao giờ chặn lúc chốt**: `Tools.apply confirm` không gọi nó, thời gian chốt không đổi. Cờ `expert.enabled` trong `config/planning.yaml` **bật** từ 2026-10-29.

```mermaid
sequenceDiagram
  participant U as Người dùng
  participant C as confirm
  participant W as worker notify (mỗi phút)
  participant S as data/planning/eve/<journey>.json
  U->>C: Chốt lịch
  C-->>U: Lịch (không chờ Expert)
  W->>W: chuyến chưa kết thúc, chưa có lượt Expert cho plan_hash
  W->>S: review → expert_notes (factor local_expert, mức 1)
  U->>S: GET /eve → ghi chú trên màn Lịch trình
```

Kết quả vào **ghi chú** của màn Lịch trình (cùng chỗ ghi chú mức 1 của kiểm tra tối trước ngày đi; `EveStore.get` gộp `notes` + `expert_notes`, bản của Expert không bị ghi đè bởi các tối kiểm tra). Mỗi `plan_hash` chạy một lần; lỗi thì thử lại tới `expert.retries` lần rồi thôi. Gợi ý sửa không đưa thành lựa chọn ở đây: đổi lịch là việc của kiểm tra tối trước ngày đi.

```mermaid
flowchart LR
  P[lịch đã qua validator] --> F[sự kiện · ngày lễ · mùa của nơi · LocalClaim kept · ghi chú]
  F --> M[Extractor: Gemma LAN, lỗi thì UIT]
  M --> G{cổng: slot có thật,<br/>mọi trích dẫn có trong prompt}
  G --> R[gợi ý sửa chạy qua validator]
  R --> W[cảnh báo trên lịch]
```

- Model **không phải nguồn**: finding `{slot_ref, message, suggestion, cites}` chỉ giữ khi slot có trong lịch và mọi `cites` là id fact đã đưa vào prompt (claim → `doc_id` có thật). Không trích dẫn được → bỏ.
- Fact chỉ lấy từ code: sự kiện / ngày lễ (`live`, `CalendarDay`), mùa tốt / tránh của nơi, `LocalClaim` trạng thái `kept` / `confirmed` (chỉ claim về thành phố/khu vực theo ngày, hoặc claim nêu đúng tên một điểm dừng; claim "nếu mưa" chỉ khi ngày đó mưa chắc), thời tiết.
- Cổng tool (`expert.doubts`): thời tiết ngoài miền vật lý, lệch xa `ClimateNormal` của tháng (`gate.normal_gap`), hai model Open-Meteo lệch → fact gắn "nghi ngờ", model không được dựa vào. Cùng cổng chặn ở `eve.gather`: giờ có số ngoài miền vật lý thành "chưa biết"; độ lệch `ClimateNormal` áp ở `eve.assess`: xác suất mưa lệch ≥ `gate.normal_gap` so với mức thường của tháng (`Factors.normal`) mà **không** có cả hai model cùng xác nhận (`disagree` khác `False`) → nghi ngờ, nguyên nhân tối đa mức 1 (ghi chú, không báo động). Cả hai model đồng ý thì vẫn báo (mưa 85 % giữa mùa khô, hai model khớp → vẫn mức 2). Không có view `ClimateNormal` → không so.
- Gợi ý `move` / `drop` chỉ được kèm `actions` khi `Engine.eve_trial` (cùng validator) chấp nhận; không tự áp dụng; nơi bắt buộc đi (`anchor`) không bao giờ được gợi ý bỏ / dời.
- Giới hạn: `timeout_s` mỗi đường (LAN rồi UIT); lỗi / quá giờ / rỗng → lịch trả về nguyên vẹn.
- Đo 2026-10-29 (`tests/planning/expert_eval.py`, 4 chuyến tổng hợp, Gemma LAN thật, `EXTRACTOR_PARALLEL=8`, host đang chạy chuỗi build; log `logs/planning_expert/`): Noel 5,3 s · dã quỳ ngoài mùa 4,4 s · tháng 7 mưa 12,3 s (3 finding) · ngày yên tĩnh không có fact → không gọi model (0 s). 3/3 chuyến có finding đúng chủ đề, mọi trích dẫn có thật. Các con số này nay nằm trong worker nền, không cộng vào thời gian chốt; mỗi đường chờ tối đa `timeout_s` (LAN rồi UIT).

## Chỗ ở không làm người dùng chờ

Crawl Maps mất giây đến chục giây, nên không chặn màn hình:

```
xác nhận địa điểm → dựng nháp với base (chỗ ở), xếp chỗ ở trong corpus nền
                 → chọn chỗ ở bắt buộc (đã đặt và có tọa độ thì dùng sẵn)
                 → tính các thẻ theo chỗ ở đã chọn, dùng chung ma trận
                 → chọn phương án bình thường / quá tải → sửa → chốt
```

## Vòng người dùng sửa và góp ý

User Web chỉ nhận `act`, tất định, không gọi model cho mỗi nút/chip. Khi xác nhận Decision, Web mở màn chọn chỗ ở trước; sau đó mới hiện thẻ bình thường hoặc các hướng quá tải. `recommend` trả `choose_hotel` khi phiên bắt buộc chỗ ở chưa có lựa chọn, và không tự chọn profile quá tải. “+ Thêm nơi” gửi `back` qua harness để về Decision trong cùng journey; lựa chọn được giữ. Contract và phiên ở `docs/AGENT_HARNESS.md`.

| Act | Việc | Chạy lại từ |
|---|---|---|
| `pick_variant(id)` | chọn một trong các phương án | — |
| `pick_lodging(id)`, `set_lodging(text, lat?, lng?)` | chọn chỗ ở ở màn riêng; tọa độ đã chọn hợp lệ được dùng trực tiếp, thiếu tọa độ mới `geocode`; `clear_lodging` bị chặn trong phiên bắt buộc chỗ ở | ⓑ |
| `set_lodging_budget(max_per_night)` | đổi trần giá → crawl lại | ⓐ |
| `move_place(place, day)`, `reorder(day, order)` | đổi ngày / thứ tự | ⓒ ngày liên quan |
| `drop_place(place, reason?)` | bỏ khỏi lịch | ⓔ + `repair_day` |
| `add_from_backup(place, day)`, `swap(a, b)` | thêm / thay từ `backup_pool` hoặc một nơi trong selection đã bị profile chừa | ⓒ–ⓔ ngày đó |
| `reoptimize` | dựng lại profile hiện tại quanh nơi đã khôi phục, khóa và nơi user đã bỏ | ⓑ |
| `make_room(edit, drop_places)` | áp dụng một chỉnh sửa cùng nhóm bỏ nơi do user chọn; chỉ nhận sau preview đã kiểm tra | ⓒ–ⓔ |
| `lock_slot(place)`, `unlock(place)` | ghim ngày / giờ | — |
| `set_pace`, `set_objective` | đổi tham số toàn chuyến | ⓑ |
| `set_day_window(day, start, end)` | đổi khung giờ một ngày | sửa ngày đó; không khả thi thì dựng lại phương án |
| `set_stop_time(place, start)` | đặt giờ bắt đầu chính xác `HH:MM` cho một nơi đang trong lịch; không đổi khung ngày/giờ rời đi | ⓒ ngày đó; vi phạm mới vẫn lưu và hiện thành cảnh báo; giờ chặn bởi giới hạn vật lý (hết ngày, giờ rời đi) thì nơi giữ giờ khác và kết quả tool có `time_not_kept` để trợ lý nói rõ |
| `relax(constraint, scope)` | nới **user** constraint, luôn kèm cái giá đã tính | ⓔ |
| `undo`, `redo` | về phiên bản khác | — |
| `confirm` | chốt → Plan Output | ⓔ + `place_live_status` |

`relax` không tồn tại cho physical constraint.

Mọi chỉnh sửa có thể xem trước qua `Engine.preview_act(sid, action)` hoặc read `preview-act`. Preview chạy trên bản sao runtime, không ghi state/history/output và không gọi crawl hay model. Kết quả mang token ràng buộc action và context; harness trả thêm revision hành trình. Khi gửi token, `act` chỉ nhận token còn mới và đúng action; `make_room` bắt buộc có token, các act legacy vẫn dùng được không cần preview. Web chỉ giữ response mới nhất của đúng session, revision và view; edit, đổi phiên hoặc tải lại view đóng preview cũ, kể cả response lỗi. Kết quả gồm delta, violations, khả năng confirm và tối đa một số đề xuất `make_room` trong ngân sách tìm kiếm. Đề xuất không tự bỏ nơi; user phải chọn rồi preview/apply riêng. `reoptimize` giữ các nơi restored/locked/assignment như `must`, coi nơi user đã bỏ là `banned`, và không chấp nhận tham số optimizer từ client. Log phiên lưu action public để restart/replay dựng lại cùng kết quả.

`keep_all` là lịch đối chiếu riêng, có timeline, lỗi validator, độ vững và chi phí địa điểm đã biết. Web cho chọn Giữ tất cả khi lịch gốc hợp lệ; API cho mở draft để xem lỗi, nhưng không cho confirm lịch vi phạm hoặc thiếu nơi chưa xếp được. Khi sửa draft, khả năng confirm được tính lại từ lịch hiện tại. Delta so với selection giữ cùng basis: thiếu dữ liệu hoặc đổi home thì phần không so được là `unknown`. Backup không góp vào utility selection được giữ; utility của backup theo sở thích không được ghi nguồn `decision_score`.

Phương án tiết kiệm giữ ít nhất `composer.alpha` giá trị selection, kể cả khi đổi một nơi lấy nơi khác. Khi so tập nơi, ưu tiên giảm `cost_unestimated` rồi giảm `estimated_cost_vnd`: giá hoàn toàn chưa biết không được thắng giá có bằng chứng nhờ tổng thiếu khoản đó. Giá nội suy chỉ lấy median từ cùng nhóm địa điểm và vẫn giữ `cost_unknown`; không biến thành giá đã xác minh. Các khoản bữa tự chọn và di chuyển chưa có giá tiếp tục hiển thị là chưa tính.

Backup đã thêm/thay giữ activity trong state và qua replay phiên. Đổi pace, mục tiêu, khung ngày hoặc chọn lại variant dùng tập nơi đang hoạt động, bao gồm backup và loại các nơi đã bỏ.

### Tính lại và cache

Kết quả tìm kiếm có deadline đã đưa ra cho người dùng được lưu JSON trong `Session.search_artifacts` (`artifacts.py`): thẻ gốc và thẻ trước khi chọn theo state. Restart/replay/undo dùng lại kết quả đã thấy thay vì chạy lại tìm directions với deadline mới; confirm vẫn kiểm toàn lịch. Không tăng deadline để giữ thẻ ổn định. Lưu artifact không được ghi đè lịch sử bằng state thử/preview. Worker `spawn` đếm số lần dựng lịch cục bộ rồi trả cùng kết quả (pool: giá trị trả về của việc; `_in_children`: pipe); không tạo semaphore cho bộ đếm sẽ bị bỏ finalizer khi worker hết deadline.

Ngày trống: `layout.assign` chuyển một nơi từ ngày đông sang ngày trống khi hai ngày mô phỏng (theo `_as_laid`: ghim ngày đó không giữ được thì bỏ như bản dựng) không vi phạm, đủ bữa, không tăng đường. `view.ghosts` bao phủ cả ngày chưa có visit và khoảng trống chưa có item (ngày không có điểm nào và chưa biết chỗ ở thì đo khoảng cách từ trọng tâm các nơi đã chọn của cả chuyến, nên vẫn có gợi ý; khoảng trống từ 21:00 là ô `late` "Ăn đêm (tự chọn)", gợi ý cả quán ăn đêm); ô ăn đầu ngày không cộng đệm sau điểm dừng, ô ăn trong khung cố định dùng được thời gian rảnh tới điểm kế (không chồng lên), ô ăn sáng ưu tiên quán có món sáng (`BREAKFAST_DISH_BONUS`): gợi ý là ID thật từ pool đã qua hard filter, kiểm ngày mở/hazard/diet và đủ thời gian ghé + đường đi. Không tự thêm vào timeline. Món chưa có visit hay ghost bữa trưa/tối được giải thích bằng `wish_unplaced`. Visit của chuyến có thú cưng mang note “Chưa rõ có cho mang thú cưng không” khi evidence unknown, giữ note cũ; allowed/no-pet không gắn. Builder dùng chung cho thẻ, view và output chốt.

Khung đến/rời có khoảng đệm được giải thích bằng `arrival_buffer`/`departure_buffer` trong warnings (kèm ngày và giờ). Thiếu điểm vào/ra thì nói rõ chưa kiểm chứng đường đi, không tạo chặng sân bay giả. Cảnh báo `lodging_requirement` được tính theo chỗ ở hiện tại cả view/confirm; undo không giữ cảnh báo của neo đã bỏ.

Act dựng state nháp, timeline, validation và view trước khi lưu. `view.metrics`, `view.robustness`, `view.backups` và `active_variant` phản ánh lịch hiện tại, kể cả khi user drop/restore/swap. `view.violations` báo các xung đột còn lại; mỗi lỗi có cảnh báo `plan_violation` trong `view.warnings`, nêu ngày/nơi, lý do chưa thể chốt và cách xử lý (hoàn tác, đổi giờ/thứ tự/ngày), không nới giờ rời đi hay yêu cầu bắt buộc. Cảnh báo được tính lại theo lịch, không lưu lỗi đã hết. Giá thiếu giữ `cost_unknown`. Lý do bỏ nơi được giữ từ thẻ gốc; thiếu metadata dùng mã `plan_excluded`, không xuất null thành chữ `None`. Confirm luôn kiểm lại toàn lịch, không dùng cache validation.

`repair_day` giữ thứ tự còn lại khi bỏ nơi và thử vị trí chèn khi thêm/thay một nơi. Kết quả local chỉ được chọn khi không vi phạm, không lỡ bữa và qua kiểm ngày; phí giờ ghé và diff chọn giữa các kết quả này. Nếu chưa đủ, dùng exact khi toàn bộ permutation nằm trong `repair_search_limit`, hoặc 2-opt/or-opt có giới hạn. Reorder mô phỏng đúng thứ tự người dùng; ngày khóa giữ assignment. Ngưỡng ở `config/planning.yaml` (`repair_local_additions`, `repair_search_limit`).

Cache chỉ trong RAM, mỗi bảng tối đa `cache_entries`: route, repair, timeline/metrics ngày, kiểm ngày, độ vững, kết quả tổng hợp và gợi ý. Key xét tập nơi/thứ tự, record, activity và tính explicit, visit/pins/relaxed, pace, ngày/khung giờ, ưu tiên giờ, config, di chuyển và live context. Weights chia ngày không làm đổi mô phỏng một ngày có cùng membership. Gợi ý còn xét ngân sách, tập nơi toàn chuyến, backup pool và chặng tới các backup; sửa dữ liệu đó không dùng kết quả cũ. Duplicate giữa ngày và anchor được kiểm mỗi lần tổng hợp.

Bộ nhớ của một chuyến (`Trip.routes`: ngày đã bố trí và thứ tự trong ngày) có giới hạn riêng `route_cache_entries` (4096), vì tìm phương án khi quá tải thử hàng chục tập nơi và lặp lại cùng một ngày. Key thứ tự trong ngày chỉ bỏ qua thứ tự chèn khi ngày không quá `realistic.seeded_exact_n` nơi (vét cạn, hạt giống không đổi kết quả); trên mức đó hạt giống là một phần của key (`build._seed_key`), nên kế hoạch không phụ thuộc kích thước hay lịch sử bộ nhớ. `repair_day` dùng cùng `_SimulationCache` như `order_day`, nên sửa một ngày cho cùng kết quả mô phỏng với lúc dựng ngày đó. `fingerprint` dùng orjson; ontology đọc một lần mỗi tiến trình (`feature_ontology`).

Khi quá tải, **ba hướng** `fit` (hợp gu nhất) / `cost` (tiết kiệm nhất) / `most` (nhiều trải nghiệm nhất: giữ nhiều nơi nhất) và đề xuất kéo dài ngày (`overload._extend`) chạy cùng lúc, mỗi việc một worker **spawn** của pool khởi động sẵn (`overload._pooled`; không thừa hưởng LanceDB / runtime native của server; dữ liệu chuyến qua đường dẫn file nhỏ), đều xuất phát từ lịch chính đã tính. Từ 18/11/2026 (chủ dự án) không còn hướng `travel` ("Di chuyển thuận lợi nhất"): mọi hướng đi qua cùng bộ xếp ngày và thứ tự, nên ít ngồi xe là thuộc tính của mọi hướng chứ không phải một lựa chọn; nhãn cũ giữ cho phiên đã chọn nó. Hai hướng ra cùng tập nơi thì gộp một thẻ (`merged`), màn chọn chỉ hiện các hướng khác nhau.

**Pool worker** (`overload.POOL_WORKERS` 8, `ProcessPoolExecutor` spawn): một interpreter mới nạp `planning` mất ~1 s, nhiều hơn phần lớn một hướng. Harness khởi động pool lúc warm-up (`planning.warm_workers`, `harness/__main__.py`); worker giữ code đã nạp tới lần restart (prod: `.prod_src/`), cấu hình đi theo `trip.cfg` mỗi việc. Một việc còn chạy khi hết hạn thì bị bỏ và cả pool bị giết (`_drop_pool`), lần tìm sau mở pool mới, nên không việc nào sống quá hạn chung. `_in_children` (một tiến trình mỗi việc) vẫn dùng cho ngữ cảnh `fork` của test.

**Preview của Lựa chọn không tìm hướng** (18/11/2026). `Engine.preview` dựng `plan_cards(trip, search=False)`: chuyến vừa thì như cũ; chuyến quá tải chỉ có lịch chính (nơi vừa được xếp, phần còn lại thành `leftover`), thẻ `main` `editable`, `confirmable = false`, thẻ quá tải `pending: true`, không hướng nào. Bản đồ ở Lựa chọn (`SplitPlan.tsx`) vì vậy hiện ngay. Cùng lúc engine tìm ba hướng ở nền (`_search_later`: luồng `plan-search`, 2 luồng; dùng lại trip và lịch chính của preview qua `quick`/`_main`, không dựng lại); việc tìm còn xếp hàng cho một lựa chọn cũ bị bỏ khi có lựa chọn mới. `create` lấy preview và **chờ** đúng việc tìm đó (`_take_preview`); preview chưa có việc tìm thì `create` dựng đầy đủ như trước. Preview không đổi sang một hướng sau khi tìm xong: bản đồ luôn là lịch chính. Engine không chạy nền (`background=False`: CLI, test) tìm đồng bộ ngay trong `preview`. Public API Planning nạp theo nhu cầu; worker xếp lịch không nạp chat/retrieval. Worker dùng lại cache ngày của lịch chính: `direction_workers` không thuộc key mô phỏng vì không đổi đồng hồ. Trong worker spawn, `_extend` thử hai phía tuần tự, không mở thêm interpreter; `direction_workers: 1` không tắt deadline hay chuyển tìm kiếm về tiến trình chính.

Hướng `most` ("Giữ nhiều nơi bạn chọn nhất", chủ dự án 13/11/2026) bỏ trước nơi chiếm nhiều thời gian nhất: nơi chưa xếp tính thời lượng ghé ngắn nhất (`visit["short"]`), nơi đã xếp tính phút nó giải phóng (`_freed`: thời gian ghé + đường đi bớt được); hòa thì bỏ nơi ít hợp gu hơn. Lý do trên thẻ: "chiếm 2h30 của lịch, tính cả đường đi" / "cần ít nhất 1h30, lịch không còn chỗ". Khi hai hướng khác ra cùng một lịch, `most` thường giữ cho màn chọn đủ ba lịch khác nhau. Đo 15/11/2026 (19 nơi / 2 ngày, spawn): 3 hướng 1,7–2,0 s, 27 lần `schedule_trip`; 4 hướng 2,7 s, 41 lần, vẫn xa hạn 15 s.

`confirm` của phiên quá tải chưa chọn hướng nào trả `NotConfirmable` (409, "choose a plan option before confirming"): bỏ nơi nào là lựa chọn của người dùng, server không tự lấy thẻ đầu (trước 15/11/2026 lỗi `AttributeError` → 500).

Cả lượt tìm có **một hạn tổng** `realistic.overload_deadline_s` (15 s, tính cả lịch chính và khởi động worker; trần chờ worker `_FORK_WAIT_S`), không hạn riêng từng con. Hết hạn: giữ các hướng đã kiểm xong và đề xuất kéo dài nếu đã tìm được; hướng chưa xong nằm trong `overload.incomplete` và cảnh báo `overload_deadline` (`unfinished`), **không** tính lại đồng bộ. Nếu lịch chính đã kiểm không có vi phạm, thêm hướng `kept` ("Giữ các nơi đã xếp vừa", **chốt được**): giữ đúng các nơi đã xếp, mỗi nơi bị bỏ có lý do "không còn chỗ trong N ngày đã kín lịch (cần thêm khoảng X phút)" — người dùng luôn có một thao tác tới lịch chốt được. Nếu chưa có hướng khả dụng, trả lịch chính đã kiểm dưới dạng **nháp mở được** (`available/status = available`, `confirmable = false`), giữ nguyên selection và đưa nơi chưa xếp vào khay; `back_to_decision = null`. Nháp có `editable = true`; act đầu tiên tự mở đúng nháp đã kiểm để người dùng bỏ/chuyển nơi mà không cần chọn một phương án chốt được trước. Không tự mở các hướng không khả dụng khác; yêu cầu chỗ ở vẫn được giữ. Nháp giữ nguyên mọi vi phạm, bổ sung lỗi anchor cho nơi bắt buộc chưa được xếp; không khẳng định nơi đó không thể vừa, không cho chốt khi còn nơi chưa xếp được (vi phạm chỉ là cảnh báo). Lời giải thích quá tải khi chưa tìm xong nói rõ trạng thái tìm kiếm, không dùng số phút của lịch hiện tại để kết luận chắc chắn thiếu thời gian. Khi tìm hoàn tất mà không hướng nào vừa, mới dùng `required_places_do_not_fit`.

Tiến trình con dẫn đầu một nhóm tiến trình, hết hạn thì kill cả nhóm (`tests/planning/test_planning_overload_parallel.py` kiểm không còn tiến trình sót). `schedule_calls` cộng các lượt `schedule_trip` do worker đã trả kết quả; worker bị hủy có thể chưa báo được số lượt. Các worker không chung memo của tập nơi, nhưng mang cache ngày từ lịch chính. Khay nơi chưa xếp (`view.unplaced`) theo thứ tự người dùng chọn, không theo `set`, nên không đổi giữa các tiến trình (`PYTHONHASHSEED`; `tests/planning/test_planning_tray_order.py`).

Gợi ý tất định `recommendations.recommend` chạy trên snapshot ngoài khóa phiên, tối đa `suggestion_workers` worker đồng thời. `_view` không tìm gợi ý. `view.suggestions` và read `suggestions` trả `{status: pending|ready|unavailable, token, session_id, items}`; `recommendations` giữ danh sách tương ứng để tương thích. Token RAM đổi theo ngữ cảnh và mỗi act/undo/redo; restore đổi generation. Worker lỗi không hỏng lịch, kết quả chỉ hiện khi key khớp. `background=False` tính gợi ý đồng bộ ngoài `_view` cho CLI/test. Đây là gợi ý tùy chọn, khác "Tối ưu lịch" (`Engine.recommend`).

Phiên lưu tối đa 40 `turn_traces`, tách khỏi nội dung chat: mỗi lượt có ID trace, tổng ms và span setup, build_messages, từng model (TTFT/dispatch khi provider cung cấp), từng tool, dựng/serialize view. Public snapshot mang các trace để controller lưu/chẩn đoán; `turn_log` RAM vẫn dùng cho event hiện tại. Không suy first-word người dùng từ TTFT nội bộ. Event harness `planning.turn` liên kết trace đã lưu qua `trace_id` và `turn_trace` (ID, tổng ms, `spans` timing `t_*`, không log nội dung); receipt replay không ghi thêm event.

`Engine.timings` giữ số đo RAM của operation: layout, validation, metrics, suggestions, view, tổng thời gian và hit cache ngày. Benchmark synthetic không gọi mạng: `python tests/planning/bench_edits.py --runs 10`; thêm `--baseline <thư mục chứa src/planning và config/planning.yaml>` để so cùng fixture với bản đã lưu. Bootstrap, cold/warm edit, load và thời gian suggestions-ready được đo riêng; kèm lượt simulate, travel, timing penalty và số vi phạm. Benchmark dựng bảy ngày: `python tests/planning/bench_routes.py --runs 3` (4 hoặc 7 điểm/ngày, không mạng); `--baseline <thư mục source đã lưu>` so cùng fixture với bản gốc. Báo riêng tìm thứ tự và tạo phiên, kèm fingerprint toàn bộ kết quả để đối chiếu lịch, điểm và diagnostics.

API Planning độc lập có `turn`: một call Agent → guard → act; lỗi dùng `policy.py`. Các ví dụ hiểu câu tự do của API này:

| Người dùng nói | Agent làm |
|---|---|
| "ngày 2 nhiều quá" | `drop_place` nơi có điểm xếp hạng Place Decision thấp nhất trong cụm xa nhất của ngày đó, hoặc hỏi một câu khi hai nơi sát điểm |
| "sáng muốn cà phê trước" | `reorder` ngày đó, nêu cái giá nếu phá giờ mở của nơi khác |
| "chỗ ở gần chợ đêm hơn" | đặt chỗ ở thủ công đúng địa danh đó (`set_lodging`) → diff |
| "xa quá" (không nói nơi nào) | hỏi một câu: nơi nào, hay cả ngày nào |
| bỏ nhiều nơi qua nhiều lượt | dừng sửa lẻ, đề nghị quay về Place Decision chọn lại (`docs/PLACE_DECISION.md` §14) |
| "đổi hết đi" | không tự xoá; hỏi xác nhận, nêu hệ quả |

## Tối ưu lịch — `optimize.py`

Nút "Tối ưu lịch" (`Engine.recommend`, harness `recommend` với payload `{scope}`) tìm lịch tốt nhất cho **đúng tập nơi, đúng các ngày, đúng chỗ ở** đang hiện, bằng tìm kiếm tất định, **không gọi model** (chủ dự án 18/11/2026; trước đó là một lượt đề xuất của Agent trên lịch cơ sở). Lịch đầu (Lập lịch, mọi lần sửa, preview) vẫn là bộ xếp nhanh ⓑ ⓒ: chèn rẻ nhất + đổi chỗ, thứ tự vét cạn tới `exact_n`; được phép chưa tối ưu toàn chuyến.

**Hàm mục tiêu** (`optimize.objective`, nhỏ hơn là tốt hơn, so theo thứ tự): số vi phạm validator → số bữa lỡ → một số gộp.
- Bữa lỡ (`optimize.meals_missed`) đếm như người dùng thấy: không tính bữa mà khung giờ đã qua trước khi ngày bắt đầu (ngày tới lúc 14:00 không có bữa trưa, không ai báo lỡ). Trước 18/11 có đếm, nên lịch tự động có ngày đầu bắt đầu 14:00 bị phạt oan và thua lịch người dùng kéo lộn.
- Số gộp = tổng phút xe (gồm lượt đi và về chỗ ở mỗi ngày; chưa có chỗ ở thì từ nơi đầu tới nơi cuối của ngày) + `BALANCE_PER_MIN` (0,25) × độ lệch tải giữa các ngày (phần thời gian tham quan + đi lại trên khung ngày, quy ra phút) + phạt giờ ghé (`time_suitability`) + `PACE_PER_PLACE` (30) × số nơi vượt `per_day` của nhịp + `spread_extra_min` (45) × mỗi ngày còn chỗ bị để trống khi chuyến có đủ nơi cho mọi ngày (`optimize.empty_cost`: gom nơi để bớt lượt về chỗ ở không bao giờ làm trống một ngày người dùng đi; thấy trên prod 18/11: chuyến 3 nơi / 3 ngày từng bị gom về 1 ngày).
- Cộng thêm những gì người đọc lịch thấy ngoài đường đi (`optimize.day_value`): `IDLE_PER_MIN` (0,5) × mỗi phút chờ / ngồi không quá `IDLE_FREE_MIN` (30′); `PIN_LOST` (90) × mỗi giờ đẹp bị bỏ (`unpinned`: hoàng hôn, bình minh, nhạc sống); `LATE_PER_MIN` (2) × mỗi phút về sau giờ kết thúc ngày. `PIN_LOST` lớn hơn một buổi chiều nghỉ ở chỗ ở: giờ đẹp là lý do người dùng chọn nơi đó (`reorder_fine`: với 45, bộ tìm từng bỏ hoàng hôn Công Viên Yersin để bớt 105′ nghỉ).

**Tìm** (hai tầng):
1. Trên ma trận đường, không chạy đồng hồ ngày: mỗi ngày tính tour chính xác từ chỗ ở qua mọi nơi rồi về (Held-Karp tới `HELD_KARP_N` 9 nơi, trên đó nearest-neighbour + 2-opt), cộng phần vượt sức chứa ngày (`layout.capacity`), độ lệch tải và nhịp. Tìm cục bộ (dời một nơi sang ngày khác, đổi hai nơi giữa hai ngày; cải thiện tốt nhất mỗi vòng) từ cách chia hiện tại và từ các cách chia **quét theo hướng quanh chỗ ở** (xếp nơi theo góc phương vị, cắt thành các cung liên tiếp, mỗi cung một ngày theo tỉ lệ sức chứa; mỗi nơi làm điểm bắt đầu một lần). Giữ `CANDIDATES` (6) cách chia khác nhau tốt nhất, luôn gồm cách chia hiện tại.
2. Mỗi ứng viên chạy đồng hồ ngày thật: ngày ≤ `EXACT_N` (5) nơi vét cạn thứ tự (`route.order_day`), ngày dài hơn tìm cục bộ đủ `improve_passes` lượt từ thứ tự hiện tại (`route.improve_order`). Chấm bằng hàm mục tiêu.

**Lịch tự động luôn là một ứng viên** (`seeds`, `Engine._optimize_inputs`): `schedule_trip` xếp lại đúng tập nơi đó (`Engine._fresh_layout`), dùng khi nó giữ mọi nơi khóa / có giờ đặt (và, với `keep_mine`, mọi chỗ người dùng tự sắp). Lịch này biết giờ đẹp, giờ mở cửa, bữa ăn, nên lịch người dùng kéo lộn luôn quay về được nó; bộ tìm trên ma trận thì không với tới (nơi bình minh bị giữ ngày trong bước tìm). Mỗi ngày có nhiều phương án: giữ nguyên ngày hiện tại, thứ tự tìm được, ngày đúng như lịch tự động xếp (kèm giờ đẹp nó đã bỏ vì lý do vật lý), thứ tự lịch tự động chạy lại. Chọn phương án theo người đọc ngày thấy gì: vi phạm validator của ngày → bữa lỡ → `day_value`; hòa thì giữ ngày hiện tại.

**Chỉ nhận khi tốt hơn** (`optimize.improves`): bớt được vi phạm hoặc bữa lỡ thì nhận, kể cả khi phải đi xe thêm (ngày đang hỏng được sửa); số vi phạm và bữa lỡ bằng nhau thì **không bao giờ tăng tổng phút xe** và số gộp phải giảm ít nhất `MIN_GAIN` (1). Lịch thắng được áp qua đúng đường sửa lịch: act `optimize` (`session.apply_act`: mỗi nơi đổi ngày như `move_place`, mỗi ngày đổi nơi hoặc thứ tự giữ thứ tự đó trong `order_override`; `unpinned` theo từng ngày mang các giờ đẹp lịch thắng đã bỏ cùng lý do, để bước xếp lại giữ đúng quyết định đó và cảnh báo `pin_dropped` nói lý do). Act chạy thử trên bản nháp, chấm lại bằng chính kết quả đó, đạt mới `act` thật. Một bước lịch sử: hoàn tác trả lịch cũ; replay sau restart dựng lại đúng lịch. Không tốt hơn thì lịch giữ nguyên.

**Giữ gì**: nơi khóa (`lock_slot`, role `locked` của Decision), nơi có giờ người dùng đặt luôn ở ngày của nó; nơi bình minh (kéo sớm đầu ngày) cũng được giữ ngày trong bước tìm trên ma trận, chỉ lịch tự động (`seeds`) được dời nó; luật cứng của ngày (`layout.allowed`: giờ mở theo thứ, hazard, hành lý ngày cuối) luôn giữ. `scope`: `keep_mine` (mặc định) giữ thêm nơi người dùng đã dời ngày (`assignment`) và các ngày người dùng tự sắp thứ tự (`order_override`, cả nơi lẫn thứ tự); `all` được đổi cả những chỗ đó. Web hỏi trước khi lịch có chỗ người dùng tự sắp (Plan.tsx `optAsk`, như `pickAsk`).

**Trả về** `proposal`: `status` `accepted` (`changed` true + `diagnostics: ["optimized"]`, hoặc `already_best`) | `fallback` (`not_better`, `choose_hotel`, `choose_overload_profile`, `no_valid_baseline`); `before` / `after` là các số hạng của hàm mục tiêu (`travel_min`, `spread_min`, `time_penalty`, `pace_excess`, `empty_days`, `idle_min`, `times_lost`, `late_min`, `problems`, `meals_missed`, `value`). Web (`parts.tsx` `Optimize`) hiện phút xe trước/sau khi giảm và các điều tốt hơn khác (ngày đều tay hơn, đúng giờ đẹp hơn, đúng nhịp hơn).

**Đo** (22 ca `realistic_cases`, không OSRM, 18/11/2026):
- `tests/planning/bench_optimize.py`: trên lịch đầu, 1/22 ca đổi (`flight_1640` bớt 30′ xe, lệch tải 127 → 54′), còn lại đã tốt nhất. Sau khi dời nơi cuối mỗi ngày sang ngày kế (`--shuffle`, như người dùng kéo thả), 14/22 ca được sửa, tổng phút xe 4790 → 4571. Ba ca đi xe thêm vì sửa được ngày hỏng: `friends_packed_bar` 160 → 187′ (hết về quá giờ), `twenty_in_2` 199 → 225′, `worker_meeting` +1′. Chậm nhất 1,9 s.
- `tests/planning/bench_judge.py OUT_DIR`: in từng ca dạng chữ trước / sau Tối ưu, trên lịch đầu và lịch shuffle, kèm kết quả bộ kiểm người dùng (`realistic_checks.CHECKS`). Mọi lịch sau Tối ưu qua hết bộ kiểm. Trước các sửa 18/11 (sau 04:26) còn 9 ca shuffle lỗi người dùng thấy ngay, ví dụ `hotel_breakfast` ngồi không ở chỗ ở 14:00–15:33, Ga Đà Lạt 19:47 (lỡ hoàng hôn), về 21:37 (quá giờ). Script phải giữ `if __name__ == "__main__"`: worker spawn của bộ tìm quá tải nạp lại script.
- Trên prod (chuyến 3 nơi của tài khoản dev, 18/11, bản 04:26): 1,2–1,4 s.

Test: `tests/planning/test_planning_optimize.py`; `test_planning_realism.py::test_optimising_a_scrambled_plan_passes_the_realism_checks` (4 ca shuffle rồi Tối ưu phải qua mọi bộ kiểm).

Log phiên cũ có act `recommend` (đề xuất của Agent trước 18/11/2026) vẫn replay qua `Engine._proposal_trial`; schema ở `proposal.py`.

## Guardrail

Có `pet` trong companions thì Planning suy thêm `pets != not_allowed` với unknown `flag`, kể cả handoff cũ thiếu filter. Quy định cấm thú cưng không bị `relaxed` bỏ qua. Ghost, backup, recommendation và phần lấp lịch không dùng nơi đã biết cấm; nơi chưa rõ giữ ghi chú “chưa rõ có cho mang thú cưng không”. Nơi người dùng đã chọn vẫn được giữ trong lịch hoặc khay vi phạm, có cảnh báo và cách sửa, chưa giải quyết thì chốt trả 409. Chỗ ở corpus (kể cả tự chọn) giữ fail-closed cả khi chưa rõ chính sách thú cưng.

Mỗi `Place` giữ activity từ Search Input hoặc vai trò chọn để ghé. Validator và backup dùng `requirements` để kiểm tra scope trước evidence, áp dụng cả `eq`/`ne`: fail luôn chặn. Ràng buộc an toàn (`effort`, `suitability`, `fit.*`, trừ chính sách thú cưng riêng ở trên) thiếu bằng chứng vẫn là unknown, không phải pass: ghost, recommendation và chỗ ở giữ ứng viên, xếp sau nơi đạt. Khi được xếp thành visit, cảnh báo `safety_unknown` nêu tên nơi và lý do (ví dụ “Chưa rõ có dốc, nhiều bậc”), tính lại theo lịch hiện tại cả view/build/confirm; không chặn chỉ vì chưa rõ. Ràng buộc khác giữ policy exclude/flag. Backup cho bữa ăn được kiểm tra ở activity eating, kể cả café hỗ trợ cả meal/experience. Coffee-only và sightseeing không cần evidence món chay. Không suy vegan từ vegetarian hay wine tasting từ generic tasting. Contract ở `docs/TRIP_UNDERSTANDING.md` §9.

| Bất biến | Cách ép |
|---|---|
| Không xáo lịch âm thầm | `repair_day` phạt mỗi thay đổi so với phiên bản trước (trọng số trong config); mọi thay đổi đi qua diff |
| Nơi `locked` / anchor không bị dời | `repair_day` từ chối, lỗi nói rõ phải hỏi người dùng |
| Physical không nới | `validate` là nơi duy nhất kết luận pass / fail; không có act `relax` cho physical |
| Không bịa | mọi `place_id`, số phút, giá trong `say` phải có trong kết quả tool của phiên; số live phải mang `source` + `fetched_at` |
| Không nhận lịch chưa kiểm | `confirm` từ chối khi `validate` chưa `ok` |
| Lịch thô không được gắn "Vững" | `robustness` đọc `travel_source`, trần "Khả thi" |
| Live không thành tri thức lâu dài | `src/live` không có đường ghi `data/intel`; test khẳng định |
| Chỗ ở chỉ từ corpus | ứng viên là bản ghi serving nhóm `stay`; Planning không cào Maps khi chạy |

## Plan Output

Kế hoạch phải trả lời được cả "vì sao chọn những nơi này" và "đã phải hy sinh gì để khả thi":

```text
Plan Output
├── variants       2–3 phương án: mục tiêu, lịch trình, điểm, độ vững, bảng đánh đổi giữa các phương án
├── chosen         phương án người dùng chốt
├── itinerary      theo ngày: nơi, giờ đến / đi, chặng (phút, mode), chờ, đệm, nghỉ, bữa ăn
├── route          hình lộ trình từng ngày (OSRM /route)
├── lodging        đã chọn + ứng viên khác, mỗi cái: tổng phút di chuyển cả chuyến, giá (hoặc unknown), amenities
├── time_budget    quỹ thời gian: số ngày, số đêm (số người dùng nói, thiếu thì ngày − 1), cửa sổ và số phút dùng được mỗi ngày;
│                  ngày đầu mở lúc tới, ngày cuối đóng lúc rời nên tổng nhỏ hơn số ngày × độ dài một ngày
├── cost           chi phí ước tính: vé / đồ uống + tiền phòng (khi biết giá)
├── checklist     chuẩn bị theo ngày và nơi: mang gì, đặt gì, khâu dễ bị chặt chém, lạnh, sương mù, lịch cố định, đúng mùa
├── travel_load    phút di chuyển mỗi ngày, chặng dài nhất
├── time_suitability  độ phù hợp giờ ghé, nguồn ước lượng, phút rút và quá tải cửa sổ
├── recommendations  gợi ý tùy chọn cho khoảng trống/quá tải; ứng viên đã qua thử xếp và validate
├── reasons        vì sao chọn những nơi này (gộp `decision_log`) và vì sao xếp như vậy
├── tradeoffs      đã hy sinh gì để khả thi
├── warnings       giờ `UNCERTAIN` / `OUTDATED`, mưa, thời tiết xấu, thông báo, đông khách, đóng cửa dịp Tết, giá tham khảo, chỗ ở chưa xác minh
├── day_conditions điều kiện từng ngày (khi có): thời tiết, loại ngày, mức đông, thông báo
├── crowd_tips     giờ vắng nhất của nơi đông, từ số liệu của chính nơi đó
├── uncertainty    phần nào là ước lượng, `travel_source`
├── robustness     mức + lý do + kịch bản làm hỏng
├── backups        phương án thay cho từng nơi nhạy cảm
└── provenance     mỗi số live kèm `source` + `fetched_at`
```

## Tiêu đề và tóm tắt tổng quan — `summary.py`

Đầu khối giới thiệu ở màn tổng quan Lịch trình có một tiêu đề ngắn và 2–3 câu tóm tắt. `Engine.summary` (đọc `planning/summary`, không đổi trạng thái) lấy từ lịch đang xem tên từng điểm ghé, khu vực và giờ bắt đầu, rồi nhờ role `AGENT` (task `PLANNING_SUMMARY`) diễn đạt; prompt cấm thêm nơi, giờ, giá, thời tiết không có trong dữ liệu. Câu trả lời được kiểm ở biên (không rỗng, tiêu đề một dòng, độ dài có giới hạn); lỗi, hết giờ (25 giây) hoặc chưa cấu hình key thì trả bản tóm tắt tất định `source: "plain"` dựng từ cùng dữ kiện, và web chỉ dùng bản `agent`, còn lại giữ câu mặc định. Câu của model được nhớ theo (phiên, dấu vân tay lịch) tối đa 256 mục; bản `plain` không được nhớ nên lần đọc sau thử lại. Model được hỏi ngoài khóa phiên.

## CLI và API

| Lệnh | Việc |
|---|---|
| `python -m planning build <decision_output.json>` | in một lịch trình đã kiểm (`--out` ghi Plan Output dạng json) |
| `python -m planning variants <decision_output.json>` | in 2–3 phương án theo mục tiêu, kèm độ vững và dự phòng (`--weather forecast.json`) |
| `python -m planning lodging <decision_output.json>` | như trên, cộng chỗ ở cạnh tranh làm neo mỗi ngày; cần Chrome đã đăng nhập `gmaps` |
| `python -m planning serve [--port 8768]` | HTTP + SSE độc lập |
| `python -m planning evaluate` | 10 chuyến có tên qua Decision → Planning → `data/planning/eval.json` (§Đo) |

`build` / `variants` / `lodging` / `evaluate` cần OSRM đang chạy để có số thật; không có thì rơi về ước lượng thô kèm cảnh báo (§Live Context).

User Web gọi Planning qua harness (`docs/AGENT_HARNESS.md`), từ Decision Output server đã xác nhận. API độc lập `serve` bind `127.0.0.1:8768`; danh sách dưới đây thuộc API này, gồm `turn` không được router harness cung cấp.

Factory capture hoặc nhận public corpus binding, mở đúng snapshot/version/region đó.
Adapter kiểm binding của Decision Output trước create/preview/lodging/restore; Plan Output
giữ binding. Không đọc serving của root khác để lấp phần thiếu.

Danh sách lodging thay thế dựng matrix bằng bản sao không có lodging hiện tại; hard filters
vẫn áp cho từng ứng viên. Vì vậy lodging cũ fail sau rebase không chặn tìm nơi thay thế;
create/preview/confirm vẫn kiểm lodging được chọn theo input thật.

Preview cache key giữ release, context/activity/requirements, input feasibility thực sự được
composer dùng, config/live settings và dependency token. Log/wishlist/feasibility phụ không
làm mất hit. Factory của immutable release dùng manifest hash đã verify thay cho serialize
lại corpus; Engine mutable dùng fingerprint records. `live_dependency_version` cho caller
đổi token khi callback data đổi; khi không truyền token, TTL reuse là 900 giây. Preview hit
không sửa shared base; create chỉ gắn log mới sau khi nhận quyền sở hữu base từ cache.

```
POST   /api/planning/sessions              {decision_session_id | decision_output}
GET    /api/planning/sessions/<id>
POST   /api/planning/sessions/<id>/act     tất định; 400 khi act sai (state không đổi)
POST   /api/planning/sessions/<id>/turn    SSE: say(delta|replace) · view · progress · done · error
GET    /api/planning/sessions/<id>/variants
GET    /api/planning/sessions/<id>/lodging trạng thái + ứng viên đã xếp
GET    /api/planning/sessions/<id>/lodging/events  SSE khi danh sách chỗ ở xếp xong
POST   /api/planning/sessions/<id>/confirm → Plan Output (kèm `violations` và cảnh báo còn lại); 409 chỉ khi chưa dựng được phương án nào
```

Lỗi: 400 act sai, 404 không có phiên, 409 sai phiên bản hoặc chưa dựng được phương án nào (thiếu chỗ ở, nơi chưa xếp được, chưa chọn phương án không còn là lý do từ chối: thành cảnh báo). Event `progress` là phần thêm so với `decision` (báo danh sách chỗ ở đang được xếp).

Web: `web/src/user/planning/` (`types.ts`, `api.ts`, `planning.tsx` — `PlanningProvider` + `usePlanning()`) và `web/src/user/screens/Plan.tsx` ở `/app/plan`. Màn gồm: chọn hành trình + bảng đánh đổi · timeline từng ngày (giờ, chặng, phút di chuyển, đệm, nghỉ) kèm điều kiện ngày · bản đồ Google · chỗ ở · dự phòng của ngày (`backups.places` / `on_delay`, thay bằng `swap`) · ngăn Tối ưu · dòng báo mỗi lần sửa + hoàn tác · nút chốt · “+ Thêm nơi”. Thanh "Đã chọn" ở Chọn nơi gọi handoff (`web/src/user/pd/decision.tsx` `toPlan`); nút "Tối ưu lịch" gọi `recommend` (`web/src/user/planning/api.ts` `runRecommend`, §Tối ưu lịch); lịch ngầm trước khi xác nhận dùng `Engine.preview` qua harness (`docs/AGENT_HARNESS.md` §2). Chức năng từng màn: `docs/Role_Web_Functional_Design.md` §2.10.

## Cấu hình — `config/planning.yaml`

Một chỗ duy nhất cho mọi ngưỡng của Planning:

| Nhóm | Khoá |
|---|---|
| Di chuyển | `road_factor`, `rough_speed_kmh` (đường lui khi OSRM chết), `walk_km`, `walk_kmh` |
| Khung ngày | `default_days`, `day_start`, `day_end`, `leave_at` |
| Nhịp độ | `visit_key`, `per_day`, `buffer_min` (+ phụ phí `long_leg_min`, `buffer_extra_long`, `buffer_extra_uncertain`, `buffer_extra_rain`), `rest_min`, `max_consecutive_min` |
| Bữa ăn, buổi | `meals_per_day`, `meal_min`, `meal_durations`, `meal_windows`, `pins` |
| Độ phù hợp giờ | `time_suitability`: `enabled`, `periods`, `sun_offsets`, `heuristic_weight`, `penalty_min`, `duration_loss_min`, `overload_weight`, `recommendation_gap_min`, `recommendations_per_gap`, `timing_bonus`, `timing_penalty`, `night_road_penalty`, `tod` |
| Ngày, thứ tự | `exact_n`, `improve_passes`, `weights` (`travel`, `overflow`, `count`, `closed`, `crowd`); `spread_extra_min` có default trong `planning/settings.py`, ghi vào YAML khi cần đổi |
| Mục tiêu, phương án | `objective_weights` (trộn lên `weights` khi chia ngày: `travel`, `exposed`, `repeat`, `pref_risk`) |
| Điều kiện ngày | `crowd_busy_pct`, `conditions` (`heavy_rain_mm`, `heavy_gust_kmh`, `severe_rain_mm`, `severe_gust_kmh`, `crowd_visit_pct`, `crowd_buffer_min`, `crowd_avoid_factor`, `closure_buffer_min`) |
| Độ vững | `rain_high`, `robustness` (kịch bản nhiễu có `tier` small / large, `solid_max_lost`, `feasible_max_lost`) |
| Dự phòng | `near_close_min`, `far_leg_min`, `backup_radius_min`, `backups_per_place` |
| Chỗ ở | `radius_km` theo mobility, `lodging_k`, `lodging_share`, `min_reviews`, `split_min`, `lodging_pool`, `lodging_weights` (`pref`, `loc`, `price`, `rating`), `loc_ref_min` |
| Phiên | trọng số phạt của `repair_day`, `decision_url` |

`version` ở đầu file.

TTL từng nguồn live và endpoint OSRM nằm ở `config/live.yaml`, không nằm ở đây: `src/live` không được đọc config của `planning` (phụ thuộc một hướng).

Thêm `config/climate.yaml` (ghi đè và ước lượng dự phòng cho khí hậu Đà Lạt theo tháng), `config/holidays.yaml` (lớp tay trên view lịch), `config/events.yaml` (lễ hội, Noel, Tết) và `config/advisories.yaml` (thông báo thiên tai; mặc định rỗng). Hai file `events.yaml`, `advisories.yaml` nhập tay và là toàn bộ sự thật: ngày không liệt kê là chưa biết, không phải bình thường.

## Test

| Mức | Nội dung |
|---|---|
| Unit | `layout`, `days` (số hạng rủi ro), `route` (vét cạn + 2-opt), `schedule` (chờ / đệm / nghỉ), `validate` (mỗi loại vi phạm), `robustness` (mỗi kịch bản), `lodging` (sàng), `objectives` — fixture thuần, không mạng |
| Fixture live | `travel_matrix`, `weather` lưu lại từ lần chạy thật (như `tests/fixtures/capture.py` của crawl, che tài khoản); test không gọi mạng |
| Golden | lịch của N chuyến mẫu; đổi thuật toán phải cập nhật golden có chủ ý |
| Bất biến | `src/live` không ghi `data/intel`; physical không có đường nới; `locked` không bị dời; `confirm` chặn khi chưa `ok`; `travel_source = rough` không được "Vững" |
| Live thật (`-m live`) | OSRM local, Open-Meteo, một lần crawl lodging — chạy tay, không trong CI |

## Đo — `python -m planning evaluate`

Dùng 10 chuyến có tên trong `config/eval_trips.yaml` (không lấy các tổ hợp `cross`): Search Input → Place Decision → `confirmed` → Planning. Chỉ chọn thẻ `available` + `confirmable`, không mặc định thẻ đầu; không có thẻ chốt được thì ghi ca không khả thi thay vì crash. `avg_saved_vs_baseline_pct` là trung bình `100 × (1 − travel_min / baseline_travel_min)` trên các ca ok, đơn vị %. `ms_total` đo create và thử chỗ ở, chưa cộng confirm.

| Chỉ số | Mục tiêu |
|---|---|
| Hard constraint violation trong lịch | 0 |
| Unsupported claim rate (`say` ngoài kết quả tool) | 0 |
| Feasible itinerary rate (tổ hợp Decision nói "khả thi" mà Planning xếp được) | cao; phần hụt là sai số ước lượng thô của Decision (`docs/PLACE_DECISION.md` §17) |
| Tỉ lệ Vững / Khả thi / Mong manh | báo cáo, chưa đặt ngưỡng trước pilot |
| Phút di chuyển so với baseline | baseline = nearest-neighbour + anchor `base`, không chọn chỗ ở. Thước đo "tối ưu" có thật |
| Chỗ ở giảm bao nhiêu phút mỗi ngày so với phương án không chỗ ở | báo cáo |
| Số lượt sửa trước `confirm` | giảm công sức |
| Độ trễ: dựng 21 phương án · xếp chỗ ở | < 2 s · báo cáo |

Hành vi agent không tất định nên đo bằng mô phỏng nhiều lần và so với `policy.py`, như `docs/PLACE_DECISION.md` §17; thêm số lần guardrail chặn, số tool-call mỗi lượt, độ trễ mỗi lượt.

## Giới hạn đã biết

- Tốc độ (`tests/planning/bench_realistic.py`, có OSRM, máy tải 13–20/40 lõi, 29/10): lịch đầu p50 0,13–0,17 s · p95 1,5–1,8 s; đổi khung ngày max 0,24 s; đổi chỗ ở max 0,34 s (số 0,85 s cũ đo lúc máy tải ~40/40). Ca dày `twenty_in_2` (19 nơi / 2 ngày) vẫn 3,7–4,3 s: lịch chính 1,5–1,8 s (vòng xếp lại nơi thừa trong `build.schedule_trip` và `build._unpin`: 18 lần `_unpin` ≈ 1,8 s, `route._heuristic` ≈ 2,6 s khi bật cProfile) cộng hướng `fit` 1,1–1,9 s (20 lần `schedule_trip`, mỗi lần 0,01–0,25 s). Đã thử 29/10: dùng chung một `cfg` cho `_route_ctx` để memo `pin_duration_floor` trúng — chỉ 8/185 lần trúng, không lợi, đã hoàn nguyên; trước đó (28/10) thử chạy trước các lần trả lại của `fit` ở 4 tiến trình — chậm hơn khi máy tải, đã gỡ. Nơi thừa bị loại chủ yếu vì vượt sức chứa ngày nhẹ (`within`) nên cận theo thời lượng tối thiểu không cắt được lần thử nào; chưa có cận chứng minh được để bỏ bớt mà không đổi kết quả, nên dừng ở đây (HANDOFF #1, #2 còn mở).
- Tốc độ 18/11/2026 (`tests/planning/bench_preview.py`, 22 ca `realistic_cases`, không OSRM, pool worker đã khởi động; preview rồi create trên cùng engine như harness). Trước: preview p50 91 ms · p90 4,3 s · max 5,7 s; create p90 3,3 s · max 6,3 s (preview chạy cả tìm hướng quá tải). Sau: preview p50 61 ms · **p90 270 ms** · max 1,3 s; create sau 3 s người dùng xem bản đồ (`--gap 3`) p50 94 ms · **p90 516 ms** · max 0,8 s; bấm Lập lịch ngay (`--gap 0`) p90 1,7 s · max 4,0 s (chờ việc tìm hướng còn chạy). Còn chậm: lịch chính của ca quá tải nặng (`family_12_in_3`, 14 nơi / 3 ngày: 1,3 s; `must_go_kept` 0,6 s) nằm ở ~30 lượt xếp ngày tuần tự của vòng xử lý nơi thừa trong `build.schedule_trip` (`_unpin`, `route._heuristic`); cấu hình vét cạn ít hơn (`exact_n` 4–5, 1–2 lượt cải thiện) không đổi thời gian, đã thử 18/11. Mục tiêu handoff (preview ≤ 300 ms, create ≤ 1 s, p90) đạt theo p90; hai ca quá tải nặng nhất chưa đạt.
- GPU không giúp phần này (chủ dự án hỏi 18/11/2026): phần tốn là mô phỏng từng ngày rẽ nhánh nhiều bằng Python, kích thước nhỏ (≤ 5040 thứ tự một ngày); đòn bẩy là 40 lõi CPU qua pool worker và cache mô phỏng. Thêm thread không nhanh hơn (GIL); thêm tiến trình chỉ có lợi khi chia nhỏ việc bên trong một hướng.
- Thời gian di chuyển không có traffic thời gian thực; profile xe máy là profile ô tô nhân hệ số.
- Giá phòng là giá OTA tại thời điểm crawl; homestay ngoài OTA không có giá.
- Mặt lodging của Maps không liệt kê đủ theo khung bản đồ.
- Vét cạn chỉ trong giới hạn `exact_n`; vượt thì rơi về heuristic và gắn cờ.
- Chưa có User Profile dài hạn nên `preference_fit` chỉ dùng `soft_weights` của phiên.
- Đổi lịch tối trước ngày đi: giao diện banner trên `/app/plan` đang có hai mẫu chờ chủ dự án chọn (`EVE_LOOK` trong `Plan.tsx`); chấp nhận một phương án làm mất các đề xuất khác còn chờ của cùng lịch (chúng thuộc `plan_hash` cũ), tối sau kiểm lại. Nghỉ lễ chỉ là ghi chú cho nơi có giờ chưa xác minh; chưa có nguồn đóng cửa ngày lễ theo từng nơi.
- Giá và tiện nghi của chỗ ở đọc bằng quét văn bản thô trên thẻ Maps (không phải DOM đã dò kỹ): có thể trống hoặc
sai nếu Maps đổi cách hiển thị; ngày check-in / check-out chưa đặt qua bộ lọc của Maps.
- Thông báo thiên tai là file nhập tay (`advisories.yaml`); chưa có nguồn tự động nên rỗng không có nghĩa an toàn. Lễ hội phải được nhập từ thông báo chính thức. Ngưỡng thời tiết và hệ số đông khách là ước lượng, chờ chỉnh sau pilot.
- `place_live_status` (đóng cửa tạm, giờ ngày lễ) chưa gọi mạng: chưa chọn được nguồn. `confirm` chỉ gom lại cờ
`UNCERTAIN` / `OUTDATED` đã có.
- `repair_day` ép "ghim ngày" của nơi `locked`, không ép cứng "ghim giờ" (vị trí chính xác trong ngày) — chỉ phạt
lệch qua `repair_diff_weight`.
- `Trip` / lịch sửa sống trong RAM; restart dựng lại từ `decision` + `states[0..position]`, nhưng kết quả tìm thẻ có deadline đã đưa ra được giữ trong `search_artifacts`. Phiên cũ chưa có artifact vẫn phải tìm lại lần đầu; không thể khôi phục chính xác thẻ từng thấy nếu phiên cũ chưa lưu chúng.
- SSE `.../lodging/events` hiện poll nội bộ mỗi 50ms tới khi danh sách chỗ ở xếp xong hoặc tối đa 10s rồi vẫn phát `progress` với
candidates hiện có — chưa có callback trực tiếp từ thread nền; một `queue.Queue` giữa thread nền và handler sẽ
thay được chỗ poll này.
- `decision_session_id` yêu cầu server của `decision` đang chạy ở `decision_url` (`config/planning.yaml`); không có
cơ chế retry / backoff — một lần lỗi mạng trả thẳng `ActionError` cho người dùng thử lại.
- Sau khi danh sách chỗ ở xếp xong, các phương án đã dựng **không** tự chấm lại theo K ứng viên chỗ ở ("chấm lại K × mục
tiêu → diff" ở §Chỗ ở không làm người dùng chờ chưa có): người dùng vẫn chọn được chỗ ở qua `pick_lodging` /
`set_lodging` và lịch xếp lại đúng, nhưng chưa có bảng so sánh "đổi sang chỗ ở X: −N phút/ngày" tự động. `act`'s
`diff` hiện chỉ có `scope`, chưa phải diff đầy đủ như §Guardrail đòi. Plan Output's `lodging.candidates` luôn `[]`
(chỉ `lodging.chosen` có dữ liệu). Không có đường nào trả kết quả sai, chỉ thiếu tính năng so sánh.
- `lodging_near` (câu nói tới một địa danh) đặt chỗ ở thủ công đúng địa danh đó (`set_lodging`), chưa tìm lại K ứng
viên chỗ ở quanh một tâm mới — cần sửa `lodging.py` / `build.py`.
- "Bỏ nhiều nơi qua nhiều lượt -> đề nghị quay về Place Decision" chỉ hoạt động trong kênh gõ chữ (`turn`); các act
`drop_place` gửi qua chip không bị chặn bởi `rethink_drops` -- Planning chưa có cơ chế `Pending`/câu hỏi mở như
`decision.Session` có.
- `python -m planning evaluate` đo lịch dựng được (tỉ lệ có lịch khả thi, phút tiết kiệm so với baseline, chỗ ở tiết
kiệm bao nhiêu phút/ngày, Vững/Khả thi/Mong manh, độ trễ) nhưng **không** mô phỏng hội thoại nhiều lượt với agent
thật: "số lần guardrail chặn, số tool-call mỗi lượt, độ trễ mỗi lượt" chưa đo được, giống khoảng trống ở
`src/decision/evaluate.py`. `confirmed` của mỗi chuyến ẩn là shortlist hạng cao nhất tự động chấp nhận (không có
người dùng thật chọn/bỏ), nên số liệu phản ánh "Planning có xếp được thứ Decision xếp hạng cao không", không phản
ánh một phiên sửa thật.
- Baseline của `evaluate` là nearest-neighbour trên đúng nhóm nơi theo ngày của phương án đã chọn. Thứ tự của
Planning tối ưu cả giờ mở cửa, chờ và cửa sổ thời gian, không chỉ phút di chuyển, nên trên một số chuyến phút di
chuyển có thể dài hơn baseline; `avg_saved_vs_baseline_pct` có thể âm và được báo đúng dấu.

## Trợ lý Lịch trình — `assistant.py`

Mỗi chuyến chỉ có một cuộc trò chuyện hiện tại (chung với Lựa chọn và trang chủ), không có danh sách lịch sử. Nút `Trò chuyện mới` ở đầu khung chat lưu mốc `new_chat` trong `Session.chat` (harness ghi mốc cả ở Trip và Decision), rồi web mới xóa tin trên client; chỉ hoạt động khi có tin và không đang trả lời. Ngữ cảnh hội thoại lượt sau bắt đầu sau mốc; các lượt cũ và tin client vẫn lưu trong snapshot server để phân tích, không cắt bỏ khi thêm lượt. Không đặt lại lịch, undo hay dữ kiện chuyến. Quyết định chủ dự án 10/11/2026; giao thức ở `docs/AGENT_HARNESS.md` §4.

Dựng prompt không quét evidence của corpus: context chỉ mang binding và trạng thái `not_requested`; facts về nơi được đọc bằng shared read tools khi cần. `recovery_actions` trả nút sửa có `action`, `label`, `reason`, `confirmable`: với điểm không khóa gây lỗi, thử bỏ điểm và chỉ đề xuất nếu toàn lịch còn lại chốt được. Vi phạm vẫn hiển thị; Chốt không từ chối vì vi phạm, chỗ ở thiếu, nơi bắt buộc chưa xếp được hay nơi đã chọn không vừa số ngày: màn hình hỏi "Vẫn chốt?", lịch đã chốt mang các điều đó thành cảnh báo (`no_lodging`, `lodging_unfit`, `required_unplaced`, `picks_left_out`); chưa chọn phương án thì dùng phương án đầu.

Chat gõ ở màn Lịch trình chạy trên lõi chung `src/agents/assistant`. Tool đọc/ghi ở `assistant.py` + `tool_schemas.py` (stage `planning`); mọi sửa đổi đi qua `Engine.act` như nút bấm, một lượt = **một phiên bản** (`Engine.collapse`, log `{"type":"batch"}`). Không lượt sửa nào bị từ chối hay hoàn tác vì luật (chủ dự án 2026-11-09: chỉ cảnh báo, người dùng quyết định): vi phạm **vật lý** hoặc không thể có mới phát sinh (`serious_violations` trong `config/planning.yaml`: `hard`, `departure`, `duplicate`, `anchor`, `overlap`, `travel`, `hazard`) trả về `serious` để trợ lý nói trước và rõ (có thể không đi được thật) kèm đề xuất hoàn tác / cách sửa; mọi vi phạm còn lại trên lịch trả `flagged`; lịch hiện cờ cảnh báo ở đúng dòng và người dùng vẫn chốt được. Tool `set_stop_time` nhận giờ bắt đầu của riêng nơi được người dùng gọi tên; tên rút gọn như “Horizon” chỉ được nhận nếu không trùng nơi khác trong lịch. Giờ được giữ qua replay/undo/redo; giờ gây thêm vi phạm vẫn được giữ và vi phạm hiện thành cảnh báo; giờ vượt giới hạn vật lý thì nơi nhận giờ khác, kết quả có `time_not_kept {asked, placed}` để trợ lý nói giờ thật và đề nghị ngày khác / hoàn tác; chỉ từ chối khi nơi đó không còn trong lịch sau khi xếp lại. Tool được khai báo đồng thời trong `skills.yaml` và `agents.contracts.TOOL_ACCESS`. Chỗ ở và ưu tiên xếp lịch đi qua đúng act của nút: `lodging_options` (đọc: chỗ ở hiện tại, người dùng tự đặt hay không, tối đa 8 chỗ ở đang được đề xuất với giá/đêm, loại giá, phút trung bình tới các nơi, điểm mạnh / điểm yếu đã xác minh; lọc được theo giá tối đa), `pick_lodging` (chỉ id do `lodging_options` trả → act `pick_lodging`), `set_lodging_budget` (→ `set_lodging_budget`), `set_priority` (`least_travel` · `low_cost` · `weather_robust` · `diverse` · `preference_fit` → `set_objective`; chỉ đổi thứ tự và cách chia ngày, không đổi luật kiểm). `add_place` chỉ nhận nơi trong `spare_places`; nơi khác người dùng gọi tên thì trợ lý chỉ sang Lựa chọn. Tool đọc địa điểm dùng chung Trip qua `Engine.trip_reader`. Cấu hình `assistant:` trong `config/planning.yaml`. Bench: `python -m planning bench --live` (`config/bench_planning_assistant.yaml`, 31 ca).
