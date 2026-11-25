# The demo environment on AWS Academy Learner Lab (us-east-1). Grows one module at a time (#21):
#   network (#23)  ->  alb (#24)  ->  app_asg blue + green (#25)  ->  monitoring (#26), aiops (#36)
# The contract with the deploy workflow (design §7.1) lands with the ALB and ASGs: variables image_tag_{blue,green},
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
