# scripts

Script chạy tay hoặc từ cron, luôn từ gốc repo. Cách dùng chi tiết nằm trong docstring / comment đầu mỗi file; tài liệu cột phải mô tả hành vi.

| Nhóm | Script | Tài liệu |
|---|---|---|
| Vận hành prod (cron) | `keepalive.py`, `disk_guard.sh`, `pg_backup_nas.sh`, `pulse_daily.sh`, `prewarm_transit.py` (qua `./run.sh prewarm`) | `docs/OPERATIONS.md` §4–5 |
| Thiết lập máy, dữ liệu | `osrm_setup.sh`, `pack_data.py` | `README.md` §Thiết lập |
| Host model tự chạy | `models_ctl.sh` (điều phối), `model_gateway.py`, `clef_server.py`, `gemma_server.sh`, `vllm_server.sh`, `vllm_patch_sm75.py` | `docs/LLM_PROVIDER.md` |
| Chuỗi corpus | `gmaps_runner.py`, `photo_targets.py`, `free_tiktok_clips.py`, `tiktok_place_loop.sh`, `rerun_observe.sh` (cổng: `observe_prompt_eval.py`), `observe_places_eval.py` | `docs/CORPUS.md` §CLI, §Vòng lặp tự động |
| Đo, thử tay | `trip_tester.py` (client Streamlit cho Trip qua harness), `journey_sim.py`, `prod_journey_e2e.py`, `local_stack.sh` (stack đo cô lập), `bench_live.sh` | `README.md` §Test, `docs/OPERATIONS.md` §1, `docs/TRIP_UNDERSTANDING.md` §16 |

Script của web (build, ảnh, snapshot, test Node) nằm ở `web/scripts/`.

Đường dẫn của các script vận hành nằm trong crontab của gpu156 và trong `run.sh`; đổi tên hay chuyển chỗ thì sửa cả hai, rồi `crontab -l` để kiểm.
