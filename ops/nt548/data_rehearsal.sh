#!/usr/bin/env bash
# Data release rehearsal on one machine (T5.4, #11): the real harness, two colors, a shared Postgres.
#
#   gate      data_check CANDIDATE against BASELINE; red -> stop here, nothing is started
#   blue      DATA_DIR with BASELINE only; serves BASELINE; a guest creates a journey (pinned to BASELINE)
#   green     DATA_DIR with BASELINE + CANDIDATE, pointer on CANDIDATE; serves CANDIDATE; the blue journey still opens
#   pin       a color holding only CANDIDATE answers that journey with 409 stale_data_version (why green keeps both)
#   rollback  green's pointer back to BASELINE (corpus.releases.publish), restart, serves BASELINE again
#
# On AWS the same switch is data_release_green + weight_blue through Terraform (#21, #29); here the colors are two
# harness processes on ports BLUE_PORT / GREEN_PORT.
#
# Environment: DATABASE_URL (required, migrations are applied), SAMPLE (default ops/nt548/sample-data; built with
# make.py --broken when missing), WORK (scratch dir, default a mktemp dir), CANDIDATE (r-b), BASELINE (r-a),
# PYTHON (python), BLUE_PORT (18001), GREEN_PORT (18002), PIN_PORT (18003).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
PYTHON=${PYTHON:-python}
SAMPLE=${SAMPLE:-$HERE/sample-data}
WORK=${WORK:-$(mktemp -d -t nt548-rehearsal-XXXX)}
CANDIDATE=${CANDIDATE:-r-b}
BASELINE=${BASELINE:-r-a}
BLUE_PORT=${BLUE_PORT:-18001}
GREEN_PORT=${GREEN_PORT:-18002}
PIN_PORT=${PIN_PORT:-18003}
: "${DATABASE_URL:?DATABASE_URL is required}"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" LANCEDB_LOG=${LANCEDB_LOG:-error}

log() { echo "[data-rehearsal] $*"; }
summary() { echo "$*"; [ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "$*" >> "$GITHUB_STEP_SUMMARY" || true; }
pids=()
cleanup() { for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT

# start <name> <data dir> <port>: the real harness on that DATA_DIR, waits until it answers (up to 120 s)
start() {
  local name=$1 data=$2 port=$3 started
  started=$(date +%s)
  DATA_DIR=$data "$PYTHON" -m harness serve --port "$port" > "$WORK/$name.log" 2>&1 &
  pids+=($!)
  for _ in $(seq 1 120); do
    if "$PYTHON" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$port/api/auth/options', timeout=2)" 2>/dev/null; then
      log "$name up on :$port in $(( $(date +%s) - started )) s ($(cat "$data/releases/current"))"
      return 0
    fi
    kill -0 "${pids[-1]}" 2>/dev/null || { tail -30 "$WORK/$name.log"; log "$name exited"; return 1; }
    sleep 1
  done
  tail -30 "$WORK/$name.log"; log "$name did not answer in 120 s"; return 1
}
stop_last() { kill "${pids[-1]}" 2>/dev/null || true; wait "${pids[-1]}" 2>/dev/null || true; unset 'pids[-1]'; }
dr() { "$PYTHON" "$HERE/data_release.py" "$@"; }

[ -d "$SAMPLE/$BASELINE" ] && [ -d "$SAMPLE/$CANDIDATE" ] || "$PYTHON" "$HERE/sample-data/make.py" --out "$SAMPLE" --broken
log "work dir $WORK"
(cd "$ROOT" && "$PYTHON" -m db migrate)

summary "### Data release rehearsal: $BASELINE -> $CANDIDATE"
if ! "$PYTHON" "$HERE/data_check.py" "$SAMPLE/$CANDIDATE" --baseline "$SAMPLE/$BASELINE"; then
  summary "- gate: **data_check refused $CANDIDATE**, nothing deployed"
  exit 1
fi
summary "- gate: data_check passed $CANDIDATE"

C="$WORK/cookies.txt"
dr stage "$WORK/blue" --release "$SAMPLE/$BASELINE" --current "$SAMPLE/$BASELINE"
start blue "$WORK/blue" "$BLUE_PORT"
dr smoke "http://127.0.0.1:$BLUE_PORT" --expect "$SAMPLE/$BASELINE" --not "$SAMPLE/$CANDIDATE" --cookies "$C" \
  --create-journey "$WORK/journey"
summary "- blue serves $BASELINE; journey $(cat "$WORK/journey") pinned to it"

dr stage "$WORK/green" --release "$SAMPLE/$BASELINE" --release "$SAMPLE/$CANDIDATE" --current "$SAMPLE/$CANDIDATE"
start green "$WORK/green" "$GREEN_PORT"
dr smoke "http://127.0.0.1:$GREEN_PORT" --expect "$SAMPLE/$CANDIDATE" --not "$SAMPLE/$BASELINE" --cookies "$C" \
  --open-journey "$WORK/journey" --want 200
summary "- green serves $CANDIDATE; the $BASELINE journey still opens (both releases mounted)"

dr stage "$WORK/pin" --release "$SAMPLE/$CANDIDATE" --current "$SAMPLE/$CANDIDATE"
start pin "$WORK/pin" "$PIN_PORT"
dr smoke "http://127.0.0.1:$PIN_PORT" --expect "$SAMPLE/$CANDIDATE" --cookies "$C" --open-journey "$WORK/journey" --want 409
stop_last
summary "- a color with only $CANDIDATE answers that journey 409 stale_data_version"

stop_last  # green restarts on the rolled-back pointer
dr stage "$WORK/green" --current "$SAMPLE/$BASELINE"
start green "$WORK/green" "$GREEN_PORT"
dr smoke "http://127.0.0.1:$GREEN_PORT" --expect "$SAMPLE/$BASELINE" --not "$SAMPLE/$CANDIDATE" --cookies "$C" \
  --open-journey "$WORK/journey" --want 200
summary "- rollback: green back on $BASELINE, $CANDIDATE kept on disk (releases are immutable)"
log "rehearsal passed"
