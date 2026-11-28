#!/usr/bin/env bash
# Blue/green release on AWS through Terraform (#29). Runs on the self-hosted runner (LabInstanceProfile) or, as a
# fallback, on a GitHub runner with lab credentials from the nt548-aws environment.
#
#   ops/nt548/deploy_aws.sh deploy <image-sha>   idle color gets <sha> -> healthy -> canary -> watch -> promote | roll back
#   ops/nt548/deploy_aws.sh data <release>       same path for data (#11): idle color gets data release <release> (r-b),
#                                                keeping the live color's image; the instance's data_check gates it
#   ops/nt548/deploy_aws.sh rollback             all traffic back to the other color (it still runs the previous sha)
#   ops/nt548/deploy_aws.sh status               live color, tags, weight
#
# Contract with T8 (design §7.1): envs/demo takes image_tag_blue, image_tag_green, weight_blue (0-100),
# data_release_blue, data_release_green and outputs target_group_arn_{blue,green}, asg_name_{blue,green},
# alb_arn_suffix, target_group_arn_suffix_{blue,green}. This script also reads the
# outputs image_tag_{blue,green}, weight_blue and data_release_{blue,green} (the inputs echoed back) to know what
# runs now; without them (first deploy, empty state) both colors get <sha> and blue takes all traffic.
# A release changes one thing on the idle color and copies the other from the live color: a code deploy carries the
# live data release, a data release carries the live image, so neither undoes the last change of the other.
# It changes AWS only through `terraform apply`; the aws calls (target health, instance refreshes, CloudWatch metrics
# in canary_watch.py) only read.
#
# FIRST_DEPLOY=0 (set by nt548-deploy-aws.yml on the automatic run after a merge): an empty state means envs/demo
# is down, so the script exits 0 without applying. Building envs/demo from nothing is aws.sh up's job (incident
# 28/11: a merge queued behind `aws.sh down` re-created half of envs/demo and left orphans when the ops machine stopped).
# Environment: TF_DIR (default ops/nt548/terraform/envs/demo), CANARY_WEIGHT (10), CANARY_SECONDS (300),
# HEALTH_TIMEOUT (600), HEALTH_POLL (10), NAME_PREFIX (passed to terraform when set), TERRAFORM (terraform),
# AWS (aws), PYTHON (python3), CANARY_CMD (default: $PYTHON canary_watch.py; thresholds in canary.yaml),
# FIRST_DEPLOY (1: an empty state gets a first deploy; 0: it is skipped).
# Before the first call: ops/nt548/aws.sh init (the state is in the bootstrap's S3 bucket).
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
CANARY_CMD=${CANARY_CMD:-$PYTHON $HERE/canary_watch.py}
FIRST_DEPLOY=${FIRST_DEPLOY:-1}

log() { echo "[deploy-aws] $*" >&2; }
summary() { echo "$*"; [ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "$*" >> "$GITHUB_STEP_SUMMARY" || true; }

tf() { "$TERRAFORM" -chdir="$TF_DIR" "$@"; }

# Current release from terraform outputs, as shell assignments: TAG_BLUE TAG_GREEN WEIGHT_BLUE DATA_BLUE DATA_GREEN
# TG_BLUE TG_GREEN, ALB_SUFFIX TGS_BLUE TGS_GREEN (metric dimensions), ASG_BLUE ASG_GREEN (empty when not there yet).
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
                           ("TG_GREEN", "target_group_arn_green", ""), ("ALB_SUFFIX", "alb_arn_suffix", ""),
                           ("TGS_BLUE", "target_group_arn_suffix_blue", ""),
                           ("TGS_GREEN", "target_group_arn_suffix_green", ""),
                           ("ASG_BLUE", "asg_name_blue", ""), ("ASG_GREEN", "asg_name_green", "")]:
    print(f"{name}={shlex.quote(v(key, default))}")
')"
}

apply() {  # apply <tag_blue> <tag_green> <weight_blue>
  log "terraform apply: blue=$1 green=$2 weight_blue=$3"
  local prefix=()
  [ -z "${NAME_PREFIX:-}" ] || prefix=(-var "name_prefix=$NAME_PREFIX")
  tf apply -auto-approve -input=false "${prefix[@]}" \
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

wait_refresh() {  # wait_refresh <color>: the instance refresh that a new image started on that color's ASG is over
  # While it runs, the old instances are still healthy targets, so target health alone would pass too early.
  # With rollout = replace (the default on Learner Lab, AWS-14) the new group has no refresh: this returns at once,
  # apply already waited for the new group, and wait_healthy waits until the old group's targets have drained.
  local color=$1 asg status start
  read_state
  asg=$([ "$color" = blue ] && echo "$ASG_BLUE" || echo "$ASG_GREEN")
  [ -n "$asg" ] || { log "no asg_name_$color output: not waiting for an instance refresh"; return 0; }
  start=$(date +%s)
  while :; do
    status=$("$AWS" autoscaling describe-instance-refreshes --auto-scaling-group-name "$asg" --max-records 1       --query 'InstanceRefreshes[0].Status' --output text 2>/dev/null || echo unknown)
    case $status in  # Pending, InProgress, Baking, Cancelling, RollbackInProgress, unknown: keep waiting
      Successful | None | "") log "$color refresh ${status:-none} after $(( $(date +%s) - start ))s"; return 0 ;;
      Failed | Cancelled | RollbackSuccessful | RollbackFailed) log "$color instance refresh $status"; return 1 ;;
    esac
    if (( $(date +%s) - start >= HEALTH_TIMEOUT )); then
      log "$color instance refresh still $status after ${HEALTH_TIMEOUT}s"
      return 1
    fi
    sleep "$HEALTH_POLL"
  done
}

