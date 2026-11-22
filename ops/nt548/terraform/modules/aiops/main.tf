# AIOps (#36): CloudWatch Anomaly Detection alarms per target group (one per color) on the ALB metrics.
# The band is a model CloudWatch trains on the metric's own history (trend, hour of day, day of week); an alarm
# fires when the metric leaves it. Fixed thresholds stay in the monitoring module (#26); this module only adds the
# learned ones, so the two can be compared on the same incident (docs/nt548/04-aiops.md).
# Alarm names start with "<name_prefix>-", which is what ops/nt548/aiops/incident.py watch --prefix reads (#38).

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
  # comparison: latency and errors only alarm upward; a drop in requests also matters (traffic lost at the ALB).
  metrics = {
    latency = {
      metric     = "TargetResponseTime"
      stat       = "p95"
      comparison = "GreaterThanUpperThreshold"
      what       = "p95 latency above the expected band"
    }
    errors = {
      metric     = "HTTPCode_Target_5XX_Count"
      stat       = "Sum"
      comparison = "GreaterThanUpperThreshold"
      what       = "5xx from targets above the expected band"
    }
    requests = {
      metric     = "RequestCount"
      stat       = "Sum"
      comparison = "LessThanLowerOrGreaterThanUpperThreshold"
      what       = "request count outside the expected band"
    }
  }

  alarms = {
    for pair in setproduct(sort(keys(var.target_groups)), sort(keys(local.metrics))) :
    "${pair[0]}-${pair[1]}" => merge(local.metrics[pair[1]], {
      color        = pair[0]
      kind         = pair[1]
      target_group = var.target_groups[pair[0]]
    })
  }
}

resource "aws_cloudwatch_metric_alarm" "anomaly" {
  for_each = local.alarms

  alarm_name          = "${var.name_prefix}-${each.key}-anomaly"
  alarm_description   = "AIOps #36: ${each.value.color} ${each.value.what} (band width ${var.band_width} sd)."
  comparison_operator = each.value.comparison
  evaluation_periods  = var.evaluation_periods
  datapoints_to_alarm = var.datapoints_to_alarm
  threshold_metric_id = "band"
  treat_missing_data  = "notBreaching" # no request in a minute is not an incident
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions

  metric_query {
    id          = "m1"
    return_data = true
    metric {
      namespace   = "AWS/ApplicationELB"
      metric_name = each.value.metric
      stat        = each.value.stat
      period      = var.period
      dimensions = {
        LoadBalancer = var.alb_arn_suffix
        TargetGroup  = each.value.target_group
      }
    }
  }

  metric_query {
    id          = "band"
    expression  = "ANOMALY_DETECTION_BAND(m1, ${var.band_width})"
    label       = "${each.value.metric} (expected)"
    return_data = true
  }

  tags = merge(var.tags, { "nt548:block" = "aiops", "nt548:color" = each.value.color })
}
