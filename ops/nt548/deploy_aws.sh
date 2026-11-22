#!/usr/bin/env bash
# Blue/green release on AWS through Terraform (#29). Runs on the self-hosted runner (LabInstanceProfile) or, as a
# fallback, on a GitHub runner with lab credentials from the nt548-aws environment.
#
#   ops/nt548/deploy_aws.sh deploy <image-sha>   idle color gets <sha> -> healthy -> canary -> watch -> promote | roll back
#   ops/nt548/deploy_aws.sh rollback             all traffic back to the other color (it still runs the previous sha)
#   ops/nt548/deploy_aws.sh status               live color, tags, weight
#
# Contract with T8 (design §7.1): envs/demo takes image_tag_blue, image_tag_green, weight_blue (0-100),
# data_release_blue, data_release_green and outputs target_group_arn_{blue,green}. This script also reads the
# outputs image_tag_{blue,green}, weight_blue and data_release_{blue,green} (the inputs echoed back) to know what
# runs now; without them (first deploy, empty state) both colors get <sha> and blue takes all traffic.
# It changes AWS only through `terraform apply`; `aws elbv2 describe-target-health` is a read.
#
# Environment: TF_DIR (default ops/nt548/terraform/envs/demo), CANARY_WEIGHT (10), CANARY_SECONDS (300),
# HEALTH_TIMEOUT (600), HEALTH_POLL (10), TERRAFORM (terraform), AWS (aws), PYTHON (python3).
set -euo pipefail

TF_DIR=${TF_DIR:-ops/nt548/terraform/envs/demo}
CANARY_WEIGHT=${CANARY_WEIGHT:-10}
CANARY_SECONDS=${CANARY_SECONDS:-300}
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-600}
HEALTH_POLL=${HEALTH_POLL:-10}
TERRAFORM=${TERRAFORM:-terraform}
AWS=${AWS:-aws}
PYTHON=${PYTHON:-python3}
HERE=$(cd "$(dirname "$0")" && pwd)

