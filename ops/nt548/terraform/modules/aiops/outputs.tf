output "alarm_names" {
  description = "<color>-<latency|errors|requests> => alarm name."
  value       = { for k, a in aws_cloudwatch_metric_alarm.anomaly : k => a.alarm_name }
}

output "alarm_arns" {
  value = { for k, a in aws_cloudwatch_metric_alarm.anomaly : k => a.arn }
}
