# terraform -chdir=ops/nt548/terraform/modules/app_asg init -backend=false && terraform -chdir=... test
# Mocked provider: no AWS account or credentials needed.

mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = {
      insecure_value = "ami-0123456789abcdef0"
    }
  }
}

variables {
  name_prefix        = "nt548"
  color              = "blue"
  subnet_ids         = ["subnet-a", "subnet-b"]
  security_group_ids = ["sg-app"]
}

run "placeholder_without_image_tag" {
  command = plan

  assert {
    condition     = aws_autoscaling_group.app.name == "nt548-blue"
    error_message = "the group is named <name_prefix>-<color> (asg_name_<color> in the contract)"
  }

  assert {
    condition     = aws_autoscaling_group.app.min_size == 1 && aws_autoscaling_group.app.max_size == 3
    error_message = "min 1 / max 3 per color"
  }

  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "traefik/whoami --port 8080")
    error_message = "no image_tag must run the placeholder on 8080"
  }

  assert {
    condition     = aws_autoscaling_group.app.health_check_type == "EC2"
    error_message = "without a target group the health is the EC2 status check"
  }

  assert {
    condition     = aws_launch_template.app.iam_instance_profile[0].name == "LabInstanceProfile"
    error_message = "Learner Lab instances use LabInstanceProfile"
  }
}

run "cpu_target_tracking" {
  command = plan

  variables {
    cpu_target = 40
  }

  assert {
    condition     = aws_autoscaling_policy.cpu.policy_type == "TargetTrackingScaling"
    error_message = "scaling is target tracking"
  }

  assert {
    condition     = aws_autoscaling_policy.cpu.target_tracking_configuration[0].target_value == 40
    error_message = "cpu_target reaches the policy"
  }

  assert {
    condition     = aws_autoscaling_policy.cpu.target_tracking_configuration[0].predefined_metric_specification[0].predefined_metric_type == "ASGAverageCPUUtilization"
    error_message = "the metric is the group's average CPU"
  }
}

run "image_and_data_release_reach_the_instances" {
  command = plan

  variables {
    color             = "green"
    image_tag         = "abc1234"
    data_release      = "r-b"
    target_group_arns = ["arn:aws:elasticloadbalancing:us-east-1:111111111111:targetgroup/nt548-green/1"]
  }

  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "ghcr.io/luanlukim/tripguardian-nt548/harness:abc1234")
    error_message = "the instances pull the harness image of image_tag"
  }

  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "DATA_RELEASE=\"r-b\"")
    error_message = "data_release is passed to compose as DATA_RELEASE"
  }

  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "fetch -q --depth 1 \"https://github.com/LuanLuKim/tripguardian-nt548.git\" \"abc1234\"")
    error_message = "without repo_ref the instance checks out the commit of the image"
  }

  assert {
    condition     = aws_autoscaling_group.app.health_check_type == "ELB"
    error_message = "with a target group the ALB health check decides"
  }

  assert {
    condition     = output.runs == { image_tag = "abc1234", data_release = "r-b" }
    error_message = "runs reports what the color runs"
  }
}

run "stub_without_database_and_real_harness_with_it" {
  command = plan

  variables {
    image_tag    = "abc1234"
    database_url = "postgresql://tg:secret@10.48.1.10:5432/tg"
  }

  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "python -m db migrate")
    error_message = "a database URL applies the migrations and starts the real harness"
  }
}

run "refresh_launches_before_it_terminates" {
  command = plan

  assert {
    condition = (aws_autoscaling_group.app.instance_refresh[0].preferences[0].min_healthy_percentage == 100
    && aws_autoscaling_group.app.instance_refresh[0].preferences[0].max_healthy_percentage == 200)
    error_message = "a color with one instance must never drop to zero during a refresh"
  }

  assert {
    condition     = aws_launch_template.app.image_id == "ami-0123456789abcdef0"
    error_message = "without ami_id the latest Amazon Linux 2023 from SSM boots"
  }

  assert {
    condition     = aws_launch_template.app.metadata_options[0].http_tokens == "required"
    error_message = "IMDSv2 only"
  }
}

run "container_logs_go_to_cloudwatch_when_a_group_is_set" {
  command = plan

  variables {
    image_tag = "abc1234"
    log_group = "/nt548/app-blue"
  }

  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "LOG_GROUP='/nt548/app-blue'")
    error_message = "the log group reaches the instance"
  }

  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "driver: awslogs")
    error_message = "the compose override switches every service to the awslogs driver"
  }
}

run "tags_say_what_the_color_runs" {
  command = plan

  variables {
    image_tag = "abc1234"
    tags      = { owner = "dinhlong06" }
  }

  assert {
    condition = (aws_launch_template.app.tags["project"] == "nt548" && aws_launch_template.app.tags["color"] == "blue"
    && aws_launch_template.app.tags["image_tag"] == "abc1234" && aws_launch_template.app.tags["owner"] == "dinhlong06")
    error_message = "project, color, image_tag and the extra tags reach the launch template"
  }

  assert {
    condition     = contains([for t in aws_autoscaling_group.app.tag : t.key if t.propagate_at_launch], "image_tag")
    error_message = "instances carry the image tag too"
  }
}

run "public_origin_reaches_the_harness" {
  command = plan

  variables {
    image_tag    = "abc1234"
    app_base_url = "http://nt548-alb-1.us-east-1.elb.amazonaws.com"
  }

  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "export APP_BASE_URL='http://nt548-alb-1.us-east-1.elb.amazonaws.com'")
    error_message = "the real harness needs the public origin, else it refuses every write"
  }
}

run "unknown_color_is_refused" {
  command = plan

  variables {
    color = "red"
  }

  expect_failures = [var.color]
}

run "bad_data_release_is_refused" {
  command = plan

  variables {
    data_release = "latest"
  }

  expect_failures = [var.data_release]
}
