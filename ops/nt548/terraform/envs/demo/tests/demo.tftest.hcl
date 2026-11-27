# terraform -chdir=ops/nt548/terraform/envs/demo init -backend=false && terraform -chdir=... test
# The whole demo environment against a mocked provider: checks the contract with the deploy workflow (design §7.1)
# without an AWS account.

mock_provider "aws" {
  mock_resource "aws_lb" {
    defaults = {
      arn        = "arn:aws:elasticloadbalancing:us-east-1:111111111111:loadbalancer/app/nt548-alb/1"
      arn_suffix = "app/nt548-alb/1"
      dns_name   = "nt548-alb-1.us-east-1.elb.amazonaws.com"
    }
  }
  mock_resource "aws_launch_template" {
    defaults = {
      id             = "lt-0123456789abcdef0"
      latest_version = 1
    }
  }
  mock_data "aws_ssm_parameter" {
    defaults = {
      insecure_value = "ami-0123456789abcdef0"
    }
  }
  mock_resource "aws_lb_target_group" {
    defaults = {
      arn        = "arn:aws:elasticloadbalancing:us-east-1:111111111111:targetgroup/nt548-tg/1"
      arn_suffix = "targetgroup/nt548-tg/1"
    }
  }
}

run "contract_outputs_exist" {
  command = apply

  assert {
    condition     = output.alb_dns_name == "nt548-alb-1.us-east-1.elb.amazonaws.com"
    error_message = "alb_dns_name is the address of the app"
  }

  assert {
    condition     = startswith(output.target_group_arn_blue, "arn:aws:elasticloadbalancing:") && startswith(output.target_group_arn_green, "arn:aws:elasticloadbalancing:")
    error_message = "target_group_arn_{blue,green} are what deploy_aws.sh polls for health"
  }

  assert {
    condition     = output.weight_blue == 100
    error_message = "a fresh environment sends everyone to blue"
  }
}

run "weight_reaches_the_listener" {
  command = apply

  variables {
    weight_blue = 10
  }

  assert {
    condition     = module.alb.weights == { blue = 10, green = 90 }
    error_message = "weight_blue of the env drives the ALB listener"
  }

  assert {
    condition     = output.weight_blue == 10
    error_message = "the live weight is echoed back for deploy_aws.sh"
  }
}

run "a_release_changes_only_the_idle_color" {
  command = apply

  variables {
    image_tag_blue     = "aaa1111"
    image_tag_green    = "bbb2222"
    data_release_green = "r-b"
    weight_blue        = 90
  }

  assert {
    condition     = output.asg_name_blue == "nt548-blue" && output.asg_name_green == "nt548-green"
    error_message = "asg_name_{blue,green} follow <name_prefix>-<color>"
  }

  assert {
    condition     = module.app["blue"].runs == { image_tag = "aaa1111", data_release = "r-a" }
    error_message = "blue keeps its tag and data"
  }

  assert {
    condition     = module.app["green"].runs == { image_tag = "bbb2222", data_release = "r-b" }
    error_message = "green gets its own tag and data release"
  }

  assert {
    condition = (output.image_tag_blue == "aaa1111" && output.image_tag_green == "bbb2222"
    && output.data_release_blue == "r-a" && output.data_release_green == "r-b" && output.weight_blue == 90)
    error_message = "every input of the contract is echoed back for deploy_aws.sh"
  }
}

run "fresh_environment_runs_the_placeholder" {
  command = apply

  assert {
    condition     = output.image_tag_blue == "" && output.image_tag_green == "" && module.app["blue"].runs.image_tag == "placeholder"
    error_message = "empty tags mean the placeholder; deploy_aws.sh treats that as a first deploy"
  }
}
