# Bàn giao: phản hồi giao diện Web 13/11/2026

Phiên trước làm gần hết danh sách phản hồi của chủ dự án (Tìm hiểu, cổng trước lập lịch, Lựa chọn, Lịch trình) rồi hết ngữ cảnh. Tài liệu này ghi việc đã xong, việc dở và cách kiểm chứng trên server thật. Xóa file này khi việc dở đã xong (`RULE.md` §0.1). Chưa commit gì; cây làm việc còn nhiều thay đổi khác của chủ dự án (pulse, events, Trends…), không đụng.

## 1. Đã xong (tsc sạch; test liên quan đạt)

| Việc | Code |
|---|---|
| Lịch sử chat: ba chấm to; dấu X xóa trong ô tìm kèm hộp xác nhận; đặt tên chat có nơi đã giữ không còn là "Cuộc trò chuyện mới" | `understand/History.tsx`, `css/workspace.css` |
| Bấm chuyện cũ chỉ mở hội thoại (không nhảy bước); quay về chat từ Lựa chọn không bị đẩy ngược (cờ `stageEntries` đọc không xóa, `peekStageEntry`, xóa khi chat đã lên màn) | `Understand.tsx` (`peek`, `selectTrip`, `open`), `journey.ts` |
| Chọn nơi giữ thứ tự thẻ khi chọn / bỏ | `ui/useStagedList.ts` |
| Ô tìm của tab Nơi lưu trú tìm chỗ ở; mọi tab có icon | `Explore.tsx`, `Lodging.tsx` (`LodgingSearchResults`) |
| Chuyến của tôi: tab *Đang lên kế hoạch* | `Account.tsx`, `css/screens.css` |
| Cổng trước lập lịch: bản tóm tắt không tự sang Lịch trình, mỗi dòng có *Sửa* dùng ô sửa của phiếu chuyến (`ticketEditors`) | `ui/ReadbackSheet.tsx`, `ui/Ticket.tsx`, `css/gate.css` |
| Thẻ ngày / lưu ý của cổng **đã hoàn về thiết kế cũ** theo yêu cầu (`Gate.tsx` = bản git trừ một dòng: cleanup của `useFan` đặt lại `raf = 0`; chỉ giữ css tóm tắt) | `ui/Gate.tsx` |
| Lịch trình: thẻ nổi bên phải (Đi với / Nhịp độ / Ngân sách / Đường tới, điểm xuất phát, chọn chỗ nghỉ, Đổi, Thêm, "+" của gợi ý); bỏ thẻ Giờ ghé; bỏ `Swap.tsx`; Đề xuất tối ưu là thẻ giữa màn; màn Hành trình trước khi chốt | `plan/{panels,pickers,fill,Journey,WayIn,parts}.tsx`, `Plan.tsx`, `css/plan.css` |
| Nơi đã lưu chưa thuộc lựa chọn: *Thêm vào lịch* = `select` ở Decision rồi dựng lại lịch (`useTripEdit`, `Step`) | `plan/fill.tsx`, `plan/pickers.tsx`, `Plan.tsx` |
| Tài liệu + `DEV_LOG` đã cập nhật (`web-ui-feedback-2026-11-13`); test `plan/notes.test.mjs` bỏ ca TimeCard / Swap | `docs/` |

## 2. Việc dở (cập nhật 17:00 ngày 13/11/2026)

Đợt phản hồi thứ hai đã làm và chạy thật (`DEV_LOG` mục `web-ui-feedback-round2-2026-11-13`, ảnh `frontend_images/real6/`, `real7/`). Còn:

1. **Cần deploy cả `src/` lẫn web** cho: `decision.trip` nhận `edit` (lưu điểm xuất phát, *Sửa* ở bản tóm tắt cổng) và tên hướng / bỏ ghép tên ở `overload.py`. Harness prod chạy `.prod_src/` cũ nên vẫn trả 400 cho `edit`. Không deploy khi chủ dự án chưa yêu cầu. **Không chạy `vite build` trong `web/`** (ghi thẳng vào `web/dist` prod đọc; xem `AGENT_FAILURES.md` F007).
2. **"3 phương án tối ưu nhất"**: web chỉ hiện tối đa 3 và bỏ trùng; khi hai hướng ra cùng lịch thì chỉ còn 2 thẻ. Muốn luôn đủ 3 lịch khác nhau thì phải sửa bộ lập lịch (`src/planning/overload.py` sinh thêm hướng); chưa làm, cần chủ dự án quyết.
   - Chủ dự án 13/11 chọn thêm hướng thứ 4 **"Giữ nhiều nơi bạn chọn nhất"** (id `most`), làm ở session riêng: `overload.py` thêm vào `DIRECTIONS` / `LABEL` / `_next` (bỏ trước nơi chiếm nhiều thời gian nhất: `visit["short"]` nếu chưa xếp, `_freed` nếu đã xếp, hòa thì bỏ nơi ít hợp gu); sửa các test đang khẳng định đúng 3 hướng (`test_planning_composer/engine/lodging_golden/overload/variants`, `realistic_checks`); web `Choose.tsx` (`SHOWN`, `WAY_NAME`, bảng nhãn) và lưới `.tg-it-choices` (3 → 4 cột); đo lại thời gian quá tải (5 tiến trình con trong hạn `overload_deadline_s` 15 giây). Deploy đóng băng cả `src/` chưa commit của cây làm việc: xem lại trước khi chạy `./run.sh prod`. Đã thử một bản và gỡ ra, chưa có gì trong code.
