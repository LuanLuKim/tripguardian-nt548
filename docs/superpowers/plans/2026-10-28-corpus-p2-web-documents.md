# Module `web` + Document (P2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SearXNG thành một nguồn của corpus: một client dùng chung có ngân sách và nhật ký engine, một phase `web search` tìm URL video TikTok / câu tìm thật (slug `/discover/`) / trang báo-blog, một phase `web documents` tải trang thành `Document` chia theo heading. Đo bằng 50 query Đà Lạt.

**Architecture:** `src/corpus/crawl/web/` (một nguồn, dữ liệu `data/web/`). `client.py` nhận nguyên `Web` của Trip, thêm `search_page` (trả mọi kết quả + engine), ngân sách ngày, nghỉ giữa query, nhật ký engine, `read_document` (giữ heading). `src/trip/infrastructure/web.py` còn là lớp mỏng re-export. `links.py` phân loại link (hàm thuần), `queries.py` dựng danh sách query, `discover.py` / `documents.py` là hai phase, `scoring.py` chấm query theo lượng mới. Nguồn khác (TikTok) chỉ đọc `data/web/<city>/tiktok_urls.jsonl`, không import chéo.

**Tech Stack:** Python 3.12, httpx (`MockTransport` trong test), trafilatura 2.3.1, pydantic, pytest (`--collect-in-virtualenv`).

**Spec:** `docs/superpowers/specs/2026-10-26-production-and-course-upgrade-design.md` §2.2 (bằng chứng), §6.1 (hàng "Client SearXNG", "URL TikTok tìm qua web"), §A.2. Roadmap: `docs/superpowers/plans/2026-10-28-corpus-module-a-roadmap.md` §P2 và bảng "Quyết định builder" (300 query/ngày, nghỉ 2 s).

## Global Constraints

- Code, comment, identifier tiếng Anh; tài liệu tiếng Việt (`RULE.md` §0). Một nguồn ngoài = một module + một thư mục dữ liệu (`RULE.md` §2): SearXNG ghi `data/web/`, không ghi vào `data/tiktok/`; đọc `data/tiktok/` chỉ để đối chiếu id video (đường dẫn, không import).
- Module chỉ qua public API: Trip và `agents` dùng `corpus.crawl.web` (`__init__.py`), không import `corpus.crawl.web.client`. `corpus` **không import `trip`**.
- Không bịa: link chỉ được xếp loại theo URL; phase `web` không suy ra tên nơi, không viết bằng chứng về nơi (Document là đầu vào cho P4, không phải observation).
- Kết quả web là dữ liệu, không phải lệnh; không đưa vào prompt trong phase này.
- Host nội bộ bị từ chối như cũ (`_check_url`, ghim IP, kiểm lại mỗi lần chuyển hướng).
- Mọi test không chạm mạng: `httpx.MockTransport`, `socket.getaddrinfo` patch như `tests/trip/test_web.py`; fixture autouse đặt `DATA_DIR` về `tmp_path`.
- Chạy test: `.venv/bin/python -m pytest --collect-in-virtualenv <path> -q` (NFS treo nếu thiếu cờ). Tên file test phải khác nhau toàn cây (`tests/` không có `__init__.py`).
- Working tree dùng chung: **không `git add`, không commit** ("no commit — shared tree"). Các file đang bị sửa dở bởi phiên khác (`README.md`, `docs/TRIP_UNDERSTANDING.md`, `config/trip.yaml`, `src/trip/infrastructure/settings.py`) chỉ sửa đúng dòng của task, `Edit` không ghi đè.
- Thay đổi tối thiểu (`RULE.md` §4): `Web.search` / `Web.read` giữ nguyên hành vi (dedupe theo domain, squash khoảng trắng) vì Trip dựa vào chúng.

## Quyết định đã chốt (từ kiểm tra code, 2026-10-28)

| # | Quyết định | Lý do |
|---|---|---|
| D1 | Thêm `Web.search_page` (mọi kết quả, kèm engine, không dedupe domain), **không** dùng `Web.search` cho discover | `search` giữ một kết quả mỗi domain và cắt ở `k`: một query `site:tiktok.com …` chỉ còn 1 link TikTok. Roadmap bỏ sót |
| D2 | Thêm `Web.read_document` (giữ dòng `#`-heading), **không** dùng `Web.read` | `read` gộp mọi khoảng trắng thành một dấu cách → mất heading. Đã chạy thử: `trafilatura.extract(..., output_format="txt", include_formatting=True)` trả `# …` / `## …`; `output_format="markdown"` bản 2.3.1 thì không |
| D3 | `validate_public_url` chuyển vào `corpus/crawl/web/client.py`, xuất ở public API; `src/agents/input_guard.py` import lại từ `corpus.crawl.web` | `agents` đã import `corpus.llm`; corpus **không** được import `agents` (import `agents` mất ~1 s, kéo `openai`, và đảo chiều phụ thuộc). Một định nghĩa duy nhất. Giá phải trả: `agents` import `corpus.crawl` (đo 0,15 s, kéo `playwright`) |
| D4 | `Frozen` của Trip → `_Frozen(BaseModel)` trong `client.py` với `ConfigDict(frozen=True, extra="forbid")` (giống `trip.domain.state.Frozen`) | corpus không import trip; `WebHit` / `WebPage` giữ thuộc tính và hành vi |
| D5 | Cache của corpus ở `data/web/cache/`; cache của Trip vẫn `data/web_cache` (Trip tự truyền đường dẫn) | Trip không đổi; hai cache khác `kind` nên không lẫn |
| D6 | File toàn cục `data/web/engines.jsonl`, `data/web/budget.json`; file theo thành phố ở `data/web/<city>/` | Engine và ngân sách là của SearXNG chung, không của một thành phố |
| D7 | Cấu hình ở `config/queries.yaml` khối `web:` (một chỗ cho "query và trần số lượng", `docs/CORPUS.md` §Dữ liệu thô) | Không thêm file config mới |
| D8 | `doc_id = sha1(canonical_url)[:16]`; canonical = bỏ `www.`, fragment, `utm_*` / `fbclid` / `gclid`, dấu `/` cuối, host hạ chữ thường | Hai URL chỉ khác tham số theo dõi không thành hai Document |
| D9 | `docs_new` trong `query_yield` đếm **URL tài liệu mới** lúc search (chưa tải) | Chấm query không phụ thuộc phase `documents` chạy chưa |
| D10 | Nhân đôi ngân sách cho nhóm query "nóng" **không làm ở P2**; P2 chỉ tính `hot_groups` (≥ 2× trung vị) và xếp query của nhóm đó lên đầu run sau | Roadmap không định nghĩa "ngân sách theo nhóm"; vòng và ngân sách là việc của P8 |

## Review Focus

