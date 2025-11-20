# ==============================================================================
# API Gateway Module - REST API with Security
# ==============================================================================
# This module creates a REST API Gateway with:
# - Multiple endpoints (/sync, /stats, /health)
# - API key authentication
# - Usage plans and rate limiting
# - Lambda integration
# - CloudWatch logging
# - CORS support
#
# API Gateway Pricing:
# - REST API: $3.50 per million requests
# - Data transfer: $0.09 per GB
# - CloudWatch Logs: $0.50 per GB
#
# Our estimated cost:
# - ~50 requests/month (manual syncs + monitoring)
# - Total: <$0.01/month
#
# Learning Points:
# - REST API vs HTTP API
# - Resources, methods, integrations
# - API keys and usage plans
# - Deployment and stages
# - Request/response transformations
# ==============================================================================

# ------------------------------------------------------------------------------
# REST API
# ------------------------------------------------------------------------------
# Root API Gateway resource

resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.project_name}-api-${var.environment}"
  description = "MyRunStreak.com API for syncing running data and retrieving stats"

  # Endpoint type determines how API is deployed
  endpoint_configuration {
    types = ["EDGE"]
    # EDGE: CloudFront distribution (global, fast, slightly more expensive)
    # REGIONAL: Single region (cheaper, less latency control)
    # PRIVATE: VPC only (internal APIs)
  }

  # Minimum TLS version for security
  minimum_compression_size = 1024  # Compress responses > 1KB (saves bandwidth)

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-api"
    }
  )
}

# ------------------------------------------------------------------------------
# CloudWatch Log Group for API Gateway
# ------------------------------------------------------------------------------
# API Gateway access logs (who called what, when, response codes)

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# ------------------------------------------------------------------------------
# API Gateway Account Settings (for CloudWatch Logs)
# ------------------------------------------------------------------------------
# This is ACCOUNT-WIDE, only needs to be created once per AWS account
# It grants API Gateway permission to write to CloudWatch Logs

resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}

# IAM Role for API Gateway to write CloudWatch Logs
resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${var.project_name}-api-gateway-cloudwatch-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "apigateway.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

# Attach managed policy for CloudWatch Logs
resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# ------------------------------------------------------------------------------
# Resource: /sync
# ------------------------------------------------------------------------------
# Endpoint to trigger manual sync

resource "aws_api_gateway_resource" "sync" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "sync"
}

# POST /sync method
resource "aws_api_gateway_method" "sync_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.sync.id
  http_method   = "POST"
  authorization = "NONE"  # Using API keys instead of IAM

  # Require API key
  api_key_required = true

  # Request validation
  request_parameters = {
    "method.request.header.x-api-key" = true
  }
}

# Lambda integration for POST /sync
resource "aws_api_gateway_integration" "sync_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.sync.id
  http_method = aws_api_gateway_method.sync_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn

  # Timeout: API Gateway max is 29 seconds
  timeout_milliseconds = 29000
}

# AWS_PROXY vs AWS:
# - AWS_PROXY: Lambda receives full HTTP request, returns formatted response
# - AWS: Can transform request/response in API Gateway (more control, more complex)

# Method response for POST /sync
resource "aws_api_gateway_method_response" "sync_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.sync.id
  http_method = aws_api_gateway_method.sync_post.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# Integration response
resource "aws_api_gateway_integration_response" "sync_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.sync.id
  http_method = aws_api_gateway_method.sync_post.http_method
  status_code = aws_api_gateway_method_response.sync_post_200.status_code

  depends_on = [aws_api_gateway_integration.sync_lambda]
}

# ------------------------------------------------------------------------------
# Resource: /health
# ------------------------------------------------------------------------------
# Public health check endpoint (no API key required)

resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "health"
}

# GET /health method
resource "aws_api_gateway_method" "health_get" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.health.id
  http_method   = "GET"
  authorization = "NONE"

  # No API key required for health checks
  api_key_required = false
}

# Mock integration (returns static response, no Lambda)
resource "aws_api_gateway_integration" "health_mock" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method

  type = "MOCK"

  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_method_response" "health_get_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "health_mock" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  status_code = aws_api_gateway_method_response.health_get_200.status_code

  response_templates = {
    "application/json" = jsonencode({
      status      = "healthy"
      service     = "myrunstreak-api"
      environment = var.environment
      timestamp   = "$context.requestTime"
    })
  }

  depends_on = [aws_api_gateway_integration.health_mock]
}

