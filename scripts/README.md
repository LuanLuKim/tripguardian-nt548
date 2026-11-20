# scripts

Script chạy tay hoặc từ cron, luôn từ gốc repo. Cách dùng chi tiết nằm trong docstring / comment đầu mỗi file; tài liệu cột phải mô tả hành vi.

| Nhóm | Script | Tài liệu |
|---|---|---|
| Vận hành prod (cron) | `keepalive.py`, `disk_guard.sh`, `pg_backup_nas.sh`, `pulse_daily.sh`, `trends_daily.sh`, `prewarm_transit.py` (qua `./run.sh prewarm`) | `docs/OPERATIONS.md` §4–5 |
| Thiết lập máy, dữ liệu | `osrm_setup.sh`, `pack_data.py` | `README.md` §Thiết lập |
| Host model tự chạy | `models_ctl.sh` (điều phối), `model_gateway.py`, `clef_server.py`, `gemma_server.sh`, `vllm_server.sh`, `vllm_patch_sm75.py` | `docs/LLM_PROVIDER.md` |
| Chuỗi corpus | `gmaps_runner.py`, `photo_targets.py`, `free_tiktok_clips.py`, `tiktok_place_loop.sh`, `rerun_observe.sh` (cổng: `observe_prompt_eval.py`), `observe_places_eval.py` | `docs/CORPUS.md` §CLI, §Vòng lặp tự động |
| Đo, thử tay | `trip_tester.py` (client Streamlit cho Trip qua harness), `journey_sim.py`, `prod_journey_e2e.py`, `local_stack.sh` (stack đo cô lập), `bench_live.sh` | `README.md` §Test, `docs/OPERATIONS.md` §1, `docs/TRIP_UNDERSTANDING.md` §16 |
| Mô hình diorama 3D | `diorama/` (engine, kit, build, render và pipeline batch; dữ liệu ngoài repo qua `DIORAMA_DATA`) | Cách dùng trong từng script |

Script của web (build, ảnh, snapshot, test Node) nằm ở `web/scripts/`.

Đường dẫn của các script vận hành nằm trong crontab của gpu156 và trong `run.sh`; đổi tên hay chuyển chỗ thì sửa cả hai, rồi `crontab -l` để kiểm.

## Diorama tự động

Stack render: `bash scripts/diorama/stack.sh up|status|down` (3 worker bridge, HTTP 8471/8472; chỉ dừng PID do stack tạo).

Lối vào: `.venv/bin/python scripts/diorama/batch/auto3d.py`. Các lệnh: `queue --tier A,B --n 3`,
`run <fid|slug>... [--kit K] [--builder agent|function] [--redo]`, `status`, `gallery [out.jpg]`,
`publish <slug>...` (chỉ nhận `ready`), `add "<tên>"`; `exam` báo chưa triển khai.
`add` chỉ gọi API đề cử corpus và in chuỗi lệnh cần chạy tiếp, không mở trình duyệt.

Ngưỡng và effort nằm ở `config/diorama.yaml`. Code ở `scripts/diorama/auto3d/`; dữ liệu theo `paths.py`:
`DIORAMA_DATA` hoặc `../tripguardian-store/splat/diorama`. Mỗi nơi lưu `places/<slug>/auto3d.json`;
`stage` là bước kế tiếp, được lưu sau mỗi chuyển trạng thái. Gate đếm ảnh exterior + view còn giữ,
không stale, trước prep và sau khi NOTES loại ảnh. Review độc lập trả checklist; code quyết định pass/dừng.
Hai builder cùng dùng ảnh bằng chứng nguyên cỡ: agent nhận catalogue/ví dụ dán sẵn, function sửa bằng patch theo id.
Boot lỗi phục hồi `place.boot.json`; dừng vì hết lượt hoặc không tăng điểm phục hồi `place.best.json`
(chưa có checklist thì dùng bản boot gần nhất nếu có). Trạng thái cuối giữ nguyên trừ `run --redo`;
lịch sử và tổng token được giữ, ledger ghi nối ở `batch/ledger.jsonl`. Render nằm ở `out_<slug>/`.
Kiểm thử không gọi model, Node hay bridge: `.venv/bin/python -m pytest tests/diorama -q`.
