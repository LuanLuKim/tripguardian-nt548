# Monitoring (#26): one CloudWatch dashboard, fixed-threshold alarms per color, an SNS topic for them, and the log
# groups the app containers write to (awslogs driver, modules/app_asg). The learned thresholds (Anomaly Detection)
# are in modules/aiops (#36); both notify the same topic, so the two can be compared on the same incident.
#
# Alarm names: <name_prefix>-<color>-<kind> (and <name_prefix>-alb-5xx), which is what
#   ops/nt548/aiops/incident.py watch --prefix <name_prefix>- --log-group /<name_prefix>/app-{color}
# reads (#38).

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  tags   = merge(var.tags, { project = "nt548", "nt548:block" = "monitoring" })
  colors = sort(keys(var.target_groups))

  # kind => what the alarm watches on one color's target group
  kinds = {
    "5xx" = {
      metric     = "HTTPCode_Target_5XX_Count"
      stat       = "Sum"
      comparison = "GreaterThanThreshold"
      threshold  = var.errors_per_minute
      what       = "more than ${var.errors_per_minute} 5xx a minute from the targets"
    }
    p95 = {
      metric     = "TargetResponseTime"
      stat       = "p95"
      comparison = "GreaterThanThreshold"
      threshold  = var.p95_seconds
      what       = "p95 latency above ${var.p95_seconds} s"
    }
    unhealthy = {
      metric     = "UnHealthyHostCount"
      stat       = "Maximum"
      comparison = "GreaterThanThreshold"
      threshold  = 0
      what       = "an instance fails the health check"
    }
    "no-healthy" = {
      metric     = "HealthyHostCount"
      stat       = "Minimum"
      comparison = "LessThanThreshold"
      threshold  = 1
      what       = "no healthy instance left"
    }
  }

  alarms = {
    for pair in setproduct(local.colors, sort(keys(local.kinds))) :
    "${pair[0]}-${pair[1]}" => merge(local.kinds[pair[1]], { color = pair[0] })
  }

  log_groups = { for c in local.colors : c => "/${var.name_prefix}/app-${c}" }
}

# ---------- notifications ----------

resource "aws_sns_topic" "alarms" {
  name = "${var.name_prefix}-alarms"
  tags = local.tags
}

# The address confirms by clicking the mail AWS sends; until then nothing is delivered.
resource "aws_sns_topic_subscription" "email" {
  count = var.alarm_email == "" ? 0 : 1

  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# ---------- container logs ----------

resource "aws_cloudwatch_log_group" "app" {
  for_each = local.log_groups

  name              = each.value
  retention_in_days = var.log_retention_days
  tags              = merge(local.tags, { "nt548:color" = each.key })
}

# ---------- alarms ----------

resource "aws_cloudwatch_metric_alarm" "color" {
  for_each = local.alarms

  alarm_name          = "${var.name_prefix}-${each.key}"
  alarm_description   = "Monitoring #26: ${each.value.color} ${each.value.what}."
  namespace           = "AWS/ApplicationELB"
  metric_name         = each.value.metric
  statistic           = each.value.stat == "p95" ? null : each.value.stat
  extended_statistic  = each.value.stat == "p95" ? "p95" : null
  period              = var.period
  evaluation_periods  = var.evaluation_periods
  datapoints_to_alarm = var.datapoints_to_alarm
  comparison_operator = each.value.comparison
  threshold           = each.value.threshold
  # no request in a minute is not an incident; a missing host count is (the color has no instance at all)
  treat_missing_data = each.value.metric == "HealthyHostCount" ? "breaching" : "notBreaching"
  alarm_actions      = [aws_sns_topic.alarms.arn]
  ok_actions         = [aws_sns_topic.alarms.arn]

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_groups[each.value.color]
  }

  tags = merge(local.tags, { "nt548:color" = each.value.color })
}

# 5xx made by the ALB itself (502/503/504: no healthy target, a target that hung up), whatever the color.
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.name_prefix}-alb-5xx"
  alarm_description   = "Monitoring #26: more than ${var.errors_per_minute} 5xx a minute made by the ALB (no healthy target, timeouts)."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_ELB_5XX_Count"
  statistic           = "Sum"
  period              = var.period
  evaluation_periods  = var.evaluation_periods
  datapoints_to_alarm = var.datapoints_to_alarm
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.errors_per_minute
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  tags = local.tags
}

# ---------- dashboard ----------

locals {
  tg_metric = { for c in local.colors : c => {
    for m in ["RequestCount", "HTTPCode_Target_5XX_Count", "TargetResponseTime", "HealthyHostCount", "UnHealthyHostCount"] :
    m => ["AWS/ApplicationELB", m, "LoadBalancer", var.alb_arn_suffix, "TargetGroup", var.target_groups[c]]
  } }

  widget = {
    for k, w in {
      requests = { title = "Requests / min by color", metric = "RequestCount", stat = "Sum" }
      errors   = { title = "5xx from targets / min by color", metric = "HTTPCode_Target_5XX_Count", stat = "Sum" }
      latency  = { title = "p95 latency (s) by color", metric = "TargetResponseTime", stat = "p95" }
      healthy  = { title = "Healthy instances by color", metric = "HealthyHostCount", stat = "Minimum" }
      } : k => {
      type   = "metric"
      width  = 12
      height = 6
      properties = {
        title   = w.title
        region  = var.region
        view    = "timeSeries"
        stat    = w.stat
        period  = var.period
        metrics = [for c in local.colors : concat(local.tg_metric[c][w.metric], [{ label = c, color = var.colors[c] }])]
      }
    }
  }

  widgets = concat(
    [for k in ["requests", "errors", "latency", "healthy"] : local.widget[k]],
    [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "CPU of each color's ASG (%), target ${var.cpu_target}"
          region = var.region
          view   = "timeSeries"
          stat   = "Average"
          period = var.period
          metrics = [for c in local.colors : ["AWS/EC2", "CPUUtilization", "AutoScalingGroupName", var.asg_names[c],
          { label = c, color = var.colors[c] }]]
          annotations = { horizontal = [{ value = var.cpu_target, label = "target" }] }
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "Instances in service by color"
          region = var.region
          view   = "timeSeries"
          stat   = "Maximum"
          period = var.period
          metrics = [for c in local.colors : ["AWS/AutoScaling", "GroupInServiceInstances", "AutoScalingGroupName",
          var.asg_names[c], { label = c, color = var.colors[c] }]]
        }
      },
      {
        type   = "alarm"
        width  = 24
        height = 4
        properties = {
          title  = "Alarms"
          alarms = concat([for a in aws_cloudwatch_metric_alarm.color : a.arn], [aws_cloudwatch_metric_alarm.alb_5xx.arn], var.extra_alarm_arns)
        }
      },
    ],
  )
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.name_prefix
  dashboard_body = jsonencode({ widgets = local.widgets })
}
