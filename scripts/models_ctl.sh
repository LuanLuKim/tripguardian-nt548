#!/bin/bash
# Start / stop the self-hosted models (docs/LLM_PROVIDER.md §Host model tự chạy).
#   scripts/models_ctl.sh start [clef|gemma|gateway|all]   (default all)
#   scripts/models_ctl.sh stop  [clef|gemma|gateway|all]
#   scripts/models_ctl.sh status
# clef = one nf4 replica per "gpu:port" in CLEF_REPLICAS (default "4:30011"; add e.g. "6:30012" for more req/s), gateway :30000
# balances them. gemma is off since 2026-10-29 (shared GPUs); "all" = clef + gateway. Logs: logs/clef, logs/gemma.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export HF_HOME="$ROOT/.cache/hf" TMPDIR="$ROOT/.cache/tmp"
mkdir -p logs/clef logs/gemma "$TMPDIR"
CLEF_REPLICAS="${CLEF_REPLICAS:-4:30011}"

pattern() {
  # bracket trick: the pattern does not match this script's own command line
  case "$1" in
    clef) echo '[s]cripts/clef_server.py' ;;
    gemma) echo '[l]lama-conda/pkg/bin/llama-server' ;;
    gateway) echo '[s]cripts/model_gateway.py' ;;
    vllm) echo '[.]venv-vllm/bin/vllm serve' ;;
  esac
}

start() {
  case "$1" in
    clef)
      # nf4 + fp16 accumulation + batched forwards: 0.26 s alone, ~5 req/s per replica (docs/LLM_PROVIDER.md)
      for replica in $CLEF_REPLICAS; do
        gpu="${replica%%:*}" port="${replica##*:}"
        curl -s -m 2 "http://127.0.0.1:$port/health" >/dev/null && { echo "clef :$port already up"; continue; }
        CUDA_VISIBLE_DEVICES="$gpu" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True nohup .venv/bin/python scripts/clef_server.py \
          --model Cloudflare/clef-flash --host 127.0.0.1 --port "$port" --quant nf4 --gib-per-gpu 10.2 --max-length 8192 \
          --max-batch-tokens 4096 > "logs/clef/server_nf4_gpu$gpu.log" 2>&1 &
      done ;;
    gemma)
      # live recipe (2026-10-29): Q4_0 on GPUs 4,7, 8 slots x 8192, q8_0 KV, GPU 4 carries less (a foreign process may sit on it)
      GEMMA_GPUS="${GEMMA_GPUS:-4,7}" GEMMA_QUANT="${GEMMA_QUANT:-Q4_0}" GEMMA_NP="${GEMMA_NP:-8}" GEMMA_CTX="${GEMMA_CTX:-65536}" \
      GEMMA_EXTRA="${GEMMA_EXTRA:--ctk q8_0 -ctv q8_0 -ts 40,60}" nohup scripts/gemma_server.sh > logs/gemma/server.log 2>&1 & ;;
    vllm)
      # NOT started by "all": needs the same GPUs as gemma (VLLM_GPUS, default 4,7), see docs/LLM_PROVIDER.md
      mkdir -p logs/vllm
      nohup scripts/vllm_server.sh > logs/vllm/server.log 2>&1 < /dev/null & echo $! > logs/vllm/server.pid ;;
    gateway)
      key="$(grep -E '^MODEL_GATEWAY_API_KEY=' .env | cut -d= -f2-)"
      clef_urls=""
      for replica in $CLEF_REPLICAS; do clef_urls="$clef_urls --clef-url http://127.0.0.1:${replica##*:}"; done
      # shellcheck disable=SC2086
      MODEL_GATEWAY_API_KEY="$key" nohup .venv/bin/python scripts/model_gateway.py --host 127.0.0.1 --port 30000 $clef_urls \
        --gemma-url "${GEMMA_URL:-http://127.0.0.1:30002}" > logs/clef/gateway.log 2>&1 & ;;
  esac
  echo "started $1 (model load takes a few minutes; check: scripts/models_ctl.sh status)"
}

stop() {
  if [ "$1" = vllm ] && [ -f logs/vllm/server.pid ]; then
    # graceful: the main process stops its engine and TP workers itself
    kill -TERM "$(cat logs/vllm/server.pid)" 2>/dev/null && echo "stopped vllm" || echo "vllm was not running"; return
  fi
  pkill -u "$(id -u)" -TERM -f "$(pattern "$1")" && echo "stopped $1" || echo "$1 was not running"
}

status() {
  for name in clef gemma vllm gateway; do
    pgrep -u "$(id -u)" -f "$(pattern "$name")" >/dev/null && echo "$name: running" || echo "$name: stopped"
  done
  for replica in $CLEF_REPLICAS; do
    curl -s -m 2 "http://127.0.0.1:${replica##*:}/health" >/dev/null && echo "clef :${replica##*:} (GPU ${replica%%:*}) health: ok" || echo "clef :${replica##*:} (GPU ${replica%%:*}): down"
  done
  curl -s -m 2 http://127.0.0.1:30002/health | grep -q '"ok"' && echo "gemma health: ok" || true
  curl -s -m 2 http://127.0.0.1:30003/health >/dev/null && echo "vllm health: ok" || true
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
}

action="${1:-status}"
target="${2:-all}"
case "$action" in
  start) [ "$target" = all ] && targets="clef gateway" || targets="$target"; for t in $targets; do start "$t"; done ;;
  stop) [ "$target" = all ] && targets="gateway gemma clef" || targets="$target"; for t in $targets; do stop "$t"; done ;;
  status) status ;;
  *) echo "usage: $0 start|stop|status [clef|gemma|vllm|gateway|all]"; exit 2 ;;
esac