1. Trip không đổi hành vi: `tests/trip/test_web.py`, `tests/trip/test_agent_web.py`, `tests/trip/test_agent_tools.py` pass **không sửa dòng nào**; `Web(base_url, cache_dir, timeout_s, ttl_days)` không có ngân sách, không ghi nhật ký (Task 1, 2: `test_plain_web_has_no_budget_and_no_log`).
2. Cache hit không tốn ngân sách, không nghỉ, không ghi engine; ngân sách hết thì **không có request HTTP** (Task 2: `test_cache_hit_is_free`, `test_budget_exhausted_raises`).
3. Trang trả 0 kết quả mà có `unresponsive_engines` = bị chặn: không cache, không tạo `search/<hash>.json` (lần sau thử lại), 3 lần liên tiếp thì dừng phase (Task 6).
4. Video / profile / ảnh TikTok: chỉ `/@u/video/<id>` thành video; slug lạc đề ("coach-mint-ashton-bag", tiếng Thái) bị bỏ (Task 3).
5. Chạy lại không nhân đôi dòng nào ở ba file `.jsonl` (Task 6: `test_second_run_is_free_and_idempotent`).
6. `Document` không bao giờ dài hơn 40.000 ký tự và luôn ghi `cut` (Task 7).

---

### Task 1: Chuyển `Web` sang `corpus.crawl.web`, Trip dùng lại

**Files:**
- Create: `src/corpus/crawl/web/__init__.py`, `src/corpus/crawl/web/client.py`
- Modify: `src/trip/infrastructure/web.py` (thành lớp mỏng), `src/agents/input_guard.py` (xóa định nghĩa `validate_public_url`, import lại; xóa import `ipaddress` / `SplitResult` nếu không còn dùng), `src/corpus/crawl/__init__.py` (docstring: ngoài ba tên, `corpus.crawl.web` có public API riêng)
- Test: `tests/trip/test_web.py` (**không sửa**), `tests/crawl/web/conftest.py`, `tests/crawl/web/test_web_move.py`

**Interfaces:**
- Produces (public, `corpus.crawl.web`): `Web`, `WebHit`, `WebPage`, `WebError`, `validate_public_url`. Các tên còn lại thêm ở Task 2 và 8.
- Mã `client.py` = nội dung hiện tại của `src/trip/infrastructure/web.py` với đúng ba thay đổi: `Frozen` → `_Frozen` (D4); `from agents import validate_public_url` → định nghĩa tại chỗ (D3, chép nguyên thân hàm từ `src/agents/input_guard.py:45-63`, thêm `import unicodedata`); `from ..domain.state import Frozen` bỏ.
- Lớp mỏng Trip:

```python
"""Trip's door to the web: the client lives in corpus.crawl.web (one SearXNG source for corpus and Trip)."""
import socket  # noqa: F401  tests/trip/test_web.py patches web_mod.socket (the same module object as client.socket)
from corpus.crawl.web import Web, WebError, WebHit, WebPage
__all__ = ["Web", "WebError", "WebHit", "WebPage"]
```

- [ ] **Step 1: Test** `tests/crawl/web/conftest.py`: fixture autouse `offline(monkeypatch, tmp_path)` → `DATA_DIR=tmp_path`, `socket.getaddrinfo` ném `OSError("offline")` (test đọc trang patch lại). `test_web_move.py`: `test_trip_shim_reexports` (`trip.infrastructure.web.Web is corpus.crawl.web.Web`, cùng `WebHit`, `WebError`); `test_validate_public_url_single_definition` (`agents.validate_public_url is corpus.crawl.web.validate_public_url`; `http://127.0.0.1/` và `http://localhost/` ném `ValueError`; `https://example.com/` trả `SplitResult`); `test_corpus_does_not_import_trip_or_agents` (chạy `subprocess` `python -c "import corpus.crawl.web, sys; assert not [m for m in sys.modules if m.split('.')[0] in ('trip','agents')]"` với `PYTHONPATH=src`).
- [ ] **Step 2:** chạy `tests/crawl/web/test_web_move.py` → FAIL (module chưa có).
- [ ] **Step 3:** tạo `client.py` (chép + 3 sửa), `__init__.py` (docstring một dòng + `__all__`), thay `trip/infrastructure/web.py`, sửa `input_guard.py`, docstring `corpus/crawl/__init__.py`.
- [ ] **Step 4:** `.venv/bin/python -m pytest --collect-in-virtualenv tests/crawl/web tests/trip/test_web.py tests/trip/test_agent_web.py tests/trip/test_agent_tools.py tests/agents -q` PASS. Nếu `tests/trip/test_web.py` đỏ vì `web_mod.socket`, kiểm dòng `import socket` ở lớp mỏng; **không** sửa test.
- [ ] **Step 5:** `PYTHONPATH=src .venv/bin/python -c "import trip.api.engine"` không lỗi; không `git add` / commit (no commit — shared tree).

### Task 2: Client — `search_page`, ngân sách, nghỉ, nhật ký engine, `read_document`

**Files:**
- Modify: `src/corpus/crawl/web/client.py`, `src/corpus/crawl/web/__init__.py`, `config/queries.yaml` (thêm khối `web:`)
- Test: `tests/crawl/web/test_web_client.py`

**Interfaces:**

```python
class SearchResult(_Frozen): url: str; title: str; snippet: str; engines: tuple[str, ...]
class SearchPage(_Frozen):
    query: str; results: tuple[SearchResult, ...]
    unresponsive: tuple[tuple[str, str], ...] = ()      # (engine, reason) từ "unresponsive_engines"
    cached: bool = False
    @property
    def blocked(self) -> bool: ...                       # not results and bool(unresponsive)
class WebDocument(_Frozen): url: str; title: str; domain: str; text: str; chars: int; cut: bool; lang: str
class BudgetExhausted(WebError): ...                     # "daily query budget used up (300/300)"

class Web:
    def __init__(self, base_url, cache_dir, timeout_s=6.0, ttl_days=30, max_bytes=2_000_000, client=None, *,
                 state_dir: Path | None = None, daily_queries: int | None = None, min_interval_s: float = 0.0,
                 clock=time.monotonic, sleep=time.sleep, today=lambda: date.today-UTC iso string): ...
    @classmethod
    def from_config(cls, cfg_web: dict, root: Path, client=None) -> "Web": ...   # root = data_dir()/"web": cache_dir=root/"cache", state_dir=root
    def search_page(self, query: str) -> SearchPage
    def read_document(self, url: str, max_chars: int = 40_000) -> WebDocument
    def budget_left(self) -> int | None                  # None khi không có daily_queries
```

