# Bàn giao: spec nâng cấp + spike 3D (2026-10-27)

Đọc file này, rồi chỉ đọc thêm thứ được trỏ tới. Không đọc lại bản spec cũ.

## 1. Spec (xong, chờ chủ dự án duyệt)

- File: `docs/superpowers/specs/2026-10-26-production-and-course-upgrade-design.md` (đã viết lại; bản cũ ở `logs/spec-2026-10-26-before-simplify.md`, chỉ để đối chiếu).
- Quyết định đã chốt nằm ở §9 của spec. Không mở lại.
- Việc còn lại: sau khi duyệt → `superpowers:writing-plans`. §5.12 (3D) cập nhật theo kết quả §2 dưới.

## 2. Spike 3D (đang dở)

Mục tiêu: xem 3D dựng từ video TikTok có đủ đẹp không; kết luận ghi vào spec §5.12; làm **trang demo** (Artifact) cho chủ dự án xem.

**Môi trường** (đều trong repo, gitignored):
- venv `.cache/splat/venv` (py3.10, torch 2.4 cu121, gsplat 1.4, VGGT `src/vggt`, lightglue, pycolmap 3.10).
- gsplat examples cần pycolmap fork: `PYTHONPATH=.cache/splat/pycolmap_fork:.cache/splat/shims` (`shims/fused_ssim.py` tự viết, máy không có nvcc).
- Weights: `HF_HOME=.cache/hf`, `TORCH_HOME=.cache/torch` (đã link `model.pt`).
- Cài code ngoài (git/pip từ GitHub) bị auto mode chặn → **đưa lệnh cho người dùng tự chạy**. Gói PyPI thường cài được.
- GPU: chỉ dùng **GPU 3** (`CUDA_VISIBLE_DEVICES=3`); 4,5,7 là Gemma của người dùng; 0,1,2,6 của người khác. 2080 Ti 11 GB.

**Script** (`logs/splat/`): `train.sh <scene> <out>` (gsplat 7k bước, không app_opt), `render_path.py <scene> <ckpt> <out>` (ra `compare.mp4`, `path.mp4`, `scene.splat`, `view.json`; chạy với PYTHONPATH fork + `.cache/splat/src/gsplat/examples`), `linhson/prep.py` (chọn frame + mask), `linhson/sfm.py` (COLMAP CPU), `linhson/to_ply.py`.

**Kết quả vòng 1** (đã ghi spec §5.12): Chùa Linh Sơn, VGGT 24 frame không BA, `conf_thres_value 1.5`, gsplat 7k + app_opt → PSNR 13,9, kém. `logs/splat/linhson/{scene,gs,linhson.ply}`.

**Vòng 2 — trạng thái:**

| Cách | Thư mục | Trạng thái | Việc tiếp |
|---|---|---|---|
| (a) VGGT + BA, 24 frame | `linhson/v2_ba/scene` | OOM 2 lần (tracker, rồi fine tracking). `--fine_tracking` là `store_true default=True`, CLI không tắt được | Thử `--max_query_pts 512 --query_frame_num 2`; hoặc giảm còn 16 ảnh; hoặc hỏi người dùng cho sửa `args.fine_tracking=False` trong demo |
| (b) COLMAP SfM 96 frame (CPU) | `linhson/v2_sfm/scene` | **Đang chạy** (pid `sfm.py`, log `v2_sfm/sfm.log`), máy tải cao nên chậm | Xong → kiểm `sparse/0` có ≥ 70% ảnh → `GPU=3 ../train.sh v2_sfm/scene v2_sfm/gs` → `render_path.py` |
| (c) Dinh Tỉnh Trưởng, video `7648281720831200519` 31–62 s (đi vòng quanh nhà, trời nắng) | `dinh/scene/images` (124 frame) | Đã trích frame | `sfm.py dinh/scene` → train → render |

Kiểm tra (b): `pgrep -af sfm.py; grep -v "^[IW]20" logs/splat/linhson/v2_sfm/sfm.log | tail`.

**Trang demo** (chưa làm): Artifact HTML (gọi `Artifact action=quickstart intent=other` trước), mỗi cách một khối: số đo (PSNR/SSIM frame giữ lại, thời gian), `compare.mp4` (thật | render, vạch vàng = frame không train), `path.mp4`; viewer 3D xoay được (`@mkkellogg/gaussian-splats-3d` từ jsdelivr, nạp `scene.splat` ≤ 15 MB qua `files`, camera đặt theo `view.json`, up = `-y` kiểu COLMAP). Vòng 1 chỉ có ảnh `linhson/gs/renders/*.png` + số. Ghi rõ "dựng tự động từ video TikTok, chỉ để xem". Lý do người dùng thấy xấu: xem từ xa quỹ đạo quay; viewer phải đặt camera gần quỹ đạo.

**Tiêu chí kết luận:** cách nào đạt PSNR ≥ 25 trên frame giữ lại → viết pipeline; không cách nào đạt → sản phẩm chỉ dùng clip lia tự chọn (bước 1). Ghi vào spec §5.12 + memory `course-upgrade-design-2026-10-26`.
