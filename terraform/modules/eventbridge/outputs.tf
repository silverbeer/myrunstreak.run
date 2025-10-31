# ==============================================================================
# EventBridge Module - Outputs
# ==============================================================================

output "rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_sync.name
}

output "rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_sync.arn
}

output "rule_id" {
  description = "ID of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_sync.id
}

output "schedule_expression" {
  description = "Cron/rate expression for the schedule"
  value       = aws_cloudwatch_event_rule.daily_sync.schedule_expression
}

output "is_enabled" {
  description = "Whether the rule is currently enabled"
  value       = aws_cloudwatch_event_rule.daily_sync.is_enabled
}
