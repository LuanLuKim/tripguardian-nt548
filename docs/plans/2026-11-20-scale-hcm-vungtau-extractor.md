# Mở rộng corpus sang TP.HCM và Vũng Tàu; chọn Extractor tự host (20/11/2026)

Chủ dự án hỏi ngày 19/11/2026: thiết kế để scale corpus sang Hồ Chí Minh và Vũng Tàu, và chọn model thay Gemma 4 26B-A4B của UIT để làm data. Model phải host được trên GPU này (được đẩy bớt ra RAM nếu cần), vừa nhanh vừa tốt, sao cho làm corpus nhanh nhất. Bản này là kết quả nghiên cứu và số đo, **chưa sửa code, chưa đổi `.env`**. Cần chủ dự án quyết các mục ở §7.

Đọc trước: `docs/CORPUS.md` (§Pipeline, §Vai trò model, §Mở rộng), `docs/LLM_PROVIDER.md` (§Host LAN, §UIT API).

## 0. Kết luận

1. **Trên card này không có model nào vừa nhanh vừa tốt bằng Gemma 26B.** Đo thật 19–20/11 trên cùng các lô review Đà Lạt (§3):
   - Qwen3.5-9B: 3–4,9 lô/phút, độ chính xác (precision) 81–86% tùy prompt.
   - Qwen3.5-4B: tối đa 2,2 lô/phút, lặp vô hạn ở 28–50% số lô.
   - Gemma 26B với expert đặt trong RAM: ~3,5 token/s tổng, không dùng được vì CPU máy dùng chung đã quá tải.
   - Mốc so: Gemma trong corpus đạt precision ~94%; host LAN từng chạy ~19 lô/phút.
2. **Extractor nên giữ Gemma 4 26B-A4B cho cả ba thành phố.** Cùng model với Đà Lạt thì nhãn Judge, ngưỡng và rule tổng hợp vẫn dùng được, chất lượng giữa các thành phố cũng so được với nhau. Thứ cần thêm là **chỗ chạy Gemma**, không phải một model khác (§4).
3. **Đòn bẩy lớn nhất không nằm ở model mà ở số token mỗi thành phố cần:**
   - JSON gọn: −50% token ra.
   - Prefix cache: bỏ được ~75% phần prefill.
   - Trần review mỗi nơi.
   - Phạm vi nơi ở HCM.

   Riêng hai đòn về prompt đã cho cùng một card +63% lô/phút (đo trên Qwen3.5-9B), nhưng chưa đo chất lượng trên Gemma. Hai đòn sau giảm số lô: trần 500 review bớt 13% ở Đà Lạt, và bớt nhiều hơn ở HCM (§2).
4. **HCM lớn gấp khoảng 8–15 lần Đà Lạt** (ước lượng, §1). Chưa giảm khối lượng thì riêng `review_observe` của HCM mất 11–20 ngày trên host LAN, 1,5–2,5 tháng trên card này. Phải chạy Discover trước để có số thật.

## 1. Khối lượng

### Đà Lạt (đo từ `data/`)

| Mục | Số |
|---|---|
| Danh sách nơi (`list/dalat.json`) | 1.780 nơi, 939k review trên Maps, trung vị 150 review/nơi; 205 nơi ≥ 1.000 review |
| Chỗ ở (`dalat_stay`) / dịch vụ (`dalat_svc`) | 1.525 / 1.279 |
| Nơi đã observe | 3.299 |
| Review gửi model (`review_observe`) | 546k → ~36k lô (15 review/lô, `prep.BATCH_REVIEWS`) |
| Mỗi lô | ~6,4k token vào (tokenizer Qwen; Gemma ~4,8k), 1,4–3k token ra |
| Ảnh Maps | 67k |

`review_observe` chiếm phần lớn token của build. Các task khác (ảnh, TikTok, span check, QC) cộng lại ít hơn nhiều.

### HCM và Vũng Tàu (ước lượng, cần Discover để có số thật)

