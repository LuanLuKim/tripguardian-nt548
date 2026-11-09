# Guided Tour — đợt 1 (bản xem được) Implementation Plan

> **Cập nhật sau phản hồi chủ sản phẩm:** bỏ chương đăng nhập (tour bắt đầu từ homepage); thanh điều khiển chỉ Tiếp / Quay lại / Bỏ qua; lời bong bóng rất ngắn; mascot ~290 px. Sự kiện `tour_*` chưa gửi (allowlist ở `src/analytics` cần thêm tên trước).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Đợt 1 của hướng dẫn có linh vật: chương 0 (đăng nhập), chương 1 (trang chủ), chương 2 (thanh bên), kết (nhảy mừng + âm + pháo giấy, rồi đi chỉ nút "Tạo chuyến đi"). Chưa có chuyến mẫu, chưa có chương Tìm hiểu / Lựa chọn / Lịch trình / Sau chốt (đợt 2).

**Architecture:** `web/src/user/tour/` là module mới, đặt `TourProvider` trên `Shell` trong `UserApp.tsx`; mỗi điểm dừng là dữ liệu trong `steps.ts` trỏ tới phần tử thật qua `data-tour="<id>"`. Lớp phủ + lỗ chiếu sáng + linh vật (cùng cách trình bày `AuthMascot`) vẽ ở `document.body` bằng portal. Âm sinh bằng Web Audio.

**Tech Stack:** React 18 + TypeScript (Vite), CSS thường theo token, Playwright (full chromium-1169) để kiểm bằng mắt, Python + 9router cho ảnh.

**Spec:** `docs/plans/2026-10-31-guided-tour-design.md`

## Global Constraints

- Tài liệu tiếng Việt; code, comment, identifier, tên file tiếng Anh (`RULE.md` §0).
- Màu chỉ từ token (`user/css/tokens.css`); `--tg-brand` #b4532a chỉ làm điểm nhấn nhỏ; chỉ máy tính; tôn trọng `prefers-reduced-motion`.
- Không nút nổi lẻ loi; nút bắt đầu nằm trong bố cục có sẵn.
- Không gọi model trong tour; lời là văn bản cố định, giọng "TripGuardian / bạn".
- Âm + pháo giấy chỉ khi bấm "Xong"; tắt tiếng thì im; giảm chuyển động: không đi, không pháo (âm vẫn phát).
- Khách: tính năng bị khoá → lời mời "Đăng nhập để hưởng đầy đủ quyền lợi", không đẩy sang màn khoá.
- Không commit, không đẩy (thư mục làm việc dùng chung).
- Module chỉ giao tiếp qua `tour/index.ts`.

## Review Focus

- Phần tử đích không có trong DOM (dữ liệu chưa tải, bị ẩn): linh vật đứng giữa màn, nói không chỉ tay, không kẹt.
- Bấm Tiếp liên tiếp khi linh vật đang đi: không chồng bước, không lỗi.
- Cửa sổ đổi cỡ / cuộn giữa tour: lỗ chiếu sáng bám theo phần tử.
- Esc / Bỏ qua giữa chừng: dọn lớp phủ, không âm, không pháo.
- Tải lại trang giữa tour: không có gì treo; tour không tự chạy lại.

## File Structure

- `web/scripts/gen_tour_mascot.py` (đã viết): ảnh dáng mới → `web/public/img/tour/`.
- `web/src/user/tour/steps.ts`: dữ liệu chương + điểm dừng, `chaptersFor(kind)`.
- `web/src/user/tour/place.ts`: tính chỗ đứng của linh vật quanh một hình chữ nhật.
- `web/src/user/tour/sound.ts`: `playCheer()`, `isMuted()`, `setMuted()`.
- `web/src/user/tour/TourProvider.tsx`: trạng thái + `useTour()`.
- `web/src/user/tour/Tour.tsx`: lớp phủ, linh vật, bong bóng, thanh điều khiển, pháo giấy.
- `web/src/user/tour/index.ts`: API công khai.
- `web/src/user/css/tour.css`.
- Sửa: `UserApp.tsx`, `main`/CSS import chỗ import các css user, `Discover.tsx`, `home/Frame.tsx`, `home/Who.tsx` hoặc `Discover.tsx` (vỏ cho rail), `Auth.tsx`, `Support.tsx`, `events.ts` (nếu `Name` giới hạn).

## Tasks

### Task 1: Ảnh dáng linh vật
- [ ] Chạy `gen_tour_mascot.py` (terra cho `wave`, sol cho còn lại); xem từng ảnh; dáng lệch nhân vật thì `--force <pose>` tạo lại.
- Kết quả: `web/public/img/tour/{walk_a,walk_b,point,point_up,wave,wow,wink,love,cheer,bow}.webp` + `manifest.json`.

