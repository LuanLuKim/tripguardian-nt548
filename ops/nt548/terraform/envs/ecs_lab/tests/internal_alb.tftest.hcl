mock_provider "aws" {}

run "harness_registers_with_a_load_balancer" {
  command = plan

  assert {
    condition     = try(one(aws_ecs_service.harness.load_balancer).container_port == 8769, false)
    error_message = "The harness service must register container port 8769 with a target group."
  }

  assert {
    condition     = aws_lb.harness.internal && aws_lb_target_group.harness.target_type == "instance"
    error_message = "The internal ALB must route to EC2 instance and host port targets."
  }

  assert {
    condition     = one(aws_lb_target_group.harness.health_check).path == "/api/harness/nt548-version"
    error_message = "The health check must use the harness stub's version endpoint."
  }
}
