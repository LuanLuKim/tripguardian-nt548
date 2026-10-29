# Chatbot Trip Understanding + Place Decision — plan thực hiện

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Plan làm việc (`RULE.md` §0.1), tạm thời. Xong thì gộp phần còn giá trị vào `docs/TRIP_UNDERSTANDING.md`, `docs/PLACE_DECISION.md` rồi xoá file này.

**Goal:** Trợ lý Trip thành chatbot kiểu ChatGPT chuyên Đà Lạt (trả lời, gợi ý nơi thật từ kho, hiện thẻ nơi), có Clef chuẩn bị tool; Lựa chọn có op xếp hạng lại / lọc / "kiếm kiểu này"; `decision evaluate` đo được các chỉ số còn thiếu.

**Architecture:** Trip đọc kho qua `corpus.retrieval` (`find`, `card`, `similar` — đã có từ plan P1 corpus) bọc trong `trip/infrastructure/knowledge.py`; thời tiết và khoảng cách là callable harness tiêm vào (Trip không import `live`). Mỗi lượt: code dò ứng viên nơi + một request Clef chọn nhóm tool → chạy song song tool chỉ đọc (≤ 1,2 s) → kết quả vào CURRENT CONTEXT và cache của `TurnTools` → sol một lần gọi. Guard đảo luật: id và số **có trong kết quả tool của phiên** được nói. Toàn bộ phần mới nằm sau cờ `assistant.enabled` (mặc định `false`) cho tới khi bench đạt. Decision giữ kiểu một call trả `TurnPlan`, thêm op mới; code xếp hạng.

**Tech Stack:** Python 3.12, pydantic v2, LangChain/LangGraph (vòng Agent sẵn có), Clef qua `trip/infrastructure/clef.py`, React/TS (`web/src/user`).

**Spec:** `docs/superpowers/specs/2026-10-26-production-and-course-upgrade-design.md` §B.1–B.5, §C.1–C.3 (bằng chứng §2.1, §2.4). Đọc thêm: `docs/TRIP_UNDERSTANDING.md`, `docs/PLACE_DECISION.md`, `logs/clef_prefetch_bench.py` (bản mẫu đã đo của B.3: `candidates`, `clef2`, `prepare2`, `compact`).

## Global Constraints

- Tài liệu tiếng Việt; code, comment, identifier, tên file tiếng Anh (`RULE.md` §0). Đọc `RULE.md` trước khi viết.
- Module chỉ qua public API (`__init__.py`); Trip **không** import `live`, `decision`, `planning`. Decision không import Trip ngoài `trip` public (đã có `from trip import contains, squash`).
- Online chỉ đọc Place Intelligence; chỉ ghi Trip State, phiên Decision, `data/trip/gaps.jsonl`.
- Không bịa nơi: tên nơi trong lời Agent chỉ được nếu id có trong kết quả tool của phiên (hoặc user tự nêu, như hiện nay). Không có → câu đó bị cắt (`prune_say`).
- Số từ field, không từ model: số trong lời Agent phải có trong lời user, Trip State, hoặc kết quả tool của phiên.
- Hard constraint fail-closed: mọi danh sách nơi Trip trả cho Agent đã qua `trip.domain.coverage.admissible` với `state.hard`. `unknown ≠ false`.
- Decision: không bao giờ loại hay trừ điểm vì một mong muốn; `filter` chỉ ẩn khỏi màn, có `unfilter`, có undo.
- Cổng lên lịch giữ nguyên (`deck.py` `at = "gate"`, `domain/required.py`, `TripNotReady` → 409).
- Clef: một request mỗi lượt, nhận nhóm khi P(có) ≥ `0.35`, ≤ 6 ứng viên nơi, prompt < 2k token. Chờ chuẩn bị tối đa `1.2` s.
- Dữ liệu cho sol: khóa ngắn của `corpus.retrieval.card` (không cắt feature); trả lời ≤ `60` từ.
- Working tree dùng chung: **không commit, không `git add`** trừ khi chủ dự án bảo (thay mọi bước "Commit" của skill bằng "ghi tiến độ vào ledger"). Ledger: `.superpowers/sdd/2026-10-28-trip-decision-chatbot/progress.md`.
- Test: `.venv/bin/python -m pytest --collect-in-virtualenv <path> -q` (thiếu cờ thì treo trên NFS). Baseline 2026-10-28: `tests/trip tests/decision` **1148 passed, 5 deselected** (197 s). File của session khác (corpus module A) có thể đang dở: test hỏng ngoài phạm vi thì kiểm trước khi kết luận là do mình.
- Khóa nhóm "Hợp nhất" trong view, tên `Catalog.by_id`, fixture `catalog` trong conftest: plan dùng tên đoán; tên thật khác thì theo code và ghi `Ruling:` vào ledger.
- Model gọi theo vai trò (`corpus.llm.AGENT`); không thêm model mới.

## Review Focus

