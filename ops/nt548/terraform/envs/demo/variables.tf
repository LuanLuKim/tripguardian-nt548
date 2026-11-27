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
