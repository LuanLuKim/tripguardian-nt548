# One color of the app (#25): launch template + auto scaling group + CPU target tracking, attached to the color's
# target group. Called twice (blue, green) by envs/demo. Changing image_tag or data_release changes the user-data,
# hence a new launch template version, and the instance refresh replaces the instances: launch first, then
# terminate (min 100 % / max 200 % healthy), so a color with one instance never drops to zero.
#
# The refresh runs after `terraform apply` returns. Whoever waits for the new version (ops/nt548/deploy_aws.sh, #29)
# waits for the refresh to finish (aws autoscaling describe-instance-refreshes), not only for healthy targets: the
# old instances are healthy too until they are replaced.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.30"
    }
  }
}

data "aws_ssm_parameter" "al2023" {
  count = var.ami_id == "" ? 1 : 0
  name  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  name     = "${var.name_prefix}-${var.color}"
  ami_id   = var.ami_id != "" ? var.ami_id : data.aws_ssm_parameter.al2023[0].insecure_value
  repo_ref = var.repo_ref != "" ? var.repo_ref : (var.image_tag != "" ? var.image_tag : "main")
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    color        = var.color
    image_tag    = var.image_tag
    data_release = var.data_release
    database_url = var.database_url
    registry     = var.registry
    repo_url     = var.repo_url
    repo_ref     = local.repo_ref
    log_group    = var.log_group
    region       = var.region
  })
  tags = merge(var.tags, {
    project      = "nt548"
    color        = var.color
    image_tag    = var.image_tag != "" ? var.image_tag : "placeholder"
    data_release = var.data_release
  })
}

resource "aws_launch_template" "app" {
  name_prefix            = "${local.name}-"
  image_id               = local.ami_id
  instance_type          = var.instance_type
  vpc_security_group_ids = var.security_group_ids
  user_data              = base64encode(local.user_data)
  update_default_version = true

  iam_instance_profile {
    name = var.instance_profile_name
  }

  metadata_options {
    http_tokens   = "required" # IMDSv2 only
    http_endpoint = "enabled"
  }

  monitoring {
    enabled = var.detailed_monitoring # 1-minute CPU, so target tracking reacts within minutes
  }

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.tags, { Name = local.name })
  }

  tags = local.tags
}

resource "aws_autoscaling_group" "app" {
  name                      = local.name
  min_size                  = var.min_size
  max_size                  = var.max_size
  vpc_zone_identifier       = var.subnet_ids
  target_group_arns         = var.target_group_arns
  health_check_type         = length(var.target_group_arns) > 0 ? "ELB" : "EC2"
  health_check_grace_period = var.warmup_seconds
  default_instance_warmup   = var.warmup_seconds
  wait_for_elb_capacity     = length(var.target_group_arns) > 0 ? var.min_size : null # create waits for healthy targets
  enabled_metrics           = ["GroupDesiredCapacity", "GroupInServiceInstances", "GroupTotalInstances"]

  launch_template {
    id      = aws_launch_template.app.id
    version = aws_launch_template.app.latest_version
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 100 # launch the new instance before the old one goes
      max_healthy_percentage = 200
      instance_warmup        = var.warmup_seconds
    }
  }

  dynamic "tag" {
    for_each = merge(local.tags, { Name = local.name })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
    ignore_changes = [desired_capacity] # target tracking owns it; an apply must not undo a scale-out
  }
}

resource "aws_autoscaling_policy" "cpu" {
  name                   = "${local.name}-cpu-${var.cpu_target}"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = var.cpu_target
  }
}
