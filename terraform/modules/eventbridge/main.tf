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
# EventBridge Rule - Daily Sync Schedule
# ------------------------------------------------------------------------------
# Triggers Lambda function daily at specified time

resource "aws_cloudwatch_event_rule" "daily_sync" {
  name                = "${var.project_name}-daily-sync-${var.environment}"
  description         = "Trigger Lambda to sync running data from SmashRun daily at ${var.schedule_description}"
  schedule_expression = var.schedule_expression

  # Enable/disable without deleting
  is_enabled = var.enabled

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-daily-sync"
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
# EventBridge Target - Lambda Function
# ------------------------------------------------------------------------------
# Defines what to invoke when the rule triggers

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.daily_sync.name
  target_id = "lambda-sync-runner"
  arn       = var.lambda_function_arn

  # Input to pass to Lambda (optional)
  # Can pass custom JSON payload to distinguish scheduled vs API-triggered runs
  dynamic "input_transformer" {
    for_each = var.custom_input != null ? [1] : []
    content {
      input_paths = {}
      input_template = jsonencode(var.custom_input)
    }
  }

  # Retry policy
  retry_policy {
    maximum_event_age       = var.maximum_event_age_seconds
    maximum_retry_attempts  = var.maximum_retry_attempts
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
# CloudWatch Metric Alarm - Invocation Failures
# ------------------------------------------------------------------------------
# Alert if EventBridge fails to invoke Lambda

resource "aws_cloudwatch_metric_alarm" "invocation_failures" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-eventbridge-failures-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FailedInvocations"
  namespace           = "AWS/Events"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "EventBridge failed to invoke Lambda"
  treat_missing_data  = "notBreaching"

  dimensions = {
    RuleName = aws_cloudwatch_event_rule.daily_sync.name
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
