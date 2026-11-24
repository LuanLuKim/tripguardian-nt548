# Báo cáo tiến độ giữa kỳ NT548, nhóm 8 (27/11/2026)

> Tình trạng đồ án đến ngày 24/11, kèm bằng chứng chạy lại được và kế hoạch tới hạn nộp **04/12/2026**. Báo cáo cuối kỳ: `REPORT.md`. Thiết kế: `docs/plans/2026-11-20-nt548-devops-design.md` (bản 3).

## 1. Đồ án làm gì

Đưa TripGuardian (web Node, harness Python, các model gọi qua gateway) lên **AWS Academy Learner Lab** bằng code. Chức năng sản phẩm giữ nguyên; đồ án chỉ làm phần vận hành:

- **CI/CD:** test, build image, phát hành blue/green có canary.
- **Hạ tầng AWS:** Terraform dựng VPC, ALB, ASG mỗi màu, CloudWatch.
- **DataOps:** release dữ liệu có phiên bản, kiểm trước khi dùng, đổi và lùi như code.
- **AIOps:** phát hiện bất thường bằng ML, tóm tắt sự cố từ bằng chứng.

Ràng buộc của lab định hình kiến trúc: 50 USD mỗi người, không GPU, không tạo được IAM role. Vì vậy dùng LLM giả thay model thật, subnet public không NAT, deploy qua self-hosted runner trong lab, và xóa hạ tầng cuối mỗi buổi.

## 2. Tiến độ theo khối

Phần trăm là ước lượng theo checklist của issue.

| Khối | Đã xong | Còn lại | Ước lượng |
|---|---|---|---|
| **T5 DataOps** (#5) | Dữ liệu mẫu tổng hợp do chính pipeline TripGuardian dựng (#9); harness thật chạy với dữ liệu mẫu (#8); `data_check` chặn release hỏng (#10); diễn tập đổi / lùi release trên harness thật (#11); nghiên cứu DVC, lakeFS, Great Expectations (#12) | Bước đổi release trên AWS (cần ALB, ASG) | ~90% |
| **T4 AIOps** (#4) | Gateway chia luồng theo trọng số + `/metrics` (#14, #15); `detect.py`: ngưỡng tĩnh, EWMA, Isolation Forest (#36); module alarm CloudWatch Anomaly Detection (#36); tóm tắt sự cố từ bằng chứng, thử với hai LLM thật (#38); LLM giả để bơm lỗi (#13) | Mẫu log Drain3 (#37); bơm lỗi và đo MTTD / MTTR (#39); chạy trên metric thật của lab | ~55% |
| **T9 CI/CD** (#28) | CI xanh trên checkout sạch (#1); ba image trên GHCR, `app.yml` chạy cả stack một màu (#44), với harness thật trên dữ liệu mẫu (PR #63); kiểm Terraform trong CI; script deploy blue/green qua Terraform có test (draft #50) | Blue/green + Nginx trên Compose (#2); canary tự rollback + k6 (#3); deploy thật lên lab (#29) | ~40% |
| **T8 AWS** (#21) | Module mạng: VPC 2 AZ, subnet public, security group từng tầng, có test (PR #62) | Kiểm quyền lab + bootstrap (#22); ALB blue/green (#24); ASG (#25); CloudWatch (#26); bật / tắt + chi phí (#27) | ~10% |
| **T7 báo cáo** (#7) | Khung `REPORT.md`, các mục DataOps, AIOps, CI/CD đã có số liệu | Mục AWS, chi phí, slide | ~30% |

## 3. Bằng chứng chạy được

| Kiểm | Kết quả | Chạy lại |
|---|---|---|
| Toàn bộ test của TripGuardian trên checkout sạch | 5.579 qua, 0 đỏ, 433 skip, 4 phút 47 giây ([run](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45369735145)) | workflow `test` |
| Stack một màu từ image của commit | `GET /` 200 trên `:8080`, gateway trả lời qua LLM giả, image không chứa `.env` / `data/` | job `app-smoke` của `nt548-ci` |
| Stack một màu với **harness thật** trên dữ liệu mẫu + Postgres | Harness lên sau 5 s; 40/40 nơi của `r-a` tìm được qua `:8080`, 3 nơi chỉ `r-b` có đều vắng; journey tạo ra vẫn mở được sau khi restart harness ([run](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45372351063), PR #63). Đây là đúng stack sẽ chạy trên máy EC2, chỉ thiếu ALB | job `app-real` của `nt548-ci` |
| Đổi release dữ liệu `r-a` → `r-b` rồi lùi, trên harness thật | Journey cũ vẫn mở khi đổi; màu thiếu release trả 409; lùi lại phục vụ `r-a` ([run](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45363252602)) | `nt548-data-release`, `candidate=r-b` |
| Release mất 20 % nơi | Gate chặn: `40 -> 32 places (20% drop, limit 10%)`, không màu nào lên ([run](https://github.com/LuanLuKim/tripguardian-nt548/actions/runs/45371363748); job đỏ là đúng) | `nt548-data-release`, `candidate=r-b-drop` |
| Phát hiện bất thường, 5 kịch bản × 20 chuỗi | Ngưỡng tĩnh không bắt được rò rỉ chậm (0/20); Isolation Forest bắt 15/20 | `python ops/nt548/aiops/detect.py compare --seeds 20` |
| Tóm tắt sự cố với LLM thật | Ba sự cố gài, cả ba chỉ đúng nguyên nhân. `gpt-6.1-sol` 3/3 câu trả lời qua kiểm bằng chứng; `llama-3.3-70b` (Workers AI) 10/10 sau khi sửa | `python ops/nt548/aiops/incident.py demo deploy_500` |
| Terraform không cần tài khoản AWS | `fmt`, `validate`, `terraform test` qua cho module `network`, `aiops` | workflow `nt548-terraform` |

## 4. Kế hoạch tới 04/12

| Ngày | Việc |
|---|---|
| 25–27/11 | Kiểm quyền lab (R2) và bootstrap; ALB + ASG với image giữ chỗ; mạng + ALB chạy thật trên lab |
| 28/11 | Ghép: image thật sau ALB thật, dữ liệu mẫu mount vào máy app |
| 29/11–01/12 | Deploy blue/green có canary qua `nt548-deploy-aws`; dashboard + alarm CloudWatch; đổi release dữ liệu trên AWS; bơm lỗi, đo MTTD / MTTR |
| 02–03/12 | Báo cáo, slide, chạy demo hai lần từ đầu (`aws-up` → demo → `aws-down`) |
| 04/12 | Nộp |

## 5. Rủi ro

| Rủi ro | Ảnh hưởng | Cách xử lý |
|---|---|---|
| Hạ tầng AWS chậm hơn lịch (mới có module mạng) | Deploy, monitoring, phần AWS của DataOps và AIOps đều chờ ALB + ASG | Ưu tiên #22, #24, #25 trước mọi việc khác; module viết sẵn và kiểm bằng mock, nên lên lab chỉ còn bước `apply` |
| `LabRole` thiếu quyền (R2) | Một số tài nguyên không tạo được | Kiểm quyền trước (#22); thiếu thì thay bằng phương án lab cho phép (thiết kế §5.2) |
| Không kịp chạy trên AWS | Mất phần hạ tầng cloud và scaling | Dự phòng: stack Compose trên một máy + Cloudflare Tunnel. Đã thử: token và account Cloudflare dùng được |
| Credential lab hết hạn theo phiên | Workflow deploy dừng giữa chừng | Deploy qua runner trong lab với `LabInstanceProfile`, không giữ key |