1. **Tên nơi user tự gõ trùng tên một nơi khác trong kho** ("quán Mơ" vs "Tiệm Cà Phê Túi Mơ To"): `candidates` giữ dấu, nguyên cụm trước → test `test_candidates_keeps_accents_and_whole_name_first` (Task 3).
2. **Tool lỗi / chậm** (Open-Meteo không trả, OSRM tắt, Clef timeout): lượt vẫn chạy, dữ liệu thiếu thì sol nói "chưa có thông tin", không treo quá `1.2` s chờ → `test_prepare_times_out_into_cache` (Task 3), `test_weather_unavailable_is_an_error_result` (Task 2).
3. **Phiên cũ đã lưu** (snapshot thiếu field `Meta` mới, thẻ `kind: places` trong transcript cũ không có): `Snapshot` load được, `_upgrade` không cần sửa → `test_old_snapshot_loads_with_new_meta` (Task 1).
4. **Hard constraint + tìm nơi**: user "đi với bé 3 tuổi" (hard `kids=unsuitable` `!=`) rồi hỏi "gợi ý quán view đồi": không nơi `kids=unsuitable` hoặc chưa rõ (khi policy exclude) lọt vào → `test_find_places_applies_hard_fail_closed` (Task 2).
5. **Cờ tắt**: `assistant.enabled: false` thì tool list, prompt, guard y như hôm nay (test cũ phải pass không sửa) → `test_flag_off_keeps_tool_list` (Task 2), chạy toàn bộ `tests/trip` ở Task 4.

---

## Bản đồ file

| File | Việc |
|---|---|
| `config/trip.yaml`, `src/trip/infrastructure/settings.py` | block `assistant` |
| `config/cities.yaml` | `dalat.center` |
| `src/trip/infrastructure/knowledge.py` (mới) | `Knowledge`: find/card/similar có hard filter; weather/distance qua `LiveTools` |
| `src/trip/infrastructure/clef.py` | `yes_prob` |
| `src/trip/agent/prefetch.py` (mới) | `candidates`, `route`, `prepare` (B.3) |
| `src/trip/agent/tool_schemas.py`, `src/trip/agent/tools.py` | tool đọc kho + hiển thị, cache, `told_ids` |
| `src/trip/agent/prompt.py` | prompt trợ lý (theo cờ), `data` trong CURRENT CONTEXT |
| `src/trip/domain/guard.py` | `bad_say(..., allowed_ids, told)` đảo luật |
| `src/trip/domain/state.py` | `Meta.shown_ids`, `Meta.told_numbers`, `Meta.intent`, `Meta.invited` |
| `src/trip/api/engine.py`, `src/trip/api/tools.py` | nối prefetch, thẻ `places`, act `like`, tiêm `live` |
| `src/harness/__main__.py` | dựng `LiveTools` từ `live` |
| `src/trip/infrastructure/gaps.py` | `city/topic/subject`, kind mới (B.5) |
| `web/src/user/ui/Assistant.tsx` (+ store/types nếu cần) | hiện thẻ nơi, nút Thích / Xem, nút trả lời nhanh |
| `src/bench/assistant.py` (mới), `src/bench/__main__.py` | `python -m bench assistant` |
| `src/decision/guard.py`, `engine.py`, `session.py`, `curation.py`, `pipeline.py`, `wishes.py`, `cards.py` | op `prefer` / `filter` / `unfilter` / `like` / `ask`; DATA nơi được nhắc |
| `src/decision/evaluate.py` | chỉ số C.3 |
| `docs/TRIP_UNDERSTANDING.md`, `docs/PLACE_DECISION.md`, `docs/log/DEV_LOG.md` | sửa cùng code |

---

### Task 1: Settings, state và guard đảo luật

**Files:**
- Modify: `config/trip.yaml`, `src/trip/infrastructure/settings.py`, `config/cities.yaml`, `src/trip/domain/state.py` (`Meta`), `src/trip/domain/guard.py` (`bad_say`)
- Test: `tests/trip/test_guard.py`, `tests/trip/test_assistant_state.py` (mới)

**Interfaces:**
- Produces:
  - `Settings.assistant: Assistant` với `enabled: bool = False`, `prefetch: bool = True`, `clef_threshold: float = 0.35`, `prefetch_wait_s: float = 1.2`, `reply_words: int = 60`, `max_candidates: int = 6`.
  - `config/cities.yaml` `dalat.center: {name: "Chợ Đà Lạt", lat: 11.9429, lng: 108.4372}`; đọc qua hàm sẵn có đọc cities (tìm bằng `grep -rn cities.yaml src/trip src/corpus`), thêm `city_center(city="dalat") -> tuple[str, float, float]` trong `trip/infrastructure/settings.py`.
  - `Meta.shown_ids: tuple[str, ...] = ()` (id nơi tool đã trả trong phiên, giữ 80 id mới nhất), `Meta.told_numbers: tuple[int, ...] = ()` (số trong kết quả tool của phiên, giữ 300), `Meta.intent: Literal["explore", "plan"] | None = None`, `Meta.invited: bool = False`.
  - `bad_say(say, heard, state, catalog, compared, reply_language=None, told="", allowed_ids: frozenset[str] = frozenset()) -> str | None`: id trong `allowed_ids ∪ state.meta.shown_ids` không bị coi là "names place"; số trong `state.meta.told_numbers` coi như đã nói.

- [ ] **Step 1: Viết test hỏng**

```python
# tests/trip/test_guard.py
def test_bad_say_allows_place_from_tool_results(catalog):
    pid, name = catalog.places[0].id, catalog.places[0].name
    st = TripState()
    assert bad_say(f"Bạn thử {name} nhé", "gợi ý quán", st, catalog, set()) == f"names place {pid}"
    assert bad_say(f"Bạn thử {name} nhé", "gợi ý quán", st, catalog, set(), allowed_ids=frozenset({pid})) is None

def test_bad_say_allows_numbers_told_this_session(catalog):
    st = with_meta(TripState(), told_numbers=(100000,))
    assert bad_say("Vé khoảng 100000 đồng", "vé bao nhiêu", st, catalog, set()) is None
    assert bad_say("Vé khoảng 90000 đồng", "vé bao nhiêu", st, catalog, set()).startswith("numbers")

# tests/trip/test_assistant_state.py
def test_old_snapshot_loads_with_new_meta():
    raw = Snapshot(id="0" * 12, state=TripState(), card=None, transcript=[]).model_dump(mode="json")
    for k in ("shown_ids", "told_numbers", "intent", "invited"):
        raw["state"]["meta"].pop(k)
    assert Snapshot.model_validate(_upgrade(raw)).state.meta.shown_ids == ()

def test_assistant_defaults_off():
    assert load().assistant.enabled is False and load().assistant.clef_threshold == 0.35
```

