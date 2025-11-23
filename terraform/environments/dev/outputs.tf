output "account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "region" {
  description = "AWS Region"
  value       = data.aws_region.current.name
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

# ==============================================================================
# S3 Outputs
# ==============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 bucket storing the DuckDB database"
  value       = module.s3.bucket_id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3.bucket_arn
}

# ==============================================================================
# IAM Outputs
# ==============================================================================

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = module.iam.lambda_execution_role_arn
}

# ==============================================================================
# Secrets Manager Outputs
# ==============================================================================

output "smashrun_secret_name" {
  description = "Name of the SmashRun OAuth secret"
  value       = module.secrets.smashrun_oauth_secret_name
}

output "api_keys_secret_name" {
  description = "Name of the API keys secret"
  value       = module.secrets.api_keys_secret_name
}

# ==============================================================================
# Lambda Outputs
# ==============================================================================

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.lambda.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.lambda.function_arn
}

output "lambda_log_group_name" {
  description = "Name of the Lambda CloudWatch log group"
  value       = module.lambda.log_group_name
}

# ==============================================================================
# Publish Status Lambda Outputs
# ==============================================================================

output "publish_status_function_name" {
  description = "Name of the publish status Lambda function"
  value       = module.lambda_publish_status.function_name
}

output "publish_status_function_arn" {
  description = "ARN of the publish status Lambda function"
  value       = module.lambda_publish_status.function_arn
}

# ==============================================================================
# ECR Outputs
# ==============================================================================

output "ecr_sync_repository_url" {
  description = "URL of the sync Lambda ECR repository"
  value       = module.ecr.sync_repository_url
}

output "ecr_query_repository_url" {
  description = "URL of the query Lambda ECR repository"
  value       = module.ecr.query_repository_url
}

output "ecr_publish_status_repository_url" {
  description = "URL of the publish status Lambda ECR repository"
  value       = module.ecr.publish_status_repository_url
}

# ==============================================================================
# GitHub OIDC Outputs
# ==============================================================================

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions deploy role (set this as AWS_LAMBDA_DEPLOY_ROLE_ARN secret in GitHub)"
  value       = module.github_oidc.deploy_role_arn
}

# ==============================================================================
# API Gateway Outputs
# ==============================================================================

output "api_gateway_url" {
  description = "Base URL of the API Gateway"
  value       = module.api_gateway.api_endpoint
}

output "api_sync_endpoint" {
  description = "Full URL for the sync endpoint"
  value       = module.api_gateway.sync_endpoint
}

output "api_health_endpoint" {
  description = "Full URL for the health check endpoint"
  value       = module.api_gateway.health_endpoint
}

output "api_key_value" {
  description = "API Gateway API key (sensitive - use with caution)"
  value       = module.api_gateway.api_key_value
  sensitive   = true
}

# ==============================================================================
# EventBridge Outputs
# ==============================================================================

output "eventbridge_rule_names" {
  description = "Names of the EventBridge rules for syncs"
  value       = module.eventbridge.rule_names
}

output "eventbridge_schedules" {
  description = "Cron expressions for the sync schedules"
  value       = module.eventbridge.schedule_expressions
}

output "eventbridge_enabled" {
  description = "Whether the EventBridge rules are currently enabled"
  value       = module.eventbridge.is_enabled
}

# ==============================================================================
# Deployment Instructions
# ==============================================================================

output "deployment_instructions" {
  description = "Instructions for testing the deployment"
  value = <<-EOT

    🎉 MyRunStreak.com Infrastructure Deployed Successfully! 🎉

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📍 API Endpoints:

    Health Check (public):
      curl ${module.api_gateway.health_endpoint}

    Manual Sync (requires API key):
      curl -X POST ${module.api_gateway.sync_endpoint} \
           -H "x-api-key: YOUR_API_KEY_HERE"

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    🔑 Get your API key:
      terraform output -raw api_key_value

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ⏰ Automated Sync Schedules:
      Morning: 9am EST / 10am EDT (14:00 UTC)
      Midday:  12pm EST / 1pm EDT (17:00 UTC)
      Status: ${module.eventbridge.is_enabled ? "ENABLED ✓" : "DISABLED ✗"}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📊 Monitoring:
      Lambda Logs:    https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#logsV2:log-groups/log-group/${replace(module.lambda.log_group_name, "/", "$252F")}
      API Gateway:    https://console.aws.amazon.com/apigateway/home?region=${data.aws_region.current.name}#/apis/${module.api_gateway.api_id}
      S3 Bucket:      https://s3.console.aws.amazon.com/s3/buckets/${module.s3.bucket_id}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📝 Next Steps:

    1. Upload initial DuckDB database to S3:
       aws s3 cp data/runs.duckdb s3://${module.s3.bucket_id}/runs.duckdb

    2. Test the health endpoint (no auth needed):
       curl ${module.api_gateway.health_endpoint}

    3. Get your API key and test manual sync:
       API_KEY=$(terraform output -raw api_key_value)
       curl -X POST ${module.api_gateway.sync_endpoint} -H "x-api-key: $API_KEY"

    4. View Lambda logs:
       aws logs tail ${module.lambda.log_group_name} --follow

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  EOT
}
