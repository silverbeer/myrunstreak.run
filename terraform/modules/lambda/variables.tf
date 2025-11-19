# ==============================================================================
# Lambda Module - Input Variables
# ==============================================================================

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "execution_role_arn" {
  description = "ARN of the IAM execution role for Lambda"
  type        = string
}

variable "package_path" {
  description = "Path to the Lambda deployment package (ZIP file) - used for local development"
  type        = string
  default     = null
}

variable "s3_package_bucket" {
  description = "S3 bucket containing the Lambda deployment package"
  type        = string
  default     = null
}

variable "s3_package_key" {
  description = "S3 key (path) to the Lambda deployment package"
  type        = string
  default     = null
}

variable "handler" {
  description = "Lambda function handler (format: filename.function_name)"
  type        = string
  default     = "lambda_function.handler"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of S3 bucket for database storage"
  type        = string
}

variable "smashrun_secret_name" {
  description = "Name of Secrets Manager secret containing SmashRun credentials"
  type        = string
}

# Performance Configuration
variable "memory_size" {
  description = "Amount of memory in MB (128-10240)"
  type        = number
  default     = 512

  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "Memory size must be between 128 and 10240 MB."
  }
}

variable "timeout" {
  description = "Function timeout in seconds (1-900)"
  type        = number
  default     = 300  # 5 minutes

  validation {
    condition     = var.timeout >= 1 && var.timeout <= 900
    error_message = "Timeout must be between 1 and 900 seconds (15 minutes max)."
  }
}

variable "ephemeral_storage_size" {
  description = "Size of /tmp directory in MB (512-10240)"
  type        = number
  default     = 1024  # 1 GB for DuckDB operations

  validation {
    condition     = var.ephemeral_storage_size >= 512 && var.ephemeral_storage_size <= 10240
    error_message = "Ephemeral storage must be between 512 and 10240 MB."
  }
}

# Logging Configuration
variable "log_level" {
  description = "Python logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.log_level)
    error_message = "Log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL."
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 14

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch retention period."
  }
}

# Permissions
variable "api_gateway_execution_arn" {
  description = "Execution ARN of API Gateway (for Lambda permission)"
  type        = string
  default     = null
}

variable "eventbridge_rule_arn" {
  description = "ARN of EventBridge rule (for Lambda permission)"
  type        = string
  default     = null
}

# Monitoring
variable "enable_xray_tracing" {
  description = "Enable AWS X-Ray tracing for distributed tracing"
  type        = bool
  default     = false
}

variable "enable_alarms" {
  description = "Enable CloudWatch alarms for errors and throttling"
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "List of ARNs to notify when alarms trigger (e.g., SNS topic ARNs)"
  type        = list(string)
  default     = []
}

# Advanced Configuration
variable "extra_environment_variables" {
  description = "Additional environment variables to set"
  type        = map(string)
  default     = {}
}

variable "reserved_concurrent_executions" {
  description = "Number of concurrent executions to reserve (-1 for unreserved)"
  type        = number
  default     = -1
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
