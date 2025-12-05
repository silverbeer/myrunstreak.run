# ==============================================================================
# API Gateway Consumer Module - Outputs
# ==============================================================================

output "api_gateway_id" {
  description = "API Gateway REST API ID (from SSM)"
  value       = local.api_gateway_id
  sensitive   = true
}

output "api_gateway_invoke_url" {
  description = "API Gateway invoke URL (from SSM)"
  value       = local.api_invoke_url
  sensitive   = true
}

output "api_gateway_execution_arn" {
  description = "API Gateway execution ARN (from SSM)"
  value       = local.api_execution_arn
  sensitive   = true
}

output "stage_name" {
  description = "API Gateway stage name (from SSM)"
  value       = local.stage_name
  sensitive   = true
}

# Endpoint URLs
output "sync_endpoint" {
  description = "Full URL for the sync endpoint"
  value       = "${local.api_invoke_url}/sync"
  sensitive   = true
}

output "stats_endpoint" {
  description = "Base URL for stats endpoints"
  value       = "${local.api_invoke_url}/stats"
  sensitive   = true
}

output "runs_endpoint" {
  description = "Base URL for runs endpoints"
  value       = "${local.api_invoke_url}/runs"
  sensitive   = true
}

output "auth_endpoint" {
  description = "Base URL for auth endpoints"
  value       = "${local.api_invoke_url}/auth"
  sensitive   = true
}

# Deployment ID (for debugging)
output "deployment_id" {
  description = "Current API Gateway deployment ID"
  value       = aws_api_gateway_deployment.myrunstreak.id
}
