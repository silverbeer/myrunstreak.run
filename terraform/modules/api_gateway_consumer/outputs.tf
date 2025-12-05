# ==============================================================================
# API Gateway Consumer Module - Outputs
# ==============================================================================

output "api_gateway_id" {
  description = "API Gateway REST API ID (from SSM)"
  value       = local.api_gateway_id
}

output "api_gateway_invoke_url" {
  description = "API Gateway invoke URL (from SSM)"
  value       = local.api_invoke_url
}

output "api_gateway_execution_arn" {
  description = "API Gateway execution ARN (from SSM)"
  value       = local.api_execution_arn
}

output "stage_name" {
  description = "API Gateway stage name (from SSM)"
  value       = local.stage_name
}

# Endpoint URLs
output "sync_endpoint" {
  description = "Full URL for the sync endpoint"
  value       = "${local.api_invoke_url}/sync"
}

output "stats_endpoint" {
  description = "Base URL for stats endpoints"
  value       = "${local.api_invoke_url}/stats"
}

output "runs_endpoint" {
  description = "Base URL for runs endpoints"
  value       = "${local.api_invoke_url}/runs"
}

output "auth_endpoint" {
  description = "Base URL for auth endpoints"
  value       = "${local.api_invoke_url}/auth"
}

# Deployment ID (for debugging)
output "deployment_id" {
  description = "Current API Gateway deployment ID"
  value       = aws_api_gateway_deployment.myrunstreak.id
}