watch_canary() {  # watch_canary <color>: canary_watch.py on the ALB metrics, new color against the live one, then
  # the new color must still be healthy
  local color=$1 old new
  read_state
  if [ "$color" = blue ]; then new=$TGS_BLUE old=$TGS_GREEN; else new=$TGS_GREEN old=$TGS_BLUE; fi
  if [ -z "$ALB_SUFFIX" ] || [ -z "$new" ] || [ -z "$old" ]; then
    log "no alb_arn_suffix / target_group_arn_suffix_* outputs: only checking that $color stays healthy for ${CANARY_SECONDS}s"
    sleep "$CANARY_SECONDS"
  else
    # shellcheck disable=SC2086
    $CANARY_CMD --step-seconds "$CANARY_SECONDS" cloudwatch --lb "$ALB_SUFFIX" --old-tg "$old" --new-tg "$new" || return 1
  fi
  HEALTH_TIMEOUT=1 wait_healthy "$color"
}

weights() {  # weights <live color> <weight of the idle color> -> weight_blue
  local live=$1 idle_w=$2
  if [ "$live" = blue ]; then echo $(( 100 - idle_w )); else echo "$idle_w"; fi
}

live_color() { if [ "${WEIGHT_BLUE:-100}" -ge 50 ]; then echo blue; else echo green; fi; }

release() {  # release <image-sha|""> <data release|"">: one of the two changes on the idle color
  local sha=$1 data=$2 what live idle tb tg
  what=$([ -n "$sha" ] && echo "deploy $sha" || echo "data $data")
  read_state
  if [ -z "$TAG_BLUE" ] && [ -z "$TAG_GREEN" ]; then
    if [ -z "$sha" ]; then
      summary "$what: envs/demo is down, nothing to switch (aws.sh up first)"
      return 1
    fi
    if [ "$FIRST_DEPLOY" != 1 ]; then
      summary "envs/demo is down: nothing to deploy ($sha not applied; aws.sh up builds it)"
      return 0
    fi
    log "first deploy: both colors get $sha, blue takes all traffic"
    apply "$sha" "$sha" 100
    wait_healthy blue
    summary "first deploy: blue=$sha green=$sha weight_blue=100"
    return 0
  fi
  live=$(live_color); idle=$([ "$live" = blue ] && echo green || echo blue)
  local live_tag live_data
  if [ "$live" = blue ]; then live_tag=$TAG_BLUE live_data=$DATA_BLUE; else live_tag=$TAG_GREEN live_data=$DATA_GREEN; fi
  if [ "$idle" = blue ]; then
    tb=${sha:-$live_tag}; tg=$TAG_GREEN; DATA_BLUE=${data:-$live_data}
  else
    tb=$TAG_BLUE; tg=${sha:-$live_tag}; DATA_GREEN=${data:-$live_data}
  fi
  log "live=$live idle=$idle: $idle gets image $([ "$idle" = blue ] && echo "$tb" || echo "$tg")," \
    "data $([ "$idle" = blue ] && echo "$DATA_BLUE" || echo "$DATA_GREEN")"

  apply "$tb" "$tg" "$(weights "$live" 0)"
  if ! wait_refresh "$idle" || ! wait_healthy "$idle"; then
    summary "$what: $idle never got healthy, traffic stayed on $live"
    return 1
  fi
  apply "$tb" "$tg" "$(weights "$live" "$CANARY_WEIGHT")"
  if ! watch_canary "$idle"; then
    apply "$tb" "$tg" "$(weights "$live" 0)"
    summary "$what: canary on $idle failed, rolled back to $live"
    return 1
  fi
  apply "$tb" "$tg" "$(weights "$live" 100)"
  summary "$what: promoted $idle (100%), $live kept for rollback"
}

deploy() {
  [[ $1 =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] || { log "not an image tag: $1"; return 2; }
  release "$1" ""
}

data() {
  [[ $1 =~ ^r-[A-Za-z0-9_-]+$ ]] || { log "not a data release: $1 (r-a, r-b, ...)"; return 2; }
  release "" "$1"
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
  summary "live=$(live_color) blue=${TAG_BLUE:--} green=${TAG_GREEN:--} weight_blue=${WEIGHT_BLUE:--}" \
    "data_blue=$DATA_BLUE data_green=$DATA_GREEN"
}

case "${1:-}" in
  deploy) [ -n "${2:-}" ] || { echo "usage: $0 deploy <image-sha>" >&2; exit 2; }; deploy "$2" ;;
  data) [ -n "${2:-}" ] || { echo "usage: $0 data <release>" >&2; exit 2; }; data "$2" ;;
  rollback) rollback ;;
  status) status ;;
  *) echo "usage: $0 deploy <image-sha> | data <release> | rollback | status" >&2; exit 2 ;;
esac
