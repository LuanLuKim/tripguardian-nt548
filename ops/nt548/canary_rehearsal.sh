#!/usr/bin/env bash
# The canary rehearsal of docs/nt548/03-canary-scale.md §Kiểm thử, in one command (CI: nt548-bluegreen.yml).
# Under background traffic, canary_watch.py drives each candidate through the weight steps:
#   good      the new image                       -> promote all steps
#   http_500  NT548_FAULT=500 (every API route)   -> rollback, the old color serves no 5xx
#   slow      NT548_FAULT=delay:800               -> rollback on p95
# Images ghcr.io/luanlukim/tripguardian-nt548/*:<OLD_TAG> and :<NEW_TAG> must exist locally. Markdown to $SUMMARY.
#
#   OLD_TAG=old NEW_TAG=new STEP_SECONDS=15 ops/nt548/canary_rehearsal.sh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
D="$ROOT/ops/nt548/deploy.sh"
PY=python3
OLD_TAG=${OLD_TAG:-old}
NEW_TAG=${NEW_TAG:-new}
STEP_SECONDS=${STEP_SECONDS:-15}
export NT548_STATE=${NT548_STATE:-$ROOT/ops/nt548/state}
LOG="$NT548_STATE/log/access.log"
WORK=$(mktemp -d)
SUMMARY=${SUMMARY:-/dev/stdout}
rows=()
fail=0

active() { cat "$NT548_STATE/active" 2>/dev/null || echo blue; }
other() { [ "$1" = blue ] && echo green || echo blue; }

"$D" up blue "$OLD_TAG"
"$D" lb
$PY "$ROOT/ops/nt548/lb_check.py" load --until "$WORK/stop" --out "$WORK/load.json" --workers 8 > "$WORK/load.log" 2>&1 &
load_pid=$!
sleep 3

case_run() {  # case_run <name> <expected promote|rollback> <NT548_FAULT>
  local name=$1 expect=$2 fault=$3 old new start rc got t0 secs reason old5xx
  old=$(active); new=$(other "$old")
  NT548_FAULT=$fault "$D" up "$new" "$NEW_TAG"
  start=$($PY -c "import time; print(int(time.time() * 1000))"); t0=$(date +%s)
  set +e
  $PY "$ROOT/ops/nt548/canary_watch.py" --step-seconds "$STEP_SECONDS" --max-wait-seconds 30 run --out "$WORK/$name.json"
  rc=$?
  set -e
  secs=$(( $(date +%s) - t0 ))
  got=$([ $rc = 0 ] && echo promote || echo rollback)
  reason=$($PY -c "import json,sys; h=json.load(open(sys.argv[1])); print(h[-1]['reason'] if h else '')" "$WORK/$name.json")
  old5xx=$($PY -c "
import json, sys
n = 0
for line in open(sys.argv[1]):
    try: r = json.loads(line)
    except ValueError: continue
    n += r['color'] == sys.argv[2] and float(r['msec']) * 1000 >= int(sys.argv[3]) and 500 <= r['status'] <= 599
print(n)" "$LOG" "$old" "$start")
  local ok=pass
  [ "$got" = "$expect" ] || ok=FAIL
  [ "$expect" = promote ] || [ "$old5xx" = 0 ] || ok=FAIL
  [ $ok = pass ] || fail=1
  rows+=("| $name | \`${fault:-none}\` on $new | $expect | $got | $ok | ${secs} s | $old5xx | $(echo "$reason" | tr '|' '/') |")
  echo "== $name: expected $expect, got $got in ${secs}s; old color 5xx $old5xx; $reason"
  [ "$got" = promote ] || "$D" down "$new"   # a rolled-back candidate is stopped
}

case_run good promote ""
case_run http_500 rollback 500
case_run slow rollback delay:800

touch "$WORK/stop"; wait "$load_pid" || true
cat "$WORK/load.log"
"$D" status

{
  echo "### Canary rehearsal (steps of canary.yaml, ${STEP_SECONDS} s each)"
  echo
  echo "| Case | Candidate | Expected | Got | Result | Time to decision | 5xx on the old color | Reason |"
  echo "|---|---|---|---|---|---|---|---|"
  printf '%s\n' "${rows[@]}"
} >> "$SUMMARY"
exit $fail
