#!/usr/bin/env bash
# Run a command while holding the GPU lease: the prod harness moves its encoders to RAM (they answer on the CPU) and
# gets the GPU back when the command exits. Several jobs queue on the lock. Usage: scripts/gpu_lease.sh <cmd> [args...]
set -euo pipefail
lease="${GPU_LEASE:-/tmp/tripguardian-gpu.lease}"
settle="${GPU_LEASE_SETTLE_S:-6}"   # the harness checks every 3 s; give it time to let go before the job allocates
exec flock -x "$lease" bash -c 'sleep "$0"; exec "$@"' "$settle" "$@"