Dùng fixture `catalog` sẵn có trong `tests/trip/conftest.py` (nếu tên khác thì theo conftest).

- [ ] **Step 2: Chạy, xác nhận hỏng** — `.venv/bin/python -m pytest --collect-in-virtualenv tests/trip/test_guard.py tests/trip/test_assistant_state.py -q` → FAIL (`allowed_ids` không có, `Meta` thiếu field).
- [ ] **Step 3: Cài** các field/hàm ở Interfaces. `bad_say`: thêm `state.meta.told_numbers` vào tập `said`; `named |= allowed_ids | set(state.meta.shown_ids)`.
- [ ] **Step 4: Chạy lại** cùng lệnh + `tests/trip/test_guard.py` toàn file → PASS.
- [ ] **Step 5: Ghi ledger** (không commit).

### Task 2: `Knowledge` + tool đọc kho cho Agent (B.2)

**Files:**
- Create: `src/trip/infrastructure/knowledge.py`
- Modify: `src/trip/agent/tool_schemas.py`, `src/trip/agent/tools.py`, `src/trip/api/tools.py` (`create_engine(..., live=None)`), `src/trip/__init__.py` (xuất `LiveTools`), `src/harness/__main__.py`
- Test: `tests/trip/test_knowledge.py` (mới), `tests/trip/test_agent_tools.py`

**Interfaces:**
- Consumes: `RetrievalEngine.find(criteria: dict, limit) -> FindResult(hits, maybe, unknown, release_id)`, `RetrievalEngine.card(pid) -> dict | None`, `RetrievalEngine.similar(pid, within, ...)` (`src/corpus/retrieval/engine.py`); `trip.domain.coverage.admissible(place, hard, activity) -> bool`; `Catalog.places`, `Catalog.by_id` (hoặc tên tương đương trong `infrastructure/catalog.py`).
- Produces:
  - `@dataclass(frozen=True) class LiveTools: weather: Callable[[float, float, list[str]], dict] | None = None; matrix: Callable[[list[tuple[float, float]]], dict] | None = None` trong `trip/infrastructure/knowledge.py`, xuất ở `trip/__init__.py`.
  - `class Knowledge(retrieval, catalog, live: LiveTools | None, center: tuple[str, float, float])` với:
    - `find(criteria: dict, state: TripState, limit: int = 6) -> dict` → `{"places": [{"id", **card}], "maybe": int, "unknown": int}`; gọi `retrieval.find(criteria, limit=40)` rồi giữ hit qua `admissible(place, state.hard, state.activities.get(id))`; `ValueError` khi criteria sai (thông điệp của `Criteria.parse`).
    - `place(pid: str) -> dict | None` (`{"id", **card}`).
    - `similar(pid: str, state: TripState, limit: int = 6) -> list[dict]` qua hard filter như `find`.
    - `weather(day: date) -> dict` → `{"date", "rain_prob", "rain_mm"?, "source", "fetched_at"}` tại `center`; không có `live.weather` hoặc nó raise → `{"error": "weather unavailable"}`.
    - `distance(a: str, b: str) -> dict` (a, b là id hoặc `"center"`) → `{"minutes", "km"?, "source"}` qua `live.matrix`; lỗi như trên.
  - Tool mới (chỉ có trong `tool_names()` khi `cfg.assistant.enabled`): `find_places(criteria: dict)`, `get_place(id: str)`, `similar_places(id: str)`, `weather(date: "YYYY-MM-DD")`, `distance(a: str, b: str)`. Model pydantic trong `tool_schemas.py`: `FindPlaces`, `GetPlace`, `SimilarPlaces`, `Weather`, `Distance` (`extra="forbid"`, docstring = mô tả tool, nêu rõ `criteria` có khóa `groups, must, prefer, open_at, opens_by, dish, month, near, text` như `corpus.retrieval.find.KEYS`).
  - `TurnTools.cache: dict[tuple[str, str], dict]` (khóa `(tên tool, json.dumps(args, sort_keys=True))`); `TurnTools.told_ids: set[str]`; `TurnTools.told_numbers: set[int]` — mọi kết quả tool đọc kho đi qua `_remember(result)` ghi id và số nguyên ≥ 10 trong kết quả.
  - `TurnTools(..., knowledge: Knowledge | None = None, assistant: bool = False)`.
  - Harness: `trip_engine(data, binding=..., retrieval=..., live=LiveTools(weather=lambda lat, lng, d: live.weather(lat, lng, d, live_cfg), matrix=lambda pts: live.travel_matrix(pts, None, live_cfg)))` với `live_cfg = live.load_settings()`.

- [ ] **Step 1: Viết test hỏng**

