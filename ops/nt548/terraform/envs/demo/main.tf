# The demo environment on AWS Academy Learner Lab (us-east-1). Grows one module at a time (#21):
#   network (#23)  ->  alb (#24)  ->  app_asg blue + green (#25)  ->  monitoring (#26), aiops (#36)
# The contract with the deploy workflow (design §7.1), complete once the ASGs are in: variables image_tag_{blue,green},
# weight_blue, data_release_{blue,green}; outputs alb_dns_name, target_group_arn_{blue,green}, asg_name_{blue,green}.
#
# State stays local until the bootstrap stack (#22) creates the S3 bucket; then add
#   backend "s3" { bucket = "<from bootstrap>"  key = "envs/demo.tfstate"  region = "us-east-1" }
# Credentials: the temporary ones of the Learner Lab session (AWS Details), never committed.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "nt548", env = "demo", name_prefix = var.name_prefix }
  }
}

module "network" {
  source      = "../../modules/network"
  name_prefix = var.name_prefix
  azs         = var.azs
}

module "alb" {
  source             = "../../modules/alb"
  name_prefix        = var.name_prefix
  vpc_id             = module.network.vpc_id
  subnet_ids         = module.network.public_subnet_ids
  security_group_id  = module.network.sg_alb_id
  weight_blue        = var.weight_blue
  stickiness_seconds = var.stickiness_seconds
}

# One ASG per color behind its target group. Only the idle color changes in a release: the deploy workflow gives it
# the new image_tag_<color>, waits for its instance refresh, then moves weight_blue (ops/nt548/deploy_aws.sh, #29).
module "app" {
  source   = "../../modules/app_asg"
  for_each = toset(["blue", "green"])

  name_prefix        = var.name_prefix
  color              = each.key
  subnet_ids         = module.network.public_subnet_ids
  security_group_ids = [module.network.sg_app_id]
  target_group_arns  = [module.alb.target_group_arns[each.key]]
  image_tag          = each.key == "blue" ? var.image_tag_blue : var.image_tag_green
  data_release       = each.key == "blue" ? var.data_release_blue : var.data_release_green
  database_url       = var.database_url
  instance_type      = var.instance_type
  min_size           = var.min_size
  max_size           = var.max_size
  cpu_target         = var.cpu_target
  region             = var.region
}
