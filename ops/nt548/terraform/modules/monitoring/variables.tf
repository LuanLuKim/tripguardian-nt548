variable "name_prefix" {
  description = "Prefix of every name, e.g. nt548 (one per member's lab); also the dashboard name."
  type        = string
}

variable "region" {
  description = "Region of the metrics shown on the dashboard."
  type        = string
  default     = "us-east-1"
}

variable "alb_arn_suffix" {
  description = "aws_lb.arn_suffix of the ALB (app/<name>/<id>), from modules/alb."
  type        = string
}

variable "target_groups" {
  description = "color => target group arn_suffix (targetgroup/<name>/<id>), from modules/alb."
  type        = map(string)

  validation {
    condition     = length(var.target_groups) > 0
    error_message = "Give at least one target group."
  }
}

variable "asg_names" {
  description = "color => ASG name, from modules/app_asg (CPU and instance count on the dashboard)."
  type        = map(string)
}

variable "colors" {
  description = "color => line color on the dashboard."
  type        = map(string)
  default     = { blue = "#1f77b4", green = "#2ca02c" }
}

variable "alarm_email" {
  description = "Address that gets the alarms (confirm the mail AWS sends first). Empty: no subscription, incident.py polls."
  type        = string
  default     = ""
}

variable "errors_per_minute" {
  description = "5xx per period above which the 5xx alarms fire."
  type        = number
  default     = 5
}

variable "p95_seconds" {
  description = "p95 latency (seconds) above which the latency alarms fire."
  type        = number
  default     = 1.5
}

variable "cpu_target" {
  description = "Target of the ASG scaling policy, drawn as a line on the CPU widget."
  type        = number
  default     = 50
}

variable "period" {
  description = "Seconds per datapoint."
  type        = number
  default     = 60
}

variable "evaluation_periods" {
  type    = number
  default = 3
}

variable "datapoints_to_alarm" {
  description = "How many of evaluation_periods must breach (M of N)."
  type        = number
  default     = 2
}

variable "log_retention_days" {
  description = "Days the container logs are kept."
  type        = number
  default     = 7
}

variable "extra_alarm_arns" {
  description = "More alarms for the dashboard's alarm widget (the anomaly alarms of modules/aiops)."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
