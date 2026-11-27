output "alb_dns_name" {
  description = "http://<this>/ is the app (contract §7.1)."
  value       = aws_lb.this.dns_name
}

output "alb_arn" {
  value = aws_lb.this.arn
}

output "alb_arn_suffix" {
  description = "LoadBalancer dimension of the AWS/ApplicationELB metrics (monitoring #26, aiops #36)."
  value       = aws_lb.this.arn_suffix
}

output "target_group_arns" {
  description = "color => target group ARN (the ASG of each color registers there, #25)."
  value       = { for c, tg in aws_lb_target_group.color : c => tg.arn }
}

output "target_group_arn_suffixes" {
  description = "color => TargetGroup dimension of the metrics."
  value       = { for c, tg in aws_lb_target_group.color : c => tg.arn_suffix }
}

output "weights" {
  description = "color => percent of new users, as the listener has it."
  value       = local.weight
}
