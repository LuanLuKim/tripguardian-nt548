# Corpus phục vụ sol và Place Decision — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corpus có một lớp đọc chung, nhanh và bám bằng chứng cho mọi khâu sau: bản ghi gọn một nơi (`card`), tìm nơi theo tiêu chí (`find`), từ vựng cho prompt (`vocabulary`), và bộ đo tốc độ + độ đúng (`python -m bench retrieval`).

**Architecture:** Thêm vào public API `corpus.retrieval` (đã là cửa đọc của Trip, Decision, Planning). `card` là hàm thuần trên serving record; `find` lọc bằng cột numpy của `snapshot.Region` (như Place Decision đang làm), cache giờ/menu theo region. Không ghi gì mới vào corpus, không đổi snapshot schema. Một sửa ở serving: vé mâu thuẫn → `UNCERTAIN`.

**Tech Stack:** Python 3, numpy, polars, orjson, pytest (`--collect-in-virtualenv`).

**Spec:** `docs/superpowers/specs/2026-10-26-production-and-course-upgrade-design.md` §A.8 (kho phục vụ sol), §3 việc 2 (vé/giá), §A.9 (đo). Chỉ dẫn của chủ dự án 2026-10-28: "corpus phải dễ RAG, dễ truy xuất cho sol và dùng cho Place Decision khi cần; Place Decision dùng được và nhanh, sol cũng tương tự".

## Global Constraints

- Code, comment, identifier tiếng Anh; tài liệu tiếng Việt (`RULE.md` §0).
- Online chỉ đọc; module chỉ qua public API `corpus.retrieval` (`__init__.py`), không deep import.
- Không bịa: mọi giá trị trong `card` / `find` lấy từ field của serving record; không có thì bỏ khóa, không điền mặc định.
- `unknown ≠ false`; lọc cứng fail-closed: chỉ `VERIFIED` / `OUTDATED` qua; `UNCERTAIN` vào `maybe`; không có bằng chứng → đếm `unknown`, không vào kết quả.
- Chỗ ở (`category_group == "stay"`) chỉ trả khi `groups` có `"stay"` (`docs/CORPUS.md` §Phạm vi).
- Ngân sách tốc độ (cùng cỡ với `create ≤ 30 ms` của Decision): `find` không `text`, region đã warm, p95 ≤ 30 ms; `card` p95 ≤ 1 ms; card p95 ≤ 2.000 ký tự.
- Chạy test: `.venv/bin/python -m pytest --collect-in-virtualenv <path> -q` (NFS treo nếu thiếu cờ).
- Working tree dùng chung: chỉ `git add` file của task, không `-A`; không commit nếu chủ dự án chưa cho.

## Review Focus

1. Nơi có feature đúng giá trị nhưng `UNCERTAIN` → không được nằm trong `hits`, phải ở `maybe` (test ở Task 3).
2. `must` với feature không tồn tại / giá trị ngoài ontology (sol gửi sai) → `ValueError` tại biên, không trả rỗng âm thầm (Task 3, `test_parse_rejects_unknown`).
3. Giờ qua nửa đêm (`["18:00","02:00"]`) và ngày không có giờ → `open_at` đúng / loại (Task 3, `test_open_at_overnight_and_missing`).
4. `card` của nơi thiếu hầu hết khối (details trống, không giá, không giờ) → không có khóa rỗng / `None` (Task 2, `test_card_omits_empty`).
5. Tên món có dấu / hoa thường khác nhau ("Bánh Căn" vs "banh can") → vẫn khớp (Task 3, `test_dish_folds_accents`).

---

### Task 1: Vé mâu thuẫn → `UNCERTAIN`

Bằng chứng (2026-10-28, `data/serving/places.json`): 15 nơi có feature `entry_fee = free` `VERIFIED` trong khi `operation.entry_fee.typical_vnd > 0`; Đồi Chè Cầu Đất `free` 22 phiếu / `paid` 12, vé ước 100.000 từ review. Nguyên tắc 4 `docs/CORPUS.md`: bất đồng → `uncertain`, giữ xung đột.

