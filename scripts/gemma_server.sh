#!/bin/bash
# Serve gemma-4-26B-A4B-it (Q8_0 GGUF) with llama.cpp on 4 GPUs, OpenAI API on 127.0.0.1:30002
# (behind scripts/model_gateway.py). Everything lives under .cache/ (no system install).
#
#   .cache/llama-conda/pkg   conda-forge llama.cpp 11860 CUDA 12.9 build (glibc 2.17 baseline; the GitHub
#                            release needs glibc 2.38, this host has 2.31)
#   .cache/llama-conda/gcc   libstdc++ / libgcc_s from conda-forge (the system ones are too old)
#   .cache/openssl/x/lib     OpenSSL 3 from conda-forge (the system has 1.1)
#   .cache/llama.cpp/bin/cudart-*  libcudart / libcublas 12.8 from the llama.cpp release
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GPUS="${GEMMA_GPUS:-3,4,5,7}"
PORT="${GEMMA_PORT:-30002}"
# llama.cpp lists CUDA devices in CUDA_VISIBLE_DEVICES order: CUDA0..CUDA(n-1)
DEVICES="$(seq -s, -f 'CUDA%g' 0 $(( $(echo "$GPUS" | tr ',' '\n' | wc -l) - 1 )))"
MODELS="$(ls -d "$ROOT"/.cache/hf/hub/models--ggml-org--gemma-4-26B-A4B-it-GGUF/snapshots/* | head -1)"

export CUDA_VISIBLE_DEVICES="$GPUS"
# CUDA graphs need extra memory per batch shape; on these full 11 GB cards the 3rd+ concurrent request
# aborts llama-server ("out of memory" in cudaGraphInstantiate). Off: stable at 64 concurrent, same speed.
export GGML_CUDA_DISABLE_GRAPHS=1
export LD_LIBRARY_PATH="$ROOT/.cache/llama-conda/gcc/lib:$ROOT/.cache/llama-conda/pkg/lib:$ROOT/.cache/llama.cpp/bin/cudart-llama-b11913-bin-ubuntu-cuda-12.8-x64:$ROOT/.cache/openssl/x/lib"

exec "$ROOT/.cache/llama-conda/pkg/bin/llama-server" \
  -m "$MODELS/gemma-4-26B-A4B-it-${GEMMA_QUANT:-Q8_0}.gguf" \
  --mmproj "$MODELS/mmproj-gemma-4-26B-A4B-it-Q8_0.gguf" \
  --alias gemma26b-a4b --host 127.0.0.1 --port "$PORT" \
  --device "$DEVICES" \
  -ngl 99 --split-mode "${GEMMA_SPLIT:-layer}" -c "${GEMMA_CTX:-32768}" -np "${GEMMA_NP:-2}" --flash-attn on --jinja ${GEMMA_EXTRA:-}
