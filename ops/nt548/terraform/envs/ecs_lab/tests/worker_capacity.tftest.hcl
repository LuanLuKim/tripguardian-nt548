mock_provider "aws" {}

run "two_harness_tasks_require_two_managed_workers" {
  command = plan

  assert {
    condition     = try(one(aws_ecs_service.harness.placement_constraints).type == "distinctInstance", false)
    error_message = "The harness replicas must be scheduled on distinct EC2 instances."
  }

  assert {
    condition     = aws_appautoscaling_target.harness.max_capacity == 2
    error_message = "The harness scaling ceiling must fit the two-worker lab."
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
