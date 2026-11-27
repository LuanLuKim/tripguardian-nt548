output "asg_name" {
  description = "Name of this color's auto scaling group (envs/demo exports it as asg_name_<color>)."
  value       = aws_autoscaling_group.app.name
}

output "asg_arn" {
  value = aws_autoscaling_group.app.arn
}

output "launch_template_id" {
  value = aws_launch_template.app.id
}

output "launch_template_version" {
  description = "Version the group runs; it changes with image_tag and data_release."
  value       = aws_launch_template.app.latest_version
}

output "runs" {
  description = "What the instances run: the image tag (or placeholder) and the data release."
  value       = { image_tag = local.tags.image_tag, data_release = var.data_release }
}
