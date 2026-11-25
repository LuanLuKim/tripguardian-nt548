variable "harness_image_tag" {
  type        = string
  default     = null
  description = "ECR tag for the real harness. Leave unset until the sample image and database parameter are ready."
}

locals {
  real_harness = var.harness_image_tag != null
}

data "aws_iam_role" "harness_execution" {
  count = local.real_harness ? 1 : 0
  name  = "LabRole"
}

resource "aws_ecr_repository" "harness" {
  name                 = "nt548-ecs-lab-harness"
  image_tag_mutability = "IMMUTABLE"
}

output "harness_repository_url" {
  value = aws_ecr_repository.harness.repository_url
}