**Files:**
- Modify: `src/corpus/serving/record.py` (`build`, ngay sau khi tính `features`, trước `groups`)
- Test: `tests/serving/test_serving.py`

**Interfaces:**
- Produces: feature `entry_fee` có `status = "UNCERTAIN"`, `reason = "conflicts_entry_fee_estimate"` khi `value == "free"` và `est["entry_fee"]["typical_vnd"] > 0`. `operation.entry_fee` giữ nguyên.

- [ ] **Step 1: Test** `test_free_entry_conflicting_with_fee_estimate_is_uncertain`: intel có `features.entry_fee` free (đủ để VERIFIED như fixture sẵn có trong file) và `estimates.entry_fee = {"min_vnd": 60000, "typical_vnd": 100000, "max_vnd": 120000, "n": 3, "source": "reviews"}` → `rec["service"]["entry_fee"]["status"] == "UNCERTAIN"`, `reason == "conflicts_entry_fee_estimate"`, `rec["operation"]["entry_fee"]["typical_vnd"] == 100000`; và `details.cost` không coi là miễn phí (`place_block` nhận feature đã đổi). Thêm `test_free_entry_without_fee_estimate_stays_verified`.
- [ ] **Step 2:** chạy, thấy FAIL.
- [ ] **Step 3:** sửa `build` (thay `features["entry_fee"]` bằng bản copy đổi status/reason).
- [ ] **Step 4:** `pytest --collect-in-virtualenv tests/serving tests/snapshot tests/decision -q` PASS.
- [ ] **Step 5:** commit `fix(serving): free entry contradicted by a fee estimate is UNCERTAIN`.

### Task 2: `card` — bản ghi gọn

**Files:**
- Create: `src/corpus/retrieval/card.py`
- Modify: `src/corpus/retrieval/engine.py` (method `card`), `src/corpus/retrieval/__init__.py` (export `card`)
- Test: `tests/retrieval/test_card.py`

**Interfaces:**
- Produces: `card(record: dict) -> dict` (thuần); `RetrievalEngine.card(place_id: str) -> dict | None`.

Khóa (bỏ khóa khi không có giá trị):

| Khóa | Lấy từ |
|---|---|
| `id`, `n`, `cat`, `g`, `addr` | `id`, `identity.name/category/category_group/address` |
| `h` | `operation.hours.value`: `{"06:30-21:30": "mon,tue,wed,thu,sat,sun", "06:00-21:30": "fri"}` (khoảng nối bằng `,` khi nhiều khoảng một ngày); `h_status` khi status ≠ VERIFIED |
| `fee` | `operation.entry_fee`: `{min, typ, max, src, kind}`; thêm `"conflict": true` khi feature `entry_fee` có reason `conflicts_entry_fee_estimate` |
| `price` | `operation.price_per_person.value` `[min_vnd, max_vnd]`; `night` = `price_per_night.value` |
| `visit` | `operation.visit_minutes` `[short, typical, long]` |
| `f` | list `"fid=value"` của feature status VERIFIED/OUTDATED, mọi nhóm (`experience`, `environment`, `service`, `effort`, `suitability`) |
| `f?` | như trên cho UNCERTAIN |
| `known` | `details.known_for.headline` + `more` (text) |
| `order`, `avoid`, `activity`, `photo_spot`, `access`, `booking`, `bring`, `situation` | `details.<k>` → tối đa 3 `text` mỗi khóa |
| `best`, `avoid_t` | `details.timing.best_time.items` / `avoid_time.items` text |
| `months`, `months_avoid` | `details.timing.best_months` / `avoid_months` |
| `dishes` | `menu.dishes[:8].name` |
| `peak` | `operation.crowd_by_time.peak` |
| `trend` | `provenance.rating_trend.direction` |
| `voices` | `provenance.voices` |
| `status` | chỉ khi ≠ `VERIFIED` |