```python
# tests/trip/test_knowledge.py  (dùng catalog/retrieval fixture nhỏ của tests/trip/conftest.py hoặc tests/retrieval/test_retrieval_boundary._make_engine)
def test_find_places_applies_hard_fail_closed(knowledge, kids_hard_state):
    out = knowledge.find({"groups": ["cafe"]}, kids_hard_state)
    assert out["places"] and all(admissible(knowledge.catalog.by_id[p["id"]], kids_hard_state.hard, None) for p in out["places"])

def test_find_bad_criteria_raises(knowledge):
    with pytest.raises(ValueError, match="unknown criteria"):
        knowledge.find({"color": "red"}, TripState())

def test_weather_unavailable_is_an_error_result(knowledge_no_live):
    assert knowledge_no_live.weather(date(2026, 11, 1)) == {"error": "weather unavailable"}

# tests/trip/test_agent_tools.py
def test_flag_off_keeps_tool_list(turn_tools):
    assert "find_places" not in turn_tools(assistant=False).tool_names()

def test_find_places_remembers_ids_and_numbers(turn_tools):
    t = turn_tools(assistant=True)
    out = t.run("find_places", {"criteria": {"groups": ["cafe"]}})
    assert {p["id"] for p in out["places"]} <= t.told_ids
    assert t.run("find_places", {"criteria": {"groups": ["cafe"]}}) == out  # second call hits the cache
```

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Cài** `Knowledge`, `LiveTools`, các tool, cache (`run` đọc cache trước khi gọi `_<name>`; tool ghi không bao giờ đọc cache), tiêm ở `create_engine` → `Engine(..., knowledge=...)` → `TurnTools`. `_trace_call` thêm dòng tiến độ: `find_places` "Tìm nơi trong dữ liệu", `get_place` "Xem chi tiết <tên>", `weather` "Xem thời tiết <ngày>", `distance` "Tính đường đi".
- [ ] **Step 4: Chạy** `tests/trip/test_knowledge.py tests/trip/test_agent_tools.py` → PASS.
- [ ] **Step 5: Ghi ledger.**

### Task 3: Clef chuẩn bị tool (B.3)

**Files:**
- Create: `src/trip/agent/prefetch.py`
- Modify: `src/trip/infrastructure/clef.py` (`yes_prob`)
- Test: `tests/trip/test_prefetch.py` (mới)

**Interfaces:**
- Consumes: `clef.ask(state: dict, questions: dict, cfg) -> dict`, `Knowledge` (Task 2), `TurnTools.cache` (Task 2).
- Produces:
  - `yes_prob(answers: dict, name: str, option: str = "A") -> float`: xác suất của `option` **bất kể** Clef chọn gì (khác `prob`).
  - `GROUPS: dict[str, str]` = nhóm `places`, `detail`, `weather`, `distance` với câu hỏi đúng như `GROUPS2` của `logs/clef_prefetch_bench.py` (nhóm `trend` để lại khi có nhịp Đà Lạt A.5).
  - `candidates(text: str, catalog: Catalog, k: int = 6) -> list[tuple[str, str]]` (id, name): so khớp **giữ dấu** (`vnorm` của bench: NFC, lower, bỏ dấu câu — không bỏ dấu thanh), tên nguyên cụm trước, rồi tên có đủ từ riêng (bỏ từ chung `GENERIC` như bench, từ ≥ 3 ký tự), xếp theo (loại khớp, độ dài, `voices`); bỏ nơi `category_group == "stay"` trừ khi khớp nguyên cụm.
  - `@dataclass class Route: groups: set[str]; places: list[str]  # ids; probs: dict[str, float]; clef_s: float`
  - `route(text: str, cands: list[tuple[str, str]], cfg: Settings, ask=clef.ask) -> Route`: một request Clef (`state={"user_message", "today"}`, câu `place1` / `place2` khi có ứng viên); nhận nhóm khi `yes_prob ≥ cfg.assistant.clef_threshold`; rồi **luật từ khóa chỉ thêm** đúng như `clef2` của bench (`DETAIL_WORDS`, `WEATHER_WORDS`, `LIST_WORDS`, bỏ `places` chỉ khi hỏi đúng một nơi có tên không kèm từ liệt kê; "chợ / trung tâm" + `distance` + < 2 nơi → thêm `"center"`). Clef trả `{}` (tắt / lỗi) → chỉ luật từ khóa.
  - `prepare(route: Route, text: str, state: TripState, tools: TurnTools, today: date, wait_s: float) -> dict`: chạy song song (ThreadPool) qua `tools.run(...)` để kết quả vào cache: `places` → `find_places({"text": places_query(text), ...})` (bỏ vế thời tiết như `places_query` của bench; có `distance` + nơi → thêm `km` từ nơi cuối tới từng nơi tìm được); `detail` → `get_place` mỗi nơi; `weather` → `weather` ngày rút từ tin nhắn (`dd/mm`, "mai", "thứ 7" qua `trip.domain.dates`), không có thì `state.start_date`; `distance` → `distance(places[0], places[1])`. Luôn có: thời tiết ngày đi khi `state.start_date` biết. Chờ tối đa `wait_s`; phần chưa xong bỏ khỏi `data` nhưng vẫn vào cache khi xong. → `{"tim_noi": [...], "chi_tiet": [...], "thoi_tiet": {...}, "khoang_cach": {...}}` (chỉ khóa có dữ liệu).

- [ ] **Step 1: Viết test hỏng** (Clef giả bằng tham số `ask=`)

