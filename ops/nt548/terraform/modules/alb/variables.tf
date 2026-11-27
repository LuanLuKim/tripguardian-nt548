variable "name_prefix" {
  description = "Prefix of every name, e.g. nt548 (one per member's lab). ALB and target group names allow 32 characters."
  type        = string

  validation {
    condition     = length(var.name_prefix) <= 26 && can(regex("^[A-Za-z0-9-]+$", var.name_prefix))
    error_message = "Use letters, digits and dashes, at most 26 characters (<prefix>-green must fit in 32)."
  }
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Public subnets in at least two AZs (network module, #23)."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "An ALB needs subnets in at least two AZs."
  }
}

variable "security_group_id" {
  description = "SG of the ALB: 80 from the internet (network module output sg_alb_id)."
  type        = string
}

variable "app_port" {
  description = "Port of the app instances (ops/nt548/compose/app.yml publishes 8080)."
  type        = number
  default     = 8080
}

variable "health_path" {
  description = "Health check of a target: GET returns 200 (design §7.1)."
  type        = string
  default     = "/"
}

variable "weight_blue" {
  description = "Percent of new users sent to blue (0-100); green gets the rest."
  type        = number
  default     = 100

  validation {
    condition     = var.weight_blue >= 0 && var.weight_blue <= 100 && floor(var.weight_blue) == var.weight_blue
    error_message = "The weight_blue value is a whole number from 0 to 100."
  }
}

variable "stickiness_seconds" {
  description = "Group stickiness: a user stays on one color this long, even across a weight change. 0 turns it off."
  type        = number
  default     = 300

  validation {
    condition     = var.stickiness_seconds >= 0 && var.stickiness_seconds <= 604800
    error_message = "The stickiness_seconds value is from 0 (off) to 604800 (7 days)."
  }
}

variable "deregistration_delay" {
  description = "Seconds a removed target keeps its open requests; short so an instance refresh or scale-in is quick."
  type        = number
  default     = 30
}

variable "idle_timeout" {
  description = "Seconds an idle connection stays open; the agent streams answers, so longer than the 60 s default."
  type        = number
  default     = 120
}

variable "tags" {
  description = "Extra tags; project = nt548 is always added."
  type        = map(string)
  default     = {}
}
