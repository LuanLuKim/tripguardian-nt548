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

variable "weight_blue" {
  description = "Percent of new users on blue (0-100), green gets the rest. The deploy workflow sets it (contract §7.1)."
  type        = number
  default     = 100
}

variable "stickiness_seconds" {
  description = "How long a user stays on the color they got, even across a weight change; 0 turns it off."
  type        = number
  default     = 300
}

variable "image_tag_blue" {
  description = "Image tag (commit sha) blue runs; empty: the placeholder traefik/whoami (contract §7.1)."
  type        = string
  default     = ""
}

variable "image_tag_green" {
  description = "Image tag (commit sha) green runs; empty: the placeholder."
  type        = string
  default     = ""
}

variable "data_release_blue" {
  description = "Sample data release of blue (ops/nt548/sample-data/<id>, T5)."
  type        = string
  default     = "r-a"
}

variable "data_release_green" {
  description = "Sample data release of green."
  type        = string
  default     = "r-a"
}

variable "database_url" {
  description = "Postgres of the ops machine (bootstrap #22); empty: the harness stub. Pass it with TF_VAR_database_url, never in a file."
  type        = string
  default     = ""
  sensitive   = true
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "min_size" {
  description = "Instances per color at least."
  type        = number
  default     = 1
}

variable "max_size" {
  description = "Instances per color at most (scale-out under load)."
  type        = number
  default     = 3
}

variable "cpu_target" {
  description = "Target tracking: average CPU of a color, in percent."
  type        = number
  default     = 50
}

variable "alarm_email" {
  description = "Address that gets the alarms by mail (confirm AWS's mail first); empty: none, incident.py polls."
  type        = string
  default     = ""
}

variable "p95_seconds" {
  description = "p95 latency above which the fixed latency alarms fire."
  type        = number
  default     = 1.5
}