- Cả nước còn khoảng 300k cửa hàng F&B (giữa 2026). Giả định TP.HCM chiếm khoảng 1/4 và 20–30% số đó có từ 30 review trên Maps (ngưỡng `gmaps.min_reviews` hiện tại), thì danh sách HCM vào khoảng **15–27k nơi**, gấp 8–15 lần Đà Lạt. Nơi ở HCM cũng nhiều review hơn, nên số lô có thể còn cao hơn tỉ lệ đó.
- Vũng Tàu: cỡ 0,7–1 lần Đà Lạt.
- Theo luật hiện tại (đọc mọi review, `max_reviews_per_place: 5000`), HCM cần khoảng **300–550k lô `review_observe`**.

| Nơi chạy | Lô/phút | Đà Lạt (36k lô) | HCM (300–550k lô) |
|---|---|---|---|
| Host LAN Gemma (đo 07/10, `LLM_PROVIDER.md`) | ~19 | ~32 giờ | 11–20 ngày |
| 2080 Ti, Qwen3.5-9B (đo 20/11) | 4,9 | ~5 ngày | 42–78 ngày |

Wall clock của crawl cũng tăng theo số nơi. TikTok bị giới hạn bởi Akamai, ~30 video/phút/IP (`config/queries.yaml`); Maps chạy theo số tab. Phần crawl nên chạy song song với phần model, không chạy nối đuôi nhau.

## 2. Bốn đòn bẩy giảm khối lượng, xếp theo hiệu quả

| Đòn bẩy | Tác động | Bằng chứng | Rủi ro |
|---|---|---|---|
| **JSON gọn**: thêm câu "Write the JSON compact on one line" vào cuối prompt | −49% token ra trên Gemma (3.012 → 1.528 token/call). Gộp với prefix cache: +63% lô/phút trên Qwen3.5-9B (3,0 → 4,9) | `LLM_PROVIDER.md` §Sức chứa thật; §3 | Đổi output: trên Gemma khớp template cũ 76,5%, trong khi mốc nhiễu (Gemma chạy lại chính nó) là 82,8%. Trên Qwen3.5-9B hụt 2–5 điểm chất lượng; trên Qwen3.5-4B tăng lặp vô hạn (§3). Phải đo trên Gemma trước khi áp |
| **Prefix cache**: dời dòng `Place:` xuống ngay trước `Reviews:` | Prefix trúng ~4,9k/6,4k token mỗi call (vLLM, đo 20/11); +26% token/s ở mức trần (host LAN) | `LLM_PROVIDER.md`; metrics vLLM 20/11 | Chỉ đổi thứ tự dòng; vẫn phải qua regression vì đổi prompt hash |
| **Trần review mỗi nơi** (đọc mới nhất trước, như hiện nay) | Đà Lạt: trần 500 còn 87% khối lượng, 97% (nơi, feature) giữ nguyên giá trị đa số; trần 300 còn 72% khối lượng, giữ 92% | Đo trên 390 nơi ≥ 400 review (§6) | Đổi quyết định "crawl hết comment" (07/10). HCM có nhiều nơi hàng nghìn review nên tiết kiệm nhiều hơn Đà Lạt |
| **Phạm vi nơi ở HCM**: tăng `min_reviews` cho nhóm ăn uống, giới hạn khu vực | Có thể giảm vài lần số nơi | Cần số Discover | Quyết định sản phẩm (§7) |

Ba đòn đầu cũng làm Đà Lạt rẻ hơn khi refresh. Chúng đổi prompt hash, nên áp vào thì cache Đà Lạt hết hạn, trừ khi chạy với `keep_stale` như hiện có.

## 3. Đo model trên GPU này (19–20/11/2026)

**Phần cứng.** Một RTX 2080 Ti 11 GB (sm75) là card duy nhất luanhh thấy được; máy có 8 card nhưng 7 card kia bị cgroup chặn. Card này:
- không có bf16, fp8 hay FlashAttention 2;
- vLLM chỉ có attention Triton, và Gated DeltaNet (lớp linear của Qwen3.5) cũng chạy kernel Triton.

CPU 2×Xeon Silver 4210 (40 luồng, AVX-512) dùng chung: load average 110–190 suốt lúc đo. RAM 754 GB.

