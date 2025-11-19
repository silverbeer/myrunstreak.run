# ==============================================================================
# Secrets Manager Module - Input Variables
# ==============================================================================

variable "project_name" {
  description = "Name of the project (used in secret naming)"
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

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# SmashRun OAuth Credentials
# These should be passed from terraform.tfvars (not committed to git)
variable "smashrun_client_id" {
  description = "SmashRun OAuth client ID"
  type        = string
  sensitive   = true
}

variable "smashrun_client_secret" {
  description = "SmashRun OAuth client secret"
  type        = string
  sensitive   = true
}

variable "smashrun_access_token" {
  description = "SmashRun OAuth access token"
  type        = string
  sensitive   = true
}

variable "smashrun_refresh_token" {
  description = "SmashRun OAuth refresh token"
  type        = string
  sensitive   = true
}

# API Gateway API Keys
variable "api_key_personal" {
  description = "Personal API key for API Gateway"
  type        = string
  sensitive   = true
}

# Supabase Credentials
variable "supabase_url" {
  description = "Supabase project URL (e.g., https://xxxxx.supabase.co)"
  type        = string
  sensitive   = true
}

variable "supabase_service_role_key" {
  description = "Supabase service role key (bypasses RLS, use with caution)"
  type        = string
  sensitive   = true
}

# Optional Features
variable "enable_rotation" {
  description = "Enable automatic secret rotation"
  type        = bool
  default     = false
}

variable "rotation_lambda_arn" {
  description = "ARN of Lambda function for secret rotation (required if enable_rotation = true)"
  type        = string
  default     = null
}

variable "enable_age_monitoring" {
  description = "Enable CloudWatch alarm for secret age"
  type        = bool
  default     = false
}

variable "max_secret_age_days" {
  description = "Maximum secret age in days before alarming"
  type        = number
  default     = 90
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms (optional)"
  type        = string
  default     = null
}

variable "use_custom_kms_key" {
  description = "Use customer-managed KMS key instead of AWS-managed"
  type        = bool
  default     = false
}