log() { echo "[deploy-aws] $*" >&2; }
summary() { echo "$*"; [ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "$*" >> "$GITHUB_STEP_SUMMARY" || true; }

tf() { "$TERRAFORM" -chdir="$TF_DIR" "$@"; }

# Current release from terraform outputs, as shell assignments: TAG_BLUE TAG_GREEN WEIGHT_BLUE DATA_BLUE DATA_GREEN
# TG_BLUE TG_GREEN (empty when not there yet).
read_state() {
  local json
  json=$(tf output -json 2>/dev/null || echo '{}')
  eval "$(printf '%s' "$json" | "$PYTHON" -c '
import json, shlex, sys
o = json.load(sys.stdin) or {}
v = lambda k, d="": str(o.get(k, {}).get("value", d))
for name, key, default in [("TAG_BLUE", "image_tag_blue", ""), ("TAG_GREEN", "image_tag_green", ""),
                           ("WEIGHT_BLUE", "weight_blue", ""), ("DATA_BLUE", "data_release_blue", "r-a"),
                           ("DATA_GREEN", "data_release_green", "r-a"), ("TG_BLUE", "target_group_arn_blue", ""),
                           ("TG_GREEN", "target_group_arn_green", "")]:
    print(f"{name}={shlex.quote(v(key, default))}")
')"
}

apply() {  # apply <tag_blue> <tag_green> <weight_blue>
  log "terraform apply: blue=$1 green=$2 weight_blue=$3"
  tf apply -auto-approve -input=false \
    -var "image_tag_blue=$1" -var "image_tag_green=$2" -var "weight_blue=$3" \
    -var "data_release_blue=$DATA_BLUE" -var "data_release_green=$DATA_GREEN" >&2
}

wait_healthy() {  # wait_healthy <color>: every target of that color's target group is healthy
  local color=$1 tg states start
  read_state
  tg=$([ "$color" = blue ] && echo "$TG_BLUE" || echo "$TG_GREEN")
  [ -n "$tg" ] || { log "no target_group_arn_$color output"; return 1; }
  start=$(date +%s)
  while :; do
    states=$("$AWS" elbv2 describe-target-health --target-group-arn "$tg" \
      --query 'TargetHealthDescriptions[].TargetHealth.State' --output text 2>/dev/null || true)
    if [ -n "$states" ] && ! printf '%s' "$states" | tr '\t ' '\n\n' | grep -qv '^healthy$'; then
      log "$color healthy after $(( $(date +%s) - start ))s"
      return 0
    fi
    if (( $(date +%s) - start >= HEALTH_TIMEOUT )); then
      log "$color not healthy after ${HEALTH_TIMEOUT}s: ${states:-no target}"
      return 1
    fi
    sleep "$HEALTH_POLL"
  done
}

watch_canary() {  # watch_canary <color>: canary_watch.py of #3 when it exists, else stay healthy for CANARY_SECONDS
  local color=$1 tg
  if [ -f "$HERE/canary_watch.py" ]; then
    read_state
    tg=$([ "$color" = blue ] && echo "$TG_BLUE" || echo "$TG_GREEN")
    "$PYTHON" "$HERE/canary_watch.py" --target-group "$tg" --seconds "$CANARY_SECONDS"
  else
    log "canary_watch.py (#3) not there yet: only checking that $color stays healthy for ${CANARY_SECONDS}s"
    sleep "$CANARY_SECONDS"
    HEALTH_TIMEOUT=1 wait_healthy "$color"
  fi
}

weights() {  # weights <live color> <weight of the idle color> -> weight_blue
  local live=$1 idle_w=$2
  if [ "$live" = blue ]; then echo $(( 100 - idle_w )); else echo "$idle_w"; fi
}

live_color() { if [ "${WEIGHT_BLUE:-100}" -ge 50 ]; then echo blue; else echo green; fi; }

deploy() {
  local sha=$1 live idle tb tg
  [[ $sha =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] || { log "not an image tag: $sha"; return 2; }
  read_state
  if [ -z "$TAG_BLUE" ] && [ -z "$TAG_GREEN" ]; then
    log "first deploy: both colors get $sha, blue takes all traffic"
    apply "$sha" "$sha" 100
    wait_healthy blue
    summary "first deploy: blue=$sha green=$sha weight_blue=100"
    return 0
  fi
  live=$(live_color); idle=$([ "$live" = blue ] && echo green || echo blue)
  tb=$TAG_BLUE; tg=$TAG_GREEN
  if [ "$idle" = blue ]; then tb=$sha; else tg=$sha; fi
  log "live=$live idle=$idle: $idle gets $sha"

  apply "$tb" "$tg" "$(weights "$live" 0)"
  if ! wait_healthy "$idle"; then
    summary "deploy $sha: $idle never got healthy, traffic stayed on $live"
    return 1
  fi
  apply "$tb" "$tg" "$(weights "$live" "$CANARY_WEIGHT")"
  if ! watch_canary "$idle"; then
    apply "$tb" "$tg" "$(weights "$live" 0)"
    summary "deploy $sha: canary on $idle failed, rolled back to $live"
    return 1
  fi
  apply "$tb" "$tg" "$(weights "$live" 100)"
  summary "deploy $sha: promoted $idle (100%), $live kept for rollback"
}

rollback() {
  local live other start
  start=$(date +%s)
  read_state
  live=$(live_color); other=$([ "$live" = blue ] && echo green || echo blue)
  if [ -z "$([ "$other" = blue ] && echo "$TAG_BLUE" || echo "$TAG_GREEN")" ]; then
    log "$other has no image: nothing to roll back to"
    return 1
  fi
  apply "$TAG_BLUE" "$TAG_GREEN" "$(weights "$live" 100)"
  summary "rollback: $live -> $other in $(( $(date +%s) - start ))s"
}

status() {
  read_state
  summary "live=$(live_color) blue=${TAG_BLUE:--} green=${TAG_GREEN:--} weight_blue=${WEIGHT_BLUE:--}"
}

case "${1:-}" in
  deploy) [ -n "${2:-}" ] || { echo "usage: $0 deploy <image-sha>" >&2; exit 2; }; deploy "$2" ;;
  rollback) rollback ;;
  status) status ;;
  *) echo "usage: $0 deploy <image-sha> | rollback | status" >&2; exit 2 ;;
esac
