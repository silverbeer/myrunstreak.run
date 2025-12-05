# ==============================================================================
# API Gateway Consumer Module - Input Variables
# ==============================================================================

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

# Sync Lambda
variable "sync_lambda_invoke_arn" {
  description = "Invoke ARN of the sync Lambda function"
  type        = string
}

variable "sync_lambda_function_name" {
  description = "Name of the sync Lambda function (for permissions)"
  type        = string
}

# Query Lambda
variable "query_lambda_invoke_arn" {
  description = "Invoke ARN of the query Lambda function"
  type        = string
}

variable "query_lambda_function_name" {
  description = "Name of the query Lambda function (for permissions)"
  type        = string
}
