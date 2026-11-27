output "sns_topic_arn" {
  description = "Topic every alarm notifies; modules/aiops sends its anomaly alarms there too."
  value       = aws_sns_topic.alarms.arn
}

output "log_group_names" {
  description = "color => CloudWatch Logs group of the app containers (/<name_prefix>/app-<color>)."
  value       = { for c, g in aws_cloudwatch_log_group.app : c => g.name }
}

output "alarm_names" {
  description = "<color>-<5xx|p95|unhealthy|no-healthy> and alb-5xx => alarm name."
  value = merge({ for k, a in aws_cloudwatch_metric_alarm.color : k => a.alarm_name },
  { "alb-5xx" = aws_cloudwatch_metric_alarm.alb_5xx.alarm_name })
}

output "dashboard_url" {
  value = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards/dashboard/${aws_cloudwatch_dashboard.this.dashboard_name}"
}
