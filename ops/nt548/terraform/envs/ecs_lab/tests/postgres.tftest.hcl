mock_provider "aws" {
  mock_data "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/LabRole" }
  }
}

run "postgres_is_private_and_password_is_managed" {
  command = plan

  assert {
    condition     = !aws_db_instance.harness.publicly_accessible && aws_db_instance.harness.storage_encrypted
    error_message = "The lab PostgreSQL instance must be private and encrypted."
  }

  assert {
    condition     = aws_db_instance.harness.engine == "postgres" && aws_db_instance.harness.manage_master_user_password
    error_message = "RDS must manage the PostgreSQL master password outside the Terraform state."
  }
}

run "real_harness_uses_shared_postgres_without_embedding_credentials" {
  command = plan

  override_resource {
    target          = aws_ecr_repository.harness
    override_during = plan
    values          = { repository_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com/nt548-ecs-lab-harness" }
  }

  variables {
    harness_image_tag = "lab-rds-v1"
  }

  assert {
    condition     = one(aws_lb_target_group.harness.health_check).path == "/api/auth/options"
    error_message = "The ALB must check a route served by the real harness."
  }

  assert {
    condition     = aws_appautoscaling_target.harness.min_capacity == 2
    error_message = "Both real harness tasks must remain available during the cross-worker database test."
  }

  assert {
    condition     = one(jsondecode(aws_ecs_task_definition.harness.container_definitions)[0].secrets).valueFrom == "/nt548/ecs-lab/harness/database-url"
    error_message = "The database URL must be injected from SSM instead of embedded in the task definition."
  }
}