- [ ] **Step 1: Test** `test_card_keys_from_record` (record mẫu cafe ở trên: `h == {"06:30-21:30": "mon,tue,wed,thu,sat,sun", "06:00-21:30": "fri"}`, `"nature=present" in f`, `"scenic_view=present" in f?`, `dishes[0] == "Cà Phê Pha Máy"`); `test_card_omits_empty` (record chỉ có identity → khóa ⊆ `{id,n,cat,g,addr}`, không giá trị `None`/rỗng); `test_card_never_serves_needs_review` (feature `NEEDS_REVIEW`/`DISABLED` không có trong `f`, `f?`); `test_card_marks_fee_conflict`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** viết `card`; `engine.card` = `card(self._region.record(pid))` hoặc `None`.
- [ ] **Step 4:** `pytest --collect-in-virtualenv tests/retrieval -q` PASS.
- [ ] **Step 5:** commit `feat(retrieval): compact place card for agents`.

### Task 3: `find` theo tiêu chí + `vocabulary`

**Files:**
- Create: `src/corpus/retrieval/find.py`
- Modify: `src/corpus/retrieval/engine.py` (methods `find`, `vocabulary`, `warm`), `src/corpus/retrieval/__init__.py`; `snapshot/read.py` không đổi (`Region` không biết `find`)
- Test: `tests/retrieval/test_find.py`

**Interfaces:**
- Consumes: `card(record)` (Task 2); `snapshot.Region` (`ids`, `feature(fid)`, `column(name)`, `record(pid)`, `stay`).
- Produces:

```python
@dataclass(frozen=True)
class Criteria:
    groups: tuple[str, ...] = ()                 # category_group; () = mọi nhóm trừ stay
    must: tuple[tuple[str, str], ...] = ()       # (fid, value) lọc cứng; fid có thể là "fit.<who>"
    prefer: tuple[tuple[str, str], ...] = ()     # (fid, value) cộng điểm
    open_at: tuple[str, str] | None = None       # ("sat", "06:00"): mở tại thời điểm đó
    opens_by: str | None = None                  # "06:00": có ít nhất một ngày mở lúc ≤ giờ này
    dish: str | None = None                      # khớp tên món trong menu (bỏ dấu, hoa thường)
    month: int | None = None                     # 1..12: cộng điểm nếu trong best_months, trừ nếu avoid_months
    near: tuple[float, float, float] | None = None  # (lat, lng, km)
    text: str | None = None                      # RetrievalEngine.semantic trên tập đã lọc

    @classmethod
    def parse(cls, raw: dict, ont: Ontology) -> "Criteria": ...  # ValueError khi fid/value/group/day/giờ/month sai

@dataclass(frozen=True)
class FindHit:
    place_id: str
    score: float
    matched: tuple[str, ...]     # "fid=value" của prefer khớp, "dish:<tên>", "month", "text"
    card: dict

@dataclass(frozen=True)
class FindResult:
    hits: tuple[FindHit, ...]    # qua mọi must (firm)
    maybe: tuple[FindHit, ...]   # qua lọc khác, ≥1 must chỉ UNCERTAIN; tối đa limit
    unknown: int                 # số nơi bị loại chỉ vì ≥1 must không có bằng chứng
    release_id: str | None

def find(region: Region, criteria: Criteria, *, limit: int = 8, semantic=None) -> FindResult
def warm(region: Region) -> None             # dựng cache giờ + món của region
def vocabulary(ont: Ontology, region: Region) -> dict
# RetrievalEngine.find(criteria: Criteria | dict, limit: int = 8) -> FindResult   (dict → Criteria.parse)
# RetrievalEngine.vocabulary() -> dict
```