```python
def test_candidates_keeps_accents_and_whole_name_first(catalog):
    ids = [pid for pid, _ in candidates("Đồi chè Cầu Đất mở cửa mấy giờ", catalog)]
    assert ids and catalog.by_id[ids[0]].name.lower().startswith("đồi chè cầu đất")
    assert candidates("mình muốn lên đó", catalog) == [] or all("len" not in n.lower().split() for _, n in candidates("mình muốn lên đó", catalog))

def test_route_keywords_only_add(cfg):
    r = route("Ngày 31/10 có mưa không, ăn gì cho ấm?", [], cfg, ask=lambda *a: {})
    assert {"weather", "places"} <= r.groups

def test_route_threshold(cfg):
    fake = lambda s, q, c: {"distance": {"choice": "B", "probabilities": {"A": 0.4, "B": 0.6}}}
    assert "distance" in route("đi mất bao lâu", [], cfg, ask=fake).groups

def test_prepare_times_out_into_cache(turn_tools_slow_weather):
    t = turn_tools_slow_weather  # weather callable sleeps 2 s
    data = prepare(Route({"weather"}, [], {}, 0.0), "mai có mưa không", TripState(), t, date(2026, 10, 28), 0.2)
    assert "thoi_tiet" not in data
```

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Cài** theo Interfaces; tách regex và `GENERIC` thành hằng số trong `prefetch.py`.
- [ ] **Step 4: Chạy** `tests/trip/test_prefetch.py tests/trip/test_clef.py` → PASS.
- [ ] **Step 5: Ghi ledger.**

### Task 4: Nối vào lượt Agent + prompt trợ lý (B.1, B.4 phần lời)

**Files:**
- Modify: `src/trip/agent/prompt.py`, `src/trip/api/engine.py` (`_agent_turn`), `src/trip/agent/tools.py` (`_ask_required`)
- Test: `tests/trip/test_assistant_turn.py` (mới; dùng chat kịch bản như `tests/trip/test_agent_loop.py`)

**Interfaces:**
- Consumes: Task 1–3.
- Produces:
  - `system_prompt(assistant: bool = False) -> str`: `False` = chuỗi hiện nay (không đổi một ký tự). `True` = bỏ câu "You never suggest places in this step" và bước 0 "never place names", thêm khối `ASSISTANT` (tiếng Anh, như văn phong prompt hiện có) nói: trả lời câu về Đà Lạt; chi tiết một nơi và gợi ý nơi **chỉ** từ `data` / tool (`find_places`, `get_place`, `similar_places`), không có thì "chưa có thông tin"; kiến thức chung tự trả lời, mở đầu "Tham khảo:" và số chỉ dạng khoảng; `data` đã là mọi thứ kho có, không gọi lại tool cho cùng nơi; ≤ 60 từ; tối đa một câu hỏi mỗi lượt; người dùng đang khám phá thì không hỏi ngày / số người / ngân sách; mời lên lịch tối đa một lần ("Bạn có muốn mình lên lịch cho chuyến này không?"); khi user muốn đi thì ghi `record_fact field=intent value=plan` và hỏi mục bắt buộc như hiện tại; hiện nơi bằng `show_places` (Task 5).
  - `build_messages(..., data: dict | None = None)`: CURRENT CONTEXT thêm `"data": data` khi có.
  - `record_fact` nhận field `intent` (`explore|plan`, chỉ `how=said`, quote phải trong tin nhắn) → `Meta.intent`.
  - `_ask_required` khi `assistant` bật: refuse `"the user is exploring; answer and invite planning once instead"` nếu `planning(state)` sai; `planning(state) = state.meta.intent == "plan" or state.start_date.known or state.days.known`. Đặt `planning` trong `trip/domain/required.py`.
  - `_agent_turn` (khi `cfg.assistant.enabled`): trước `build_messages` chạy `candidates` → `route` → `prepare` (song song với `lookups` sẵn có); sau vòng lặp: `check` dùng `allowed_ids=frozenset(tools.told_ids)`, `told` thêm số của `tools.told_numbers`; ghi `Meta.shown_ids`, `Meta.told_numbers` (giữ cuối 80 / 300); câu mời lên lịch: lần đầu → `Meta.invited=True`, lần sau → `drop_questions`. Log lượt thêm `prefetch groups=… clef=…s wait=…s`.

- [ ] **Step 1: Viết test hỏng**

```python
def test_flag_off_prompt_unchanged():
    assert system_prompt() == system_prompt(assistant=False) and "never suggest places" in system_prompt()

def test_assistant_turn_names_a_found_place(engine_assistant, scripted_chat):
    # the scripted model calls find_places, then replies naming the first hit
    s = run_turn(engine_assistant, "Gợi ý quán cà phê view đồi", scripted_chat(name_first_hit=True))
    assert first_hit_name in last_say(s) and first_hit_id in s.state.meta.shown_ids

def test_assistant_turn_prunes_unfound_place(engine_assistant, scripted_chat):
    s = run_turn(engine_assistant, "Gợi ý quán cà phê", scripted_chat(reply="Bạn ghé <tên nơi không có trong data> nhé. Quán nào cũng ấm."))
    assert "<tên" not in last_say(s)

def test_exploring_user_is_not_asked_required(engine_assistant, scripted_chat):
    s = run_turn(engine_assistant, "Đà Lạt tháng 11 có gì vui?", scripted_chat(call=("ask_required", {"topic": "dates", "question": "Bạn đi ngày nào?"})))
    assert "ask_required:error" in system_log(s)
```

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Cài** theo Interfaces.
- [ ] **Step 4: Chạy** `tests/trip -q` toàn bộ → mọi test cũ vẫn pass (cờ mặc định tắt) + test mới pass.
- [ ] **Step 5: Ghi ledger.**

### Task 5: Thẻ nơi trong chat, nút trả lời nhanh, act Thích (B.4)

**Files:**
- Modify: `src/trip/agent/tool_schemas.py`, `src/trip/agent/tools.py`, `src/trip/api/engine.py` (`TurnInput.kind` thêm `"like"`, transcript, event), `src/trip/api/tools.py` nếu cần, `web/src/user/ui/Assistant.tsx` (+ kiểu dữ liệu trong `web/src/user/store.ts` / `trip.tsx` nơi transcript được map)
- Test: `tests/trip/test_assistant_cards.py` (mới); web: `cd web && npx tsc --noEmit`

