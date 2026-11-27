# terraform -chdir=ops/nt548/terraform/bootstrap init -backend=false && terraform -chdir=... test
# Mocked providers: no AWS account or credentials needed.

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "111111111111"
    }
  }
  mock_data "aws_ssm_parameter" {
    defaults = {
      insecure_value = "ami-0123456789abcdef0"
    }
  }
  mock_resource "aws_instance" {
    defaults = {
      private_ip = "10.48.0.10"
    }
  }
}

mock_provider "random" {
  mock_resource "random_password" {
    defaults = {
      result = "pw0123456789"
    }
  }
}

# First run: the instance ignores later user-data changes (lifecycle), so the token must be there from the start.
run "ops_machine_runs_postgres_and_the_runner" {
  command = apply

  variables {
    runner_token = "AAAATOKEN"
  }

  assert {
    condition     = aws_instance.ops.instance_type == "t3.small" && aws_instance.ops.iam_instance_profile == "LabInstanceProfile"
    error_message = "t3.small with LabInstanceProfile (the runner's credentials)"
  }

  assert {
    condition     = tolist(aws_instance.ops.vpc_security_group_ids)[0] == module.network.sg_ops_id
    error_message = "the ops SG: 5432 from the app SG only, no SSH"
  }

  assert {
    condition     = strcontains(aws_instance.ops.user_data, "postgres:16") && strcontains(aws_instance.ops.user_data, "POSTGRES_PASSWORD='pw0123456789'")
    error_message = "Postgres runs with the generated password"
  }

  assert {
    condition     = strcontains(aws_instance.ops.user_data, "--labels 'nt548-aws'")
    error_message = "the runner registers with label nt548-aws"
  }

  assert {
    condition     = strcontains(aws_instance.ops.user_data, "TOKEN='AAAATOKEN'")
    error_message = "the registration token reaches the machine"
  }

  assert {
    condition     = aws_instance.ops.metadata_options[0].http_tokens == "required" && aws_instance.ops.root_block_device[0].encrypted
    error_message = "IMDSv2 only, encrypted disk"
  }
}

run "state_bucket_is_private_versioned_and_per_account" {
  command = apply

  assert {
    condition     = aws_s3_bucket.state.bucket == "nt548-tfstate-111111111111" && output.state_bucket == aws_s3_bucket.state.bucket
    error_message = "bucket <prefix>-tfstate-<account>: unique per lab, and aws.sh can compute it"
  }

  assert {
    condition     = aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled"
    error_message = "a broken apply can be undone from an older state version"
  }

  assert {
    condition = (aws_s3_bucket_public_access_block.state.block_public_acls && aws_s3_bucket_public_access_block.state.block_public_policy
    && aws_s3_bucket_public_access_block.state.restrict_public_buckets)
    error_message = "the state holds the database URL: never public"
  }

  assert {
    condition     = !aws_s3_bucket.state.force_destroy
    error_message = "destroying bootstrap must not silently delete the state"
  }
}

run "database_url_goes_to_ssm" {
  command = apply

  assert {
    condition     = aws_ssm_parameter.database_url.name == "/nt548/database-url" && aws_ssm_parameter.database_url.type == "SecureString"
    error_message = "envs/demo reads /<prefix>/database-url"
  }

  assert {
    condition     = aws_ssm_parameter.database_url.value == "postgresql://tg:pw0123456789@10.48.0.10:5432/tg"
    error_message = "the URL points at the ops machine's private IP (stable across stop / start)"
  }
}

run "network_lives_here" {
  command = apply

  variables {
    name_prefix = "nt548-dl"
  }

  assert {
    condition     = length(output.public_subnet_ids) == 2 && aws_instance.ops.tags["Name"] == "nt548-dl-ops"
    error_message = "the network and the ops machine carry the member's prefix"
  }
}
