variable "name_prefix" {
  description = "Prefix of every resource name, e.g. nt548 (one per member's lab)."
  type        = string
}

variable "cidr" {
  description = "VPC CIDR; each AZ gets the /24 at its index."
  type        = string
  default     = "10.48.0.0/16"

  validation {
    condition     = can(cidrhost(var.cidr, 0)) && tonumber(split("/", var.cidr)[1]) <= 22
    error_message = "Give a valid CIDR of /22 or larger (it is cut into /24 subnets, one per AZ)."
  }
}

variable "azs" {
  description = "Availability zones of the public subnets; an ALB needs at least two."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.azs) >= 2 && length(distinct(var.azs)) == length(var.azs)
    error_message = "Give at least two different availability zones (an ALB spans two)."
  }
}

variable "app_port" {
  description = "Port the app instances listen on (ops/nt548/compose/app.yml publishes 8080)."
  type        = number
  default     = 8080
}

variable "tags" {
  description = "Extra tags; project = nt548 is always added."
  type        = map(string)
  default     = {}
}
