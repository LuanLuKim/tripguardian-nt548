"""ops/nt548/aws_r2_probe.sh (#22) against a fake `aws`: the table, denied actions, dry runs and the clean-up."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "ops" / "nt548" / "aws_r2_probe.sh"
BASH = shutil.which("bash")

# Fake aws CLI: answers the reads the probe needs, fails the operations listed in FAKE_DENY with AccessDenied, and
# logs every call to FAKE_LOG.
FAKE_AWS = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
args=" $* "
op=""
for a in "$@"; do case $a in --*|us-east-1|text) ;; *) [ -z "$svc" ] && svc=$a || { op=$a; break; } ;; esac; done
for d in $FAKE_DENY; do
  if [ "$op" = "$d" ]; then
    echo "An error occurred (AccessDeniedException) when calling the $op operation: denied" >&2; exit 254
  fi
done
case "$svc $op" in
  "sts get-caller-identity") case $args in *Account*) echo 111111111111 ;; *) echo arn:aws:sts::111111111111:assumed-role/LabRole/x ;; esac ;;
  "ec2 describe-vpcs") echo vpc-1 ;;
  "ec2 describe-subnets") printf 'subnet-a\tsubnet-b\n' ;;
  "ec2 describe-security-groups") echo sg-1 ;;
  "ssm get-parameter") echo ami-1 ;;
  "ec2 run-instances") echo "An error occurred (DryRunOperation) when calling the RunInstances operation" >&2; exit 254 ;;
  "ec2 create-vpc") echo vpc-new ;;
  "elbv2 create-target-group") echo arn:aws:elasticloadbalancing:us-east-1:111111111111:targetgroup/t/1 ;;
  "elbv2 create-load-balancer") echo arn:aws:elasticloadbalancing:us-east-1:111111111111:loadbalancer/app/t/1 ;;
  *) echo "ok $op" ;;
esac
"""


@pytest.fixture
def fake(tmp_path: Path) -> dict:
    aws = tmp_path / "aws"
    aws.write_text(FAKE_AWS, newline="\n")
    aws.chmod(0o755)
    return {"aws": aws, "log": tmp_path / "calls.log", "out": tmp_path / "r2.md"}


def run(fake: dict, deny: str = "") -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin", "AWS": str(fake["aws"]), "FAKE_LOG": str(fake["log"]), "FAKE_DENY": deny,
           "AWS_REGION": "us-east-1"}
    return subprocess.run([BASH, str(PROBE), "--out", str(fake["out"])], env=env, capture_output=True, text=True,
                          timeout=60)


pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")


def test_everything_allowed_exits_0_and_cleans_up(fake):
    r = run(fake)
    assert r.returncode == 0, r.stderr + r.stdout
    table = fake["out"].read_text()
    assert "0 of " in table and "**denied**" not in table
    assert "| EC2: run t3.small with LabInstanceProfile | ok (dry run) |" in table
    calls = fake["log"].read_text()
    for cleanup in ("delete-vpc --vpc-id vpc-new", "delete-load-balancer", "delete-target-group", "delete-auto-scaling-group",
                    "delete-launch-template", "delete-dashboards", "delete-alarms", "delete-topic", "delete-log-group",
                    "delete-bucket", "delete-parameter"):
        assert cleanup in calls, f"{cleanup} not called"


def test_denied_action_is_marked_and_exit_1(fake):
    r = run(fake, deny="create-topic put-dashboard")
    assert r.returncode == 1
    table = fake["out"].read_text()
    assert "| SNS: create / delete topic | **denied** (AccessDeniedException) |" in table
    assert "| CloudWatch: put / delete dashboard | **denied** (AccessDeniedException) |" in table
    assert "2 of " in table
    calls = fake["log"].read_text()
    assert "delete-topic" not in calls and "delete-dashboards" not in calls  # nothing was created


def test_denied_asg_skips_its_policy_but_still_deletes_the_template(fake):
    r = run(fake, deny="create-auto-scaling-group")
    assert r.returncode == 1
    table = fake["out"].read_text()
    assert "target tracking policy" not in table
    assert "delete-launch-template" in fake["log"].read_text()


def test_no_credentials_exit_2(fake):
    r = run(fake, deny="get-caller-identity")
    assert r.returncode == 2
    assert "no AWS credentials" in r.stderr
