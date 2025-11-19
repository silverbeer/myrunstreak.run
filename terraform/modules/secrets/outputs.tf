# ==============================================================================
# Secrets Manager Module - Outputs
# ==============================================================================

output "smashrun_oauth_secret_arn" {
  description = "ARN of the SmashRun OAuth secret"
  value       = aws_secretsmanager_secret.smashrun_oauth.arn
}

output "smashrun_oauth_secret_name" {
  description = "Name of the SmashRun OAuth secret"
  value       = aws_secretsmanager_secret.smashrun_oauth.name
}

output "api_keys_secret_arn" {
  description = "ARN of the API keys secret"
  value       = aws_secretsmanager_secret.api_keys.arn
}

output "api_keys_secret_name" {
  description = "Name of the API keys secret"
  value       = aws_secretsmanager_secret.api_keys.name
}

output "supabase_secret_arn" {
  description = "ARN of the Supabase credentials secret"
  value       = aws_secretsmanager_secret.supabase.arn
}

output "supabase_secret_name" {
  description = "Name of the Supabase credentials secret"
  value       = aws_secretsmanager_secret.supabase.name
}

# Note: We don't output secret values for security
# Lambda reads secrets directly from Secrets Manager at runtime
