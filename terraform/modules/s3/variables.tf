# ==============================================================================
# S3 Module - Input Variables
# ==============================================================================

variable "project_name" {
  description = "Name of the project (used in bucket naming)"
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

variable "account_id" {
  description = "AWS account ID (for globally unique bucket name)"
  type        = string
}

variable "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role (for bucket policy)"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# CORS Configuration
variable "enable_cors" {
  description = "Enable CORS configuration for web access"
  type        = bool
  default     = false
}

variable "cors_allowed_origins" {
  description = "List of origins allowed to access the bucket via CORS"
  type        = list(string)
  default     = ["https://myrunstreak.com"]
}

# Monitoring Configuration
variable "enable_monitoring" {
  description = "Enable CloudWatch alarms for bucket monitoring"
  type        = bool
  default     = true
}

variable "max_bucket_size_bytes" {
  description = "Maximum bucket size in bytes before alerting"
  type        = number
  default     = 1073741824 # 1 GB
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms (optional)"
  type        = string
  default     = null
}
