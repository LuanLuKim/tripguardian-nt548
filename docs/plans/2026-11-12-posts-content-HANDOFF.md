# Bàn giao: nội dung cho màn Bài viết (12/11/2026)

Giao diện Bài viết (`/app/posts`) đã lên production 12/11/2026 (chỉ dựng lại `web/dist`, không đụng `src/` và dịch vụ). Màn này đang chạy bằng dữ liệu tạm; hai việc dưới đây là phần nội dung còn thiếu, giao cho phiên khác.

## Cập nhật 12/11/2026 (tối): Việc A và B đã làm

Chủ dự án chốt 12/11: phần giới thiệu viết giọng **hướng dẫn viên** (có lịch sử, điểm nổi bật; tóm tắt ngắn mà hấp dẫn, không quá "AI", không quá đời thường), làm cho **mọi nơi trong corpus**; bài PR đứng tên **hệ thống (TripGuardian)**, viết bằng sol; viết bằng sol, kiểm bằng Gemma UIT (khác họ model). Câu hỏi 1–2 ở §3 coi như đã trả lời: nguồn lịch sử dùng các trang đã crawl (Wikipedia, báo, trang du lịch; năm tháng cần nguồn chính thống hoặc 2 site), không crawl thêm.

| Việc | Ở đâu | Trạng thái |
|---|---|---|
| A. Giới thiệu mọi nơi | `src/corpus/intro/` (`evidence.py`, `gate.py`, `run.py`), `config/intro.yaml`, task `INTRO_WRITE` / `INTRO_CHECK`, vai trò `WRITER`; `python -m corpus intro build` → `data/dalat/intro/intros.json`; `corpus serving` gắn `details.intro`, card Agent có `about`; web `Intro` (`user/ui/PlaceDetails.tsx`) trong `Summary` của Bài viết và `PlaceSheet` | xong code + dữ liệu; mô tả đầy đủ `docs/CORPUS.md` §Giới thiệu địa điểm |
| B. Bài PR cho nơi có 3D | `src/corpus/intro/posts.py`, task `INTRO_POSTS`; `python -m corpus intro posts` → `data/dalat/intro/posts.json`; `web/scripts/export_posts.py` → `web/public/data/posts.json`; web: nhãn "TripGuardian biên tập", dòng nguồn cuối bài | xong code + dữ liệu |
| Tên địa điểm chuẩn hóa | `corpus.aggregate.naming` (`display_name` thêm luật, `distinct_names` tách chi nhánh), serving `identity.name` + `name_raw`, tìm theo tên khớp cả tên gốc (`retrieval.search_names`, Trip resolve, local resolve), `web/src/data/placeName.ts` cùng luật | xong code; vào dữ liệu prod khi dựng release mới |

**Chưa làm / cần chủ dự án:** dựng release mới (`python -m corpus normalize --rebuild`, không `--publish`) rồi publish và deploy web: phải chủ dự án cho phép (đổi dữ liệu prod đang đọc). Route harness cho bài người dùng (§2 "Chỗ đặt bài") vẫn chưa có; bài biên tập là file tĩnh.

## 0. Hiện trạng (lúc bàn giao, trước khi làm)

| Phần | Ở đâu | Ghi chú |
|---|---|---|
| Màn bài viết (danh sách nơi + bản đồ, trang đọc, trình viết) | `web/src/user/community/` (`Posts.tsx`, `Reader.tsx`, `Compose.tsx`, `PostMap.tsx`, `Search.tsx`, `data.ts`), `web/src/user/css/posts.css` | mô tả: `docs/Role_Web_Functional_Design.md` §6, dòng "Bài viết về địa điểm" |
| Kho bài viết | `web/src/user/community/data.ts` | **chưa có route harness**: bài, phản ứng, bình luận, nháp lưu ở `localStorage` (`tg.posts.v1`); 10 bài mẫu viết tay ở mảng `SEED` (nhãn "Bài mẫu"), chỉ 6 nơi |
| Khung giới thiệu đầu cột một nơi | `Summary` trong `Posts.tsx` | ghép `KnownFor` + `About` (`web/src/user/ui/PlaceDetails.tsx`) + một lời khách thật (`info(id).quotes[0]`) |
| Nơi có mô hình 3D | `web/space3d/places.json` (107 nơi, `slug` + `id`) | 107 nơi đã lên prod |

Giới hạn của `Summary` hôm nay: `About` chỉ nói "là loại gì, ở khu nào, điểm Google, điều hay được khen, điều cần lưu ý". Chưa có **thuyết minh** (lịch sử, ý nghĩa, vì sao đáng đến) và chưa có **lời kể kiểu review** cho quán cà phê. Chủ dự án muốn: nơi di tích (Dinh Bảo Đại…) có vài câu lịch sử; quán cà phê có vài câu như một bài review ngắn; mục đích là thu hút người dùng và cho biết sơ lược nơi đó.

## 1. Việc A — corpus cho khung giới thiệu

**Cần có**, với mỗi nơi (ưu tiên 107 nơi 3D, rồi các nơi nổi bật ở Trending), một bản ghi giới thiệu:

