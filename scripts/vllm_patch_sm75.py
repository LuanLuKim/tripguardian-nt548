"""Idempotent patch of .venv-vllm for Turing (sm75, 64 KB shared memory per block).

vLLM 0.32.0 Triton unified attention needs ~96 KB shared memory for Gemma 4 global-attention layers
(head_dim 512) with its default tile 32 and pipelined loads; sm75 has 64 KB, so the CUDA-graph profile
dies with "OutOfResources: shared memory, Required: 98304, Hardware limit: 65536". The patch shrinks the
KV tile to 16 and uses one pipeline stage when the head size is >= 512 and the GPU is older than sm80.

    .venv/bin/python scripts/vllm_patch_sm75.py
"""

import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / ".venv-vllm/lib/python3.12/site-packages/vllm/v1/attention/ops/triton_unified_attention.py"
MARK = "# tripguardian sm75 patch"
ANCHOR = "    # USE_TD requires BLOCK_SIZE % TILE_SIZE == 0 (enforced by a\n"
PATCH = f"""    {MARK}: head_dim >= 512 does not fit 64 KB shared memory with tile 32
    if head_size >= 512 and not current_platform.has_device_capability(80):
        TILE_SIZE_PREFILL = min(TILE_SIZE_PREFILL, 16)
        TILE_SIZE_DECODE = min(TILE_SIZE_DECODE, 16)
        launch_num_stages = 1

"""

text = TARGET.read_text()
if MARK in text:
    print("already patched")
    sys.exit(0)
assert text.count(ANCHOR) == 1, "anchor not found: vLLM version changed?"
TARGET.write_text(text.replace(ANCHOR, PATCH + ANCHOR))
print("patched", TARGET)