# ------------------------------------------------------------------------------
# CORS Configuration
# ------------------------------------------------------------------------------
# Enable cross-origin requests from web browsers

resource "aws_api_gateway_method" "sync_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.sync.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "sync_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.sync.id
  http_method = aws_api_gateway_method.sync_options.http_method

  type = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "sync_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.sync.id
  http_method = aws_api_gateway_method.sync_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "sync_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.sync.id
  http_method = aws_api_gateway_method.sync_options.http_method
  status_code = aws_api_gateway_method_response.sync_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.sync_options]
}

# ------------------------------------------------------------------------------
# API Key
# ------------------------------------------------------------------------------
# Create API key for authenticated access

resource "aws_api_gateway_api_key" "personal" {
  name        = "${var.project_name}-personal-${var.environment}"
  description = "Personal API key for MyRunStreak.com"
  enabled     = true

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Usage Plan
# ------------------------------------------------------------------------------
# Define rate limits and quotas

resource "aws_api_gateway_usage_plan" "main" {
  name        = "${var.project_name}-usage-plan-${var.environment}"
  description = "Usage plan for MyRunStreak.com API"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.main.stage_name
  }

  # Rate limiting
  throttle_settings {
    burst_limit = var.burst_limit  # Max concurrent requests
    rate_limit  = var.rate_limit   # Requests per second (sustained)
  }

  # Quota (total requests per period)
  quota_settings {
    limit  = var.quota_limit
    period = var.quota_period  # DAY, WEEK, or MONTH
  }

  tags = var.tags
}

# Associate API key with usage plan
resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.personal.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.main.id
}

# ------------------------------------------------------------------------------
# Deployment
# ------------------------------------------------------------------------------
# Deploy the API to make changes live

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  # Trigger redeployment when resources change
  triggers = {
    redeployment = sha1(jsonencode(concat([
      aws_api_gateway_resource.sync.id,
      aws_api_gateway_method.sync_post.id,
      aws_api_gateway_integration.sync_lambda.id,
      aws_api_gateway_resource.health.id,
      aws_api_gateway_method.health_get.id,
      aws_api_gateway_integration.health_mock.id,
    ], var.additional_deployment_triggers)))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.sync_lambda,
    aws_api_gateway_integration.health_mock,
  ]
}

# ------------------------------------------------------------------------------
# Stage
# ------------------------------------------------------------------------------
# Stage represents an environment (dev, prod)

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.environment

  # CloudWatch logging
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  # Execution logging
  xray_tracing_enabled = var.enable_xray_tracing

  tags = var.tags

  # Must wait for API Gateway account settings to be configured
  depends_on = [aws_api_gateway_account.main]
}

# Method settings for the stage
resource "aws_api_gateway_method_settings" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.main.stage_name
  method_path = "*/*"  # Apply to all methods

  settings {
    metrics_enabled      = true
    logging_level        = var.logging_level  # OFF, ERROR, or INFO
    data_trace_enabled   = var.environment == "dev"  # Log full request/response in dev
    throttling_burst_limit = var.burst_limit
    throttling_rate_limit  = var.rate_limit
  }
}

# ------------------------------------------------------------------------------
# CloudWatch Alarms
# ------------------------------------------------------------------------------
# Monitor API Gateway metrics

resource "aws_cloudwatch_metric_alarm" "api_4xx_errors" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-api-4xx-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "API Gateway is returning 4XX errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.main.name
    Stage   = aws_api_gateway_stage.main.stage_name
  }

  alarm_actions = var.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "api_5xx_errors" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-api-5xx-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "API Gateway is returning 5XX errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.main.name
    Stage   = aws_api_gateway_stage.main.stage_name
  }

  alarm_actions = var.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-api-latency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Average"
  threshold           = "5000"  # 5 seconds
  alarm_description   = "API Gateway latency is high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.main.name
    Stage   = aws_api_gateway_stage.main.stage_name
  }

  alarm_actions = var.alarm_actions
}