**Interfaces:**
- Produces:
  - Tool `show_places(ids: list[str] (1–6), why: str ≤ 120)`: chỉ id trong `told_ids ∪ meta.shown_ids`, khác thì error; `quick_replies(options: list[str] 2–4, mỗi cái ≤ 40 ký tự)`. Cả hai không kết thúc lượt.
  - Transcript: `{"role": "agent", "kind": "places", "turn", "ids", "why"}` và `{"role": "agent", "kind": "replies", "turn", "options"}`; event `emit("places", {"ids", "why", "cards": [...]})`, `emit("replies", {"options"})`.
  - `Knowledge.view(pid: str) -> dict | None` trong `trip/infrastructure/knowledge.py`: `{id, name, category, area, rating, reviews, photos (≤ 5 url, ưu tiên cảnh khác nhau nếu record có nhãn), hours_today, price, liked: bool}` — field lấy từ serving record, thiếu thì `null`, không suy ra.
  - `engine.load` trả cards dựng lại từ ids cho mọi thẻ `places` trong transcript (thẻ cũ không có `kind` này thì không đổi gì).
  - `TurnInput(kind="like", target=<place id>, value="on"|"off")` → không gọi model; `on` thêm `Anchor(text=name, place_id=id, state="matched", priority="want")`, `off` bỏ anchor `want` đó; id phải có trong `meta.shown_ids`.
  - Harness: kiểm `grep -rn "\"say\"\|allow" src/harness/dispatch.py src/harness/*.py` xem event có bị lọc theo allowlist không; có thì thêm `places`, `replies`. Thêm `place_like` vào allowlist `src/harness/events.py` và `web/src/user/events.ts` cạnh `outbound_click`.
  - Web: tin nhắn `places` = hàng thẻ dùng lại `PlaceCard.tsx` (≥ 3 ảnh khi có), nút **Thích** (gửi turn `like`), **Xem** (mở `PlaceSheet`); `replies` = các nút, bấm = gửi text như user gõ. Màu chỉ từ token (`tokens.css`); chỉ desktop. Dùng `/ui-ux-pro-max` trước khi sửa giao diện (memory chủ dự án).

- [ ] **Step 1: Viết test hỏng**

```python
def test_show_places_refuses_unseen_id(turn_tools):
    t = turn_tools(assistant=True)
    assert "error" in t.run("show_places", {"ids": ["nope"], "why": "x"})

def test_places_message_persists_and_reloads(engine_assistant, scripted_chat):
    s = run_turn(engine_assistant, "Gợi ý quán cà phê view đồi", scripted_chat(show_first_hit=True))
    msg = next(t for t in s.transcript if t.get("kind") == "places")
    loaded = engine_assistant.load(s.id)
    assert any(m.get("kind") == "places" and m["cards"][0]["id"] == msg["ids"][0] for m in loaded["transcript"])

def test_like_writes_want_anchor_without_model(engine_assistant, shown_session):
    engine_assistant.turn(shown_session.id, TurnInput(kind="like", target=shown_session.state.meta.shown_ids[0], value="on"), lambda *a: None)
    assert any(a.priority == "want" for a in engine_assistant.store.get(shown_session.id).state.anchors)
```

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Cài backend**, rồi web.
- [ ] **Step 4: Chạy** `tests/trip -q`, `cd web && npx tsc --noEmit` → PASS. Chụp màn chat với một thẻ nơi (vite port riêng, xem memory `landing-3d-screenshot-testing` về port) và tự xem như người mới.
- [ ] **Step 5: Ghi ledger.**

### Task 6: Câu chưa trả lời được → gaps (B.5)

**Files:**
- Modify: `src/trip/infrastructure/gaps.py`, `src/trip/agent/tools.py`, `src/trip/api/engine.py`
- Test: `tests/trip/test_gaps.py` (mới hoặc file gaps sẵn có)

**Interfaces:**
- Produces: `record(path, phrase, kind, city="dalat", topic=None, subject=None)`; dòng gom theo `(squash(phrase), kind, city)`. Kind mới: `zero_hits` (`find_places` trả 0 nơi; `phrase` = `json.dumps(criteria)`), `no_answer` (lời cuối có "chưa có thông tin"; `phrase` = tin nhắn user, `topic` = nhóm Clef đầu tiên), `unsourced_place` (`prune_say` cắt vì "names place"; `subject` = id). Không ghi `user_id`, session id hay dữ liệu cá nhân nào khác.

- [ ] **Step 1: Test hỏng**

```python
def test_gap_kinds_and_city(tmp_path):
    p = tmp_path / "gaps.jsonl"
    record(p, "quán mở 5h sáng", "zero_hits", topic="places")
    record(p, "quán mở 5h sáng", "zero_hits", topic="places")
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    assert rows == [{"phrase": "quán mở 5h sáng", "kind": "zero_hits", "city": "dalat", "topic": "places", "subject": None, "count": 2, "last_seen": rows[0]["last_seen"]}]
```

- [ ] **Step 2–4:** hỏng → cài → `tests/trip -q` pass.
- [ ] **Step 5: Ghi ledger.**

### Task 7: Bench trợ lý và bật cờ (B.3.7)

**Files:**
- Create: `src/bench/assistant.py`; Modify: `src/bench/__main__.py`
- Test: `tests/bench/test_assistant_bench.py` (mới; chạy với chat kịch bản, không gọi mạng)

