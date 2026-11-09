#!/bin/bash
# Serve gemma-4-26B-A4B-it (AWQ 4-bit, compressed-tensors w4a16) with vLLM on 2 GPUs (tensor parallel),
# OpenAI API on 127.0.0.1:30003 (behind scripts/model_gateway.py). Own venv .venv-vllm, caches in .cache/.
#   uv venv --python 3.12 .venv-vllm && UV_CACHE_DIR=$PWD/.cache/uv uv pip install --python .venv-vllm/bin/python vllm==0.32.0
# Turing (2080 Ti, sm75): fp16 only, no bf16, no FlashAttention 2. Knobs via env: VLLM_GPUS, VLLM_PORT,
# VLLM_MAX_LEN, VLLM_MEM_UTIL, VLLM_EXTRA.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CUDA_VISIBLE_DEVICES="${VLLM_GPUS:-0,1}"
export HF_HOME="$ROOT/.cache/hf" TMPDIR="$ROOT/.cache/tmp" VLLM_CACHE_ROOT="$ROOT/.cache/vllm" HF_HUB_OFFLINE=1
export TRITON_CACHE_DIR="$ROOT/.cache/triton" TORCHINDUCTOR_CACHE_DIR="$ROOT/.cache/inductor" XDG_CACHE_HOME="$ROOT/.cache/xdg"
export VLLM_RPC_BASE_PATH=/tmp/tg_vllm_rpc  # unix socket paths must be < 108 chars; the repo path is too long
export VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1
mkdir -p "$TMPDIR" "$VLLM_CACHE_ROOT" "$VLLM_RPC_BASE_PATH"
NGPU="$(echo "$CUDA_VISIBLE_DEVICES" | tr ',' '\n' | wc -l)"

exec "$ROOT/.venv-vllm/bin/vllm" serve "${VLLM_MODEL:-cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit}" \
  --served-model-name gemma26b-a4b gemma26b-a4b-vllm \
  --host 127.0.0.1 --port "${VLLM_PORT:-30003}" \
  --tensor-parallel-size "$NGPU" --dtype float16 \
  --max-model-len "${VLLM_MAX_LEN:-16384}" --gpu-memory-utilization "${VLLM_MEM_UTIL:-0.92}" \
  --max-num-seqs "${VLLM_MAX_SEQS:-48}" ${VLLM_EXTRA:-}
