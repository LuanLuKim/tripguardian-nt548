#!/usr/bin/env bash
# The blue/green rehearsal of docs/nt548/02-bluegreen-lb.md §Kiểm thử, in one command (CI: nt548-bluegreen.yml).
# Images ghcr.io/luanlukim/tripguardian-nt548/{harness,web,llm-fake}:<OLD_TAG> and :<NEW_TAG> must exist locally
# (CI builds them once and tags the build twice). Background traffic runs through every switch; at the end it must
# have seen no connection error and no 5xx. A markdown table of the checks goes to $SUMMARY (default stdout).
#
#   OLD_TAG=old NEW_TAG=new ops/nt548/bluegreen_rehearsal.sh
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
D="$ROOT/ops/nt548/deploy.sh"
CHECK="python3 $ROOT/ops/nt548/lb_check.py"
OLD_TAG=${OLD_TAG:-old}
NEW_TAG=${NEW_TAG:-new}
WORK=$(mktemp -d)
SUMMARY=${SUMMARY:-/dev/stdout}
rows=()
fail=0

check() {  # check <name> <criterion> <command...>: run, record the JSON it prints and whether it passed
  local name=$1 crit=$2 out rc; shift 2
  set +e; out=$("$@" 2>&1); rc=$?; set -e
  echo "== $name: $out"
  rows+=("| $name | $crit | $([ $rc = 0 ] && echo pass || echo FAIL) | \`$(echo "$out" | tail -n 1 | tr '|' '/')\` |")
  [ $rc = 0 ] || fail=1
}

echo "== blue on $OLD_TAG, nginx in front"
"$D" up blue "$OLD_TAG"
"$D" lb
check "blue serves everyone" "100 % blue" $CHECK split --color blue --expect 100 --tol 0 --n 200

echo "== green on $NEW_TAG, no traffic yet; background traffic starts"
"$D" up green "$NEW_TAG"
$CHECK load --until "$WORK/stop" --out "$WORK/load.json" --workers 8 > "$WORK/load.log" 2>&1 &
load_pid=$!
sleep 3

"$D" weight 10
check "split at weight 10" "7–13 % green over 1000 new cookies" $CHECK split --color green --expect 10 --tol 3
check "sticky" "20 users × 100 requests, each on one color" $CHECK sticky --users 20 --n 100

"$D" weight 100
check "weight 100" "100 % green" $CHECK split --color green --expect 100 --tol 0 --n 200

t0=$(date +%s.%N)
"$D" rollback
check "rollback" "100 % back on blue in < 60 s" $CHECK wait-color --color blue --timeout 60
rollback_s=$(awk "BEGIN{printf \"%.2f\", $(date +%s.%N) - $t0}")

"$D" weight 100
"$D" promote
check "promote" "green active, 100 % green" $CHECK split --color green --expect 100 --tol 0 --n 200

sleep 2
touch "$WORK/stop"; wait "$load_pid" || true
cat "$WORK/load.log"
check "no request lost while switching" "0 connection errors, 0 5xx" $CHECK verify "$WORK/load.json" --max-conn-errors 0 --max-5xx 0
"$D" status

{
  echo "### Blue/green rehearsal ($OLD_TAG → $NEW_TAG)"
  echo
  echo "| Check | Criterion | Result | Output |"
  echo "|---|---|---|---|"
  printf '%s\n' "${rows[@]}"
  echo
  echo "Rollback, command to 100 % on blue: **${rollback_s} s**. Background traffic: \`$(python3 -c "import json,sys; s=json.load(open(sys.argv[1])); print(f\"{s['requests']} requests, status {s['status']}, p95 {s['p95_ms']} ms\")" "$WORK/load.json")\`"
} >> "$SUMMARY"
cp "$WORK/load.json" "${LOAD_OUT:-$WORK/load.json}" 2>/dev/null || true
exit $fail