Quy tắc:
- Tập ứng viên: `groups` (mặc định mọi `category_group` trừ `stay`), rồi `near` (haversine trên cột `lat`/`lng`), `open_at` / `opens_by` (giờ từ `record.operation.hours.value`; khoảng `[a, b]` với `b < a` là qua nửa đêm; ngày không có khóa = đóng; hours status không VERIFIED/OUTDATED → nơi đó không qua lọc giờ), `dish` (fold bằng `ontology.fold_text`, chuỗi con của tên món đã fold).
- Cache theo region (dict giữ trong `find.py`, khóa `id(region)`): giờ đã parse và tên món đã fold, dựng lần đầu; `RetrievalEngine.warm()` gọi `find.warm(self._region)`.
- `must`: `FeatureColumn.firm & eq(value)` → qua; `uncertain & eq(value)` → `maybe`; `status is None` → đếm `unknown`; còn lại loại.
- Điểm: `Σ conf` của `prefer` khớp (firm) `+ 0.3` (month trong `best_months`) `− 0.3` (trong `avoid_months`) `+ semantic score` `+ 0.05·log1p(voices)`; hòa → voices giảm dần, rồi id.
- `text`: chỉ khi `semantic` được truyền (engine truyền `self.semantic`), gọi trên tập đã lọc (`within`), không gọi khi tập rỗng.
- `vocabulary`: `{"groups": {group: số nơi}, "features": {fid: {"values": [...], "label": claims[value] hoặc hint cắt ở dấu "." / ":" đầu tiên, ≤ 80 ký tự}}, "companions": {id: vi}}`.

- [ ] **Step 1: Tests** trên `Region.from_records(...)` với 5 record dựng tay:
  - `test_must_firm_only` (VERIFIED → `hits`; UNCERTAIN → `maybe`; không có → `unknown == 1`; giá trị khác → không ở đâu).
  - `test_stay_only_when_asked`.
  - `test_open_at_overnight_and_missing` (`["18:00","02:00"]` mở lúc `("sat","01:00")` khi khoảng thuộc `fri`; ngày thiếu → loại; hours UNCERTAIN → loại).
  - `test_opens_by`.
  - `test_dish_folds_accents` (`"banh can"` khớp `"Bánh Căn Nhà Chung"`).
  - `test_near_km`.
  - `test_prefer_and_month_order`.
  - `test_parse_rejects_unknown` (fid lạ, value ngoài ontology, group lạ, `month=13`, `"25:00"` → `ValueError`).
  - `test_text_never_embeds_on_empty_scope` (semantic mock ném lỗi nếu bị gọi).
  - `test_vocabulary_shapes`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** viết `find.py`, method engine, export (`Criteria`, `FindHit`, `FindResult`, `card` vào `__all__`).
- [ ] **Step 4:** `pytest --collect-in-virtualenv tests/retrieval tests/decision tests/trip/test_catalog_snapshot.py -q` PASS.
- [ ] **Step 5:** commit `feat(retrieval): criteria search and vocabulary for agents`.

### Task 4: `python -m bench retrieval` — đo trên release thật

**Files:**
- Create: `src/bench/retrieval.py`
- Modify: `src/bench/__main__.py` (subcommand `retrieval`, `--release`, `--out`)
- Test: `tests/bench/test_retrieval_bench.py`

**Interfaces:**
- Consumes: `RetrievalEngine.open(release_id)`, `.card`, `.find`, `.vocabulary`, `corpus.serving.feature`.
- Produces: `CASES: list[tuple[str, dict]]` (tên ca, criteria dict); `run(engine, repeats: int = 30) -> dict`; `main(release: str | None, out: Path | None) -> int` ghi `data/bench/retrieval/<YYYYmmdd-HHMMSS>.json`.

`CASES` = 15 yêu cầu gợi ý của §2.1 (`logs/model_knowledge_full.py` `DISC`), viết lại thành criteria:

