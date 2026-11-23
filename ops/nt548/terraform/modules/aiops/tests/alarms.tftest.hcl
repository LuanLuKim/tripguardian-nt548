# terraform -chdir=ops/nt548/terraform/modules/aiops init -backend=false && terraform -chdir=... test
# Mocked provider: no AWS account or credentials needed.

mock_provider "aws" {}

variables {
  name_prefix    = "nt548"
  alb_arn_suffix = "app/nt548-alb/0123456789abcdef"
  target_groups = {
    blue  = "targetgroup/nt548-blue/aaaa"
    green = "targetgroup/nt548-green/bbbb"
  }
}

run "one_alarm_per_color_and_metric" {
  command = plan

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.anomaly) == 6
    error_message = "expected 2 colors x 3 metrics"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.anomaly["blue-latency"].alarm_name == "nt548-blue-latency-anomaly"
    error_message = "alarm names must start with name_prefix (incident.py watch --prefix)"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.anomaly["green-requests"].comparison_operator == "LessThanLowerOrGreaterThanUpperThreshold"
    error_message = "a drop in requests must alarm too"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.anomaly["blue-errors"].threshold_metric_id == "band"
    error_message = "the threshold is the anomaly band, not a fixed number"
  }
}

run "band_width_reaches_the_expression" {
  command = plan

  variables {
    band_width    = 3
    target_groups = { blue = "targetgroup/nt548-blue/aaaa" }
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.anomaly) == 3
    error_message = "one color gives 3 alarms"
  }

  assert {
    condition = anytrue([for q in aws_cloudwatch_metric_alarm.anomaly["blue-latency"].metric_query :
    q.expression == "ANOMALY_DETECTION_BAND(m1, 3)"])
    error_message = "band_width must reach ANOMALY_DETECTION_BAND"
  }
}

run "no_target_group_is_rejected" {
  command = plan

  variables {
    target_groups = {}
  }

  expect_failures = [var.target_groups]
}
