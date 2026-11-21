# 06. Demo Kubernetes bằng `kind` trong CI (T6, DontMadWhenBad)

Phần điểm cộng, làm sau khi 02 chạy. Thiếu thời gian thì bỏ, không ảnh hưởng phần chính.

Đọc xong làm được: một workflow dựng cluster `kind` trên runner GitHub, chạy blue/green bằng đổi `selector` của Service, scale bằng `kubectl scale`, rồi tự xóa cluster.

## Vì sao chỉ trong CI

Không có server, không có quota cloud. `kind` dựng cluster trong Docker của runner, mất khi job xong, không tốn tiền. Cùng ý tưởng với Compose (02): hai bản, đổi traffic, lùi; khác công cụ.

## Manifest

```mermaid
flowchart LR
  S["Service web<br/>selector: app=web, color=blue"] --> DB["Deployment web-blue<br/>image :sha-cũ"]
  S -. đổi selector .-> DG["Deployment web-green<br/>image :sha-mới"]
  DB & DG --> HS["Service harness-{color}"] --> HD["Deployment harness-{color}"]
```

`ops/nt548/k8s/` viết YAML thẳng, không Helm, không Argo Rollouts (dễ đọc khi vấn đáp):

| File | Nội dung |
|---|---|
| `postgres.yaml` | StatefulSet 1 bản + Service |
| `web-blue.yaml`, `web-green.yaml` | Deployment, nhãn `color`, `readinessProbe` |
| `harness-blue.yaml`, `harness-green.yaml` | Deployment + Service theo màu (hoặc stub nếu 05 R1 không qua) |
| `web-service.yaml` | Service `web`, `selector.color` là chỗ đổi màu |

## Workflow `nt548-k8s-demo.yml`

`workflow_dispatch` + hằng tuần. Bước: `helm/kind-action` → `kind load docker-image` (image từ GHCR) → `kubectl apply` → chờ `rollout status` → kiểm `curl` qua `port-forward` trả `X-Color: blue` → `kubectl patch service web -p '{"spec":{"selector":{"color":"green"}}}'` → kiểm `green` → patch lại `blue` (rollback) → `kubectl scale deployment web-blue --replicas=3` → kiểm 3 pod Ready.

## Nghiên cứu ghi vào báo cáo

So Compose với K8s ở: khai báo trạng thái mong muốn, tự khởi động lại pod, readiness, scale. Vì sao nhóm không dùng K8s để chạy thật (một máy, GPU dùng chung, không quota). Argo Rollouts làm canary thế nào (chỉ mô tả).

## Xong khi

Workflow xanh, log có đủ ba lần đổi màu và lần scale.
