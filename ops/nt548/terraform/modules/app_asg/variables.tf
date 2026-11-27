variable "name_prefix" {
  description = "Prefix of every name, e.g. nt548 (one per member's lab)."
  type        = string
}

variable "color" {
  description = "blue or green; the module is called once per color."
  type        = string

  validation {
    condition     = contains(["blue", "green"], var.color)
    error_message = "color must be blue or green."
  }
}

variable "subnet_ids" {
  description = "Public subnets (one per AZ) the instances start in (network module, #23)."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) > 0
    error_message = "Give at least one subnet."
  }
}

variable "security_group_ids" {
  description = "Security groups of the app instances (port 8080 from the ALB only)."
  type        = list(string)
}

variable "target_group_arns" {
  description = "Target group(s) of this color (ALB module, #24). Empty: no ALB yet, health is the EC2 status check."
  type        = list(string)
  default     = []
}

variable "image_tag" {
  description = "Tag of ghcr.io/.../{harness,web,llm-fake} to run. Empty: the placeholder traefik/whoami on 8080 (design §7.1)."
  type        = string
  default     = ""
}

variable "data_release" {
  description = "Sample data release the harness mounts (ops/nt548/sample-data/<id>, T5)."
  type        = string
  default     = "r-a"

  validation {
    condition     = can(regex("^r-[A-Za-z0-9_-]+$", var.data_release))
    error_message = "data_release looks like r-a."
  }
}

variable "database_url" {
  description = "Postgres URL of the ops machine. Set: the real harness runs (python -m harness serve); empty: the harness stub."
  type        = string
  default     = ""
  sensitive   = true
}

variable "registry" {
  description = "Image registry path (public, no login)."
  type        = string
  default     = "ghcr.io/luanlukim/tripguardian-nt548"
}

variable "repo_url" {
  description = "Public git repo the instance reads ops/nt548/compose/app.yml and the sample data generator from."
  type        = string
  default     = "https://github.com/LuanLuKim/tripguardian-nt548.git"
}

variable "repo_ref" {
  description = "Branch, tag or commit of repo_url to check out. Empty: image_tag (images are tagged with the commit sha), else main."
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "Learner Lab allows nano to large; R1 measured the harness well under 1.5 GB, so t3.small."
  type        = string
  default     = "t3.small"
}

variable "instance_profile_name" {
  description = "Learner Lab's prebuilt profile (no IAM role can be created)."
  type        = string
  default     = "LabInstanceProfile"
}

variable "ami_id" {
  description = "AMI to boot. Empty: the latest Amazon Linux 2023 x86_64 from SSM."
  type        = string
  default     = ""
}

variable "min_size" {
  type    = number
  default = 1
}

variable "max_size" {
  type    = number
  default = 3
}

variable "cpu_target" {
  description = "Target tracking: average CPU of the group, in percent."
  type        = number
  default     = 50

  validation {
    condition     = var.cpu_target > 0 && var.cpu_target < 100
    error_message = "cpu_target is a percentage between 0 and 100."
  }
}

variable "warmup_seconds" {
  description = "Seconds a new instance needs (Docker pull + compose up) before its health and CPU count."
  type        = number
  default     = 180
}

variable "log_group" {
  description = "CloudWatch Logs group for the containers (awslogs driver), e.g. /nt548/app-blue (monitoring #26). Empty: json-file on the instance."
  type        = string
  default     = ""
}

variable "region" {
  description = "Region of the log group."
  type        = string
  default     = "us-east-1"
}

variable "detailed_monitoring" {
  description = "1-minute EC2 metrics (a few cents a day); with 5-minute ones, target tracking reacts far too late for a demo."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Extra tags; project, color, image_tag and data_release are always added."
  type        = map(string)
  default     = {}
}
