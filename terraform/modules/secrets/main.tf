# ==============================================================================
# Secrets Manager Module - Secure Credential Storage
# ==============================================================================
# This module creates AWS Secrets Manager secrets for:
# - SmashRun OAuth credentials (client ID, secret, tokens)
# - API Gateway API keys
#
# Key Features:
# - Encrypted at rest with KMS
# - Version history (can rollback)
# - Automatic rotation (optional)
# - Recovery window (prevents accidental deletion)
# - IAM access control
#
# Security Benefits over Environment Variables:
# - Not visible in AWS console
# - Separate encryption per secret
# - Audit trail in CloudTrail
# - Can rotate without redeploying Lambda
#
# Learning Points:
# - Secret vs secret version
# - JSON secret strings
# - Recovery window
# - Sensitive variables in Terraform
# ==============================================================================

# ------------------------------------------------------------------------------
# SmashRun OAuth Credentials Secret
# ------------------------------------------------------------------------------
# Stores all SmashRun API credentials in a single JSON secret
# Format: {
#   "client_id": "streak_xxxxx",
#   "client_secret": "xxxxxxxx",
#   "access_token": "xxxxxxxx",
#   "refresh_token": "xxxxxxxx"
# }

resource "aws_secretsmanager_secret" "smashrun_oauth" {
  name        = "${var.project_name}/${var.environment}/smashrun/oauth"
  description = "SmashRun OAuth credentials for API access"

  # Recovery window - can recover secret if accidentally deleted
  # Set to 0 in dev for immediate deletion (easier testing)
  recovery_window_in_days = var.environment == "dev" ? 0 : 30

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-smashrun-oauth"
      Description = "SmashRun OAuth tokens"
      Rotation    = var.enable_rotation ? "Enabled" : "Disabled"
    }
  )
}

# Why JSON format instead of separate secrets?
# - Single API call to get all credentials (faster, cheaper)
# - Atomic updates (all credentials change together)
# - Easier to manage related credentials
# - SmashRun tokens should always be in sync

# Secret Version - The actual secret value
resource "aws_secretsmanager_secret_version" "smashrun_oauth" {
  secret_id = aws_secretsmanager_secret.smashrun_oauth.id

  secret_string = jsonencode({
    client_id     = var.smashrun_client_id
    client_secret = var.smashrun_client_secret
    access_token  = var.smashrun_access_token
    refresh_token = var.smashrun_refresh_token
  })

  # Lifecycle prevents recreation on every apply
  # Secret values should be updated manually or via rotation lambda
  lifecycle {
    ignore_changes = [
      secret_string
    ]
  }
}

# Why ignore_changes?
# - After initial creation, secret may be updated by:
#   - Manual update in console
#   - Rotation Lambda
#   - Application code
# - Don't want Terraform to overwrite these updates
# - Terraform manages the secret resource, not its value

# ------------------------------------------------------------------------------
# Supabase Credentials Secret
# ------------------------------------------------------------------------------
# Stores Supabase URL and service role key
# Used by Lambda functions to connect to PostgreSQL database

resource "aws_secretsmanager_secret" "supabase" {
  name                    = "${var.project_name}/${var.environment}/supabase/credentials"
  description             = "Supabase PostgreSQL database credentials"
  recovery_window_in_days = var.environment == "dev" ? 0 : 30

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-supabase-credentials"
      Description = "Supabase database access"
    }
  )
}

resource "aws_secretsmanager_secret_version" "supabase" {
  secret_id = aws_secretsmanager_secret.supabase.id

  secret_string = jsonencode({
    url = var.supabase_url
    key = var.supabase_service_role_key
  })

  lifecycle {
    ignore_changes = [
      secret_string
    ]
  }
}

# ------------------------------------------------------------------------------
# API Gateway API Keys Secret
# ------------------------------------------------------------------------------
# Stores API keys for API Gateway access
# Separate from SmashRun because they have different lifecycles

