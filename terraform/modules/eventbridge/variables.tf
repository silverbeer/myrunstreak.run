# ==============================================================================
# EventBridge Module - Input Variables
# ==============================================================================

variable "project_name" {
  description = "Name of the project (used in rule naming)"
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

variable "lambda_function_arn" {
  description = "ARN of the Lambda function to invoke"
  type        = string
}

# Schedule Configuration
variable "schedules" {
  description = "List of schedules with name, cron expression, and description"
  type = list(object({
    name        = string
    expression  = string
    description = string
  }))
  default = [
    {
      name        = "morning"
      expression  = "cron(0 14 * * ? *)"
      description = "9am EST / 10am EDT (14:00 UTC)"
    }
  ]
}

variable "enabled" {
  description = "Whether the EventBridge rule is enabled"
  type        = bool
  default     = true
}

# Input Configuration
variable "custom_input" {
  description = "Custom JSON input to pass to Lambda (optional)"
  type        = map(any)
  default     = null

  # Example:
  # {
  #   "source": "eventbridge",
  #   "action": "daily_sync"
  # }
}

# Retry Configuration
variable "maximum_event_age_seconds" {
  description = "Maximum age of event before discarding (60-86400)"
  type        = number
  default     = 3600  # 1 hour

  validation {
    condition     = var.maximum_event_age_seconds >= 60 && var.maximum_event_age_seconds <= 86400
    error_message = "Maximum event age must be between 60 and 86400 seconds."
  }
}

variable "maximum_retry_attempts" {
  description = "Maximum number of retry attempts (0-185)"
  type        = number
  default     = 2

  validation {
    condition     = var.maximum_retry_attempts >= 0 && var.maximum_retry_attempts <= 185
    error_message = "Maximum retry attempts must be between 0 and 185."
  }
}

# Dead Letter Queue
variable "dlq_arn" {
  description = "ARN of SQS queue or SNS topic for failed invocations (optional)"
  type        = string
  default     = null
}

# Monitoring
variable "enable_alarms" {
  description = "Enable CloudWatch alarms for invocation failures"
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "List of ARNs to notify when alarms trigger (e.g., SNS topic ARNs)"
  type        = list(string)
  default     = []
}

# Logging
variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days (if logging enabled)"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