Hành vi chốt:
- `search_page`: query 1–200 ký tự (như `search`, `ValueError`). Cache kind `"page"` khóa = query, trả `cached=True`. Chỉ trang **không** `blocked` mới được cache.
- Lượt gọi mạng: (1) nếu `daily_queries` đặt và `budget.json` `{"day": "YYYY-MM-DD" (UTC), "used": n}` có `used >= daily_queries` → `BudgetExhausted` trước mọi request; ngày đổi thì `used = 0`. (2) nghỉ `max(0, min_interval_s − (clock() − last_end))` bằng `sleep`; `last_end` chỉ cập nhật sau lượt mạng, cache hit không nghỉ. (3) tăng `used` **trước** request (timeout vẫn tính, vì engine đã bị gọi), ghi nguyên tử. (4) ghi một dòng `state_dir/engines.jsonl`: `{"at", "query", "n", "engines": {"duckduckgo": 12, "google cse": 4}, "unresponsive": [["brave", "Suspended: too many requests"]]}` — `engines` đếm số kết quả mỗi engine (một kết quả có thể có nhiều engine). Lỗi HTTP / timeout → `WebError` như `search`, vẫn tính ngân sách, ghi dòng `{"error": "..."}`.
- Không đặt `state_dir` / `daily_queries` / `min_interval_s` (Trip) → không đếm, không nghỉ, không ghi file.
- `read_document`: dùng chung đường tải với `read` (tách `_fetch_page(url) -> (final, media_type, content)` từ thân `read`; `read` gọi lại nó, hành vi giữ nguyên). HTML: `trafilatura.extract(content, output_format="txt", include_formatting=True, include_comments=False, include_tables=False)`; `text/plain`: nguyên văn. Chuẩn hóa: bỏ khoảng trắng cuối dòng, từ 3 dòng trống liền trở lên gộp thành 1 dòng trống. `chars` = độ dài trước khi cắt; `text = text[:max_chars]`; `cut = chars > max_chars`. `lang`: `"vi"` nếu ≥ 1 % ký tự thuộc `ăâđêôơưĂÂĐÊÔƠƯ`, còn lại `"und"`. Trang rỗng → `WebError("empty page")`. Cache kind `"doc"`.
- `config/queries.yaml` khối mới (giá trị chốt):

```yaml
web:                       # SearXNG (docs/CORPUS.md §Nguồn): python -m corpus web <search|documents|all>
  base_url: http://127.0.0.1:8888
  timeout_s: 10.0
  cache_ttl_days: 30
  daily_queries: 300       # queries to the engines per UTC day; cache hits are free
  min_interval_s: 2.0      # between two real queries
  stop_after_blocked: 3    # consecutive blocked / failed queries end the search phase
  slug_queries_per_run: 25
  gap_queries_per_run: 20
  doc_max_chars: 40000
  doc_min_chars: 300
  page_pause_s: 1.0        # between two page reads
```

- [ ] **Step 1: Tests** (`MockTransport`, đồng hồ giả `clock`/`sleep`/`today` tiêm vào):
  - `test_search_page_returns_every_result_and_engines`: 3 kết quả cùng `tiktok.com` + `unresponsive_engines: [["brave","Suspended: too many requests"]]` → `len(results) == 3` (khác `search`: dedupe domain), `results[0].engines == ("duckduckgo",)`, `unresponsive == (("brave", "Suspended: too many requests"),)`.
  - `test_search_page_logs_engines`: `engines.jsonl` đúng một dòng, `n == 3`, `engines == {"duckduckgo": 2, "google cse": 1}`.
  - `test_cache_hit_is_free`: gọi hai lần cùng query → handler 1 lần, `budget.json used == 1`, `engines.jsonl` 1 dòng, lần hai `cached is True`, `sleep` không được gọi lần hai.
  - `test_blocked_page_is_not_cached`: `results: []` + `unresponsive` → `blocked is True`; gọi lại → handler 2 lần; `used == 2`.
  - `test_budget_exhausted_raises`: `daily_queries=2`, ba query khác nhau → lần ba ném `BudgetExhausted` (`"2/2"` trong thông báo), handler đúng 2 lần; query đã cache vẫn trả được sau đó.
  - `test_budget_resets_on_new_day`: `today` đổi → `used` về 0, `budget_left() == 2`.
  - `test_min_interval_sleeps_between_real_queries`: `min_interval_s=2.0`, `clock` giả tăng 0,5 s giữa hai query → `sleep` được gọi với `1.5`; query đầu không nghỉ.
  - `test_failed_request_counts_and_raises`: handler ném `httpx.ReadTimeout` → `WebError`, `used == 1`, dòng log có `error`.
  - `test_plain_web_has_no_budget_and_no_log`: `Web("http://search.test", tmp_path, client=…)` gọi `search_page` → không tạo `budget.json` / `engines.jsonl`, `budget_left() is None`.
  - `test_read_document_keeps_headings`: HTML `<h1>Đà Lạt</h1><p>…</p><h2>Đi mùa nào</h2><p>…</p>` (patch `getaddrinfo` như test hiện có) → `"\n## Đi mùa nào\n"` có trong `text`, `lang == "vi"`, `cut is False`.
  - `test_read_document_cuts_and_flags`: trang `text/plain` 60.000 ký tự, `max_chars=40_000` → `len(text) == 40_000`, `chars == 60_000`, `cut is True`.
  - `test_from_config_uses_root_dirs`: `Web.from_config({...}, tmp_path/"web")` → cache ở `tmp_path/"web"/"cache"` sau một query, `daily_queries == 300`.
- [ ] **Step 2:** chạy → FAIL.
- [ ] **Step 3:** viết code (sửa `read` chỉ ở chỗ tách `_fetch_page`), thêm khối `web:` vào `config/queries.yaml` (không đổi khối khác), export `SearchPage`, `SearchResult`, `WebDocument`, `BudgetExhausted` ở `__init__.py`.
- [ ] **Step 4:** `pytest --collect-in-virtualenv tests/crawl/web tests/trip/test_web.py tests/trip/test_agent_web.py -q` PASS.
- [ ] **Step 5:** no commit — shared tree.

### Task 3: `links.py` — phân loại link

**Files:**
- Create: `src/corpus/crawl/web/links.py`
- Test: `tests/crawl/web/test_web_links.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class Link:
    kind: str            # "video" | "discover" | "doc" | "drop"
    url: str             # video: URL chuẩn https://www.tiktok.com/@<author>/video/<id>; doc: URL gốc; còn lại như vào
    video_id: str = ""
    author: str = ""
    text: str = ""       # discover: câu tìm đã giải mã ("du lịch đà lạt")
    reason: str = ""     # drop: "social" | "ota" | "photo" | "tiktok_other" | "file" | "invalid"

def classify(url: str) -> Link
def slug_relevant(text: str, city_name: str) -> bool     # fold(text) chứa fold(city_name) hoặc dạng bỏ dấu cách ("dalat")
def canonical_url(url: str) -> str
def doc_id(url: str) -> str                               # sha1(canonical_url(url))[:16]
```

Quy tắc (theo thứ tự):
1. URL không phải http(s) hoặc không có host → `drop/invalid`.
2. Host `tiktok.com` hoặc `*.tiktok.com` (kể cả `notes.`, `m.`, `support16-…`):
   - path khớp `^/@([A-Za-z0-9._]{1,64})/video/(\d{8,25})/?$` → `video`;
   - `/@…/photo/<id>` → `drop/photo` (pipeline `poi_crawl` cũng bỏ bài ảnh);
   - path khớp `^/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?discover/([^/]+)/?$` → `discover`, `text` = `unquote(slug)`, `-` và `_` → dấu cách, NFC, gộp khoảng trắng (query `?region=vn` bỏ);
   - còn lại (profile, `/tag/`, `vm.tiktok.com` link rút gọn…) → `drop/tiktok_other`.
