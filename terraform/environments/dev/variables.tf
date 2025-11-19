variable "aws_region" {
  description = "AWS region for infrastructure"
  type        = string
  default     = "us-east-2"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"
}

variable "smashrun_client_id" {
  description = "SmashRun OAuth Client ID"
  type        = string
  sensitive   = true
}

variable "smashrun_client_secret" {
  description = "SmashRun OAuth Client Secret"
  type        = string
  sensitive   = true
}

variable "smashrun_access_token" {
  description = "SmashRun OAuth Access Token"
  type        = string
  sensitive   = true
}

variable "smashrun_refresh_token" {
  description = "SmashRun OAuth Refresh Token"
  type        = string
  sensitive   = true
}

variable "api_key_personal" {
  description = "Personal API key for API Gateway"
  type        = string
  sensitive   = true
}

variable "supabase_url" {
  description = "Supabase project URL (e.g., https://xxxxx.supabase.co)"
  type        = string
  sensitive   = true
}

variable "supabase_service_role_key" {
  description = "Supabase service role key for Lambda access (bypasses RLS)"
  type        = string
  sensitive   = true
}

variable "lambda_package_path" {
  description = "Path to Lambda deployment package (ZIP file) - for local development"
  type        = string
  default     = null
}

variable "lambda_s3_bucket" {
  description = "S3 bucket containing Lambda deployment packages (for CI/CD)"
  type        = string
  default     = null
}

variable "lambda_s3_key_sync" {
  description = "S3 key for sync Lambda deployment package"
  type        = string
  default     = "lambda-packages/sync-runner/latest.zip"
}

variable "lambda_s3_key_query" {
  description = "S3 key for query Lambda deployment package"
  type        = string
  default     = "lambda-packages/query-runner/latest.zip"
}

variable "lambda_log_level" {
  description = "Python logging level for Lambda function"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], var.lambda_log_level)
    error_message = "Log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL."
  }
}

variable "eventbridge_enabled" {
  description = "Enable/disable the daily EventBridge schedule"
  type        = bool
  default     = true
}
