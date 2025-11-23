# ==============================================================================
# EventBridge Module - Scheduled Lambda Invocation
# ==============================================================================
# This module creates an EventBridge (CloudWatch Events) rule that triggers
# Lambda on a cron schedule for automated daily syncs.
#
# EventBridge Pricing:
# - $1.00 per million custom events
# - Scheduled rules are free!
# - Our cost: $0.00/month
#
# Cron Expression Format (6 fields):
# cron(Minutes Hours Day-of-month Month Day-of-week Year)
#
# Examples:
# - cron(0 11 * * ? *)      - Every day at 11:00 UTC (6am EST)
# - cron(0 6 * * MON-FRI *)  - Weekdays at 6:00 UTC
# - cron(0 */6 * * ? *)     - Every 6 hours
#
# Learning Points:
# - EventBridge vs CloudWatch Events (EventBridge is the newer name)
# - Cron expressions (6 fields in AWS, not 5 like Linux)
# - UTC time zone (always use UTC, no daylight saving complexity)
# - Lambda permissions for EventBridge invocation
# ==============================================================================

# ------------------------------------------------------------------------------
# EventBridge Rules - Sync Schedules
# ------------------------------------------------------------------------------
# Triggers Lambda function at specified times

resource "aws_cloudwatch_event_rule" "sync" {
  for_each = { for s in var.schedules : s.name => s }

  name                = "${var.project_name}-sync-${each.key}-${var.environment}"
  description         = "Trigger Lambda to sync running data from SmashRun at ${each.value.description}"
  schedule_expression = each.value.expression

  # Enable/disable without deleting
  state = var.enabled ? "ENABLED" : "DISABLED"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-sync-${each.key}"
    }
  )
}

# Why UTC?
# - AWS always uses UTC for cron
# - No daylight saving time confusion
# - Convert local time to UTC:
#   - 6:00am EST = 11:00 UTC (winter)
#   - 6:00am EDT = 10:00 UTC (summer)
# - Using 11:00 UTC means it runs at 6am EST / 7am EDT
# - If you want consistent 6am year-round, use 11:00 UTC (winter time)

# ------------------------------------------------------------------------------
# EventBridge Targets - Lambda Function
# ------------------------------------------------------------------------------
# Defines what to invoke when each rule triggers

resource "aws_cloudwatch_event_target" "lambda" {
  for_each = aws_cloudwatch_event_rule.sync

  rule      = each.value.name
  target_id = "lambda-sync-runner"
  arn       = var.lambda_function_arn

  # Input to pass to Lambda (optional)
  # Can pass custom JSON payload to distinguish scheduled vs API-triggered runs
  input = jsonencode(merge(
    var.custom_input != null ? var.custom_input : {},
    {
      schedule = each.key
    }
  ))

  # Retry policy
  retry_policy {
    maximum_event_age_in_seconds = var.maximum_event_age_seconds
    maximum_retry_attempts       = var.maximum_retry_attempts
  }

  # Dead letter queue (optional)
  # Send failed invocations to SQS/SNS for investigation
  dynamic "dead_letter_config" {
    for_each = var.dlq_arn != null ? [1] : []
    content {
      arn = var.dlq_arn
    }
  }
}

# What's the difference between input and input_transformer?
# - input: Static JSON string
# - input_transformer: Can extract data from the event and insert into template
# Example use case: Pass the rule name to Lambda so it knows why it was invoked

# ------------------------------------------------------------------------------
# CloudWatch Metric Alarms - Invocation Failures
# ------------------------------------------------------------------------------
# Alert if EventBridge fails to invoke Lambda

resource "aws_cloudwatch_metric_alarm" "invocation_failures" {
  for_each = var.enable_alarms ? aws_cloudwatch_event_rule.sync : {}

  alarm_name          = "${var.project_name}-eventbridge-failures-${each.key}-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FailedInvocations"
  namespace           = "AWS/Events"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "EventBridge failed to invoke Lambda for ${each.key} schedule"
  treat_missing_data  = "notBreaching"

  dimensions = {
    RuleName = each.value.name
  }

  alarm_actions = var.alarm_actions
}

# ------------------------------------------------------------------------------
# CloudWatch Log Group for EventBridge (Optional)
# ------------------------------------------------------------------------------
# EventBridge can log all events to CloudWatch for debugging
# This is optional and costs extra ($0.50/GB for log storage)

# Uncomment to enable detailed EventBridge logging:
# resource "aws_cloudwatch_log_group" "eventbridge" {
#   name              = "/aws/events/${var.project_name}-${var.environment}"
#   retention_in_days = var.log_retention_days
#
#   tags = var.tags
# }

# ------------------------------------------------------------------------------
# Additional Scheduled Rules (Optional)
# ------------------------------------------------------------------------------
# If you want multiple schedules, create additional rules here

# Example: Hourly health check
# resource "aws_cloudwatch_event_rule" "hourly_check" {
#   name                = "${var.project_name}-hourly-check-${var.environment}"
#   description         = "Hourly health check"
#   schedule_expression = "cron(0 * * * ? *)"  # Every hour
#   is_enabled          = var.enabled
#
#   tags = var.tags
# }
#
# resource "aws_cloudwatch_event_target" "hourly_lambda" {
#   rule      = aws_cloudwatch_event_rule.hourly_check.name
#   target_id = "lambda-health-check"
#   arn       = var.lambda_function_arn
#
#   input = jsonencode({
#     action = "health_check"
#   })
# }