3. Đuôi `.pdf .jpg .jpeg .png .gif .webp .mp4 .zip .doc .docx .xls .xlsx` → `drop/file`.
4. Host (khớp `host == d` hoặc `host.endswith("." + d)`) thuộc `SOCIAL` → `drop/social`: `facebook.com fb.com fb.watch instagram.com youtube.com youtu.be twitter.com x.com pinterest.com threads.net threads.com linkedin.com reddit.com zalo.me lemon8-app.com t.me snapchat.com douyin.com bilibili.com`.
5. Host thuộc `OTA` → `drop/ota`, **trừ** khi path chứa `/blog` (Klook, Mytour có blog bài viết thật — đã thấy trong kết quả): `booking.com agoda.com traveloka.com expedia.com trip.com tripadvisor.com tripadvisor.com.vn airbnb.com klook.com kkday.com mytour.vn ivivu.com vntrip.vn hotels.com trivago.com google.com`.
6. Còn lại → `doc`.

`canonical_url`: scheme+host hạ chữ thường, bỏ `www.`, bỏ fragment, bỏ tham số `utm_*`, `fbclid`, `gclid` (giữ các tham số khác theo thứ tự gốc), bỏ `/` cuối path (trừ path `/`).

- [ ] **Step 1: Tests** (parametrize):
  - `test_tiktok_video_urls`: `https://www.tiktok.com/@adinhsg/video/7433374830822526216`, `…?lang=vi` và `https://m.tiktok.com/@a.b_c/video/7433374830822526216/` → `kind == "video"`, `video_id == "7433374830822526216"`, `url == "https://www.tiktok.com/@a.b_c/video/…"`.
  - `test_tiktok_non_video_is_dropped`: `/@du_lich_dalat` → `tiktok_other`; `/@x/photo/7433374830822526216` → `photo`; `https://vm.tiktok.com/ZS8abc/` → `tiktok_other`; `/tag/dalat` → `tiktok_other`.
  - `test_discover_slug_variants`: `https://www.tiktok.com/discover/du-l%E1%BB%8Bch-%C4%91%C3%A0-l%E1%BA%A1t` → `text == "du lịch đà lạt"`; `https://notes.tiktok.com/discover/du%20l%E1%BB%8Bch%20%C4%91%C3%A0%20l%E1%BA%A1t?region=vn` → cùng `text`; `https://www.tiktok.com/vi-VN/discover/c%E1%BA%A3nh-%C4%91%C3%A0-l%E1%BA%A1t` → `"cảnh đà lạt"`.
  - `test_slug_relevant`: `"thành phố đà lạt mới nhất 2026"` True; `"dalat"` True; `"coach mint ashton bag"` False; chuỗi Thái False.
  - `test_social_and_ota_dropped`: `https://m.facebook.com/x`, `https://www.youtube.com/watch?v=1`, `https://www.instagram.com/p/1/` → `social`; `https://www.booking.com/hotel/vn/x.html`, `https://www.agoda.com/vi-vn/x` → `ota`.
  - `test_ota_blog_is_kept`: `https://www.klook.com/vi/blog/du-lich-da-lat/` và `https://mytour.vn/vi/blog/bai-viet/x.html` → `doc`.
  - `test_news_and_gov_are_docs`: `https://vnexpress.net/x`, `https://dalat.lamdong.gov.vn/x`, `https://vi.wikipedia.org/wiki/%C4%90%C3%A0_L%E1%BA%A1t` → `doc`.
  - `test_file_and_invalid_dropped`: `https://a.vn/x.pdf` → `file`; `ftp://a/b`, `not a url` → `invalid`.
  - `test_canonical_and_doc_id`: `https://www.A.vn/p/?utm_source=x&id=2#top` và `https://a.vn/p?id=2` → cùng `canonical_url` (`https://a.vn/p?id=2`) và cùng `doc_id` (16 ký tự hex).
- [ ] **Step 2:** FAIL. **Step 3:** viết `links.py`. **Step 4:** `pytest --collect-in-virtualenv tests/crawl/web/test_web_links.py -q` PASS. **Step 5:** no commit — shared tree.

### Task 4: `queries.py` — nguồn query

**Files:**
- Create: `src/corpus/crawl/web/queries.py`
- Test: `tests/crawl/web/test_web_queries.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class Query:
    text: str
    group: str           # nhóm chấm: aspect key | khóa seed | "slug" | "gap"
    source: str          # "mining_map" | "seed" | "slug" | "gap"

def query_hash(text: str) -> str                         # sha1(NFC, casefold, gộp khoảng trắng)[:16]
def seed_queries(city_name: str) -> list[Query]          # đúng 69 phần tử, thứ tự dưới đây
def mining_queries(root: Path, city: str, city_name: str) -> list[Query] | None   # None: không có / sai khuôn
def slug_queries(web_root: Path, city: str, limit: int) -> list[Query]
def gap_queries(trip_gaps: Path, city_name: str, limit: int) -> list[Query]
def plan(city: str, city_name: str, cfg_web: dict, root: Path, hot: set[str] = frozenset()) -> list[Query]
```

`root` = `data_dir()`; `web_root` = `root/"web"/city`.

**Seed (69 query, thứ tự cố định).** Mẫu: query web `"{phrase} {city}"`; query TikTok `"site:tiktok.com {phrase} {city}"`; phrase có `{city}` thì thay tại chỗ và không thêm đuôi.
1. Hai query `discover` (group `discover`): `site:tiktok.com/discover {city}`, `site:tiktok.com/discover du lịch {city}`.
2. 15 phrase của `DISC` (`logs/model_knowledge_full.py`), mỗi phrase **hai** query (web rồi TikTok), group = khóa DISC:

| group | phrase |
|---|---|
| cafe_view | quán cà phê view đồi thông thung lũng |
| cloud | quán cà phê săn mây |
| early | quán cà phê mở cửa sớm 6h sáng |
| laptop | quán cà phê yên tĩnh làm việc laptop |
| music | quán nhạc sống buổi tối |
| veg | quán chay ngon |
| kids | điểm tham quan cho trẻ nhỏ |
| elderly | điểm tham quan cho người lớn tuổi ít dốc |
| pets | quán cà phê cho mang thú cưng |
| sunset | chỗ ngắm hoàng hôn đẹp |
| pick | vườn dâu tự hái |
| lau_ga | lẩu gà lá é |
| banh_can | bánh căn |
| xiu_mai | bánh mì xíu mại |
| parking | quán cà phê có chỗ đỗ ô tô |

3. 28 phrase của `GEN`, group = nhóm của câu (`transport`, `budget`, …), mỗi phrase một query web; thêm query TikTok cho 9 phrase đánh dấu `+tt`:

