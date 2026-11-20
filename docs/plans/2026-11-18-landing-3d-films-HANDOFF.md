# Bàn giao deploy: landing mới (Khám phá 3D, hai phim, tinh gọn) — 18/11/2026

Chủ dự án (18/11) bảo: landing mới **đi cùng lần deploy của phiên planning** (`2026-11-18-planning-fast-optimal-HANDOFF.md`), không deploy riêng. Lý do: cây web đang chứa UI "Tối ưu lịch" dở của phiên planning (`Plan.tsx`, `plan/Choose.tsx`, `plan/parts.tsx`, `planning/api.ts`, `planning/planning.tsx`, `store.ts`); không tách được hai việc ra khỏi cùng một `vite build`.

## Việc cần làm khi deploy

1. Deploy đầy đủ như thường: `HARNESS_GPU=0 nohup ./run.sh prod > logs/run/deploy.log 2>&1 &`, rồi `./run.sh prod-check` (`docs/OPERATIONS.md`).
2. **Bắt buộc là deploy đầy đủ hoặc ít nhất restart `web/server.mjs`**: `server.mjs` có sửa mới (`LANDING_CLIP`: phục vụ `/media/landing/*.mp4` có Range; `/media/landing/` đệm 1 ngày). Chép đè `web/dist` mà không restart thì mp4 vẫn 404. Trước sửa, prod trả 404 cho mọi mp4 ngoài `/media/tiktok`.
3. Sau deploy, kiểm tay trên domain thật (chưa kiểm được ở máy dev):
   - `curl -sI -H "Range: bytes=0-99" https://<domain>/media/landing/langbiang.mp4` ra `206`.
   - Landing: cuộn tới `Khám phá` → bấm một ô 3D (hiện poster rồi mô hình); bấm phim Langbiang (phát được, tua được, kể cả Safari); bấm phim `Mùa xuân không về`: site Vercel mở trong khung, thanh tải chạy, bấm `Thắp đèn, nghe kể` có tiếng. Nếu khung phim trống thì đổi poster thành mở tab mới (`FILM_SITE` trong `Showcase.tsx`).

## Đã làm (chưa commit)

- `web/src/user/landing/Showcase.tsx` (mới), `web/src/user/screens/Landing.tsx`, `web/src/user/css/landing.css`, `web/src/user/ui/Space3d.tsx` (export `prefetch`), `web/server.mjs`, `web/public/media/landing/{langbiang.mp4,langbiang-poster.webp,ho-than-tho-poster.webp}`, `tests/web/test_landing_3d_structure.py`, `docs/UI_SPEC_LANDING.md`, mục DEV_LOG `landing` (18/11).
- Commit riêng các path này (không lẫn việc planning). `web/public/media/landing/langbiang.mp4` là 7,6 MB, chấp nhận được trong git; nếu repo giới hạn tệp lớn thì giữ ngoài git và chép vào `web/public/media/landing/` khi build.
- Kiểm: `npx tsc --noEmit -p web`, `pytest tests/web/test_landing_3d_structure.py` đều qua. Build ra thư mục tạm + `node server.mjs <cổng>` + Chromium: Range 206, hover dựng khung phim ẩn, đóng gỡ khung, 3D hiện poster rồi vào mô hình, Esc đóng.
- Chưa kiểm: phát mp4 thật (Chromium của Playwright không có H.264), site Vercel trong iframe trên domain thật.

## Còn mở

- Tên phim Langbiang: đang là "Langbiang" (theo tiêu đề phim); chủ dự án chưa xác nhận có đổi "Chiếc vòng đồng" không.
