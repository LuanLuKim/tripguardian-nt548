output "vpc_id" {
  description = "The bootstrap's VPC, found by name."
  value       = data.aws_vpc.this.id
}

# ---------- contract with the deploy workflow (design §7.1) ----------

output "alb_dns_name" {
  description = "The app is http://<alb_dns_name>/."
  value       = module.alb.alb_dns_name
}

output "target_group_arn_blue" {
  value = module.alb.target_group_arns["blue"]
}

output "target_group_arn_green" {
  value = module.alb.target_group_arns["green"]
}

output "weight_blue" {
  description = "The input echoed back: ops/nt548/deploy_aws.sh reads the live color from the state (#50)."
  value       = var.weight_blue
}

output "asg_name_blue" {
  value = module.app["blue"].asg_name
}

output "asg_name_green" {
  value = module.app["green"].asg_name
}

# The inputs echoed back, so the state alone says what runs (#50 reads them).
output "image_tag_blue" {
  value = var.image_tag_blue
}

output "image_tag_green" {
  value = var.image_tag_green
}

output "data_release_blue" {
  value = var.data_release_blue
}

output "data_release_green" {
  value = var.data_release_green
}

# ---------- monitoring (#26) ----------

output "dashboard_url" {
  value = module.monitoring.dashboard_url
}

output "sns_topic_arn" {
  value = module.monitoring.sns_topic_arn
}

output "log_group_names" {
  description = "color => log group of the app containers (log_patterns.py --log-group, incident.py watch --log-group)."
  value       = module.monitoring.log_group_names
}

output "alarm_names" {
  description = "Fixed (monitoring) and learned (aiops) alarms; all start with <name_prefix>-."
  value       = merge(module.monitoring.alarm_names, { for k, n in module.aiops.alarm_names : "${k}-anomaly" => n })
}
