terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

module "network" {
  source      = "../../modules/network"
  name_prefix = "nt548-ecs-lab"
}

resource "aws_ecs_cluster" "lab" {
  name = "nt548-ecs-lab"
}

data "aws_ssm_parameter" "ecs_ami" {
  name = "/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id"
}

locals {
  worker_user_data = <<-SCRIPT
    #!/bin/bash
    echo 'ECS_CLUSTER=${aws_ecs_cluster.lab.name}' >> /etc/ecs/ecs.config
  SCRIPT
}

removed {
  from = aws_instance.worker

  lifecycle {
    destroy = false
  }
}

resource "aws_ecs_task_definition" "harness" {
  family                   = "nt548-ecs-lab-harness"
  requires_compatibilities = ["EC2"]
  network_mode             = "bridge"
  memory                   = local.real_harness ? "896" : "384"
  execution_role_arn       = one(data.aws_iam_role.harness_execution[*].arn)

  container_definitions = jsonencode([
    {
      name      = "harness"
      image     = local.real_harness ? "${aws_ecr_repository.harness.repository_url}:${var.harness_image_tag}" : "ghcr.io/luanlukim/tripguardian-nt548/harness:main"
      cpu       = local.real_harness ? 512 : 256
      memory    = local.real_harness ? 768 : 256
      essential = true
      command   = local.real_harness ? ["python", "-m", "harness", "serve", "--host", "0.0.0.0"] : ["python", "ops/nt548/compose/harness_stub.py", "--host", "0.0.0.0"]

      environment = local.real_harness ? [
        { name = "APP_BASE_URL", value = local.web_url }
      ] : []

      secrets = local.real_harness ? [
        { name = "DATABASE_URL", valueFrom = "/nt548/ecs-lab/harness/database-url" }
      ] : []

      portMappings = [
        {
          name          = "harness-http"
          containerPort = 8769
        }
      ]
    }
  ])

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_ecs_service" "harness" {
  name                               = "harness"
  cluster                            = aws_ecs_cluster.lab.id
  task_definition                    = aws_ecs_task_definition.harness.arn
  desired_count                      = 1
  wait_for_steady_state              = true
  force_new_deployment               = true
  deployment_minimum_healthy_percent = 50

  capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.workers.name
    weight            = 1
  }

  ordered_placement_strategy {
    type  = "binpack"
    field = "memory"
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.harness.arn
    container_name   = "harness"
    container_port   = 8769
  }

  depends_on = [
    aws_ecs_cluster_capacity_providers.lab,
    aws_lb_listener.harness,
    aws_vpc_security_group_egress_rule.harness_alb_to_tasks,
    aws_vpc_security_group_ingress_rule.ecs_internal_ports
  ]

  lifecycle {
    ignore_changes = [desired_count]
  }
}

resource "aws_appautoscaling_target" "harness" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.lab.name}/${aws_ecs_service.harness.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = 3
}

resource "aws_appautoscaling_policy" "harness_cpu" {
  name               = "nt548-ecs-lab-harness-cpu"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.harness.service_namespace
  resource_id        = aws_appautoscaling_target.harness.resource_id
  scalable_dimension = aws_appautoscaling_target.harness.scalable_dimension

  target_tracking_scaling_policy_configuration {
    target_value       = 25
    scale_out_cooldown = 60
    scale_in_cooldown  = 120

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