| group | phrase |
|---|---|
| transport | thuê xe máy giá một ngày giấy tờ |
| transport | đèo Prenn hay đèo Mimosa lái ô tô an toàn hơn |
| transport | gửi ô tô ở trung tâm giá bao nhiêu |
| transport | Grab xe công nghệ đi Langbiang giá |
| transport | từ Nha Trang lên {city} đi đường nào mất bao lâu |
| budget | 3 ngày 2 đêm cho 2 người chi phí tiết kiệm |
| stay | nên ở khu nào yên tĩnh gần trung tâm |
| stay | đặt phòng dịp 30/4 trước bao lâu |
| crowd | đông nhất vào những dịp nào trong năm |
| crowd | Langbiang ngày thường hay cuối tuần đông mấy giờ |
| safety | chặt chém lừa khách kinh nghiệm |
| safety | đường đèo mùa mưa sạt lở đoạn nào cần chú ý |
| health | người bệnh tim huyết áp cần lưu ý |
| health | bệnh viện lớn cấp cứu |
| custom | đi chùa ăn mặc thế nào cấm chụp ảnh |
| weather | tháng 12 ban đêm lạnh mấy độ mặc gì |
| weather | tháng 7 mưa nhiều không đi chơi buổi nào |
| season | hoa phượng tím nở tháng mấy `+tt` |
| season | mùa hồng chín tháng nào `+tt` |
| season | mimosa vàng tháng mấy `+tt` |
| food | ăn sáng ăn gì mấy giờ quán đông `+tt` |
| food | đặc sản mua làm quà ở đâu giá mứt atiso `+tt` |
| night | buổi tối ngoài chợ đêm đi đâu chơi `+tt` |
| kids | đi với bé 3 tuổi chuẩn bị gì nên tránh gì `+tt` |
| photo | chụp ảnh bình minh chỗ nào đẹp `+tt` |
| event | lễ hội sự kiện tháng 3 `+tt` |
| area | Trại Mát Cầu Đất cách trung tâm bao xa đi chung buổi |
| plan | một ngày Langbiang sáng chiều đồi chè Cầu Đất |

Tổng: 2 + 15·2 + 28 + 9 = 69.

**Nguồn và thứ tự `plan`:**
1. `mining_queries`: đọc `root/city/navigate/mining_map.json` (P3). Với mỗi `aspects[*]` dict: mỗi `queries[*]` là chuỗi 1–200 ký tự → `Query(text, group=aspect["key"], source="mining_map")`; chưa có tên thành phố (so khi bỏ dấu) thì thêm `" {city_name}"`; nếu `sources` của aspect (hạ chữ thường) chứa `"tiktok"` thì thêm query `site:tiktok.com {text}`. File không có → `None`; không phải JSON / không có `aspects` list → `None` và in một dòng cảnh báo; không có query hợp lệ nào → `None`. `None` → dùng `seed_queries`. (Hợp đồng với P3: P3 phải ghi `sources` có `"tiktok"` cho aspect cần video.)
2. `slug_queries`: đọc `web_root/discover_slugs.jsonl` (Task 6 ghi), mỗi slug một query `site:tiktok.com {text}` (group `slug`, `source="slug"`), bỏ slug đã có `search/<hash>.json`, lấy tối đa `cfg_web["slug_queries_per_run"]` (25) theo thứ tự tìm thấy.
3. `gap_queries`: đọc `root/"trip"/"gaps.jsonl"` (đường dẫn thật là **file** `data/trip/gaps.jsonl`, không phải thư mục như roadmap viết), dòng `kind == "no_data"`, sắp `count` giảm dần, tối đa `gap_queries_per_run` (20), query `"{phrase} {city_name}"` nếu `phrase` ≤ 120 ký tự (group `gap`, `source="gap"`).
4. Sau cùng loại trùng theo `query_hash` (giữ lần đầu); nhóm trong `hot` được ổn định-xếp lên đầu (D10).

- [ ] **Step 1: Tests** (`tmp_path` làm `root`):
  - `test_seed_queries_shape`: `len == 69`; `[0].text == "site:tiktok.com/discover Đà Lạt"`; tất cả chứa `"Đà Lạt"`; không trùng `query_hash`; mọi chuỗi ≤ 200 ký tự; 24 query bắt đầu `site:tiktok.com ` ngoài 2 discover → `sum(q.text.startswith("site:tiktok.com ") for q in qs) == 2 + 15 + 9`; `Query` của `transport` thứ năm bằng `"từ Nha Trang lên Đà Lạt đi đường nào mất bao lâu"`.
  - `test_query_hash_ignores_case_and_spaces`: `query_hash(" Bánh  Căn ")  == query_hash("bánh căn")`.
  - `test_mining_map_replaces_seeds`: file có 2 aspect (`key: cloud_sea`, `queries: ["săn mây", "mây Đà Lạt sáng sớm"]`, `sources: ["web", "tiktok"]`; `key: pine`, `queries: ["đồi thông"]`, `sources: ["web"]`) → `plan` = `["săn mây Đà Lạt", "site:tiktok.com săn mây Đà Lạt", "mây Đà Lạt sáng sớm", "site:tiktok.com mây Đà Lạt sáng sớm", "đồi thông Đà Lạt"]` (không có seed), group đúng khóa aspect.
  - `test_bad_mining_map_falls_back_to_seeds`: file `{"aspects": "x"}` → `plan` bắt đầu bằng 2 discover seed; `capsys` có cảnh báo.
  - `test_slug_queries_skip_done_and_cap`: 30 slug trong `discover_slugs.jsonl`, 5 đã có `search/<hash>.json` → 25 query, không có slug đã làm, đúng thứ tự.
  - `test_gap_queries_sorted_and_filtered`: 3 dòng (`count` 1, 5, 3; một dòng `kind: other`) → thứ tự 5, 3, 1 bỏ dòng `other`; cắt ở `limit`.
  - `test_hot_groups_go_first`: `hot={"cloud"}` → mọi query `group == "cloud"` đứng đầu, thứ tự tương đối còn lại giữ nguyên.
- [ ] **Step 2:** FAIL. **Step 3:** viết `queries.py` (bảng seed là hằng `SEEDS` trong file). **Step 4:** PASS. **Step 5:** no commit — shared tree.

### Task 5: `scoring.py` — `query_yield.jsonl`

**Files:**
- Create: `src/corpus/crawl/web/scoring.py`
- Test: `tests/crawl/web/test_web_yield.py`

**Interfaces:**

```python
def yield_row(q: Query, h: str, *, results: int, videos_total: int, videos_new: int, docs_new: int,
              slugs_new: int, blocked: list[str], cached: bool) -> dict
    # {"at", "query", "hash", "group", "source", "results", "videos_total", "videos_new", "docs_new",
    #  "slugs_new", "new": videos_new + docs_new + slugs_new, "blocked_engines", "cached"}
def group_scores(path: Path) -> dict[str, dict]          # group -> {"queries", "new", "mean_new"}
def hot_groups(path: Path) -> set[str]                   # new >= 2 × trung vị của "new" theo nhóm, và new > 0
```

