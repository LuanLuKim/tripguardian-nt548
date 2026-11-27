#!/usr/bin/env bash
# R2 (#22): can this identity (LabRole through the lab's temporary credentials or LabInstanceProfile) do what the
# NT548 Terraform needs? Each probe creates the smallest thing it can and deletes it right away; a few are dry runs.
# Prints a markdown table (paste it into issue #22) and exits 1 when something is denied.
#
#   ops/nt548/aws_r2_probe.sh [--out r2.md]
#
# Uses the default VPC for the ALB / target group probes. Cost: one ALB for a few seconds (a fraction of a cent).
# Environment: AWS_REGION (default us-east-1), AWS (aws).
set -uo pipefail

REGION=${AWS_REGION:-us-east-1}
AWS=${AWS:-aws}
OUT=""
[ "${1:-}" = "--out" ] && OUT=${2:?--out needs a file}
TAG="nt548-r2-$(date +%s)"
ROWS=()
DENIED=0

aws_() { "$AWS" --region "$REGION" --output text "$@"; }

# probe <what> <command...>: ok / denied (with the error code) / other error. The output of a success is in LAST.
LAST=""
probe() {
  local what=$1 out code
  shift
  if out=$("$@" 2>&1); then
    ROWS+=("| $what | ok |")
    LAST=$out
    return 0
  fi
  code=$(printf '%s' "$out" | grep -oE '\(([A-Za-z.]+)\)' | head -1 | tr -d '()')
  case $code in
    DryRunOperation) ROWS+=("| $what | ok (dry run) |"); return 0 ;;
    AccessDenied* | UnauthorizedOperation | AuthorizationError | *NotAuthorized*)
      ROWS+=("| $what | **denied** ($code) |"); DENIED=$((DENIED + 1)) ;;
    *) ROWS+=("| $what | error: $(printf '%s' "$out" | tr '\n|' '  ' | cut -c1-120) |"); DENIED=$((DENIED + 1)) ;;
  esac
  return 1
}

ME=$(aws_ sts get-caller-identity --query Arn) || { echo "no AWS credentials (Start Lab, AWS Details)" >&2; exit 2; }
ACCOUNT=$(aws_ sts get-caller-identity --query Account)
echo "[r2] identity: $ME, region $REGION" >&2

