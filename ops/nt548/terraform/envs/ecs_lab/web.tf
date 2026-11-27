resource "aws_ecr_repository" "web" {
  name = "nt548-ecs-lab-web"
}

locals {
  web_container_port = 8080
  web_url            = "http://${aws_lb.web.dns_name}"
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
      # The web server listens on loopback; edge exposes it on the container interface.
      command = ["sh", "-ec", "node edge.mjs & exec node server.mjs"]

      environment = [
        { name = "EDGE_PORT", value = tostring(local.web_container_port) },
        { name = "HARNESS_HOST", value = aws_lb.harness.dns_name },
        { name = "HARNESS_PORT", value = tostring(aws_lb_listener.harness.port) }
      ]

      portMappings = [
        { containerPort = local.web_container_port }
      ]
    }
  ])
}

resource "aws_ecs_service" "web" {
  name                 = "web"
  cluster              = aws_ecs_cluster.lab.id
  task_definition      = aws_ecs_task_definition.web.arn
  desired_count        = 1
  force_new_deployment = true

  capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.workers.name
    weight            = 1
  }

  ordered_placement_strategy {
    type  = "binpack"
    field = "memory"
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = local.web_container_port
  }

  depends_on = [
    aws_ecs_service.harness,
    aws_vpc_security_group_ingress_rule.harness_alb_from_app,
    aws_lb_listener_rule.web_reject_cloudflare_ip,
    aws_vpc_security_group_ingress_rule.web_tasks_from_alb
  ]

  lifecycle {
    ignore_changes = [desired_count]
  }
}

resource "aws_appautoscaling_target" "web" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.lab.name}/${aws_ecs_service.web.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = 2
}

resource "aws_appautoscaling_policy" "web_cpu" {
  name               = "nt548-ecs-lab-web-cpu"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.web.service_namespace
  resource_id        = aws_appautoscaling_target.web.resource_id
  scalable_dimension = aws_appautoscaling_target.web.scalable_dimension

  target_tracking_scaling_policy_configuration {
    target_value       = 25
    scale_out_cooldown = 60
    scale_in_cooldown  = 120

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

output "web_repository_url" {
  value = aws_ecr_repository.web.repository_url
}

output "web_url" {
  value = local.web_url
}