**Interfaces:**
- Produces: `python -m bench assistant [--live] [--out data/bench/assistant/<ts>.json]`. Ca = 30 tin nhắn `MSGS` của `logs/clef_prefetch_bench.py` (chép sang `config/bench_assistant.yaml` với nhóm mong đợi); mỗi ca một phiên mới, Trip State gieo "2 người lớn, 2026-10-30 → 2026-11-01, xe máy", `assistant.enabled=True`. Đo mỗi ca: thời gian lượt, số lần gọi Agent (`t_call` trong `tools.timings`), nhóm Clef so nhóm mong đợi, số trong lời không có trong kết quả tool / state / tin nhắn, id hiện. Tóm tắt: p50 / p90, gọi/lượt, % lượt một lần gọi, `clef_full` (ca có đủ nhóm mong đợi), `ungrounded`.
- Ngưỡng bật (`--live`, sol thật): p50 ≤ 7,5 s, p90 ≤ 11 s, `ungrounded == 0`, `clef_full ≥ 29/30`. Đạt → đổi `config/trip.yaml` `assistant.enabled: true` và ghi số đo vào `docs/log/DEV_LOG.md`; không đạt → giữ `false`, ghi số đo và ca chậm vào ledger, báo chủ dự án.
- Đo lại persona "vague" của `docs/plans/TRIP_REDESIGN_HANDOFF.md` (spec D.1: 5/7 mục) bằng bench Trip sẵn có (`python -m bench run`, xem `src/bench/run.py`) với cờ bật; ghi trước/sau.

- [ ] **Step 1: Test hỏng** — `test_bench_assistant_summary_shape`: chạy 2 ca với chat kịch bản, assert khóa `p50_s, p90_s, calls_per_turn, single_call_rate, clef_full, ungrounded` có trong tóm tắt và `ungrounded == 0`.
- [ ] **Step 2–4:** hỏng → cài → pass; rồi chạy `--live` một lần (cần 9router :20128, gateway Clef :30000 sống — kiểm bằng curl trước).
- [ ] **Step 5:** Sửa `docs/TRIP_UNDERSTANDING.md`: §1 thay quy tắc "Chưa đề xuất địa điểm" bằng luật mới (được hiện nơi từ kho, qua tool), thêm mục trợ lý (tool, Clef chuẩn bị, guard đảo, thẻ `places`, gaps kind mới); ghi ledger.

### Task 8: Decision — op xếp hạng lại, lọc, "kiếm kiểu này", hỏi về nơi (C.1)

**Files:**
- Modify: `src/decision/guard.py`, `src/decision/engine.py` (`turn`, `_fields`, `_grounded_context`), `src/decision/session.py` (`State`), `src/decision/curation.py` (`apply`), `src/decision/pipeline.py` / `wishes.py` (likes vào wish), `src/decision/cards.py` hoặc nơi dựng `view` (filter), prompt `DECISION_TURN` (tìm bằng `grep -rn DECISION_TURN src/corpus/llm`), `src/decision/heuristics.py` nếu thêm câu quen
- Test: `tests/decision/test_decision_guard.py`, `tests/decision/test_decision_engine.py`, `tests/decision/test_curation.py`

**Interfaces:**
- Produces:
  - `Op` thêm `"prefer" | "filter" | "unfilter" | "like"`. `PlanUpdate.value`: `prefer` = `"<fid>=<value>"` hoặc `"<fid>=<value>:avoid"`; `filter` = `"<fid>=<value>"` hoặc `"opens_by=HH:MM"`; `like` cần `place` (alias).
  - guard → act: `prefer` → `{"type": "prefer", "feature", "value", "weight": ±1}` (act sẵn có, `curation.apply`; sai ontology thì drop kèm log); `filter` → `{"type": "filter", "key", "value"}`; `unfilter` → `{"type": "unfilter"}`; `like` → `{"type": "like", "place_id"}`.
  - `State.filters: list[tuple[str, str]] = []`, `State.likes: list[str] = []`. `curation.apply`: `filter` thêm (key phải là feature ontology với value hợp lệ, hoặc `opens_by` với `HH:MM`), `unfilter` xoá hết, `like` thêm id (phải là nơi có record).
  - Pipeline: mỗi id trong `State.likes` thành wish `like:<id>` như `si.wishes.like` (`decision/wishes.py` dòng ~50–59), cùng hệ số `a["like"]`.
  - View: nhóm chỉ hiện thẻ qua mọi `filters` (giá trị `VERIFIED`/`OUTDATED` khớp; giờ mở từ `operation.hours`); thẻ không qua **không** đổi `status`/`score`, chỉ ẩn; `view["filter"] = {"active": [...], "hidden": n}`. Nơi đã chọn/khoá luôn hiện.
  - Hỏi về nơi: `_fields` thêm `"data"` = `card()` (qua `self.retrieval.card`) của tối đa 3 alias user nhắc tên (cùng thứ tự như `_grounded_context`); prompt nói "DATA đã là mọi thứ kho có; trường không có thì nói chưa có thông tin; ≤ 60 từ". `_bad_say`: số trong DATA được phép (thêm vào `screen_text`).
  - Câu quen vẫn qua `heuristics` không gọi model; thêm vào `common_wish`: "chỉ (xem|lấy) quán mở (trước|từ) Xh" → `filter opens_by`, "bỏ lọc" → `unfilter`.

- [ ] **Step 1: Test hỏng**

