# Báo cáo đồ án NT548, nhóm 8: vận hành TripGuardian

> Khung báo cáo (T7, #7). Mỗi người viết mục của các issue mình làm, kèm lệnh chạy lại được và số đo thật. Cách ghép báo cáo: `07-sync-report.md`.

## 1. Bài toán và kiến trúc tổng

_LuanLuKim._ Sản phẩm, phạm vi đồ án, kiến trúc trên AWS Learner Lab, lý do chọn (thiết kế bản 3: `docs/plans/2026-11-20-nt548-devops-design.md`).

## 2. Hạ tầng AWS bằng Terraform (T8, #21)

_hohoangluan, Đình Long._ VPC, subnet, security group, máy ops + self-hosted runner, giới hạn của Learner Lab (bảng quyền R2).

## 3. Load balancer và scalability (T8, #21)

_hohoangluan, Đình Long._ ALB + target group blue/green, ASG + target tracking, số đo scale-out.

## 4. CI/CD và phát hành (T9, #28)

_LuanLuKim, Quỳnh._ Pipeline từ PR tới AWS, image theo sha, blue/green, canary tự rollback, rollback tay, số đo k6.

## 5. Monitoring (T8, #21)

_hohoangluan, Đình Long._ Dashboard, alarm, log; ảnh chụp một alarm bắn thật.

## 6. AI ops (T4, #4)

_LuanLuKim, Quỳnh._ LLM giả, chia luồng model theo trọng số, `/metrics`, eval gate, canary model; MLOps / LLMOps khác DevOps ở đâu.

## 7. DataOps (T5, #5)

_hohoangluan, Đình Long._ Dữ liệu mẫu, `data_check`, đổi / lùi release dữ liệu; so sánh với DVC, Great Expectations, lakeFS.

## 8. Chi phí

Bảng chi tiêu Learner Lab theo buổi, tổng tới ngày nộp, ảnh Budget.

## 9. Hạn chế và hướng mở rộng

Kubernetes, Cloudflare, deploy kéo (GitOps), dữ liệu và model thật.
