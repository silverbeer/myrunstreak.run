# ==============================================================================
# EventBridge Module - Outputs
# ==============================================================================

output "rule_names" {
  description = "Names of the EventBridge rules"
  value       = { for k, v in aws_cloudwatch_event_rule.sync : k => v.name }
}

output "rule_arns" {
  description = "ARNs of the EventBridge rules"
  value       = { for k, v in aws_cloudwatch_event_rule.sync : k => v.arn }
}

output "rule_ids" {
  description = "IDs of the EventBridge rules"
  value       = { for k, v in aws_cloudwatch_event_rule.sync : k => v.id }
}

output "schedule_expressions" {
  description = "Cron/rate expressions for the schedules"
  value       = { for k, v in aws_cloudwatch_event_rule.sync : k => v.schedule_expression }
}

output "is_enabled" {
  description = "Whether the rules are currently enabled"
  value       = length(aws_cloudwatch_event_rule.sync) > 0 ? values(aws_cloudwatch_event_rule.sync)[0].state == "ENABLED" : false
}
