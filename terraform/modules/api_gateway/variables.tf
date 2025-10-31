# ==============================================================================
# API Gateway Module - Input Variables
# ==============================================================================

variable "project_name" {
  description = "Name of the project (used in API naming)"
  type        = string
  default     = "myrunstreak"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function to integrate with"
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function (for permissions)"
  type        = string
}

# Rate Limiting
variable "burst_limit" {
  description = "Maximum number of concurrent requests (burst)"
  type        = number
  default     = 10
}

variable "rate_limit" {
  description = "Sustained request rate limit (requests per second)"
  type        = number
  default     = 5
}

# Quota
variable "quota_limit" {
  description = "Total number of requests allowed per quota period"
  type        = number
  default     = 1000
}

variable "quota_period" {
  description = "Quota period (DAY, WEEK, or MONTH)"
  type        = string
  default     = "DAY"

  validation {
    condition     = contains(["DAY", "WEEK", "MONTH"], var.quota_period)
    error_message = "Quota period must be DAY, WEEK, or MONTH."
  }
}

# Logging
variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 14
}

variable "logging_level" {
  description = "API Gateway execution logging level (OFF, ERROR, INFO)"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["OFF", "ERROR", "INFO"], var.logging_level)
    error_message = "Logging level must be OFF, ERROR, or INFO."
  }
}

# Monitoring
variable "enable_xray_tracing" {
  description = "Enable AWS X-Ray tracing"
  type        = bool
  default     = false
}

variable "enable_alarms" {
  description = "Enable CloudWatch alarms for API Gateway"
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "List of ARNs to notify when alarms trigger (e.g., SNS topic ARNs)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
