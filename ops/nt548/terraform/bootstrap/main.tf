# Bootstrap (#22): what lives as long as the lab account and costs (almost) nothing while the demo is down.
#   - the network (modules/network, #23): free, and the ops machine sits in it;
#   - the S3 bucket that holds the state of envs/demo (versioned, private, encrypted);
#   - the ops machine (t3.small): Postgres in a container for the app instances, and the GitHub self-hosted runner
#     (label nt548-aws) that deploys with LabInstanceProfile, so GitHub holds no AWS key (design §5.2);
#   - the database URL in SSM Parameter Store (/<name_prefix>/database-url), where envs/demo reads it.
# envs/demo (ALB, ASGs, monitoring: what costs money) finds the network by name and is destroyed by aws-down;
# this stack stays, and aws-down only stops the ops machine.
#
# Run once per lab account from a member's machine with the lab's temporary credentials (docs/nt548/08-aws-infra.md):
#   terraform -chdir=ops/nt548/terraform/bootstrap apply -var name_prefix=nt548 -var runner_token=<1-hour token>
# State: local (terraform.tfstate here, never committed). Losing it does not lose the resources; see the doc.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "nt548", env = "bootstrap", name_prefix = var.name_prefix }
  }
}

data "aws_caller_identity" "me" {}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

module "network" {
  source      = "../modules/network"
  name_prefix = var.name_prefix
  azs         = var.azs
}

# ---------- state bucket ----------

# Learner Lab's SCP denies s3:GetBucketObjectLockConfiguration, which the aws_s3_bucket resource reads after every
# create and refresh (403, AWS-02 / AWS-06 in #80). So by default the bucket is made once with the CLI
# (`aws s3api create-bucket`, docs/nt548/08-aws-infra.md) and this stack only manages its versioning, encryption and
# public access block, which are separate resources. create_state_bucket = true makes the bucket here (normal account).
locals {
  state_bucket = "${var.name_prefix}-tfstate-${data.aws_caller_identity.me.account_id}"
}

resource "aws_s3_bucket" "state" {
  count         = var.create_state_bucket ? 1 : 0
  bucket        = local.state_bucket
  force_destroy = false # the state of envs/demo; delete it by hand if you really mean it
}

locals {
  state_bucket_id = var.create_state_bucket ? aws_s3_bucket.state[0].id : local.state_bucket
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = local.state_bucket_id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = local.state_bucket_id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = local.state_bucket_id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------- ops machine: Postgres + runner ----------

resource "random_password" "db" {
  length  = 24
  special = false # goes into a URL
}

locals {
  database_url = "postgresql://tg:${random_password.db.result}@${aws_instance.ops.private_ip}:5432/tg"
}

resource "aws_instance" "ops" {
  ami                    = data.aws_ssm_parameter.al2023.insecure_value
  instance_type          = var.ops_instance_type
  subnet_id              = module.network.public_subnet_ids[0]
  vpc_security_group_ids = [module.network.sg_ops_id]
  iam_instance_profile   = var.instance_profile_name

  user_data = templatefile("${path.module}/ops_user_data.sh.tftpl", {
    db_password    = random_password.db.result
    runner_token   = var.runner_token
    runner_url     = var.runner_url
    runner_name    = "${var.name_prefix}-ops"
    runner_labels  = var.runner_labels
    runner_version = var.runner_version
    tf_version     = var.terraform_version
  })

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "${var.name_prefix}-ops", "nt548:role" = "ops" }

  lifecycle {
    # The runner applies this repo's Terraform from this very machine: a newer AMI or a new runner token must never
    # replace it (that would drop Postgres and the runner). Rebuild on purpose with -replace=aws_instance.ops.
    ignore_changes = [ami, user_data]
  }
}

resource "aws_ssm_parameter" "database_url" {
  name        = "/${var.name_prefix}/database-url"
  description = "Postgres of ${var.name_prefix}-ops for the app instances (envs/demo reads it)."
  type        = "SecureString"
  value       = local.database_url
}
