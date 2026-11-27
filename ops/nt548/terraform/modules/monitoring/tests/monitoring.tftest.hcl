# terraform -chdir=ops/nt548/terraform/modules/monitoring init -backend=false && terraform -chdir=... test
# Mocked provider: no AWS account or credentials needed.

mock_provider "aws" {
  mock_resource "aws_sns_topic" {
    defaults = {
      arn = "arn:aws:sns:us-east-1:111111111111:nt548-alarms"
    }
  }
  mock_resource "aws_cloudwatch_metric_alarm" {
    defaults = {
      arn = "arn:aws:cloudwatch:us-east-1:111111111111:alarm:nt548-x"
    }
  }
}

variables {
  name_prefix    = "nt548"
  alb_arn_suffix = "app/nt548-alb/0123456789abcdef"
  target_groups = {
    blue  = "targetgroup/nt548-blue/aaaa"
    green = "targetgroup/nt548-green/bbbb"
  }
  asg_names = { blue = "nt548-blue", green = "nt548-green" }
}

run "four_alarms_per_color_and_one_for_the_alb" {
  command = apply

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.color) == 8
    error_message = "2 colors x (5xx, p95, unhealthy, no-healthy)"
  }

  assert {
    condition = alltrue([for n in values(output.alarm_names) : startswith(n, "nt548-")]) && (
    output.alarm_names["green-unhealthy"] == "nt548-green-unhealthy")
    error_message = "names <prefix>-<color>-<kind>: incident.py watch --prefix finds them and reads the color"
  }

  assert {
    condition = (aws_cloudwatch_metric_alarm.color["blue-5xx"].dimensions["TargetGroup"] == "targetgroup/nt548-blue/aaaa"
    && aws_cloudwatch_metric_alarm.color["blue-5xx"].dimensions["LoadBalancer"] == "app/nt548-alb/0123456789abcdef")
    error_message = "a color's alarms watch that color's target group on the ALB"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.alb_5xx.metric_name == "HTTPCode_ELB_5XX_Count" && !contains(keys(aws_cloudwatch_metric_alarm.alb_5xx.dimensions), "TargetGroup")
    error_message = "the ALB's own 5xx (no healthy target) are watched for the whole ALB"
  }

  assert {
    condition     = alltrue([for a in values(aws_cloudwatch_metric_alarm.color) : a.alarm_actions == toset(["arn:aws:sns:us-east-1:111111111111:nt548-alarms"])])
    error_message = "every alarm notifies the SNS topic"
  }
}

run "thresholds" {
  command = plan

  variables {
    p95_seconds = 0.8
  }

  assert {
    condition = (aws_cloudwatch_metric_alarm.color["blue-p95"].extended_statistic == "p95"
    && aws_cloudwatch_metric_alarm.color["blue-p95"].threshold == 0.8)
    error_message = "latency alarms on p95 at p95_seconds"
  }

  assert {
    condition = (aws_cloudwatch_metric_alarm.color["green-unhealthy"].metric_name == "UnHealthyHostCount"
    && aws_cloudwatch_metric_alarm.color["green-unhealthy"].threshold == 0)
    error_message = "one failing instance is enough (health check per instance, lesson of #39)"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.color["blue-no-healthy"].treat_missing_data == "breaching"
    error_message = "no host count at all means the color is gone"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.color["blue-5xx"].treat_missing_data == "notBreaching"
    error_message = "a minute without requests is not an incident"
  }
}

run "log_group_per_color_matches_log_patterns" {
  command = plan

  assert {
    condition     = output.log_group_names == { blue = "/nt548/app-blue", green = "/nt548/app-green" }
    error_message = "/<prefix>/app-<color>, as log_patterns.py --log-group reads it"
  }

  assert {
    condition     = aws_cloudwatch_log_group.app["blue"].retention_in_days == 7
    error_message = "logs are kept a week, not forever"
  }
}

run "email_only_when_given" {
  command = plan

  assert {
    condition     = length(aws_sns_topic_subscription.email) == 0
    error_message = "no address, no subscription"
  }
}

run "email_subscription" {
  command = plan

  variables {
    alarm_email = "team@example.com"
  }

  assert {
    condition     = aws_sns_topic_subscription.email[0].protocol == "email" && aws_sns_topic_subscription.email[0].endpoint == "team@example.com"
    error_message = "the address gets the alarms by mail"
  }
}

run "dashboard_shows_both_colors" {
  command = apply

  assert {
    condition     = length(jsondecode(aws_cloudwatch_dashboard.this.dashboard_body).widgets) == 7
    error_message = "requests, 5xx, p95, healthy, CPU, instances, alarms"
  }

  assert {
    condition = alltrue([for w in slice(jsondecode(aws_cloudwatch_dashboard.this.dashboard_body).widgets, 0, 6) :
    length(w.properties.metrics) == 2])
    error_message = "every metric widget has a line per color"
  }

  assert {
    condition     = strcontains(aws_cloudwatch_dashboard.this.dashboard_body, "\"AutoScalingGroupName\",\"nt548-green\"")
    error_message = "the CPU widget reads the ASG of each color"
  }
}
