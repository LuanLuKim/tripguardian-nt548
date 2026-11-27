# terraform -chdir=ops/nt548/terraform/modules/alb init -backend=false && terraform -chdir=... test
# Mocked provider: no AWS account or credentials needed.

# The provider checks ARN syntax, so the mock hands out well-formed ones.
mock_provider "aws" {
  mock_resource "aws_lb" {
    defaults = {
      arn        = "arn:aws:elasticloadbalancing:us-east-1:111111111111:loadbalancer/app/nt548-alb/1"
      arn_suffix = "app/nt548-alb/1"
      dns_name   = "nt548-alb-1.us-east-1.elb.amazonaws.com"
    }
  }
  mock_resource "aws_lb_target_group" {
    defaults = {
      arn        = "arn:aws:elasticloadbalancing:us-east-1:111111111111:targetgroup/nt548-tg/1"
      arn_suffix = "targetgroup/nt548-tg/1"
    }
  }
}

variables {
  name_prefix       = "nt548"
  vpc_id            = "vpc-1"
  subnet_ids        = ["subnet-a", "subnet-b"]
  security_group_id = "sg-alb"
}

run "one_alb_two_colors_all_traffic_to_blue_by_default" {
  command = apply

  assert {
    condition     = aws_lb.this.load_balancer_type == "application" && !aws_lb.this.internal && length(aws_lb.this.subnets) == 2
    error_message = "an internet-facing ALB over both public subnets"
  }

  assert {
    condition     = join(",", sort(keys(aws_lb_target_group.color))) == "blue,green"
    error_message = "one target group per color"
  }

  assert {
    condition     = output.weights == { blue = 100, green = 0 }
    error_message = "the default sends every new user to blue"
  }

  assert {
    condition     = aws_lb_listener.http.port == 80 && aws_lb_listener.http.default_action[0].type == "forward"
    error_message = "the listener on :80 forwards"
  }
}

run "health_check_is_get_root_on_the_app_port" {
  command = apply

  assert {
    condition = alltrue([for tg in aws_lb_target_group.color : tg.port == 8080 && tg.health_check[0].path == "/"
    && tg.health_check[0].matcher == "200" && tg.health_check[0].port == "traffic-port"])
    error_message = "GET / on 8080 must return 200 (contract §7.1)"
  }

  assert {
    condition     = alltrue([for tg in aws_lb_target_group.color : tg.deregistration_delay == "30"])
    error_message = "a short deregistration delay keeps a refresh quick"
  }
}

run "canary_ten_percent_to_green" {
  command = apply

  variables {
    weight_blue = 90
  }

  assert {
    condition     = output.weights == { blue = 90, green = 10 }
    error_message = "green gets 100 - weight_blue"
  }

  assert {
    condition     = sort([for tg in aws_lb_listener.http.default_action[0].forward[0].target_group : tg.weight]) == tolist(["10", "90"])
    error_message = "the listener carries both weights"
  }
}

run "group_stickiness_on_by_default" {
  command = plan

  assert {
    condition = (aws_lb_listener.http.default_action[0].forward[0].stickiness[0].enabled
    && aws_lb_listener.http.default_action[0].forward[0].stickiness[0].duration == 300)
    error_message = "a user stays on one color for 5 minutes by default"
  }
}

run "zero_turns_group_stickiness_off" {
  command = plan

  variables {
    stickiness_seconds = 0
  }

  assert {
    condition     = !aws_lb_listener.http.default_action[0].forward[0].stickiness[0].enabled
    error_message = "0 turns group stickiness off (a rollback then moves every user at once)"
  }
}

run "names_start_with_the_prefix" {
  command = plan

  variables {
    name_prefix = "nt548-dl"
  }

  assert {
    condition     = aws_lb.this.name == "nt548-dl-alb" && aws_lb_target_group.color["green"].name == "nt548-dl-green"
    error_message = "every name starts with name_prefix, so two labs never clash"
  }
}

run "weight_above_100_is_refused" {
  command = plan

  variables {
    weight_blue = 110
  }

  expect_failures = [var.weight_blue]
}

run "one_subnet_is_refused" {
  command = plan

  variables {
    subnet_ids = ["subnet-a"]
  }

  expect_failures = [var.subnet_ids]
}
