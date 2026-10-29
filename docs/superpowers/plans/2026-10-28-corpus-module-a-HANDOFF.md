# Bàn giao: Module A Corpus (2026-10-28)

> Bàn giao làm việc, tạm thời (`RULE.md` §0.1). Phiên mới đọc file này trước, rồi ledger. Xóa khi module A xong.

## Chủ dự án muốn gì

- Làm **toàn bộ phần Corpus (A.1–A.9)** của spec `docs/superpowers/specs/2026-10-26-production-and-course-upgrade-design.md`.
- Corpus xây để **khâu khác dùng**: sol (Agent Trip) và Place Decision truy xuất **nhanh, dễ RAG**; mọi giá trị có nguồn.
- Cách làm: xem §Cách chạy bên dưới (chốt cuối 2026-10-28).
- Gemma tự host đã chạy lại: `gemma26b-a4b` ở `127.0.0.1:30002`, sau gateway `:30000`, khoảng 8 req/s, có tool call. Cần thì dùng.
- "Cho chạy hết": được chạy Chromium **ngoài sandbox** (cờ mặc định, không UA giả, không cờ né phát hiện) để đo / crawl.
- **Không commit / không `git add`** (working tree dùng chung với session khác). Review dùng diff theo đường dẫn.

## Đọc theo thứ tự

| File | Là gì |
|---|---|
| `docs/superpowers/plans/2026-10-28-corpus-module-a-roadmap.md` | lộ trình P0–P8, phụ thuộc, số đo "xong khi", quyết định builder |
| `docs/superpowers/plans/2026-10-28-corpus-serving-for-sol-and-decision.md` | plan chi tiết **P1** (5 task) |
| `docs/superpowers/plans/2026-10-28-corpus-p2-web-documents.md` | plan chi tiết **P2** (10 task, Sonnet viết, đã sửa 7 lỗi của roadmap — xem ledger) |
| `.superpowers/sdd/2026-10-28-corpus-serving-for-sol-and-decision/progress.md` | **ledger**: bảng quét, mọi `Ruling:`, trạng thái từng task, minor hoãn |
| cùng thư mục: `task-N-brief.md`, `task-1-2-report.md`, `review-t1-2-verdict.md`, `constraints.md`, `pkg.sh` | brief, báo cáo, review, ràng buộc chung, script tạo gói diff |

## Trạng thái (cập nhật 2026-10-28 14:45)

| Phase | Trạng thái | Việc tiếp |
|---|---|---|
| P0 crawl treo | **tạm dừng, chưa giải được.** D-Bus `/run/user/2420/bus` treo: Chromium trần tắt D-Bus vào TikTok 1,2 s, Maps 3,3 s (bật thì 28–45 s). Nhưng đường crawl thật (`corpus.crawl.open_sessions`, đúng env đã chạy được hôm 27/10) vẫn hết hạn chờ 30 s trên Maps/TikTok/Travel kể cả khi tắt D-Bus, rồi `ctx.close()` treo và trình duyệt kẹt hẳn; Chromium trần cũng kẹt 2/6 lần. Chi tiết trong ledger (`P0 findings`) | chỉ chặn P5 (giá phòng mỗi giờ, media). Dò tiếp: chạy `logs/crawl_path_check.py` (lệnh trong docs/CORPUS.md §Xử lý lỗi), xem tiến trình renderer/zygote và network service lúc kẹt. **Theo `RULE.md` §7 (F001): kiểm đường đã chạy được trước, không dựng probe mới** |
| P1 lớp đọc | **xong**, release `r-3526a43af23d55a4915aecca-bb18c207` **đã publish** 2026-10-28 (chủ dự án yêu cầu; `data/releases/current`, rollback = xóa pointer hoặc publish release cũ). Tiến trình prod đang chạy chưa khởi động lại | minor hoãn trong ledger P1 |
| P2 web + Document | **xong** (10 task, chưa commit; ledger `.superpowers/sdd/2026-10-28-corpus-p2-web-documents/progress.md`). Đo 50 query: `logs/web_probe_50_2026-10-28.json` (40/50 query rồi engine chặn; 282 video mới, 335 URL trang, 39 Document) | còn 10 slug query chạy tiếp ngày sau: `python -m corpus web search` |
| P3–P8 | chưa bắt đầu. **P5 do session `tripguardian-77` nhận** (2026-10-28), đừng làm trùng | việc tiếp: P3 (sol dẫn đường) — viết plan superpowers rồi làm |

## File đang sửa, chưa commit (của luồng này)

P1: `src/corpus/serving/record.py`, `tests/serving/test_serving.py`, `src/corpus/retrieval/{card,find}.py` (mới), `src/corpus/retrieval/engine.py`, `src/corpus/retrieval/__init__.py`, `tests/retrieval/{test_card,test_find}.py` (mới), `src/bench/retrieval.py` (mới), `src/bench/__main__.py`, `tests/bench/test_retrieval_bench.py` (mới), `docs/CORPUS.md`, `docs/log/DEV_LOG.md`, spec A.8. P0: `logs/pw_probe.py`, `logs/crawl_path_check.py`. Rule: `RULE.md` §7, `docs/log/AGENT_FAILURES.md` F001. Plan: 5 file trong `docs/superpowers/plans/`.

## Cách chạy SDD ở đây

**Cách làm (chủ dự án chốt 2026-10-28):** viết plan bằng superpowers xong thì **model đang dùng làm hết**. Có gọi skill superpowers thì theo đúng flow của skill, không chỉnh gì thêm. Vẫn giữ: không commit, bàn giao khi context dài.

- Gói review: `.superpowers/sdd/<plan>/pkg.sh <out.md> <path>…` (diff theo đường dẫn với HEAD + toàn văn file mới).
- Test: `.venv/bin/python -m pytest --collect-in-virtualenv <path> -q` (thiếu cờ thì treo trên NFS).

## Dữ kiện đã đo (đừng đo lại)

- Serving 3.172 nơi; bản ghi trung vị 8,9k ký tự; `card` p50 583 / p95 1.316 / max 2.480 ký tự, 0,04 ms.
- 15 nơi có `entry_fee = free` mâu thuẫn với vé ước từ review (Đồi Chè Cầu Đất: free 22 / paid 12, vé ước 100.000).
- Khối `details` gần như trống: `known_for` / `order` / `avoid` = 0 nơi, `activity` 162 (đều `UNCERTAIN`), `best_months` 29, menu 899 — việc của plan bổ sung chi tiết 13 mục, ngoài module A.
- 3.133 / 3.172 `visit_minutes` là `category_default`.
- Dịch vụ sống 2026-10-28: 9router sol :20128, SearXNG :8888 (~3,5 s/query), gateway Clef :30000.
- Place Decision `create` p50 ~50 ms trên 3.208 nơi (`data/bench/latency/20261013-163300.json`).