3. Server trả 500 khi `confirm` lịch chưa chọn phương án (web không còn gửi). Chưa sửa.
4. Lỗi "chat mới hiện lịch cũ": hỏi chủ dự án còn gặp không.
5. Gửi chủ dự án đường dẫn ảnh (`RULE.md` §0.2); chưa commit.

## 3. Cách chạy trên server thật (không deploy)

- Harness thật đã chạy ở `:8769` (prod, 30 GB RAM). Vite dev đã chạy ở `:5199` (đọc `src/` hiện tại, proxy sang `:8769`). Không bật harness thứ hai (ngốn RAM / GPU dùng chung).
- POST bị `403 cross-origin` vì `Origin` khác `APP_BASE_URL` (https). Trong Playwright: `context.route('**/api/**', r => r.continue({ headers: { ...r.request().headers(), origin: PUBLIC } }))` với `PUBLIC` = `APP_BASE_URL` đọc từ `.env`.
- Đăng nhập: nút *Dùng thử, không cần tài khoản* ở `/app/login` (tạo tài khoản khách trên prod; mỗi lần chạy một khách, tự hết hạn sau 24 giờ không dùng — xóa chuyến thử bằng `DELETE /api/harness/sessions/<id>` nếu muốn dọn).
- Vào thẳng `/app/understand` (trang chủ bật tour che nút). Chromium: `.cache/ms-playwright/chromium-1169/chrome-linux/chrome`; dùng `waitUntil: 'domcontentloaded'` (snapshot lớn làm `networkidle` treo).
- Qua Chọn nơi: gõ tin đầu ("3 ngày 2 đêm ở Đà Lạt cho hai người yêu nhau, đi xe máy, thích cà phê và săn mây"), bấm *Bỏ qua* ở thẻ hiện ra, rồi `.tg-cx__go` ("Tiếp tục đến chọn nơi"); khoảng 60 giây. Chọn nơi: `.tg-pc .tg-pc__act .tg-btn--primary`; lưu nơi: `.tg-pc .tg-pc__save`. *Lập lịch*: nút ở thanh `SelectedBar`.
- Script đã dùng nằm ở `/tmp/claude-2420/-data-work-luanhh-local-tripguardian/83dcc290-7524-414d-99eb-6f7d3eb7c492/scratchpad/{common,toplan,plan,route,confirm}.mjs` (`toplan` tới Lịch trình và lưu `state.json`; `plan` đi các thẻ nổi tới Chốt) (tạm; có thể mất, mục này đủ để viết lại). Ảnh thật ở `frontend_images/real/`, ảnh fixture ở `frontend_images/ui-feedback-*.png`.

## 4. Lưu ý

- Quy ước chủ dự án: tự code, không dùng skill `superpowers:*`; thiết kế UI chỉ dùng `ui-ux-pro-max`; tài liệu tiếng Việt, code tiếng Anh; commit author `hohoangluan` + co-author theo ghi chú memory; HTTPS / SSH push không chạy từ gpu156, chủ dự án tự push.
- Server chỉ đổi / thêm trực tiếp nơi thuộc lựa chọn hoặc dự phòng đã kiểm tra (`src/planning/session.py`: `add_from_backup`, `swap`); đừng nới phía Planning, dùng đường `select` ở Decision.
- Lịch trình bị dựng lại sau mỗi lần lưu thông tin chuyến / thêm nơi ngoài lựa chọn (thứ tự sắp tay mất): cân nhắc nhắc người dùng trước khi áp dụng.

## 5. Bàn giao cho session thiết kế giao diện (13/11/2026, 17:00)

Trạng thái giao diện Lịch trình sau hai đợt phản hồi, mọi thứ chưa commit, chưa deploy:

| Phần | File | Ghi chú cho người thiết kế tiếp |
|---|---|---|
| Chọn phương án (tối đa 3, Lợi ích / Hạn chế, bấm thẻ = xem lịch) | `web/src/user/screens/plan/Choose.tsx`, `css/itinerary.css` (`.tg-it-pc`) | Thẻ chỗ ở phía trên vẫn 3 chỗ (`NoHotel` trong `parts.tsx`) |
| Tổng quan: Điểm xuất phát riêng, Đến Đà Lạt, lưới chỗ nghỉ đầy khung | `Overview.tsx`, `Plan.tsx`, `parts.tsx` (`LodgingGhost`), `css/plan.css` (`.tg-staygrid`) | Thẻ *Bạn khởi hành từ đâu?* lưu được chỉ sau deploy `src/` |
| Gợi ý khoảng trống: hàng thẻ cũ + "+" mở *Thêm trải nghiệm* (không còn quạt khi rê: chủ dự án 13/11 bỏ) | `GhostSlot.tsx`, `css/day.css` (`.tg-gdisc__plus`) | — |
| Thêm / Đổi trải nghiệm (thiết kế cũ, đè nửa bản đồ) | `Find.tsx`, `css/day.css` (`.is-pane`) | Nguồn *Tất cả* = cả danh mục (1789 nơi, 198 loại, khung loại cuộn) |
| Hành trình (sơ đồ lộ trình, bảng màu Lịch trình) | `Journey.tsx`, `css/journey.css` | Mục đúng như màn từng ngày; đường nét đứt nối *Kết thúc ngày* → *Nghỉ đêm* → *Xuất phát* ngày sau; chưa có chỗ ở thì ô ghi "Nghỉ đêm" |

Chạy thật: mục 3 (script `{common,toplan,plan2,wheel}.mjs` ở scratchpad của session 83dcc290). Ảnh mới nhất: `frontend_images/real6/`, `real7/`. Quy ước: chỉ dùng skill `ui-ux-pro-max` cho thiết kế, không dùng `superpowers:*`; **không build vào `web/dist`**.
