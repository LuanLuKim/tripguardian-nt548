resource "aws_launch_template" "worker" {
  name_prefix   = "nt548-ecs-lab-worker-"
  image_id      = data.aws_ssm_parameter.ecs_ami.value
  instance_type = "t3.small"
  user_data     = base64encode(local.worker_user_data)

  iam_instance_profile {
    name = "LabInstanceProfile"
  }

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [module.network.sg_app_id]
  }
}

resource "aws_autoscaling_group" "workers" {
  name                = "nt548-ecs-lab-workers"
  min_size            = 1
  max_size            = 2
  vpc_zone_identifier = module.network.public_subnet_ids

  launch_template {
    id      = aws_launch_template.worker.id
    version = aws_launch_template.worker.latest_version
  }

  tag {
    key                 = "Name"
    value               = "nt548-ecs-lab-asg-worker"
    propagate_at_launch = true
  }

  tag {
    key                 = "AmazonECSManaged"
    value               = "true"
    propagate_at_launch = true
  }
}

resource "aws_ecs_capacity_provider" "workers" {
  name = "nt548-ecs-lab-workers"

  auto_scaling_group_provider {
    auto_scaling_group_arn = aws_autoscaling_group.workers.arn
    managed_draining       = "ENABLED"

    managed_scaling {
      status                    = "ENABLED"
      target_capacity           = 100
      minimum_scaling_step_size = 1
      maximum_scaling_step_size = 1
      instance_warmup_period    = 120
    }
  }
}

resource "aws_ecs_cluster_capacity_providers" "lab" {
  cluster_name       = aws_ecs_cluster.lab.name
  capacity_providers = [aws_ecs_capacity_provider.workers.name]
}