| Trường | Nội dung |
|---|---|
| `kind` | `heritage` (di tích, công trình, danh thắng) · `cafe_food` (quán) · `nature` · `other` |
| `story` | 2–4 câu thuyết minh cho `heritage` / `nature`: nơi này là gì, lịch sử hoặc đặc điểm chính, vì sao đáng đến |
| `taste` | 2–3 câu kiểu review cho `cafe_food`: không gian, món hay được nhắc, hợp đi với ai, giờ nào |
| `sources` | mỗi câu trỏ về bằng chứng: trang chính thức / bài viết, hoặc số người nhắc trong review (`n`) |

**Ràng buộc (bất biến của dự án, `AGENTS.md`):**
- Không bịa. Câu không có bằng chứng thì không viết; không có `story` thì khung giới thiệu giữ như hiện tại (chỉ `About`). Không có bằng chứng ≠ "không có".
- Lịch sử, năm tháng, tên người phải có nguồn chính thức hoặc nhiều nguồn độc lập; ghi nguồn ở `sources`. Không để model tự "nhớ" lịch sử.
- Offline ghi Place Intelligence; web chỉ đọc. Ghi qua module corpus (`src/corpus/serving/details.py` → `web/scripts/export_snapshot.py` → `Place.details` trong `web/src/data/types.ts`), không ghi thẳng từ web. Module chỉ gọi nhau qua `__init__.py`.
- Gọi model theo vai trò (Extractor / Judge), model và key ở config (`docs/LLM_PROVIDER.md`). Có bước Judge kiểm từng câu đối chiếu với `sources` trước khi vào serving.
- Văn phong tiếng Việt, ngắn, không quảng cáo quá lời; không dùng "nổi tiếng nhất", "độc nhất" khi không có nguồn.

**Việc cần làm:** (1) khảo sát nguồn có sẵn trong `data/` (gmaps, gsearch, official, tiktok) cho từng nơi 3D, đo bao nhiêu nơi có nguồn đủ cho `story`; (2) nếu thiếu, đề xuất nguồn cần crawl thêm (trang chính thức, du lịch) và hỏi chủ dự án trước khi crawl; (3) thêm trường vào serving + `docs/CORPUS.md`; (4) báo lại danh sách nơi đủ / chưa đủ nguồn.

**Phía web (làm sau khi có dữ liệu):** `Summary` đọc trường mới, ưu tiên `story` / `taste`, rồi mới tới `About`; hiện nguồn ở dòng nhỏ. Chưa làm trong lượt này.

## 2. Việc B — bài viết hay về các nơi có 3D

Chủ dự án muốn có vài bài viết hay, giọng PR, về các nơi đang có mô hình 3D, để màn Bài viết không trống và để người dùng thấy bài viết nên trông thế nào. Dùng sol 6.1 qua `scripts/diorama/run_agent.sh sol <brief.md> <run.log> <effort>`; chủ dự án đã nói được giao cho phiên khác làm (xem `docs/plans/2026-11-10-3d-scale-HANDOFF.md` cho cách chạy).

**Cấu trúc một bài** (khớp `Post` / `Block` trong `data.ts`): `title`, `blocks` (`p` đoạn, `h` tiêu đề phụ, `q` trích dẫn, `img` ảnh `cover:<n>` = ảnh thứ n của nơi), `tags` (≤ 5), `facts` (đi ngày / đi cùng / phương tiện / chi phí, bỏ trống được), `placeId`, tác giả.

**Ràng buộc:**
- Bài PR không được giả là bài của người dùng thật: tác giả là tài khoản biên tập "TripGuardian", nhãn riêng (không dùng "Bài mẫu", không bịa tên người, không bịa bình luận, không bịa số người thích).
- Mỗi sự kiện, giờ, giá, câu trích phải lấy từ corpus (review thật, serving `details`, `docs/CORPUS.md`); lời trích dùng nguyên văn một review có thật. Không có thì không viết. Dùng cùng kho bằng chứng với Việc A.
- Chỉ nơi đặc biệt, đẹp, nổi tiếng (3D không làm cho chuỗi, khách sạn; chủ dự án 11/2026). 2–3 bài cho mỗi nơi là đủ, không cần phủ hết 107.
- Ảnh chỉ lấy từ ảnh được phép (`web/public/data/photo_allow.json`: không có người).
- Cuối mỗi bài có thể nhắc "xem mô hình 3D của nơi này" (tab Khám phá 3D của `PlaceSheet`).
- Đi qua Judge / kiểm tay của con người trước khi vào kho; ghi lại những câu bị loại vì thiếu bằng chứng.

**Chỗ đặt bài:** hiện chỉ có `SEED` trong `data.ts` và `localStorage`. Bài thật cần một route harness (bảng bài viết, phản ứng, bình luận, quyền xem Công khai / Bạn bè / Chỉ mình tôi, cờ `consent` cho việc TripGuardian học từ bài công khai). Phiên nhận việc nên đề xuất schema và route trước, chờ chủ dự án duyệt, rồi mới thêm; web đổi `data.ts` từ `localStorage` sang gọi route đó. Bài biên tập có thể vào trước dưới dạng một file tĩnh do web đọc.

## 3. Câu hỏi cho chủ dự án

1. Nguồn cho phần lịch sử: chấp nhận crawl trang du lịch / chính thức nào?
2. Bài PR gắn tên "TripGuardian" hay một chuyên mục riêng (ví dụ "Góc nhìn TripGuardian")?
3. Bài do người dùng viết có cần kiểm duyệt trước khi hiện Công khai không?