- [ ] **Step 1: Tests:** `test_yield_row_new_is_sum`; `test_group_scores_sums_by_group` (3 dòng, 2 nhóm → đúng `queries`, `new`, `mean_new`); `test_hot_groups_two_times_median` (tổng theo nhóm `{a: 10, b: 4, c: 3, d: 2, e: 1}` → trung vị 3, ngưỡng 6 → `{"a"}`; `{a: 6, b: 3, c: 3}` → `{"a"}`; mọi nhóm `new == 0` → `set()`); `test_hot_groups_missing_file_is_empty`.
- [ ] **Step 2:** FAIL. **Step 3:** viết (đọc `jsonl` bỏ dòng hỏng). **Step 4:** PASS. **Step 5:** no commit — shared tree.

### Task 6: `discover.py` — phase `web search`

**Files:**
- Create: `src/corpus/crawl/web/discover.py`
- Modify: `src/corpus/crawl/web/__init__.py` (export `run_search`, `Query`, `seed_queries`, `slug_queries`)
- Test: `tests/crawl/web/test_web_discover.py`

**Interfaces:**

```python
def known_video_ids() -> set[str]       # chỉ đọc data/tiktok/: tên thư mục videos/*, và mọi "video_id": "<digits>" trong
                                        # place_search/*/*.json, poi_crawl/*.json, search/*/*.jsonl (regex trên text)
def run(city: str, limit: int | None = None, queries: list[Query] | None = None, web: Web | None = None) -> dict
```

Dữ liệu ghi (mọi file ở `data/web/<city>/`, ghi nguyên tử bằng `write_json` / `append_jsonl` của `crawl/common/files.py`):

| File | Bản ghi |
|---|---|
| `search/<query_hash>.json` | `{query, hash, group, source, searched_at, cached, results:[{url, title, snippet, engines, kind, reason}], unresponsive:[[engine, reason]]}` — **tồn tại = query đã xong** (không search lại) |
| `tiktok_urls.jsonl` | `{url, video_id, author, title, query, found_at}` — chỉ video **chưa** có trong `known_video_ids()` và chưa có trong file; `url` là URL chuẩn của `classify` |
| `discover_slugs.jsonl` | `{slug, text, query, url, found_at}` — `slug` = `text` bỏ dấu, `-` nối; chỉ `slug_relevant(text, city_name)`; khóa trùng = `slug` |
| `doc_urls.jsonl` | `{url, doc_id, domain, title, snippet, query, found_at}` — khóa trùng = `doc_id` |
| `query_yield.jsonl` | `scoring.yield_row` — mỗi query vừa chạy một dòng |
| `errors.jsonl` | `log_error(web_root, query_hash, "search", err)` |

Luồng: `load_config(city)` → `(name, cfg)`; `web = web or Web.from_config(cfg["web"], data_dir()/"web")`; `queries = queries or plan(city, name, cfg["web"], data_dir(), hot_groups(...))`; nạp tập khóa đã có của ba `.jsonl` + `known_video_ids()` một lần; với mỗi query chưa có `search/<hash>.json`: `web.search_page` → phân loại từng kết quả (`classify`) → ghi dòng mới → ghi `search/<hash>.json` **sau cùng** (chạy lại sau sập không mất, nhờ khóa trùng không nhân đôi) → ghi dòng yield → in một dòng tiến độ.

Dừng sạch:
- `BudgetExhausted` → dừng vòng lặp, `stop_reason = "budget"`, **không** ném ra ngoài; query chưa làm không có file nên lần sau (ngày sau) làm tiếp.
- `page.blocked` hoặc `WebError`: ghi `errors.jsonl` / dòng yield `blocked_engines`, **không** ghi `search/<hash>.json`; đủ `stop_after_blocked` (3) lần liên tiếp → `stop_reason = "engines_blocked"`. Một query thành công đặt lại bộ đếm.
- `limit` đếm query chạm mạng (không đếm query bỏ qua vì đã có file): đủ → `stop_reason = "limit"`.

Trả về (và `print`): `{"planned", "resumed", "network", "cached", "results", "videos_total", "videos_new", "videos_known", "slugs_new", "docs_new", "dropped": {reason: n}, "blocked_engines": {engine: n}, "stop_reason": None | "budget" | "engines_blocked" | "limit", "per_query": [yield rows]}`.

- [ ] **Step 1: Tests** (`Web` tiêm client `MockTransport`, `daily_queries`/`min_interval_s=0` để nhanh; `DATA_DIR` là `tmp_path`; thành phố `dalat` từ `config/cities.yaml` thật):
  - `test_search_splits_links_and_writes_files`: một query, payload 8 kết quả: video mới `A`, video `B` đã có thư mục `data/tiktok/videos/B/`, profile TikTok, discover `du-lịch-đà-lạt`, discover `coach-mint-bag`, `facebook.com/x`, hai bài báo `https://vnexpress.net/p?utm_source=x` và `https://www.vnexpress.net/p` → `tiktok_urls.jsonl` đúng 1 dòng (`video_id == "A"`, có `url`, `query`, `found_at`), `discover_slugs.jsonl` 1 dòng (`text == "du lịch đà lạt"`), `doc_urls.jsonl` 1 dòng (`domain == "vnexpress.net"`), `search/<hash>.json` có 8 kết quả với `kind`/`reason`, `query_yield.jsonl` 1 dòng `videos_total == 2`, `videos_new == 1`, `slugs_new == 1`, `docs_new == 1`, `new == 3`; stats `dropped == {"tiktok_other": 1, "social": 1, "slug_offtopic": 1}`, `videos_known == 1`.
  - `test_second_run_is_free_and_idempotent`: chạy hai lần → handler đúng số lần của lần đầu, mọi `.jsonl` không đổi số dòng, `stats["resumed"] == 1`.
  - `test_stops_cleanly_when_budget_exhausted`: `daily_queries=1`, 3 query → `stop_reason == "budget"`, 1 file `search/`, không ném lỗi, handler 1 lần; `stats["network"] == 1`.
  - `test_stops_after_three_blocked`: handler luôn trả `results: []` + `unresponsive_engines` → 5 query kế hoạch, dừng sau 3: `stop_reason == "engines_blocked"`, 0 file `search/`, `blocked_engines == {"brave": 3}`, `errors`/yield có dòng.
  - `test_blocked_then_ok_resets_counter`: block, block, ok, block, block → không dừng.
  - `test_limit_counts_only_network_queries`: 2 query đã có file + `limit=1` với 3 query mới → chạy đúng 1 query mới.
  - `test_known_video_ids_reads_every_tiktok_source`: dựng `videos/111/`, `place_search/dalat/x.json` có `"video_id": "222"`, `poi_crawl/y.json` có `"video_id": "333"`, `search/dalat/q.jsonl` có `"video_id": "444"` → `{"111","222","333","444"}`; thiếu thư mục `data/tiktok` → `set()`.
  - `test_run_with_explicit_queries_skips_planning`: `queries=[Query(...)]` → không đọc `mining_map.json` / `gaps.jsonl`.