resource "aws_secretsmanager_secret" "api_keys" {
  name                    = "${var.project_name}/${var.environment}/api/keys"
  description             = "API Gateway API keys for authenticated access"
  recovery_window_in_days = var.environment == "dev" ? 0 : 30

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-api-keys"
      Description = "API Gateway access keys"
    }
  )
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id

  secret_string = jsonencode({
    personal_key = var.api_key_personal
    # Add more keys as needed:
    # github_actions_key = var.api_key_github_actions
    # mobile_app_key = var.api_key_mobile_app
  })

  lifecycle {
    ignore_changes = [
      secret_string
    ]
  }
}

# ------------------------------------------------------------------------------
# Automatic Rotation Configuration (Optional)
# ------------------------------------------------------------------------------
# Secrets Manager can automatically rotate secrets using a Lambda function
# This is advanced - not implementing initially but structure is here

# resource "aws_secretsmanager_secret_rotation" "smashrun_oauth" {
#   count               = var.enable_rotation ? 1 : 0
#   secret_id           = aws_secretsmanager_secret.smashrun_oauth.id
#   rotation_lambda_arn = var.rotation_lambda_arn
#
#   rotation_rules {
#     automatically_after_days = 90  # Rotate every 90 days
#   }
# }

# How rotation works:
# 1. Secrets Manager invokes rotation Lambda
# 2. Lambda calls SmashRun API to refresh tokens
# 3. Lambda updates secret with new tokens
# 4. Old tokens remain valid during rotation
# 5. After verification, old tokens are revoked
#
# Benefits:
# - No manual token management
# - Reduces risk of token leakage
# - Compliance requirement for some organizations

# ------------------------------------------------------------------------------
# CloudWatch Metric Alarm - Secret Age
# ------------------------------------------------------------------------------
# Alert if secret hasn't been rotated in X days (if not using auto-rotation)

resource "aws_cloudwatch_metric_alarm" "secret_age" {
  count = var.enable_age_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-secret-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "SecretAge"
  namespace           = "AWS/SecretsManager"
  period              = "86400"  # Daily check
  statistic           = "Maximum"
  threshold           = var.max_secret_age_days
  alarm_description   = "Secret has not been rotated recently"
  treat_missing_data  = "notBreaching"

  dimensions = {
    SecretId = aws_secretsmanager_secret.smashrun_oauth.id
  }

  alarm_actions = var.alarm_sns_topic_arn != null ? [var.alarm_sns_topic_arn] : []
}

# ------------------------------------------------------------------------------
# KMS Key for Secret Encryption (Optional - Enhanced Security)
# ------------------------------------------------------------------------------
# By default, Secrets Manager uses AWS-managed KMS key (free)
# For enhanced control, create a customer-managed key

# Uncomment to use customer-managed KMS key:
# resource "aws_kms_key" "secrets" {
#   count = var.use_custom_kms_key ? 1 : 0
#
#   description             = "KMS key for ${var.project_name} secrets encryption"
#   deletion_window_in_days = 30
#   enable_key_rotation     = true
#
#   tags = merge(
#     var.tags,
#     {
#       Name = "${var.project_name}-secrets-kms"
#     }
#   )
# }
#
# resource "aws_kms_alias" "secrets" {
#   count = var.use_custom_kms_key ? 1 : 0
#
#   name          = "alias/${var.project_name}-secrets"
#   target_key_id = aws_kms_key.secrets[0].key_id
# }
#
# Then add to secret resource:
#   kms_key_id = var.use_custom_kms_key ? aws_kms_key.secrets[0].arn : null

# Cost comparison:
# - AWS-managed KMS key: $0 (included with Secrets Manager)
# - Customer-managed KMS key: $1/month + $0.03 per 10k API calls
#
# Benefits of customer-managed key:
# - Full control over key policies
# - Can grant cross-account access
# - Can disable/re-enable key
# - Detailed CloudTrail logs
#
# For MyRunStreak: AWS-managed key is sufficient
