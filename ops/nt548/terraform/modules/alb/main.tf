# ALB (#24): one internet-facing ALB over the public subnets, a target group per color, and one listener on :80 that
# forwards by weight (weight_blue to blue, 100 - weight_blue to green). A release only changes weight_blue; the
# deploy workflow does that through `terraform apply` (design §7.1), never through the ELB API.
#
# Two stickiness levels:
#   - group stickiness (on the listener): a user stays on the color they first got, as on the Compose rehearsal (#2).
#     It outlives a weight change, so after a rollback a sticky user still reaches the old color for up to
#     stickiness_seconds. Keep it short; 0 turns it off.
#   - target stickiness (on each target group): off, the app keeps no state on the instance (sessions are in Postgres).

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  tags   = merge(var.tags, { project = "nt548" })
  colors = ["blue", "green"]
  weight = { blue = var.weight_blue, green = 100 - var.weight_blue }
}

resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = var.subnet_ids
  security_groups    = [var.security_group_id]
  idle_timeout       = var.idle_timeout
  tags               = merge(local.tags, { Name = "${var.name_prefix}-alb" })
}

resource "aws_lb_target_group" "color" {
  for_each = toset(local.colors)

  name                 = "${var.name_prefix}-${each.key}"
  port                 = var.app_port
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
  target_type          = "instance"
  deregistration_delay = var.deregistration_delay

  health_check {
    path                = var.health_path
    port                = "traffic-port"
    matcher             = "200"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = merge(local.tags, { Name = "${var.name_prefix}-${each.key}", color = each.key })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "forward"
    forward {
      dynamic "target_group" {
        for_each = local.colors
        content {
          arn    = aws_lb_target_group.color[target_group.value].arn
          weight = local.weight[target_group.value]
        }
      }
      stickiness {
        enabled  = var.stickiness_seconds > 0
        duration = max(var.stickiness_seconds, 1) # the API wants 1..604800 even when off
      }
    }
  }

  tags = local.tags
}