VPC=$(aws_ ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId')
SUBNETS=$(aws_ ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC" "Name=default-for-az,Values=true" \
  --query 'Subnets[0:2].SubnetId')
SG=$(aws_ ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC" Name=group-name,Values=default \
  --query 'SecurityGroups[0].GroupId')
AMI=$(aws_ ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query Parameter.Value)

probe "EC2: describe VPC / subnets (default VPC $VPC)" test -n "$VPC" -a "$VPC" != None
probe "IAM: read LabInstanceProfile" aws_ iam get-instance-profile --instance-profile-name LabInstanceProfile
probe "EC2: run t3.small with LabInstanceProfile" aws_ ec2 run-instances --dry-run --image-id "$AMI" \
  --instance-type t3.small --iam-instance-profile Name=LabInstanceProfile --subnet-id "${SUBNETS%%[[:space:]]*}"

# network module (#23) and the state bucket (#22)
if probe "EC2: create / delete VPC" aws_ ec2 create-vpc --cidr-block 10.249.0.0/16 --query Vpc.VpcId; then
  aws_ ec2 delete-vpc --vpc-id "$LAST" >/dev/null 2>&1
fi
B="$TAG-$ACCOUNT"
if probe "S3: create bucket + versioning" aws_ s3api create-bucket --bucket "$B"; then
  probe "S3: put versioning" aws_ s3api put-bucket-versioning --bucket "$B" --versioning-configuration Status=Enabled
  aws_ s3api delete-bucket --bucket "$B" >/dev/null 2>&1
fi
if probe "SSM: put SecureString parameter" aws_ ssm put-parameter --name "/$TAG/x" --type SecureString --value x; then
  aws_ ssm delete-parameter --name "/$TAG/x" >/dev/null 2>&1
fi

# ALB (#24)
if probe "ELB: create / delete target group" aws_ elbv2 create-target-group --name "$TAG" --protocol HTTP --port 8080 \
  --vpc-id "$VPC" --target-type instance --query 'TargetGroups[0].TargetGroupArn'; then
  TG=$LAST
fi
# shellcheck disable=SC2086
if probe "ELB: create / delete ALB" aws_ elbv2 create-load-balancer --name "$TAG" --subnets $SUBNETS --security-groups "$SG"   --query 'LoadBalancers[0].LoadBalancerArn'; then
  LB=$LAST
  if [ -n "${TG:-}" ]; then
    probe "ELB: weighted forward listener" aws_ elbv2 create-listener --load-balancer-arn "$LB" --protocol HTTP --port 80 \
      --default-actions "Type=forward,ForwardConfig={TargetGroups=[{TargetGroupArn=$TG,Weight=100}],TargetGroupStickinessConfig={Enabled=true,DurationSeconds=300}}"
  fi
  aws_ elbv2 delete-load-balancer --load-balancer-arn "$LB" >/dev/null 2>&1
  aws_ elbv2 wait load-balancers-deleted --load-balancer-arns "$LB" >/dev/null 2>&1
fi
[ -n "${TG:-}" ] && aws_ elbv2 delete-target-group --target-group-arn "$TG" >/dev/null 2>&1

# ASG (#25)
if probe "EC2: create launch template" aws_ ec2 create-launch-template --launch-template-name "$TAG" \
  --launch-template-data "{\"ImageId\":\"$AMI\",\"InstanceType\":\"t3.small\",\"IamInstanceProfile\":{\"Name\":\"LabInstanceProfile\"}}"; then
  if probe "ASG: create group (0 instances)" aws_ autoscaling create-auto-scaling-group --auto-scaling-group-name "$TAG" \
    --launch-template "LaunchTemplateName=$TAG,Version=\$Latest" --min-size 0 --max-size 0 \
    --vpc-zone-identifier "$(echo $SUBNETS | tr ' ' ',')"; then
    probe "ASG: target tracking policy" aws_ autoscaling put-scaling-policy --auto-scaling-group-name "$TAG" \
      --policy-name "$TAG" --policy-type TargetTrackingScaling \
      --target-tracking-configuration '{"PredefinedMetricSpecification":{"PredefinedMetricType":"ASGAverageCPUUtilization"},"TargetValue":50}'
    probe "ASG: instance refresh API" aws_ autoscaling describe-instance-refreshes --auto-scaling-group-name "$TAG"
    aws_ autoscaling delete-auto-scaling-group --auto-scaling-group-name "$TAG" --force-delete >/dev/null 2>&1
  fi
  aws_ ec2 delete-launch-template --launch-template-name "$TAG" >/dev/null 2>&1
fi

# monitoring (#26) and aiops (#36)
if probe "CloudWatch: put / delete dashboard" aws_ cloudwatch put-dashboard --dashboard-name "$TAG" \
  --dashboard-body '{"widgets":[{"type":"text","x":0,"y":0,"width":6,"height":2,"properties":{"markdown":"r2"}}]}'; then
  aws_ cloudwatch delete-dashboards --dashboard-names "$TAG" >/dev/null 2>&1
fi
if probe "CloudWatch: put / delete alarm" aws_ cloudwatch put-metric-alarm --alarm-name "$TAG" --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count --statistic Sum --period 60 --evaluation-periods 1 --threshold 5 \
  --comparison-operator GreaterThanThreshold; then
  aws_ cloudwatch delete-alarms --alarm-names "$TAG" >/dev/null 2>&1
fi
if probe "CloudWatch: anomaly detection alarm" aws_ cloudwatch put-metric-alarm --alarm-name "$TAG-ad" \
  --evaluation-periods 1 --comparison-operator GreaterThanUpperThreshold --threshold-metric-id band \
  --metrics '[{"Id":"m1","ReturnData":true,"MetricStat":{"Metric":{"Namespace":"AWS/ApplicationELB","MetricName":"RequestCount"},"Period":60,"Stat":"Sum"}},{"Id":"band","Expression":"ANOMALY_DETECTION_BAND(m1, 2)","ReturnData":true}]'; then
  aws_ cloudwatch delete-alarms --alarm-names "$TAG-ad" >/dev/null 2>&1
fi
if probe "SNS: create / delete topic" aws_ sns create-topic --name "$TAG"; then
  aws_ sns delete-topic --topic-arn "arn:aws:sns:$REGION:$ACCOUNT:$TAG" >/dev/null 2>&1
fi
if probe "Logs: create / delete log group" aws_ logs create-log-group --log-group-name "/$TAG"; then
  aws_ logs delete-log-group --log-group-name "/$TAG" >/dev/null 2>&1
fi


{
  echo "R2 on $(date -u +%FT%TZ), identity \`$ME\`, region $REGION"
  echo
  echo "| Action | Result |"
  echo "|---|---|"
  printf '%s\n' "${ROWS[@]}"
  echo
  echo "$DENIED of ${#ROWS[@]} not allowed."
} | tee ${OUT:+"$OUT"}
[ "$DENIED" -eq 0 ]
