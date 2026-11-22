variable "name_prefix" {
  description = "Prefix of every alarm name, e.g. nt548 (one per member's lab)."
  type        = string
}

variable "alb_arn_suffix" {
  description = "aws_lb.arn_suffix of the ALB (app/<name>/<id>)."
  type        = string
}

variable "target_groups" {
  description = "color => aws_lb_target_group.arn_suffix (targetgroup/<name>/<id>), e.g. { blue = ..., green = ... }."
  type        = map(string)

  validation {
    condition     = length(var.target_groups) > 0
    error_message = "Give at least one target group."
  }
}

variable "band_width" {
  description = "Width of the expected band in standard deviations; wider means fewer false alarms and later detection."
  type        = number
  default     = 2
}

variable "period" {
  description = "Seconds per datapoint."
  type        = number
  default     = 60
}

variable "evaluation_periods" {
  description = "Datapoints looked at for each evaluation."
  type        = number
  default     = 3
}

variable "datapoints_to_alarm" {
  description = "How many of those must be outside the band (M of N), like --persist of detect.py."
  type        = number
  default     = 2
}

variable "alarm_actions" {
  description = "ARNs notified on ALARM and OK (e.g. an SNS topic of the monitoring module); empty is fine, incident.py polls."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