**Cách đo.**
- Bộ đo: 96 lô `review_observe` thật lấy từ 96 nơi Đà Lạt chọn ngẫu nhiên (seed 7, mỗi nơi lô đầu), đúng prompt và schema hiện tại, guided JSON, temperature 0, thinking tắt. Mỗi model chạy 16–32 lô.
- Mốc so: observation Gemma 26B đã lưu trong `data/gmaps/observations/` (đã qua gate và span check). Theo chủ dự án, không gọi UIT vì UIT đang bận.
- Output của model thử đi qua đúng gate của production (`observe/gmaps/gate.py`: feature có trong ontology, quote có trong review), không qua span check.
- Claim chỉ một bên có được terra (9router) chấm: review có nói điều đó không.
- Precision ước tính = (claim cả hai bên cùng có + claim riêng được terra xác nhận) / tổng claim của bên đó. "Tìm được" = số claim đúng bên đó có / tổng claim đúng của cả hai bên.

| Model / engine | Lô/phút | Token ra/lô | Lô hỏng | Precision | Tìm được claim đúng |
|---|---|---|---|---|---|
| Gemma 26B trong corpus (mốc) | (host LAN ~19) | ~3k (JSON thụt lề) | — | ~94% * | ~90% |
| Qwen3.5-9B Q4_K_M, llama.cpp 8 slot, prompt hiện tại | 3,0 | 1,9k | 0/16 | ~86% | ~79% |
| Qwen3.5-9B, prompt gọn (JSON một dòng + `Place:` dời xuống) | **4,9** | 1,4k | 0/32 | ~81% (16 lô đầu: 84%) | ~72% (16 lô đầu: 74%) |
| Qwen3.5-9B, prompt gọn, 16 slot | 4,3 | 1,6k | 2/32 lặp | — | — |
| Qwen3.5-9B, prompt gọn, không guided | 3,5 | 1,6k | 1/16 lặp | — | — |
| Qwen3.5-4B AWQ, vLLM 0.32, prompt hiện tại | 1,9 | 4,2k | 9/32 (5 lặp tới 8k token, 4 quá hạn) | ~80% | ~82% |
| Qwen3.5-4B AWQ, vLLM, prompt gọn | 2,2 | 4,9k | 16/32 lặp | ~76% | ~86% |
| Gemma 4 26B-A4B QAT q4_0, llama.cpp, expert 18/30 lớp trong RAM | ~0,15 (3,5 token/s tổng) | — | — | (cùng model với mốc) | — |

\* Precision của Gemma là sau span check; model thử chưa qua span check, nên chênh thật nhỏ hơn bảng một chút. Precision chỉ tính trên các lô có trả lời.

Đọc bảng:

- **Qwen3.5-9B là model tự host tốt nhất trên card này**: ổn định, không lặp, nhanh nhất. Với prompt hiện tại, precision thấp hơn Gemma ~8 điểm, tìm được claim đúng thấp hơn ~13 điểm; với prompt gọn thì nhanh hơn 63% nhưng còn hụt thêm 2–5 điểm. Dù vậy vẫn chậm gần 4–6 lần host LAN, và 8 slot đã là trần: 16 slot không nhanh hơn. Trên benchmark công khai, Qwen3.5-9B ngang Gemma 26B-A4B (MMLU-Pro 82,5 so với 82,6), nhưng bài trích review tiếng Việt có ontology thì không ngang.
- **Prompt gọn làm giảm chất lượng trên Qwen3.5-9B** (16 lô, cùng mốc), nên phải đo trên Gemma trước khi áp (§5 bước 3).
- **Qwen3.5-4B** lặp vô hạn trên một phần lớn số lô; prompt gọn làm nặng hơn.
- **vLLM trên Turing nghẽn ở GPU**: chạy 100%, 200–250 W, mà chỉ ~25 token/s mỗi chuỗi. Bộ nhớ chỉ đủ KV cho ~8 call cùng lúc. Server mất 25 phút để khởi động.
- **llama.cpp** dùng GPU 40–80%, phần còn lại chờ CPU.
- **Đẩy expert Gemma ra RAM** cần CPU rảnh. Máy này đang chạy job của người khác (load > 100), nên tiến trình chỉ giành được ~10 lõi: 0,8–1 token/s mỗi chuỗi.
- **Không vừa card**:
  - Gemma 4 12B: bản AWQ 11,2 GB.
  - Gemma 4 26B-A4B: bản AWQ 17,2 GB.
  - Qwen3.5-9B AWQ cho vLLM: 9,1 GB vì bảng embedding để bf16, không còn chỗ cho KV.
