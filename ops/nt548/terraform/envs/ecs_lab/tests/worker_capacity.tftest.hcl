mock_provider "aws" {
  mock_data "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/LabRole" }
  }
}

run "services_scale_on_shared_workers" {
  command = plan

  variables {
    harness_image_tag = "lab-v1"
  }

  assert {
    condition     = length(aws_ecs_service.harness.placement_constraints) == 0
    error_message = "Multiple harness tasks must be able to share a worker."
  }

  assert {
    condition     = aws_appautoscaling_target.harness.min_capacity == 1 && aws_appautoscaling_target.harness.max_capacity == 3
    error_message = "The real harness must scale from one to three tasks."
  }

  assert {
    condition     = aws_appautoscaling_target.web.min_capacity == 1 && aws_appautoscaling_target.web.max_capacity == 2
    error_message = "Web must scale from one to two tasks."
  }

  assert {
    condition     = aws_appautoscaling_policy.web_cpu.resource_id == aws_appautoscaling_target.web.resource_id
    error_message = "The web CPU scaling policy must apply to the web service."
  }

  assert {
    condition = alltrue([
      for service in [aws_ecs_service.harness, aws_ecs_service.web] :
      try(one(service.ordered_placement_strategy).type == "binpack" && one(service.ordered_placement_strategy).field == "memory", false)
    ])
    error_message = "Both services must pack tasks onto existing workers based on memory."
  }

  assert {
    condition     = aws_autoscaling_group.workers.min_size == 1 && aws_autoscaling_group.workers.max_size == 2
    error_message = "The lab must maintain one worker and allow expansion to two."
  }

  assert {
    condition     = one(aws_ecs_service.harness.capacity_provider_strategy).capacity_provider == aws_ecs_capacity_provider.workers.name
    error_message = "The harness service must use the ASG-backed capacity provider."
  }
}
