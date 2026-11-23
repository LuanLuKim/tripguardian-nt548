# Báo cáo đồ án NT548, nhóm 8: vận hành TripGuardian

> Khung báo cáo (T7, #7). Mỗi người viết mục của các issue mình làm, kèm lệnh chạy lại được và số đo thật. Cách ghép báo cáo: `07-sync-report.md`.

## 1. Bài toán và kiến trúc tổng

_LuanLuKim._

**Sản phẩm.** TripGuardian lập lịch trình du lịch cá nhân hóa: web (Node), harness (Python, FastAPI), các model gọi qua `scripts/model_gateway.py`. Đồ án **không đổi chức năng sản phẩm**. Đồ án chỉ làm phần vận hành: đưa sản phẩm lên AWS bằng code, phát hành an toàn, theo dõi, và dùng AI / ML để vận hành (AIOps).

**Ràng buộc định hình kiến trúc** (AWS Academy Learner Lab, `us-east-1`):

| Ràng buộc | Hệ quả |
|---|---|
| 50 USD mỗi thành viên, không GPU | Model thật được thay bằng `llm-fake` tương thích OpenAI. Hạ tầng tắt cuối mỗi buổi (`nt548-aws-down`) |
| Không tạo được IAM role / OIDC provider | GitHub không giữ key AWS. Deploy chạy trên **self-hosted runner** trong lab, dùng `LabInstanceProfile` |
| Tiền NAT Gateway | VPC 2 AZ chỉ có subnet public. Security group chỉ cho ALB → app → Postgres |
| Repo public | Image public trên GHCR; không secret, dữ liệu thật hay credential nào trong repo |

**Kiến trúc.** Chi tiết ở thiết kế bản 3 (`docs/plans/2026-11-20-nt548-devops-design.md` §5).

```mermaid
flowchart LR
  PR["PR"] --> CI["test.yml + nt548-ci<br/>(runner GitHub)"]
  CI -->|merge main| IMG["nt548-images<br/>GHCR :sha"]
  IMG --> DEP["nt548-deploy-aws<br/>(runner self-hosted trong lab)"]
  DEP -->|terraform apply| ALB["ALB: blue / green theo trọng số"]
  ALB --> B["ASG blue"] & G["ASG green"]
  CW["CloudWatch metric + log"] --> AI["AIOps: phát hiện bất thường,<br/>tóm tắt sự cố → issue"]
  ALB & B & G -.-> CW
```

**Chia việc** (thiết kế §7): bốn khối, hai cặp làm song song, chỉ gặp nhau ở hợp đồng giữa khối (§7.1).
- hohoangluan + dinhlong06: hạ tầng AWS (T8) và DataOps (T5).
- LuanLuKim + DontMadWhenBad: CI/CD (T9) và AIOps (T4).

## 2. Hạ tầng AWS bằng Terraform (T8, #21)

_hohoangluan, dinhlong06._ VPC, subnet, security group, máy ops + self-hosted runner, giới hạn của Learner Lab (bảng quyền R2).

## 3. Load balancer và scalability (T8, #21)

_hohoangluan, dinhlong06._ ALB + target group blue/green, ASG + target tracking, số đo scale-out.

## 4. CI/CD và phát hành (T9, #28)

_LuanLuKim, DontMadWhenBad._ Hướng dẫn chi tiết: `01-ci-cd.md`. Phần của DontMadWhenBad (blue/green trên Compose + Nginx, canary tự rollback, k6) ghi tiếp ở đây khi xong.

**4.1 CI xanh (#1, LuanLuKim).**
- Lúc nhận repo, `test.yml` đỏ trên checkout sạch: thiếu dependency, và có test cần dữ liệu chỉ có trên máy prod (bị `.gitignore`).
- Sửa (#31, #42):
  - thêm dependency;
  - test thiếu file đầu vào thì tự skip;
  - marker `corpus` skip khi thiếu `data/snapshot/current`.
  Không đổi code sản phẩm.
- Kết quả: run của PR #47 (21/11) có `pytest` 5.542 qua, 0 đỏ, 433 skip trong 3 phút 46 giây; job `web` (type check + build) 23 giây.

**4.2 Image và stack một màu (#2, draft #44).**
- `harness.Dockerfile`, `web.Dockerfile`, `ops/nt548/compose/app.yml` chạy cả stack một màu trên một máy, cổng `8080`.
- `nt548-ci` có job `app-smoke`: build 3 image, chạy `app.yml`, kiểm `GET /` trả 200. Job cũng kiểm stub báo đúng màu, gateway trả lời qua LLM giả, và image không chứa `.env` / `data/`.
- `nt548-images` đẩy `:sha` lên GHCR sau mỗi merge.
- Chờ DontMadWhenBad review.

**4.3 Deploy lên AWS (#29, draft #50).** `nt548-deploy-aws` gọi `ops/nt548/deploy_aws.sh`. Script chỉ thay đổi AWS qua `terraform apply` của `envs/demo`, theo hợp đồng với T8.

| Bước | Trọng số màu cũ / màu mới | Sang bước sau khi |
|---|---|---|
| Màu rảnh nhận image `:sha` | 100 / 0 | mọi target `healthy` |
| Canary | 90 / 10 | `canary_watch` (#3) qua |
| Promote | 0 / 100 | màu cũ giữ sha cũ để lùi |
| Canary hỏng | 100 / 0 | dừng, job đỏ |

- Rollback tay chỉ đổi trọng số.
- Workflow không có trigger `pull_request`, nên code của PR không chạy trên runner self-hosted.
- Workflow chỉ chạy khi admin bật `NT548_DEPLOY_ENABLED`. Dự phòng khi runner hỏng: chạy trên runner GitHub với credential tạm trong Environment `nt548-aws`.
- 7 test chạy script với `terraform` / `aws` giả: thứ tự trọng số, màu hỏng không nhận traffic, canary hỏng thì lùi, tag lạ bị từ chối.
- Chưa chạy thật: cần runner, ALB và `envs/demo` của T8.

**4.4 Kiểm Terraform trong CI (draft #49).** Workflow `nt548-terraform` chạy `fmt -check`, `validate` và `terraform test` (provider giả) cho mọi module trong `ops/nt548/terraform`, kể cả module của T8 khi thêm vào.

**Còn đo:** thời gian rollback tay trên lab (mục tiêu < 1 phút), k6 không rớt request khi đổi màu (#3).

## 5. Monitoring (T8, #21)

_hohoangluan, dinhlong06._ Dashboard, alarm, log; ảnh chụp một alarm bắn thật.

## 6. AI ops (T4, #4)

_LuanLuKim, DontMadWhenBad._ Hướng dẫn chi tiết: `04-aiops.md`.
- **AI ops của đồ án là AIOps** (chủ dự án chốt 21/11): dùng AI / ML để vận hành hệ thống, theo chuỗi quan sát → phát hiện → chẩn đoán → hành động.
- LLMOps (eval gate #16, canary model #17) không bắt buộc.
- Phần của DontMadWhenBad ghi tiếp ở đây khi xong: mẫu log Drain3 (#37), bơm lỗi và đo MTTD / MTTR (#39).

**6.1 Quan sát (#14, #15, đã merge).**
- `model_gateway` chia luồng theo trọng số `URL@weight`.
- Endpoint `/metrics` (Prometheus) đếm request theo upstream và mã trả về, đo histogram độ trễ, báo trạng thái cooldown và trọng số.
- 16/16 test của gateway qua.

**6.2 Phát hiện bất thường (#36, `detect.py` đã merge, module AWS ở draft #49).** Bốn cách trên cùng chuỗi:
- ngưỡng tĩnh, như người vận hành đặt tay;
- EWMA z-score;
- Isolation Forest, trên giá trị, độ thay đổi, độ lệch so với trung bình trượt, và pha chu kỳ;
- `combined`: EWMA hoặc Isolation Forest.

Chạy lại bằng `python ops/nt548/aiops/detect.py compare --seeds 20`. Mỗi kịch bản có 20 chuỗi tổng hợp:

| Kịch bản | Ngưỡng tĩnh | EWMA | Isolation Forest | `combined` |
|---|---|---|---|---|
| Gai lớn (`spike`) | 18 / 20 | **20 / 20** | 16 / 20, 6 báo nhầm | **20 / 20**, 6 báo nhầm |
| Rò rỉ chậm (`drift`) | 0 / 20 | 0 / 20 | **15 / 20** (trễ ~117 điểm) | **15 / 20** |
| Gai dưới đỉnh chu kỳ (`seasonal_spike`) | 0 / 20 | 0 / 20 | **16 / 20**, 3 báo nhầm | **16 / 20** |
| Tăng nền +60 (`level_shift`) | 0 / 20 | **20 / 20** | 17 / 20 | **20 / 20** |
| Không lỗi (`quiet`): số báo nhầm | 0 | 0 | 6 | 6 |

Kết luận trên dữ liệu tổng hợp:
- Ngưỡng tĩnh chỉ bắt được gai lớn.
- EWMA nhanh và không báo nhầm, nhưng tự thích nghi theo rò rỉ chậm nên bỏ sót nó.
- Isolation Forest là cách duy nhất bắt được rò rỉ chậm và gai nằm trong chu kỳ. Cái giá là khoảng 6 lần báo nhầm trên 20 chuỗi.
- Trên AWS, module Terraform `modules/aiops` tạo alarm CloudWatch Anomaly Detection (dải dự báo do CloudWatch học) cho p95 độ trễ, 5xx và số request theo từng target group.
- Giới hạn: ALB bị xóa mỗi buổi, nên metric mới chưa có lịch sử và dải của CloudWatch kém tin cậy trong những giờ đầu. Vì vậy so sánh trên lab dựa vào `detect.py`.

**6.3 Chẩn đoán và hành động: tóm tắt sự cố (#38, PR #48).** `incident.py` gom bằng chứng và đánh số E1…En:
- alarm;
- metric trước và sau alarm;
- detector nào bắt;
- mẫu log tăng;
- deploy trong 30 phút trước alarm.

Sau đó `incident.py` mở một issue nhãn `incident` cho mỗi alarm; alarm lặp lại thì comment vào issue đó.

Rủi ro chính của LLM trong xử lý sự cố là **bịa nguyên nhân**. Cách giảm:
- LLM chỉ nhận danh sách bằng chứng.
- Mỗi giả thuyết phải dẫn mã bằng chứng có thật. Không đạt thì bỏ cả câu trả lời và dùng luật cố định; issue ghi rõ lý do.
- Lệnh gợi ý chỉ lấy từ luật cố định và không bao giờ tự chạy.

Ba sự cố tổng hợp cho đúng nguyên nhân đã gài:

| Sự cố gài | Giả thuyết đầu tiên | Lệnh gợi ý |
|---|---|---|
| Deploy hỏng, 5xx tăng 32 lần | deploy `a1b2c3d` 7 phút trước alarm (high) | rollback qua `nt548-deploy-aws` |
| LLM chậm, deploy cũ 3 giờ trước | mẫu log timeout của gateway; không đổ lỗi deploy cũ | đọc `/metrics` của gateway |
| Tải tăng 4 lần, không deploy | tải tăng, không phải đổi code | kiểm hoạt động scale của ASG |

**Còn lại:**
- chạy trên metric thật của lab (cần ALB của T8);
- mẫu log thật (#37);
- bảng MTTD / MTTR / báo nhầm khi bơm lỗi thật (#39).

**LLMOps khác AIOps ở đâu** (ghi tiếp ở #18): AIOps dùng ML để vận hành *hệ thống*. LLMOps vận hành chính *model*: đánh giá phiên bản, canary model, theo dõi chất lượng câu trả lời.

## 7. DataOps (T5, #5)

_hohoangluan, dinhlong06._ Dữ liệu mẫu, `data_check`, đổi / lùi release dữ liệu; so sánh với DVC, Great Expectations, lakeFS.

## 8. Chi phí

Bảng chi tiêu Learner Lab theo buổi, tổng tới ngày nộp, ảnh Budget.

## 9. Hạn chế và hướng mở rộng

Kubernetes, Cloudflare, deploy kéo (GitOps), dữ liệu và model thật.
