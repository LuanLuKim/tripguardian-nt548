resource "aws_ecr_repository" "web" {
  name = "nt548-ecs-lab-web"
}

resource "aws_ecs_task_definition" "web" {
  family                   = "nt548-ecs-lab-web"
  requires_compatibilities = ["EC2"]
  network_mode             = "bridge"
  memory                   = "384"

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = "${aws_ecr_repository.web.repository_url}:lab-v1"
      cpu       = 256
      memory    = 256
      essential = true

      environment = [
        { name = "HARNESS_HOST", value = aws_lb.harness.dns_name },
        { name = "HARNESS_PORT", value = tostring(aws_lb_listener.harness.port) }
      ]
    }
  ])
}

resource "aws_ecs_service" "web" {
  name            = "web"
  cluster         = aws_ecs_cluster.lab.id
  task_definition = aws_ecs_task_definition.web.arn
  launch_type     = "EC2"
  desired_count   = 1

  depends_on = [aws_ecs_service.harness, aws_vpc_security_group_ingress_rule.harness_alb_from_app]
}

output "web_repository_url" {
  value = aws_ecr_repository.web.repository_url
}
