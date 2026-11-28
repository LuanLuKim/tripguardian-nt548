# The demo environment on AWS Academy Learner Lab (us-east-1): what costs money, created by aws-up and destroyed by
# aws-down (ops/nt548/aws.sh, #27). The network, the ops machine and the state bucket are in ../../bootstrap (#22);
# this env finds them by name (<name_prefix>-vpc, -alb, -app) and reads the database URL from SSM.
#   alb (#24)  ->  app_asg blue + green (#25)  ->  monitoring (#26) + aiops (#36)
# Contract with the deploy workflow (design §7.1): variables image_tag_{blue,green}, weight_blue,
# data_release_{blue,green}; outputs alb_dns_name, target_group_arn_{blue,green}, asg_name_{blue,green}, and the
# inputs echoed back.
#
# State: S3 bucket of the bootstrap, given at init (ops/nt548/aws.sh init does it):
#   terraform init -backend-config=bucket=<prefix>-tfstate-<account> -backend-config=key=envs/demo/<prefix>.tfstate #     -backend-config=region=us-east-1
# Credentials: LabInstanceProfile on the runner, or the temporary ones of the Learner Lab session; never committed.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "nt548", env = "demo", name_prefix = var.name_prefix }
  }
}

# ---------- from the bootstrap (#22) ----------

data "aws_vpc" "this" {
  tags = { Name = "${var.name_prefix}-vpc" }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }
  tags = { Name = "${var.name_prefix}-public-*" }
}

data "aws_security_group" "tier" {
  for_each = toset(["alb", "app"])
  vpc_id   = data.aws_vpc.this.id
  name     = "${var.name_prefix}-${each.key}"
}

data "aws_ssm_parameter" "database_url" {
  count = var.real_harness && var.database_url == "" ? 1 : 0
  name  = "/${var.name_prefix}/database-url"
}

locals {
  subnet_ids = sort(data.aws_subnets.public.ids)
  # real harness: the Postgres of the ops machine; stub: no database
  database_url = var.database_url != "" ? var.database_url : (var.real_harness ? data.aws_ssm_parameter.database_url[0].value : "")
}

module "alb" {
  source             = "../../modules/alb"
  name_prefix        = var.name_prefix
  vpc_id             = data.aws_vpc.this.id
  subnet_ids         = local.subnet_ids
  security_group_id  = data.aws_security_group.tier["alb"].id
  weight_blue        = var.weight_blue
  stickiness_seconds = var.stickiness_seconds
}

# One ASG per color behind its target group. Only the idle color changes in a release: the deploy workflow gives it
# the new image_tag_<color>, waits until the new version serves, then moves weight_blue (ops/nt548/deploy_aws.sh, #29).
# rollout = replace (default): apply itself waits, since a new version is a new group (Learner Lab denies instance
# refresh, AWS-14).
module "app" {
  source   = "../../modules/app_asg"
  for_each = toset(["blue", "green"])

  name_prefix        = var.name_prefix
  color              = each.key
  subnet_ids         = local.subnet_ids
  security_group_ids = [data.aws_security_group.tier["app"].id]
  target_group_arns  = [module.alb.target_group_arns[each.key]]
  image_tag          = each.key == "blue" ? var.image_tag_blue : var.image_tag_green
  data_release       = each.key == "blue" ? var.data_release_blue : var.data_release_green
  database_url       = local.database_url
  app_base_url       = var.app_base_url != "" ? var.app_base_url : "http://${module.alb.alb_dns_name}"
  instance_type      = var.instance_type
  min_size           = var.min_size
  max_size           = var.max_size
  cpu_target         = var.cpu_target
  rollout            = var.rollout
  region             = var.region
  log_group          = local.log_groups[each.key]
}

# Log group names are fixed here, not read from module.monitoring, so the app does not wait for the monitoring
# module (the awslogs driver creates a missing group anyway).
locals {
  log_groups = { for c in ["blue", "green"] : c => "/${var.name_prefix}/app-${c}" }
}

module "monitoring" {
  source           = "../../modules/monitoring"
  name_prefix      = var.name_prefix
  region           = var.region
  alb_arn_suffix   = module.alb.alb_arn_suffix
  target_groups    = module.alb.target_group_arn_suffixes
  asg_names        = { for c, m in module.app : c => m.asg_name }
  cpu_target       = var.cpu_target
  alarm_email      = var.alarm_email
  p95_seconds      = var.p95_seconds
  extra_alarm_arns = values(module.aiops.alarm_arns)
}

# Learned thresholds (#36) next to the fixed ones, on the same topic.
module "aiops" {
  source         = "../../modules/aiops"
  name_prefix    = var.name_prefix
  alb_arn_suffix = module.alb.alb_arn_suffix
  target_groups  = module.alb.target_group_arn_suffixes
  alarm_actions  = [module.monitoring.sns_topic_arn]
}
