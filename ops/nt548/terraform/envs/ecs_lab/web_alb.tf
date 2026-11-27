resource "aws_vpc_security_group_ingress_rule" "web_tasks_from_alb" {
  security_group_id            = module.network.sg_app_id
  referenced_security_group_id = module.network.sg_alb_id
  ip_protocol                  = "tcp"
  from_port                    = 32768
  to_port                      = 65535
}

resource "aws_lb" "web" {
  name               = "nt548-ecs-lab-web"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [module.network.sg_alb_id]
  subnets            = module.network.public_subnet_ids
}

resource "aws_lb_target_group" "web" {
  name        = "nt548-ecs-lab-web"
  port        = local.web_container_port
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = module.network.vpc_id

  health_check {
    path    = "/"
    matcher = "200"
  }
}

resource "aws_lb_listener" "web" {
  load_balancer_arn = aws_lb.web.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener_rule" "web_reject_cloudflare_ip" {
  listener_arn = aws_lb_listener.web.arn
  priority     = 10

  # The web image trusts this header behind Cloudflare; public ALB clients can supply it themselves.
  condition {
    http_header {
      http_header_name = "CF-Connecting-IP"
      values           = ["*"]
    }
  }

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      status_code  = "400"
    }
  }
}
