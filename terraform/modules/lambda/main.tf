# ==============================================================================
# Lambda Module - Serverless Sync Function
# ==============================================================================
# This module creates the Lambda function that:
# - Downloads runs.duckdb from S3
# - Fetches new activities from SmashRun API
# - Updates DuckDB database
# - Uploads updated database back to S3
#
# Lambda Pricing Model:
# - $0.20 per 1M requests
# - $0.0000166667 per GB-second
# - First 1M requests + 400,000 GB-seconds free per month
#
# Our estimated cost:
# - 31 requests/month (daily sync)
# - 512 MB × 30 sec × 31 = 465 GB-seconds
# - Total: <$0.01/month (within free tier)
#
# Learning Points:
# - Lambda execution model (event-driven)
# - Cold starts vs warm starts
# - Memory allocation (affects CPU)
# - Timeout configuration
# - Environment variables vs Secrets Manager
# - CloudWatch Logs integration
# ==============================================================================

# ------------------------------------------------------------------------------
# CloudWatch Log Group
# ------------------------------------------------------------------------------
# Create log group explicitly so we can set retention
# Lambda creates this automatically, but without retention policy

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  # KMS encryption for logs (optional - costs $1/month for key)
  # kms_key_id = var.kms_key_id

  tags = merge(
    var.tags,
    {
      Name = "${var.function_name}-logs"
    }
  )
}

# Why set retention?
# - Logs are stored indefinitely by default (costs add up)
# - 7-30 days is usually sufficient for debugging
# - Older logs can be archived to S3 if needed
# - Saves cost ($0.50 per GB/month for log storage)

# ------------------------------------------------------------------------------
# Lambda Function
# ------------------------------------------------------------------------------
# The main serverless compute resource

resource "aws_lambda_function" "sync_runner" {
  function_name = var.function_name
  description   = "Syncs running data from SmashRun API to DuckDB database"

  # IAM Role
  role = var.execution_role_arn

  # Code Package - supports either local file or S3
  # Use S3 for CI/CD (GitHub Actions), local file for development
  filename         = var.package_path != null ? var.package_path : null
  source_code_hash = var.package_path != null ? filebase64sha256(var.package_path) : null
  s3_bucket        = var.s3_package_bucket
  s3_key           = var.s3_package_key
  # Note: When using S3, code updates are triggered by changing s3_key
  # Lambda workflow uploads new versions with unique keys

  # Runtime Configuration
  runtime = "python3.12"
  handler = var.handler  # Format: "filename.function_name"
  # Example: "lambda_function.handler" means:
  #   - File: lambda_function.py
  #   - Function: handler(event, context)

  # Performance Configuration
  memory_size = var.memory_size  # 128-10240 MB
  timeout     = var.timeout      # 1-900 seconds (15 minutes max)
  # More memory = more CPU = faster execution
  # But also = higher cost per second
  # 512 MB is sweet spot for most workloads

  # Architecture
  architectures = ["x86_64"]  # or ["arm64"] (Graviton2 - 20% cheaper)
  # arm64 requires all dependencies compiled for ARM
  # x86_64 is safer for compatibility

  # Environment Variables
  environment {
    variables = merge(
      {
        # Core configuration
        ENVIRONMENT    = var.environment
        S3_BUCKET_NAME = var.s3_bucket_name
        # Note: AWS_REGION is automatically provided by Lambda runtime (reserved variable)

        # Secrets Manager secret names (not the actual secrets!)
        SMASHRUN_SECRET_NAME = var.smashrun_secret_name

        # Logging configuration
        LOG_LEVEL = var.log_level

        # Feature flags
        ENABLE_SPLITS = "true"
      },
      var.extra_environment_variables
    )
  }

  # Why not put secrets in environment variables?
  # - Visible in console/CloudTrail
  # - Stored in plaintext in Terraform state
  # - Can't rotate without redeploying Lambda
  # Instead: Store secret NAME, fetch value at runtime

  # Reserved Concurrent Executions
  # Limits how many instances of this function can run simultaneously
  # reserved_concurrent_executions = var.reserved_concurrent_executions
  # Default: Unreserved (shares account limit of 1000)
  # Set to 1 to ensure only one sync runs at a time

  # Dead Letter Queue (DLQ)
  # Send failed invocations to SQS/SNS for retry/investigation
  # dead_letter_config {
  #   target_arn = var.dlq_arn
  # }

  # VPC Configuration (if Lambda needs private network access)
  # Not needed for MyRunStreak - we only call public APIs
  # dynamic "vpc_config" {
  #   for_each = var.vpc_config != null ? [var.vpc_config] : []
  #   content {
  #     subnet_ids         = vpc_config.value.subnet_ids
  #     security_group_ids = vpc_config.value.security_group_ids
  #   }
  # }

  # File System (EFS mount)
  # For persistent storage across invocations
  # Not needed - we use S3 instead
  # file_system_config {
  #   arn              = var.efs_arn
  #   local_mount_path = "/mnt/efs"
  # }

  # Tracing (X-Ray)
  # Enable if you want distributed tracing
  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  # Ephemeral Storage (/tmp directory)
  ephemeral_storage {
    size = var.ephemeral_storage_size  # 512-10240 MB
  }
  # Lambda provides /tmp directory for temporary files
  # DuckDB database is ~3 MB, plus some overhead
  # 512 MB (default) is plenty, 1024 MB gives extra buffer

  # Tags
  tags = merge(
    var.tags,
    {
      Name = var.function_name
    }
  )

  # Dependencies
  depends_on = [
    aws_cloudwatch_log_group.lambda
  ]
  # Ensure log group exists before Lambda tries to write to it
}

