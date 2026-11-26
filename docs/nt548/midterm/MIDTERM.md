# Báo cáo tiến độ giữa kỳ NT548, nhóm 8 (27/11/2026)

> Tình trạng đồ án đến ngày 26/11, kèm bằng chứng chạy lại được và kế hoạch tới hạn nộp **04/12/2026**. Repo: <https://github.com/LuanLuKim/tripguardian-nt548>. Báo cáo cuối kỳ: `REPORT.md`. Thiết kế: `docs/plans/2026-11-20-nt548-devops-design.md` (bản 3). Việc theo dõi bằng issue GitHub; số issue (#N) và PR dẫn thẳng tới bằng chứng.

## 1. Ý tưởng đồ án

Đưa TripGuardian lên **AWS Academy Learner Lab** bằng code và vận hành nó như một dịch vụ thật. TripGuardian là ứng dụng lập lịch trình du lịch, gồm web (Node), harness (Python, FastAPI) và các model gọi qua gateway. Chức năng sản phẩm giữ nguyên; đồ án chỉ làm phần vận hành:

- **CI/CD:** test, build image, phát hành blue/green có canary tự rollback.
- **Hạ tầng AWS:** Terraform dựng VPC, ALB, ASG mỗi màu, CloudWatch.
- **DataOps:** release dữ liệu có phiên bản, kiểm trước khi dùng, đổi và lùi như code.
- **AIOps:** phát hiện bất thường bằng ML, gom mẫu log, tóm tắt sự cố từ bằng chứng, đo MTTD / MTTR bằng bơm lỗi.

Ràng buộc của lab định hình kiến trúc: 50 USD mỗi người, không GPU, không tạo được IAM role. Vì vậy:
- LLM giả thay model thật;
- subnet public, không NAT;
- deploy qua self-hosted runner trong lab;
- xóa hạ tầng cuối mỗi buổi.

## 2. Phân công

Bốn khối, hai cặp làm song song, chỉ gặp nhau ở hợp đồng giữa khối (thiết kế §7.1).