- [ ] **Step 2:** FAIL. **Step 3:** viết `discover.py`. **Step 4:** `pytest --collect-in-virtualenv tests/crawl/web -q` PASS. **Step 5:** no commit — shared tree.

### Task 7: `documents.py` — phase `web documents`

**Files:**
- Create: `src/corpus/crawl/web/documents.py`
- Modify: `src/corpus/crawl/web/__init__.py` (export `run_documents`)
- Test: `tests/crawl/web/test_web_documents.py`

**Interfaces:**

```python
def split_sections(text: str) -> list[dict]       # [{"heading": str, "text": str}]
def run(city: str, limit: int | None = None, web: Web | None = None) -> dict
```

`Document` (`data/web/<city>/documents/<doc_id>.json`, schema như roadmap, thêm `chars`, `cut`, `query`):

```json
{"doc_id": "…16 hex…", "source_url": "https://…", "domain": "vnexpress.net", "title": "…",
 "retrieved_at": "2026-10-28T…+00:00", "lang": "vi", "kind": "web",
 "sections": [{"heading": "", "text": "…"}, {"heading": "Đi mùa nào", "text": "…"}],
 "chars": 61234, "cut": true, "query": "site:tiktok.com … Đà Lạt"}
```

- `split_sections`: dòng khớp `^#{1,6}\s+(.+?)\s*$` mở section mới với `heading` = phần chữ; chữ trước heading đầu tiên là section `heading == ""`; section không có chữ thân bị bỏ; thân = các dòng nối bằng `"\n"`, bỏ dòng trống đầu/cuối.
- `run`: đọc `doc_urls.jsonl` (thứ tự cũ → mới); bỏ URL đã có `documents/<doc_id>.json`; bỏ URL lỗi ≥ 2 lần (đếm dòng `errors.jsonl` có `id == doc_id` và `stage == "document"`); gọi `web.read_document(url, max_chars=cfg["doc_max_chars"])` tuần tự, nghỉ `page_pause_s` giữa hai trang; `chars < doc_min_chars` → coi là lỗi `TooShort` (ghi `log_error`, không ghi Document); `WebError` → `log_error(web_root, doc_id, "document", err)` rồi đi tiếp. `limit` = số trang thử tải mỗi run. Trả `{"todo", "ok", "failed", "too_short", "cut", "skipped_failed", "seconds"}`.
- Document là đầu vào của P4; phase này **không** gọi Extractor và không ghi observation.

- [ ] **Step 1: Tests** (patch `getaddrinfo` → IP công cộng; `page_pause_s=0`):
  - `test_split_sections`: văn bản `"Mở đầu\n\n## Đi mùa nào\nTháng 12\n\n## Ăn gì\n- Bánh căn"` → `[{"heading":"","text":"Mở đầu"},{"heading":"Đi mùa nào","text":"Tháng 12"},{"heading":"Ăn gì","text":"- Bánh căn"}]`; heading không thân bị bỏ; văn bản không heading → 1 section `heading == ""`.
  - `test_document_schema`: một URL trong `doc_urls.jsonl`, trang HTML có `<h2>` → file `documents/<doc_id>.json` có đủ khóa trên, `doc_id == links.doc_id(url)`, `kind == "web"`, `lang == "vi"`, `retrieved_at` ISO UTC, headings đúng.
  - `test_document_cut_at_40000`: trang `text/plain` 60.000 ký tự → `sum(len(s["text"]) for s in sections) <= 40_000`, `cut is True`, `chars == 60_000`.
  - `test_existing_document_not_fetched_again`: chạy hai lần → handler 1 lần.
  - `test_failed_page_logged_and_given_up_after_two`: handler trả 500 → run 1 và run 2 mỗi lần 1 request và 1 dòng `errors.jsonl` (`stage == "document"`); run 3 không request, `skipped_failed == 1`.
  - `test_too_short_page_is_not_a_document`: trang 100 ký tự → không có file Document, có dòng lỗi `TooShort`.
  - `test_limit`: 3 URL, `limit=2` → 2 request.
- [ ] **Step 2:** FAIL. **Step 3:** viết `documents.py`. **Step 4:** PASS. **Step 5:** no commit — shared tree.

### Task 8: CLI `python -m corpus web <search|documents|all>`

**Files:**
- Modify: `src/corpus/__main__.py` (docstring đầu file, import, `PHASES["web"]`, một nhánh trong `run`, help của `--limit`), `src/corpus/crawl/web/__init__.py` (hoàn tất `__all__`)
- Test: `tests/crawl/web/test_web_cli.py`

**Interfaces:**
- `PHASES["web"] = {"search": (web_discover.run, False), "documents": (web_documents.run, False)}`; `all` chạy `search` rồi `documents` (thứ tự khai báo, như nguồn khác).
- Trong `run()` thêm trước nhánh `else`: `elif source == "web": out = fn(city, limit=limit)`. `--headed` hiện ở mọi nguồn và bị bỏ qua với `web` (không thêm cờ riêng).
- Help `--limit`: thêm "web search: only N queries per run; web documents: only N pages per run".
- `__all__` của `corpus.crawl.web`: `Web`, `WebHit`, `WebPage`, `WebError`, `BudgetExhausted`, `SearchPage`, `SearchResult`, `WebDocument`, `validate_public_url`, `Query`, `seed_queries`, `slug_queries`, `run_search`, `run_documents`.

- [ ] **Step 1: Tests:** `test_web_phases_registered` (`set(PHASES["web"]) == {"search", "documents"}`; cả hai `needs browser is False`); `test_web_run_passes_limit` (monkeypatch hai hàm trong `PHASES["web"]` bằng recorder; `run("web", "all", "dalat", False, limit=5)` → gọi `search` rồi `documents`, mỗi lần `(city="dalat", limit=5)`); `test_public_api_names` (`importlib` mọi tên của `__all__` tồn tại).
- [ ] **Step 2:** FAIL. **Step 3:** sửa `__main__.py`, `__init__.py`. **Step 4:** `.venv/bin/python -m pytest --collect-in-virtualenv tests/crawl/web tests/trip/test_web.py tests/trip/test_agent_web.py tests/agents -q` PASS; `PYTHONPATH=src .venv/bin/python -m corpus web --help` in được `{search,documents,all}`. **Step 5:** no commit — shared tree.

### Task 9: Đo — `logs/web_probe_50.py`

**Files:**
- Create: `logs/web_probe_50.py` (chỉ dùng public API `corpus.crawl.web` và `corpus.data_root`)
- Output: `logs/web_probe_50_<YYYY-MM-DD>.json`

Quy trình: (1) từ chối chạy nếu `Web.from_config(...).budget_left() < 50`. (2) **Giai đoạn A, 25 query**: `seeds[:2] + seeds[2:][::3][:23]` (hai query discover + 23 query cách đều trong 67 seed, xen web / TikTok) qua `run_search(city, queries=…)`. (3) **Giai đoạn B, 25 query**: `slug_queries(web_root, city, limit=25)` (slug mà giai đoạn A vừa tìm; ít hơn 25 thì chạy bấy nhiêu và ghi `slug_queries_available`) qua `run_search`. (4) `run_documents(city, limit=40)`. (5) ghi JSON:

```json
{"date": "…", "stage_a": {"queries": 25, "videos_total": 0, "videos_new": 0, "docs_new": 0, "slugs_new": 0},
 "stage_b": {"queries": 25, "slug_queries_available": 25, "videos_total": 0, "videos_new": 0, "docs_new": 0},
 "totals": {"queries": 50, "network": 0, "cached": 0, "results": 0,
            "videos_total": 0, "videos_new": 0, "video_new_ratio": 0.0,
            "doc_urls": 0, "doc_url_ratio": 0.0, "docs_read": 0, "docs_ok": 0, "doc_ok_ratio": 0.0,
            "slugs_new": 0, "blocked_engines": {"brave": 0}, "stop_reason": null, "seconds": 0.0},
 "per_group": {"cloud": {"queries": 2, "new": 9}}, "hot_groups": []}
```

`video_new_ratio = videos_new / videos_total`; `doc_url_ratio = doc_urls / results`; `doc_ok_ratio = docs_ok / docs_read`. Đây là cột "Xong khi" của P2 trong roadmap (video mới, tỉ lệ có trang báo/blog, engine bị chặn, cache hit).

- [ ] **Step 1:** viết script (không có test riêng: nó chỉ ghép các hàm đã có test; kiểm bằng chạy thật).
- [ ] **Step 2:** chạy thử nhỏ: `PYTHONPATH=src .venv/bin/python logs/web_probe_50.py --dry` (cờ `--dry` chỉ in kế hoạch 50 query và `budget_left`, không gọi mạng) — kiểm đúng 25 + 25 và các query có `Đà Lạt`.
- [ ] **Step 3:** chạy thật một lần: `PYTHONPATH=src .venv/bin/python logs/web_probe_50.py` (SearXNG `127.0.0.1:8888` phải sống: `curl -s 'http://127.0.0.1:8888/search?q=test&format=json' | head -c 80`; mất ~50 × 2 s + 40 trang ≈ 3–4 phút). Dùng ≈ 50/300 query của ngày. Không chạy lại trong cùng ngày nếu không cần.
- [ ] **Step 4:** dán bảng `totals` + `per_group` vào báo cáo cho chủ dự án; kèm 3 slug và 3 trang báo lấy ngẫu nhiên làm ví dụ (kiểm tay: slug đúng chủ đề Đà Lạt, trang đọc ra heading). Số lỗi thật (ví dụ engine `duckduckgo` trả `CAPTCHA`, đã thấy ở thử nghiệm) ghi nguyên, không làm tròn.
- [ ] **Step 5:** no commit — shared tree.

### Task 10: Tài liệu

**Files:**
- Modify: `docs/CORPUS.md` (tiếng Việt, mô tả đúng code vừa viết, không "trước đây / sau này", `RULE.md` §0.1), `docs/TRIP_UNDERSTANDING.md` (hai dòng 157 và 449 trỏ `infrastructure/web.py`), `docker/searxng/settings.yml` (dòng đầu comment), `README.md` chỉ khi mục lục cần (không cần: không thêm file tài liệu)
- Verify: `grep -n "web" docs/CORPUS.md` khớp code

Sửa trong `docs/CORPUS.md`:
- **§Nguồn và mỗi nguồn chứng minh điều gì** (bảng, sau hàng "Website / trang chính thức"): hàng `Web (SearXNG)` | Dùng cho: URL video TikTok không qua ô search (không captcha), câu tìm thật (slug `/discover/`), trang báo / blog làm `Document` (đầu vào của tri thức bản địa) | Không bao giờ dùng cho: chi tiết một nơi (giờ, giá, đặc điểm), tạo hay xác nhận địa điểm, hiển thị nguyên văn trang cho người dùng.
- **§CLI** (khối code): thêm `python -m corpus web <search|documents|all> [--city dalat] [--limit N]   # SearXNG: URL video / slug / Document (data/web/)`; bảng phase thêm hàng `web` | `search` → `documents`; câu về `--limit` thêm `web search` (N query) và `web documents` (N trang).
- **§Data model** (bảng): hàng `data/web/` | `corpus.crawl.web` | `cache/`, `engines.jsonl`, `budget.json`, `<city>/search/`, `tiktok_urls.jsonl`, `discover_slugs.jsonl`, `doc_urls.jsonl`, `documents/`, `query_yield.jsonl`.
- **§1 Discover → Dữ liệu thô** (cây `data/`, sau khối `tiktok/`): khối `web/` mô tả từng file với schema ở Task 6–7, ngân sách (300 query / ngày UTC, nghỉ 2 s, cache hit miễn phí, hết ngân sách → phase dừng, ngày sau chạy tiếp), nhật ký engine (`unresponsive_engines`), quy tắc phân loại link ngắn gọn (video / discover / doc / bỏ mạng xã hội và OTA trừ `/blog`), dedupe video với `data/tiktok/` (hiện chỉ ghi `tiktok_urls.jsonl`; `tiktok` đọc file này, không import), `Document` chia theo heading, cắt 40.000 ký tự, chấm query `query_yield.jsonl` + `hot_groups`.
- `docs/TRIP_UNDERSTANDING.md` §18 / cây thư mục: `infrastructure/web.py` → "lớp mỏng trên `corpus.crawl.web`; cache `data/web_cache`".
- `docker/searxng/settings.yml`: `src/trip/infrastructure/web.py` → `src/corpus/crawl/web/client.py (Trip and corpus)`.
- `docs/log/DEV_LOG.md`: **không** sửa trong plan này (chủ dự án quyết lúc đóng phase).

- [ ] **Step 1:** sửa các mục trên bằng `Edit` đúng đoạn (tránh ghi đè sửa dở của phiên khác trong `docs/TRIP_UNDERSTANDING.md`).
- [ ] **Step 2:** `.venv/bin/python -m pytest --collect-in-virtualenv tests/crawl tests/trip/test_web.py tests/trip/test_agent_web.py tests/trip/test_agent_tools.py tests/agents -q` PASS lần cuối; `git diff --stat` chỉ gồm file của plan (không file lạ).
- [ ] **Step 3:** no commit — shared tree.

## Ngoài plan này (việc sau, theo roadmap)

- P3 ghi `mining_map.json` (nguồn query số 1; `sources` có `"tiktok"` để sinh query video), P4 đọc `documents/*.json` thành `LocalClaim`, P7 `tiktok web_videos` đọc `tiktok_urls.jsonl`.
- P8: nhân đôi ngân sách cho nhóm `hot_groups`, dừng khi vòng thêm < 5 % mới (P2 chỉ cung cấp `hot_groups`, D10).
- SerpApi dự phòng khi mọi engine bị chặn (spec §A.2) — P2 chỉ dừng sạch và ghi engine; không phân trang (`pageno=2` có kết quả mới, chưa dùng).
- Làm tươi: query đã có `search/<hash>.json` không tự search lại (xóa file để làm mới).