# ------------------------------------------------------------------------------
# Lambda Permission - API Gateway Invocation
# ------------------------------------------------------------------------------
# Allow API Gateway to invoke this Lambda function
# This is a resource-based policy (attached to Lambda, not IAM role)

resource "aws_lambda_permission" "api_gateway" {
  count = var.api_gateway_execution_arn != null ? 1 : 0

  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sync_runner.function_name
  principal     = "apigateway.amazonaws.com"

  # Source ARN restricts which API Gateway can invoke
  # Format: arn:aws:execute-api:region:account:api-id/stage/method/path
  source_arn = "${var.api_gateway_execution_arn}/*/*"
  # /*/* means any stage, any method/path
}

# Why is this needed?
# - IAM role defines what Lambda can do
# - Lambda permission defines who can invoke Lambda
# - Both are required for security

# ------------------------------------------------------------------------------
# Lambda Permission - EventBridge Invocation
# ------------------------------------------------------------------------------
# Allow EventBridge (CloudWatch Events) to invoke Lambda on schedule

resource "aws_lambda_permission" "eventbridge" {
  count = var.eventbridge_rule_arn != null ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sync_runner.function_name
  principal     = "events.amazonaws.com"

  source_arn = var.eventbridge_rule_arn
}

# ------------------------------------------------------------------------------
# Lambda Function URL (Optional)
# ------------------------------------------------------------------------------
# Direct HTTPS endpoint for Lambda (no API Gateway needed)
# Simpler but fewer features (no API keys, usage plans, etc.)

# Uncomment to enable:
# resource "aws_lambda_function_url" "sync_runner" {
#   count = var.enable_function_url ? 1 : 0
#
#   function_name      = aws_lambda_function.sync_runner.function_name
#   authorization_type = "AWS_IAM"  # Requires AWS signature
#   # authorization_type = "NONE"   # Public (dangerous!)
#
#   cors {
#     allow_origins = ["https://myrunstreak.com"]
#     allow_methods = ["POST"]
#     max_age       = 86400
#   }
# }

# Function URL vs API Gateway:
# - Function URL: Free, simple, fewer features
# - API Gateway: $3.50/M requests, rich features (API keys, throttling, etc.)
# We use API Gateway for better control

# ------------------------------------------------------------------------------
# CloudWatch Metric Alarms
# ------------------------------------------------------------------------------
# Alert on Lambda errors and throttling

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.function_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"  # 5 minutes
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "Lambda function is experiencing errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.sync_runner.function_name
  }

  alarm_actions = var.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.function_name}-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "Lambda function is being throttled"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.sync_runner.function_name
  }

  alarm_actions = var.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.function_name}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Maximum"
  threshold           = var.timeout * 1000 * 0.9  # 90% of timeout (in milliseconds)
  alarm_description   = "Lambda function is approaching timeout"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.sync_runner.function_name
  }

  alarm_actions = var.alarm_actions
}

# Why 90% of timeout?
# - Lambda approaching timeout is a warning sign
# - Might indicate performance issues
# - Better to alert before actual timeout occurs
# - Gives time to investigate and increase timeout if needed
