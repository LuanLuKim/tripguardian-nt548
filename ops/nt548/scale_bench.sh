#!/usr/bin/env bash
# Scale numbers of docs/nt548/03-canary-scale.md: the same k6 journey against 1 and then 2 replicas of blue behind
# nginx, at each VU count. Images ghcr.io/luanlukim/tripguardian-nt548/*:<TAG> must exist locally. Markdown to $SUMMARY.
#
#   TAG=new VUS="20 50 100" DURATION=20s ops/nt548/scale_bench.sh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
D="$ROOT/ops/nt548/deploy.sh"
TAG=${TAG:-new}
VUS=${VUS:-20 50 100}
DURATION=${DURATION:-20s}
REPLICAS=${REPLICAS:-1 2}
export NT548_STATE=${NT548_STATE:-$ROOT/ops/nt548/state}
WORK=$(mktemp -d); chmod 777 "$WORK"
SUMMARY=${SUMMARY:-/dev/stdout}
rows=()

"$D" lb
for n in $REPLICAS; do
  "$D" up blue "$TAG" "$n"
  for v in $VUS; do
    docker run --rm --network host -v "$ROOT/ops/nt548/load:/s:ro" -v "$WORK:/out" grafana/k6:0.54.0 run --quiet \
      -e BASE=http://127.0.0.1:${LB_PORT:-8080} -e VUS="$v" -e DURATION="$DURATION" \
      --summary-export "/out/r$n-v$v.json" /s/journey.js > /dev/null
    rows+=("$(python3 - "$WORK/r$n-v$v.json" "$n" "$v" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))["metrics"]
d, f, r = m["http_req_duration"], m["http_req_failed"], m["http_reqs"]
print(f"| {sys.argv[2]} web + {sys.argv[2]} harness | {sys.argv[3]} | {d['med']:.1f} | {d['p(95)']:.1f} | "
      f"{100 * f['value']:.2f} | {r['rate']:.0f} |")
PY
)")
    echo "${rows[-1]}"
  done
done

{
  echo "### Scale on one runner (stub harness, nginx, k6 journey, $DURATION per row)"
  echo
  echo "Machine: $(nproc) vCPU, $(awk '/MemTotal/ {printf "%.1f GB", $2 / 1048576}' /proc/meminfo) RAM; k6 runs on the same machine."
  echo
  echo "| Replicas | VUs | p50 ms | p95 ms | errors % | req/s |"
  echo "|---|---|---|---|---|---|"
  printf '%s\n' "${rows[@]}"
} >> "$SUMMARY"
