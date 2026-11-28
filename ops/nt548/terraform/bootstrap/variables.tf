variable "region" {
  description = "Learner Lab only allows us-east-1 (and us-west-2)."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix of every resource; each member uses their own on their own lab (e.g. nt548-dl), the shared demo uses nt548."
  type        = string
  default     = "nt548"
}

variable "azs" {
  description = "Two AZs for the public subnets and the ALB."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "ops_instance_type" {
  description = "Postgres + runner (Terraform, k6 runs elsewhere)."
  type        = string
  default     = "t3.small"
}

variable "instance_profile_name" {
  description = "Learner Lab's prebuilt profile (no IAM role can be created); the runner's AWS credentials."
  type        = string
  default     = "LabInstanceProfile"
}

variable "runner_token" {
  description = "Registration token of a new self-hosted runner (lives one hour). Empty: the machine starts without a runner."
  type        = string
  default     = ""
  sensitive   = true
}

variable "runner_url" {
  description = "Repository the runner registers with."
  type        = string
  default     = "https://github.com/LuanLuKim/tripguardian-nt548"
}

variable "runner_labels" {
  description = "Labels of the runner; the AWS workflows run on [self-hosted, nt548-aws]."
  type        = string
  default     = "nt548-aws"
}

variable "runner_version" {
  description = "actions/runner release. GitHub refuses to register a runner older than its minimum (2.329.0 since 2026; 2.321.0 failed on 28/11)."
  type        = string
  default     = "2.338.2"
}

variable "terraform_version" {
  description = "Terraform installed on the runner."
  type        = string
  default     = "1.9.8"
}

variable "create_state_bucket" {
  description = "true: this stack creates the state bucket. false (Learner Lab, whose SCP breaks the bucket resource): the bucket <name_prefix>-tfstate-<account> already exists (aws s3api create-bucket) and only its settings are managed here."
  type        = bool
  default     = false
}
