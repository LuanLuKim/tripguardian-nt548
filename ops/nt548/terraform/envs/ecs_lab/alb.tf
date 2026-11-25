resource "aws_security_group" "harness_alb" {
  name        = "nt548-ecs-lab-harness-alb"
  description = "Private HTTP entry point for the harness service"
  vpc_id      = module.network.vpc_id

  tags = { Name = "nt548-ecs-lab-harness-alb" }
}

resource "aws_vpc_security_group_ingress_rule" "harness_alb_from_app" {
  security_group_id            = aws_security_group.harness_alb.id
  referenced_security_group_id = module.network.sg_app_id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}

resource "aws_vpc_security_group_egress_rule" "harness_alb_to_tasks" {
  security_group_id            = aws_security_group.harness_alb.id
  referenced_security_group_id = module.network.sg_app_id
  ip_protocol                  = "tcp"
  from_port                    = 32768
  to_port                      = 65535
}

resource "aws_vpc_security_group_ingress_rule" "ecs_internal_ports" {
  security_group_id            = module.network.sg_app_id
  referenced_security_group_id = aws_security_group.harness_alb.id
  ip_protocol                  = "tcp"
  from_port                    = aws_vpc_security_group_egress_rule.harness_alb_to_tasks.from_port
  to_port                      = aws_vpc_security_group_egress_rule.harness_alb_to_tasks.to_port
}

resource "aws_lb" "harness" {
  name               = "nt548-ecs-lab-harness"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.harness_alb.id]
  subnets            = module.network.public_subnet_ids
}

resource "aws_lb_target_group" "harness" {
  name        = "nt548-ecs-lab-harness"
  port        = 8769
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = module.network.vpc_id

  health_check {
    path    = local.real_harness ? "/api/auth/options" : "/api/harness/nt548-version"
    matcher = "200"
  }
}

resource "aws_lb_listener" "harness" {
  load_balancer_arn = aws_lb.harness.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.harness.arn
  }
}
