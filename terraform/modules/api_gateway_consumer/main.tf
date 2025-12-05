# ==============================================================================
# API Gateway Consumer Module
# ==============================================================================
# This module reads shared API Gateway configuration from SSM Parameter Store
# and creates service-specific routes and Lambda integrations.
#
# The base API Gateway (REST API, stage, API key, etc.) is managed by the
# runstreak-common repository. This module only creates routes and integrations.
#
# Routes created by this module:
# - /sync (POST) - Manual sync trigger (requires API key)
# - /stats/{proxy+} (GET) - Stats queries
# - /runs (GET) - List runs
# - /runs/{proxy+} (GET) - Get specific runs
# - /sync-user (POST) - User-initiated sync
# - /auth/store-tokens (POST) - Store OAuth tokens
# - /auth/login-url (GET) - Get OAuth login URL
# - /auth/callback (POST) - OAuth callback handler
# ==============================================================================

# ------------------------------------------------------------------------------
# Read API Gateway Configuration from SSM
# ------------------------------------------------------------------------------

data "aws_ssm_parameter" "api_gateway_id" {
  name = "/runstreak/shared/${var.environment}/api-gateway-id"
}

data "aws_ssm_parameter" "api_gateway_root_resource_id" {
  name = "/runstreak/shared/${var.environment}/api-gateway-root-resource-id"
}

data "aws_ssm_parameter" "api_gateway_execution_arn" {
  name = "/runstreak/shared/${var.environment}/api-gateway-execution-arn"
}

data "aws_ssm_parameter" "api_gateway_stage_name" {
  name = "/runstreak/shared/${var.environment}/api-gateway-stage-name"
}

data "aws_ssm_parameter" "api_gateway_invoke_url" {
  name = "/runstreak/shared/${var.environment}/api-gateway-invoke-url"
}

locals {
  api_gateway_id     = data.aws_ssm_parameter.api_gateway_id.value
  root_resource_id   = data.aws_ssm_parameter.api_gateway_root_resource_id.value
  api_execution_arn  = data.aws_ssm_parameter.api_gateway_execution_arn.value
  stage_name         = data.aws_ssm_parameter.api_gateway_stage_name.value
  api_invoke_url     = data.aws_ssm_parameter.api_gateway_invoke_url.value
}

# ==============================================================================
# /sync Endpoint (Sync Lambda)
# ==============================================================================

resource "aws_api_gateway_resource" "sync" {
  rest_api_id = local.api_gateway_id
  parent_id   = local.root_resource_id
  path_part   = "sync"
}

resource "aws_api_gateway_method" "sync_post" {
  rest_api_id      = local.api_gateway_id
  resource_id      = aws_api_gateway_resource.sync.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true

  request_parameters = {
    "method.request.header.x-api-key" = true
  }
}

resource "aws_api_gateway_integration" "sync_lambda" {
  rest_api_id             = local.api_gateway_id
  resource_id             = aws_api_gateway_resource.sync.id
  http_method             = aws_api_gateway_method.sync_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.sync_lambda_invoke_arn
  timeout_milliseconds    = 29000
}

