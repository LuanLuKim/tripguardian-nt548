mock_provider "aws" {}

run "public_web_routes_to_ecs" {
  command = plan

  override_resource {
    target          = aws_ecr_repository.web
    values          = { repository_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com/nt548-ecs-lab-web" }
    override_during = plan
  }

  override_resource {
    target          = aws_lb.harness
    override_during = plan
    values = {
      arn      = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/nt548-ecs-lab-harness/0123456789abcdef"
      dns_name = "internal-harness.example.com"
    }
  }

  assert {
    condition     = !aws_lb.web.internal && aws_lb.harness.internal && aws_lb_listener.web.port == 80
    error_message = "Only the web ALB must expose an internet-facing HTTP listener."
  }

  assert {
    condition     = one(aws_ecs_service.web.load_balancer).container_port == aws_lb_target_group.web.port && aws_lb_target_group.web.target_type == "instance"
    error_message = "ECS must register each web task's instance and mapped port with the web target group."
  }

  assert {
    condition     = one(jsondecode(aws_ecs_task_definition.web.container_definitions)[0].portMappings).containerPort == 8080
    error_message = "The web task must publish the edge container port."
  }

  assert {
    condition     = one(aws_lb_target_group.web.health_check).path == "/" && one(aws_lb_target_group.web.health_check).matcher == "200"
    error_message = "The web ALB must check that the SPA responds successfully."
  }

  assert {
    condition     = one(one(aws_lb_listener_rule.web_reject_cloudflare_ip.condition).http_header).values == toset(["*"]) && one(one(aws_lb_listener_rule.web_reject_cloudflare_ip.action).fixed_response).status_code == "400"
    error_message = "The public web listener must reject client-supplied Cloudflare IP headers."
  }
}