| Thành viên | Khối phụ trách | Đã xong | Đang / sẽ làm |
|---|---|---|---|
| LuanLuKim (trưởng nhóm) | T9 CI/CD, T4 AIOps, T7 báo cáo | CI xanh (#1); image + stack một màu (#44); gateway chia trọng số + `/metrics` (#14, #15); phát hiện bất thường (#36); tóm tắt sự cố (#38); kiểm Terraform trong CI (#49) | Stack với harness thật (PR #63, CI xanh, chờ merge); deploy lên AWS (#29, draft #50); báo cáo, slide |
| DontMadWhenBad | T9 CI/CD, T4 AIOps, T6 Kubernetes | LLM giả (#13); blue/green + Nginx (#2); canary tự rollback, k6, scale (#3); mẫu log Drain3 (#37); bơm lỗi, đo MTTD / MTTR (#39); eval gate model (#16); nghiên cứu AIOps (#18); demo kind (#6) | Mẫu log và bơm lỗi trên lab |
| hohoangluan | T5 DataOps | Dữ liệu mẫu (#9); harness thật chạy với dữ liệu mẫu (#8); `data_check` (#10); đổi / lùi release (#11); nghiên cứu DVC, lakeFS, Great Expectations (#12) | Đổi release trên AWS |
| dinhlong06 | T8 AWS | Module mạng: VPC 2 AZ, subnet public, security group (#23); trace LangSmith làm bằng chứng sự cố (#66) | Kiểm quyền lab (#22); ALB (#24); ASG (#25); CloudWatch (#26); bật / tắt + chi phí (#27) |

## 3. Tiến độ: đã làm, đang làm, sẽ làm

Phần trăm là ước lượng theo checklist của issue.

| Khối | Đã làm | Đang làm | Sẽ làm | Ước lượng |
|---|---|---|---|---|
| **T9 CI/CD** (#28) | CI xanh trên checkout sạch; 3 image trên GHCR; blue/green trên Compose + Nginx; canary tự promote / rollback; k6 và bảng scale; kiểm Terraform | Script deploy blue/green qua Terraform, có test với `terraform` / `aws` giả (draft #50) | Deploy thật lên lab qua self-hosted runner (#29) | ~70% |
| **T4 AIOps** (#4) | Chuỗi quan sát → phát hiện → chẩn đoán → hành động chạy đủ trên Compose: `/metrics`, `detect.py`, `log_patterns.py`, `incident.py`, `canary_watch.py`; bảng MTTD / MTTR / báo nhầm (#39); eval gate (#16) | | Chạy trên metric và log thật của lab (cần #24, #26); canary model (#17, không bắt buộc) | ~85% |
| **T5 DataOps** (#5) | Dữ liệu mẫu tổng hợp; gate `data_check`; đổi / lùi release trên harness thật; ghi chú nghiên cứu | | Bước đổi release trên AWS | ~90% |
| **T6 Kubernetes** (#6, điểm cộng) | Manifest + workflow `nt548-k8s-demo` trên kind: đổi màu, scale, tự dựng lại pod | | | 100% |
| **T8 AWS** (#21) | Module mạng, có test | ASG mỗi màu (#25, bản nháp chưa push) | Kiểm quyền lab + bootstrap (#22); ALB (#24); CloudWatch (#26); `aws-up` / `aws-down`, budget (#27) | ~10% |
| **T7 báo cáo** (#7) | Khung `REPORT.md`; các mục CI/CD, AIOps, DataOps có số liệu trong hướng dẫn từng khối | Báo cáo tiến độ này | Mục AWS, chi phí; chuyển số đo của #2, #3, #5 vào `REPORT.md`; slide | ~35% |

Đường găng là **T8**. Mọi việc "sẽ làm" của T9, T4 và T5 đều chờ ALB + ASG chạy thật trên lab.

## 4. Kết quả đo được

Mọi số dưới đây là từ CI hoặc lệnh chạy lại được, không phải ước lượng.

Số của blue/green lấy từ [run 45819985864](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45819985864); canary và scale từ [run 45820052392](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45820052392); kind từ [run 45825947271](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45825947271). Mỗi lần chạy, số dao động nhẹ: qua 6 lần chạy gần nhất, chia 10 % ra 8,6–11 % sang green.

**Phát hành (T9).**

| Kiểm | Kết quả | Chạy lại |
|---|---|---|
| Blue/green: chia 10 % | 9,1 % trên 1.000 người dùng mới sang green; sticky: 0 / 20 người bị đổi màu | workflow `nt548-bluegreen` |
| Blue/green: đổi màu dưới tải | 5.726 request chạy suốt `10 %` → `100 %` → rollback → promote: 0 lỗi kết nối, 0 5xx | như trên |
| Rollback tay | lệnh 0,8 s, 100 % về blue sau thêm 0,1 s | như trên |
| Canary, bản tốt | promote sau 33 s (2 bước 15 s) | `ops/nt548/canary_rehearsal.sh` |
| Canary, bản trả 500 | rollback sau 17 s ở bước 10 %; màu cũ 0 lỗi | như trên |
| Canary, bản chậm 800 ms | rollback sau 16 s vì p95 (803 ms so với 2 ms) | như trên |
| Scale trên một runner 4 vCPU | 1 bản: 386 / 898 / 1.509 req/s ở 20 / 50 / 100 người dùng ảo; 2 bản: 382 / 892 / 1.621. Trên một máy, thêm bản không giúp vì k6, Nginx và hai bản tranh nhau CPU. Scale-out thật cần ASG (#25) | `ops/nt548/scale_bench.sh` |
| Kubernetes (kind) | đổi selector sang green: 20/20 request sang green sau 2 s; rollback 1 s; scale lên 3 pod; xóa một pod thì Deployment tự về 3 pod | workflow `nt548-k8s-demo` |

Hai lỗi lộ ra nhờ đo và đã sửa:
- `nginx -s reload` trả về trước khi worker mới nhận cấu hình, nên ngay sau lệnh chỉ 84,5 % sang green. `deploy.sh` giờ chờ worker mới.
- Script kiểm của demo kind đếm sai câu trả lời (JSON không có xuống dòng cuối). App vẫn đúng; đã sửa script.

**DataOps (T5).**

| Kiểm | Kết quả | Chạy lại |
|---|---|---|
| Harness thật trên dữ liệu mẫu + Postgres | 40/40 nơi của `r-a` tìm được qua `:8080`; journey vẫn mở sau khi restart harness | job `app-real` của `nt548-ci` (PR #63, chờ merge) |
| Đổi release `r-a` → `r-b` rồi lùi | journey cũ vẫn mở khi đổi; màu thiếu release trả 409; lùi lại phục vụ `r-a` | `nt548-data-release`, `candidate=r-b` |
| Release mất 20 % nơi | gate chặn: `40 -> 32 places (20% drop, limit 10%)`, không màu nào lên (job đỏ là đúng) | `nt548-data-release`, `candidate=r-b-drop` |

**AIOps (T4).**

| Kiểm | Kết quả | Chạy lại |
|---|---|---|
| Phát hiện bất thường, 5 kịch bản × 20 chuỗi tổng hợp | ngưỡng tĩnh không bắt được rò rỉ chậm (0/20); Isolation Forest bắt 15/20 | `python ops/nt548/aiops/detect.py compare --seeds 20` |
| Tóm tắt sự cố với LLM thật | 3 sự cố gài, cả 3 chỉ đúng nguyên nhân; câu trả lời không dẫn được bằng chứng bị bỏ | `python ops/nt548/aiops/incident.py demo deploy_500` |
| Eval gate model | bản lỗi 30 % và bản hỏng JSON 50 % bị chặn; bản tốt qua | `python ops/nt548/eval_gate.py` |
| Bơm lỗi trên stack Compose (#39) | xem bảng dưới | workflow `nt548-fault-eval` |

Bơm lỗi trên stack Compose, CI 26/11 ([run 45827111505](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45827111505); 96.522 request trong 22,6 phút, 0 lỗi kết nối). MTTD tính từ lúc bơm lỗi tới khi alarm kêu:

| Kịch bản | Ngưỡng tĩnh / EWMA | Isolation Forest | Mẫu log | Phục hồi | 5xx người dùng thấy |
|---|---|---|---|---|---|
| LLM giả lỗi 30 % | 20 s | không bắt | **15 s** | tay: MTTD + người phản ứng + lệnh 23,5 s | 558 |
| LLM chậm thêm 2 s | 20 s | không bắt | không có dòng lỗi | tay: MTTD + người phản ứng + lệnh 24,9 s | 0 |
| Tắt một bản app | không bắt | không bắt | không bắt | tay, lệnh 11,2 s | 1 |
| Deploy bản trả 500 | 7,9 s | không bắt | **5 s** | **tự động, 21,6 s** (`canary_watch`) | 41 |
| Tải tăng 5 lần | 10 s | không bắt | – | hết tải | 0 |
| 5 phút không lỗi: số báo nhầm | 0 | 0 | 0 | | |

Đọc số (chi tiết ở `REPORT.md` §6.4):
- Tự động rollback cho MTTR 21,6 s và 41 lỗi. Ở ca phục hồi tay, bộ đo giữ lỗi 60 s thay cho lúc người phản ứng. Từ lúc bắt đầu bơm lỗi tới khi phục hồi xong mất 108 s, và người dùng thấy 558 lỗi.
- Mẫu log bắt sớm nhất khi lỗi có dòng log riêng. Lỗi chỉ làm chậm thì chỉ metric bắt được.
- Tắt một bản app chỉ gây 1 lỗi, vì Nginx chuyển sang bản còn lại. Phát hiện máy chết cần health check theo máy, không phải metric 5xx.
- Isolation Forest không bắt được ca nào: nó chỉ học 90 s mà trong đó 5xx toàn là 0. Trên dữ liệu tổng hợp, nó lại là cách duy nhất bắt rò rỉ chậm. Alarm thật dùng `combined` (EWMA hoặc Isolation Forest), nên vẫn bắt mọi ca EWMA bắt.
- Bản chạy đầu tiên lộ một lỗi của chính bộ đo: log của màu green bị xóa trước khi được lưu, nên mẫu log không thấy deploy hỏng. Đã sửa, và số ở trên là của lần chạy sau khi sửa.

## 5. Test case

Test của đồ án nằm trong `tests/nt548`, chạy trong job `lint-test` của `nt548-ci` trên mọi PR. Số dưới đây là của `main` sau khi merge các PR của 26/11 ([run 45851981554](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45851981554): 92 qua, 3 file bỏ qua).

| File test | Kiểm gì | Số test | Qua |
|---|---|---|---|
| `test_llm_fake` | LLM giả: tương thích OpenAI, bơm lỗi / chậm / hỏng JSON theo biến môi trường | 12 | 12 |
| `test_harness_stub` | stub harness báo đúng màu, bơm `NT548_FAULT` | 13 | 13 |
| `test_lb_check` | đo chia %, sticky, đổi màu không rớt request | 5 | 5 |
| `test_canary_watch` | quyết định promote / rollback / chờ theo 5xx và p95 | 11 | 11 |
| `test_detect` | ngưỡng tĩnh, EWMA, Isolation Forest trên chuỗi tổng hợp | 10 | 10 |
| `test_log_patterns` | gom mẫu log, mẫu mới, mẫu lỗi tăng đột biến, đọc CloudWatch Logs | 13 | 13 |
| `test_incident` | nghi phạm đầu tiên đúng (deploy, tải, trace LangSmith); kiểm dẫn chứng của LLM, LLM hỏng thì về mẫu cố định; mở / comment issue | 21 | 21 |
| `test_fault_eval` | chia chuỗi theo ô 5 s; lỗi bị bắt trong vài giây, đoạn không lỗi thì im; MTTR đo được khi tự phục hồi | 3 | 3 |
| `test_eval_gate` | câu trả lời hợp lệ; chặn bản lỗi 30 %, bản hỏng JSON; cho bản tốt qua | 4 | 4 |
| `test_sample_data` | dữ liệu mẫu đủ cho harness | 4 | 4 |
| `test_data_check` | gate release dữ liệu | 7 | 7 |
| `test_data_release` | đổi / lùi release | 4 | 4 |
| **Tổng** | | **107** | **107** |

Ba file cuối cần `lancedb`, nên `nt548-ci` bỏ qua chúng; workflow `test` (môi trường đầy đủ của TripGuardian) chạy cả ba.

Ngoài ra:
- Toàn bộ test của TripGuardian trên `main`: 5.618 qua, 0 đỏ, 434 bỏ qua, 3 phút 40 giây ([run 45827417239](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45827417239)). Đồ án không đổi code sản phẩm, nên con số này là kiểm hồi quy.
- Gateway: 16/16 test qua.
- Terraform: `fmt`, `validate`, `terraform test` qua cho module `network` và `aiops` (workflow `nt548-terraform`).
- Script deploy AWS: 7 test với `terraform` / `aws` giả (draft #50, chưa merge).

## 6. Chỉ số DevOps

Tính từ 20/11 (ngày nhận repo) đến 22:45 ngày 26/11 (lúc merge #70), lấy từ GitHub API. Dữ liệu thô của mọi bảng trong báo cáo nằm ở `data/` (CSV).

**Luồng thay đổi.**

| Chỉ số | Giá trị | Ghi chú |
|---|---|---|
| PR đã merge | 35: LuanLuKim 20, DontMadWhenBad 7, hohoangluan 6, dinhlong06 2 | Còn mở: #64 (báo cáo này), #63, #59, draft #50 |
| Thời gian từ lúc mở PR tới lúc merge | trung vị 0,36 giờ; 90 % PR dưới 32 giờ | PR nhỏ, mỗi PR một việc, merge khi CI xanh |
| Số PR merge vào `main` theo ngày | 21/11: 13; 23/11: 4; 24/11: 9; 25/11: 2; 26/11: 7 | |
| Lượt chạy workflow xong | 177: 149 xanh (84 %), 24 đỏ, 4 hủy | |
| `main` bị đỏ | 1 lần: workflow `test` ngày 21/11, trước khi CI chạy được trên checkout sạch (#1). Xanh lại sau 5 giờ; từ đó `main` luôn xanh | |
| Phát hành | 10 lần build image lên GHCR từ `main`. Chưa deploy lên AWS | Deploy thật chờ T8 (#24, #25, #29) |

**Theo workflow.**

| Workflow | Kiểm gì | Xanh / tổng | Trên `main` | Thời gian (trung vị) |
|---|---|---|---|---|
| `test` | toàn bộ test TripGuardian | 77 / 93 | 25 / 29 | 5,5 phút |
| `nt548-ci` | lint, `tests/nt548`, stack Compose (stub và harness thật) | 37 / 40 | 12 / 12 | 2,5 phút |
| `nt548-images` | build 3 image lên GHCR | 10 / 12 (2 hủy) | 10 / 12 | 1,3 phút |
| `nt548-bluegreen` | chia %, sticky, đổi màu dưới tải | 11 / 14 (1 đỏ là lỗi reload, đã sửa; 2 hủy) | 3 / 5 | 8,0 phút |
| `nt548-data-release` | đổi / lùi release dữ liệu | 4 / 7 (1 đỏ cố ý: gate chặn `r-b-drop`; 2 lượt 0 giây không chạy job nào) | | 1,9 phút |
| `nt548-terraform` | `fmt`, `validate`, `terraform test` | 4 / 4 | 2 / 2 | 0,7 phút |
| `nt548-fault-eval` | bơm lỗi, đo MTTD / MTTR | 3 / 3 | | 27,1 phút |
| `nt548-k8s-demo` | demo kind | 1 / 2 (1 đỏ do script kiểm đếm sai, đã sửa) | | 3,1 phút |
| `nt548-incident` | tóm tắt sự cố, mở issue | 2 / 2 | | 0,6 phút |

**Vận hành** (chi tiết ở §4; đo trên Compose, chưa phải trên AWS).

| Chỉ số | Giá trị |
|---|---|
| Rollback tay blue/green | lệnh 0,8 s, 100 % về blue sau thêm 0,1 s |
| Canary tự rollback | 17 s với bản trả 500, 16 s với bản chậm 800 ms |
| MTTD nhanh nhất | 5 s (mẫu log, deploy bản trả 500); metric: 7,9–20 s |
| MTTR | tự động 21,6 s, 41 lỗi người dùng thấy; tay (bộ đo giữ lỗi 60 s thay cho người) 108 s, 558 lỗi |
| Báo nhầm | 0 trong 5 phút không lỗi (bằng chứng còn yếu, xem §4) |

## 7. Kế hoạch tới 04/12

| Ngày | Việc | Người |
|---|---|---|
| 27/11 | Kiểm quyền `LabRole` (R2) + bootstrap (#22). Quyết định: dựng ALB + ASG trên lab hay chuyển dự phòng | dinhlong06, LuanLuKim |
| 28–29/11 | ALB blue/green (#24), ASG mỗi màu (#25) với image thật; mount dữ liệu mẫu vào máy app | dinhlong06, hohoangluan |
| 30/11 | Deploy blue/green có canary qua `nt548-deploy-aws` (#29); k6 vào URL ALB, bảng scale-out 1 → 3 máy | LuanLuKim, DontMadWhenBad |
| 01/12 | CloudWatch dashboard + alarm + log (#26); AIOps trên metric và log thật; đổi release dữ liệu trên AWS | dinhlong06, DontMadWhenBad, hohoangluan |
| 02/12 | `aws-up` / `aws-down`, budget, bảng chi phí (#27) | dinhlong06 |
| 02–03/12 | Báo cáo, slide; chạy demo hai lần từ đầu (`aws-up` → demo → `aws-down`) | cả nhóm |
| 04/12 | Nộp | |

Mốc dự phòng: nếu đến hết 29/11 ALB + ASG chưa chạy được trên lab, chuyển sang stack Compose trên một máy + Cloudflare Tunnel. Stack này đã chạy đủ blue/green, canary và bơm lỗi trong CI.

## 8. Rủi ro

| Rủi ro | Ảnh hưởng | Cách xử lý |
|---|---|---|
| Hạ tầng AWS chậm hơn lịch: kế hoạch 24/11 hẹn ALB + ASG ngày 25–27/11, tới 26/11 mới có module mạng | Deploy thật, monitoring, phần AWS của DataOps và AIOps đều chờ T8 | T8 là việc đầu tiên của cả nhóm từ 27/11. Các phần chờ T8 đã viết sẵn và kiểm bằng mock / Compose, nên lên lab chỉ còn bước `apply` |
| `LabRole` thiếu quyền (R2) | Một số tài nguyên không tạo được | Kiểm quyền ngày 27/11 (#22); thiếu thì thay bằng phương án lab cho phép (thiết kế §5.2) |
| Không kịp chạy trên AWS | Mất phần hạ tầng cloud và scale-out | Mốc dự phòng 29/11 ở §7. Token và account Cloudflare đã thử, dùng được |
| Credential lab hết hạn theo phiên | Workflow deploy dừng giữa chừng | Deploy qua runner trong lab với `LabInstanceProfile`, không giữ key |
| Số đo trên một runner không đại diện cho scale thật | Bảng scale hiện tại không cho thấy lợi ích của thêm máy | Đo lại trên ASG (#25); bảng hiện tại ghi rõ là cùng một máy |

## 9. Dữ liệu

Dữ liệu thô của các bảng nằm trong `data/`. Các file là CSV, mã hóa UTF-8, mở được bằng Excel.

| File | Nội dung | Dùng cho |
|---|---|---|
| `members.csv` | khối phụ trách, số PR đã merge, số commit trên `main` của từng thành viên | §2 |
| `prs_merged.csv` | từng PR đã merge: tác giả, giờ mở, giờ merge, số giờ chờ | §6 |
| `prs_per_day.csv` | số PR merge mỗi ngày | §6 |
| `workflow_runs.csv` | từng lượt chạy workflow: kết quả, thời gian, link | §6 |
| `workflow_summary.csv` | tổng hợp theo workflow | §6 |
| `tests_nt548.csv` | số test theo file | §5 |
| `bluegreen.csv`, `canary.csv`, `scale.csv`, `k8s_kind.csv` | kết quả phát hành | §4 |
| `data_release.csv` | đổi / lùi release dữ liệu, gate chặn release hỏng | §4 |
| `fault_eval.csv`, `fault_false_alarms.csv` | bơm lỗi: MTTD theo cách phát hiện, phục hồi, lỗi người dùng thấy, báo nhầm | §4, §6 |
| `detect_compare.csv` | so sánh bốn cách phát hiện trên chuỗi tổng hợp | §4 |

Các file kết quả đo có cột `run_id`; `workflow_runs.csv` có cả link, để đối chiếu với run trên GitHub Actions. Số tính tới 22:45 ngày 26/11.

`MIDTERM.html` là cùng nội dung này, dạng trang web, có thêm biểu đồ. Mở trực tiếp bằng trình duyệt, không cần mạng.