resource "aws_api_gateway_method_response" "sync_post_200" {
  rest_api_id = local.api_gateway_id
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

resource "aws_api_gateway_integration_response" "sync_lambda" {
  rest_api_id = local.api_gateway_id
  resource_id = aws_api_gateway_resource.sync.id
  http_method = aws_api_gateway_method.sync_post.http_method
  status_code = aws_api_gateway_method_response.sync_post_200.status_code

  depends_on = [aws_api_gateway_integration.sync_lambda]
}

# CORS for /sync
resource "aws_api_gateway_method" "sync_options" {
  rest_api_id   = local.api_gateway_id
  resource_id   = aws_api_gateway_resource.sync.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "sync_options" {
  rest_api_id = local.api_gateway_id
  resource_id = aws_api_gateway_resource.sync.id
  http_method = aws_api_gateway_method.sync_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "sync_options_200" {
  rest_api_id = local.api_gateway_id
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
  rest_api_id = local.api_gateway_id
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

# ==============================================================================
# /stats Endpoints (Query Lambda)
# ==============================================================================

resource "aws_api_gateway_resource" "stats" {
  rest_api_id = local.api_gateway_id
  parent_id   = local.root_resource_id
  path_part   = "stats"
}

resource "aws_api_gateway_resource" "stats_proxy" {
  rest_api_id = local.api_gateway_id
  parent_id   = aws_api_gateway_resource.stats.id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "stats_proxy_get" {
  rest_api_id   = local.api_gateway_id
  resource_id   = aws_api_gateway_resource.stats_proxy.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "stats_proxy" {
  rest_api_id             = local.api_gateway_id
  resource_id             = aws_api_gateway_resource.stats_proxy.id
  http_method             = aws_api_gateway_method.stats_proxy_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.query_lambda_invoke_arn
}

# ==============================================================================
# /runs Endpoints (Query Lambda)
# ==============================================================================

resource "aws_api_gateway_resource" "runs" {
  rest_api_id = local.api_gateway_id
  parent_id   = local.root_resource_id
  path_part   = "runs"
}

resource "aws_api_gateway_method" "runs_get" {
  rest_api_id   = local.api_gateway_id
  resource_id   = aws_api_gateway_resource.runs.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "runs_get" {
  rest_api_id             = local.api_gateway_id
  resource_id             = aws_api_gateway_resource.runs.id
  http_method             = aws_api_gateway_method.runs_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.query_lambda_invoke_arn
}

resource "aws_api_gateway_resource" "runs_proxy" {
  rest_api_id = local.api_gateway_id
  parent_id   = aws_api_gateway_resource.runs.id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "runs_proxy_get" {
  rest_api_id   = local.api_gateway_id
  resource_id   = aws_api_gateway_resource.runs_proxy.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "runs_proxy" {
  rest_api_id             = local.api_gateway_id
  resource_id             = aws_api_gateway_resource.runs_proxy.id
  http_method             = aws_api_gateway_method.runs_proxy_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.query_lambda_invoke_arn
}

# ==============================================================================
# /sync-user Endpoint (Query Lambda)
# ==============================================================================

resource "aws_api_gateway_resource" "sync_user" {
  rest_api_id = local.api_gateway_id
  parent_id   = local.root_resource_id
  path_part   = "sync-user"
}

resource "aws_api_gateway_method" "sync_user_post" {
  rest_api_id   = local.api_gateway_id
  resource_id   = aws_api_gateway_resource.sync_user.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "sync_user" {
  rest_api_id             = local.api_gateway_id
  resource_id             = aws_api_gateway_resource.sync_user.id
  http_method             = aws_api_gateway_method.sync_user_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.query_lambda_invoke_arn
}

# ==============================================================================
# /auth Endpoints (Query Lambda)
# ==============================================================================

resource "aws_api_gateway_resource" "auth" {
  rest_api_id = local.api_gateway_id
  parent_id   = local.root_resource_id
  path_part   = "auth"
}

# /auth/store-tokens
resource "aws_api_gateway_resource" "auth_store_tokens" {
  rest_api_id = local.api_gateway_id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "store-tokens"
}

resource "aws_api_gateway_method" "auth_store_tokens_post" {
  rest_api_id   = local.api_gateway_id
  resource_id   = aws_api_gateway_resource.auth_store_tokens.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_store_tokens" {
  rest_api_id             = local.api_gateway_id
  resource_id             = aws_api_gateway_resource.auth_store_tokens.id
  http_method             = aws_api_gateway_method.auth_store_tokens_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.query_lambda_invoke_arn
}

# /auth/login-url
resource "aws_api_gateway_resource" "auth_login_url" {
  rest_api_id = local.api_gateway_id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "login-url"
}

resource "aws_api_gateway_method" "auth_login_url_get" {
  rest_api_id   = local.api_gateway_id
  resource_id   = aws_api_gateway_resource.auth_login_url.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_login_url" {
  rest_api_id             = local.api_gateway_id
  resource_id             = aws_api_gateway_resource.auth_login_url.id
  http_method             = aws_api_gateway_method.auth_login_url_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.query_lambda_invoke_arn
}

# /auth/callback
resource "aws_api_gateway_resource" "auth_callback" {
  rest_api_id = local.api_gateway_id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "callback"
}

resource "aws_api_gateway_method" "auth_callback_post" {
  rest_api_id   = local.api_gateway_id
  resource_id   = aws_api_gateway_resource.auth_callback.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "auth_callback" {
  rest_api_id             = local.api_gateway_id
  resource_id             = aws_api_gateway_resource.auth_callback.id
  http_method             = aws_api_gateway_method.auth_callback_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.query_lambda_invoke_arn
}

# ==============================================================================
# Lambda Permissions for API Gateway
# ==============================================================================

resource "aws_lambda_permission" "sync_lambda_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke-${var.environment}"
  action        = "lambda:InvokeFunction"
  function_name = var.sync_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${local.api_execution_arn}/*/*"
}

resource "aws_lambda_permission" "query_lambda_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke-${var.environment}"
  action        = "lambda:InvokeFunction"
  function_name = var.query_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${local.api_execution_arn}/*/*"
}

# ==============================================================================
# Deployment Trigger
# ==============================================================================
# Creates a new deployment and updates the stage when routes change

resource "aws_api_gateway_deployment" "myrunstreak" {
  rest_api_id = local.api_gateway_id

  triggers = {
    redeployment = sha1(jsonencode([
      # Sync endpoint
      aws_api_gateway_resource.sync.id,
      aws_api_gateway_method.sync_post.id,
      aws_api_gateway_integration.sync_lambda.id,
      aws_api_gateway_method.sync_options.id,
      aws_api_gateway_integration.sync_options.id,
      # Stats endpoints
      aws_api_gateway_resource.stats.id,
      aws_api_gateway_resource.stats_proxy.id,
      aws_api_gateway_method.stats_proxy_get.id,
      aws_api_gateway_integration.stats_proxy.id,
      # Runs endpoints
      aws_api_gateway_resource.runs.id,
      aws_api_gateway_method.runs_get.id,
      aws_api_gateway_integration.runs_get.id,
      aws_api_gateway_resource.runs_proxy.id,
      aws_api_gateway_method.runs_proxy_get.id,
      aws_api_gateway_integration.runs_proxy.id,
      # Sync-user endpoint
      aws_api_gateway_resource.sync_user.id,
      aws_api_gateway_method.sync_user_post.id,
      aws_api_gateway_integration.sync_user.id,
      # Auth endpoints
      aws_api_gateway_resource.auth.id,
      aws_api_gateway_resource.auth_store_tokens.id,
      aws_api_gateway_method.auth_store_tokens_post.id,
      aws_api_gateway_integration.auth_store_tokens.id,
      aws_api_gateway_resource.auth_login_url.id,
      aws_api_gateway_method.auth_login_url_get.id,
      aws_api_gateway_integration.auth_login_url.id,
      aws_api_gateway_resource.auth_callback.id,
      aws_api_gateway_method.auth_callback_post.id,
      aws_api_gateway_integration.auth_callback.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.sync_lambda,
    aws_api_gateway_integration.sync_options,
    aws_api_gateway_integration.stats_proxy,
    aws_api_gateway_integration.runs_get,
    aws_api_gateway_integration.runs_proxy,
    aws_api_gateway_integration.sync_user,
    aws_api_gateway_integration.auth_store_tokens,
    aws_api_gateway_integration.auth_login_url,
    aws_api_gateway_integration.auth_callback,
  ]
}

# Update the stage to use the new deployment
resource "null_resource" "update_stage_deployment" {
  triggers = {
    deployment_id = aws_api_gateway_deployment.myrunstreak.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws apigateway update-stage \
        --rest-api-id ${local.api_gateway_id} \
        --stage-name ${local.stage_name} \
        --patch-operations op=replace,path=/deploymentId,value=${aws_api_gateway_deployment.myrunstreak.id} \
        --region ${var.aws_region}
    EOT
  }

  depends_on = [
    aws_api_gateway_deployment.myrunstreak,
  ]
}
