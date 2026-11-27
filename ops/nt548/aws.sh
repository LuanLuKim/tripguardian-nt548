#!/usr/bin/env bash
# Start and end of a lab session (#27): the costly part (envs/demo: ALB, ASGs, monitoring) only lives while someone
# works. The bootstrap (network, state bucket, ops machine) must exist (#22); see docs/nt548/08-aws-infra.md.
#
#   ops/nt548/aws.sh up [<image sha>]   start the ops machine, init the state, apply envs/demo
#                                       (both colors on <sha>, blue live; no sha: what the state had, else placeholder)
#   ops/nt548/aws.sh down               destroy envs/demo, then stop the ops machine (KEEP_OPS=1: leave it running)
#   ops/nt548/aws.sh status             ops machine, what envs/demo runs, ALB address, instances per color
#   ops/nt548/aws.sh init               only terraform init of envs/demo against the bootstrap bucket
#
# Runs on a member's machine (lab credentials in ~/.aws) or on the runner (LabInstanceProfile).
# Environment: NAME_PREFIX (nt548), AWS_REGION (us-east-1), TF_DIR (ops/nt548/terraform/envs/demo), TF_ARGS (extra
# arguments of apply/destroy, e.g. "-var real_harness=false"), KEEP_OPS, TERRAFORM (terraform), AWS (aws).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
NAME_PREFIX=${NAME_PREFIX:-nt548}
REGION=${AWS_REGION:-us-east-1}
TF_DIR=${TF_DIR:-$HERE/terraform/envs/demo}
TERRAFORM=${TERRAFORM:-terraform}
AWS=${AWS:-aws}
read -r -a EXTRA <<< "${TF_ARGS:-}"

log() { echo "[aws] $*" >&2; }
summary() { echo "$*"; [ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "$*" >> "$GITHUB_STEP_SUMMARY" || true; }
aws_() { "$AWS" --region "$REGION" --output text "$@"; }
tf() { "$TERRAFORM" -chdir="$TF_DIR" "$@"; }

ops_id() {
  aws_ ec2 describe-instances --filters "Name=tag:Name,Values=$NAME_PREFIX-ops" \
    "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[].Instances[].InstanceId'
}

ops_state() {
  local id=$1
  aws_ ec2 describe-instances --instance-ids "$id" --query 'Reservations[0].Instances[0].State.Name'
}

init() {
  local account
  account=$(aws_ sts get-caller-identity --query Account) || { log "no AWS credentials (Start Lab, AWS Details)"; exit 2; }
  tf init -input=false -reconfigure \
    -backend-config="bucket=$NAME_PREFIX-tfstate-$account" \
    -backend-config="key=envs/demo/$NAME_PREFIX.tfstate" \
    -backend-config="region=$REGION" >&2
}

output() {  # output <name>: a value from the state, '' when there is none
  tf output -raw "$1" 2>/dev/null || true
}

up() {
  local sha=${1:-} id state start
  start=$(date +%s)
  [ -z "$sha" ] || [[ $sha =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] || { log "not an image tag: $sha"; exit 2; }
  id=$(ops_id)
  [ -n "$id" ] || { log "no $NAME_PREFIX-ops machine: run the bootstrap first (docs/nt548/08-aws-infra.md)"; exit 1; }
  state=$(ops_state "$id")
  if [ "$state" != running ]; then
    log "starting $NAME_PREFIX-ops ($id, $state)"
    [ "$state" = stopping ] && aws_ ec2 wait instance-stopped --instance-ids "$id"
    aws_ ec2 start-instances --instance-ids "$id" >/dev/null
    aws_ ec2 wait instance-running --instance-ids "$id"
  fi
  init
  local vars=()
  if [ -n "$sha" ]; then
    vars=(-var "image_tag_blue=$sha" -var "image_tag_green=$sha" -var weight_blue=100)
  else
    # keep what the state had (an aws.sh up on a live environment changes nothing)
    local tb tg w
    tb=$(output image_tag_blue); tg=$(output image_tag_green); w=$(output weight_blue)
    vars=(-var "image_tag_blue=$tb" -var "image_tag_green=$tg" -var "weight_blue=${w:-100}")
  fi
  tf apply -auto-approve -input=false -var "name_prefix=$NAME_PREFIX" -var "region=$REGION" "${vars[@]}" "${EXTRA[@]}" >&2
  summary "up in $(( $(date +%s) - start ))s: http://$(output alb_dns_name)/ (blue=$(output image_tag_blue) green=$(output image_tag_green) weight_blue=$(output weight_blue))"
}

down() {
  local id start ops="left running"
  start=$(date +%s)
  init
  tf destroy -auto-approve -input=false -var "name_prefix=$NAME_PREFIX" -var "region=$REGION" "${EXTRA[@]}" >&2
  id=$(ops_id)
  if [ -n "$id" ] && [ -z "${KEEP_OPS:-}" ]; then
    log "stopping $NAME_PREFIX-ops ($id)"
    aws_ ec2 stop-instances --instance-ids "$id" >/dev/null
    ops=stopped
  fi
  summary "down in $(( $(date +%s) - start ))s: envs/demo destroyed, $NAME_PREFIX-ops $ops"
}

status() {
  local id c asg
  id=$(ops_id)
  summary "ops: ${id:-none} $([ -n "$id" ] && ops_state "$id")"
  init
  if [ -z "$(output alb_dns_name)" ]; then
    summary "envs/demo: down"
    return 0
  fi
  summary "envs/demo: http://$(output alb_dns_name)/ blue=$(output image_tag_blue) green=$(output image_tag_green) weight_blue=$(output weight_blue)"
  for c in blue green; do
    asg=$(output "asg_name_$c")
    summary "  $c: $(aws_ autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$asg" \
      --query 'AutoScalingGroups[0].[DesiredCapacity,length(Instances)]' | tr '\t' '/') desired/instances"
  done
}

case "${1:-}" in
  up) up "${2:-}" ;;
  down) down ;;
  status) status ;;
  init) init ;;
  *) sed -n '2,13p' "$0" >&2; exit 2 ;;
esac
