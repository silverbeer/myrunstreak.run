# ==============================================================================
# API Gateway Module - Outputs
# ==============================================================================

output "api_id" {
  description = "ID of the REST API"
  value       = aws_api_gateway_rest_api.main.id
}

output "api_arn" {
  description = "ARN of the REST API"
  value       = aws_api_gateway_rest_api.main.arn
}

output "api_endpoint" {
  description = "Base URL of the API Gateway stage"
  value       = aws_api_gateway_stage.main.invoke_url
}

output "api_execution_arn" {
  description = "Execution ARN of the REST API (for Lambda permissions)"
  value       = aws_api_gateway_rest_api.main.execution_arn
}

output "stage_name" {
  description = "Name of the deployed stage"
  value       = aws_api_gateway_stage.main.stage_name
}

output "api_key_id" {
  description = "ID of the personal API key"
  value       = aws_api_gateway_api_key.personal.id
}

output "api_key_value" {
  description = "Value of the personal API key (sensitive)"
  value       = aws_api_gateway_api_key.personal.value
  sensitive   = true
}

output "usage_plan_id" {
  description = "ID of the usage plan"
  value       = aws_api_gateway_usage_plan.main.id
}

output "sync_endpoint" {
  description = "Full URL for the sync endpoint"
  value       = "${aws_api_gateway_stage.main.invoke_url}/sync"
}

output "health_endpoint" {
  description = "Full URL for the health endpoint"
  value       = "${aws_api_gateway_stage.main.invoke_url}/health"
}