### Task 2: Placement (có test)
**Interfaces — Produces:** `placeMascot(target: Rect | null, view: {w:number;h:number}, size: number, bubbleH: number): { x:number; y:number; side:'left'|'right' }` (x,y = góc trên trái của hộp linh vật; `side` = phía có ô đích so với linh vật).
- [ ] Test (`web/scripts/test_tour_place.mjs`, Node thuần): đích bên trái màn → linh vật bên phải đích; đích sát cạnh phải → bên trái đích; đích sát đỉnh → `y >= bubbleH`; `target=null` → giữa màn; kết quả không giao với đích và nằm trong màn.
- [ ] Cài `place.ts` cho test qua.

### Task 3: Dữ liệu điểm dừng + âm
**Interfaces — Produces:** `type Pose`, `type Step = { id; chapter; target?: string; pose: Pose; say: string; guestSay?: string; cta?: 'done' | 'create' }`, `chaptersFor(kind: 'member'|'guest'|'visitor'): Chapter[]`; `playCheer(): void`, `isMuted(): boolean`, `setMuted(m: boolean): void`.
- [ ] Viết `steps.ts` đủ chương 0/1/2/kết theo spec §5 (chương 0 chỉ khách + người chưa đăng nhập; kết: bước `done` (nhảy mừng, nút "Xong") rồi bước `start` (đi chỉ `new-trip`, chỉ khi có)).
- [ ] Viết `sound.ts` theo spec §7 (bốn nốt C5–E5–G5–C6 + tiếng lấp lánh, gain ≤ 0,15, `localStorage` bọc try/catch).

### Task 4: Provider + lớp phủ + linh vật
**Interfaces — Consumes:** Task 2, 3. **Produces:** `TourProvider`, `useTour(): { start(kind?): void; stop(): void; active: boolean }`.
- [ ] `TourProvider` tính `kind` từ `useAccount()`; `start()` mở tour ở bước đầu; chuyển trang bằng `navigate` khi chương cần (`/app/login` cho chương 0, về `/app` cho chương 1).
- [ ] `Tour.tsx`: lỗ chiếu sáng (box-shadow) bám phần tử `[data-tour]` (cuộn vào giữa, theo dõi đổi cỡ), lớp chặn bấm, linh vật đi (walk_a/walk_b luân phiên, lật hướng, ~700 ms), chấm "…" ~700 ms rồi lời, thanh điều khiển (chấm tiến độ theo chương, Quay lại, Bỏ qua chương, Tắt tiếng, Tiếp / Xong), phím ← → Enter Esc, `aria-live`.
- [ ] Bước `done`: bấm Xong → `playCheer()`, pháo giấy ~2 s, nhảy mừng, rồi sang bước `start` (hoặc đóng nếu không còn bước).
- [ ] CSS `tour.css` theo token; tái dùng lớp bong bóng / chấm của `auth.css` (`tg-auth__say`, `tg-auth__dots`) khi hợp.

### Task 5: Gắn vào app
- [ ] `data-tour` lên phần tử thật: `Discover.tsx` (`search`, `hero`, `themes`), vỏ rail (`who`, `calendar`, `trending`), `Frame.tsx` (`nav-trips`, `nav-saved`, `nav-recent`, `nav-settings`, `nav-support`, `new-trip`), `Auth.tsx` (`auth-google`, `auth-email`, `auth-guest`, `auth-fine`).
- [ ] Nút "Hướng dẫn" (mặt linh vật) ở cuối `tg-hm__bar`; nút "Xem hướng dẫn cùng linh vật" trong `Support.tsx`; lối "Xem hướng dẫn" trong `Auth.tsx`.
- [ ] Bọc `Shell` bằng `TourProvider` trong `UserApp.tsx`; sự kiện `tour_start/tour_step/tour_skip/tour_done` qua `track`.

### Task 6: Kiểm bằng mắt + tài liệu
- [ ] Playwright (chromium-1169, phiên khách, Origin được viết lại như `explore.mjs`): chạy tour khách đủ chương, chụp ảnh từng điểm dừng; xem ảnh: lỗ chiếu sáng đúng ô, linh vật không che ô, "…" rồi lời, kết có pháo; không lỗi console.
- [ ] `tsc` + build web sạch.
- [ ] Cập nhật `docs/Role_Web_Functional_Design.md` §6 (hàng "Hướng dẫn có linh vật"), `docs/log/DEV_LOG.md`.

## Tự rà

- Phủ spec: chương 0/1/2/kết, khách bị khoá, "…", tay chỉ, đi, âm, pháo: có. Chưa phủ (đợt 2, ghi rõ): chương 3–6 + chuyến mẫu + khoá ghi phía máy chủ + `data-tour` đối chiếu test trên chuyến mẫu.