| Ca | criteria |
|---|---|
| cafe_view | `groups=[cafe], must=[[scenic_view,present]]` |
| cloud | `must=[[cloud_hunting,present]]` |
| early | `groups=[cafe], opens_by="06:00"` |
| laptop | `groups=[cafe], must=[[laptop_friendly,present]]` |
| music | `must=[[live_music,present]]` |
| veg | `must=[[vegetarian_options,yes]]` |
| kids | `groups=[attraction,nature,garden_farm,amusement], must=[[kids,suitable]]` |
| elderly | `groups=[attraction,nature,garden_farm], must=[[steep_or_stairs,absent]]` |
| pets | `groups=[cafe], must=[[pets,allowed]]` |
| sunset | `must=[[sunset_view,present]]` |
| pick | `must=[[pick_your_own,present]]` |
| lau_ga | `dish="lá é"` |
| banh_can | `dish="bánh căn"` |
| xiu_mai | `dish="xíu mại"` |
| parking | `groups=[cafe], must=[[parking,easy]]` |

Thêm 3 ca kết hợp: `cafe_view` + `open_at=["sat","07:00"]`; `kids` + `near=[11.9404,108.4583,5]`; `veg` + `prefer=[[noise,quiet]]`.

Báo cáo:
- `startup`: thời gian `open` + `warm` (s).
- mỗi ca: `hits`, `maybe`, `unknown`, `find` warm `{p50, p95, max}` ms (`repeats` lần), `correct` = mọi hit qua lại kiểm độc lập trên record (`serving.feature` firm + đúng value; giờ/món kiểm lại từ record), `recall` = số hit ÷ số nơi brute-force qua cùng điều kiện trên `region.records()` (limit = ∞ khi so).
- `card`: mọi nơi, `{p50, p95}` ms và ký tự (`len(orjson.dumps(card))`), ước token = ký tự / 3.
- `vocabulary`: ký tự.
- `ok`: `find p95 ≤ 30`, `card p95 ≤ 1 ms`, `card chars p95 ≤ 2000`, mọi ca `correct`, `recall == 1.0`.

- [ ] **Step 1: Test** `test_bench_on_fixture_region` (engine dựng từ `Region.from_records` qua `tests/retrieval/test_retrieval_boundary._make_engine` hoặc `from_snapshot` mock như `test_contract.py`; `run(engine, repeats=2)` có đủ khóa ca, `correct` True, `ok` là bool).
- [ ] **Step 2:** FAIL. **Step 3:** viết. **Step 4:** test PASS.
- [ ] **Step 5:** chạy thật: `PYTHONPATH=src .venv/bin/python -m bench retrieval` trên release hiện hành (`data/releases/current`), dán bảng kết quả vào báo cáo cho chủ dự án.
- [ ] **Step 6:** commit `feat(bench): retrieval latency and correctness`.

### Task 5: Release mới có sửa vé + tài liệu

- [ ] **Step 1:** `corpus.releases.rebuild("dalat", publish=False)` (chỉ dữ liệu đã lưu); chạy lại bench Task 4 với `--release <id mới>`; ghi số nơi `entry_fee` chuyển `UNCERTAIN` (kỳ vọng 15). **Không publish** — publish và restart prod là quyết định của chủ dự án.
- [ ] **Step 2:** `docs/CORPUS.md` đoạn "Public `corpus.retrieval`": thêm `card`, `find(Criteria)`, `vocabulary`, quy tắc must/maybe/unknown, ngân sách tốc độ, `python -m bench retrieval`; §CLI không đổi (bench là CLI riêng). `docs/log/DEV_LOG.md` theo khuôn của nó. Spec A.8: dòng `get_place`/`search_places` trỏ sang `corpus.retrieval.card` / `find`.
- [ ] **Step 3:** commit `docs(corpus): agent retrieval API`.

## Ngoài plan này (việc sau, theo spec)

- Nối `card` / `find` / `vocabulary` vào tool của Trip (B.2–B.3) và chatbot Lựa chọn (C.1); đảo `guard.bad_say` (A.8).
- Trang `aspect` (cần bản đồ khai thác A.1), `LocalClaim` (A.3), khám phá qua web (A.2), media (A.6), giá phòng (A.7).
- Lấp khối `details` (plan bổ sung chi tiết 13 mục, chưa làm): hiện `known_for`/`order`/`avoid` = 0 nơi.