- **Bản vLLM vá cho 2080 Ti** (weicj, kernel Gated DeltaNet riêng cho sm75) chỉ được kiểm trên 2 card 22 GB có NVLink, không phải một card 11 GB.

Script, bộ 96 lô, kết quả thô và log server nằm ở `logs/llm_bench/` (gitignore, không nằm trong repo):

- `build_set.py`: dựng bộ lô.
- `serve_vllm.sh`, `serve_llama.sh`: chạy server bench trên GPU 0, cổng 30005 / 30006. Bọc trong `scripts/gpu_lease.sh`.
- `run_set.py`: gửi bộ lô tới một endpoint, có các cờ `--compact`, `--place-last`, `--no-guided`.
- `score.py`: so với observation đã lưu; `--arbiter` cho terra chấm phần lệch, verdict cache trong `terra_cache.json`.
- `saturation.py`: đo trần review (§6).

Đo Gemma (§5 bước 3):

```bash
.venv/bin/python logs/llm_bench/run_set.py --set logs/llm_bench/set96.jsonl --base <url> --model <tên> --key-env UIT_API_KEY --conc 16 [--compact --place-last] --out <file>
PYTHONPATH=src .venv/bin/python logs/llm_bench/score.py --set logs/llm_bench/set96.jsonl --res <file> --arbiter
```

## 4. Thiết kế đề xuất

### 4.1 Model theo vai trò

- **Extractor = Gemma 4 26B-A4B** cho mọi thành phố, như hiện nay. Không đổi model giữa chừng: nhãn Judge, `label_stats` và ngưỡng servable đo theo output của model này.
- **Judge**: giữ như `LLM_PROVIDER.md`.
- **Qwen3.5-9B trên 2080 Ti**: không dùng cho `review_observe`. Chỉ đáng thử cho task ngắn có đáp án đóng (`PLACE_FILTER`, `VIDEO_FILTER`, `PLACE_POI_MATCH`), sau khi đo trên bộ nhãn có sẵn. Chưa đo.

### 4.2 Chỗ chạy Gemma (cần thêm sức chứa)

Code đã có sẵn lane cho nhiều endpoint: `Slots` của `gmaps observe`, cùng `EXTRACTOR_ALSO_UIT` và `EXTRACTOR_ALSO_SELFHOST` / `SELFHOST_EXTRACTOR_*` (`src/corpus/llm/roles.py`). Thêm sức chứa Gemma thì không phải sửa code. Thứ tự nên làm:

1. **Đưa host LAN `192.168.20.150` chạy lại.** Không phản hồi từ 15/11; khi chạy, nó là nguồn Gemma nhanh nhất mình có (~940 token sinh/s).
2. **Xin thêm card trên gpu156.** Gemma 26B-A4B AWQ cần từ 3–4 card 11 GB trở lên cho vLLM (thử 29/10: 2 card không đủ KV). Bản vá sm75 `scripts/vllm_patch_sm75.py` đã có. Khi có 4 card thì đo lại bằng bộ bench ở §3.
3. **UIT** khi rảnh, chung key 40 call với Judge.
4. **GPU thuê theo đợt**, nếu cần xong HCM nhanh. Một card ≥ 48 GB chạy vLLM Gemma 26B-A4B có KV rộng và gom batch lớn. Chưa đo, chỉ là phương án.

### 4.3 Thứ tự build một thành phố mới

```text
Discover (search → filter → counts → list)        crawl Maps, PLACE_FILTER ngắn; ra số nơi thật
   → chủ dự án chốt phạm vi (min_reviews, khu vực) theo số đó
   → crawl review / ảnh  ║  TikTok place_search     song song, theo throttle sẵn có
   → observe theo lô, nơi nhiều người xem trước     lane: LAN + UIT (+ card thêm)
   → aggregate → judge → serving
```

Observe nên đi theo thứ tự ưu tiên (nơi nổi bật, nơi có TikTok trước) để có bản phục vụ được sớm, không chờ xong cả thành phố.

### 4.4 Việc cần làm trong code/config để chạy thành phố mới

Phần build corpus gần như chỉ là config, nhưng còn mấy chỗ gắn với Đà Lạt:

