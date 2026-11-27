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