```python
def test_guard_prefer_and_filter(aliases, name_keys):
    plan = TurnPlan(say="", updates=(PlanUpdate(op="prefer", value="noise=quiet", quote="yên tĩnh"),
                                     PlanUpdate(op="filter", value="opens_by=07:00", quote="mở trước 7h")))
    acts = guard(plan, "ưu tiên yên tĩnh, chỉ xem quán mở trước 7h", aliases, "", name_keys).actions
    assert {"type": "prefer", "feature": "noise", "value": "quiet", "weight": 1} in acts
    assert {"type": "filter", "key": "opens_by", "value": "07:00"} in acts

def test_filter_hides_but_never_rescores(engine_with_session):
    e, sid = engine_with_session
    before = {c["id"]: c for g in e.load(sid)["view"]["groups"] for c in g["cards"]}
    after = e.act(sid, {"type": "filter", "key": "opens_by", "value": "07:00"})["view"]
    assert after["filter"]["hidden"] > 0
    for g in after["groups"]:
        for c in g["cards"]:
            assert c.get("score") == before[c["id"]].get("score")
    assert e.act(sid, {"type": "undo"})["view"].get("filter", {}).get("active", []) == []

def test_like_lifts_similar_places(engine_with_session_two_lookalike_cafes):
    # fixture: cafes A and B share every look feature; B starts below rank 1 of its group
    e, sid, a, b = engine_with_session_two_lookalike_cafes
    rank = lambda v: [c["id"] for g in v["groups"] if g["key"] == "best" for c in g["cards"]]  # "Hợp nhất"
    before = rank(e.load(sid)["view"])
    after = rank(e.act(sid, {"type": "like", "place_id": a})["view"])
    assert after.index(b) < before.index(b)
    assert set(before) <= set(after) | {a}  # no place leaves the list because of a wish
```

- [ ] **Step 2: Chạy, xác nhận hỏng.**
- [ ] **Step 3: Cài.**
- [ ] **Step 4: Chạy** `tests/decision -q` → PASS (test cũ không sửa assert).
- [ ] **Step 5:** `docs/PLACE_DECISION.md` §18 thêm op mới, `filter` theo phiên, DATA; ghi ledger.

### Task 9: `decision evaluate` — chỉ số C.3

**Files:**
- Modify: `src/decision/evaluate.py`, `config/eval_trips.yaml` (thêm `wishes` cho vài trip: `dish`, `kind`, `like`)
- Test: `tests/decision/test_evaluate.py`

**Interfaces:**
- Produces: `evaluate()` thêm vào kết quả (`data/decision/eval.json`):
  - `wish_hit_rate`: tỉ lệ mong muốn user nói (`dish|kind|like`) có ≥ 1 nơi khớp trong "Hợp nhất" khi corpus có nơi qua hard (mục tiêu đo, cảnh báo < 0,9);
  - `wish_rank_median`: thứ hạng trung vị của nơi khớp trong nhóm của nó (mục tiêu ≤ `cfg.page_size` hoặc tên tương đương);
  - `drop_one_changes`: tỉ lệ mục Search Input (mỗi soft, mỗi wish) bỏ đi thì thứ hạng hoặc `because` đổi (mục tiêu 1,0; mục không đổi gì liệt kê tên);
  - `wish_penalized`: số nơi bị loại hoặc trừ điểm vì một mong muốn (mục tiêu 0);
  - `rebase_ms` p50/p95 (`Tools.rebase` trên phiên đã có, mục tiêu < 1.000), `text_turn_ms` p50/p95 cho câu đi `heuristics` (mục tiêu < 300; 10 câu cố định trong `evaluate.py`).
  - Bộ ca persona: chuyển các ca Search Input của 77 persona (`docs/superpowers/specs/2026-10-15-trip-understanding-cases.md`) thành `config/eval_personas.yaml` (chỉ trường Search Input đã compile: hard, soft, wishes, purpose, pace) — nếu file case không đủ để compile thì ghi vào ledger và chỉ dùng `eval_trips.yaml`.

- [ ] **Step 1: Test hỏng** — `test_evaluate_reports_c3_metrics`: chạy `evaluate(records=<fixture nhỏ>)`, assert có các khóa trên, `wish_penalized == 0`, `0 <= wish_hit_rate <= 1`.
- [ ] **Step 2–4:** hỏng → cài → pass; chạy `python -m decision evaluate` thật một lần, ghi số vào ledger.
- [ ] **Step 5:** Chỗ nào sai / chậm so với mục tiêu: sửa trong cùng task (một vòng), không nới ràng buộc; còn lại ghi vào ledger cho chủ dự án. Cập nhật `docs/PLACE_DECISION.md` §17.

---

## Để sau (không trong plan này)

| Mục spec | Vì sao chưa |
|---|---|
| B.1 "đào sâu khi câu trả lời đổi thứ hạng" (harness chạy thử Search Input qua `decision.run_pipeline`) | cần đường harness → Decision mới; làm sau khi Task 4 đo xong |
| B.2 `aspect`, `local_knowledge`, `trends`, `stay_price`, `transport`; B.4 `show_map`, `show_media` | dữ liệu chưa có (corpus P3–P7, A.5, A.6, A.7) |
| B.6 đường từ nhà tới chỗ ở + `booking` | plan riêng; chuyến bay cần Playwright (P0 chưa xong) |
| C.1 chatbot Decision dùng Clef chuẩn bị đầy đủ (thời tiết, khoảng cách) | Task 8 chỉ chuẩn bị DATA nơi; mở rộng khi Task 7 chứng minh đường Trip |
| C.2 "đang hot", lọc theo đặc trưng thành phố, thẻ ≥ 3 ảnh theo cảnh, "Xem không gian" | cần A.5, A.1, A.6, E.2 |
| E.1 hồ sơ cá nhân hóa | spec §3 việc 10 |