- `config/cities.yaml`: thêm `hcm` và `vungtau` (area, `stay_within`, `center`). Từ 01/7/2025, Vũng Tàu thuộc TP.HCM sau sáp nhập tỉnh. Corpus vẫn coi chúng là hai điểm đến riêng (hai bbox), nhưng dữ liệu theo tỉnh (`config/provinces.yaml`, thời tiết, sự kiện, ngày lễ) sẽ gộp cả hai vào "TP. Hồ Chí Minh", cần kiểm.
- `config/queries.yaml`:
  - `gmaps.categories` mang đặc thù Đà Lạt (thác, đồi, rừng thông, vườn dâu). Cần danh mục theo thành phố: Vũng Tàu cần bãi biển, hải đăng, quán hải sản; HCM cần phố đi bộ, rooftop bar, quán ốc.
  - `stay.areas` đang là phường của Đà Lạt; cần danh sách khu vực theo thành phố.
- `config/ontology.yaml` chưa có biển / tắm biển / hải sản / máy lạnh / kẹt xe. Thêm feature làm đổi `cache_key` của observe, nên mọi nơi Đà Lạt sẽ bị coi là cũ. Nên chạy observe Đà Lạt với `keep_stale` khi đổi ontology, hoặc tách ontology thành phần chung + phần theo thành phố.
- Prompt corpus còn ghi cứng "Đà Lạt": `MENU_READ` (`src/corpus/llm/tasks.py` ~dòng 1899), và các tập từ "loose" của events / pulse / seasons (`dalat`, `da`, `lat`).
- Phần online (`src/trip`, `src/planning`, harness) còn nhiều chỗ chỉ biết Đà Lạt (prompt Agent, câu hỏi, guard). Ngoài phạm vi bản này, nhưng phải làm thì người dùng mới chọn được thành phố mới.

### 4.5 Dùng chung GPU

- Job model trên GPU chạy qua `scripts/gpu_lease.sh`: harness prod chuyển encoder sang CPU (~10 s mỗi call) trong lúc job giữ GPU.
- Vì vậy chạy model corpus dài ngày trên card này cũng làm chậm phần ảnh / câu của người dùng trên prod suốt thời gian đó. Đây là thêm một lý do không đặt lane chính lên card này.

## 5. Kế hoạch

1. Chạy Discover cho `vungtau` rồi `hcm`, sau khi thêm config ở §4.4 (danh mục, khu vực). Chưa observe.
2. Chủ dự án chốt phạm vi HCM theo số nơi thật (§7).
3. Đo JSON gọn + dời `Place:` trên **Gemma** bằng bộ bench §3 khi UIT hoặc host LAN rảnh: chất lượng ở mức (review, feature, value) so với observation đã lưu, có terra chấm phần lệch. Đạt thì áp vào `REVIEW_OBSERVE` và các task cùng kiểu.
4. Gom sức chứa Gemma (§4.2), rồi observe theo thứ tự ưu tiên.

## 6. Cách đo trần review

- Lấy 390 nơi Đà Lạt có ≥ 400 review đã đọc, xếp review mới nhất trước.
- Với mỗi (nơi, feature) có ≥ 3 tác giả, so giá trị đa số (theo tác giả) khi chỉ đọc N review đầu với khi đọc hết.

| N review mới nhất | Feature còn thấy | Cùng giá trị đa số | Phần khối lượng của cả Đà Lạt |
|---|---|---|---|
| 100 | 79,8% | 73,6% | 42% |
| 200 | 91,3% | 85,7% | 61% |
| 300 | 96,0% | 91,7% | 72% |
| 500 | 99,0% | 97,0% | 87% |
| 800 | 100% | 99,8% | 97% |

Đây là xấp xỉ: rule tổng hợp thật (`corpus/aggregate`) dùng confidence và luật riêng từng feature, không phải đa số đơn giản.

## 7. Cần chủ dự án quyết

1. Nguồn Gemma cho đợt HCM: khôi phục host LAN, xin thêm card trên gpu156, hay thuê GPU theo đợt (§4.2)?
2. Phạm vi HCM: `min_reviews` cho nhóm ăn uống và khu vực nào (quyết sau khi có số Discover)?
3. Trần review mỗi nơi (300 hay 500, hay giữ đọc hết) cho thành phố mới?
4. Áp JSON gọn + dời `Place:` sau khi đo trên Gemma?
